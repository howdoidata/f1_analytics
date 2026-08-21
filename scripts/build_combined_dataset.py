#!/usr/bin/env python3
"""Build the current-season combined tables via the Kaggle/Jolpica coverage arbiter (Story 1.7).

Two-phase, mirroring `pull_fastf1_data.py`: subprocess-invoke the isolated
pandas-<3.0 `jolpica_fetch.py` half to pull the season's Jolpica race
results (the FastF1 3.8.3 Ergast-compatible client, per the source-adoption
decision record), then hand its dumped CSV to the main-env
`jolpica_loader.py` half to shape and id-validate it. Creates the
`kaggle_jolpica_coverage` view (the single AD-2 arbiter, sql/), builds
`combined_results` by applying its status tags -- Kaggle rows win every
season/round except `jolpica_only` -- and builds combined driver/
constructor standings by handing `combined_results` to the existing
`standings.compute_cumulative_standings()` (no parallel standings
computation). Every write goes through the existing replace-sync helper
(AD-4). A `row_count_diverges` round never resolves silently: this script
names it explicitly in its own printed output.

A live Jolpica fetch failure (subprocess error, incomplete pagination,
etc.) is reported by name and degrades to zero Jolpica rows for this run
rather than aborting the build -- the coverage view still tags every
season/round correctly from whatever landed, mirroring
`pull_fastf1_data.py`'s "one source's failure never blocks the rest"
posture -- but the run EXITS 1, so a caller can distinguish it from a
clean build. The one case that does abort: if a failed fetch would leave
a previously-landed `raw_jolpica_results` in place (`refuse_regression`
declining the 0-row write), the run raises rather than silently
republishing those stale rows as this run's current-season data. A
merely PARTIAL fetch still reuses the better previous table, since there
the source was actually reached. Decisions recorded 2026-08-20.
posture. Only a genuinely MISSING curated prerequisite table
(`results`/`races`/`drivers`/`constructors`) is a hard, pre-write failure
(mirrors `require_curated_tables()` in `pull_fastf1_data.py`).

After writes, runs Story 1.8's advisory null-rate/referential-integrity
validations against curated + `combined_results` tables (not the two
`*_standings_by_round` tables -- no registry entry checks them) and logs
`source_load` rows for both kaggle and jolpica. A failing check is
printed but never changes this script's exit code (AD-8:
advisory-and-logged).

Run from the repository root:

    uv run scripts/build_combined_dataset.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import duckdb
import pandas as pd

from f1_analytics.config import DUCKDB_PATH, FASTF1_CACHE_DIR, JOLPICA_RAW_DIR
from f1_analytics.data_sources.jolpica_loader import (
    JolpicaResultsLoadError,
    empty_shaped_results,
    load_and_map_season_results,
)
from f1_analytics.data_sources.standings import compute_cumulative_standings
from f1_analytics.database.duckdb_io import WriteRegressionError, connect_duckdb, write_dataframe
from f1_analytics.validation.checks import run_validations
from f1_analytics.validation.runner import load_present_tables, print_validation_findings
from f1_analytics.validation.store import log_source_load, log_validation_results


ROOT = Path(__file__).resolve().parents[1]
FETCH_SCRIPT_PATH = ROOT / "src" / "f1_analytics" / "data_sources" / "jolpica_fetch.py"
COVERAGE_VIEW_SQL_PATH = ROOT / "sql" / "kaggle_jolpica_coverage.sql"
FETCH_TIMEOUT_SECONDS = 300
SEASON = 2026

REQUIRED_CURATED_TABLES = ("results", "races", "drivers", "constructors")
# Columns build_combined_standings() merges from races -- table existence
# alone (require_curated_tables) doesn't guarantee these are present.
REQUIRED_RACES_COLUMNS = ("season", "round", "date", "time", "circuit_id", "url")

# Curated tables (Story 1.5) plus this run's own combined_results
# extension (Story 1.7) -- exactly what checks.NULL_RATE_CHECKS/
# REFERENTIAL_CHECKS reference for this script. Deliberately excludes
# combined_driver_standings_by_round/combined_constructor_standings_by_round
# -- no registry entry checks them (see deferred-work.md).
VALIDATION_TABLES: tuple[str, ...] = (
    "results",
    "drivers",
    "constructors",
    "final_driver_standings",
    "races",
    "circuits",
    "combined_results",
)

# AD-2's five-status vocabulary; combined_results reads these tags,
# never recomputes the comparison.
KAGGLE_WINS_STATUSES = ("match", "kaggle_only", "row_count_diverges")
JOLPICA_FILLS_STATUS = "jolpica_only"
DIVERGES_STATUS = "row_count_diverges"
NO_DATA_STATUS = "no_data"
# The complete AD-2 vocabulary, asserted against what the view actually emits.
# The five statuses are declared twice with no shared source of truth -- as SQL
# string literals in `kaggle_jolpica_coverage.sql`'s CASE, and as the Python
# constants above. A rename on either side would make the tag filters below
# match nothing and silently drop whole rounds from `combined_results` and the
# standings -- exactly the silent resolution this story's own posture forbids.
# Checking here converts that drift from silent data loss into a named failure.
KNOWN_COVERAGE_STATUSES = frozenset(KAGGLE_WINS_STATUSES) | {JOLPICA_FILLS_STATUS, NO_DATA_STATUS}

# Output columns of the two standings tables, used only to shape the
# zero-row frames the empty-combined_results path returns, so a degenerate
# build still writes tables with the same schema a populated one produces.
EMPTY_DRIVER_STANDINGS_COLUMNS = [
    "season", "round", "race_name", "date", "driver_id", "driver_name",
    "race_points", "race_wins", "cumulative_points", "cumulative_wins",
    "standing_rank", "source",
]
EMPTY_CONSTRUCTOR_STANDINGS_COLUMNS = [
    "season", "round", "race_name", "date", "constructor_id", "constructor",
    "race_points", "race_wins", "cumulative_points", "cumulative_wins",
    "standing_rank", "source",
]

FetchFn = Callable[[int, Path], dict]


def require_curated_tables(conn, db_path: Path) -> None:
    """Fail fast with a named error if Story 1.5's curated tables aren't landed yet.

    Mirrors `pull_fastf1_data.require_curated_tables()`.
    """
    existing = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    missing = [table for table in REQUIRED_CURATED_TABLES if table not in existing]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"Missing curated table(s) in {db_path}: {missing_list}. "
            "Run scripts/build_f1_dataset.py (Story 1.5) first."
        )


def require_races_columns(races: pd.DataFrame, db_path: Path) -> None:
    """Fail fast with a named error if `races` is missing columns `build_combined_standings` needs.

    Table-existence alone (`require_curated_tables`) doesn't guarantee
    schema -- a present-but-incomplete `races` table must still fail before
    any write, not surface as a raw `KeyError` from deep inside a merge.
    """
    missing = [column for column in REQUIRED_RACES_COLUMNS if column not in races.columns]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(f"races table in {db_path} is missing column(s): {missing_list}.")


def run_fetch_subprocess(season: int, cache_dir: Path, output_dir: Path) -> dict:
    """Invoke jolpica_fetch.py in the isolated pandas-<3.0 environment.

    Mirrors `pull_fastf1_data.run_fetch_subprocess`: FastF1 pins
    `pandas>=2.1.1,<3.0.0`, so this isolated subprocess -- never a
    project-wide pandas downgrade -- is the source-adoption decision
    record's sanctioned fallback.
    """
    command = [
        "uv",
        "run",
        "--isolated",
        "--python",
        "3.13",
        "--with",
        "fastf1==3.8.3",
        "python",
        str(FETCH_SCRIPT_PATH),
        "--season",
        str(season),
        "--cache-dir",
        str(cache_dir),
        "--output-dir",
        str(output_dir),
    ]
    try:
        # mkdir failures (permission denied, disk full, ...) are a live-
        # source hiccup like any other here -- a statused failure, never a
        # crash that takes down the whole build.
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=FETCH_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        return {
            "season": season,
            "status": "failed",
            "exception": f"TimeoutExpired: fetch exceeded {FETCH_TIMEOUT_SECONDS}s",
        }
    except Exception as error:  # Live-subprocess invocation can raise diverse failure types.
        return {"season": season, "status": "failed", "exception": f"{type(error).__name__}: {error}"}

    try:
        result = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        result = {}
    if not isinstance(result, dict):
        # Valid JSON that isn't an object (a bare list/number/string) is
        # just as unusable as a parse failure -- treat it the same way
        # rather than letting a later `result.get(...)` raise AttributeError.
        result = {}

    # "empty" is a legitimate, non-error outcome (jolpica_fetch.py's own
    # contract for a genuinely rowless season) and already carries its own
    # row_count -- it must never be overwritten into a fabricated "failed"
    # status with a misleading synthesized exception message.
    if result.get("status") not in ("pass", "empty"):
        result.setdefault("season", season)
        result.setdefault("status", "failed")
        result.setdefault(
            "exception",
            f"fetch subprocess exited {completed.returncode}: {completed.stderr.strip()[-2000:]}",
        )
    return result


def build_fetch(cache_dir: Path) -> FetchFn:
    def fetch(season: int, output_dir: Path) -> dict:
        return run_fetch_subprocess(season, cache_dir, output_dir)

    return fetch


def load_jolpica_results(
    season: int,
    season_dir: Path,
    fetch_result: dict,
    drivers: pd.DataFrame,
    constructors: pd.DataFrame,
) -> pd.DataFrame:
    """Load one season's Jolpica results if the fetch landed data; degrade to empty otherwise.

    A live-source hiccup (fetch failure, or a genuinely rowless season) is
    reported by name here but never aborts the build -- the coverage view
    still tags correctly from whatever landed, and any round that was truly
    `jolpica_only` in reality simply reads as `no_data` this run instead
    (absent from `combined_results`, per the I/O matrix -- not a corrupted
    or guessed row).
    """
    status = fetch_result.get("status")
    if status == "empty":
        print(f"[build_combined_dataset] Jolpica reports season {season} has zero rows so far (not a failure)")
        return empty_shaped_results()
    if status != "pass":
        detail = fetch_result.get("exception", fetch_result)
        print(f"[build_combined_dataset] Jolpica fetch did not land season {season} data: {detail}")
        return empty_shaped_results()

    try:
        return load_and_map_season_results(season_dir, drivers, constructors, season=season)
    except JolpicaResultsLoadError as error:
        print(f"[build_combined_dataset] Jolpica load failed: {error}")
        return empty_shaped_results()


def build_combined_results(
    coverage: pd.DataFrame,
    kaggle_results: pd.DataFrame,
    jolpica_results: pd.DataFrame,
) -> pd.DataFrame:
    """Apply AD-2 precedence by reading the coverage view's own status tags.

    Kaggle rows win every season/round tagged `match`/`kaggle_only`/
    `row_count_diverges`; Jolpica rows fill only `jolpica_only` rounds. The
    comparison itself was already computed by the view -- this function
    only reads its tags, never recomputes them (AD-2's single-arbiter
    rule).

    The coverage view's own `status` column is renamed to `coverage_status`
    before merging: both `kaggle_results` and `jolpica_results` already
    carry their own per-row `status` (race classification, e.g. "Finished"/
    "Retired"), and merging two same-named columns would otherwise silently
    rename them to `status_x`/`status_y` instead of raising.
    """
    unknown_statuses = sorted(set(coverage["status"].dropna()) - KNOWN_COVERAGE_STATUSES)
    if unknown_statuses:
        raise RuntimeError(
            f"kaggle_jolpica_coverage emitted status(es) outside the AD-2 vocabulary: "
            f"{', '.join(unknown_statuses)}. Expected one of: {', '.join(sorted(KNOWN_COVERAGE_STATUSES))}. "
            "The view's CASE and this script's status constants have drifted apart; "
            "rounds carrying an unrecognized tag would otherwise be dropped silently."
        )

    round_status = coverage[["season", "round", "status"]].rename(columns={"status": "coverage_status"})

    tagged_kaggle = kaggle_results.merge(round_status, on=["season", "round"], how="inner")
    kaggle_rows = (
        tagged_kaggle[tagged_kaggle["coverage_status"].isin(KAGGLE_WINS_STATUSES)]
        .drop(columns=["coverage_status"])
        .copy()
    )
    kaggle_rows["source"] = "kaggle"

    tagged_jolpica = jolpica_results.merge(round_status, on=["season", "round"], how="inner")
    jolpica_rows = (
        tagged_jolpica[tagged_jolpica["coverage_status"] == JOLPICA_FILLS_STATUS]
        .drop(columns=["coverage_status"])
        .copy()
    )
    jolpica_rows["source"] = "jolpica"

    combined = pd.concat([kaggle_rows, jolpica_rows], ignore_index=True)
    return combined.sort_values(["season", "round"], kind="stable").reset_index(drop=True)


def build_combined_standings(combined_results: pd.DataFrame, races: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Derive combined driver/constructor standings via the one shared standings function.

    Enriches `combined_results` with `races`' date/circuit metadata --
    exactly like `kaggle_csv.build_curated_tables` enriches curated results
    before standings -- then calls `compute_cumulative_standings()`
    unmodified for both driver and constructor standings (no parallel
    standings computation, per this story's Boundaries). Each round's
    `source` is uniform across all of its rows (AD-2 precedence resolves a
    whole round to one source), so it is safe to merge back onto the
    per-round standings rows afterward.
    """
    # A fully-empty `combined_results` (every round `no_data`: curated
    # `results` empty and Jolpica landed nothing -- a realistic pre-season or
    # first-run state) cannot go through `compute_cumulative_standings`: the
    # empty-frame `groupby(...).apply(...)` in `add_standing_rank` returns a
    # DataFrame rather than a Series and raises `ValueError: Cannot set a
    # DataFrame with multiple columns to the single column standing_rank`.
    # That raise landed AFTER `raw_jolpica_results` and `combined_results`
    # were already written, leaving the two standings tables missing -- the
    # partial-write-then-crash class this script's fail-fast discipline
    # exists to prevent. Typing the empty frame's columns does not avoid it
    # (verified), so the empty case is answered here instead of pushing a
    # degenerate frame through the shared standings function.
    if combined_results.empty:
        return (
            pd.DataFrame(columns=EMPTY_DRIVER_STANDINGS_COLUMNS),
            pd.DataFrame(columns=EMPTY_CONSTRUCTOR_STANDINGS_COLUMNS),
        )

    enriched = combined_results.merge(
        races[["season", "round", "date", "time", "circuit_id", "url"]],
        on=["season", "round"],
        how="left",
        suffixes=("", "_race"),
    )
    round_source = combined_results.drop_duplicates(subset=["season", "round"])[["season", "round", "source"]]

    driver_standings = compute_cumulative_standings(enriched, "driver_id", "driver_name").merge(
        round_source, on=["season", "round"], how="left"
    )
    constructor_standings = compute_cumulative_standings(enriched, "constructor_id", "constructor").merge(
        round_source, on=["season", "round"], how="left"
    )
    return driver_standings, constructor_standings


