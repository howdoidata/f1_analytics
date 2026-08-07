"""Offline tests for the main-env FastF1 loader (Story 1.6).

Covers name mapping (incl. the unmapped-name error), stint derivation from
laps, and completeness verification against the counts sidecar. No
`fastf1` import, no network (AD-11) -- everything here reads fixture CSVs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.data_sources.fastf1_loader import (
    FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES,
    FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES,
    AmbiguousFastF1DriverCodeError,
    FastF1RaceLoadError,
    IncompleteFastF1DataError,
    UnassignedFastF1StintError,
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


def test_map_driver_ids_raises_named_error_for_an_ambiguous_code_with_no_sanctioned_override():
    # Real F1 3-letter codes are reused across eras. MAG (Jan Magnussen /
    # Kevin Magnussen) is a genuine curated-table collision with no entry
    # in FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES -- a silent drop_duplicates()
    # pick would resolve confidently to the wrong driver with no error;
    # this must raise instead.
    assert "MAG" not in FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES
    ambiguous_drivers = pd.DataFrame(
        {"driver_id": ["magnussen", "kevin_magnussen"], "code": ["MAG", "MAG"]}
    )
    laps = pd.DataFrame({"Driver": ["MAG"]})

    with pytest.raises(AmbiguousFastF1DriverCodeError) as excinfo:
        map_driver_ids(laps, ambiguous_drivers)

    assert "MAG" in str(excinfo.value)


def test_map_driver_ids_resolves_an_ambiguous_code_via_the_sanctioned_override_table():
    # VER matches both vergne and max_verstappen in the curated table
    # (fastf1-driver-code-reconciliation-decision-record.md); it must
    # resolve to the sanctioned override, never an arbitrary curated row.
    assert FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES["VER"] == "max_verstappen"
    ambiguous_drivers = pd.DataFrame(
        {"driver_id": ["vergne", "max_verstappen"], "code": ["VER", "VER"]}
    )
    laps = pd.DataFrame({"Driver": ["VER"]})

    mapped = map_driver_ids(laps, ambiguous_drivers)

    assert mapped.tolist() == ["max_verstappen"]


def test_map_driver_ids_does_not_raise_for_an_ambiguous_code_absent_from_this_races_laps():
    # A duplicate code elsewhere in the curated table that this race's
    # laps never reference (and that has no sanctioned override) must not
    # block an otherwise-clean mapping.
    assert "MAG" not in FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES
    ambiguous_drivers = pd.DataFrame(
        {
            "driver_id": ["magnussen", "kevin_magnussen", "hamilton"],
            "code": ["MAG", "MAG", "HAM"],
        }
    )
    laps = pd.DataFrame({"Driver": ["HAM"]})

    mapped = map_driver_ids(laps, ambiguous_drivers)

    assert mapped.tolist() == ["hamilton"]


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


def test_map_constructor_ids_raises_named_error_when_an_alias_target_is_absent_from_constructors():
    # A stale alias (its target id no longer present, e.g. after a curated
    # -table refresh) must not silently inject a dangling constructor_id --
    # it falls through to the same UnmappedFastF1NameError as any other
    # unresolved Team string.
    constructors_missing_alias_target = pd.DataFrame({"constructor_id": ["ferrari"], "name": ["Ferrari"]})
    laps = pd.DataFrame({"Team": ["Red Bull Racing"]})

    with pytest.raises(UnmappedFastF1NameError) as excinfo:
        map_constructor_ids(laps, constructors_missing_alias_target)

    assert "Red Bull Racing" in str(excinfo.value)


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


def test_derive_stints_raises_named_error_for_a_lap_with_no_stint_assignment(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    # FastF1 leaves some untimed/out-laps with no Stint assignment. Folding
    # those into one artificial stint per driver would span non-contiguous
    # laps under a single stint_number -- this must raise instead.
    laps, _, _ = read_race_dump(FASTF1_FIXTURE_DIR / "normal_race")
    mapped = map_laps_to_ids(laps, drivers, constructors)
    mapped["Stint"] = mapped["Stint"].astype(float)
    ver_index = mapped.index[mapped["Driver"] == "VER"][0]
    mapped.loc[ver_index, "Stint"] = None

    with pytest.raises(UnassignedFastF1StintError) as excinfo:
        derive_stints(mapped)

    assert "verstappen" in str(excinfo.value)


def test_verify_completeness_raises_named_error_for_a_driver_missing_from_landed_laps(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    # Lap/weather counts both meet the sidecar's totals here, isolating the
    # driver-roster check from the lap/weather undercount checks -- unlike
    # incomplete_laps, which conflates both failure modes in one fixture
    # and never lets this branch run independently.
    laps, weather, counts = read_race_dump(FASTF1_FIXTURE_DIR / "missing_driver")
    mapped = map_laps_to_ids(laps, drivers, constructors)

    with pytest.raises(IncompleteFastF1DataError) as excinfo:
        verify_completeness(mapped, weather, counts)

    assert "ALO" in str(excinfo.value)


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


def test_load_and_map_race_raises_named_error_when_round_is_missing_from_counts(
    tmp_path: Path, drivers: pd.DataFrame, constructors: pd.DataFrame
):
    # fastf1_fetch.py falls back to a None round when it can't read
    # RoundNumber off the FastF1 session -- a null round would otherwise
    # silently defeat the season+round join later stories depend on.
    race_dir = tmp_path / "NoRound"
    race_dir.mkdir()
    source_dir = FASTF1_FIXTURE_DIR / "normal_race"
    shutil.copy(source_dir / "laps.csv", race_dir / "laps.csv")
    shutil.copy(source_dir / "weather.csv", race_dir / "weather.csv")
    counts = json.loads((source_dir / "counts.json").read_text())
    counts["round"] = None
    (race_dir / "counts.json").write_text(json.dumps(counts))

    with pytest.raises(FastF1RaceLoadError) as excinfo:
        load_and_map_race(race_dir, drivers, constructors, label="NoRound", season=2026)

    assert "round" in str(excinfo.value)


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
