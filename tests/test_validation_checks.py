"""Offline unit tests for `validation/checks.py` (Story 1.8).

Covers `check_null_rate`/`check_referential_integrity` directly (including
the missing-column guard both must share), and `run_validations()` against
curated tables, `combined_results` (Story 1.7), and `raw_fastf1_laps`/
`raw_fastf1_stints`/`raw_fastf1_weather` (Story 1.6) -- the amended scope
this story's registries cover, per the frozen spec's Spec Change Log.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1_analytics.validation.checks import (
    NULL_RATE_CHECKS,
    REFERENTIAL_CHECKS,
    check_null_rate,
    check_referential_integrity,
    run_validations,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "validation"
NULL_VIOLATION_DIR = FIXTURE_DIR / "null_violation"
ORPHAN_REFERENTIAL_DIR = FIXTURE_DIR / "orphan_referential"


def _load_scenario(scenario_dir: Path) -> dict[str, pd.DataFrame]:
    """Load a scenario dir's curated CSVs plus its combined_results-shaped addition."""
    return {
        "results": pd.read_csv(scenario_dir / "results.csv"),
        "drivers": pd.read_csv(scenario_dir / "drivers.csv"),
        "constructors": pd.read_csv(scenario_dir / "constructors.csv"),
        "races": pd.read_csv(scenario_dir / "races.csv"),
        "circuits": pd.read_csv(scenario_dir / "circuits.csv"),
        "combined_results": pd.read_csv(scenario_dir / "combined_results.csv"),
    }


