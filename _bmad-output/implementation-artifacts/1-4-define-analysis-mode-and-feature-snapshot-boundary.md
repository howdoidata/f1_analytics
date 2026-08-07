---
baseline_commit: 20bb6f67959918322c5b65c8fb573bec068f9979
story_key: 1-4-define-analysis-mode-and-feature-snapshot-boundary
created: 2026-07-17 06:13 CDT
---

# Story 1.4: Define Analysis Mode And Feature Snapshot Boundary

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Antonio,
I want each question to declare pre-race and post-race mode boundaries,
so that prediction inputs and actual answers can share a target definition without leaking post-race facts into baseline predictions.

## Acceptance Criteria

1. Given a Question Catalog row exists, when analysis mode support is implemented, then the same Question ID can be evaluated in `pre_race` mode for Prediction Inputs and `post_race` mode for Actual Answer extraction, and switching modes is controlled by a flag, configuration value, or equivalent run setting rather than duplicating catalog rows.
2. Given a question is used for future prediction or baseline work, when its Feature Snapshot boundary is defined, then the boundary records the cutoff timestamp or session boundary for that Question ID, and post-race facts including results, fastest laps, pit stops, tyre changes, incidents, retirements, and race-control messages are forbidden as pre-race features.
3. Given prediction inputs and actual answers are separate concepts, when their contracts are implemented, then Prediction Inputs and Actual Answer Components are stored as separate tables/files or generated artifacts, and each artifact records mode, source boundary, and leakage status where applicable.
4. Given a pre-race baseline cannot be generated without leakage or unsupported assumptions, when the system validates the Feature Snapshot boundary, then the prediction input can be marked unavailable with a reason, and the target definition remains usable for post-race Actual Answer extraction.

## Tasks / Subtasks

- [x] Add analysis-mode and feature-snapshot boundary support to the catalog contract. (AC: 1, 2)
  - [x] Update `src/f1_analytics/analysis/question_catalog.py` or a small companion module imported by it with a controlled `AnalysisMode` enum containing exactly `pre_race` and `post_race`.
  - [x] Add a lightweight immutable `FeatureSnapshotBoundary` contract that records the Question ID or owning row context, a cutoff timestamp or session boundary, the allowed pre-race feature scope, and forbidden post-race fact groups.
  - [x] Preserve existing `QuestionCatalogRow` construction by using backwards-compatible defaults only where they do not hide missing Story 1.4 data; update all seed rows explicitly where this story requires explicit boundaries.
  - [x] Validate that each supplied PDF question supports both modes on the same `question_id`; do not create duplicated catalog rows for pre/post mode.
  - [x] Define the canonical forbidden pre-race fact groups at minimum as results, fastest laps, pit stops, tyre changes, incidents, retirements, and race-control messages.
- [x] Add the Prediction Input contract separately from Actual Answer Components. (AC: 3, 4)
  - [x] Create `src/f1_analytics/analysis/question_predictions.py` or an equivalently focused module for prediction-input records and validation.
  - [x] Define a `PredictionInput` dataclass or equivalent with fields for `question_id`, optional `component_key`, analysis mode, prediction value/display fields, method, source boundary or feature snapshot reference, build timestamp or build ID, leakage status, availability/status, and unavailable reason.
  - [x] Enforce that Prediction Inputs are `pre_race` artifacts; Actual Answer Components remain the `post_race` target path from `question_answers.py`.
  - [x] Allow unavailable prediction rows only when they preserve an explicit reason such as leakage risk, unsupported assumption, unavailable source, or unsupported answer type.
  - [x] Do not store prediction values in `ActualAnswerComponent`, and do not add prediction fields to actual-answer components.
- [x] Add validation helpers for mode, leakage, and boundary behavior. (AC: 1, 2, 3, 4)
  - [x] Return structured validation errors consistent with existing `CatalogValidationError` / `ActualAnswerValidationError` style instead of incidental exceptions for ordinary invalid rows.
  - [x] Reject unsupported mode values and empty mode sets.
  - [x] Reject feature snapshots that do not record either a cutoff timestamp or a session boundary.
  - [x] Reject `pre_race` Prediction Inputs whose source boundary includes forbidden post-race facts.
  - [x] Reject available Prediction Inputs without a value/display context, method, build timestamp/build ID, source boundary, and leakage-safe status.
  - [x] Reject unavailable Prediction Inputs without an unavailable reason.
