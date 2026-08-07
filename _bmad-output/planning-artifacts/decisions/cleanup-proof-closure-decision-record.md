---
title: "Cleanup-Proof Closure Decision"
status: accepted
created: 2026-07-21
source_material:
  - _bmad-output/planning-artifacts/cross-repo-notes/administrative-to-f1-stop-cleanup-proof-expansion-2026-07-21.md
  - _bmad-output/specs/spec-cleanup-proof/SPEC.md
  - _bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md
  - _bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md
  - _bmad-output/implementation-artifacts/deferred-work.md
  - _bmad-output/planning-artifacts/decisions/run-record-contract-decision-record.md
---

# Cleanup-Proof Closure Decision

## Purpose

Record F1's durable answer to administrative's 2026-07-21 recommendation to stop cleanup-proof expansion and close the migration through one bounded terminal story.

## Decision

F1 accepts the recommendation. As of the 2026-07-21 AGENTS update, `docs/run_log.md` is frozen historical evidence and current command/validation evidence belongs in the active story's Dev Agent Record under `_bmad-output/implementation-artifacts/`. Automated runtime telemetry writes to `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` under the accepted BMAD run-record contract.

Effective immediately, no new cleanup-proof `CP-*` cases should be created unless an active code/path reference is broken, a sibling project is blocked, or Antonio explicitly authorizes a new case. Open cleanup-proof work should route through the terminal story `_bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md`.

Proof rows are evidence, not authority. Final authority lives only in the named durable home for the artifact or fact being classified.

## Authority Homes

- Durable decisions: `_bmad-output/planning-artifacts/decisions/` is the current durable decision home. `docs/decisions.md` is a historical/transitional decision log pending CP-016 triage, not the current destination for new durable decisions.
- Deferred work: `_bmad-output/implementation-artifacts/deferred-work.md` is the active deferred-work surface. `docs/backlog.md` remains a retained CP-014 classification snapshot, not an active roadmap or deferred-work ledger.
- Run evidence: `docs/run_log.md` is frozen historical evidence. Current command/validation evidence belongs in active BMAD implementation artifacts; automated runtime evidence uses `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` and remains gitignored runtime telemetry.

## Consequences

The cleanup-proof SPEC, ledger, and manifest should stop growing as an operating procedure. After the terminal story closes, those artifacts become migration evidence unless a future accepted decision explicitly keeps a specific piece as current process.

The manifest top paragraph and narrative cells should not be extended for routine proof. Any remaining proof should be compact and link to terminal-story evidence.

Retained legacy docs should get only a one-line status header where needed. Do not add bespoke disclaimers to individual paragraphs or cases.

## Status

Accepted. Terminal closure story created. No deletion is authorized by this decision.
