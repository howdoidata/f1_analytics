---
baseline_commit: 20bb6f67959918322c5b65c8fb573bec068f9979
story_key: 2-2-extract-results-based-williams-finishing-answers
created: 2026-07-17
---

# Story 2.2: Extract Results-Based Williams Finishing Answers

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Antonio,
I want source-backed extraction for Williams finishing-position questions,
so that the Miami and Canadian examples produce computed or explicitly statused Actual Answer Components.

## Acceptance Criteria

1. Given Williams participants have been resolved for a target race, when the highest Williams finishing-position extractor runs, then it returns the best Williams classified finishing position and attached driver for the Canadian GP example when source data supports it, and it records source table, source row grain, source precedence, extraction method, and validation status.
2. Given Williams participants have been resolved for a target race, when the combined Williams finishing-position extractor runs, then it returns the sum of both Williams drivers' classified numeric finishing positions for the Miami GP example when both positions are scoreable, and it records each contributing driver position plus the combined display answer.
3. Given a driver has DNS, DNF, DSQ, no-classification, missing position, or nonnumeric classification data, when either results-based extractor runs, then it represents the source classification/status before any numeric scoring, and it returns an explicit validation status rather than silently summing or ranking incomplete data.
4. Given a source-backed result differs from the PDF Known Answer Example, when the Actual Answer Component is generated, then the component status is `discrepant_needs_review`, and both the PDF known value and extracted source-backed value are preserved with citations.

## Tasks / Subtasks

- [x] Add reusable results-answer extraction under `src/f1_analytics/analysis/`. (AC: 1, 2, 3, 4)
  - [x] Prefer a focused companion module such as `src/f1_analytics/analysis/question_result_answers.py`; do not bury extraction in notebooks, `scripts/*.py`, or the already-large `question_answers.py` contract module.
  - [x] Reuse `QuestionCatalogRow`, `AnswerType`, and `supplied_pdf_question_catalog_rows()` from `question_catalog.py`; do not create a second question catalog or duplicate seed rows.
  - [x] Reuse `ActualAnswerComponent`, `ActualAnswerStatus`, and validation helpers from `question_answers.py`; generated components must validate against their catalog rows.
  - [x] Reuse `QuestionParticipantResolution` and `resolve_williams_participants_for_question()` from `question_participants.py`; do not reimplement Williams alias resolution or participant discovery.
- [x] Extract highest Williams finishing position for the Canadian GP question. (AC: 1, 3, 4)
  - [x] Select only resolved Williams participant rows from `combined_results` for the catalog season/grand prix/constructor/driver set.
  - [x] Treat lower numeric finishing position as better, but only after preserving each driver's source `position` and `status`.
  - [x] Return Carlos Sainz P9 for current local Canadian GP data when source rows remain as inspected during story creation.
  - [x] Produce one `ActualAnswerComponent` with `answer_type=AnswerType.FINISHING_POSITION`, `component_key="actual_answer"`, `component_order=1`, `numeric_value=9`, `unit="position"`, `precision=0`, and a display value that includes the attached driver.
- [x] Extract combined Williams finishing position for the Miami GP question. (AC: 2, 3, 4)
  - [x] Require exactly the expected Williams participant positions to be classified numeric positions before summing.
  - [x] Return combined position `19` for current local Miami GP data when Carlos Sainz is P9 and Alexander Albon is P10.
  - [x] Preserve contributor detail in the extraction result and display value, e.g. `Carlos Sainz P9 + Alexander Albon P10 = 19`.
  - [x] Produce one `ActualAnswerComponent` with `answer_type=AnswerType.COMBINED_FINISHING_POSITION`, `component_key="actual_answer"`, `component_order=1`, `numeric_value=19`, `unit="position_sum"`, and `precision=0`.
