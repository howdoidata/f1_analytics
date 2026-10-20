"""Pins on the real DuckDB file `uv run build` writes from the committed data/raw/.

Locally the module skips when the file is missing; in CI (where `CI` is set and
the build step runs first) a missing file fails it. The pins are filtered to
races up to 2026 R17, so a later refresh adds rows without breaking them.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

from f1_analytics import config


MISSING_DB = "real DuckDB not built; run uv run build"
# Races up to 2026 R17: every committed season before 2026, and 2026 R1-17.
UP_TO_2026_R17 = "(season < 2026 OR (season = 2026 AND round <= 17))"


def _has_pit_stops(path: Path) -> bool:
    with duckdb.connect(str(path), read_only=True) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'pit_stops'"
        ).fetchone()[0] > 0


def require_real_db(path: Path, environ=os.environ) -> Path:
    """`path` if it exists and has `pit_stops`; otherwise skip, or fail when `CI` is set.

    A DB built before the pit-stop marts counts as not built.
    """
    if path.exists() and _has_pit_stops(path):
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
