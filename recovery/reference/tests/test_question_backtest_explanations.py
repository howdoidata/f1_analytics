from __future__ import annotations

import unittest

from f1_analytics.analysis.question_answers import ActualAnswerStatus, TyreCompound
from f1_analytics.analysis.question_backtest_explanations import (
    NarrativeContextNote,
    PortfolioQuestionExplanation,
    build_portfolio_explanations,
    build_portfolio_question_explanation,
    portfolio_question_explanation_to_record,
)
from f1_analytics.analysis.question_backtest_report import ReportRowOutcome, build_question_report_row
from f1_analytics.analysis.question_backtest_scoring import Scoreability
from f1_analytics.analysis.question_catalog import AnswerType, supplied_pdf_question_catalog_rows

from tests.test_question_backtest_report import (
    actual_component,
    available_prediction,
    supplied_row,
    unavailable_prediction,
)


FORBIDDEN_PUBLIC_TERMS = ("betting", "odds", "gambling", "wagering")


def all_public_text(explanation: PortfolioQuestionExplanation) -> tuple[str, ...]:
    texts = [explanation.summary_text, *explanation.component_texts, *explanation.source_references]
    if explanation.narrative_text is not None:
        texts.append(explanation.narrative_text)
    return tuple(texts)


class BuildPortfolioQuestionExplanationSingleAnswerTests(unittest.TestCase):
    def test_scoreable_correct_explanation_names_subject_race_score_and_source(self) -> None:
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
            source_table_or_file="lap_times",
            source_field_or_method="fastest Williams lap method",
        )
        report_row = build_question_report_row(row, (prediction,), (actual,))

        explanation = build_portfolio_question_explanation(row, report_row)

        self.assertEqual(row.question_id, explanation.question_id)
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, explanation.combined_outcome)
        self.assertEqual(Scoreability.SCOREABLE, explanation.combined_scoreability)
        self.assertLessEqual(len(explanation.summary_text), 320)
        for expected_text in (
            "Carlos Sainz",
            "Williams F1 Team",
            "2026 Spanish Grand Prix",
            "Prediction Lap 60",
            "actual Lap 60",
            "scoreable",
            "tolerance 0",
            "lap_times",
            "fastest Williams lap method",
        ):
            self.assertIn(expected_text, explanation.summary_text)
        self.assertEqual(("lap_times", "fastest Williams lap method"), explanation.source_references)

    def test_scoreable_incorrect_explanation_reports_prediction_vs_actual_without_source_blocking(self) -> None:
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
            source_table_or_file="lap_times",
            source_field_or_method="fastest Williams lap method",
        )
        report_row = build_question_report_row(row, (prediction,), (actual,))

        explanation = build_portfolio_question_explanation(row, report_row)

        self.assertEqual(ReportRowOutcome.PREDICTION_INCORRECT, explanation.combined_outcome)
        self.assertIn("Prediction Lap 58", explanation.summary_text)
        self.assertIn("actual Lap 60", explanation.summary_text)
        self.assertIn("did not match", explanation.summary_text)
        self.assertNotIn("source-blocked", explanation.summary_text.lower())

    def test_scoreable_prediction_display_falls_back_to_machine_value(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value=None)
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

        explanation = build_portfolio_question_explanation(row, report_row)

        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT, explanation.combined_outcome)
        self.assertIn("Prediction 60", explanation.summary_text)
        self.assertNotIn("Prediction unavailable", explanation.summary_text)

    def test_required_source_facts_are_preserved_when_scoreable_text_is_shortened(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        long_display = "Lap 60 " + "with extended public detail " * 12
        prediction = available_prediction(row, prediction_value=60, display_value=long_display)
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=60,
            tolerance=0,
            display_value=long_display,
            source_table_or_file="lap_times_required_source",
            source_field_or_method="required fastest Williams lap method",
        )
        report_row = build_question_report_row(row, (prediction,), (actual,))

        explanation = build_portfolio_question_explanation(row, report_row, max_summary_chars=220)

        self.assertLessEqual(len(explanation.summary_text), 220)
        self.assertIn("lap_times_required_source", explanation.summary_text)
        self.assertIn("required fastest Williams lap method", explanation.summary_text)