- [x] Handle abnormal or incomplete classifications explicitly. (AC: 3)
  - [x] Define a small source-position contract that preserves `driver_id`, `driver_name`, raw `position`, normalized numeric position if available, raw `status`, and scoreability reason.
  - [x] Treat blank, null, NaN, zero, negative, or nonnumeric positions as non-scoreable unless a later approved scoring rule says otherwise.
  - [x] Treat DNS, DNF, DSQ, retired, not-classified, excluded, withdrawn, failed-to-qualify, and similar status/classification values as explicit non-computed outcomes before numeric scoring.
  - [x] For combined-position extraction, return `partial`, `source_blocked`, or `discrepant_needs_review` with source details when either Williams driver lacks a scoreable numeric classified position; do not sum incomplete data.
  - [x] For highest-position extraction, preserve non-scoreable drivers in notes/details, but the answer may still be `computed` if at least one resolved Williams driver has a scoreable classified position and no source integrity issue remains.
- [x] Preserve PDF validation behavior and discrepancy handling. (AC: 4)
  - [x] Compare source-backed values against the catalog `known_answer_example` for Q02 and Q03 without treating the PDF as authoritative source truth.
  - [x] If Miami is not `19` or Canadian is not Carlos Sainz P9, return `ActualAnswerStatus.DISCREPANT_NEEDS_REVIEW`.
  - [x] Discrepant components must set `known_answer_example`, `source_value`, and `discrepancy_notes` so `validate_actual_answer_component()` passes.
  - [x] Matching source-backed answers may use `ActualAnswerStatus.COMPUTED`.
- [x] Repair or extend real DuckDB participant/source lookup where needed. (AC: 1, 2, 3)
  - [x] Local inspection showed `kaggle_jolpica_coverage` has `season`, `round`, row-count columns, and `results_coverage_status`; it does not have `race_name`.
  - [x] If using `resolve_williams_participants_from_duckdb()`, adjust coverage lookup to derive the target round from `combined_results` or another existing race table, then query coverage by `season` and `round`.
  - [x] Add regression coverage so real DuckDB lookup does not depend on a nonexistent `kaggle_jolpica_coverage.race_name` column.
- [x] Add focused standard-library tests. (AC: 1, 2, 3, 4)
  - [x] Add `tests/test_question_result_answers.py` using `unittest`.
  - [x] Test current Miami seeded row returns a valid computed combined-position component and contributor details from stable in-memory `combined_results`-shaped fixtures.
  - [x] Test current Canadian seeded row returns a valid computed highest-position component and attached driver from stable fixtures.
  - [x] Test participant resolution failures stop extraction with the existing explicit status/reason instead of guessing.
  - [x] Test nonnumeric/missing positions, DNS/DNF/DSQ/retired/not-classified statuses, one missing participant, duplicate participant rows, and mixed/missing source values.
  - [x] Test discrepancy handling by changing fixture positions away from the PDF known examples and asserting `discrepant_needs_review` with preserved known/source values.
  - [x] Preserve existing catalog, answer, prediction, and participant tests.
- [x] Verify and log the result. (AC: 1-4)
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_result_answers`.
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_participants`.
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_catalog`.
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_answers`.
  - [x] Run `PYTHONPATH=src python3 -m unittest tests.test_question_predictions`.
  - [x] Run `PYTHONPATH=src python3 -m unittest discover -s tests`.
  - [x] Run `python3 -m compileall src/f1_analytics`.
  - [x] Run `git diff --check` scoped to touched source, tests, story, and `docs/run_log.md`; for untracked new files, also use `git diff --no-index --check -- /dev/null <new-file>`.
  - [x] Append command and validation evidence to `docs/run_log.md`.

### Review Findings

- [x] [Review][Patch] Highest extractor abnormal-classification coverage is missing [tests/test_question_result_answers.py:116]
- [x] [Review][Patch] DNF reason status vocabulary is under-tested and may be under-guarded [tests/test_question_result_answers.py:206]
- [x] [Review][Patch] Result tests do not prove extraction ignores contaminating non-target rows [tests/test_question_result_answers.py:91]
- [x] [Review][Patch] Required provenance/citation fields are under-asserted in result tests [tests/test_question_result_answers.py:99]
- [x] [Review][Patch] Dev Agent Record contains copied non-story-specific completion text [_bmad-output/implementation-artifacts/2-2-extract-results-based-williams-finishing-answers.md:209]

