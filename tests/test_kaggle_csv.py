"""Tests for Kaggle CSV loading, fail-fast, and curated-table construction (AC 1, 2, 3, 4)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from f1_analytics.data_sources.kaggle_csv import (
    RAW_FILES,
    build_curated_tables,
    read_raw_csvs,
    require_raw_files,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kaggle_csv"

CURATED_TABLE_COLUMNS = {
    "races": {"season", "round", "race_name", "circuit_id", "date", "time", "url"},
    "results": {
        "season",
        "round",
        "race_name",
        "driver_id",
        "driver_name",
        "constructor_id",
        "constructor",
        "grid",
        "position",
        "points",
        "laps",
        "status",
        "time",
        "fastest_lap",
        "fastest_lap_rank",
    },
    "drivers": {"driver_id", "given_name", "family_name", "dob", "nationality", "number", "code", "url"},
    "constructors": {"constructor_id", "name", "nationality", "url"},
    "circuits": {"circuit_id", "circuit_name", "locality", "country", "lat", "lng", "url"},
    "qualifying": {"season", "round", "driver_id", "constructor_id", "position", "q1", "q2", "q3"},
    "race_results_enriched": {
        "season",
        "round",
        "race_name",
        "driver_id",
        "driver_name",
        "constructor_id",
        "constructor",
        "points",
        "position",
        "date",
    },
    "driver_standings_by_round": {
        "season",
        "round",
        "race_name",
        "date",
        "driver_id",
        "driver_name",
        "cumulative_points",
        "cumulative_wins",
        "standing_rank",
    },
    "constructor_standings_by_round": {
        "season",
        "round",
        "race_name",
        "date",
        "constructor_id",
        "constructor",
        "cumulative_points",
        "cumulative_wins",
        "standing_rank",
    },
    "final_driver_standings": {"season", "position", "points", "wins", "driver_id", "constructor", "constructor_id"},
    "final_constructor_standings": {"season", "position", "points", "wins", "constructor_id", "constructor"},
}


def test_require_raw_files_raises_with_missing_filename_named(tmp_path: Path):
    for filename in RAW_FILES.values():
        shutil.copy(FIXTURE_DIR / filename, tmp_path / filename)
    (tmp_path / "f1_circuits.csv").unlink()

    with pytest.raises(FileNotFoundError) as excinfo:
        require_raw_files(tmp_path)

    assert "f1_circuits.csv" in str(excinfo.value)


def test_build_curated_tables_produces_all_expected_tables_and_columns():
    raw = read_raw_csvs(FIXTURE_DIR)
    curated = build_curated_tables(raw)

    assert set(curated) == set(CURATED_TABLE_COLUMNS)
    for table_name, expected_columns in CURATED_TABLE_COLUMNS.items():
        assert expected_columns.issubset(set(curated[table_name].columns)), table_name
        assert len(curated[table_name]) > 0, table_name


def test_constructor_id_reconciliation_resolves_every_row_including_a_constructor_change():
    raw = read_raw_csvs(FIXTURE_DIR)
    curated = build_curated_tables(raw)

    final_driver_standings = curated["final_driver_standings"].set_index(["season", "driver_id"])
    assert final_driver_standings.loc[(2024, "verstappen"), "constructor_id"] == "red_bull"
    assert final_driver_standings.loc[(2024, "alonso"), "constructor_id"] == "aston_martin"
    assert final_driver_standings.loc[(2025, "alonso"), "constructor_id"] == "alpine"

    assert curated["final_driver_standings"]["constructor_id"].notna().all()
