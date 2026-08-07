"""Build the scoped, precedence-ruled combined Kaggle+Jolpica dataset.

Scope: current-season leader identification only (2026-07-09 decision,
`docs/decisions.md`). Kaggle wins for any season/round where Kaggle has at
least one results row. Jolpica fills a season/round only where Kaggle has
zero rows there (the `jolpica_only` status in `kaggle_jolpica_coverage`).
Existing Kaggle-only curated tables (`results`, `driver_standings_by_round`,
`constructor_standings_by_round`, `final_driver_standings`,
`final_constructor_standings`) are untouched by this module.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.data_sources.kaggle_csv import coerce_numeric
from f1_analytics.data_sources.standings import compute_cumulative_standings
from f1_analytics.database.duckdb_io import connect_duckdb, log_source_load, register_source, write_dataframe


COMBINED_SOURCE_NAME = "combined_kaggle_jolpica_current_season"

COMBINED_RESULT_COLUMNS = [
    "season",
    "round",
    "race_name",
    "date",
    "driver_id",
    "driver_name",
    "constructor_id",
    "constructor",
    "grid",
    "position",
    "points",
    "laps",
    "status",
    "source",
]

REQUIRED_KAGGLE_TABLES = {"results", "races", "drivers", "constructors"}
REQUIRED_JOLPICA_TABLES = {"raw_jolpica_results"}
REQUIRED_VIEWS = {"kaggle_jolpica_coverage"}


def require_source_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Raise a clear error if Kaggle curated or raw_jolpica_* prerequisites are missing.

    `SHOW TABLES` in DuckDB lists both tables and views, so this also covers
    the `kaggle_jolpica_coverage` view.
    """
    existing = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    missing = (REQUIRED_KAGGLE_TABLES | REQUIRED_JOLPICA_TABLES | REQUIRED_VIEWS) - existing
    if missing:
        raise RuntimeError(
            "Combined dataset build requires Kaggle curated tables, raw_jolpica_* tables, and the "
            f"kaggle_jolpica_coverage view. Missing: {sorted(missing)}. Run scripts/build_f1_dataset.py "
            "and scripts/pull_jolpica_data.py first."
        )


def read_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> pd.DataFrame:
    """Read a DuckDB table or view into a DataFrame.

    Assumes the caller supplies a trusted table/view name from project-owned code.
    """
    return conn.execute(f"SELECT * FROM {table_name}").df()


def build_combined_results(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Union Kaggle results with Jolpica gap-fill results under the precedence rule.

    Kaggle rows are kept for every season/round. Jolpica rows are added only
    for season/round pairs flagged `jolpica_only` by the existing
    `kaggle_jolpica_coverage` view (Kaggle has zero rows there), reusing that
    view instead of re-deriving overlap/gap status. Each row is tagged with
    its `source` (`kaggle` or `jolpica`).
    """
    results = read_table(conn, "results")
    races = read_table(conn, "races")[["season", "round", "date"]]
    kaggle_part = results.merge(races, on=["season", "round"], how="left")
    kaggle_part["source"] = "kaggle"
    kaggle_part = kaggle_part[COMBINED_RESULT_COLUMNS]

    coverage = read_table(conn, "kaggle_jolpica_coverage")
    gap_rounds = coverage.loc[coverage["results_coverage_status"] == "jolpica_only", ["season", "round"]]

    jolpica_raw = read_table(conn, "raw_jolpica_results")
    jolpica_gap = jolpica_raw.merge(gap_rounds, on=["season", "round"], how="inner")
    jolpica_gap = coerce_numeric(jolpica_gap, ["season", "round", "grid", "position", "points", "laps"])
    jolpica_gap["date"] = pd.to_datetime(jolpica_gap["date"], errors="coerce")

    drivers = read_table(conn, "drivers")
    drivers = drivers.assign(
        driver_name=drivers["given_name"].fillna("") + " " + drivers["family_name"].fillna("")
    )[["driver_id", "driver_name"]]
    constructors = read_table(conn, "constructors")[["constructor_id", "name"]].rename(
        columns={"name": "constructor"}
    )

    jolpica_gap = jolpica_gap.merge(drivers, on="driver_id", how="left")
    jolpica_gap = jolpica_gap.merge(constructors, on="constructor_id", how="left")
    jolpica_gap["source"] = "jolpica"
    jolpica_gap = jolpica_gap[COMBINED_RESULT_COLUMNS]

    return pd.concat([kaggle_part, jolpica_gap], ignore_index=True)


def build_combined_standings(combined_results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recompute cumulative driver/constructor standings from combined_results.

    Reuses the same cumulative-points/wins/standing-rank logic as the Kaggle
    curated standings tables (`compute_cumulative_standings`) instead of a
    second, parallel implementation.
    """
    driver_standings = compute_cumulative_standings(combined_results, "driver_id", "driver_name")
    constructor_standings = compute_cumulative_standings(combined_results, "constructor_id", "constructor")
    return driver_standings, constructor_standings


def write_combined_tables(
    combined_results: pd.DataFrame,
    combined_driver_standings: pd.DataFrame,
    combined_constructor_standings: pd.DataFrame,
    *,
    db_path: Path = DUCKDB_PATH,
) -> dict[str, int]:
    tables = {
        "combined_results": combined_results,
        "combined_driver_standings_by_round": combined_driver_standings,
        "combined_constructor_standings_by_round": combined_constructor_standings,
    }
    row_counts: dict[str, int] = {}
    with connect_duckdb(db_path) as conn:
        for table_name, frame in tables.items():
            write_dataframe(conn, table_name, frame)
            log_source_load(
                conn,
                source_name=COMBINED_SOURCE_NAME,
                table_name=table_name,
                source_path=db_path,
                row_count=len(frame),
            )
            row_counts[table_name] = len(frame)

        register_source(
            conn,
            source_name=COMBINED_SOURCE_NAME,
            source_type="derived_combined",
            description=(
                "Scoped, precedence-ruled combination of Kaggle curated results and Jolpica "
                "gap-fill results for current-season leader identification only. Kaggle wins on "
                "any season/round overlap; Jolpica fills only season/rounds where Kaggle has zero rows."
            ),
            landing_tables=list(tables),
            credential_required=False,
            status="loaded",
        )

    return row_counts


def build_combined_dataset(*, db_path: Path = DUCKDB_PATH) -> dict[str, object]:
    """Build and write `combined_results` and the combined standings tables.

    Assumes `db_path` already contains Kaggle curated tables, raw_jolpica_*
    tables, and the `kaggle_jolpica_coverage` view (built by
    `scripts/build_f1_dataset.py` and `scripts/pull_jolpica_data.py`). Raises
    FileNotFoundError if the database file is missing, or RuntimeError if a
    required table/view is missing from it.
    """
    if not db_path.is_file():
        raise FileNotFoundError(f"DuckDB database missing: {db_path}. Run scripts/build_f1_dataset.py first.")

    with connect_duckdb(db_path, read_only=True) as conn:
        require_source_tables(conn)
        combined_results = build_combined_results(conn)

    combined_driver_standings, combined_constructor_standings = build_combined_standings(combined_results)
    row_counts = write_combined_tables(
        combined_results,
        combined_driver_standings,
        combined_constructor_standings,
        db_path=db_path,
    )
    return {"row_counts": row_counts}
