"""Read-only loaders for the analysis and the reports.

This is the only analysis module that touches DuckDB. Every other module takes
the DataFrames these functions return, so tests can pass synthetic frames.

Every public loader declares the marts it reads with `@reads(...)` (its
`fn.reads`); `f1_analytics.mart_check` follows each report's imports to the
loaders it names and checks those tables against the mart tags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TypeVar

import duckdb
import pandas as pd

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.database.duckdb_io import connect_duckdb


F = TypeVar("F", bound=Callable)


def reads(*tables: str) -> Callable[[F], F]:
    """Declare the marts a loader reads: sets `fn.reads` to `tables` as a frozenset."""

    def mark(fn: F) -> F:
        fn.reads = frozenset(tables)
        return fn

    return mark


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


@reads("results")
def load_results(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Every race result, all seasons."""
    return con.execute(
        "SELECT season, round, race_name, driver_id, driver_name, constructor_id, constructor, "
        "grid, position, status FROM results ORDER BY season, round, position"
    ).df()


@reads("constructor_standings_by_round")
def load_constructor_standings(con: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    """Constructor standings after every round of `season`."""
    return con.execute(
        "SELECT season, round, constructor_id, constructor, standing_rank, cumulative_points "
        "FROM constructor_standings_by_round WHERE season = ? ORDER BY round, standing_rank",
        [season],
    ).df()


@reads("raw_fastf1_laps")
def load_laps(con: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    """FastF1 laps of `season` (only the columns the analysis uses)."""
    return con.execute(
        "SELECT season, round, Driver, driver_id, constructor_id, LapTime "
        "FROM raw_fastf1_laps WHERE season = ?",
        [season],
    ).df()


@reads(
    "driver_standings_by_round", "constructor_standings_by_round",
    "final_driver_standings", "final_constructor_standings",
)
def load_standings_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """The four standings marts the championship-leader analysis reads."""
    return {
        "driver_standings": con.execute("SELECT * FROM driver_standings_by_round").df(),
        "constructor_standings": con.execute("SELECT * FROM constructor_standings_by_round").df(),
        "driver_final": con.execute("SELECT * FROM final_driver_standings").df(),
        "constructor_final": con.execute("SELECT * FROM final_constructor_standings").df(),
    }


@reads(*(load_results.reads | load_constructor_standings.reads | load_laps.reads))
def load_race_data(db_path: Path = DUCKDB_PATH, season: int = 2026) -> dict[str, pd.DataFrame]:
    """Results (all seasons), constructor standings and laps (`season`) in one read-only pass."""
    with open_database(db_path) as con:
        return {
            "results": load_results(con),
            "standings": load_constructor_standings(con, season),
            "laps": load_laps(con, season),
        }


WEATHER_FORECAST_COLUMNS = [
    "season", "round", "kind", "hour_utc", "endpoint", "fetched_at", "race_start_utc",
    "precipitation_probability", "precipitation_mm", "air_temp",
]


def _no_weather_forecasts() -> pd.DataFrame:
    return pd.DataFrame(columns=WEATHER_FORECAST_COLUMNS)


RACE_INCIDENT_COLUMNS = ["season", "round", "incident"]


def _no_race_incidents() -> pd.DataFrame:
    return pd.DataFrame(columns=RACE_INCIDENT_COLUMNS)


STOP_RULE_COLUMNS = ["circuit_id", "from_season", "dry_minimum"]


def _no_stop_rules() -> pd.DataFrame:
    return pd.DataFrame(columns=STOP_RULE_COLUMNS)


@dataclass(frozen=True)
class PitStopTables:
    """The ten marts the pit-stop analysis reads, one DataFrame each.

    `weather_forecasts`, `race_incidents` and `stop_rules` default to empty
    frames, so callers that build the tables by hand and need no forecasts,
    incidents or circuit stop rules can leave them out.
    """

    races: pd.DataFrame
    results: pd.DataFrame
    constructors: pd.DataFrame
    circuits: pd.DataFrame
    pit_stops: pd.DataFrame
    car_races: pd.DataFrame
    practice_stints: pd.DataFrame
    weather_forecasts: pd.DataFrame = field(default_factory=_no_weather_forecasts)
    race_incidents: pd.DataFrame = field(default_factory=_no_race_incidents)
    stop_rules: pd.DataFrame = field(default_factory=_no_stop_rules)


@reads(*PitStopTables.__dataclass_fields__)
def load_pit_stop_tables(db_path: Path = DUCKDB_PATH) -> PitStopTables:
    """Every row of the ten pit-stop marts, in one read-only pass."""
    with open_database(db_path) as con:
        return PitStopTables(**{
            name: con.execute(f"SELECT * FROM {name}").df()
            for name in PitStopTables.__dataclass_fields__
        })