def _findings_by_table_column(frame: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    return {(row["table_name"], row["column_name"]): row for _, row in frame.iterrows()}


# --- check_null_rate() ---------------------------------------------------


def test_check_null_rate_passes_when_no_nulls():
    frame = pd.DataFrame({"points": [25, 18, 15]})
    finding = check_null_rate(frame, "results", "points")

    assert finding == {
        "check_type": "null_rate",
        "table_name": "results",
        "column_name": "points",
        "ref_table_name": None,
        "row_count": 3,
        "null_count": 0,
        "null_rate": 0.0,
        "orphan_count": None,
        "passed": True,
    }


def test_check_null_rate_fails_and_counts_nulls():
    frame = pd.DataFrame({"points": [25, None, 15, None]})
    finding = check_null_rate(frame, "results", "points")

    assert finding["passed"] is False
    assert finding["null_count"] == 2
    assert finding["null_rate"] == 0.5
    assert finding["row_count"] == 4


def test_check_null_rate_on_an_empty_frame_passes():
    frame = pd.DataFrame({"points": pd.Series([], dtype="float64")})
    finding = check_null_rate(frame, "results", "points")

    assert finding["passed"] is True
    assert finding["row_count"] == 0
    assert finding["null_rate"] == 0.0


def test_check_null_rate_guards_a_missing_column():
    # Never a KeyError -- a missing column is treated as every row being
    # unverifiable, so it fails the same way an all-null column would.
    frame = pd.DataFrame({"other_column": [1, 2, 3]})
    finding = check_null_rate(frame, "results", "points")

    assert finding["passed"] is False
    assert finding["null_count"] == 3
    assert finding["row_count"] == 3


# --- check_referential_integrity() ---------------------------------------


def test_check_referential_integrity_passes_when_every_child_value_resolves():
    child = pd.DataFrame({"driver_id": ["verstappen", "hamilton"]})
    parent = pd.DataFrame({"driver_id": ["verstappen", "hamilton", "alonso"]})
    finding = check_referential_integrity(child, "results", "driver_id", parent, "drivers", "driver_id")

    assert finding == {
        "check_type": "referential_integrity",
        "table_name": "results",
        "column_name": "driver_id",
        "ref_table_name": "drivers.driver_id",
        "row_count": 2,
        "null_count": None,
        "null_rate": None,
        "orphan_count": 0,
        "passed": True,
    }


def test_check_referential_integrity_fails_and_counts_orphans():
    child = pd.DataFrame({"driver_id": ["verstappen", "ghost_driver"]})
    parent = pd.DataFrame({"driver_id": ["verstappen", "hamilton"]})
    finding = check_referential_integrity(child, "results", "driver_id", parent, "drivers", "driver_id")

    assert finding["passed"] is False
    assert finding["orphan_count"] == 1
    assert finding["row_count"] == 2


def test_check_referential_integrity_ignores_nulls_in_the_child_column():
    # A NULL foreign key is a null-rate concern, not an orphan -- matches
    # the salvaged recovery reference exactly (see deferred-work.md's
    # "code review of story-1.8" entry: a scope decision, not a defect).
    child = pd.DataFrame({"driver_id": ["verstappen", None]})
    parent = pd.DataFrame({"driver_id": ["verstappen"]})
    finding = check_referential_integrity(child, "results", "driver_id", parent, "drivers", "driver_id")

    assert finding["passed"] is True
    assert finding["orphan_count"] == 0


def test_check_referential_integrity_guards_a_missing_child_column():
    child = pd.DataFrame({"other_column": [1, 2]})
    parent = pd.DataFrame({"driver_id": ["verstappen"]})
    finding = check_referential_integrity(child, "results", "driver_id", parent, "drivers", "driver_id")

    assert finding["passed"] is False
    assert finding["orphan_count"] == 2
    assert finding["row_count"] == 2


def test_check_referential_integrity_guards_a_missing_parent_column():
    child = pd.DataFrame({"driver_id": ["verstappen"]})
    parent = pd.DataFrame({"other_column": [1]})
    finding = check_referential_integrity(child, "results", "driver_id", parent, "drivers", "driver_id")

    assert finding["passed"] is False
    assert finding["orphan_count"] == 1


# --- run_validations(): envelope + registry-skip behavior ----------------


def test_run_validations_adds_check_id_and_checked_at_to_every_row():
    tables = {"drivers": pd.DataFrame({"driver_id": ["verstappen"]})}
    result = run_validations(tables)

    assert "check_id" in result.columns
    assert result["check_id"].is_unique
    assert result["checked_at"].notna().all()
    assert list(result.columns)[0] == "check_id"


def test_run_validations_skips_registry_entries_for_absent_tables_without_raising():
    result = run_validations({})

    assert len(result) == 0


# --- run_validations(): curated tables ------------------------------------


def test_run_validations_logs_a_null_violation_for_curated_results():
    tables = _load_scenario(NULL_VIOLATION_DIR)
    result = run_validations(tables)
    findings = _findings_by_table_column(result[result["check_type"] == "null_rate"])

    points_finding = findings[("results", "points")]
    assert not points_finding["passed"]
    assert points_finding["null_count"] == 1

    driver_id_finding = findings[("results", "driver_id")]
    assert driver_id_finding["passed"]


def test_run_validations_logs_an_orphan_for_curated_results():
    tables = _load_scenario(ORPHAN_REFERENTIAL_DIR)
    result = run_validations(tables)
    referential = result[result["check_type"] == "referential_integrity"]
    driver_orphan = referential[
        (referential["table_name"] == "results") & (referential["column_name"] == "driver_id")
    ].iloc[0]

    assert not driver_orphan["passed"]
    assert driver_orphan["orphan_count"] == 1
    assert driver_orphan["ref_table_name"] == "drivers.driver_id"

    # The constructor_id referential check is unaffected -- the orphan row's
    # constructor_id ("red_bull") is a real, present constructor.
    constructor_check = referential[
        (referential["table_name"] == "results") & (referential["column_name"] == "constructor_id")
    ].iloc[0]
    assert constructor_check["passed"]


# --- run_validations(): combined_results (Story 1.7 amendment) -----------


def test_run_validations_logs_a_null_violation_for_combined_results():
    tables = _load_scenario(NULL_VIOLATION_DIR)
    result = run_validations(tables)
    findings = _findings_by_table_column(result[result["check_type"] == "null_rate"])

    combined_points = findings[("combined_results", "points")]
    assert not combined_points["passed"]
    assert combined_points["null_count"] == 1


def test_run_validations_logs_an_orphan_for_combined_results():
    tables = _load_scenario(ORPHAN_REFERENTIAL_DIR)
    result = run_validations(tables)
    referential = result[result["check_type"] == "referential_integrity"]
    combined_orphan = referential[
        (referential["table_name"] == "combined_results") & (referential["column_name"] == "driver_id")
    ].iloc[0]

    assert not combined_orphan["passed"]
    assert combined_orphan["orphan_count"] == 1


# --- run_validations(): raw_fastf1_* tables (Story 1.6 amendment) --------


def _raw_fastf1_laps_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2026, 2026, 2026],
            "round": [1, 1, 1],
            "driver_id": ["verstappen", None, "hamilton"],
            "constructor_id": ["red_bull", "red_bull", "ghost_team"],
        }
    )


