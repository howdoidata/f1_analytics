"""Pins on the real DuckDB file `uv run build` writes from the committed data/raw/.

Locally the module skips when the file is missing; in CI (where `CI` is set and
the build step runs first) a missing file fails it. The pins are filtered to
races up to 2026 R17, so a later refresh adds rows without breaking them.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1_analytics import config
from f1_analytics.analysis.data import load_pit_stop_tables
from f1_analytics.analysis.pit_stops import backtest, forecast, incident_chance


MISSING_DB = "real DuckDB not built; run uv run build"
# Races up to 2026 R17: every committed season before 2026, and 2026 R1-17.
UP_TO_2026_R17 = "(season < 2026 OR (season = 2026 AND round <= 17))"


REQUIRED_TABLES = ("pit_stops", "weather_forecasts", "race_incidents")


def _has_required_tables(path: Path) -> bool:
    with duckdb.connect(str(path), read_only=True) as connection:
        found = {name for (name,) in connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
    return set(REQUIRED_TABLES) <= found


def require_real_db(path: Path, environ=os.environ) -> Path:
    """`path` if it exists and has `pit_stops`, `weather_forecasts` and `race_incidents`; otherwise skip, or fail when `CI` is set.

    A DB built before those marts counts as not built.
    """
    if path.exists() and _has_required_tables(path):
        return path
    if "CI" in environ:
        pytest.fail(MISSING_DB)
    pytest.skip(MISSING_DB)


@pytest.fixture(scope="module")
def conn():
    path = require_real_db(config.DUCKDB_PATH)
    with duckdb.connect(str(path), read_only=True) as connection:
        yield connection


def _one(conn, sql: str):
    return conn.execute(sql).fetchone()


def test_pit_stops_counts_every_committed_stop(conn):
    assert _one(conn, f"SELECT COUNT(*) FROM pit_stops WHERE {UP_TO_2026_R17}") == (12_881,)
    assert _one(conn, f"SELECT COUNT(*) FROM pit_stops WHERE {UP_TO_2026_R17} AND duration_s IS NULL") == (14,)
    nulls = _one(conn, "SELECT COUNT(*) FROM pit_stops WHERE season IS NULL OR round IS NULL OR driver_id IS NULL "
                       "OR constructor_id IS NULL OR stop IS NULL OR lap IS NULL OR time IS NULL OR stop_type IS NULL")
    assert nulls == (0,)


def test_every_stop_before_2018_is_unknown(conn):
    assert _one(conn, "SELECT COUNT(*) FROM pit_stops WHERE season < 2018") > (0,)
    assert _one(conn, "SELECT COUNT(*) FROM pit_stops WHERE season < 2018 AND stop_type <> 'unknown'") == (0,)


def test_2026_stop_type_split(conn):
    split = dict(conn.execute(
        "SELECT stop_type, COUNT(*) FROM pit_stops WHERE season = 2026 AND round <= 17 GROUP BY 1").fetchall())
    assert split == {"normal": 348, "sc_vsc": 274, "red_flag": 67}
    assert sum(split.values()) == 689
    # Every red-flag stop is a long one (the car waited in the pit lane).
    assert _one(conn, "SELECT MIN(duration_s) > 60 FROM pit_stops "
                      "WHERE season = 2026 AND round <= 17 AND stop_type = 'red_flag'") == (True,)


def test_car_races_and_practice_stints_rows(conn):
    assert _one(conn, f"SELECT COUNT(*) FROM car_races WHERE {UP_TO_2026_R17}") == (514,)
    assert _one(conn, "SELECT COUNT(*) FROM practice_stints WHERE season = 2026 AND round = 13 AND session = 'FP2'") == (97,)


# --- story 5: the count model on the committed data -------------------------
# Pinned from the incident covariate's decision run on the committed data/raw/
# (2026-10-20). They change only in a PR that says why.

BACKTEST_PINS = {
    # method: (mae, mae_clean, mae_incident, hit_rate, width, n); every method scored against
    # all of the team's stops, split by whether the race had a safety car or red flag
    "model": (1.71, 1.53, 1.84, 0.85, 5.25, 187),
    "circuit_history": (1.56, 1.31, 1.73, None, None, 187),
    "season_form": (1.67, 1.39, 1.87, None, None, 187),
}
TABLE_VALUES = ("mae", "mae_clean", "mae_incident", "hit_rate", "width")


@pytest.fixture(scope="module")
def tables(conn):
    return load_pit_stop_tables(config.DUCKDB_PATH)


def test_story_5_stop_pins(conn):
    assert _one(conn, "SELECT COUNT(*) FROM pit_stops WHERE season = 2026 AND round BETWEEN 1 AND 17") == (689,)
    assert _one(conn, "SELECT COUNT(*) FROM pit_stops JOIN races USING (season, round) "
                      "WHERE races.circuit_id = 'americas' AND season BETWEEN 2012 AND 2025") == (416,)


def test_every_backtest_round_has_a_day_before_forecast(conn):
    assert _one(conn, "SELECT COUNT(DISTINCT round) FROM weather_forecasts "
                      "WHERE season = 2026 AND round BETWEEN 1 AND 17 AND kind = 'day_before'") == (17,)


def test_backtest_2026_rounds_1_to_17(tables):
    table = backtest(tables, 2026, range(1, 18)).table.set_index("method")
    assert list(table.index) == list(BACKTEST_PINS)
    assert list(table.columns) == [*TABLE_VALUES, "n"]
    for method, (*values, n) in BACKTEST_PINS.items():
        row = table.loc[method]
        for column, pin in zip(TABLE_VALUES, values):
            if pin is None:
                assert pd.isna(row[column]), (method, column)
            else:
                assert round(row[column], 2) == pin, (method, column)
        assert row["n"] == n, method


def test_incident_chance_at_cota_2026_round_18(tables):
    # 12 of the 24 earlier car_races races (COTA 2018-25 and 2026 R1-17) had a safety car or red flag.
    assert round(incident_chance(tables, "americas", 2026, 18), 2) == 0.50


def test_forecast_at_cota_2026_round_18(tables):
    result = forecast(tables, "williams", "americas", 2026, 18,
                      start_compounds=["MEDIUM", "MEDIUM"], air_temp=25.0, weather="dry")
    assert result.incident_chance == incident_chance(tables, "americas", 2026, 18)
    total = result.total
    assert (total.mean, total.p10, total.p90) == (3.0, 1.0, 6.0)


# --- the skip / fail rule ----------------------------------------------------


def test_a_missing_db_skips_locally(tmp_path: Path):
    with pytest.raises(pytest.skip.Exception, match=MISSING_DB):
        require_real_db(tmp_path / "missing.duckdb", environ={})


def test_a_missing_db_fails_in_ci(tmp_path: Path):
    with pytest.raises(pytest.fail.Exception, match=MISSING_DB):
        require_real_db(tmp_path / "missing.duckdb", environ={"CI": "true"})


@pytest.mark.parametrize("environ", [{}, {"CI": ""}])
def test_a_db_without_pit_stops_counts_as_not_built(tmp_path: Path, environ):
    path = tmp_path / "old.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE results AS SELECT 1 AS x")
    expected = pytest.fail.Exception if "CI" in environ else pytest.skip.Exception
    with pytest.raises(expected, match=MISSING_DB):
        require_real_db(path, environ=environ)


@pytest.mark.parametrize("environ", [{}, {"CI": ""}])
def test_a_db_without_weather_forecasts_counts_as_not_built(tmp_path: Path, environ):
    path = tmp_path / "story4.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE pit_stops AS SELECT 1 AS x")
    expected = pytest.fail.Exception if "CI" in environ else pytest.skip.Exception
    with pytest.raises(expected, match=MISSING_DB):
        require_real_db(path, environ=environ)


@pytest.mark.parametrize("environ", [{}, {"CI": ""}])
def test_a_db_without_race_incidents_counts_as_not_built(tmp_path: Path, environ):
    path = tmp_path / "f3d04f2.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE pit_stops AS SELECT 1 AS x")
        connection.execute("CREATE TABLE weather_forecasts AS SELECT 1 AS x")
    expected = pytest.fail.Exception if "CI" in environ else pytest.skip.Exception
    with pytest.raises(expected, match=MISSING_DB):
        require_real_db(path, environ=environ)
