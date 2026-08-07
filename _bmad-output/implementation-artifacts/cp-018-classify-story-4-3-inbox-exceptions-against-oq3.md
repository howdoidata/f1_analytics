---
baseline_commit: 20bb6f67959918322c5b65c8fb573bec068f9979
---

# Story CP-018.1: Classify Story 4.3 Inbox Exceptions Against OQ3

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an agent proving the F1 cleanup state,
I want the two retained Story 4.3 inbox markdown exceptions classified against OQ3 with path-level evidence,
so that they are retained, retired, or deferred only when their load-bearing cross-repo facts have durable F1-owned successors.

## Acceptance Criteria

1. CP-018 is represented with path-level evidence for both retained exception files: `docs/inbox/f1-to-platform-story-4-3-response-2026-07-15.md` and `docs/inbox/platform-to-f1-story-4-3-handoff-2026-07-15.md`.
2. Each CP-018 path-level row records the cleanup-proof ledger fields: stable case id, exact path, category, current authority, replacement or successor, active-reference check, existence check, load-bearing-content check, and status (`covered`, `partially_covered`, `unresolved`, `excluded_with_reason`, or `not_yet_researched`).
3. The implementation decides whether OQ3 now has durable resolution permitting retirement of these two markdown notes by checking direct evidence, not inference. At minimum, it checks:
   - F1's accepted Story 4.3 source-control claim at commit `59294ce`.
   - F1's exchange-record commit `20bb6f6`.
   - Platform's Story 4.3 acknowledgment, if still available in `../platform/exchange/` or a claimed durable local copy.
   - `_bmad-output/planning-artifacts/decisions/run-record-contract-decision-record.md`.
   - `_bmad-output/implementation-artifacts/deferred-work.md`.
   - `_bmad-output/specs/spec-cleanup-proof/SPEC.md` and `cleanup-proof-ledger.md`.
4. If evidence proves the two notes have durable successors and no independent active references remain, the implementation may mark CP-018 as retirement-permitted and update cleanup-proof artifacts accordingly. It must not delete either inbox markdown file unless Antonio gives fresh explicit deletion authorization in that implementation session and that authorization is recorded in `docs/run_log.md`.
5. If evidence does not prove durable successor coverage, the two inbox markdown files remain present and CP-018 stays `unresolved` or `partially_covered` with a concrete blocker. Do not paper over missing platform acknowledgment, missing run-record-contract follow-up, or unresolved OQ3 state with vague "historical only" wording.
6. This story does not touch `docs/inbox/Gmail - 2026 F1 Questions.pdf`, does not remove `docs/inbox/` as a directory, and does not change `src/f1_analytics/analysis/question_catalog.py`'s active PDF reference.
7. Command and validation evidence is appended to `docs/run_log.md`; story status/progress and file list are updated in this implementation artifact. If `_bmad-output/implementation-artifacts/sprint-status.yaml` is still absent, record that no sprint-status sync was possible.

## Tasks / Subtasks

- [x] Capture pre-work state and confirm scope. (AC: 1, 4, 6, 7)
  - [x] Run `git status --short` and record that the working tree is already dirty; do not revert, normalize, or take ownership of unrelated changes.
  - [x] Confirm whether `_bmad-output/implementation-artifacts/sprint-status.yaml` exists before assuming story status sync is possible.
  - [x] Read this story file, `_bmad-output/specs/spec-cleanup-proof/SPEC.md`, `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md`, and `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md` before editing.
  - [x] Confirm both CP-018 source paths exist before making any classification or retirement claim.
- [x] Build the CP-018 evidence set. (AC: 1, 2, 3)
  - [x] Read both retained inbox notes completely.
  - [x] Read current local copies and/or exchange copies for Story 4.3 response, Story 4.3 acknowledgment, Story 3.3 run-record response, and platform Story 4.4 blocking context where available.
  - [x] Run active-reference searches for both exact paths and basenames across `AGENTS.md`, `PROJECT.md`, `_bmad-output`, `docs`, `src`, `scripts`, and `notebooks`.
  - [x] If inspecting sibling `../platform` evidence, keep it read-only except for sanctioned `../platform/exchange/` staging if a later explicit cross-repo note is required.
