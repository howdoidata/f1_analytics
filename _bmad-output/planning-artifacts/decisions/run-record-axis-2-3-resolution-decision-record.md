---
title: "Run-Record Contract Decision — Axis 2/3 Resolution"
status: accepted
created: 2026-07-21
source_material:
  - _bmad-output/planning-artifacts/decisions/run-record-contract-decision-record.md
  - _bmad-output/implementation-artifacts/deferred-work.md
  - _bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md
  - _bmad-output/planning-artifacts/cross-repo-notes/f1-to-administrative-run-record-axis-2-3-scoping-2026-07-21.md
  - ../platform/exchange/administrative-to-f1-project-authority-boundary-and-open-admin-blockers-2026-07-21.md
  - _bmad-output/planning-artifacts/cross-repo-notes/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md
  - _bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md
---

# Run-Record Contract Decision — Axis 2/3 Resolution

## Purpose

Resolves the two axes `run-record-contract-decision-record.md` (2026-07-16) explicitly deferred: Axis 2 (the concrete write contract for `run_daily_pipeline.py` evidence, which platform's Story 4.4 is blocked on) and Axis 3 (`docs/run_log.md`'s final disposition). Made live with Antonio during a 2026-07-21 correct-course session, after F1 asked administrative whether it wanted co-decision authority over this and administrative declined (`administrative-to-f1-project-authority-boundary-and-open-admin-blockers-2026-07-21.md`: "Administrative does not request co-decision authority over this Project's implementation story... The Project owns its local implementation and enforcement decisions").

## Decision — Axis 2: How `run_daily_pipeline.py` should write run evidence

**Decided: a new dedicated machine-readable log**, separate from `docs/run_log.md` and from hand/agent-authored prose Dev Agent Records. Automated per-run pipeline telemetry (start, per-stage success/failure, benign-skip vs. failure distinction) is high-frequency and machine-generated; interleaving it into either prose-oriented evidence artifact would degrade both.

Clarification accepted 2026-07-22: "separate from BMAD implementation artifacts" means separate from prose, per-story implementation records, not necessarily outside the broader `_bmad-output/implementation-artifacts/` directory tree. The concrete JSONL path `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` satisfies this Axis 2 category because it is a dedicated machine-readable runtime telemetry file, is explicitly gitignored with its lock file, and has its own schema/append contract in `_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md`.

## Decision — Axis 3: `docs/run_log.md`'s disposition

**Decided: closed as a historical record**, once `AGENTS.md` no longer requires writing to it. `docs/run_log.md` (~7,141 lines as of 2026-07-21) stops accepting new entries at that point and is retained as closed historical/evidence material, consistent with AD-2's framing (historical/evidence material only, never governance authority) and AD-3 (retirement requires explicit scope + salvage proof, which this decision provides — no content is discarded, only frozen).

## Consequence For Platform's Story 4.4

Platform's Story 4.4 AC text still names `docs/run_log.md` as the literal write target (per the preserved snapshot in `run-record-contract-decision-record.md`'s appendix). That target remains incorrect under this decision too — the correct target is the new dedicated machine-readable log the follow-up story defines. Platform is notified via `../platform/exchange/f1-to-platform-run-record-axis-2-3-resolved-2026-07-21.md`.

## Follow-Up Story

`_bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md` carries out the concrete implementation: define the new log's format/location/schema, update `run_daily_pipeline.py` to write to it, update `AGENTS.md` to stop requiring `docs/run_log.md`, and close `docs/run_log.md` as historical. The follow-up story has now implemented the concrete contract at `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl`.

## Status

Accepted. Axis 2 and Axis 3 both resolved. Platform's Story 4.4 may now proceed with `bmad-create-story` against `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` and `_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md`, rather than against `docs/run_log.md`'s stale AC text.
