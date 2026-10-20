"""The chain fixture world builds, and holds what stories 4-6's chain test needs."""

from __future__ import annotations

from pathlib import Path

import duckdb

from chain_world import (
    CHAIN_CIRCUIT, CHAIN_EARLIER_SEASON, CHAIN_RAW, CHAIN_ROUNDS, CHAIN_SEASON, CHAIN_TEAM, make_chain_world,
)
from f1_analytics import cli


def test_chain_world_builds_with_a_non_williams_team_at_a_non_cota_circuit(tmp_path: Path):
    raw = make_chain_world(tmp_path / "raw")
    db_path = tmp_path / "chain.duckdb"
    assert cli.build(["--raw-dir", str(raw), "--db", str(db_path)]) == 0

    with duckdb.connect(str(db_path), read_only=True) as conn:
        def rows(sql, *params):
            return conn.execute(sql, list(params)).fetchall()

        assert CHAIN_TEAM != "williams" and CHAIN_CIRCUIT != "americas"
        # The team's three races in one season, and the same circuit a season earlier.
        assert rows(
            "SELECT DISTINCT season, round FROM results WHERE constructor_id = ? ORDER BY 1, 2", CHAIN_TEAM
        ) == [(CHAIN_EARLIER_SEASON, 1)] + [(CHAIN_SEASON, r) for r in CHAIN_ROUNDS]
        assert rows("SELECT season, circuit_id FROM races WHERE round = 1 ORDER BY season") == [
            (CHAIN_EARLIER_SEASON, CHAIN_CIRCUIT), (CHAIN_SEASON, CHAIN_CIRCUIT)]
        assert rows("SELECT circuit_id FROM races WHERE season = ? ORDER BY round", CHAIN_SEASON) == [
            ("bahrain",), ("jeddah",), ("albert_park",)]

        # Every stop is typed (every race has car_races rows), with all three types present.
        assert rows("SELECT COUNT(*) FROM pit_stops") == [(35,)]
        assert dict(rows("SELECT stop_type, COUNT(*) FROM pit_stops GROUP BY 1")) == {
            "normal": 24, "sc_vsc": 7, "red_flag": 4}
        # The team's stops: 2023 R2 lap 30 is in both an sc and a red_flag period.
        assert rows(
            "SELECT season, round, driver_id, lap, stop_type FROM pit_stops WHERE constructor_id = ? "
            "AND stop_type <> 'normal' ORDER BY season, round, lap, driver_id", CHAIN_TEAM
        ) == [(2022, 1, "hamilton", 47, "sc_vsc"), (2023, 1, "russell", 20, "sc_vsc"),
              (2023, 2, "hamilton", 30, "red_flag")]
        assert rows("SELECT DISTINCT duration_s FROM pit_stops WHERE stop_type = 'red_flag'") == [(72.345,)]

        assert rows(
            "SELECT COUNT(*), COUNT(DISTINCT (season, round)) FROM car_races WHERE constructor_id = ?", CHAIN_TEAM
        ) == [(8, 4)]
        assert dict(rows(
            "SELECT status, COUNT(*) FROM staging.stg_fastf1_summary__track_status_periods GROUP BY 1"
        )) == {"sc": 2, "vsc": 2, "red_flag": 1}
        assert rows(
            "SELECT season, round, session, COUNT(*) FROM practice_stints GROUP BY ALL"
        ) == [(CHAIN_SEASON, 1, "FP2", 12)]
        assert rows(
            "SELECT driver_id, stint, laps FROM practice_stints WHERE constructor_id = ? ORDER BY 1, 2", CHAIN_TEAM
        ) == [("hamilton", 1, 6), ("hamilton", 2, 14), ("russell", 1, 6), ("russell", 2, 14)]


def test_chain_tree_is_separate_and_has_no_2025_round_3():
    assert sorted(p.name for p in (CHAIN_RAW / "jolpica").iterdir()) == sorted(
        p.name for p in (CHAIN_RAW.parent / "jolpica_raw").iterdir())
    for path in CHAIN_RAW.rglob("*.csv"):
        assert "2025," not in path.read_text(), path