- [x] Decide CP-018 status without overclaiming. (AC: 2, 3, 4, 5)
  - [x] Identify the load-bearing facts in the inbound handoff: Story 4.3 dirty/accepted file classification, validation evidence, deferred items, and the Story 4.4 run-log gate.
  - [x] Identify the load-bearing facts in the outbound response: F1's acceptance of Story 4.3 commit `59294ce`, local conversation/planning artifacts not committed as Story 4.3 implementation, cleanup may begin as separate pass, and Story 4.4 pause.
  - [x] Map each load-bearing fact to a durable successor or blocker. Expected successor candidates include `docs/run_log.md` historical evidence, `run-record-contract-decision-record.md`, `deferred-work.md`, cleanup-proof SPEC/ledger/manifest rows, and any claimed platform acknowledgment record.
  - [x] Classify CP-018 as `covered`, `partially_covered`, or `unresolved` based on direct evidence. Do not use proof-created self-hits as independent active authority.
- [x] Update cleanup-proof artifacts. (AC: 1, 2, 4, 5)
  - [x] Add CP-018 path-level evidence to the cleanup-proof manifest. If extending the existing CP-017-focused manifest, first adjust its parent/purpose wording so the file no longer falsely claims to contain only CP-017 rows.
  - [x] Update `cleanup-proof-ledger.md` CP-018 wording to point to the new path-level evidence and state the exact status reached.
  - [x] If CP-018 remains unresolved, add or update the concrete blocker in `_bmad-output/implementation-artifacts/deferred-work.md`.
  - [x] If retirement is permitted but not authorized, record that distinction explicitly; proof coverage is not deletion authorization.
- [x] Conditionally retire only the two markdown exceptions. (AC: 4, 5, 6)
  - [x] If and only if direct evidence proves retirement is permitted and Antonio explicitly authorizes deletion in the implementation session, delete only:
    - `docs/inbox/f1-to-platform-story-4-3-response-2026-07-15.md`
    - `docs/inbox/platform-to-f1-story-4-3-handoff-2026-07-15.md`
  - [x] Do not delete `docs/inbox/Gmail - 2026 F1 Questions.pdf`.
  - [x] Do not delete `docs/inbox/` while the PDF or any other retained source artifact remains there.
  - [x] If deletion is not authorized, leave both markdown files in place even if evidence says retirement is permitted.
- [x] Validate and record evidence. (AC: 1-7)
  - [x] Re-run existence checks for the two CP-018 markdown notes and the PDF.
  - [x] Re-run active-reference searches and classify active, historical, exchange-staging, cleanup-proof self-hit, and unresolved hits.
  - [x] Run `git diff --check` scoped to touched files.
  - [x] For any new untracked markdown artifact, run no-index whitespace validation with `git diff --no-index --check /dev/null <file>` and treat exit code `1` as expected when the diff itself is clean.
  - [x] Append command/result evidence to `docs/run_log.md` and verify the append landed at the tail.
  - [x] Update this story's task checkboxes, Debug Log References, Completion Notes, File List, and Change Log.

### Review Findings

