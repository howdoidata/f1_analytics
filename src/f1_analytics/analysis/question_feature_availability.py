"""Feature availability contract for leakage-safe question prediction work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Iterable

from f1_analytics.analysis.question_catalog import (
    AnalysisMode,
    FeatureSnapshotBoundary,
    FeatureSnapshotSessionBoundary,
    POST_RACE_FORBIDDEN_FEATURE_GROUPS,
    QuestionCatalogRow,
    supplied_pdf_question_catalog_rows,
    validate_feature_snapshot_boundary,
)


class FeatureAvailabilityStatus(str, Enum):
    """Controlled availability labels for candidate prediction feature groups."""

    ALREADY_AVAILABLE = "already_available"
    DERIVABLE_FROM_CURRENT_TABLES = "derivable_from_current_tables"
    REQUIRES_NEW_SOURCE = "requires_new_source"
    USER_SUPPLIED = "user_supplied"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class FeatureGroupAvailability:
    """One feature group row in the availability contract."""

    group_key: str
    display_label: str
    availability_status: FeatureAvailabilityStatus | str
    pre_race_usable: bool
    leakage_status: str
    source_boundary: FeatureSnapshotBoundary
    source_tables_or_artifacts_inspected: tuple[str, ...]
    current_evidence_summary: str
    question_scope: tuple[str, ...]
    build_timestamp_or_id: str
    reason: str
    forbidden_fact_group: str | None = None


@dataclass(frozen=True)
class FeatureAvailabilityContract:
    """Aggregate feature availability contract for a question scope."""

    analysis_mode: AnalysisMode | str
    question_scope: tuple[str, ...]
    source_boundary: FeatureSnapshotBoundary
    build_timestamp_or_id: str
    feature_groups: tuple[FeatureGroupAvailability, ...]
    source_tables_or_artifacts_inspected: tuple[str, ...]
    prediction_inputs: tuple[()] = ()
    actual_answer_components: tuple[()] = ()


@dataclass(frozen=True)
class FeatureAvailabilityValidationError:
    """Structured validation failure for feature availability contracts."""

    field_name: str
    message: str
    error_code: str


BASE_FEATURE_GROUP_DEFINITIONS = (
    {
        "group_key": "results_form",
        "display_label": "Results form",
        "availability_status": FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        "source_tables": (
            "results",
            "combined_results",
            "driver_standings_by_round",
            "combined_driver_standings_by_round",
            "race_results_enriched",
            "dataset-precedence-decision-record.md",
        ),
        "evidence": (
            "Historical finishing, points, grid, laps, status, standings, and source precedence context are "
            "available for pre-target-event form features."
        ),
        "reason": (
            "Historical result form is derivable before the target race; completed target-event results remain "
            "forbidden post-race facts for pre_race inputs."
        ),
    },
    {
        "group_key": "qualifying_form",
        "display_label": "Qualifying form",
        "availability_status": FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        "source_tables": ("qualifying", "raw_jolpica_qualifying"),
        "evidence": "Qualifying position and segment timing surfaces exist locally with event-boundary caveats.",
        "reason": (
            "Qualifying form is usable for before_race_start snapshots only when qualifying has occurred before "
            "the prediction cutoff."
        ),
    },
    {
        "group_key": "track_history",
        "display_label": "Track history",
        "availability_status": FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        "source_tables": ("races", "circuits"),
        "evidence": "Race calendar and circuit metadata are available locally for historical venue context.",
        "reason": "Track history can be derived from race and circuit tables without target-event race results.",
    },
    {
        "group_key": "driver_history",
        "display_label": "Driver history",
        "availability_status": FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        "source_tables": (
            "drivers",
            "results",
            "combined_results",
            "driver_standings_by_round",
            "combined_driver_standings_by_round",
        ),
        "evidence": "Driver identity, historical results, and standings surfaces exist locally.",
        "reason": "Driver history is derivable when filtered to facts before the target event boundary.",
    },
    {
        "group_key": "constructor_performance",
        "display_label": "Constructor performance",
        "availability_status": FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        "source_tables": (
            "constructors",
            "combined_results",
            "constructor_standings_by_round",
            "combined_constructor_standings_by_round",
        ),
        "evidence": "Constructor identity, results, and standings surfaces exist locally.",
        "reason": "Constructor performance is derivable when limited to historical facts before the target event.",
    },
    {
        "group_key": "pit_tyre_tendencies",
        "display_label": "Pit/tyre tendencies",
        "availability_status": FeatureAvailabilityStatus.REQUIRES_NEW_SOURCE,
        "source_tables": ("raw_jolpica_pitstops", "OpenF1 candidate source"),
        "evidence": (
            "Historical pit-stop lap and stop patterns are locally derivable. OpenF1's stints endpoint "
            "(Story 7.2) verified starting tyre compound for one driver/session live, but this group's "
            "broader stint-compound and tendency facts are not yet wired to that source and remain "
            "source-blocked."
        ),
        "reason": (
            "The group is conservatively source-blocked because current local pit-stop fields do not include "
            "tyre compound or stint compound evidence."
        ),
    },
    {
        "group_key": "weather_session_conditions",
        "display_label": "Weather/session conditions",
        "availability_status": FeatureAvailabilityStatus.REQUIRES_NEW_SOURCE,
        "source_tables": ("OpenF1 candidate source",),
        "evidence": "OpenF1 has candidate weather and session-condition surfaces, but no verified local source exists.",
        "reason": "Weather and session conditions require a verified local/free source before they can be prediction inputs.",
    },
    {
        "group_key": "source_freshness",
        "display_label": "Source freshness",
        "availability_status": FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        "source_tables": (
            "source_load_log",
            "source_registry",
            "kaggle_jolpica_coverage",
            "local table metadata",
        ),
        "evidence": "Load logs, registry rows, coverage view, and build timestamps can support freshness checks.",
        "reason": "Freshness and coverage indicators are derivable from existing metadata and generated build context.",
    },
)

FORBIDDEN_FACT_SOURCE_TABLES = {
    "results": ("results", "combined_results", "race_results_enriched"),
    "fastest_laps": ("raw_jolpica_results", "raw_jolpica_laps", "combined_results"),
    "pit_stops": ("raw_jolpica_pitstops",),
    "tyre_changes": ("raw_jolpica_pitstops", "OpenF1 candidate source"),
    "incidents": ("OpenF1 candidate source", "race-control/session narrative candidate source"),
    "retirements": ("results", "raw_jolpica_results", "combined_results"),
    "race_control_messages": ("OpenF1 candidate source", "race-control/session narrative candidate source"),
}

PRE_RACE_USABLE_AVAILABILITY_STATUSES = frozenset(
    {
        FeatureAvailabilityStatus.ALREADY_AVAILABLE,
        FeatureAvailabilityStatus.DERIVABLE_FROM_CURRENT_TABLES,
        FeatureAvailabilityStatus.USER_SUPPLIED,
    }
)

QUALIFYING_UNAVAILABLE_SESSION_BOUNDARIES = frozenset(
    {
        FeatureSnapshotSessionBoundary.BEFORE_EVENT_START,
        FeatureSnapshotSessionBoundary.BEFORE_QUALIFYING,
    }
)


def build_supplied_pdf_feature_availability_contract(
    catalog_rows: Iterable[QuestionCatalogRow] | None = None,
    build_timestamp_or_id: str | None = None,
    analysis_mode: AnalysisMode | str = AnalysisMode.PRE_RACE,
) -> FeatureAvailabilityContract:
    """Build the conservative availability contract for the supplied PDF question set."""
    rows = tuple(catalog_rows) if catalog_rows is not None else supplied_pdf_question_catalog_rows()
    if not rows:
        raise ValueError("Feature availability contract requires at least one catalog row.")

    normalized_mode = _coerce_analysis_mode(analysis_mode)
    if normalized_mode is not AnalysisMode.PRE_RACE:
        raise ValueError("Feature availability contract only supports pre_race analysis mode.")

    _validate_catalog_rows_for_contract(rows)
    question_scope = tuple(row.question_id for row in rows)
    source_boundary = _aggregate_source_boundary(rows)
    build_id = build_timestamp_or_id or datetime.now(UTC).replace(microsecond=0).isoformat()

    feature_groups = tuple(
        _build_base_feature_group(definition, rows, source_boundary, question_scope, build_id, normalized_mode)
        for definition in BASE_FEATURE_GROUP_DEFINITIONS
    ) + tuple(
        _build_forbidden_fact_group(fact_group, source_boundary, question_scope, build_id)
        for fact_group in POST_RACE_FORBIDDEN_FEATURE_GROUPS
    )

    source_tables = _unique_sorted(
        table
        for group in feature_groups
        for table in group.source_tables_or_artifacts_inspected
    )

    return FeatureAvailabilityContract(
        analysis_mode=normalized_mode,
        question_scope=question_scope,
        source_boundary=source_boundary,
        build_timestamp_or_id=build_id,
        feature_groups=feature_groups,
        source_tables_or_artifacts_inspected=source_tables,
    )


def feature_availability_contract_to_records(
    contract: FeatureAvailabilityContract,
) -> tuple[dict[str, object], ...]:
    """Serialize a feature availability contract into deterministic row-like records."""
    return tuple(
        {
            "group_key": group.group_key,
            "display_label": group.display_label,
            "availability_status": _coerce_availability_status(group.availability_status).value,
            "pre_race_usable": group.pre_race_usable,
            "leakage_status": group.leakage_status,
            "source_boundary": _source_boundary_record(group.source_boundary),
            "source_tables_or_artifacts_inspected": group.source_tables_or_artifacts_inspected,
            "current_evidence_summary": group.current_evidence_summary,
            "question_scope": group.question_scope,
            "build_timestamp_or_id": group.build_timestamp_or_id,
            "reason": group.reason,
            "forbidden_fact_group": group.forbidden_fact_group,
            "analysis_mode": _coerce_analysis_mode(contract.analysis_mode).value,
        }
        for group in contract.feature_groups
    )


def validate_feature_group_availability(
    group: FeatureGroupAvailability,
) -> list[FeatureAvailabilityValidationError]:
    """Return explicit validation failures for one feature availability group."""
    if not isinstance(group, FeatureGroupAvailability):
        return [
            FeatureAvailabilityValidationError(
                field_name="feature_group",
                message="Feature availability groups must be FeatureGroupAvailability values.",
                error_code="invalid_feature_group_availability",
            )
        ]

    errors: list[FeatureAvailabilityValidationError] = []

    try:
        _coerce_availability_status(group.availability_status)
    except ValueError:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="availability_status",
                message=f"Unsupported feature availability status: {group.availability_status}.",
                error_code="unsupported_feature_availability_status",
            )
        )

    if not _has_text(group.group_key):
        errors.append(_missing_text_error("group_key"))
    if not _has_text(group.display_label):
        errors.append(_missing_text_error("display_label"))
    if not _has_text(group.leakage_status):
        errors.append(_missing_text_error("leakage_status"))
    if not _has_text(group.current_evidence_summary):
        errors.append(_missing_text_error("current_evidence_summary"))
    if not _has_text(group.build_timestamp_or_id):
        errors.append(_missing_text_error("build_timestamp_or_id"))
    if not _has_text(group.reason):
        errors.append(_missing_text_error("reason"))
    if not isinstance(group.pre_race_usable, bool):
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="pre_race_usable",
                message="Feature availability groups must record a boolean pre-race usability flag.",
                error_code="invalid_pre_race_usable",
            )
        )
    if not isinstance(group.source_boundary, FeatureSnapshotBoundary):
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="source_boundary",
                message="Feature availability groups must record a FeatureSnapshotBoundary source boundary.",
                error_code="invalid_source_boundary",
            )
        )
    if not group.source_tables_or_artifacts_inspected:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="source_tables_or_artifacts_inspected",
                message="Feature availability groups must record inspected source tables or artifacts.",
                error_code="missing_source_tables_or_artifacts",
            )
        )
    if not group.question_scope:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="question_scope",
                message="Feature availability groups must record question scope.",
                error_code="missing_question_scope",
            )
        )

    if group.forbidden_fact_group is not None:
        normalized_forbidden_group = _normalize_key(group.forbidden_fact_group)
        if normalized_forbidden_group in POST_RACE_FORBIDDEN_FEATURE_GROUPS:
            if group.pre_race_usable:
                errors.append(
                    FeatureAvailabilityValidationError(
                        field_name="pre_race_usable",
                        message="Forbidden post-race fact groups must be unavailable for pre_race features.",
                        error_code="forbidden_fact_group_marked_pre_race_usable",
                    )
                )
            if group.leakage_status != "leakage_boundary_constraint":
                errors.append(
                    FeatureAvailabilityValidationError(
                        field_name="leakage_status",
                        message="Forbidden post-race fact groups must record leakage_boundary_constraint.",
                        error_code="missing_leakage_boundary_constraint",
                    )
                )

    return errors


def validate_feature_availability_contract(
    contract: FeatureAvailabilityContract,
) -> list[FeatureAvailabilityValidationError]:
    """Return validation failures for a feature availability contract."""
    if not isinstance(contract, FeatureAvailabilityContract):
        return [
            FeatureAvailabilityValidationError(
                field_name="contract",
                message="Feature availability contracts must be FeatureAvailabilityContract values.",
                error_code="invalid_feature_availability_contract",
            )
        ]

    errors: list[FeatureAvailabilityValidationError] = []
    try:
        _coerce_analysis_mode(contract.analysis_mode)
    except ValueError:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="analysis_mode",
                message=f"Unsupported analysis mode: {contract.analysis_mode}.",
                error_code="unsupported_analysis_mode",
            )
        )

    if not contract.question_scope:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="question_scope",
                message="Feature availability contracts must record question scope.",
                error_code="missing_question_scope",
            )
        )
    else:
        for question_id in contract.question_scope:
            if not _has_text(question_id):
                errors.append(
                    FeatureAvailabilityValidationError(
                        field_name="question_scope",
                        message="Feature availability contract question-scope entries must be non-empty strings.",
                        error_code="invalid_question_scope",
                    )
                )
                break
    if not _has_text(contract.build_timestamp_or_id):
        errors.append(_missing_text_error("build_timestamp_or_id"))
    if not isinstance(contract.source_boundary, FeatureSnapshotBoundary):
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="source_boundary",
                message="Feature availability contracts must record a FeatureSnapshotBoundary source boundary.",
                error_code="invalid_source_boundary",
            )
        )
    else:
        errors.extend(
            FeatureAvailabilityValidationError(
                field_name=error.field_name.replace("feature_snapshot_boundary", "source_boundary"),
                message=error.message,
                error_code=error.error_code,
            )
            for error in validate_feature_snapshot_boundary(contract.source_boundary)
        )
    if not contract.source_tables_or_artifacts_inspected:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="source_tables_or_artifacts_inspected",
                message="Feature availability contracts must record inspected source tables or artifacts.",
                error_code="missing_source_tables_or_artifacts",
            )
        )
    else:
        for source in contract.source_tables_or_artifacts_inspected:
            if not _has_text(source):
                errors.append(
                    FeatureAvailabilityValidationError(
                        field_name="source_tables_or_artifacts_inspected",
                        message="Source table or artifact entries must be non-empty strings.",
                        error_code="invalid_source_tables_or_artifacts",
                    )
                )
                break
    if not contract.feature_groups:
        errors.append(
            FeatureAvailabilityValidationError(
                field_name="feature_groups",
                message="Feature availability contracts must include feature groups.",
                error_code="missing_feature_groups",
            )
        )

    for group in contract.feature_groups:
        errors.extend(validate_feature_group_availability(group))

    return errors


def _build_base_feature_group(
    definition: dict[str, object],
    rows: tuple[QuestionCatalogRow, ...],
    source_boundary: FeatureSnapshotBoundary,
    question_scope: tuple[str, ...],
    build_id: str,
    analysis_mode: AnalysisMode,
) -> FeatureGroupAvailability:
    status = _coerce_availability_status(definition["availability_status"])  # type: ignore[arg-type]
    pre_race_usable = (
        analysis_mode is AnalysisMode.PRE_RACE
        and status in PRE_RACE_USABLE_AVAILABILITY_STATUSES
    )
    leakage_status = "leakage_safe"
    reason = str(definition["reason"])

    if status is FeatureAvailabilityStatus.REQUIRES_NEW_SOURCE:
        leakage_status = "source_blocked"

    if definition["group_key"] == "qualifying_form" and _has_pre_qualifying_boundary(rows):
        status = FeatureAvailabilityStatus.OUT_OF_SCOPE
        pre_race_usable = False
        leakage_status = "unavailable_before_snapshot_boundary"
        reason = (
            "Qualifying form is unavailable for pre-qualifying snapshots because qualifying facts have not "
            "occurred before that feature boundary."
        )

    return FeatureGroupAvailability(
        group_key=str(definition["group_key"]),
        display_label=str(definition["display_label"]),
        availability_status=status,
        pre_race_usable=pre_race_usable,
        leakage_status=leakage_status,
        source_boundary=source_boundary,
        source_tables_or_artifacts_inspected=tuple(definition["source_tables"]),  # type: ignore[arg-type]
        current_evidence_summary=str(definition["evidence"]),
        question_scope=question_scope,
        build_timestamp_or_id=build_id,
        reason=reason,
    )


def _build_forbidden_fact_group(
    fact_group: str,
    source_boundary: FeatureSnapshotBoundary,
    question_scope: tuple[str, ...],
    build_id: str,
) -> FeatureGroupAvailability:
    label = fact_group.replace("_", " ").title()
    return FeatureGroupAvailability(
        group_key=f"target_event_{fact_group}",
        display_label=f"Target-event {label}",
        availability_status=FeatureAvailabilityStatus.OUT_OF_SCOPE,
        pre_race_usable=False,
        leakage_status="leakage_boundary_constraint",
        source_boundary=source_boundary,
        source_tables_or_artifacts_inspected=FORBIDDEN_FACT_SOURCE_TABLES.get(fact_group, ("source not inspected",)),
        current_evidence_summary=(
            f"{label} may exist in local tables after the race, but those facts occur after the prediction boundary."
        ),
        question_scope=question_scope,
        build_timestamp_or_id=build_id,
        reason=(
            "leakage_boundary_constraint: target-event post-race facts cannot be used as pre_race prediction "
            f"features even when {fact_group} data exists locally after the race."
        ),
        forbidden_fact_group=fact_group,
    )


def _aggregate_source_boundary(rows: tuple[QuestionCatalogRow, ...]) -> FeatureSnapshotBoundary:
    first_boundary = rows[0].feature_snapshot_boundary
    if not isinstance(first_boundary, FeatureSnapshotBoundary):
        raise ValueError("Catalog rows must define FeatureSnapshotBoundary values.")

    boundaries = tuple(row.feature_snapshot_boundary for row in rows)
    if not all(isinstance(boundary, FeatureSnapshotBoundary) for boundary in boundaries):
        raise ValueError("Catalog rows must define FeatureSnapshotBoundary values.")

    session_boundaries = tuple(boundary.session_boundary for boundary in boundaries)
    if session_boundaries and all(boundary == session_boundaries[0] for boundary in session_boundaries):
        session_boundary = session_boundaries[0]
    else:
        raise ValueError("Feature availability aggregate contracts require homogeneous session boundaries.")

    allowed_scope = _unique_preserve_order(
        feature_group
        for boundary in boundaries
        for feature_group in boundary.allowed_pre_race_feature_scope
    )

    return FeatureSnapshotBoundary(
        question_id="supplied_pdf_question_scope",
        cutoff_timestamp=None,
        session_boundary=session_boundary,
        allowed_pre_race_feature_scope=allowed_scope,
        forbidden_post_race_fact_groups=POST_RACE_FORBIDDEN_FEATURE_GROUPS,
    )


def _source_boundary_record(boundary: FeatureSnapshotBoundary) -> dict[str, object]:
    session_boundary = boundary.session_boundary
    if isinstance(session_boundary, FeatureSnapshotSessionBoundary):
        session_boundary_value = session_boundary.value
    else:
        session_boundary_value = session_boundary

    return {
        "question_id": boundary.question_id,
        "cutoff_timestamp": boundary.cutoff_timestamp,
        "session_boundary": session_boundary_value,
        "allowed_pre_race_feature_scope": boundary.allowed_pre_race_feature_scope,
        "forbidden_post_race_fact_groups": boundary.forbidden_post_race_fact_groups,
    }


def _validate_catalog_rows_for_contract(rows: tuple[QuestionCatalogRow, ...]) -> None:
    for row in rows:
        errors = validate_feature_snapshot_boundary(
            row.feature_snapshot_boundary,
            expected_question_id=row.question_id,
        )
        if errors:
            error_codes = ", ".join(error.error_code for error in errors)
            raise ValueError(
                f"Catalog row {row.question_id} has an invalid feature snapshot boundary: {error_codes}."
            )


def _has_pre_qualifying_boundary(rows: tuple[QuestionCatalogRow, ...]) -> bool:
    for row in rows:
        boundary = row.feature_snapshot_boundary
        if not isinstance(boundary, FeatureSnapshotBoundary):
            continue
        session_boundary = boundary.session_boundary
        if session_boundary is not None and not isinstance(session_boundary, FeatureSnapshotSessionBoundary):
            session_boundary = FeatureSnapshotSessionBoundary(session_boundary)
        if session_boundary in QUALIFYING_UNAVAILABLE_SESSION_BOUNDARIES:
            return True
    return False


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _unique_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return tuple(ordered)


def _coerce_availability_status(status: FeatureAvailabilityStatus | str) -> FeatureAvailabilityStatus:
    if isinstance(status, FeatureAvailabilityStatus):
        return status
    return FeatureAvailabilityStatus(status)


def _coerce_analysis_mode(mode: AnalysisMode | str) -> AnalysisMode:
    if isinstance(mode, AnalysisMode):
        return mode
    return AnalysisMode(mode)


def _normalize_key(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _missing_text_error(field_name: str) -> FeatureAvailabilityValidationError:
    return FeatureAvailabilityValidationError(
        field_name=field_name,
        message="Feature availability groups must record non-empty text values.",
        error_code="missing_feature_availability_text",
    )