- [x] Keep scope limited to contracts and validation. (AC: 1-4)
  - [x] Do not generate baseline predictions, compute actual answers, score predictions, inspect Williams participants, extract lap/results/tyre facts, write DuckDB target tables, or build reports/notebooks in this story.
  - [x] Do not add FastF1, pandas serialization, Pydantic, dbt, Airflow, a scheduler, or a hosted/dashboard layer.
  - [x] Do not modify Kaggle curated tables, Jolpica raw loaders, combined dataset precedence logic, existing notebooks, or `question_answers.py` behavior except for imports/tests strictly needed to prove separation.
- [x] Add focused tests. (AC: 1, 2, 3, 4)
  - [x] Extend `tests/test_question_catalog.py` for mode/boundary fields on supplied rows, same Question ID across modes, unsupported mode rejection, and missing boundary rejection.
  - [x] Add `tests/test_question_predictions.py` for valid available Prediction Input, valid unavailable-with-reason Prediction Input, post-race fact leakage rejection, unsupported mode rejection, and proof that Prediction Input validation does not require Actual Answer Components.
  - [x] Preserve existing `tests/test_question_catalog.py` and `tests/test_question_answers.py` coverage.
- [x] Verify and log the result. (AC: 1-4)
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_catalog`.
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_answers`.
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_predictions`.
  - [x] Run `PYTHONPATH=src python3 -m unittest discover -s tests`.
  - [x] Run `python3 -m compileall src/f1_analytics`.
  - [x] Run `git diff --check` scoped to touched source, test, story, and run-log paths.
  - [x] Append command and validation evidence to `docs/run_log.md`.

### Review Findings

- [x] [Review][Patch] Add explicit post-race mode and source-boundary metadata to Actual Answer Components, per review decision. [`src/f1_analytics/analysis/question_answers.py`:94]
- [x] [Review][Patch] Replace free-text Feature Snapshot session boundaries with a controlled pre-race vocabulary, per review decision. [`src/f1_analytics/analysis/question_catalog.py`:78]
- [x] [Review][Patch] Invalid Prediction Input `source_boundary` values can raise `AttributeError` instead of returning only structured validation errors. [`src/f1_analytics/analysis/question_predictions.py`:123]
- [x] [Review][Patch] Catalog-linked Prediction Inputs do not validate `component_key` against single-answer or multi-part catalog targets. [`src/f1_analytics/analysis/question_predictions.py`:200]
- [x] [Review][Patch] Empty `allowed_pre_race_feature_scope` passes Feature Snapshot boundary validation even though the boundary contract must record allowed pre-race scope. [`src/f1_analytics/analysis/question_catalog.py`:418]
- [x] [Review][Patch] Catalog validation permits rows with only one analysis mode even though Story 1.4 requires the same Question ID to support both `pre_race` and `post_race`. [`src/f1_analytics/analysis/question_catalog.py`:630]
- [x] [Review][Patch] Prediction Input status consistency is under-validated: available rows can carry `unavailable_reason`, and unavailable rows can still carry prediction/build fields. [`src/f1_analytics/analysis/question_predictions.py`:98]
- [x] [Review][Patch] Catalog validation lacks the structured type guard used by the answer and prediction validators. [`src/f1_analytics/analysis/question_catalog.py`:280]

## Dev Notes

### Story Scope

This story defines the mode and leakage-boundary contract only. It is the bridge between the Question Catalog/Actual Answer Component contracts from Stories 1.1-1.3 and later Epic 3 baseline/scoring work.

The expected implementation shape is small and standard-library only:

- Update target: `src/f1_analytics/analysis/question_catalog.py`
- Likely new file: `src/f1_analytics/analysis/question_predictions.py`
- Likely new tests: `tests/test_question_predictions.py`
- Existing tests to preserve: `tests/test_question_catalog.py`, `tests/test_question_answers.py`

`src/f1_analytics/analysis/__init__.py` currently contains only a package docstring. Do not add heavy imports or runtime work there.

### Current File State To Preserve

`src/f1_analytics/analysis/question_catalog.py` currently defines:

- `AnswerType`
- `ExtractionSupportStatus`
- `QuestionTargetComponent`
- `QuestionCatalogRow`
- `AnswerTypeMetadata`
- `CatalogValidationError`
- metadata lookup helpers
- `validate_question_catalog_row`
- `supplied_pdf_question_catalog_rows`

Story 1.4 may add mode and boundary fields to `QuestionCatalogRow`, but it must preserve the five supplied rows and existing validation semantics:

- Q01 and Q03 are team-scoped rows using `target_subject_scope` instead of pretending the known-answer driver was the asked scope.
- Q05 is one `multi_part` row with two deterministic target definitions: `starting_tyre_compound` and `first_tyre_change_lap`.
- `known_answer_example` remains validation context only.
- `extraction_support_status` remains schema-level extraction support, not actual-answer or prediction status.

`src/f1_analytics/analysis/question_answers.py` currently defines the Actual Answer Component contract and validation helpers:

- `ActualAnswerStatus`
- `TyreCompound`
- `ActualAnswerComponent`
- `ActualAnswerValidationError`
- `validate_actual_answer_component`
- `validate_actual_answer_components`

Do not merge prediction-input status into `ActualAnswerStatus`. Actual Answer Components are target/label records and Prediction Inputs are forecast/baseline records.

### Recommended Contract Shape

Exact names can vary, but the behavior should be explicit and reusable.

Catalog-side mode and boundary primitives:

- `AnalysisMode`: `PRE_RACE = "pre_race"`, `POST_RACE = "post_race"`
- `FeatureSnapshotBoundary`: immutable record for cutoff/session boundary and allowed/forbidden fact groups
- `POST_RACE_FORBIDDEN_FEATURE_GROUPS`: results, fastest laps, pit stops, tyre changes, incidents, retirements, race-control messages
- validation helper such as `validate_feature_snapshot_boundary(boundary) -> list[CatalogValidationError]`

Prediction-side primitives:

- `PredictionInputStatus`: at least available and unavailable-style states; avoid using actual-answer statuses for prediction availability.
- `LeakageStatus`: at least leakage-safe, leakage-risk, and not-checked/unknown-style states.
- `PredictionInput`: immutable record with `question_id`, optional `component_key`, `analysis_mode`, prediction value/display fields, method, feature/source boundary, build timestamp or build ID, leakage status, prediction status, and unavailable reason.
- validation helper such as `validate_prediction_input(prediction, catalog_row=None) -> list[PredictionInputValidationError]`.

Pre-race baseline generation itself is not part of this story. This story only creates the row shape and validation so later stories can safely store either an available Prediction Input or an unavailable-with-reason row.

### Architecture Compliance

- Reusable contracts belong under `src/f1_analytics/`; scripts and notebooks must not become the source of truth for mode or leakage behavior. [Source: `_bmad-output/project-context.md`; `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-1---Layer-Ownership-For-Reproducible-Analytics-ADOPTED`]
- Question answers are statused targets, not free text. This story must keep target components separate from prediction inputs. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-3---Question-Answers-Are-Statused-Targets-Not-Free-Text-ADOPTED`]
- PDF Known Answer Examples are validation examples and must not become Prediction Inputs or Actual Answers by default. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-4---PDF-Known-Answers-Are-Validation-Examples-ADOPTED`]
- Prediction inputs and actual answers are separate tables/files or generated artifacts. Each Question ID defines a feature snapshot boundary before scoring depends on it. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-8---Leakage-Boundary-Precedes-Prediction-Scoring-ADOPTED`]
- Scoring and baseline generation are later work. Do not make this story compute model outputs, extract source-backed actuals, or score anything. [Source: `_bmad-output/planning-artifacts/epics.md#Epic-3-Leakage-Safe-Baselines-And-Scoring`]

