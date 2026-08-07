---
baseline_commit: 20bb6f67959918322c5b65c8fb573bec068f9979
---

# Story CP-014.1: Settle Backlog Durable Tracking Home

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an agent proving the F1 cleanup state,
I want `docs/backlog.md` classified item-by-item and either migrated to a durable tracking home or kept with an explicit narrow authority label,
so that CP-014 is resolved with command-checkable proof and no active deferred work is lost, duplicated, or left inside a stale governance surface.

## Acceptance Criteria

1. `docs/backlog.md` remains present after implementation unless Antonio gives fresh explicit deletion authorization in that implementation session and the implementation proves every load-bearing backlog item has a durable successor. The default outcome is classify/migrate/keep with proof, not deletion.
2. Every current section and bullet in `docs/backlog.md` is classified as one of: active F1 backlog item, active cross-project/platform follow-up, completed historical item, superseded/stale governance item, duplicate of a current planning artifact, or no-action/historical context.
3. Active backlog items have an explicit durable tracking home. At minimum, the implementation must classify or migrate the `Deferred Items` and `Not Started` items: polished visualization, dbt evaluation, Airflow orchestration, dashboard/Tableau-ready outputs, machine-learning exploration, generated-report tracking, and next public artifact choice.
4. The long `Architecture Governance` section is not preserved as active authority by inertia. Its platform/bootstrap items are either mapped to existing durable platform/F1 planning artifacts, moved to an appropriate F1-owned follow-up location, or marked historical/stale with a cited reason. Do not create a new local governance framework to preserve it.
5. Completed foundation items are not treated as open backlog. If they remain anywhere, they are labeled as historical/project context or are proven duplicated in current durable sources such as `PROJECT.md`, `_bmad-output/project-context.md`, current PRDs, architecture spines, implementation artifacts, or data-source docs.
6. `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md` gains CP-014 path-level evidence using the existing manifest fields: stable case id, exact path, category, current authority, replacement or successor, active-reference check, existence check, load-bearing-content check, and status.
7. `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md` updates the CP-014 row from "Retained, needs migration or keep decision" to the exact evidence-backed status reached by this implementation (`covered`, `partially_covered`, or `unresolved`). Use the ledger's real `Required Proof` column, not a fabricated status/disposition column.
8. `_bmad-output/implementation-artifacts/deferred-work.md` is updated only for CP-014-related follow-up: mark the existing `docs/backlog.md` migration item resolved if fully settled, or replace it with narrower remaining blockers if any backlog content lacks a durable home.
9. CP-014 does not silently resolve CP-013 (`docs/asset_inventory.md`), CP-015 (`docs/questions.md`), CP-016 (`docs/decisions.md`), CP-017 FR5 artifact triage, CP-018 inbox-retirement blockers, or the run-record transition. References to those cases may be cited as dependencies or sibling cases only.
10. Command and validation evidence is appended to `docs/run_log.md`; this story's Dev Agent Record, File List, Change Log, and status are updated. `_bmad-output/implementation-artifacts/sprint-status.yaml` was absent at story creation, so record no sprint-status sync unless the file exists by implementation time.

## Tasks / Subtasks

- [x] Capture pre-work state and confirm scope. (AC: 1, 9, 10)
  - [x] Run `git status --short` and record that the working tree was already dirty; do not revert, normalize, or take ownership of unrelated changes.
  - [x] Confirm whether `_bmad-output/implementation-artifacts/sprint-status.yaml` exists before assuming story status sync is possible.
  - [x] Read this story, `docs/backlog.md`, `_bmad-output/specs/spec-cleanup-proof/SPEC.md`, `cleanup-proof-ledger.md`, `cleanup-proof-manifest.md`, `_bmad-output/implementation-artifacts/deferred-work.md`, and Story 1.2's review correction before editing.
- [x] Build the CP-014 evidence set. (AC: 2-5)
  - [x] Read `docs/backlog.md` completely and inventory every section/bullet.
  - [x] Run active-reference searches for `docs/backlog.md` and `backlog.md` across `AGENTS.md`, `PROJECT.md`, `_bmad-output`, `docs`, `src`, `scripts`, `notebooks`, and `tests`; classify hits as active, historical, cleanup-proof self-hit, or stale.
  - [x] Specifically inspect `docs/data_sources.md` and `docs/asset_inventory.md` hits for stale claims about `docs/backlog.md`; fix, classify, or defer them with cited rationale rather than leaving contradictions unmentioned.
  - [x] Cross-check active-looking backlog content against `PROJECT.md`, `_bmad-output/project-context.md`, current PRDs, current architecture, `deferred-work.md`, and implementation artifacts before deciding whether to migrate or keep it.
