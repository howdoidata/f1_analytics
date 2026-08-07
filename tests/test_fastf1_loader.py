"""Offline tests for the main-env FastF1 loader (Story 1.6).

Covers name mapping (incl. the unmapped-name error), stint derivation from
laps, and completeness verification against the counts sidecar. No
`fastf1` import, no network (AD-11) -- everything here reads fixture CSVs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.data_sources.fastf1_loader import (
    FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES,
    FastF1RaceLoadError,
    IncompleteFastF1DataError,
    UnmappedFastF1NameError,
    derive_stints,
    load_and_map_race,
    map_constructor_ids,
    map_driver_ids,
    map_laps_to_ids,
    read_race_dump,
    verify_completeness,
)


FASTF1_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "fastf1_csv"
KAGGLE_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kaggle_csv"


@pytest.fixture
def drivers() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_drivers.csv")


@pytest.fixture
def constructors() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_constructors.csv")


def test_read_race_dump_loads_laps_weather_and_counts():
    laps, weather, counts = read_race_dump(FASTF1_FIXTURE_DIR / "normal_race")

    assert len(laps) == 6
    assert len(weather) == 2
    assert counts["lap_count"] == 6
    assert counts["drivers"] == ["ALO", "HAM", "VER"]


def test_read_race_dump_raises_named_error_for_missing_dump_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError) as excinfo:
        read_race_dump(tmp_path)

    assert "laps.csv" in str(excinfo.value)


def test_map_driver_ids_resolves_by_code_never_by_driver_number(drivers: pd.DataFrame):
    # DriverNumber values are deliberately swapped relative to the real
    # numbers (VER=1, HAM=44) so a mapping that mistakenly used
    # DriverNumber instead of the Driver code would resolve the wrong ids.
    laps = pd.DataFrame({"Driver": ["VER", "HAM"], "DriverNumber": [44, 1]})

    mapped = map_driver_ids(laps, drivers)

    assert mapped.tolist() == ["verstappen", "hamilton"]


def test_map_driver_ids_raises_named_error_for_unmapped_code(drivers: pd.DataFrame):
    laps = pd.DataFrame({"Driver": ["VER", "ZZZ"]})

    with pytest.raises(UnmappedFastF1NameError) as excinfo:
        map_driver_ids(laps, drivers)

    assert "ZZZ" in str(excinfo.value)


def test_map_driver_ids_raises_named_error_for_a_nan_driver_value_instead_of_dropping_the_row(
    drivers: pd.DataFrame,
):
    # A NaN Driver must not silently land a null driver_id -- it's treated
    # as unresolved too, named distinctly from an unresolved-but-present
    # string.
    laps = pd.DataFrame({"Driver": ["VER", None]})

    with pytest.raises(UnmappedFastF1NameError) as excinfo:
        map_driver_ids(laps, drivers)

    assert "<missing Driver value>" in str(excinfo.value)


def test_map_constructor_ids_raises_named_error_for_unmapped_team(constructors: pd.DataFrame):
    laps = pd.DataFrame({"Team": ["Red Bull", "Unknown Racing"]})

    with pytest.raises(UnmappedFastF1NameError) as excinfo:
        map_constructor_ids(laps, constructors)

    assert "Unknown Racing" in str(excinfo.value)


def test_map_constructor_ids_resolves_by_exact_name_match(constructors: pd.DataFrame):
    # "Aston Martin" matches constructors.name exactly -- no alias needed.
    laps = pd.DataFrame({"Team": ["Aston Martin"]})

    mapped = map_constructor_ids(laps, constructors)

    assert mapped.tolist() == ["aston_martin"]


def test_map_constructor_ids_falls_back_to_the_sanctioned_alias_table(constructors: pd.DataFrame):
    # "Red Bull Racing" has no exact constructors.name match (curated name
    # is "Red Bull"); resolves via FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES per
    # fastf1-constructor-name-reconciliation-decision-record.md.
    assert "Red Bull Racing" in FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES
    laps = pd.DataFrame({"Team": ["Red Bull Racing"]})

    mapped = map_constructor_ids(laps, constructors)

    assert mapped.tolist() == ["red_bull"]


def test_map_constructor_ids_raises_named_error_when_neither_exact_nor_alias_resolves(
    constructors: pd.DataFrame,
):
    # A string absent from both constructors.name and the alias table must
    # still raise -- the alias table is a fixed list, never a fuzzy match.
    laps = pd.DataFrame({"Team": ["Aston Martin", "Red Bull Racing", "Some New Team"]})

    with pytest.raises(UnmappedFastF1NameError) as excinfo:
        map_constructor_ids(laps, constructors)

    assert "Some New Team" in str(excinfo.value)
    assert "Aston Martin" not in str(excinfo.value)
    assert "Red Bull Racing" not in str(excinfo.value)


def test_map_constructor_ids_raises_named_error_for_a_nan_team_value_instead_of_dropping_the_row(
    constructors: pd.DataFrame,
):
    # A NaN Team must not be looked up in the alias table (it can't match a
    # string key) and must not silently land a null constructor_id either.
    laps = pd.DataFrame({"Team": ["Aston Martin", None]})

    with pytest.raises(UnmappedFastF1NameError) as excinfo:
        map_constructor_ids(laps, constructors)

    assert "<missing Team value>" in str(excinfo.value)


def test_map_constructor_ids_resolves_all_four_sanctioned_aliases_against_real_curated_names():
    # Real curated constructors.name spellings from the decision record's
    # evidence table -- deliberately not the shared kaggle_csv fixture,
    # which happens to already spell "Alpine" without the "F1 Team" suffix
    # (so it resolves via the exact-match branch there) and doesn't carry
    # cadillac/rb at all. This exercises every alias-fallback row for real.
    real_constructors = pd.DataFrame(
        {
            "constructor_id": ["alpine", "cadillac", "rb", "red_bull"],
            "name": ["Alpine F1 Team", "Cadillac F1 Team", "RB F1 Team", "Red Bull"],
        }
    )
    laps = pd.DataFrame({"Team": ["Alpine", "Cadillac", "Racing Bulls", "Red Bull Racing"]})

    mapped = map_constructor_ids(laps, real_constructors)

    assert mapped.tolist() == ["alpine", "cadillac", "rb", "red_bull"]


def test_map_laps_to_ids_adds_both_id_columns(drivers: pd.DataFrame, constructors: pd.DataFrame):
    laps, _, _ = read_race_dump(FASTF1_FIXTURE_DIR / "normal_race")

    mapped = map_laps_to_ids(laps, drivers, constructors)

    assert mapped.loc[mapped["Driver"] == "VER", "driver_id"].unique().tolist() == ["verstappen"]
    assert mapped.loc[mapped["Team"] == "Red Bull", "constructor_id"].unique().tolist() == ["red_bull"]
    assert mapped["driver_id"].notna().all()
    assert mapped["constructor_id"].notna().all()


def test_derive_stints_groups_by_driver_and_stint_with_lap_bounds(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    laps, _, _ = read_race_dump(FASTF1_FIXTURE_DIR / "normal_race")
    mapped = map_laps_to_ids(laps, drivers, constructors)

    stints = derive_stints(mapped)

    ver_stint_1 = stints[(stints["driver_id"] == "verstappen") & (stints["stint_number"] == 1)].iloc[0]
    assert ver_stint_1["compound"] == "SOFT"
    assert ver_stint_1["lap_start"] == 1
    assert ver_stint_1["lap_end"] == 2
    assert ver_stint_1["lap_count"] == 2
    assert ver_stint_1["constructor_id"] == "red_bull"

    ver_stint_2 = stints[(stints["driver_id"] == "verstappen") & (stints["stint_number"] == 2)].iloc[0]
    assert ver_stint_2["compound"] == "MEDIUM"
    assert ver_stint_2["lap_start"] == 3
    assert ver_stint_2["lap_end"] == 3
    assert ver_stint_2["lap_count"] == 1

    assert len(stints) == 4  # VER x2 stints, HAM x1, ALO x1


def test_verify_completeness_passes_when_landed_matches_sidecar(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    laps, weather, counts = read_race_dump(FASTF1_FIXTURE_DIR / "normal_race")
    mapped = map_laps_to_ids(laps, drivers, constructors)

    verify_completeness(mapped, weather, counts)  # must not raise


def test_verify_completeness_raises_named_error_when_laps_undercount_sidecar(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    laps, weather, counts = read_race_dump(FASTF1_FIXTURE_DIR / "incomplete_laps")
    mapped = map_laps_to_ids(laps, drivers, constructors)

    with pytest.raises(IncompleteFastF1DataError) as excinfo:
        verify_completeness(mapped, weather, counts)

    assert "4" in str(excinfo.value) and "6" in str(excinfo.value)


def test_verify_completeness_raises_named_error_when_weather_undercounts_sidecar(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    laps, weather, counts = read_race_dump(FASTF1_FIXTURE_DIR / "normal_race")
    mapped = map_laps_to_ids(laps, drivers, constructors)
    inflated_counts = {**counts, "weather_count": counts["weather_count"] + 5}

    with pytest.raises(IncompleteFastF1DataError) as excinfo:
        verify_completeness(mapped, weather, inflated_counts)

    assert "weather" in str(excinfo.value)
    assert str(len(weather)) in str(excinfo.value)
    assert str(inflated_counts["weather_count"]) in str(excinfo.value)


def test_load_and_map_race_happy_path_returns_all_three_tagged_frames(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    result = load_and_map_race(
        FASTF1_FIXTURE_DIR / "normal_race", drivers, constructors, label="Normal", season=2026
    )

    assert set(result) == {"laps", "stints", "weather"}
    assert (result["laps"]["race_label"] == "Normal").all()
    assert (result["laps"]["season"] == 2026).all()
    assert (result["stints"]["race_label"] == "Normal").all()
    assert (result["weather"]["race_label"] == "Normal").all()
    assert len(result["laps"]) == 6
    assert len(result["weather"]) == 2
    # `round` (from the counts sidecar) lets Story 1.7/Epic 2 join back to
    # the curated `races` table, which is keyed on season+round, not label.
    assert (result["laps"]["round"] == 1).all()
    assert (result["stints"]["round"] == 1).all()
    assert (result["weather"]["round"] == 1).all()


def test_load_and_map_race_raises_named_error_for_unmapped_driver(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    with pytest.raises(FastF1RaceLoadError) as excinfo:
        load_and_map_race(
            FASTF1_FIXTURE_DIR / "unmapped_driver",
            drivers,
            constructors,
            label="UnmappedDriver",
            season=2026,
        )

    assert "ZZZ" in str(excinfo.value)
    assert "UnmappedDriver" in str(excinfo.value)


def test_load_and_map_race_raises_named_error_for_incomplete_laps(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    with pytest.raises(FastF1RaceLoadError) as excinfo:
        load_and_map_race(
            FASTF1_FIXTURE_DIR / "incomplete_laps",
            drivers,
            constructors,
            label="Incomplete",
            season=2026,
        )

    assert "Incomplete" in str(excinfo.value)


def test_load_and_map_race_wraps_a_corrupt_counts_json_instead_of_crashing_the_run(
    tmp_path: Path, drivers: pd.DataFrame, constructors: pd.DataFrame
):
    # A malformed counts.json (json.JSONDecodeError) or malformed CSV must
    # become a per-race FastF1RaceLoadError too -- not an uncaught crash
    # that would abort every remaining race in the orchestrator's loop.
    race_dir = tmp_path / "CorruptCounts"
    race_dir.mkdir()
    source_dir = FASTF1_FIXTURE_DIR / "normal_race"
    shutil.copy(source_dir / "laps.csv", race_dir / "laps.csv")
    shutil.copy(source_dir / "weather.csv", race_dir / "weather.csv")
    (race_dir / "counts.json").write_text("{not valid json")

    with pytest.raises(FastF1RaceLoadError) as excinfo:
        load_and_map_race(race_dir, drivers, constructors, label="CorruptCounts", season=2026)

    assert "CorruptCounts" in str(excinfo.value)
