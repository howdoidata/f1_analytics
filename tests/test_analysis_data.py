"""Tests for the read-only loaders in analysis.data."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from f1_analytics.analysis.data import MissingDatabaseError, load_race_data, open_database


def test_missing_db_names_the_path_and_the_build_command(tmp_path: Path):
    missing = tmp_path / "nope.duckdb"
    with pytest.raises(MissingDatabaseError) as info:
        open_database(missing)
    message = str(info.value)
    assert str(missing) in message
    assert "uv run build" in message
    assert not missing.exists()
    with pytest.raises(FileNotFoundError):
        load_race_data(missing)


def test_load_race_data_reads_the_three_frames(tmp_path: Path):
    db_path = tmp_path / "tiny.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "CREATE TABLE results AS SELECT * FROM (VALUES "
            "(2026, 1, 'A GP', 'albon', 'Alex Albon', 'williams', 'Williams', 15, 12, 'Finished'), "
            "(2025, 1, 'A GP', 'albon', 'Alex Albon', 'williams', 'Williams', 10, 9, 'Finished')) "
            "t(season, round, race_name, driver_id, driver_name, constructor_id, constructor, grid, position, status)"
        )
        con.execute(
            "CREATE TABLE constructor_standings_by_round AS SELECT * FROM (VALUES "
            "(2026, 1, 'williams', 'Williams', 1, 4.0), (2025, 1, 'williams', 'Williams', 1, 2.0)) "
            "t(season, round, constructor_id, constructor, standing_rank, cumulative_points)"
        )
        con.execute(
            "CREATE TABLE raw_fastf1_laps AS SELECT * FROM (VALUES "
            "(2026, 1, 'ALB', 'albon', 'williams', '0 days 00:01:30.000000', 'extra')) "
            "t(season, round, Driver, driver_id, constructor_id, LapTime, Other)"
        )
    data = load_race_data(db_path, season=2026)
    assert len(data["results"]) == 2
    assert data["standings"]["season"].tolist() == [2026]
    assert list(data["laps"].columns) == ["season", "round", "Driver", "driver_id", "constructor_id", "LapTime"]
