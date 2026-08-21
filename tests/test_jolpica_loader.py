"""Offline tests for the main-env Jolpica loader (Story 1.7).

Covers column shaping into curated `results`'s shape, id validation against
curated drivers/constructors (incl. the unresolved-id and missing-value
errors), and completeness verification against the counts sidecar. No
`fastf1` import, no network (AD-11) -- everything here reads fixture CSVs
under tests/fixtures/combined/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.data_sources.jolpica_loader import (
    NUMERIC_FLOAT_COLUMNS,
    NUMERIC_INT_COLUMNS,
    RESULTS_COLUMNS,
    IncompleteJolpicaDataError,
    InvalidJolpicaSeasonOrRoundError,
    JolpicaResultsLoadError,
    UnresolvedJolpicaIdError,
    empty_shaped_results,
    load_and_map_season_results,
    read_season_dump,
    shape_results,
    validate_ids,
    verify_completeness,
)


COMBINED_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "combined"
KAGGLE_FIXTURE_DIR = COMBINED_FIXTURE_DIR / "kaggle"
JOLPICA_DUMP_DIR = COMBINED_FIXTURE_DIR / "jolpica_dump"


@pytest.fixture
def drivers() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "drivers.csv")


@pytest.fixture
def constructors() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "constructors.csv")


def test_read_season_dump_loads_results_and_counts():
    results, counts = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")

    assert len(results) == 7
    assert counts["season"] == 2026
    assert counts["row_count"] == 7
    assert counts["rounds"] == [1, 3, 4]


def test_read_season_dump_raises_named_error_for_missing_dump_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError) as excinfo:
        read_season_dump(tmp_path)

    assert "race_results.csv" in str(excinfo.value)


def test_verify_completeness_passes_when_landed_matches_sidecar():
    results, counts = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")

    verify_completeness(results, counts)  # must not raise


def test_verify_completeness_raises_named_error_when_rows_undercount_sidecar():
    results, counts = read_season_dump(JOLPICA_DUMP_DIR / "incomplete")

    with pytest.raises(IncompleteJolpicaDataError) as excinfo:
        verify_completeness(results, counts)

    assert "1" in str(excinfo.value) and "2" in str(excinfo.value)


def test_verify_completeness_raises_named_error_when_rows_overcount_sidecar():
    # An over-count is just as much a mismatch against "the source's own
    # published total" (AD-13) as an under-count -- not merely "at least".
    results, counts = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    deflated_counts = {**counts, "row_count": counts["row_count"] - 1}

    with pytest.raises(IncompleteJolpicaDataError) as excinfo:
        verify_completeness(results, deflated_counts)

    assert str(counts["row_count"]) in str(excinfo.value)
    assert str(deflated_counts["row_count"]) in str(excinfo.value)


def test_verify_completeness_raises_named_error_when_row_count_key_missing():
    # A counts sidecar missing its own row_count key is just as much "not
    # verified against the source's own published total" (AD-13) as a
    # mismatched count -- must never be silently accepted as close enough.
    results, counts = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    counts_without_row_count = {key: value for key, value in counts.items() if key != "row_count"}

    with pytest.raises(IncompleteJolpicaDataError) as excinfo:
        verify_completeness(results, counts_without_row_count)

    assert "row_count" in str(excinfo.value)


def test_shape_results_maps_ergast_columns_to_curated_results_columns():
    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")

    shaped = shape_results(results)

    assert list(shaped.columns) == RESULTS_COLUMNS
    row1 = shaped[(shaped["round"] == 1) & (shaped["driver_id"] == "verstappen")].iloc[0]
    assert row1["driver_name"] == "Max Verstappen"
    assert row1["constructor"] == "Red Bull"
    assert row1["constructor_id"] == "red_bull"
    assert row1["points"] == 25
    assert row1["position"] == 1
    assert row1["fastest_lap"] == 55
    assert row1["fastest_lap_rank"] == 1
    assert row1["race_name"] == "Match Grand Prix"


def test_shape_results_casts_numeric_columns_to_nullable_integer_dtype():
    # Kaggle's curated `results` columns are already integer-typed;
    # leaving Jolpica's coerced columns as float64 would make
    # `combined_results`/combined standings' dtype for these columns shift
    # depending on which source supplied a given round's rows once
    # concatenated -- notably `position`, which Epic 2 Story 2.1's AC
    # requires typed INTEGER end-to-end.
    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")

    shaped = shape_results(results)

    for column in NUMERIC_INT_COLUMNS:
        assert str(shaped[column].dtype) == "Int64", f"{column} dtype is {shaped[column].dtype}, expected Int64"


def test_shape_results_preserves_half_points_rather_than_failing_the_whole_season():
    # F1 awards half points when a race is stopped early (2021 Spa is the most
    # recent of 8 fractional-points rounds in the curated data). `points` was
    # once cast to Int64 alongside the other numerics, which raised on such a
    # value -- and because `shape_results` shapes a whole season at once and
    # `build_combined_dataset.load_jolpica_results` degrades any
    # `JolpicaResultsLoadError` to an empty frame, ONE half-points race
    # silently emptied the entire season's gap-fill while the build exited 0.
    # This pins the fractional value surviving, not merely the dtype: an
    # Int64 regression would truncate 12.5 to 12 or raise, and both fail here.
    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    results = results.copy()
    results["points"] = results["points"].astype(float)
    round_one = results["round"] == 1
    results.loc[round_one, "points"] = results.loc[round_one, "points"] / 2

    shaped = shape_results(results)

    assert len(shaped) == len(results), "a fractional points value must not drop rows"
    half_pointed = shaped[shaped["round"] == 1].sort_values("position")
    assert half_pointed["points"].tolist() == [12.5, 9.0]
    # Rounds that were never fractional must be untouched -- the old failure
    # took these with it.
    assert shaped[shaped["round"] == 3]["points"].tolist() == [25.0, 18.0]


def test_points_is_fractional_safe_and_stays_out_of_the_integer_cast_list():
    # Guards the two lists directly, so a future edit that moves `points` back
    # into NUMERIC_INT_COLUMNS fails here with a pointed message rather than
    # only surfacing as a silently emptied season in a live build.
    assert "points" not in NUMERIC_INT_COLUMNS, (
        "points must not be Int64-cast: half-points races are legitimate and an "
        "Int64 cast empties the whole season's gap-fill via the degrade path"
    )
    assert "points" in NUMERIC_FLOAT_COLUMNS

    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    shaped = shape_results(results)

    # Float64 (nullable), matching curated `results.points` (DOUBLE), so a
    # concat with Kaggle rows neither upcasts to object nor loses precision.
    assert str(shaped["points"].dtype) == "Float64"


def test_empty_shaped_results_matches_a_populated_frames_numeric_dtypes():
    # The "nothing landed this run" degrade path must produce a frame that
    # concatenates cleanly with a populated one -- same columns, and the
    # same nullable-integer dtype on every numeric column -- so pd.concat
    # never silently upcasts a numeric column back to float64 (string-ish
    # columns aren't load-bearing here: pandas' `str` vs. legacy `object`
    # dtype for an all-empty text column doesn't affect any downstream
    # numeric operation the way an upcast `points`/`position` would).
    populated = shape_results(read_season_dump(JOLPICA_DUMP_DIR / "normal_season")[0])

    empty = empty_shaped_results()

    assert len(empty) == 0
    assert list(empty.columns) == list(populated.columns)
    for column in NUMERIC_INT_COLUMNS:
        assert str(empty[column].dtype) == "Int64" == str(populated[column].dtype), column


def test_shape_results_raises_named_error_for_a_non_numeric_round_value():
    # pd.to_numeric(..., errors="coerce") silently turns a bad round value
    # into null; left unchecked that row would just vanish from a later
    # inner merge instead of raising (AD-16 fail-early).
    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    corrupted = results.copy()
    corrupted["round"] = corrupted["round"].astype(object)
    corrupted.loc[0, "round"] = "not-a-number"  # row 0 is round 1's verstappen row

    with pytest.raises(InvalidJolpicaSeasonOrRoundError) as excinfo:
        shape_results(corrupted)

    assert "verstappen" in str(excinfo.value)


def test_shape_results_raises_named_error_for_a_non_numeric_season_value():
    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    corrupted = results.copy()
    corrupted["season"] = corrupted["season"].astype(object)
    corrupted.loc[0, "season"] = "not-a-number"

    with pytest.raises(InvalidJolpicaSeasonOrRoundError) as excinfo:
        shape_results(corrupted)

    assert "verstappen" in str(excinfo.value)


def test_validate_ids_raises_named_error_for_an_unresolved_driver_id(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    shaped = pd.DataFrame(
        [
            {
                "season": 2026,
                "round": 1,
                "race_name": "Match Grand Prix",
                "driver_id": "verstappen",
                "driver_name": "Max Verstappen",
                "constructor_id": "red_bull",
                "constructor": "Red Bull",
                "grid": 1,
                "position": 1,
                "points": 25,
                "laps": 57,
                "status": "Finished",
                "time": None,
                "fastest_lap": 55,
                "fastest_lap_rank": 1,
            },
            {
                "season": 2026,
                "round": 1,
                "race_name": "Match Grand Prix",
                "driver_id": "unknown_driver",
                "driver_name": "Zed Zeta",
                "constructor_id": "red_bull",
                "constructor": "Red Bull",
                "grid": 20,
                "position": 20,
                "points": 0,
                "laps": 55,
                "status": "Retired",
                "time": None,
                "fastest_lap": None,
                "fastest_lap_rank": None,
            },
        ]
    )[RESULTS_COLUMNS]

    with pytest.raises(UnresolvedJolpicaIdError) as excinfo:
        validate_ids(shaped, drivers, constructors)

    assert "unknown_driver" in str(excinfo.value)


def test_validate_ids_raises_named_error_for_an_unresolved_constructor_id(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    shaped = pd.DataFrame(
        [
            {
                "season": 2026,
                "round": 1,
                "race_name": "Match Grand Prix",
                "driver_id": "verstappen",
                "driver_name": "Max Verstappen",
                "constructor_id": "unknown_team",
                "constructor": "Unknown Team",
                "grid": 1,
                "position": 1,
                "points": 25,
                "laps": 57,
                "status": "Finished",
                "time": None,
                "fastest_lap": 55,
                "fastest_lap_rank": 1,
            }
        ]
    )[RESULTS_COLUMNS]

    with pytest.raises(UnresolvedJolpicaIdError) as excinfo:
        validate_ids(shaped, drivers, constructors)

    assert "unknown_team" in str(excinfo.value)


def test_validate_ids_raises_named_error_for_a_missing_driver_id_instead_of_dropping_the_row(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    shaped = pd.DataFrame(
        [
            {
                "season": 2026,
                "round": 1,
                "race_name": "Match Grand Prix",
                "driver_id": None,
                "driver_name": "  ",
                "constructor_id": "red_bull",
                "constructor": "Red Bull",
                "grid": 1,
                "position": 1,
                "points": 25,
                "laps": 57,
                "status": "Finished",
                "time": None,
                "fastest_lap": 55,
                "fastest_lap_rank": 1,
            }
        ]
    )[RESULTS_COLUMNS]

    with pytest.raises(UnresolvedJolpicaIdError) as excinfo:
        validate_ids(shaped, drivers, constructors)

    assert "<missing driverId value>" in str(excinfo.value)


def test_validate_ids_passes_for_all_known_ids(drivers: pd.DataFrame, constructors: pd.DataFrame):
    results, _ = read_season_dump(JOLPICA_DUMP_DIR / "normal_season")
    shaped = shape_results(results)

    validate_ids(shaped, drivers, constructors)  # must not raise


def test_load_and_map_season_results_happy_path(drivers: pd.DataFrame, constructors: pd.DataFrame):
    shaped = load_and_map_season_results(
        JOLPICA_DUMP_DIR / "normal_season", drivers, constructors, season=2026
    )

    assert list(shaped.columns) == RESULTS_COLUMNS
    assert len(shaped) == 7
    assert set(shaped["round"].unique().tolist()) == {1, 3, 4}
    assert shaped["driver_id"].notna().all()
    assert shaped["constructor_id"].notna().all()


def test_load_and_map_season_results_wraps_incomplete_data_error(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    with pytest.raises(JolpicaResultsLoadError) as excinfo:
        load_and_map_season_results(JOLPICA_DUMP_DIR / "incomplete", drivers, constructors, season=2026)

    assert "season 2026" in str(excinfo.value)


def test_load_and_map_season_results_wraps_unresolved_id_error(
    drivers: pd.DataFrame, constructors: pd.DataFrame
):
    with pytest.raises(JolpicaResultsLoadError) as excinfo:
        load_and_map_season_results(JOLPICA_DUMP_DIR / "unresolved_id", drivers, constructors, season=2026)

    assert "unknown_driver" in str(excinfo.value)


def test_load_and_map_season_results_wraps_invalid_season_or_round_error(
    tmp_path: Path, drivers: pd.DataFrame, constructors: pd.DataFrame
):
    source_dir = JOLPICA_DUMP_DIR / "normal_season"
    season_dir = tmp_path / "BadRound"
    season_dir.mkdir()
    corrupted = pd.read_csv(source_dir / "race_results.csv")
    corrupted["round"] = corrupted["round"].astype(object)
    corrupted.loc[0, "round"] = "not-a-number"
    corrupted.to_csv(season_dir / "race_results.csv", index=False)
    (season_dir / "counts.json").write_text((source_dir / "counts.json").read_text())

    with pytest.raises(JolpicaResultsLoadError) as excinfo:
        load_and_map_season_results(season_dir, drivers, constructors, season=2026)

    assert "verstappen" in str(excinfo.value)


def test_load_and_map_season_results_wraps_a_corrupt_counts_json_instead_of_crashing_the_run(
    tmp_path: Path, drivers: pd.DataFrame, constructors: pd.DataFrame
):
    season_dir = tmp_path / "CorruptCounts"
    season_dir.mkdir()
    source_dir = JOLPICA_DUMP_DIR / "normal_season"
    (season_dir / "race_results.csv").write_text((source_dir / "race_results.csv").read_text())
    (season_dir / "counts.json").write_text("{not valid json")

    with pytest.raises(JolpicaResultsLoadError):
        load_and_map_season_results(season_dir, drivers, constructors, season=2026)
