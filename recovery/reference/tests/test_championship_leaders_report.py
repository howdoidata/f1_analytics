from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from f1_analytics.analysis.championship_leaders import (
    CONVERSION_REPORT_QUESTION,
    write_followup_report,
    write_report,
)
from f1_analytics.analysis.report_summary import REPORT_SUMMARY_FIELD_ORDER


CONVERSION_SECTIONS = (
    "## Question",
    "## Cutoff Definition",
    "## Drivers",
    "## Constructors",
    "## Current Season Leaders",
    "## Data Limitations",
    "## Output Tables",
)

FOLLOWUP_SECTIONS = (
    "## Data Sources",
    "## Current Cutoff",
    "## Current Conversion Answers",
    "## Largest Constructor Comeback",
    "## Candidate Recovery Features",
    "## Outputs",
    "## Limitations",
)


def coverage_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "target_season", "value": "2026"},
            {"metric": "cutoff_round", "value": "12"},
            {"metric": "scheduled_races_target_season", "value": "24"},
            {"metric": "completed_result_rounds_target_season", "value": "12"},
        ]
    )


def conversion_frame(converted: list[bool]) -> pd.DataFrame:
    return pd.DataFrame({"converted": converted})


def current_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "entity_type": "driver",
                "leader_name": "Test Driver",
                "leader_points": 210.0,
                "leader_wins": 5,
            },
            {
                "entity_type": "constructor",
                "leader_name": "Test Constructor",
                "leader_points": 380.0,
                "leader_wins": 8,
            },
        ]
    )


def comeback_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2009,
                "champion_constructor": "Test Constructor",
                "cutoff_points": 40.0,
                "cutoff_leader_points": 95.0,
                "points_deficit_overcome": 55.0,
                "cutoff_rank": 3,
                "final_points": 172.0,
                "final_wins": 6,
            }
        ]
    )


def feature_candidates_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "feature": "points deficit at cutoff",
                "plain_language_definition": "How many points the team trails the cutoff leader by.",
                "current_status": "Available from constructor_standings_by_round.",
            }
        ]
    )


def write_conversion_report(
    report_path: Path,
    driver_conversion: pd.DataFrame | None = None,
    constructor_conversion: pd.DataFrame | None = None,
) -> str:
    write_report(
        2026,
        12,
        "Test Grand Prix",
        "2026-07-05",
        coverage_frame(),
        conversion_frame([True, True, False, True, False]) if driver_conversion is None else driver_conversion,
        conversion_frame([True, False, True]) if constructor_conversion is None else constructor_conversion,
        current_frame(),
        report_path,
    )
    return report_path.read_text(encoding="utf-8")


def write_followup(report_path: Path, comeback_cases: pd.DataFrame | None = None) -> str:
    write_followup_report(
        2026,
        12,
        "Test Grand Prix",
        "2026-07-05",
        coverage_frame(),
        conversion_frame([True, True, False, True, False]),
        conversion_frame([True, False, True]),
        current_frame(),
        comeback_frame() if comeback_cases is None else comeback_cases,
        feature_candidates_frame(),
        None,
        report_path,
    )
    return report_path.read_text(encoding="utf-8")