## Dev Notes

### Story Scope

This story computes or explicitly statuses only results-based Williams finishing-position actual answers for the two supplied results questions:

- Q02 `2026_pdf_q02_miami_combined_williams_finish`
- Q03 `2026_pdf_q03_canadian_highest_williams_finish`

Do not compute lap-time, lap-number, tyre compound, pit/change lap, prediction inputs, scoring rows, reports, dashboards, notebooks, FastF1 source coverage, or a persisted Backtest Target Store in this story. A small reusable extraction module plus tests is sufficient unless implementation reveals a direct need for a thin wrapper.

### Current File State To Preserve

- `src/f1_analytics/analysis/question_catalog.py` defines the five supplied PDF catalog rows and validates answer types, analysis modes, and feature snapshot boundaries. Q02 is a `COMBINED_FINISHING_POSITION` row for Miami; Q03 is a `FINISHING_POSITION` row for Canada with Williams team scope and no single `driver_scope`.
- `src/f1_analytics/analysis/question_answers.py` defines the `ActualAnswerComponent` contract. Non-pending components must record `source_table_or_file`, `source_field_or_method`, `extraction_timestamp_or_build_id`, `analysis_mode=post_race`, and a `source_boundary`.
- `src/f1_analytics/analysis/question_participants.py` resolves Williams aliases and participants from `combined_results`-shaped rows. Extend or consume it; do not fork alias/participant logic.
- `src/f1_analytics/data_sources/combined_dataset.py` defines `COMBINED_RESULT_COLUMNS`: `season`, `round`, `race_name`, `date`, `driver_id`, `driver_name`, `constructor_id`, `constructor`, `grid`, `position`, `points`, `laps`, `status`, `source`. Do not alter the combined dataset builder unless a bug fix is directly required and covered by tests.
- `src/f1_analytics/database/duckdb_io.py` provides `connect_duckdb`; use connection objects for local DB reads instead of module-global DuckDB calls.
- `tests/test_question_participants.py` already has stable in-memory fixture patterns for `combined_results` and coverage rows. Reuse those patterns for results-answer fixtures.

### Local Source Evidence From Story Creation

A read-only inspection of `data/processed/f1_analytics.duckdb` on 2026-07-17 found these current rows:

| Race | Driver | Position | Status | Source |
| --- | --- | ---: | --- | --- |
| Miami Grand Prix | Alexander Albon | 10 | Finished | jolpica |
| Miami Grand Prix | Carlos Sainz | 9 | Finished | jolpica |
| Canadian Grand Prix | Alexander Albon | 21 | Retired | jolpica |
| Canadian Grand Prix | Carlos Sainz | 9 | Lapped | jolpica |

The same inspection found `kaggle_jolpica_coverage` rows for 2026 rounds 4 and 5 with `results_coverage_status='jolpica_only'`, `kaggle_result_rows=0`, and `jolpica_result_rows=22`. The coverage table is keyed by `season` and `round`; it does not expose `race_name`.

Use these rows as implementation context, not hardcoded source truth. Unit tests should use stable fixtures. Optional integration smoke checks may read the local DuckDB file if present, but tests must not depend on mutable `data/` contents.

### Architecture Compliance