- [x] [Review][Patch] Replay validation commands omit touched CP-018 artifacts [_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md:61]
- [x] [Review][Patch] External platform acknowledgment is listed as successor coverage without durable-local qualification [_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md:20]
- [x] [Review][Patch] Ledger required-research guidance still says to extend beyond CP-017 after CP-018 rows were added [_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md:75]
- [x] [Review][Patch] Ledger status field contract does not match the story's literal status values [_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md:56]
- [x] [Review][Patch] Story-creation run-log entry cites validation and sprint-status results without recording all replay commands [docs/run_log.md:6122]
- [x] [Review][Patch] Implementation run-log entry lacks after-work `git status --short` evidence [docs/run_log.md:6178]
- [x] [Review][Patch] Implementation run-log entry lacks post-edit retained-source existence evidence [docs/run_log.md:6180]
- [x] [Review][Patch] Implementation run-log entry lacks CP-018 manifest row-completeness validation evidence [docs/run_log.md:6214]
- [x] [Review][Patch] Implementation run-log entry lacks append-tail verification evidence [docs/run_log.md:6201]

## Dev Notes

### Scope Boundary

- This is a cleanup-proof classification and retirement-permission story, not a broad docs cleanup pass.
- The only CP-018 source paths are the two Story 4.3 markdown notes under `docs/inbox/`.
- The active F1 questions PDF is CP-019, not CP-018. It remains out of scope and currently has an active code reference in `src/f1_analytics/analysis/question_catalog.py`.
- Do not delete files as part of "proof" unless the implementation session gets fresh explicit deletion authorization from Antonio.
- Do not create a new cleanup framework. Extend the existing SPEC/ledger/manifest pattern unless direct evidence shows a separate companion is required.

### Current CP-018 Path Inventory

Both CP-018 paths were present at story creation:

| Path | Story-creation observation |
| --- | --- |
| `docs/inbox/f1-to-platform-story-4-3-response-2026-07-15.md` | 54 lines. F1 acceptance/response note for Story 4.3. States Story 4.3 was accepted at commit `59294ce`, names accepted implementation files, classifies the two local inbox notes as conversation/planning artifacts, says cleanup may begin separately, and says Story 4.4 should remain paused until F1 decides the future run-record contract. |
| `docs/inbox/platform-to-f1-story-4-3-handoff-2026-07-15.md` | 100 lines. Platform handoff clarification. Names expected Story 4.3 F1-side outputs, records validation evidence platform had, lists deferred items not to solve during docs cleanup, and asks F1 to confirm Story 4.3 claim status plus Story 4.4 pause. |

### Story-Creation Active Reference Snapshot

The story-creation search found exact CP-018 path/basename hits in:

