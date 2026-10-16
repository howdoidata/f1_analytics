"""`uv run build` and `uv run refresh`.

- `build` turns `data/raw/` into the DuckDB file. It is offline: it reads only
  the committed CSVs, needs no credentials, and never imports `fastf1`.
- `refresh` checks the F1TV token first, then appends newly published rounds
  from Jolpica, fetches the FastF1 extract of every completed round that lacks
  one, and finally runs `build`.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from f1_analytics.config import DUCKDB_PATH, FASTF1_CACHE_DIR, RAW_DATA_DIR
from f1_analytics.data_sources.fastf1_loader import FastF1RaceLoadError, load_extracts
from f1_analytics.data_sources.jolpica_loader import build_curated_tables, read_jolpica_raw
from f1_analytics.database.duckdb_io import (
    WriteRegressionError,
    existing_row_count,
    connect_duckdb,
    write_dataframe,
)
from f1_analytics.validation.checks import run_validations
from f1_analytics.validation.runner import load_present_tables, print_validation_findings
from f1_analytics.validation.store import log_source_load, log_validation_results


LOGIN_COMMAND = "python -m fastf1 auth f1tv --authenticate"

# Tables fed by data that only ever grows; a build that would shrink one
# means a raw file was truncated or lost, so the write is refused.
REGRESSION_GUARDED_TABLES = frozenset(
    {"results", "sprint_results", "qualifying", "raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather"}
)
# Append-only logs (validation/store.py), kept across builds.
LOG_TABLES = frozenset({"validation_results", "source_registry", "source_load_log"})
VALIDATION_TABLES = (
    "results",
    "drivers",
    "constructors",
    "final_driver_standings",
    "races",
    "circuits",
    "raw_fastf1_laps",
    "raw_fastf1_stints",
    "raw_fastf1_weather",
)


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------


def build_tables(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Every DuckDB table, built from `raw_dir` only."""
    tables = build_curated_tables(read_jolpica_raw(raw_dir / "jolpica"))
    extracts = load_extracts(raw_dir / "fastf1", tables["drivers"], tables["constructors"])
    tables["raw_fastf1_laps"] = extracts["laps"]
    tables["raw_fastf1_stints"] = extracts["stints"]
    tables["raw_fastf1_weather"] = extracts["weather"]
    return tables