- Reusable ingestion, extraction, source-coverage, target-building, and scoring logic belongs under `src/f1_analytics/`; scripts remain thin orchestration wrappers and notebooks/reports only render already-computed facts. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-1---Layer-Ownership-For-Reproducible-Analytics-ADOPTED`]
- Results extraction must preserve the Kaggle/Jolpica precedence rule: Kaggle wins for season/rounds where Kaggle has result rows; Jolpica fills only Kaggle-empty rounds; row-count divergence must be surfaced, not silently resolved. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-2---Source-Precedence-And-Deviation-Surfacing-ADOPTED`; `_bmad-output/planning-artifacts/decisions/dataset-precedence-decision-record.md`]
- Every generated answer must be a statused Actual Answer Component with answer type, value, unit/precision where applicable, source artifact/table/method, build id or extraction timestamp, and one of the controlled statuses. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-3---Question-Answers-Are-Statused-Targets-Not-Free-Text-ADOPTED`]
- PDF Known Answer Examples are validation inputs only. If source extraction disagrees, preserve both values and mark the component `discrepant_needs_review`; do not auto-resolve to either source. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-4---PDF-Known-Answers-Are-Validation-Examples-ADOPTED`]
- Post-race result facts are valid actual-answer sources but forbidden as pre-race prediction features. This story must not leak results into `PredictionInput` rows. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-8---Leakage-Boundary-Precedes-Prediction-Scoring-ADOPTED`]
- Results scoring must inspect source classification/status fields before numeric comparison; combined finishing positions are unscoreable when a required numeric classified position is absent unless a later user-approved scoring rule handles that class. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-9---Scoring-Uses-Source-Grade-Facts-ADOPTED`; `_bmad-output/planning-artifacts/decisions/question-backtest-mode-and-scoring-decision-record.md`]

### Previous Story Intelligence

Story 2.1, `_bmad-output/implementation-artifacts/2-1-resolve-williams-participants-and-team-aliases.md`, is `done` and established the dependency this story should reuse:

- `question_participants.py` owns exact Williams alias resolution for `Williams`, `Williams F1 Team`, and `Atlassian Williams F1 Team`.
- Participant resolution returns immutable records with original team scope, canonical constructor identity, resolved participant IDs/names, `source_table_or_file`, `source_row_grain`, `source_precedence`, `validation_status`, and `validation_reason`.
- It deliberately does not compute finishing positions. Story 2.2 owns finishing-answer extraction.
- It uses standard-library `unittest`, frozen dataclasses, enums/status values from `question_answers.py`, and in-memory pandas DataFrame fixtures shaped like source tables.
- Code-review patches tightened the resolver against malformed driver identities, conflicting rounds, missing/mixed source values, constructor-name disagreement, and coverage query failures. Preserve that strictness.

Stories 1.1-1.4 established the surrounding contracts:

- Do not edit seeded catalog rows just to make extraction easier.
- Q03 is team-scoped and should attach the winning Williams driver during extraction, not by converting the catalog row to a single-driver question.
- Actual Answer Components must preserve provenance and discrepancy context.
- Prediction inputs and actual answers remain separate.

Older implementation artifacts with overlapping IDs from the cleanup/root-protocol stream still exist. Do not treat them as predecessors for this capability and do not overwrite them.

### Git Intelligence

Recent commits at story creation:

- `20bb6f6 docs: record story 4.3 platform exchange`
- `59294ce feat: claim daily pipeline atomic staging`
- `3a84543 Initial baseline commit`

The working tree was already dirty at story creation with uncommitted planning artifacts, cleanup deletions, question/backtest source and test files, notebook changes, and `docs/run_log.md` edits. Do not revert, normalize, or take ownership of unrelated changes.

### Latest Technical Information

