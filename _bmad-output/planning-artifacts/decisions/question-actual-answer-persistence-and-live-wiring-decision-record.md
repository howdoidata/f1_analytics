---
title: "Question Actual-Answer Persistence Surface And Live Wiring Decision Record"
status: accepted
created: 2026-07-28
source_material:
  - "_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md"
  - "_bmad-output/implementation-artifacts/sprint-status.yaml"
  - "_bmad-output/implementation-artifacts/deferred-work.md"
  - "src/f1_analytics/analysis/question_feature_availability.py"
  - "src/f1_analytics/analysis/question_answers.py"
  - "src/f1_analytics/analysis/question_backtest_scoring.py"
  - "src/f1_analytics/analysis/question_workflow_surfaces.py"
  - "scripts/build_question_baseline_predictions.py"
  - "_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md"
---

# Question Actual-Answer Persistence Surface And Live Wiring Decision Record

## Decision

This resolves the epic-3 and epic-5 `sprint-status.yaml` action items — the two open decisions were the same decision family (a persistence surface, and wiring live extraction into it), so they are decided together.

1. **Persistence surface**: `Actual Answer Components` (from `question_answers.py`) and the `Feature Availability Contract` (from `question_feature_availability.py`) get a durable DuckDB target-store table each — `question_actual_answer_components` and `question_feature_availability_contract` — built the same way the existing `raw_jolpica_*` / `combined_*` tables are: a thin `scripts/*.py` wrapper calling a `src/f1_analytics/` build function that writes via `duckdb_io.py`.
2. Unlike the raw/combined ingestion tables (which are idempotent `CREATE OR REPLACE` syncs of an external source), these two target-store tables are **append-only history**, one row per `(question_id, component_key, extraction_timestamp_or_build_id)`. A re-run adds new rows; it never overwrites or deletes a prior run's rows.
3. **Live wiring**: a new script (e.g. `scripts/build_question_actual_answers.py`) runs the existing Epic-2 extractors (`question_lap_answers.py`, the results-based extractor, etc.) against real DuckDB source tables for every `question_catalog.py` row, and writes the result to `question_actual_answer_components`. `question_backtest_scoring.py` and `question_workflow_surfaces.py` then read from that persisted table instead of relying on a caller to hand them in-memory rows built ad hoc — closing the gap visible today in `outputs/reports/question_workflow_surfaces.md`, where every `Report Summary` reads "Answer: not yet computed in this bundle."

This decision covers the *design*; it does not itself write the new script or tables — see Consequences for the follow-up action item.

## Rationale

- **Boring technology, no new infrastructure.** DuckDB is already the project's only data store (`project-context.md`: "no server-based database"), and the architecture spine's own `## Deferred` section names this exact choice as open ("Storage choice for question catalog and target store — DuckDB tables, checked-in seeds plus build step, or generated outputs are all viable"). A DuckDB table, built by a thin script exactly like every other target table in this repo, is the option that adds zero new moving parts.
- **Append-only, not replace-in-place, because the consumers need history.** `deferred-work.md`'s "Track 2 — blocked surfaces" entry is explicit that Target Store Review, Scoring and Baseline Review, and the Discrepancy Panel are all blocked on "a durable store of Actual Answer Components across runs" and, for the Discrepancy Panel specifically, one that can "preserve both values across re-runs." A `CREATE OR REPLACE` table (the pattern `raw_jolpica_*` and `combined_*` already use) would silently destroy exactly the discrepancy evidence those three surfaces exist to review. Appending with `extraction_timestamp_or_build_id` as part of the row identity — a field `ActualAnswerComponent` already carries — gets history for free without a new schema concept.
- **Matches AD-3's own vocabulary, doesn't invent one.** `ARCHITECTURE-SPINE.md` AD-3 already defines Actual Answer Components as statused targets with a controlled status set; this decision persists that existing shape verbatim rather than designing a new one.
- **Closes a real, confirmed gap, not a hypothetical one.** Running `scripts/build_question_workflow_surfaces.py` live today confirms every `Report Summary`'s `answer_display` is `None` ("not yet computed in this bundle") — this is the literal, current state of the "not yet live end-to-end" problem the epic-5 action item names.

## Consequences

- The epic-3 action item ("Decide the durable persistence surface...") and the epic-5 action item ("Decide whether/how to wire live DuckDB extractors...") are marked `done` as **decisions** — the design is chosen, per this record.
- **No table, script, or wiring code exists yet.** Building `question_actual_answer_components` / `question_feature_availability_contract` (schema, write function in `src/f1_analytics/`, a `CREATE TABLE IF NOT EXISTS` + `INSERT` pattern rather than `duckdb_io.write_dataframe()`'s existing `CREATE OR REPLACE` helper, which is the wrong tool for append-only history), the new orchestration script, and rewiring `question_backtest_scoring.py` / `question_workflow_surfaces.py` to read from it, is separate, not-yet-scheduled implementation work. A new action item tracks this below.
- This is epic-sized, not story-sized: it touches the scoring module, the workflow-surfaces module, and adds two new tables plus a new script. Recommend running `bmad-create-epics-and-stories` (or `bmad-correct-course` if it should fold into Epic 7's scope) to size and sequence it properly rather than starting it as an ad hoc story.
- Until this is built, `question_backtest_scoring.py` and `question_workflow_surfaces.py` keep their current caller-supplied-data contract; no existing story or test needs to change because of this decision alone.
- The Track 2 UX surfaces (Target Store Review, Scoring and Baseline Review, Discrepancy Panel) remain blocked until the append-only table exists and is populated — this decision unblocks their design, not their build.
