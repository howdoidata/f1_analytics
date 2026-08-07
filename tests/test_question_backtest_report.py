from __future__ import annotations

import unittest
from dataclasses import replace

from f1_analytics.analysis.question_answers import (
    ActualAnswerComponent,
    ActualAnswerStatus,
    TyreCompound,
)
from f1_analytics.analysis.question_backtest_report import (
    ReportRowOutcome,
    build_question_report,
    build_question_report_row,
    component_report_row_to_record,
    question_report_row_to_record,
)
from f1_analytics.analysis.question_backtest_scoring import Scoreability
from f1_analytics.analysis.question_catalog import AnalysisMode, AnswerType, supplied_pdf_question_catalog_rows
from f1_analytics.analysis.question_predictions import LeakageStatus, PredictionInput, PredictionInputStatus


def supplied_row(question_id: str):
    rows_by_id = {row.question_id: row for row in supplied_pdf_question_catalog_rows()}
    return rows_by_id[question_id]


def available_prediction(row, component_key=None, prediction_value=None, display_value=None) -> PredictionInput:
    return PredictionInput(
        question_id=row.question_id,
        component_key=component_key,
        analysis_mode=AnalysisMode.PRE_RACE,
        prediction_value=prediction_value,
        display_value=display_value,
        method="test baseline method",
        source_boundary=row.feature_snapshot_boundary,
        build_timestamp_or_id="test-build-2026-07-18",
        leakage_status=LeakageStatus.LEAKAGE_SAFE,
        prediction_status=PredictionInputStatus.AVAILABLE,
        unavailable_reason=None,
        source_inputs_or_artifacts=("feature:test_source",),
    )


def unavailable_prediction(row, component_key=None, reason="no leakage-safe method yet") -> PredictionInput:
    return PredictionInput(
        question_id=row.question_id,
        component_key=component_key,
        analysis_mode=AnalysisMode.PRE_RACE,
        prediction_value=None,
        display_value=None,
        method=None,
        source_boundary=row.feature_snapshot_boundary,
        build_timestamp_or_id=None,
        leakage_status=LeakageStatus.NOT_CHECKED,
        prediction_status=PredictionInputStatus.UNAVAILABLE,
        unavailable_reason=reason,
        source_inputs_or_artifacts=(),
    )


def actual_component(
    row,
    component_key,
    component_label,
    answer_type,
    component_order,
    validation_status,
    **overrides,
) -> ActualAnswerComponent:
    values = {
        "question_id": row.question_id,
        "component_key": component_key,
        "component_label": component_label,
        "answer_type": answer_type,
        "display_value": None,
        "component_order": component_order,
        "validation_status": validation_status,
        "numeric_value": None,
        "categorical_value": None,
        "text_value": None,
        "source_value": None,
        "unit": None,
        "precision": None,
        "tolerance": None,
        "source_table_or_file": "test_source_table",
        "source_field_or_method": "test source field",
        "extraction_timestamp_or_build_id": "test-build-2026-07-18",
        "known_answer_example": None,
        "discrepancy_notes": None,
    }
    values.update(overrides)
    return ActualAnswerComponent(**values)


class BuildQuestionReportRowSingleAnswerTests(unittest.TestCase):
    def test_scoreable_correct_prediction_maps_to_prediction_correct(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        report_row = build_question_report_row(row, (prediction,), (actual,))

        self.assertEqual(1, len(report_row.component_rows))
        component_row = report_row.component_rows[0]
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, component_row.outcome)
        self.assertTrue(component_row.is_correct)
        self.assertEqual(ActualAnswerStatus.COMPUTED, component_row.actual_answer_status)
        self.assertEqual("test_source_table", component_row.source_table_or_file)
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, report_row.combined_outcome)
        self.assertTrue(report_row.combined_is_correct)

    def test_scoreable_incorrect_prediction_maps_to_prediction_incorrect(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=58, display_value="Lap 58")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        report_row = build_question_report_row(row, (prediction,), (actual,))

        component_row = report_row.component_rows[0]
        self.assertEqual(ReportRowOutcome.PREDICTION_INCORRECT, component_row.outcome)
        self.assertFalse(component_row.is_correct)
        self.assertEqual(ReportRowOutcome.PREDICTION_INCORRECT, report_row.combined_outcome)
        self.assertFalse(report_row.combined_is_correct)


