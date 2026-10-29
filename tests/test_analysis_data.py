"""Tests for the read-only loaders in analysis.data."""

from __future__ import annotations

import inspect
import re
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1_analytics.analysis import data
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


class _RecordingConnection:
    """Stands in for a DuckDB connection: records every SQL text, returns empty frames."""

    def __init__(self):
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        return self

    def df(self) -> pd.DataFrame:
        return pd.DataFrame()


def _public_loaders():
    return [
        fn for name, fn in inspect.getmembers(data, inspect.isfunction)
        if name.startswith("load_") and fn.__module__ == data.__name__
    ]


def test_there_are_six_public_loaders_and_each_declares_its_tables():
    loaders = _public_loaders()
    assert sorted(fn.__name__ for fn in loaders) == [
        "load_constructor_standings", "load_laps", "load_pit_stop_tables",
        "load_race_data", "load_results", "load_standings_tables",
    ]
    for fn in loaders:
        assert isinstance(getattr(fn, "reads", None), frozenset) and fn.reads, fn.__name__


@pytest.mark.parametrize("loader", _public_loaders(), ids=lambda fn: fn.__name__)
def test_each_loader_declares_exactly_the_tables_its_sql_names(loader, monkeypatch):
    con = _RecordingConnection()

    @contextmanager
    def fake_open(db_path=None):
        yield con

    monkeypatch.setattr(data, "open_database", fake_open)
    params = inspect.signature(loader).parameters
    args = {"con": con, "season": 2026, "db_path": Path("unused.duckdb")}
    loader(**{name: args[name] for name in params if name in args})
    named = {
        table for sql in con.sql
        for table in re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_]\w*)", sql, flags=re.IGNORECASE)
    }
    assert con.sql, f"{loader.__name__} ran no SQL"
    assert named == set(loader.reads)