class ConversionReportSummaryTests(unittest.TestCase):
    def test_report_summary_leads_the_report_after_the_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_conversion_report(Path(tmp_dir) / "championship_leader_conversion.md")

        title_index = text.index("# Championship Leader Conversion At Current Season Cutoff")
        summary_index = text.index("## Report Summary")
        first_existing_section = min(text.index(section) for section in CONVERSION_SECTIONS)

        self.assertLess(title_index, summary_index)
        self.assertLess(summary_index, first_existing_section)

    def test_summary_block_carries_the_contract_fields_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_conversion_report(Path(tmp_dir) / "championship_leader_conversion.md")

        summary_block = text[text.index("## Report Summary") : min(text.index(s) for s in CONVERSION_SECTIONS)]
        positions = [summary_block.index(f"- {label}:") for label in REPORT_SUMMARY_FIELD_ORDER]

        self.assertEqual(sorted(positions), positions)
        self.assertIn("60.0%", summary_block)
        self.assertIn("Test Grand Prix", summary_block)
        self.assertIn("[COMPUTED]", summary_block)
        self.assertIn("outputs/tables/driver_leader_conversion.csv", summary_block)

    def test_every_pre_existing_section_survives_the_retrofit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_conversion_report(Path(tmp_dir) / "championship_leader_conversion.md")

        for section in CONVERSION_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, text)
        self.assertIn("The cutoff uses the latest completed round available in the local", text)
        self.assertIn("`outputs/tables/data_coverage_summary.csv`", text)

    def test_an_empty_conversion_sample_is_reported_as_partial_not_computed(self) -> None:
        # summarize_conversion() reports 0.0% for an empty frame; a 0-of-0 rate must never ship
        # as a computed answer.
        empty = conversion_frame([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_conversion_report(Path(tmp_dir) / "championship_leader_conversion.md", empty, empty)

        summary_block = text[text.index("## Report Summary") : min(text.index(s) for s in CONVERSION_SECTIONS)]

        self.assertIn("- Status: [PARTIAL]", summary_block)
        self.assertNotIn("- Status: [COMPUTED]", summary_block)
        self.assertIn("empty sample", summary_block)
        self.assertIn("driver or constructor", summary_block)

    def test_a_single_empty_side_still_downgrades_the_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_conversion_report(
                Path(tmp_dir) / "championship_leader_conversion.md",
                constructor_conversion=conversion_frame([]),
            )

        summary_block = text[text.index("## Report Summary") : min(text.index(s) for s in CONVERSION_SECTIONS)]

        self.assertIn("- Status: [PARTIAL]", summary_block)
        self.assertIn("constructor season", summary_block)

    def test_the_question_section_and_the_summary_state_the_same_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_conversion_report(Path(tmp_dir) / "championship_leader_conversion.md")

        self.assertEqual(2, text.count(CONVERSION_REPORT_QUESTION))


class FollowupReportSummaryTests(unittest.TestCase):
    def test_report_summary_leads_the_followup_report_after_the_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_followup(Path(tmp_dir) / "championship_leader_followup.md")

        title_index = text.index("# Championship Leader Follow-Up")
        summary_index = text.index("## Report Summary")
        first_existing_section = min(text.index(section) for section in FOLLOWUP_SECTIONS)

        self.assertLess(title_index, summary_index)
        self.assertLess(summary_index, first_existing_section)

    def test_summary_answer_reuses_the_comeback_framing_and_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_followup(Path(tmp_dir) / "championship_leader_followup.md")

        summary_block = text[text.index("## Report Summary") : min(text.index(s) for s in FOLLOWUP_SECTIONS)]
        positions = [summary_block.index(f"- {label}:") for label in REPORT_SUMMARY_FIELD_ORDER]

        self.assertEqual(sorted(positions), positions)
        self.assertIn("55 points", summary_block)
        self.assertIn("Kaggle", summary_block)
        self.assertIn("outputs/tables/constructor_comeback_cases.csv", summary_block)

    def test_summary_states_absence_when_no_positive_comeback_cases_exist(self) -> None:
        empty_cases = comeback_frame().assign(points_deficit_overcome=0.0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_followup(Path(tmp_dir) / "championship_leader_followup.md", empty_cases)

        summary_block = text[text.index("## Report Summary") : min(text.index(s) for s in FOLLOWUP_SECTIONS)]

        self.assertIn("No positive constructor comeback cases", summary_block)
        # An absence of qualifying cases is not a computed answer.
        self.assertIn("- Status: [PARTIAL]", summary_block)
        self.assertNotIn("- Status: [COMPUTED]", summary_block)
        self.assertIn("absence of qualifying cases", summary_block)

    def test_a_present_comeback_case_still_reports_a_computed_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_followup(Path(tmp_dir) / "championship_leader_followup.md")

        summary_block = text[text.index("## Report Summary") : min(text.index(s) for s in FOLLOWUP_SECTIONS)]

        self.assertIn("- Status: [COMPUTED]", summary_block)

    def test_every_pre_existing_followup_section_survives_the_retrofit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            text = write_followup(Path(tmp_dir) / "championship_leader_followup.md")

        for section in FOLLOWUP_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, text)
        self.assertIn("The cutoff remains Kaggle-baseline round 12", text)
        self.assertIn("`outputs/tables/recovery_feature_candidates.csv`", text)
        self.assertIn("No figure generated because there were no positive comeback cases.", text)


if __name__ == "__main__":
    unittest.main()