class BuildQuestionReportRowActualAnswerBlockedTests(unittest.TestCase):
    def test_blocked_actual_answer_statuses_map_to_actual_answer_unscoreable(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        statuses = (
            ActualAnswerStatus.PENDING,
            ActualAnswerStatus.PARTIAL,
            ActualAnswerStatus.SOURCE_BLOCKED,
            ActualAnswerStatus.DISCREPANT_NEEDS_REVIEW,
            ActualAnswerStatus.USER_MANUAL_OPTION,
        )
        for status in statuses:
            with self.subTest(status=status):
                actual = actual_component(
                    row,
                    component_key="actual_answer",
                    component_label="Actual answer",
                    answer_type=AnswerType.LAP_NUMBER,
                    component_order=1,
                    validation_status=status,
                    display_value="Lap under review",
                )

                report_row = build_question_report_row(row, (prediction,), (actual,))

                component_row = report_row.component_rows[0]
                self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, component_row.outcome)
                self.assertEqual(status, component_row.actual_answer_status)
                self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, report_row.combined_outcome)
                self.assertIsNone(report_row.combined_is_correct)


class BuildQuestionReportRowPredictionUnavailableTests(unittest.TestCase):
    def test_unavailable_prediction_maps_to_prediction_unscoreable(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = unavailable_prediction(row, reason="no leakage-safe baseline method yet")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        report_row = build_question_report_row(row, (prediction,), (actual,))

        component_row = report_row.component_rows[0]
        self.assertEqual(ReportRowOutcome.PREDICTION_UNSCOREABLE, component_row.outcome)
        self.assertEqual(ReportRowOutcome.PREDICTION_UNSCOREABLE, report_row.combined_outcome)
        self.assertIsNone(report_row.combined_is_correct)
        self.assertEqual(ActualAnswerStatus.COMPUTED, component_row.actual_answer_status)


class BuildQuestionReportRowMismatchedQuestionIdTests(unittest.TestCase):
    def test_mismatched_question_id_prediction_is_excluded_not_paired(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        other_row = supplied_row("2026_pdf_q03_canadian_highest_williams_finish")
        mismatched_prediction = available_prediction(other_row, prediction_value=9, display_value="P9")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        report_row = build_question_report_row(row, (mismatched_prediction,), (actual,))

        component_row = report_row.component_rows[0]
        self.assertIsNone(component_row.prediction_value)
        self.assertEqual(Scoreability.UNSCOREABLE, component_row.scoreability)
        self.assertIn("0 prediction(s)", component_row.explanation)
        self.assertEqual(ActualAnswerStatus.COMPUTED, component_row.actual_answer_status)

    def test_mismatched_question_id_actual_component_is_excluded_not_paired(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        other_row = supplied_row("2026_pdf_q03_canadian_highest_williams_finish")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        mismatched_actual = actual_component(
            other_row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.FINISHING_POSITION,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=9,
            tolerance=0,
            display_value="P9",
        )

        report_row = build_question_report_row(row, (prediction,), (mismatched_actual,))

        component_row = report_row.component_rows[0]
        self.assertIsNone(component_row.actual_answer_status)
        self.assertIsNone(component_row.source_table_or_file)
        self.assertEqual(Scoreability.UNSCOREABLE, component_row.scoreability)
        self.assertEqual("actual_answer", component_row.component_label)
        self.assertEqual(1, component_row.order)


class BuildQuestionReportRowMultiPartTests(unittest.TestCase):
    def _tyre_prediction_and_actual(self, row, prediction_value="medium", actual_value=TyreCompound.MEDIUM):
        prediction = available_prediction(
            row, component_key="starting_tyre_compound", prediction_value=prediction_value, display_value=prediction_value
        )
        actual = actual_component(
            row,
            component_key="starting_tyre_compound",
            component_label="Starting tyre compound",
            answer_type=AnswerType.TYRE_COMPOUND,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            categorical_value=actual_value,
            display_value=actual_value.value,
        )
        return prediction, actual

    def _pit_change_prediction_and_actual(self, row, prediction_value=1, actual_value=1):
        prediction = available_prediction(
            row, component_key="first_tyre_change_lap", prediction_value=prediction_value, display_value=f"Lap {prediction_value}"
        )
        actual = actual_component(
            row,
            component_key="first_tyre_change_lap",
            component_label="First tyre-change lap",
            answer_type=AnswerType.PIT_CHANGE_LAP,
            component_order=2,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=actual_value,
            tolerance=0,
            display_value=f"Lap {actual_value}",
        )
        return prediction, actual

    def test_multi_part_both_components_scoreable_and_correct_combined_prediction_correct(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        tyre_prediction, tyre_actual = self._tyre_prediction_and_actual(row)
        pit_prediction, pit_actual = self._pit_change_prediction_and_actual(row)

        report_row = build_question_report_row(row, (tyre_prediction, pit_prediction), (tyre_actual, pit_actual))

        self.assertEqual(2, len(report_row.component_rows))
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, report_row.combined_outcome)
        self.assertTrue(report_row.combined_is_correct)
        for component_row in report_row.component_rows:
            self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, component_row.outcome)
            self.assertEqual(ActualAnswerStatus.COMPUTED, component_row.actual_answer_status)

    def test_multi_part_one_component_actual_answer_unscoreable_rolls_up_combined(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        tyre_prediction, tyre_actual = self._tyre_prediction_and_actual(row)
        pit_prediction, _ = self._pit_change_prediction_and_actual(row)
        blocked_pit_actual = actual_component(
            row,
            component_key="first_tyre_change_lap",
            component_label="First tyre-change lap",
            answer_type=AnswerType.PIT_CHANGE_LAP,
            component_order=2,
            validation_status=ActualAnswerStatus.SOURCE_BLOCKED,
            display_value="Pit stop source not covered",
        )

        report_row = build_question_report_row(
            row, (tyre_prediction, pit_prediction), (tyre_actual, blocked_pit_actual)
        )

        self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, report_row.combined_outcome)
        self.assertIsNone(report_row.combined_is_correct)
        component_rows_by_key = {
            component_row.component_key: component_row for component_row in report_row.component_rows
        }
        self.assertEqual(
            ReportRowOutcome.PREDICTION_CORRECT, component_rows_by_key["starting_tyre_compound"].outcome
        )
        self.assertEqual(
            ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, component_rows_by_key["first_tyre_change_lap"].outcome
        )
        self.assertEqual(
            ActualAnswerStatus.SOURCE_BLOCKED, component_rows_by_key["first_tyre_change_lap"].actual_answer_status
        )

    def test_multi_part_missing_component_leaves_metadata_none_without_crash(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        tyre_prediction, tyre_actual = self._tyre_prediction_and_actual(row)

        report_row = build_question_report_row(row, (tyre_prediction,), (tyre_actual,))

        self.assertEqual(2, len(report_row.component_rows))
        component_rows_by_key = {
            component_row.component_key: component_row for component_row in report_row.component_rows
        }
        pit_row = component_rows_by_key["first_tyre_change_lap"]
        self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, pit_row.outcome)
        self.assertIsNone(pit_row.actual_answer_status)
        self.assertIsNone(pit_row.source_table_or_file)
        self.assertIsNone(pit_row.source_field_or_method)
        self.assertIsNone(pit_row.known_answer_example)
        self.assertIsNone(pit_row.discrepancy_notes)
        self.assertEqual("First tyre-change lap", pit_row.component_label)
        self.assertEqual(2, pit_row.order)
        self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, report_row.combined_outcome)

    def test_multi_part_mixed_actual_unscoreable_and_prediction_unscoreable_prefers_actual(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        _, tyre_actual = self._tyre_prediction_and_actual(row)
        pit_prediction, _ = self._pit_change_prediction_and_actual(row)
        blocked_pit_actual = actual_component(
            row,
            component_key="first_tyre_change_lap",
            component_label="First tyre-change lap",
            answer_type=AnswerType.PIT_CHANGE_LAP,
            component_order=2,
            validation_status=ActualAnswerStatus.SOURCE_BLOCKED,
            display_value="Pit stop source not covered",
        )
        unavailable_tyre_prediction = unavailable_prediction(row, component_key="starting_tyre_compound")

        report_row = build_question_report_row(
            row, (unavailable_tyre_prediction, pit_prediction), (tyre_actual, blocked_pit_actual)
        )

        self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, report_row.combined_outcome)
        component_rows_by_key = {
            component_row.component_key: component_row for component_row in report_row.component_rows
        }
        self.assertEqual(
            ReportRowOutcome.PREDICTION_UNSCOREABLE, component_rows_by_key["starting_tyre_compound"].outcome
        )
        self.assertEqual(
            ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, component_rows_by_key["first_tyre_change_lap"].outcome
        )

    def test_multi_part_empty_target_components_maps_to_actual_answer_unscoreable(self) -> None:
        row = replace(supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change"), target_components=())

        report_row = build_question_report_row(row, (), ())

        self.assertEqual(0, len(report_row.component_rows))
        self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, report_row.combined_outcome)
        self.assertIsNone(report_row.combined_is_correct)
        self.assertEqual(Scoreability.UNSCOREABLE, report_row.combined_scoreability)


class BuildQuestionReportTests(unittest.TestCase):
    def test_build_question_report_across_multiple_rows_in_catalog_order(self) -> None:
        catalog_rows = supplied_pdf_question_catalog_rows()
        q01 = catalog_rows[0]
        q04 = catalog_rows[3]

        q01_prediction = available_prediction(q01, prediction_value=83.6, display_value="1:23.600")
        q01_actual = actual_component(
            q01,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_TIME,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=83.59,
            tolerance=0.05,
            display_value="1:23.590",
            source_field_or_method=(
                "minimum Williams race lap time (source_grade=official_timing; coverage_status=validated)"
            ),
        )

        q04_prediction = available_prediction(q04, prediction_value=60, display_value="Lap 60")
        q04_actual = actual_component(
            q04,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        predictions_by_question_id = {
            q01.question_id: (q01_prediction,),
            q04.question_id: (q04_prediction,),
        }
        actual_components_by_question_id = {
            q01.question_id: (q01_actual,),
            q04.question_id: (q04_actual,),
        }

        report = build_question_report(catalog_rows, predictions_by_question_id, actual_components_by_question_id)

        self.assertEqual(len(catalog_rows), len(report))
        self.assertEqual(
            tuple(row.question_id for row in catalog_rows), tuple(row.question_id for row in report)
        )

        report_by_id = {row.question_id: row for row in report}
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, report_by_id[q01.question_id].combined_outcome)
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, report_by_id[q04.question_id].combined_outcome)

        for row in catalog_rows:
            if row.question_id in (q01.question_id, q04.question_id):
                continue
            row_report = report_by_id[row.question_id]
            self.assertEqual(Scoreability.UNSCOREABLE, row_report.combined_scoreability)
            self.assertIn(
                row_report.combined_outcome,
                (ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, ReportRowOutcome.PREDICTION_UNSCOREABLE),
            )


class SerializationTests(unittest.TestCase):
    def test_component_report_row_to_record_uses_plain_values(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        report_row = build_question_report_row(row, (prediction,), (actual,))
        record = component_report_row_to_record(report_row.component_rows[0])

        self.assertIsInstance(record, dict)
        self.assertEqual("prediction_correct", record["outcome"])
        self.assertEqual("computed", record["actual_answer_status"])
        self.assertEqual("scoreable", record["scoreability"])
        self.assertEqual("exact_match", record["scoring_rule"])

    def test_question_report_row_to_record_nests_component_records(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value="Lap 60",
        )

        report_row = build_question_report_row(row, (prediction,), (actual,))
        record = question_report_row_to_record(report_row)

        self.assertEqual(1, len(record["component_rows"]))
        self.assertIsInstance(record["component_rows"][0], dict)
        self.assertEqual("prediction_correct", record["combined_outcome"])
        self.assertEqual("scoreable", record["combined_scoreability"])


if __name__ == "__main__":
    unittest.main()