### Previous Story Intelligence

Story 1.3 (`_bmad-output/implementation-artifacts/1-3-define-actual-answer-component-contract.md`) is the immediate predecessor for this F1 questions/backtest stream. It established:

- Use standard-library `Enum`, frozen `dataclass`, tuples, and structured validation errors.
- Reuse `AnswerType`; do not define overlapping answer-type vocabularies.
- Keep Actual Answer Components separate from catalog rows, prediction inputs, and scores.
- No DuckDB persistence, generated output files, scripts, FastF1, pandas serialization, Pydantic, dbt, Airflow, or notebooks were added for contract work.
- Focused tests use standard-library `unittest`; current discovery includes catalog and answer-contract tests.

Story 1.2 established the five supplied PDF catalog rows and the British GP multi-part catalog target definitions. Story 1.4 must build on those rows; do not reseed different IDs or split the British GP question.

Older implementation artifacts with Story IDs 1.1, 1.2, and 1.3 from the cleanup/root-protocol stream still exist. Do not treat `_bmad-output/implementation-artifacts/1-3-retire-required-pre-read-docs-and-repoint-project-pointers.md` as this story and do not overwrite it.

### Git Intelligence

Recent commits at story creation:

- `20bb6f6 docs: record story 4.3 platform exchange`
- `59294ce feat: claim daily pipeline atomic staging`
- `3a84543 Initial baseline commit`

The working tree is already dirty and includes uncommitted current Story 1.1-1.3 code/test/story artifacts plus older cleanup deletions and planning artifacts. Do not revert, normalize, or attribute unrelated changes.

### Latest Technical Information

