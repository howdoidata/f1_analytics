"""Portfolio-facing explanation text for question backtest report rows."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from f1_analytics.analysis.question_backtest_report import ComponentReportRow, QuestionReportRow, ReportRowOutcome
from f1_analytics.analysis.question_backtest_scoring import Scoreability
from f1_analytics.analysis.question_catalog import AnswerType, QuestionCatalogRow


FORBIDDEN_PUBLIC_FRAMING_TERMS = ("betting", "odds", "gambling", "wagering")
_TRUNCATION_PLACEHOLDER = "..."

_FORBIDDEN_PUBLIC_FRAMING_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in FORBIDDEN_PUBLIC_FRAMING_TERMS) + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NarrativeContextNote:
    """Optional public narrative context kept separate from deterministic target values."""

    question_id: str
    text: str
    source_label: str
    related_component_keys: tuple[str, ...] = ()
    status_reference: str | None = None


@dataclass(frozen=True)
class PortfolioQuestionExplanation:
    """Concise public explanation text for one report row."""

    question_id: str
    summary_text: str
    component_texts: tuple[str, ...]
    narrative_text: str | None
    source_references: tuple[str, ...]
    combined_outcome: ReportRowOutcome
    combined_scoreability: Scoreability


def build_portfolio_question_explanation(
    catalog_row: QuestionCatalogRow,
    report_row: QuestionReportRow,
    narrative_notes: Iterable[NarrativeContextNote] = (),
    max_summary_chars: int = 320,
) -> PortfolioQuestionExplanation:
    """Build a concise public explanation from an already-built report row."""
    if catalog_row.question_id != report_row.question_id:
        raise ValueError(
            f"Catalog row question_id {catalog_row.question_id!r} does not match report row "
            f"question_id {report_row.question_id!r}."
        )
    notes = tuple(narrative_notes)

    subject_phrase = _subject_phrase(catalog_row)
    race_phrase = f"{catalog_row.season} {catalog_row.grand_prix}"
    component_texts = tuple(_component_text(component) for component in report_row.component_rows)
    source_references = _source_references(report_row.component_rows, notes, catalog_row.question_id)
    summary_text = _summary_text(subject_phrase, race_phrase, report_row, max_summary_chars)
    narrative_text = _narrative_text(catalog_row.question_id, notes)

    return PortfolioQuestionExplanation(
        question_id=report_row.question_id,
        summary_text=summary_text,
        component_texts=component_texts,
        narrative_text=narrative_text,
        source_references=source_references,
        combined_outcome=report_row.combined_outcome,
        combined_scoreability=report_row.combined_scoreability,
    )


def build_portfolio_explanations(
    catalog_rows: Iterable[QuestionCatalogRow],
    report_rows_by_question_id: Mapping[str, QuestionReportRow],
    narrative_notes_by_question_id: Mapping[str, Iterable[NarrativeContextNote]] | None = None,
) -> tuple[PortfolioQuestionExplanation, ...]:
    """Build portfolio explanations in catalog-row order."""
    explanations: list[PortfolioQuestionExplanation] = []
    notes_by_question_id = narrative_notes_by_question_id or {}
    for catalog_row in catalog_rows:
        if catalog_row.question_id not in report_rows_by_question_id:
            raise KeyError(catalog_row.question_id)
        explanations.append(
            build_portfolio_question_explanation(
                catalog_row,
                report_rows_by_question_id[catalog_row.question_id],
                narrative_notes=notes_by_question_id.get(catalog_row.question_id, ()),
            )
        )
    return tuple(explanations)


def portfolio_question_explanation_to_record(explanation: PortfolioQuestionExplanation) -> dict[str, object]:
    """Return a deterministic, dependency-free dict record for one explanation."""
    return {
        "question_id": explanation.question_id,
        "summary_text": explanation.summary_text,
        "component_texts": explanation.component_texts,
        "narrative_text": explanation.narrative_text,
        "source_references": explanation.source_references,
        "combined_outcome": _enum_value(explanation.combined_outcome),
        "combined_scoreability": _enum_value(explanation.combined_scoreability),
    }


def _summary_text(
    subject_phrase: str,
    race_phrase: str,
    report_row: QuestionReportRow,
    max_summary_chars: int,
) -> str:
    prefix = f"{subject_phrase}, {race_phrase}: "
    if _is_multi_part(report_row.answer_type):
        text = prefix + _multi_part_summary(report_row)
    elif report_row.combined_outcome is ReportRowOutcome.PREDICTION_CORRECT:
        text = prefix + _scoreable_summary(report_row, "matched")
    elif report_row.combined_outcome is ReportRowOutcome.PREDICTION_INCORRECT:
        text = prefix + _scoreable_summary(report_row, "did not match")
    elif report_row.combined_outcome is ReportRowOutcome.PREDICTION_UNSCOREABLE:
        text = prefix + _prediction_unscoreable_summary(report_row)
    else:
        text = prefix + _actual_unscoreable_summary(report_row)
    return _short_public_text(text, max_summary_chars)


def _multi_part_summary(report_row: QuestionReportRow) -> str:
    component_count = len(report_row.component_rows)
    if report_row.combined_scoreability is Scoreability.SCOREABLE:
        return (
            f"Multi-part target is scoreable across {component_count} components; "
            f"combined outcome {_friendly_enum_value(report_row.combined_outcome)}. "
            "Component lines keep prediction, actual, status, and source details separate."
        )
    if report_row.combined_outcome is ReportRowOutcome.PREDICTION_UNSCOREABLE:
        return (
            f"Multi-part target has {component_count} components, but at least one prediction is unavailable; "
            "component lines keep actual target status separate."
        )
    return (
        f"Multi-part target is unresolved/unscoreable across {component_count} components because at least "
        "one actual component status or source state is not scoreable."
    )


def _scoreable_summary(report_row: QuestionReportRow, result_phrase: str) -> str:
    component = _first_component(report_row)
    if component is None:
        return f"Scoreable result {result_phrase}, but no component row was available."

    parts = [f"{_friendly_enum_value(component.scoreability)} via {_friendly_enum_value(component.scoring_rule)}"]
    source = _component_source_phrase(component)
    if source:
        parts.append(f"Source: {source}")
    parts.append(
        f"Prediction {_prediction_display(component)} {result_phrase} actual {_display(component.actual_display_value)}"
    )
    if component.absolute_error is not None or component.tolerance is not None:
        parts.append(f"error {_display(component.absolute_error)}/tolerance {_display(component.tolerance)}")
    return "; ".join(parts) + "."


def _actual_unscoreable_summary(report_row: QuestionReportRow) -> str:
    component = _first_unscoreable_actual_component(report_row) or _first_component(report_row)
    if component is None:
        return "Target is unresolved/unscoreable because no component row is available."

    status = _enum_value(component.actual_answer_status) or "missing_actual_status"
    parts = [
        f"Target is unresolved/unscoreable; actual status {status}",
        f"component {component.component_key}",
    ]
    source = _component_source_phrase(component)
    if source:
        parts.append(f"Source: {source}")
    if component.explanation:
        parts.append(f"reason {_neutralize_public_text(component.explanation)}")
    if component.actual_display_value:
        parts.append(f"current target display {_display(component.actual_display_value)}")
    if component.prediction_display_value:
        parts.append(f"prediction {_prediction_display(component)} is not evaluated until actual is trusted")
    if component.discrepancy_notes:
        parts.append(component.discrepancy_notes)
    return "; ".join(parts) + "."


def _prediction_unscoreable_summary(report_row: QuestionReportRow) -> str:
    component = _first_prediction_unscoreable_component(report_row) or _first_component(report_row)
    if component is None:
        return "Prediction unavailable; no scoreable prediction component is available."

    parts = [_prediction_issue_phrase(component)]
    if component.actual_display_value:
        status = _enum_value(component.actual_answer_status) or "unknown_status"
        parts.append(f"actual target {_display(component.actual_display_value)} is available ({status})")
    source = _component_source_phrase(component)
    if source:
        parts.append(f"Source: {source}")
    if component.explanation:
        parts.append(f"reason {_neutralize_public_text(component.explanation)}")
    return "; ".join(parts) + "."


def _component_text(component: ComponentReportRow) -> str:
    if component.scoreability is Scoreability.SCOREABLE:
        result = "matched" if component.is_correct else "did not match"
        parts = [f"{component.component_label}: status {_friendly_enum_value(component.actual_answer_status)}"]
        source = _component_source_phrase(component)
        if source:
            parts.append(f"source {source}")
        parts.append(
            f"prediction {_prediction_display(component)} {result} actual {_display(component.actual_display_value)}"
        )
        if component.absolute_error is not None or component.tolerance is not None:
            parts.append(f"error {_display(component.absolute_error)}/tolerance {_display(component.tolerance)}")
    elif component.outcome is ReportRowOutcome.PREDICTION_UNSCOREABLE:
        parts = [
            f"{component.component_label}: {_prediction_issue_phrase(component)}",
            f"actual target {_display(component.actual_display_value)}",
            f"status {_friendly_enum_value(component.actual_answer_status)}",
        ]
    else:
        parts = [
            f"{component.component_label}: actual target unresolved/unscoreable",
            f"status {_friendly_enum_value(component.actual_answer_status)}",
        ]
        if component.explanation:
            parts.append(f"reason {_neutralize_public_text(component.explanation)}")
        if component.prediction_display_value or component.prediction_value is not None:
            parts.append(f"prediction {_prediction_display(component)} not evaluated")

    source = _component_source_phrase(component)
    if source and f"source {source}" not in parts:
        parts.append(f"source {source}")
    return _short_public_text("; ".join(parts) + ".", 220)


def _narrative_text(question_id: str, narrative_notes: Iterable[NarrativeContextNote]) -> str | None:
    parts = []
    for note in narrative_notes:
        if note.question_id != question_id:
            continue
        source_label = _neutralize_public_text(note.source_label)
        status_reference = _neutralize_public_text(note.status_reference) if note.status_reference else None
        component_reference = ", ".join(note.related_component_keys)
        reference_parts = [f"Narrative source {source_label}."]
        if status_reference:
            reference_parts.append(f"Status: {status_reference}.")
        if component_reference:
            reference_parts.append(f"Components: {component_reference}.")
        if _has_forbidden_public_framing(note.text):
            text = " ".join(reference_parts) + " Public framing omitted."
        else:
            text = " ".join(reference_parts) + f" {_neutralize_public_text(note.text)}"
        parts.append(text)
    if not parts:
        return None
    return _short_public_text(" ".join(parts), 320)


def _subject_phrase(catalog_row: QuestionCatalogRow) -> str:
    subject = (
        _non_empty(catalog_row.driver_scope)
        or _non_empty(catalog_row.target_subject_scope)
        or _non_empty(catalog_row.team_scope)
        or "the target"
    )
    team = _non_empty(catalog_row.team_scope)
    if team and not _effectively_included(team, subject):
        return f"{subject} ({team})"
    return subject


def _is_multi_part(answer_type: AnswerType | str) -> bool:
    try:
        return answer_type is AnswerType.MULTI_PART or AnswerType(answer_type) is AnswerType.MULTI_PART
    except (ValueError, TypeError):
        return False


def _source_references(
    component_rows: Iterable[ComponentReportRow],
    narrative_notes: Iterable[NarrativeContextNote],
    question_id: str,
) -> tuple[str, ...]:
    references: list[str] = []
    for component in component_rows:
        _append_unique(references, component.source_table_or_file)
        _append_unique(references, component.source_field_or_method)
    for note in narrative_notes:
        if note.question_id == question_id:
            _append_unique(references, note.source_label)
    return tuple(references)


def _first_component(report_row: QuestionReportRow) -> ComponentReportRow | None:
    return report_row.component_rows[0] if report_row.component_rows else None


def _first_unscoreable_actual_component(report_row: QuestionReportRow) -> ComponentReportRow | None:
    for component in report_row.component_rows:
        if component.outcome is ReportRowOutcome.ACTUAL_ANSWER_UNSCOREABLE:
            return component
    return None


def _first_prediction_unscoreable_component(report_row: QuestionReportRow) -> ComponentReportRow | None:
    for component in report_row.component_rows:
        if component.outcome is ReportRowOutcome.PREDICTION_UNSCOREABLE:
            return component
    return None


def _component_source_phrase(component: ComponentReportRow) -> str:
    return "; ".join(
        value for value in (component.source_table_or_file, component.source_field_or_method) if _non_empty(value)
    )


def _short_public_text(text: str, max_chars: int) -> str:
    if max_chars < len(_TRUNCATION_PLACEHOLDER) + 1:
        raise ValueError(
            f"max_chars must be at least {len(_TRUNCATION_PLACEHOLDER) + 1} "
            f"when using the {_TRUNCATION_PLACEHOLDER!r} truncation placeholder."
        )
    neutralized = _neutralize_public_text(" ".join(text.split()))
    if len(neutralized) <= max_chars:
        return neutralized
    return textwrap.shorten(neutralized, width=max_chars, placeholder=_TRUNCATION_PLACEHOLDER)


def _neutralize_public_text(text: object) -> str:
    return _FORBIDDEN_PUBLIC_FRAMING_PATTERN.sub("prediction framing", str(text))


def _has_forbidden_public_framing(text: str) -> bool:
    return _FORBIDDEN_PUBLIC_FRAMING_PATTERN.search(str(text or "")) is not None


def _prediction_display(component: ComponentReportRow) -> str:
    if component.prediction_display_value:
        return component.prediction_display_value
    return _display(component.prediction_value)


def _prediction_issue_phrase(component: ComponentReportRow) -> str:
    if component.prediction_display_value or component.prediction_value is not None:
        return "Prediction is not scoreable"
    return "Prediction unavailable; no scoreable prediction is available"


def _display(value: object) -> str:
    if value is None:
        return "unavailable"
    return str(value)


def _non_empty(value: str | None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _effectively_included(candidate: str, text: str) -> bool:
    normalized_candidate = _normalize_for_inclusion(candidate)
    normalized_text = _normalize_for_inclusion(text)
    if normalized_candidate in normalized_text:
        return True
    candidate_tokens = set(normalized_candidate.split())
    text_tokens = set(normalized_text.split())
    meaningful_candidate_tokens = {token for token in candidate_tokens if len(token) > 2}
    return bool(meaningful_candidate_tokens) and meaningful_candidate_tokens <= text_tokens


def _normalize_for_inclusion(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _append_unique(values: list[str], candidate: str | None) -> None:
    if candidate is not None and candidate.strip():
        neutralized_candidate = _neutralize_public_text(candidate.strip())
        if neutralized_candidate not in values:
            values.append(neutralized_candidate)


def _enum_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def _friendly_enum_value(value: object) -> object:
    enum_value = _enum_value(value)
    if isinstance(enum_value, str):
        return enum_value.replace("_", " ")
    return enum_value