- Python 3.13 `dataclasses` remain appropriate for immutable result contracts; official docs describe `@dataclass` as generating methods from type-annotated fields. [Source: https://docs.python.org/3.13/library/dataclasses.html]
- Python 3.13 `Enum` remains appropriate for controlled statuses and answer types; official docs define enumerations as symbolic names bound to unique values and iterable in definition order. [Source: https://docs.python.org/3.13/library/enum.html]
- DuckDB's current Python docs identify DuckDB Python client 1.5.4 as latest stable and recommend connection objects for package code instead of the module-global connection. This matches `connect_duckdb`. [Source: https://duckdb.org/docs/current/clients/python/overview; https://duckdb.org/docs/stable/clients/python/overview]
- pandas `to_numeric` remains the standard API for coercing source-like values when needed; default behavior raises on invalid parsing unless `errors='coerce'` is chosen intentionally. Keep fixture and extraction coercion explicit. [Source: https://pandas.pydata.org/docs/reference/api/pandas.to_numeric.html]

### Testing Requirements

Use existing lightweight `unittest` patterns. Required implementation verification:

- `PYTHONPATH=src python3 -m unittest tests.test_question_result_answers`
- `PYTHONPATH=src python3 -m unittest tests.test_question_participants`
- `PYTHONPATH=src python3 -m unittest tests.test_question_catalog`
- `PYTHONPATH=src python3 -m unittest tests.test_question_answers`
- `PYTHONPATH=src python3 -m unittest tests.test_question_predictions`
- `PYTHONPATH=src python3 -m unittest discover -s tests`
- `python3 -m compileall src/f1_analytics`
- `git diff --check` scoped to touched files plus `git diff --no-index --check -- /dev/null <new-file>` for untracked new files

No pytest, Pydantic, FastF1, dbt, Airflow, dashboard, or persistence-layer adoption is required for this story.

### References

- `_bmad-output/planning-artifacts/epics.md#Story-2.2-Extract-Results-Based-Williams-Finishing-Answers`
- `_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md#4.2-Results-Based-Actual-Answer-Extraction`
- `_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/addendum.md#Source-Extraction-Notes`
- `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/decisions/dataset-precedence-decision-record.md`
- `_bmad-output/planning-artifacts/decisions/question-backtest-mode-and-scoring-decision-record.md`
- `_bmad-output/implementation-artifacts/2-1-resolve-williams-participants-and-team-aliases.md`
- `src/f1_analytics/analysis/question_catalog.py`
- `src/f1_analytics/analysis/question_answers.py`
- `src/f1_analytics/analysis/question_participants.py`
- `src/f1_analytics/data_sources/combined_dataset.py`
- `src/f1_analytics/database/duckdb_io.py`
- `tests/test_question_catalog.py`
- `tests/test_question_answers.py`
- `tests/test_question_participants.py`
- `tests/test_question_predictions.py`

### Open Questions

None blocking. Exact classification vocabulary beyond the locally observed statuses should be implemented conservatively from source rows and tests; if a new status class affects scoreability policy, record the rule in code and tests rather than relying on chat history.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- Red phase: `PYTHONPATH=src python3 -m unittest tests.test_question_result_answers` failed with missing `question_result_answers` module.
- Red phase: `PYTHONPATH=src python3 -m unittest tests.test_question_participants` exposed the DuckDB coverage lookup dependency on nonexistent `kaggle_jolpica_coverage.race_name`.
- Green/refactor validation: focused result, participant, catalog, answer, prediction tests; full `unittest discover`; `python3 -m compileall src/f1_analytics`; scoped whitespace checks.

### Completion Notes List

- Sprint status file was not present at configured path `_bmad-output/implementation-artifacts/sprint-status.yaml`; story was created directly from the requested Story 2.2 in `epics.md`.
- Implemented `question_result_answers.py` as a focused results-answer extractor using existing catalog, participant, and Actual Answer Component contracts.
- Added source-position preservation before scoring, including raw position, raw status, normalized numeric position, and scoreability reason.
- Added Miami combined-position and Canadian highest-position extraction with computed/discrepant/partial/source-blocked statuses and PDF known-answer discrepancy preservation.
- Repaired DuckDB coverage lookup to query `kaggle_jolpica_coverage` by `season` and derived `round`, not `race_name`.
- Added focused `unittest` coverage for computed examples, participant-resolution failures, non-scoreable classifications, duplicate/missing/mixed source cases, discrepancy handling, and coverage lookup regression.
- Resolved code-review findings by adding highest-extractor non-scoreable coverage, DNF reason status guards, contaminating-row fixture coverage, direct provenance assertions, and story-specific completion notes.

### File List

- `_bmad-output/implementation-artifacts/2-2-extract-results-based-williams-finishing-answers.md`
- `docs/run_log.md`
- `src/f1_analytics/analysis/question_participants.py`
- `src/f1_analytics/analysis/question_result_answers.py`
- `tests/test_question_participants.py`
- `tests/test_question_result_answers.py`

## Change Log

- 2026-07-17: Story context created and set to `ready-for-dev`.
- 2026-07-17: Implemented source-backed Williams finishing-position extraction, tests, DuckDB coverage lookup repair, and validation logging; story set to `review`.
- 2026-07-17: Resolved code-review findings and set story to `done`.