def _drop_stale_objects(conn, keep: set[str]) -> list[str]:
    """Drop tables/views a previous pipeline left behind, so the DB mirrors `data/raw/`."""
    rows = conn.execute(
        "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    dropped = []
    for name, table_type in rows:
        if name in keep or name in LOG_TABLES:
            continue
        conn.execute(f'DROP {"VIEW" if table_type == "VIEW" else "TABLE"} IF EXISTS "{name}"')
        dropped.append(name)
    return sorted(dropped)


def run_build(raw_dir: Path = RAW_DATA_DIR, db_path: Path = DUCKDB_PATH, *, log: Callable[[str], None] = print) -> int:
    tables = build_tables(raw_dir)
    # With no FastF1 extracts at all, the raw_fastf1_* frames have no columns
    # and there is no table to write.
    tables = {name: frame for name, frame in tables.items() if len(frame.columns)}
    with connect_duckdb(db_path) as conn:
        # Check every guarded table before writing any, so a refused build
        # leaves the previous database whole.
        # A guarded table already landed but absent from this build counts as 0 rows.
        for name in sorted(REGRESSION_GUARDED_TABLES):
            existing = existing_row_count(conn, name)
            new_count = len(tables[name]) if name in tables else 0
            if existing is not None and new_count < existing:
                raise WriteRegressionError(
                    f"{name}: this write has {new_count} row(s), fewer than the "
                    f"{existing} row(s) already landed -- refusing to replace"
                )
        for name, frame in tables.items():
            write_dataframe(conn, name, frame)
        dropped = _drop_stale_objects(conn, set(tables))

        validation = run_validations(load_present_tables(conn, list(VALIDATION_TABLES)))
        log_validation_results(conn, validation)
        print_validation_findings("build", validation)
        for name, frame in tables.items():
            if name.startswith("raw_fastf1_"):
                log_source_load(conn, "fastf1", name, len(frame))
            else:
                log_source_load(conn, "jolpica", name, len(frame))

    log(f"[build] DuckDB built: {db_path}")
    for name, frame in tables.items():
        log(f"[build]   {name}: {len(frame)} row(s)")
    if dropped:
        log(f"[build] dropped stale table(s)/view(s): {', '.join(dropped)}")
    return 0


def build(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build", description="Build the DuckDB file from data/raw/ (offline).")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--db", type=Path, default=DUCKDB_PATH)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run_build(args.raw_dir, args.db)
    except (FileNotFoundError, FastF1RaceLoadError) as error:
        print(f"[build] {error}", file=sys.stderr)
        return 1
    except WriteRegressionError as error:
        print(f"[build] {error}. If the raw data shrank on purpose, delete {args.db} and rebuild.", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------
# refresh
# --------------------------------------------------------------------------


class TokenError(RuntimeError):
    """The F1TV token is missing, unreadable, malformed, or expired."""


def default_token_path() -> Path:
    """FastF1's token file. Resolved without `ensure_exists`, so the check creates nothing."""
    import platformdirs

    return Path(platformdirs.user_data_dir("fastf1")) / "f1auth.json"


def check_token(token_path: Path | None = None, *, now: float | None = None) -> str:
    """Return the F1TV token if it decodes as a JWT whose `exp` is in the future.

    Offline only: the signature is not verified and
    `fastf1.internals.f1auth` (which creates directories and calls the
    network) is never imported. The file holds a raw JWT, not JSON.
    """
    import jwt

    path = token_path or default_token_path()
    try:
        token = path.read_text().strip()
    except OSError as error:
        raise TokenError(f"no readable F1TV token at {path} ({type(error).__name__})") from error
    if not token:
        raise TokenError(f"F1TV token file {path} is empty")
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as error:
        raise TokenError(f"F1TV token at {path} is not a valid JWT ({type(error).__name__})") from error
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        raise TokenError(f"F1TV token at {path} has no expiry")
    if exp <= (time.time() if now is None else now):
        raise TokenError(f"F1TV token at {path} expired")
    return token


def missing_extract_rounds(raw_dir: Path, season: int, today: date | None = None) -> list[tuple[int, str]]:
    """Completed rounds of `season` with results but no FastF1 extract: `[(round, dir_name)]`."""
    from f1_analytics.data_sources.fastf1_fetch import round_dir_name
    from f1_analytics.data_sources.jolpica_fetch import completed_rounds, read_raw_table

    races = read_raw_table(raw_dir / "jolpica", "races")
    names = {
        int(round_): race_name
        for season_, round_, race_name in zip(races["season"], races["round"], races["raceName"])
        if int(season_) == season
    }
    season_dir = raw_dir / "fastf1" / str(season)
    missing = []
    for round_ in completed_rounds(raw_dir / "jolpica", season, today):
        # Any `<RR>-*` folder with a counts.json counts, so a renamed race is not refetched.
        if not any(season_dir.glob(f"{round_:02d}-*/counts.json")):
            missing.append((round_, round_dir_name(round_, names[round_])))
    return missing


def refresh(
    argv: Sequence[str] | None = None,
    *,
    token_path: Path | None = None,
    raw_dir: Path = RAW_DATA_DIR,
    db_path: Path = DUCKDB_PATH,
    cache_dir: Path = FASTF1_CACHE_DIR,
    jolpica_client=None,
    fetch_race=None,
    today: date | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="refresh", description="Check the F1TV token, update Jolpica and FastF1 raw data, then build."
    )
    parser.parse_args(sys.argv[1:] if argv is None else argv)

    # 1. The token, before any request or write.
    try:
        token = check_token(token_path)
    except TokenError as error:
        print(f"[refresh] {error}.", file=sys.stderr)
        print(f"[refresh] Log in to F1TV, then rerun:\n\n    {LOGIN_COMMAND}\n", file=sys.stderr)
        return 1

    from f1_analytics.data_sources import fastf1_fetch, jolpica_fetch

    # 2. Jolpica: append newly published rounds.
    client = jolpica_client or jolpica_fetch.JolpicaClient()
    update = jolpica_fetch.update_raw_dir(raw_dir / "jolpica", client)
    appended = ", ".join(f"{s} R{r}" for s, r in update["appended"]) or "none"
    print(f"[refresh] Jolpica rounds appended: {appended}")

    # 3. FastF1: every completed round of the latest season lacking an extract.
    results = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "results")
    season = int(pd.to_numeric(results["season"]).max())
    fetch_race = fetch_race or fastf1_fetch.fetch_race
    failed = []
    missing = missing_extract_rounds(raw_dir, season, today)
    if not missing:
        print(f"[refresh] FastF1: every completed {season} round has an extract")
    for round_, dir_name in missing:
        outcome = fetch_race(season, round_, cache_dir, raw_dir / "fastf1" / str(season) / dir_name, token)
        status = outcome.get("status")
        if status == "pass":
            print(
                f"[refresh] FastF1 {season} R{round_} ({dir_name}): {outcome.get('lap_count')} laps, "
                f"{outcome.get('weather_count')} weather rows"
            )
        else:
            failed.append(round_)
            detail = outcome.get("exception") or f"{outcome.get('lap_count', 0)} laps"
            print(f"[refresh] FastF1 {season} R{round_} ({dir_name}): FAILED ({status}) -- {detail}", file=sys.stderr)

    # 4. Build from the updated raw data.
    run_build(raw_dir, db_path)
    if failed:
        print(f"[refresh] {len(failed)} round(s) failed: {', '.join(f'R{r}' for r in failed)}", file=sys.stderr)
        return 1
    return 0
