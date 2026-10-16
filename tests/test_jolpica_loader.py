"""Offline tests for shaping the committed Jolpica CSVs into curated tables.

Fixtures: `tests/fixtures/jolpica_raw/` -- a two-season, two-round world in the
same CSV layout as `data/raw/jolpica/`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.data_sources.jolpica_fetch import read_raw_table, write_raw_table
from f1_analytics.data_sources.jolpica_loader import (
    NUMERIC_FLOAT_COLUMNS,
    NUMERIC_INT_COLUMNS,
    RESULTS_COLUMNS,
    InvalidJolpicaSeasonOrRoundError,
    UnresolvedJolpicaIdError,
    build_curated_tables,
    read_jolpica_raw,
    shape_constructors,
    shape_drivers,
    shape_results,
    validate_ids,
)


RAW_DIR = Path(__file__).parent / "fixtures" / "jolpica_raw"


@pytest.fixture
def raw() -> dict[str, pd.DataFrame]:
    return read_jolpica_raw(RAW_DIR)


@pytest.fixture
def curated(raw) -> dict[str, pd.DataFrame]:
    return build_curated_tables(raw)


def test_read_jolpica_raw_names_a_missing_file(tmp_path: Path):
    shutil.copytree(RAW_DIR, tmp_path / "jolpica")
    (tmp_path / "jolpica" / "qualifying.csv").unlink()
    with pytest.raises(FileNotFoundError, match="qualifying.csv"):
        read_jolpica_raw(tmp_path / "jolpica")


def test_shape_results_maps_ergast_columns_to_curated_results_columns(raw):
    shaped = shape_results(raw["results"])

    assert list(shaped.columns) == RESULTS_COLUMNS
    row = shaped[(shaped["season"] == 2024) & (shaped["round"] == 1) & (shaped["driver_id"] == "verstappen")].iloc[0]
    assert row["driver_name"] == "Max Verstappen"
    assert row["constructor"] == "Red Bull"
    assert row["constructor_id"] == "red_bull"
    assert row["points"] == 25
    assert row["position"] == 1
    assert row["fastest_lap"] == 55
    assert row["fastest_lap_rank"] == 1
    assert row["time"] == "1:31:44.742"
    assert row["race_name"] == "Bahrain Grand Prix"


def test_shape_results_dtypes_match_the_curated_table(raw):
    shaped = shape_results(raw["results"])
    for column in NUMERIC_INT_COLUMNS:
        assert str(shaped[column].dtype) == "Int64", column
    # fastest_lap/fastest_lap_rank are DOUBLE in curated results; points is fractional.
    for column in NUMERIC_FLOAT_COLUMNS:
        assert str(shaped[column].dtype) == "Float64", column
    assert {"points", "fastest_lap", "fastest_lap_rank"} <= set(NUMERIC_FLOAT_COLUMNS)


def test_shape_results_preserves_half_points(raw):
    results = raw["results"].copy()
    results.loc[results["round"] == "1", "points"] = "12.5"
    shaped = shape_results(results)
    assert len(shaped) == len(results)
    assert set(shaped.loc[shaped["round"] == 1, "points"]) == {12.5}


@pytest.mark.parametrize("column", ["season", "round"])
def test_shape_results_raises_named_error_for_a_non_numeric_season_or_round(raw, column):
    results = raw["results"].copy()
    results.loc[0, column] = "not-a-number"
    with pytest.raises(InvalidJolpicaSeasonOrRoundError, match="verstappen"):
        shape_results(results)


def test_validate_ids_names_an_unresolved_driver_and_constructor(raw):
    drivers = shape_drivers(raw["drivers"])
    constructors = shape_constructors(raw["constructors"])
    shaped = shape_results(raw["results"])

    ghost_driver = shaped.copy()
    ghost_driver.loc[0, "driver_id"] = "ghost"
    with pytest.raises(UnresolvedJolpicaIdError, match="driver id\\(s\\): ghost"):
        validate_ids(ghost_driver, drivers, constructors)

    ghost_team = shaped.copy()
    ghost_team.loc[0, "constructor_id"] = pd.NA
    with pytest.raises(UnresolvedJolpicaIdError, match="<missing constructor_id value>"):
        validate_ids(ghost_team, drivers, constructors)


def test_build_rejects_a_result_whose_driver_is_missing_from_drivers_csv(tmp_path: Path):
    shutil.copytree(RAW_DIR, tmp_path / "jolpica")
    drivers = read_raw_table(tmp_path / "jolpica", "drivers")
    write_raw_table(tmp_path / "jolpica", "drivers", drivers[drivers["driverId"] != "alonso"])
    with pytest.raises(UnresolvedJolpicaIdError, match="results: .*alonso"):
        build_curated_tables(read_jolpica_raw(tmp_path / "jolpica"))


def test_curated_tables_keep_the_columns_the_analysis_reads(curated):
    assert list(curated["races"].columns) == ["season", "round", "race_name", "circuit_id", "date", "time", "url"]
    assert list(curated["drivers"].columns) == [
        "driver_id", "given_name", "family_name", "dob", "nationality", "number", "code", "url"]
    assert list(curated["constructors"].columns) == ["constructor_id", "name", "nationality", "url"]
    assert list(curated["circuits"].columns) == ["circuit_id", "circuit_name", "locality", "country", "lat", "lng", "url"]
    assert list(curated["qualifying"].columns) == [
        "season", "round", "driver_id", "constructor_id", "position", "q1", "q2", "q3"]
    assert list(curated["final_driver_standings"].columns) == [
        "season", "position", "points", "wins", "driver_id", "constructor", "driver_name", "constructor_id"]
    assert list(curated["final_constructor_standings"].columns) == [
        "season", "position", "points", "wins", "constructor_id", "constructor"]
    assert list(curated["sprint_results"].columns) == RESULTS_COLUMNS


def test_final_standings_are_the_official_jolpica_table_not_a_derivation(curated):
    final = curated["final_driver_standings"]
    season_2025 = final[final["season"] == 2025].set_index("driver_id")
    assert season_2025.loc["hamilton", "position"] == 1
    assert season_2025.loc["hamilton", "points"] == 51
    assert season_2025.loc["alonso", "constructor"] == "Alpine"
    assert season_2025.loc["alonso", "constructor_id"] == "alpine"
    assert season_2025.loc["alonso", "driver_name"] == "Fernando Alonso"


def test_final_driver_standings_keep_the_first_of_several_constructors(tmp_path: Path):
    shutil.copytree(RAW_DIR, tmp_path / "jolpica")
    standings = read_raw_table(tmp_path / "jolpica", "final_driver_standings")
    standings.loc[standings["driverId"] == "alonso", "constructorIds"] = "aston_martin;alpine"
    write_raw_table(tmp_path / "jolpica", "final_driver_standings", standings)
    final = build_curated_tables(read_jolpica_raw(tmp_path / "jolpica"))["final_driver_standings"]
    assert set(final.loc[final["driver_id"] == "alonso", "constructor_id"]) == {"aston_martin"}


def test_by_round_standings_add_sprint_points_but_not_sprint_wins(curated):
    driver = curated["driver_standings_by_round"]
    r2 = driver[(driver["season"] == 2025) & (driver["round"] == 2)].set_index("driver_id")
    # Race 25 + sprint 8 for Hamilton; race 18 + sprint 7 for Verstappen.
    assert r2.loc["hamilton", "race_points"] == 33
    assert r2.loc["verstappen", "race_points"] == 25
    assert r2.loc["hamilton", "cumulative_points"] == 51
    assert r2.loc["hamilton", "standing_rank"] == 1
    # Hamilton won both the race and the sprint; only the race counts as a win.
    assert r2.loc["hamilton", "race_wins"] == 1
    constructor = curated["constructor_standings_by_round"]
    c2 = constructor[(constructor["season"] == 2025) & (constructor["round"] == 2)].set_index("constructor_id")
    assert c2.loc["mercedes", "cumulative_points"] == 51


def test_by_round_standings_date_comes_from_races(curated):
    driver = curated["driver_standings_by_round"]
    first = driver[(driver["season"] == 2024) & (driver["round"] == 1)].iloc[0]
    assert str(first["date"]) == "2024-03-02"