- Python 3.13 standard-library `dataclasses` remain appropriate for immutable contract records; the official docs describe `@dataclass` as generating methods from type-annotated fields and document `frozen=True` behavior. [Source: https://docs.python.org/3.13/library/dataclasses.html]
- Python 3.13 `Enum` remains appropriate for controlled mode/status vocabularies; the official docs define enumerations as symbolic names bound to unique values and iterable in definition order. [Source: https://docs.python.org/3.13/library/enum.html]
- DuckDB 1.5.4 is the current stable Python client documented by DuckDB, and the official docs recommend connection objects for package code instead of relying on the shared module/global connection. Story 1.4 should not need DuckDB writes; if a later story persists Prediction Inputs, it should use existing project DuckDB helpers. [Source: https://duckdb.org/docs/stable/clients/python/overview; `src/f1_analytics/database/duckdb_io.py`]
- No package-version-sensitive external API is needed for this story. Do not add FastF1; it remains a later source-coverage adapter candidate after local install/runtime verification.

### Testing Requirements

Use the existing lightweight `unittest` pattern. Required implementation verification:

- `PYTHONPATH=src python3 -m unittest tests.test_question_catalog`
- `PYTHONPATH=src python3 -m unittest tests.test_question_answers`
- `PYTHONPATH=src python3 -m unittest tests.test_question_predictions`
- `PYTHONPATH=src python3 -m unittest discover -s tests`
- `python3 -m compileall src/f1_analytics`
- `git diff --check` for touched files

No broad test framework adoption is required.

### References

- `_bmad-output/planning-artifacts/epics.md#Story-1.4-Define-Analysis-Mode-And-Feature-Snapshot-Boundary`
- `_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md#4.1-Question-Catalog-And-Answer-Schema`
- `_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md#4.6-Feature-Snapshot-Contract-For-Future-Models`
- `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/decisions/question-backtest-mode-and-scoring-decision-record.md`
- `_bmad-output/implementation-artifacts/1-1-define-question-catalog-and-answer-type-schema.md`
- `_bmad-output/implementation-artifacts/1-2-seed-supplied-pdf-questions-into-the-catalog.md`
- `_bmad-output/implementation-artifacts/1-3-define-actual-answer-component-contract.md`
- `src/f1_analytics/analysis/question_catalog.py`
- `src/f1_analytics/analysis/question_answers.py`
- `tests/test_question_catalog.py`
- `tests/test_question_answers.py`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Red checks:
  - `PYTHONPATH=src python3 -m unittest tests.test_question_catalog` failed before implementation with missing catalog mode/boundary imports.
  - `PYTHONPATH=src python3 -m unittest tests.test_question_predictions` failed before implementation with missing catalog mode support and missing prediction module.
- Green checks:
  - `PYTHONPATH=src python3 -m unittest tests.test_question_catalog` passed: 31 tests.
  - `PYTHONPATH=src python3 -m unittest tests.test_question_answers` passed: 12 tests.
  - `PYTHONPATH=src python3 -m unittest tests.test_question_predictions` passed: 8 tests.
  - `PYTHONPATH=src python3 -m unittest discover -s tests` passed: 51 tests.
  - `python3 -m compileall src/f1_analytics` passed.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Added `AnalysisMode` with exactly `pre_race` and `post_race`, a canonical forbidden post-race fact-group tuple, and immutable `FeatureSnapshotBoundary` records in the catalog contract.
- Updated all five supplied PDF catalog rows with explicit pre/post mode support and race-start feature snapshot boundaries while preserving one row per `question_id`.
- Added a separate Prediction Input contract with availability/leakage statuses, structured prediction validation errors, available/unavailable validation paths, and source-boundary leakage checks.
- Preserved separation from Actual Answer Components: `question_answers.py` behavior and fields were not modified.
- Kept implementation scoped to contracts, validation, and tests only; no baseline generation, scoring, data extraction, DuckDB writes, reports, notebooks, or new dependencies were added.

### File List

- `_bmad-output/implementation-artifacts/1-4-define-analysis-mode-and-feature-snapshot-boundary.md`
- `docs/run_log.md`
- `src/f1_analytics/analysis/question_catalog.py`
- `src/f1_analytics/analysis/question_predictions.py`
- `tests/test_question_catalog.py`
- `tests/test_question_predictions.py`

## Change Log

- 2026-07-17: Story context created and set to `ready-for-dev`.
- 2026-07-17: Implemented analysis mode, feature snapshot boundary, and prediction input contracts; story set to `review`.
- 2026-07-17: Resolved code-review findings for mode/boundary metadata, controlled boundaries, and validation hardening; story set to `done`.