def print_row_count_diverges_deviations(coverage: pd.DataFrame) -> None:
    """Name every row_count_diverges round explicitly -- never silently resolved (AD-2)."""
    diverging = coverage[coverage["status"] == DIVERGES_STATUS].sort_values(["season", "round"])
    if diverging.empty:
        print("[build_combined_dataset] no row_count_diverges deviations")
        return

    print(f"[build_combined_dataset] row_count_diverges deviations ({len(diverging)} round(s), Kaggle rows kept):")
    for _, row in diverging.iterrows():
        print(
            f"  season {int(row['season'])} round {int(row['round'])}: "
            f"kaggle={int(row['kaggle_row_count'])} jolpica={int(row['jolpica_row_count'])}"
        )


def load_curated_tables(db_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Open `db_path` read-only and return `(results, races, drivers, constructors)`.

    A database file that doesn't exist at all yet (Story 1.5's build script
    never ran) and one that exists but is missing a required table are the
    same class of missing prerequisite from this story's point of view --
    both must fail fast with a clear, named error, never a raw
    `duckdb.IOException` surfacing from deep inside `connect_duckdb` for the
    former case.
    """
    try:
        with connect_duckdb(db_path, read_only=True) as conn:
            require_curated_tables(conn, db_path)
            kaggle_results = conn.execute("SELECT * FROM results").fetch_df()
            races = conn.execute("SELECT * FROM races").fetch_df()
            drivers = conn.execute("SELECT * FROM drivers").fetch_df()
            constructors = conn.execute("SELECT * FROM constructors").fetch_df()
            require_races_columns(races, db_path)
    except duckdb.Error as error:
        raise RuntimeError(
            f"Cannot read curated tables from {db_path}: {error}. "
            "Run scripts/build_f1_dataset.py (Story 1.5) first."
        ) from error
    return kaggle_results, races, drivers, constructors


def main(
    season: int = SEASON,
    db_path: Path = DUCKDB_PATH,
    jolpica_raw_dir: Path = JOLPICA_RAW_DIR,
    fastf1_cache_dir: Path = FASTF1_CACHE_DIR,
    fetch: FetchFn | None = None,
) -> int:
    if fetch is None:
        fetch = build_fetch(fastf1_cache_dir)

    kaggle_results, races, drivers, constructors = load_curated_tables(db_path)

    season_dir = jolpica_raw_dir / str(season)
    fetch_result = fetch(season, season_dir)
    jolpica_results = load_jolpica_results(season, season_dir, fetch_result, drivers, constructors)

    with connect_duckdb(db_path) as conn:
        # raw_jolpica_results is written even when empty on a table's first
        # write: kaggle_jolpica_coverage.sql joins against it every run, so
        # it must always exist first. On every later run, refuse_regression
        # guards against a degraded/partial fetch overwriting a previously
        # more-complete table -- if refused, the existing (better) table is
        # reused for the rest of this run instead of degrading to it.
        try:
            write_dataframe(conn, "raw_jolpica_results", jolpica_results, refuse_regression=True)
        except WriteRegressionError as error:
            # Reuse is only honest when the fetch actually SUCCEEDED and simply
            # landed fewer rows (a partial/incomplete pagination): the source
            # was reached, so the previously-landed table is still the better
            # answer for this run. When the fetch FAILED outright there is no
            # new evidence at all, and silently re-publishing the previous
            # run's rows under `source = "jolpica"` makes a broken run
            # indistinguishable from a clean one -- the run reports current
            # -season coverage it did not actually obtain. Decision 2026-08-20
            # (Antonio): fail loud rather than paper over it with stale data.
            if fetch_result.get("status") == "failed":
                raise RuntimeError(
                    f"Jolpica fetch failed and the previously-landed raw_jolpica_results "
                    f"({error}) would be silently republished as this run's current-season "
                    f"data. Refusing: this run obtained no new Jolpica evidence. Re-run once "
                    f"the source is reachable, or drop raw_jolpica_results to rebuild without it."
                ) from error
            print(f"[build_combined_dataset] {error}; reusing the previously-landed table for this run")
            jolpica_results = conn.execute("SELECT * FROM raw_jolpica_results").fetch_df()

        conn.execute(COVERAGE_VIEW_SQL_PATH.read_text())
        coverage = conn.execute("SELECT * FROM kaggle_jolpica_coverage").fetch_df()

        combined_results = build_combined_results(coverage, kaggle_results, jolpica_results)
        write_dataframe(conn, "combined_results", combined_results)

        driver_standings, constructor_standings = build_combined_standings(combined_results, races)
        write_dataframe(conn, "combined_driver_standings_by_round", driver_standings)
        write_dataframe(conn, "combined_constructor_standings_by_round", constructor_standings)

        # Advisory validation (Story 1.8, AD-8): runs after this script's
        # own writes above -- a failing check is printed and logged but
        # never changes this script's exit code.
        tables = load_present_tables(conn, list(VALIDATION_TABLES))
        validation_frame = run_validations(tables)
        log_validation_results(conn, validation_frame)
        print_validation_findings("build_combined_dataset", validation_frame)

        # combined_results is fully rebuilt every run, so these counts
        # always reflect this run's own write -- never a stale figure from
        # an earlier run.
        kaggle_row_count = int((combined_results["source"] == "kaggle").sum()) if len(combined_results) else 0
        jolpica_row_count = int((combined_results["source"] == "jolpica").sum()) if len(combined_results) else 0
        log_source_load(conn, "kaggle", "combined_results", kaggle_row_count)
        log_source_load(conn, "jolpica", "combined_results", jolpica_row_count)

    print_row_count_diverges_deviations(coverage)

    print(
        f"[build_combined_dataset] combined_results: {len(combined_results)} row(s) "
        f"({kaggle_row_count} kaggle, {jolpica_row_count} jolpica)"
    )
    print(
        f"[build_combined_dataset] combined_driver_standings_by_round: {len(driver_standings)} row(s); "
        f"combined_constructor_standings_by_round: {len(constructor_standings)} row(s)"
    )

    # Decision 2026-08-20 (Antonio): a failed Jolpica fetch exits non-zero.
    # The build still degrades rather than aborting -- combined tables are
    # rebuilt from whatever landed, so "one source's failure never blocks the
    # rest" still holds for the DATA -- but the run is no longer reported as
    # clean. Previously this returned a bare 0, so a cron/CI wrapper could not
    # tell a failed fetch from a good one. Mirrors `pull_fastf1_data.main`'s
    # `0 if landed else 1`. `empty` is a legitimate outcome (a season with no
    # races yet), not a failure; per AD-8 advisory validation findings still
    # never affect the exit code.
    if fetch_result.get("status") == "failed":
        print(
            "[build_combined_dataset] exiting 1: the Jolpica fetch failed. Combined tables were "
            "rebuilt from whatever landed, but this run did not obtain current-season Jolpica data."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