def _drivers_and_constructors() -> dict[str, pd.DataFrame]:
    return {
        "drivers": pd.DataFrame({"driver_id": ["verstappen", "hamilton"]}),
        "constructors": pd.DataFrame({"constructor_id": ["red_bull", "mercedes"]}),
    }


def test_run_validations_covers_raw_fastf1_laps_null_and_referential_entries():
    tables = {"raw_fastf1_laps": _raw_fastf1_laps_frame(), **_drivers_and_constructors()}
    result = run_validations(tables)

    null_findings = _findings_by_table_column(result[result["check_type"] == "null_rate"])
    driver_id_null = null_findings[("raw_fastf1_laps", "driver_id")]
    assert not driver_id_null["passed"]
    assert driver_id_null["null_count"] == 1

    referential = result[result["check_type"] == "referential_integrity"]
    constructor_orphan = referential[
        (referential["table_name"] == "raw_fastf1_laps") & (referential["column_name"] == "constructor_id")
    ].iloc[0]
    assert not constructor_orphan["passed"]
    assert constructor_orphan["orphan_count"] == 1  # "ghost_team" isn't in constructors

    driver_orphan = referential[
        (referential["table_name"] == "raw_fastf1_laps") & (referential["column_name"] == "driver_id")
    ].iloc[0]
    # The one NULL driver_id row is excluded from the referential check
    # (dropna'd, per check_referential_integrity's contract) -- the two
    # resolved driver_id values both exist in `drivers`.
    assert driver_orphan["passed"]


def test_run_validations_covers_raw_fastf1_stints_registry_entries():
    stints = pd.DataFrame(
        {
            "season": [2026],
            "round": [1],
            "driver_id": ["verstappen"],
            "constructor_id": ["red_bull"],
        }
    )
    tables = {"raw_fastf1_stints": stints, **_drivers_and_constructors()}
    result = run_validations(tables)

    # `drivers`/`constructors` (also present) contribute their own
    # NULL_RATE_CHECKS rows too -- everything passes since this fixture is
    # clean, but the row set spans all three tables, not just the stints one.
    assert result["passed"].all()
    stints_rows = result[result["table_name"] == "raw_fastf1_stints"]
    assert set(stints_rows["check_type"]) == {"null_rate", "referential_integrity"}
    assert len(stints_rows[stints_rows["check_type"] == "referential_integrity"]) == 2


def test_run_validations_covers_raw_fastf1_weather_track_level_only():
    # raw_fastf1_weather is track-level (no driver_id) -- only season/round
    # are checked, and it has no referential-integrity entries at all.
    weather = pd.DataFrame({"season": [2026, None], "round": [1, 1]})
    result = run_validations({"raw_fastf1_weather": weather})

    assert set(result["check_type"]) == {"null_rate"}
    findings = _findings_by_table_column(result)
    assert findings[("raw_fastf1_weather", "season")]["null_count"] == 1
    assert findings[("raw_fastf1_weather", "round")]["null_count"] == 0


def test_raw_fastf1_weather_registry_has_no_referential_entries():
    assert not any(child_table == "raw_fastf1_weather" for child_table, *_ in REFERENTIAL_CHECKS)
    weather_columns = dict(NULL_RATE_CHECKS)["raw_fastf1_weather"]
    assert weather_columns == ["season", "round"]