- The two CP-018 source files themselves.
- `docs/run_log.md` historical command evidence for claiming and routing the Story 4.3 handoff/response.
- `_bmad-output/implementation-artifacts/deferred-work.md`, which states these files were restored and must stay until OQ3 is resolved and cited.
- `_bmad-output/implementation-artifacts/1-2-delete-zero-dependency-legacy-docs.md`, whose review corrections restored these two notes because OQ3 was not actually resolved.
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md`, which defines CP-018.
- `_bmad-output/planning-artifacts/research/cleanup-proof-first-principles-draft-2026-07-17.md`, which classifies CP-018 as unresolved.

No story-creation hit was found in `src/`, `scripts/`, `notebooks/`, `AGENTS.md`, or `PROJECT.md` for the two markdown note paths. Re-run the search during implementation because the working tree is active.

### Cleanup-Proof Contract To Preserve

`_bmad-output/specs/spec-cleanup-proof/SPEC.md` is the canonical cleanup-proof contract. Relevant constraints:

- Proof must be path-level and case-level.
- Proof is not deletion authorization.
- Cross-repo exchange notes are staging and coordination evidence, not the durable home for F1-local decisions.
- Retained docs must be current, explicitly historical, or tracked for triage.
- Routine F1-local cleanup progress stays in F1; exchange notes are required only when proof work changes active cross-project references, evidence locations, paths another project names, setup expectations, dependencies, protocols, or authority assumptions.

`cleanup-proof-ledger.md` defines CP-018 as a retained exception and asks whether OQ3 now has durable resolution permitting retirement. The dev agent must answer that exact question with evidence, not by relabeling the notes as obsolete because they are old.

### Previous Story Intelligence

- CP-017.1 split a broad retained category into exact path-level rows and established the manifest field shape. Reuse that shape and its reference-classification guardrails.
- CP-017.1 review found that plain scoped `git diff --check` does not validate untracked new artifacts. Use no-index whitespace checks for new markdown files.
- Story 1.2 over-deleted retained material and had to restore these exact two CP-018 files because OQ3 was still unresolved. Treat deletion as a gated outcome, not the default.
- Story 3.3 produced the run-record direction: future runtime evidence moves to BMAD implementation artifacts, but the concrete write contract and `docs/run_log.md` disposition remain deferred. That may partially resolve the Story 4.4 gate, but it does not automatically prove every CP-018 load-bearing fact has a successor.

### Architecture And Process Guardrails

- Root conventions come from sibling `../platform`, but `f1_analytics` remains independent. Do not move code, data, docs, outputs, or git history across repos.
- Durable F1 decisions live under `_bmad-output/planning-artifacts/decisions/`.
- Cross-repo exchange files are staging/coordination evidence. If this story affects platform dependencies or closes a platform-named path, create a F1-owned durable record first and use `../platform/exchange/` only for notification.
- Command and validation evidence still goes to `docs/run_log.md` under current `AGENTS.md`. The future run-record direction does not repeal the active project instruction for this story.
- No code changes are expected.

### Expected File Locations

Expected touched files for implementation:

- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md` (extend from CP-017-only to include CP-018 rows, or add a clearly linked companion if extension would be misleading)
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md` (update CP-018 status/routing)
- `_bmad-output/implementation-artifacts/deferred-work.md` (only if CP-018 remains blocked or if a follow-up is needed)
- `_bmad-output/implementation-artifacts/cp-018-classify-story-4-3-inbox-exceptions-against-oq3.md` (this story)
- `docs/run_log.md` (append-only evidence)

Conditional deletion only with explicit authorization:

- `docs/inbox/f1-to-platform-story-4-3-response-2026-07-15.md`
- `docs/inbox/platform-to-f1-story-4-3-handoff-2026-07-15.md`

Do not touch for CP-018:

- `docs/inbox/Gmail - 2026 F1 Questions.pdf`
- `src/f1_analytics/analysis/question_catalog.py`
- Any F1 source code, tests, notebooks, or data outputs

### Testing And Validation

There is no automated test suite requirement for this documentation/proof story unless implementation unexpectedly changes code. Validation is evidence-oriented:

- `git status --short` before and after.
- `test -f` checks for both CP-018 markdown paths and the PDF.
- `rg` exact path/basename searches for both CP-018 markdown notes.
- Manifest row completeness check for CP-018 path-level rows.
- `git diff --check` scoped to touched files.
- No-index whitespace checks for untracked new markdown artifacts.
- `docs/run_log.md` append-tail verification.

If the dev agent deletes the two markdown notes after explicit authorization, validation must prove only those two CP-018 markdown paths became absent and that the PDF remains present.

### Git Intelligence

Recent commits at story creation:

- `20bb6f6 docs: record story 4.3 platform exchange`
- `59294ce feat: claim daily pipeline atomic staging`
- `3a84543 Initial baseline commit`

The working tree was already dirty at story creation with uncommitted planning artifacts, cleanup deletions, current F1 questions/backtest source and test files, notebook changes, and `docs/run_log.md` edits. Preserve unrelated changes.

### Latest Technical Information

No external API, package, framework, or version-sensitive implementation detail applies to CP-018. Use local markdown artifacts and shell evidence only; do not add dependencies.

### References

- [Source: `_bmad-output/specs/spec-cleanup-proof/SPEC.md`](../specs/spec-cleanup-proof/SPEC.md) - canonical cleanup-proof contract, constraints, non-goals, and open questions.
- [Source: `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md`](../specs/spec-cleanup-proof/cleanup-proof-ledger.md) - CP-018 retained-exception row and required manifest fields.
- [Source: `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md`](../specs/spec-cleanup-proof/cleanup-proof-manifest.md) - CP-017 precedent for path-level cleanup-proof rows.
- [Source: `_bmad-output/planning-artifacts/research/cleanup-proof-first-principles-draft-2026-07-17.md`](../planning-artifacts/research/cleanup-proof-first-principles-draft-2026-07-17.md) - CP-018 unresolved-case rationale.
- [Source: `_bmad-output/implementation-artifacts/cp-017-split-path-level-cleanup-proof-manifest.md`](cp-017-split-path-level-cleanup-proof-manifest.md) - previous cleanup-proof story and validation/review lessons.
- [Source: `_bmad-output/implementation-artifacts/1-2-delete-zero-dependency-legacy-docs.md`](1-2-delete-zero-dependency-legacy-docs.md) - review correction that restored the two CP-018 files pending OQ3 resolution.
- [Source: `_bmad-output/implementation-artifacts/3-3-decide-future-run-record-contract-before-platform-story-4.4.md`](3-3-decide-future-run-record-contract-before-platform-story-4.4.md) - run-record decision story and remaining deferrals.
- [Source: `_bmad-output/planning-artifacts/decisions/run-record-contract-decision-record.md`](../planning-artifacts/decisions/run-record-contract-decision-record.md) - accepted Axis 1 decision and Axis 2/3 deferrals.
- [Source: `_bmad-output/implementation-artifacts/deferred-work.md`](deferred-work.md) - deferred CP-018/OQ3 and Story 3.3 follow-up blockers.
- [Source: `docs/inbox/f1-to-platform-story-4-3-response-2026-07-15.md`](../../docs/inbox/f1-to-platform-story-4-3-response-2026-07-15.md) - F1 Story 4.3 response retained exception.
- [Source: `docs/inbox/platform-to-f1-story-4-3-handoff-2026-07-15.md`](../../docs/inbox/platform-to-f1-story-4-3-handoff-2026-07-15.md) - platform Story 4.3 handoff retained exception.
- [Source: `PROJECT.md`](../../PROJECT.md) and [Source: `_bmad-output/project-context.md`](../project-context.md) - active local project rules and implementation context.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-07-18: `git status --short` confirmed the working tree was already dirty before CP-018 implementation; unrelated modified/deleted/untracked files were preserved.
- 2026-07-18: `_bmad-output/implementation-artifacts/sprint-status.yaml` existence check returned absent, so story tracking is file-local only.
- 2026-07-18: Full pre-read completed for the CP-018 story, cleanup-proof SPEC, cleanup-proof ledger, and cleanup-proof manifest before classification edits.
- 2026-07-18: Existence checks confirmed both CP-018 markdown notes and `docs/inbox/Gmail - 2026 F1 Questions.pdf` are present.
- 2026-07-18: Read both retained CP-018 inbox notes completely and inspected related Story 4.3, Story 3.3, and Story 4.4 evidence. Sibling `../platform/exchange/` inspection was read-only.
- 2026-07-18: Active-reference searches for both CP-018 exact paths and basenames found no hits in `AGENTS.md`, `PROJECT.md`, `src`, `scripts`, or `notebooks`; hits are source self-references, historical `docs/run_log.md` evidence, BMAD implementation/spec/research artifacts, and deferred-work/cleanup-proof records.
- 2026-07-18: Classification decision: CP-018 is `partially_covered`, not retirement-permitted. Covered facts include F1 Story 4.3 claim commit `59294ce`, exchange-record commit `20bb6f6`, and platform's available Story 4.3 acknowledgment. Blockers remain for durable successor coverage of the inbound Story 4.3 deferred caveats and unresolved run-record-contract follow-ups.
- 2026-07-18: Updated cleanup-proof manifest with CP-018A/CP-018B path-level rows, updated the ledger CP-018 row to point to those rows, and tightened the existing deferred-work blocker with the concrete `partially_covered` reasons.
- 2026-07-18: Conditional deletion gate evaluated false: retirement is not permitted on the evidence, Antonio gave no fresh deletion authorization, both CP-018 markdown notes remain present, and the CP-019 PDF/directory were untouched.
- 2026-07-18: Validation passed. Existence checks confirmed both CP-018 markdown notes and the CP-019 PDF present; active-reference searches found no `AGENTS.md`, `PROJECT.md`, `src`, `scripts`, or `notebooks` hits; scoped `git diff --check` emitted no errors; no-index whitespace checks for touched markdown artifacts returned expected clean-diff code `1`; `PYTHONPATH=src python3 -m unittest discover -s tests` ran 210 tests successfully; `tail -n 120 docs/run_log.md` verified the implementation evidence entry landed at the file tail.
- 2026-07-18: Final completion gate passed: no unchecked task boxes remained, `PYTHONPATH=src python3 -m unittest discover -s tests` again ran 210 tests successfully, scoped `git diff --check` emitted no errors, touched-artifact no-index whitespace checks were clean, and `_bmad-output/implementation-artifacts/sprint-status.yaml` remained absent.
- 2026-07-18: Code-review follow-up resolved nine patch findings across the CP-018 artifacts and run-log evidence. Supplemental validation recorded post-review `git status --short`, sprint-status absence, final retained-source existence checks, CP-018A/CP-018B row completeness/status validation, scoped whitespace validation, and empty workflow `on_complete`.

### Completion Notes List

- Completed CP-018 pre-work scope capture. No source code changed; validation for this step is command-evidence based.
- Built the CP-018 evidence set from local inbox notes, F1 commits `59294ce` and `20bb6f6`, platform's available Story 4.3 acknowledgment, Story 3.3 run-record decision/response, Story 4.4 blocking context, and active-reference searches.
- Decided CP-018 status as `partially_covered`: some facts have durable successors, but the two markdown notes remain present because direct evidence does not prove full successor coverage or deletion authorization.
- Added CP-018 path-level cleanup-proof rows without deleting, moving, or rewriting either retained inbox source note.
- Conditional retirement was not performed. The two CP-018 markdown files, the CP-019 PDF, and `docs/inbox/` remain in place.
- Appended command/result evidence to `docs/run_log.md` and verified the append at the tail.
- No sprint-status sync was possible because `_bmad-output/implementation-artifacts/sprint-status.yaml` is absent.
- Story status set to `review` after all tasks/subtasks were checked and final validation passed.
- Code review found and fixed nine patch findings. Story status set to `done` after review findings were checked off and supplemental validation passed.

### File List

- `_bmad-output/implementation-artifacts/cp-018-classify-story-4-3-inbox-exceptions-against-oq3.md`
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-manifest.md`
- `_bmad-output/specs/spec-cleanup-proof/cleanup-proof-ledger.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `docs/run_log.md`

## Change Log

- 2026-07-18: Story drafted by `bmad-create-story` from cleanup-proof SPEC/ledger CP-018, retained inbox exception files, CP-017 precedent, Story 1.2 restoration evidence, and Story 3.3 run-record decision context. Status set to `ready-for-dev`. Sprint status was not updated because `_bmad-output/implementation-artifacts/sprint-status.yaml` is absent.
- 2026-07-18: Implemented CP-018 classification. Added CP-018A/CP-018B path-level manifest rows, updated the ledger and deferred-work blocker, classified CP-018 as `partially_covered`, left both markdown notes/PDF/directory present, appended validation evidence to `docs/run_log.md`, and kept sprint status file-local because no sprint-status file exists.
- 2026-07-18: Resolved code-review patch findings. Clarified external acknowledgment as staging evidence, fixed replay validation commands, aligned ledger enum wording and future-work guidance, added supplemental run-log replay evidence, checked off all review findings, and moved status to `done`.
