"""Read-only loaders for the analysis and the reports.

This is the only analysis module that touches DuckDB. Every other module takes
the DataFrames these functions return, so tests can pass synthetic frames.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.database.duckdb_io import connect_duckdb


class MissingDatabaseError(FileNotFoundError):
    """The DuckDB file the analysis reads has not been built yet."""


def open_database(db_path: Path = DUCKDB_PATH) -> duckdb.DuckDBPyConnection:
    """Open the DuckDB file read-only, or say how to build it."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise MissingDatabaseError(
            f"No DuckDB file at {db_path}. Build it first with `uv run build`."
        )
    return connect_duckdb(db_path, read_only=True)


def load_results(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Every race result, all seasons."""
    return con.execute(
        "SELECT season, round, race_name, driver_id, driver_name, constructor_id, constructor, "
        "grid, position, status FROM results ORDER BY season, round, position"
    ).df()


def load_constructor_standings(con: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    """Constructor standings after every round of `season`."""
    return con.execute(
        "SELECT season, round, constructor_id, constructor, standing_rank, cumulative_points "
        "FROM constructor_standings_by_round WHERE season = ? ORDER BY round, standing_rank",
        [season],
    ).df()


def load_laps(con: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    """FastF1 laps of `season` (only the columns the analysis uses)."""
    return con.execute(
        "SELECT season, round, Driver, driver_id, constructor_id, LapTime "
        "FROM raw_fastf1_laps WHERE season = ?",
        [season],
    ).df()


def load_standings_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """The four standings marts the championship-leader analysis reads."""
    return {
        "driver_standings": con.execute("SELECT * FROM driver_standings_by_round").df(),
        "constructor_standings": con.execute("SELECT * FROM constructor_standings_by_round").df(),
        "driver_final": con.execute("SELECT * FROM final_driver_standings").df(),
        "constructor_final": con.execute("SELECT * FROM final_constructor_standings").df(),
    }


def load_race_data(db_path: Path = DUCKDB_PATH, season: int = 2026) -> dict[str, pd.DataFrame]:
    """Results (all seasons), constructor standings and laps (`season`) in one read-only pass."""
    with open_database(db_path) as con:
        return {
            "results": load_results(con),
            "standings": load_constructor_standings(con, season),
            "laps": load_laps(con, season),
        }
