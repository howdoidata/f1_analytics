"""Smoke tests proving the Kaggle CSV fixtures are well-formed before anything depends on them."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kaggle_csv"

EXPECTED_COLUMNS = {
    "f1_races.csv": ["season", "round", "race_name", "circuit_id", "date", "time", "url"],
    "f1_results.csv": [
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
    ],
    "f1_drivers.csv": ["driver_id", "given_name", "family_name", "dob", "nationality", "number", "code", "url"],
    "f1_constructors.csv": ["constructor_id", "name", "nationality", "url"],
    "f1_driver_standings.csv": ["season", "position", "points", "wins", "driver_id", "constructor"],
    "f1_constructor_standings.csv": ["season", "position", "points", "wins", "constructor_id", "constructor"],
    "f1_circuits.csv": ["circuit_id", "circuit_name", "locality", "country", "lat", "lng", "url"],
    "f1_qualifying.csv": ["season", "round", "driver_id", "constructor_id", "position", "q1", "q2", "q3"],
}


@pytest.mark.parametrize("filename", sorted(EXPECTED_COLUMNS))
def test_fixture_csv_has_expected_columns(filename: str):
    frame = pd.read_csv(FIXTURE_DIR / filename)
    assert list(frame.columns) == EXPECTED_COLUMNS[filename]
    assert len(frame) > 0


def test_fixture_has_a_driver_whose_constructor_name_changes_between_rows():
    driver_standings = pd.read_csv(FIXTURE_DIR / "f1_driver_standings.csv")
    constructor_names_by_driver = driver_standings.groupby("driver_id")["constructor"].nunique()
    assert (constructor_names_by_driver > 1).any()