- [x] Classify or migrate backlog content without overclaiming. (AC: 1-5, 8, 9)
  - [x] For `Deferred Items`, map each item to a durable home or migrate it: polished visualization, dbt, Airflow, dashboard/Tableau outputs, and ML exploration.
  - [x] For `Not Started`, map or migrate generated-report tracking and next public artifact choice.
  - [x] For `Architecture Governance`, separate historical platform-bootstrap narrative from still-active cross-project or cleanup-proof follow-ups.
  - [x] For `Completed Foundation Items`, either remove from active backlog context, relabel as historical, or prove the content already lives in current durable project/data-source context.
  - [x] If `docs/backlog.md` remains, rewrite its purpose/status so it cannot be mistaken for active governance authority unless that is the explicit keep decision.
  - [x] Do not create `docs/roadmap.md`, a new backlog framework, a new routing protocol, or a local governance script unless a direct requirement emerges and is recorded as a separate decision.
- [x] Add CP-014 cleanup-proof evidence. (AC: 6, 7)
  - [x] Add a CP-014 row to `cleanup-proof-manifest.md`, following the established CP-017/CP-018/CP-019/CP-022/CP-026 table shape.
  - [x] Update the manifest top matter ("Parent cases" and purpose paragraph) if needed so it accurately includes CP-014 without implying deletion authorization.
  - [x] Update the CP-014 row in `cleanup-proof-ledger.md` to point to the manifest row and state the evidence-backed status.
  - [x] Preserve the cleanup-proof non-goal: proof is not deletion authorization.
- [x] Reconcile deferred-work tracking. (AC: 8, 9)
  - [x] Update only the existing CP-014 `docs/backlog.md` migration item from the Story 1.2 code-review resolution section.
  - [x] If active content remains unresolved, replace the broad item with specific blockers and their current owner/path.
  - [x] Do not absorb CP-015 questions, CP-016 decisions, CP-017 platform-provenance triage, or run-record-transition work into CP-014.
- [x] Validate and record evidence. (AC: 1-10)
  - [x] Run `test -f docs/backlog.md && echo present || echo missing`.
  - [x] Run active-reference searches for `docs/backlog.md` and `backlog.md`, then classify the hits.
  - [x] Validate the CP-014 manifest row has all required columns and no blank line breaks the manifest table.
  - [x] Validate the CP-014 ledger row uses the real `Required Proof` column and does not invent a new field.
  - [x] Run `git diff --check` scoped to touched tracked files.
  - [x] For new or untracked markdown artifacts, run no-index whitespace checks and treat exit code `1` as expected when the diff itself is clean.
  - [x] Append command/result evidence to `docs/run_log.md` and verify the append landed at the tail.
  - [x] Update this story's task checkboxes, Debug Log References, Completion Notes, File List, Change Log, and status.

### Review Findings

- [x] [Review][Patch] Active deferred backlog items are marked resolved without a real tracking surface [docs/backlog.md:27]
- [x] [Review][Patch] Platform-bootstrap sub-follow-ups are collapsed instead of mapped or explicitly deferred [docs/backlog.md:11]
- [x] [Review][Patch] Same-date PRD and FR/OQ references are ambiguous enough to break replayable proof [docs/backlog.md:27]
- [x] [Review][Patch] Active-reference classification omits the `docs/decisions.md` backlog hit [cleanup-proof-manifest.md:11]
- [x] [Review][Patch] Manifest replay block omits CP-014 existence and active-reference checks [cleanup-proof-manifest.md:46]
- [x] [Review][Patch] CP-014 proof overstates the baseline `docs/data_sources.md` contradiction [cleanup-proof-manifest.md:11]

## Dev Notes

### Scope Boundary