class BuildPortfolioQuestionExplanationUnscoreableTests(unittest.TestCase):
    def test_actual_answer_unscoreable_statuses_do_not_imply_prediction_was_wrong(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        statuses = (
            ActualAnswerStatus.SOURCE_BLOCKED,
            ActualAnswerStatus.PARTIAL,
            ActualAnswerStatus.DISCREPANT_NEEDS_REVIEW,
        )
        forbidden_wrong_terms = ("wrong", "incorrect", "did not match")
        for status in statuses:
            with self.subTest(status=status):
                actual = actual_component(
                    row,
                    component_key="actual_answer",
                    component_label="Actual answer",
                    answer_type=AnswerType.LAP_NUMBER,
                    component_order=1,
                    validation_status=status,
                    display_value=f"{status.value} target",
                    source_table_or_file="lap_times",
                    source_field_or_method="fastest Williams lap method",
                    discrepancy_notes="component needs source review",
                )
                report_row = build_question_report_row(row, (prediction,), (actual,))

                explanation = build_portfolio_question_explanation(row, report_row)

                self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, explanation.combined_outcome)
                self.assertIn(status.value, explanation.summary_text)
                self.assertIn("unscoreable", explanation.summary_text)
                lowered = explanation.summary_text.lower()
                for forbidden in forbidden_wrong_terms:
                    self.assertNotIn(forbidden, lowered)

    def test_prediction_unscoreable_explanation_blames_unavailable_prediction_not_actual_source(self) -> None:
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
            source_table_or_file="lap_times",
            source_field_or_method="fastest Williams lap method",
        )
        report_row = build_question_report_row(row, (prediction,), (actual,))

        explanation = build_portfolio_question_explanation(row, report_row)

        self.assertEqual(ReportRowOutcome.PREDICTION_UNSCOREABLE, explanation.combined_outcome)
        self.assertIn("Prediction unavailable", explanation.summary_text)
        self.assertIn("actual target Lap 60", explanation.summary_text)
        self.assertNotIn("source-blocked", explanation.summary_text.lower())
        self.assertNotIn("wrong", explanation.summary_text.lower())

    def test_invalid_prediction_is_not_described_as_unavailable(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value="lap sixty", display_value=None)
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

        explanation = build_portfolio_question_explanation(row, report_row)

        self.assertEqual(ReportRowOutcome.PREDICTION_UNSCOREABLE, explanation.combined_outcome)
        self.assertIn("Prediction is not scoreable", explanation.summary_text)
        self.assertIn("Prediction value 'lap sixty' is not a numeric value", explanation.summary_text)
        self.assertNotIn("Prediction unavailable", explanation.summary_text)

    def test_actual_unscoreable_includes_scoring_reason(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        prediction = available_prediction(row, prediction_value=60, display_value="Lap 60")
        actual = actual_component(
            row,
            component_key="actual_answer",
            component_label="Actual answer",
            answer_type=AnswerType.LAP_NUMBER,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value="sixty",
            tolerance=0,
            display_value="Lap 60",
        )
        report_row = build_question_report_row(row, (prediction,), (actual,))

        explanation = build_portfolio_question_explanation(row, report_row)

        self.assertEqual(ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE, explanation.combined_outcome)
        self.assertIn("reason Actual numeric value 'sixty' is not a numeric value", explanation.summary_text)
        self.assertIn("reason Actual numeric value 'sixty' is not a numeric value", explanation.component_texts[0])


class BuildPortfolioQuestionExplanationMultiPartTests(unittest.TestCase):
    def test_multi_part_components_stay_separate_from_british_gp_narrative_note(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        tyre_prediction = available_prediction(
            row, component_key="starting_tyre_compound", prediction_value="medium", display_value="medium"
        )
        tyre_actual = actual_component(
            row,
            component_key="starting_tyre_compound",
            component_label="Starting tyre compound",
            answer_type=AnswerType.TYRE_COMPOUND,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            categorical_value=TyreCompound.MEDIUM,
            display_value="medium",
            source_table_or_file="race_starts",
            source_field_or_method="starting tyre source",
        )
        pit_prediction = available_prediction(
            row, component_key="first_tyre_change_lap", prediction_value=1, display_value="Lap 1"
        )
        pit_actual = actual_component(
            row,
            component_key="first_tyre_change_lap",
            component_label="First tyre-change lap",
            answer_type=AnswerType.PIT_CHANGE_LAP,
            component_order=2,
            validation_status=ActualAnswerStatus.COMPUTED,
            numeric_value=1,
            tolerance=0,
            display_value="Lap 1",
            source_table_or_file="pit_stops",
            source_field_or_method="first tyre-change source",
        )
        report_row = build_question_report_row(row, (tyre_prediction, pit_prediction), (tyre_actual, pit_actual))
        note = NarrativeContextNote(
            question_id=row.question_id,
            text="Lap 1 collision and restart explain why public context may mention a front-wing change.",
            source_label="British GP incident/restart note",
            related_component_keys=("starting_tyre_compound", "first_tyre_change_lap"),
            status_reference="deterministic components remain computed source-backed targets",
        )

        explanation = build_portfolio_question_explanation(row, report_row, narrative_notes=(note,))

        self.assertEqual(2, len(explanation.component_texts))
        self.assertIn("Starting tyre compound", explanation.component_texts[0])
        self.assertIn("First tyre-change lap", explanation.component_texts[1])
        self.assertNotIn("front-wing", " ".join(explanation.component_texts))
        self.assertIsNotNone(explanation.narrative_text)
        self.assertIn("British GP incident/restart note", explanation.narrative_text)
        self.assertIn("deterministic components remain computed source-backed targets", explanation.narrative_text)
        self.assertIn("starting_tyre_compound", explanation.narrative_text)
        self.assertIn("front-wing", explanation.narrative_text)

    def test_forbidden_public_framing_terms_are_removed_from_generated_text(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        tyre_prediction = available_prediction(
            row, component_key="starting_tyre_compound", prediction_value="medium", display_value="medium"
        )
        tyre_actual = actual_component(
            row,
            component_key="starting_tyre_compound",
            component_label="Starting tyre compound",
            answer_type=AnswerType.TYRE_COMPOUND,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            categorical_value=TyreCompound.MEDIUM,
            display_value="medium",
        )
        report_row = build_question_report_row(row, (tyre_prediction,), (tyre_actual,))
        note = NarrativeContextNote(
            question_id=row.question_id,
            text="Remove betting odds, gambling angle, and wagering framing from this public note.",
            source_label="betting odds public copy review",
            related_component_keys=("starting_tyre_compound",),
            status_reference="actual status computed",
        )

        explanation = build_portfolio_question_explanation(row, report_row, narrative_notes=(note,))

        self.assertIn("prediction framing prediction framing public copy review", explanation.source_references)
        for public_text in all_public_text(explanation):
            lowered = public_text.lower()
            for forbidden in FORBIDDEN_PUBLIC_TERMS:
                self.assertNotIn(forbidden, lowered)

    def test_generator_narrative_notes_render_once_and_filter_wrong_question_sources(self) -> None:
        row = supplied_row("2026_pdf_q05_british_albon_start_tyre_and_first_change")
        other_row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        tyre_prediction = available_prediction(
            row, component_key="starting_tyre_compound", prediction_value="medium", display_value="medium"
        )
        tyre_actual = actual_component(
            row,
            component_key="starting_tyre_compound",
            component_label="Starting tyre compound",
            answer_type=AnswerType.TYRE_COMPOUND,
            component_order=1,
            validation_status=ActualAnswerStatus.COMPUTED,
            categorical_value=TyreCompound.MEDIUM,
            display_value="medium",
        )
        report_row = build_question_report_row(row, (tyre_prediction,), (tyre_actual,))
        notes = (
            note
            for note in (
                NarrativeContextNote(
                    question_id=row.question_id,
                    text="Lap 1 restart context stays narrative-only.",
                    source_label="matching British GP note",
                    related_component_keys=("starting_tyre_compound",),
                    status_reference="actual status computed",
                ),
                NarrativeContextNote(
                    question_id=other_row.question_id,
                    text="Wrong question note must not leak.",
                    source_label="wrong question source",
                ),
            )
        )

        explanation = build_portfolio_question_explanation(row, report_row, narrative_notes=notes)

        self.assertIsNotNone(explanation.narrative_text)
        self.assertIn("matching British GP note", explanation.narrative_text)
        self.assertIn("matching British GP note", explanation.source_references)
        self.assertNotIn("wrong question source", explanation.source_references)
        self.assertNotIn("wrong question source", explanation.narrative_text)


class PortfolioExplanationWrapperAndSerializationTests(unittest.TestCase):
    def test_question_id_mismatch_raises_value_error(self) -> None:
        row = supplied_row("2026_pdf_q04_barcelona_sainz_fastest_lap_number")
        other_row = supplied_row("2026_pdf_q03_canadian_highest_williams_finish")
        prediction = available_prediction(other_row, prediction_value=9, display_value="P9")
        actual = actual_component(
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
        report_row = build_question_report_row(other_row, (prediction,), (actual,))

        with self.assertRaises(ValueError):
            build_portfolio_question_explanation(row, report_row)

    def test_wrapper_preserves_catalog_order_and_missing_report_raises_key_error(self) -> None:
        catalog_rows = supplied_pdf_question_catalog_rows()[:2]
        report_rows_by_question_id = {}
        for row in reversed(catalog_rows):
            prediction = available_prediction(row, prediction_value=19, display_value="P9 + P10 = 19")
            actual = actual_component(
                row,
                component_key="actual_answer",
                component_label="Actual answer",
                answer_type=row.answer_type,
                component_order=1,
                validation_status=ActualAnswerStatus.COMPUTED,
                numeric_value=19,
                tolerance=0,
                display_value="P9 + P10 = 19",
            )
            report_rows_by_question_id[row.question_id] = build_question_report_row(row, (prediction,), (actual,))

        explanations = build_portfolio_explanations(catalog_rows, report_rows_by_question_id)

        self.assertEqual(tuple(row.question_id for row in catalog_rows), tuple(item.question_id for item in explanations))
        with self.assertRaises(KeyError):
            build_portfolio_explanations(catalog_rows, {catalog_rows[0].question_id: report_rows_by_question_id[catalog_rows[0].question_id]})

    def test_serialization_emits_plain_values(self) -> None:
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
        explanation = build_portfolio_question_explanation(row, report_row)

        record = portfolio_question_explanation_to_record(explanation)

        self.assertEqual(row.question_id, record["question_id"])
        self.assertIsInstance(record["component_texts"], tuple)
        self.assertEqual(ReportRowOutcome.PREDICTION_CORRECT.value, record["combined_outcome"])
        self.assertEqual(Scoreability.SCOREABLE.value, record["combined_scoreability"])

    def test_tiny_summary_width_raises_clear_value_error(self) -> None:
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

        with self.assertRaisesRegex(ValueError, "max_chars must be at least 4"):
            build_portfolio_question_explanation(row, report_row, max_summary_chars=3)


if __name__ == "__main__":
    unittest.main()