- This is a backlog-content classification/migration and cleanup-proof evidence story. It is not a broad roadmap redesign or product-planning exercise.
- Default implementation keeps `docs/backlog.md` present unless explicit deletion authorization is given and every load-bearing fact has a durable successor.
- The implementation may rewrite `docs/backlog.md` in place, migrate content to existing BMAD artifacts, or leave it as a narrowly labeled retained backlog file if that is the evidence-backed keep decision.
- Do not solve CP-013 (`docs/asset_inventory.md`), CP-015 (`docs/questions.md`), CP-016 (`docs/decisions.md`), CP-017, CP-018, CP-023, or run-record-transition work beyond citing them as dependencies or sibling cases.
- Do not add source code, tests, notebooks, dependencies, dbt, Airflow, dashboard scaffolding, or ML scaffolding for this story.

### Current CP-014 State

`cleanup-proof-ledger.md` defines CP-014 as:

| Field | Value |
| --- | --- |
| Artifact or path | `docs/backlog.md` |
| Classification | Retained, needs migration or keep decision |
| Required proof | Identify active backlog items and their durable tracking home. |

At story creation on 2026-07-21, `docs/backlog.md` is present and 38 lines long. It contains:

- `Architecture Governance` with a long multi-project platform/bootstrap follow-up, monthly inventory review, inventory validation/detail cleanup, potential `docs/roadmap.md`, possible automation/fitness checks, and `docs/asset_inventory.md` unknown/TBD review.
- `Completed Foundation Items` for KaggleHub setup, raw Kaggle download, DuckDB build, first report/output generation, source/database/analysis module structure, SQL folders, Jolpica loading, circuits/qualifying load, validation checks, and constructor reconciliation.
- `Deferred Items`: polished visualization, dbt evaluation, Airflow orchestration, dashboard/Tableau-ready outputs, and machine-learning exploration.
- `Not Started`: whether generated reports should be tracked as portfolio artifacts, and whether the next public artifact should be Markdown, Plotly, or Tableau-ready export.

The current file still describes architecture-governance follow-ups as a local backlog surface and mentions `docs/architecture_operating_model.md`, `docs/architecture_principles.md`, and local governance automation candidates. Those docs and scripts have been retired or moved under the platform/BMAD authority model, so the developer must not preserve that language as active authority without direct evidence.

### Existing File Intelligence

Current active-looking backlog items likely requiring durable placement:

- Future stack/options already appear in active project direction: `PROJECT.md` names Airflow, dbt, Tableau/dashboard outputs, scikit-learn/ML, and Plotly as progressive future directions, not current v1 implementation requirements.
- The 2026-07-17 product PRD and architecture spine keep Airflow, dbt, hosted dashboards, production deployment, and forecast-model design deferred unless a later PRD changes scope.
- The questions-analysis PRD/addendum also keep forecast modeling, dashboards, automated ingestion, paid APIs, heavy infrastructure, and broader source enrichment outside MVP.
- `deferred-work.md` currently has the exact CP-014 follow-up from Story 1.2 review: migrate `docs/backlog.md`'s open `Deferred Items` and `Not Started` items to a successor location, or leave the file in place if no successor is warranted.

Items that should not be treated as active backlog without evidence:

- `Completed Foundation Items` are historical status/context, not work to do.
- The platform/bootstrap Phase 0-6 narrative is partly historical and partly cross-project/platform-owned. Do not move platform-owned work into F1 as if it were F1-local implementation scope.
- The potential `docs/roadmap.md` item should not cause the dev agent to create `docs/roadmap.md` automatically; it is itself a backlog-routing question.
- Inventory review items overlap CP-013 and `docs/asset_inventory.md`; cite CP-013 or its resolved/narrowed state rather than absorbing asset-inventory cleanup into CP-014.
- `docs/data_sources.md` currently contains stale no-longer-deferred wording that points at `docs/backlog.md` even though CP-014 is changing backlog authority. Because `docs/data_sources.md` is a CP-017 platform-provenance file, CP-014 should either make a narrowly justified wording fix if required for CP-014 proof or record the contradiction as a CP-017/CP-014-adjacent deferred blocker. Do not silently ignore it.
- `docs/asset_inventory.md` currently describes `docs/backlog.md` as part of an active governance/log surface. If CP-014 changes the backlog authority model, update or explicitly defer that adjacent reference so the implementation does not leave two active stories about backlog authority.

### Cleanup-Proof Contract To Preserve

`_bmad-output/specs/spec-cleanup-proof/SPEC.md` is the canonical cleanup-proof contract. Relevant constraints:

- The proof must be path-level and case-level.
- The proof is not deletion authorization.
- Retained docs must be current, explicitly historical, or tracked for triage; stale retained files cannot silently remain ambiguous authority.
- Load-bearing facts from retained-stale documents must have a durable surviving home or a named deferred state.
- Routine F1-local cleanup progress stays in F1 unless cross-project references, evidence locations, named external paths, setup expectations, dependency assumptions, protocol assumptions, or authority assumptions change.

`cleanup-proof-manifest.md` already contains long single-line GFM table rows. Preserve that established shape unless a separate story redesigns it. Prior reviews found recurring pitfalls: placeholder commands in manifest rows, blank lines between adjacent table rows, and claims that scoped `git diff --check` covers untracked files when it does not.

### Previous Story Intelligence

- Story 1.2 over-deleted `docs/backlog.md` and restored it after review because it contained open work with no successor list. Do not repeat that by deleting before migration or keep-decision proof.
- CP-013.1 established the sibling boundary: `docs/backlog.md`, `docs/questions.md`, and `docs/decisions.md` are separate cleanup-proof cases and must not be silently resolved inside another case.
- CP-017.1 established path-level manifest rows and the rule that broad categories cannot stand in for exact proof.
- CP-018.1 established that proof coverage and deletion authorization are separate gates.
- CP-019.1 and CP-026.1 exposed manifest-editing pitfalls: avoid broken `rg` syntax, avoid blank table-row breaks, and use the ledger's real `Required Proof` column.
- CP-022.1 is the closest verification-and-ledger precedent for a resolved cleanup-proof case: it added manifest rows, reconciled the ledger, ran tests as a doc-only sanity check, and kept source verification targets read-only.

### Architecture And Process Guardrails

- Root conventions come from sibling `../platform`, but `f1_analytics` remains an independent repo. Do not move F1 files, data, source artifacts, decisions, or history into `../platform`.
- Active F1 knowledge homes are narrow: `PROJECT.md`, `_bmad-output/project-context.md`, `_bmad-output/planning-artifacts/**`, code/notebooks/runtime docs, and narrowly triaged `docs/` files only for project knowledge, navigation, setup, standards, or evidence.
- Durable planning decisions live under `_bmad-output/planning-artifacts/decisions/`, not `docs/decisions.md`.
- Current project rules require command and validation results in `docs/run_log.md`; this story should append evidence there even though future runtime-evidence direction remains unsettled.
- No source-code changes are expected for CP-014. Reusable code remains under `src/f1_analytics/`; scripts remain thin wrappers.

### Latest Technical Information

No external API, package, framework, or version-sensitive implementation detail applies to CP-014. Use local markdown artifacts, `rg`, `test`, and Git whitespace validation only; do not add dependencies.

### Testing And Validation

Minimum validation:

- `git status --short` before and after.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` existence check.
- `test -f docs/backlog.md && echo present || echo missing`.
- `rg -n "docs/backlog\\.md|backlog\\.md" AGENTS.md PROJECT.md _bmad-output docs src scripts notebooks tests -S`, with hit classification.
- A content classification check proving every `docs/backlog.md` section/bullet is either migrated, retained with explicit authority, marked historical/completed, or left as a concrete deferred blocker.
- Manifest row check for exactly one CP-014 row unless implementation deliberately uses deterministic sub-rows and updates the ledger accordingly.
- `git diff --check` scoped to touched tracked files.
- No-index whitespace checks for new/untracked markdown artifacts.
- `PYTHONPATH=src python3 -m unittest discover -s tests` is recommended as a doc-only regression sanity check because this repo has an established test suite, but the primary proof is the document/reference evidence above.
- `tail -n 80 docs/run_log.md` or equivalent after appending evidence.

### Git Intelligence

Recent commits at story creation:

- `20bb6f6 docs: record story 4.3 platform exchange`
- `59294ce feat: claim daily pipeline atomic staging`
- `3a84543 Initial baseline commit`

The working tree was already dirty at story creation with many unrelated modified/deleted/untracked files across planning artifacts, cleanup artifacts, `docs/`, source, tests, and notebooks. Preserve unrelated changes.

### Project Structure Notes

Expected touched files:

- `docs/backlog.md` (classification/migration/retained-status rewrite, unless implementation proves no in-place edit is warranted)
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md` (new CP-014 row)
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md` (updated CP-014 row/status)
- `_bmad-output/implementation-artifacts/deferred-work.md` (resolve or narrow CP-014 deferred item)
- `_bmad-output/implementation-artifacts/cp-014-settle-backlog-durable-tracking-home.md` (this story)
- `docs/run_log.md` (append-only evidence)

Conditional/narrow touches only if direct reference wording requires them:

- `docs/asset_inventory.md` (only to avoid a stale `docs/backlog.md` authority claim; do not resolve CP-013 here)
- `docs/data_sources.md` (only to avoid a false `docs/backlog.md` deleted/present claim; do not resolve CP-017 here)
- Current PRD/architecture artifacts only if the implementation chooses them as a durable tracking home and records why that edit is in scope

Expected untouched paths:

- `src/`, `scripts/`, `notebooks/`, `tests/`, `data/`, `outputs/`, `external/`
- `docs/questions.md` and `docs/decisions.md` except read-only checks
- CP-018 inbox notes
- CP-017 platform-provenance files other than append-only `docs/run_log.md` evidence

### References

- [Source: `_bmad-output/specs/spec-cleanup-proof/SPEC.md`](../specs/spec-cleanup-proof/SPEC.md) - canonical cleanup-proof contract, constraints, non-goals, and CP-014-adjacent open question.
- [Source: `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md`](../specs/spec-cleanup-proof/cleanup-proof-ledger.md) - CP-014 row and manifest field contract.
- [Source: `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md`](../specs/spec-cleanup-proof/cleanup-proof-manifest.md) - path-level evidence pattern and reference-classification guardrails.
- [Source: `docs/backlog.md`](../../docs/backlog.md) - source artifact to classify or migrate.
- [Source: `_bmad-output/implementation-artifacts/deferred-work.md`](deferred-work.md) - CP-014 deferred migration item from Story 1.2 review.
- [Source: `_bmad-output/implementation-artifacts/1-2-delete-zero-dependency-legacy-docs.md`](1-2-delete-zero-dependency-legacy-docs.md) - review correction that restored `docs/backlog.md` and required migration/keep decision instead of deletion.
- [Source: `_bmad-output/planning-artifacts/research/cleanup-proof-first-principles-draft-2026-07-17.md`](../planning-artifacts/research/cleanup-proof-first-principles-draft-2026-07-17.md) - original CP-014 unresolved-case rationale.
- [Source: `_bmad-output/planning-artifacts/prds/prd-f1_analytics-2026-07-15/prd.md`](../planning-artifacts/prds/prd-f1_analytics-2026-07-15/prd.md) - original cleanup PRD and later-superseded deletion wording.
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-15/ARCHITECTURE-SPINE.md`](../planning-artifacts/architecture/architecture-f1_analytics-2026-07-15/ARCHITECTURE-SPINE.md) - retained-doc triage and active-knowledge-home invariants.
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md`](../planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md) - current local analytics/question-backtesting architecture and deferred future-work boundaries.
- [Source: `_bmad-output/implementation-artifacts/cp-013-reclassify-asset-inventory.md`](cp-013-reclassify-asset-inventory.md), [Source: `_bmad-output/implementation-artifacts/cp-017-split-path-level-cleanup-proof-manifest.md`](cp-017-split-path-level-cleanup-proof-manifest.md), [Source: `_bmad-output/implementation-artifacts/cp-018-classify-story-4-3-inbox-exceptions-against-oq3.md`](cp-018-classify-story-4-3-inbox-exceptions-against-oq3.md), [Source: `_bmad-output/implementation-artifacts/cp-022-confirm-f1-recorded-durable-disposition-separately.md`](cp-022-confirm-f1-recorded-durable-disposition-separately.md), and [Source: `_bmad-output/implementation-artifacts/cp-026-confirm-doc-cleanup-does-not-break-questions-analysis-work.md`](cp-026-confirm-doc-cleanup-does-not-break-questions-analysis-work.md) - cleanup-proof precedents and review lessons.
- [Source: `PROJECT.md`](../../PROJECT.md) and [Source: `_bmad-output/project-context.md`](../project-context.md) - active local project rules and implementation context.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-07-21 07:54 CDT: Pre-work `git status --short` showed a broadly dirty working tree before CP-014 edits; unrelated changes were left untouched.
- 2026-07-21 07:54 CDT: `_bmad-output/implementation-artifacts/sprint-status.yaml` was absent, so story status was tracked only in this file.
- 2026-07-21 07:54 CDT: Red checks confirmed the CP-014 manifest row was absent and stale backlog wording existed in `docs/data_sources.md` / `docs/asset_inventory.md` before implementation.
- 2026-07-21 07:54 CDT: Validation evidence appended to `docs/run_log.md` under "BMad Dev Story CP-014.1 Settle Backlog Durable Tracking Home".
- 2026-07-21 08:08 CDT: Code-review patch pass resolved all six CP-014.1 review findings and kept sibling cases separate.

### Implementation Plan

- Retain `docs/backlog.md` and rewrite it as a CP-014 classification snapshot rather than a roadmap/governance/deferred-work authority.
- Use `_bmad-output/implementation-artifacts/deferred-work.md` plus exact supporting PRD/architecture paths for active future-work items.
- Fix only adjacent stale `docs/backlog.md` authority references required for CP-014 proof in `docs/data_sources.md` and `docs/asset_inventory.md`.
- Add CP-014 path-level proof to the cleanup-proof manifest and update the ledger's real `Required Proof` column.
- Narrow only the existing CP-014 migration item in `deferred-work.md`; leave sibling cleanup cases separate.

### Completion Notes List

- 2026-07-21: Story drafted by `bmad-create-story` from CP-014 cleanup-proof ledger/spec context, current `docs/backlog.md`, Story 1.2 restoration evidence, deferred-work item, cleanup architecture, current analytics architecture, and CP-013/CP-017/CP-018/CP-022/CP-026 precedents. Status set to `ready-for-dev`.
- 2026-07-21: `_bmad-output/implementation-artifacts/sprint-status.yaml` was absent at story creation, so no sprint-status sync was possible.
- 2026-07-21: Latest technical research determined not applicable because CP-014 is local markdown/proof work with no external API, package, framework, or version-sensitive dependency.
- 2026-07-21: Implemented CP-014.1. `docs/backlog.md` remains present and now classifies every former backlog bullet as active F1 backlog, active cross-project/platform follow-up, completed historical item, superseded/stale governance item, or sibling cleanup-proof scope. It is explicitly not active roadmap/governance/deferred-work authority.
- 2026-07-21: Active future-work bullets for visualization polish, dbt, Airflow, dashboard/Tableau outputs, ML exploration, generated-report tracking, and next public artifact choice now point to narrowed entries in `_bmad-output/implementation-artifacts/deferred-work.md` plus exact supporting PRD/architecture paths.
- 2026-07-21: Clarified adjacent CP-014 stale authority wording in `docs/data_sources.md` and `docs/asset_inventory.md`; `docs/questions.md` remains unchanged and is classified as CP-015 sibling scope.
- 2026-07-21: Added CP-014 manifest/ledger proof, replaced the broad CP-014 deferred-work migration item with narrower follow-ups, and preserved the cleanup-proof non-goal that proof is not deletion authorization.
- 2026-07-21: Code-review patches resolved: split platform-bootstrap residuals, made active deferred work explicit in `deferred-work.md`, replaced ambiguous same-date PRD/OQ shorthand with exact paths, classified the `docs/decisions.md` backlog hit, added CP-014 replay commands, and corrected the `docs/data_sources.md` proof description.
- 2026-07-21: Story status set to `done` after all review findings were patched and checked off. `_bmad-output/implementation-artifacts/sprint-status.yaml` remains absent, so no sprint-status sync was possible.
- 2026-07-21: Validation passed: `docs/backlog.md` present; active-reference sweep classified hits; stale-wording check clean; CP-014 manifest/ledger table shape valid; scoped `git diff --check` clean; no-index whitespace checks clean with expected exit code 1; full unittest regression ran 210 tests and returned OK with sandbox-related Arrow `sysctlbyname` warnings.

### File List

- `docs/backlog.md`
- `docs/data_sources.md`
- `docs/asset_inventory.md`
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md`
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/cp-014-settle-backlog-durable-tracking-home.md`
- `docs/run_log.md`

## Change Log

- 2026-07-21: Story drafted by `bmad-create-story`. Status set to `ready-for-dev`. Sprint status was not updated because `_bmad-output/implementation-artifacts/sprint-status.yaml` is absent.
- 2026-07-21: Implemented CP-014.1 backlog classification, durable tracking-home proof, manifest/ledger updates, deferred-work reconciliation, adjacent stale-reference fixes, and validation evidence. Status set to `review`.
- 2026-07-21: Applied code-review fixes for all six CP-014.1 findings. Status set to `done`; sprint status was not updated because `_bmad-output/implementation-artifacts/sprint-status.yaml` is absent.
