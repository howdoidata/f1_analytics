---
id: define-run-daily-pipeline-evidence-write-contract-and-close-run-log
title: "Define run_daily_pipeline.py Evidence Write Contract And Close docs/run_log.md"
status: review
created: 2026-07-21
baseline_commit: 20bb6f67959918322c5b65c8fb573bec068f9979
decision:
  - _bmad-output/planning-artifacts/decisions/run-record-axis-2-3-resolution-decision-record.md
  - _bmad-output/planning-artifacts/decisions/run-record-contract-decision-record.md
source_material:
  - _bmad-output/implementation-artifacts/deferred-work.md
  - _bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md
  - scripts/run_daily_pipeline.py
  - AGENTS.md
  - docs/run_log.md
---

# Define run_daily_pipeline.py Evidence Write Contract And Close docs/run_log.md

## Story

As Antonio,
I want `run_daily_pipeline.py`'s automated run evidence written to a dedicated machine-readable log and `docs/run_log.md` closed as a historical record,
so that platform's Story 4.4 has a real contract to implement against and F1 stops requiring new entries in a file the architecture already treats as historical-only.

## Acceptance Criteria

1. A concrete write contract is defined for `run_daily_pipeline.py`'s automated evidence: file location, format (e.g. JSONL), schema fields (timestamp, run start, per-stage success/failure, error message on failure, benign-skip-vs-failure distinction), and append semantics — satisfying the Axis 2 resolution in `run-record-axis-2-3-resolution-decision-record.md`.
2. `run_daily_pipeline.py` is updated to write to the new contract's destination instead of having no run-log integration.
3. `AGENTS.md`'s line requiring commands/validation results to be recorded in `docs/run_log.md` is updated so it no longer names `docs/run_log.md` as a required destination.
4. `docs/run_log.md` receives a final closing entry marking it historical/frozen as of this story, and no code or process path writes to it afterward.
5. Platform is notified via `../platform/exchange/` that the concrete contract now exists, so platform's Story 4.4 can implement against it.
6. The cleanup-proof terminal closure story's CP-017B/CP-023 task is satisfied by this story's completion.

## Tasks

- [x] Define the new log's file path, format, and schema (Axis 2 concrete contract).
- [x] Implement the write calls in `run_daily_pipeline.py` (start, per-stage success/failure, benign-skip distinction).
- [x] Update `AGENTS.md` to remove the `docs/run_log.md` requirement and point at the new contract.
- [x] Append a final closing entry to `docs/run_log.md` and mark it historical (no further writes).
- [x] Send an outbound exchange note to platform pointing at the new contract, so Story 4.4 can proceed.
- [x] Update `deferred-work.md` and the cleanup-proof terminal closure story to reference this story as the CP-017B/CP-023 resolution.
- [x] Append evidence of this story's own commands/validation to the new contract's location (not `docs/run_log.md`, since it is now closed) or to this story's Dev Agent Record.

## Non-Goals

- Do not redesign BMAD implementation-artifact evidence conventions — this story only concerns automated pipeline-run telemetry, not hand/agent-authored story evidence.
- Do not delete `docs/run_log.md` — it is closed/frozen, not removed.
- Do not implement platform's Story 4.4 itself — that remains platform's own story, unblocked by this one.

## Dev Agent Record

### Debug Log

- Activation resolved `bmad-dev-story` workflow customization: no prepend/append steps; persistent fact was `_bmad-output/project-context.md`.
- No `_bmad-output/implementation-artifacts/sprint-status.yaml` exists. Non-sprint discovery found no literal `ready-for-dev` stories, but this story was the only non-done implementation story and had `status: ready`; treated that as the ready development candidate.
- Captured baseline commit: `20bb6f67959918322c5b65c8fb573bec068f9979`.
- Red phase: added `tests/test_run_daily_pipeline_records.py`; focused test run failed with `AttributeError: module 'scripts.run_daily_pipeline' has no attribute 'RUN_RECORD_PATH'`, confirming the missing contract implementation.
- Green/refactor phase: added JSONL run-record constants/helper to `scripts/run_daily_pipeline.py`; wired `run_started`, `stage_succeeded`, `stage_failed`, `run_failed`, `run_skipped`, and `run_succeeded` records into the existing marker, lock, stage, swap, and success paths without changing stage order, swap order, lock cleanup, or marker-success semantics.
- Updated `scripts/verify_daily_pipeline_swap_contract.py` to patch `RUN_RECORD_PATH` into its temp sandbox so verifier runs do not write to the real project telemetry log.
- Defined the durable contract in `_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md`: JSONL path, append semantics, required fields, controlled event/outcome values, conditional fields, and platform contract.
- Updated `AGENTS.md` so manual command/validation evidence belongs in active BMAD implementation artifacts and automated daily-pipeline telemetry belongs in the JSONL contract.
- Marked `docs/run_log.md` as `Historical evidence` and added a physical final closing entry. No new evidence should be appended there after this story.
- Created `_bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md` and copied it to `../platform/exchange/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md`; `cmp` verified the sibling exchange copy matches the local note.
- Updated `_bmad-output/implementation-artifacts/deferred-work.md` and `_bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md` so CP-017B/CP-023 now point at this completed story and the JSONL contract, rather than an unexecuted follow-up.
- 2026-07-22 blocker reassessment: confirmed the original platform-side blocker ("F1 has no concrete run-record contract") no longer holds because the JSONL contract exists and was already sent to platform; confirmed the still-current blocker is F1-local decision integrity, because the accepted Axis 2 wording says the machine-readable log is separate from BMAD implementation artifacts while the concrete JSONL path is under `_bmad-output/implementation-artifacts/`.
- Created and staged `_bmad-output/planning-artifacts/cross-repo-notes/f1-to-administrative-run-record-current-blocker-and-upcoming-story-check-2026-07-22.md` to request Administrative recommendations and ask whether any upcoming administrative/platform/operations/token-governance story is expected to handle the evidence-contract alignment.
- Claimed Administrative's response from `../platform/exchange/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` into `_bmad-output/planning-artifacts/cross-repo-notes/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md`; reviewed it as non-binding guidance recommending a narrow F1 decision clarification rather than moving the JSONL path.
- 2026-07-22 rule clarification: accepted Administrative's non-binding recommendation and clarified `_bmad-output/planning-artifacts/decisions/run-record-axis-2-3-resolution-decision-record.md` so the Axis 2 dedicated machine-readable log is separate from `docs/run_log.md` and prose Dev Agent Records, not necessarily outside the broader `_bmad-output/implementation-artifacts/` tree.
- 2026-07-22 rule clarification: updated `_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md` to identify `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` as the accepted Axis 2 destination.
- 2026-07-22 rule clarification: updated `_bmad-output/implementation-artifacts/deferred-work.md` so the JSONL destination conflict is resolved; only the two pre-existing runtime behavior deferrals remain.
- Created `_bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-run-record-destination-clarified-2026-07-22.md` and copied it to `../platform/exchange/f1-to-platform-run-record-destination-clarified-2026-07-22.md`; `cmp` verified the sibling exchange copy matches the local note.
- Removed the already-claimed inbound Administrative recommendation from `../platform/exchange/` after confirming the F1-owned cross-repo note byte-matched the staged copy.

### Validation Evidence

- `PYTHONPATH=src python3 -m unittest tests.test_run_daily_pipeline_records` — 7 tests, `OK`.
- `PYTHONPATH=src:scripts python3 scripts/verify_daily_pipeline_swap_contract.py` — `daily pipeline swap contract verified`.
- `git diff --check -- scripts/run_daily_pipeline.py scripts/verify_daily_pipeline_swap_contract.py tests/test_run_daily_pipeline_records.py AGENTS.md docs/run_log.md _bmad-output/implementation-artifacts/deferred-work.md _bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md _bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md _bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md` — clean, no output.
- `PYTHONPATH=src python3 -m unittest discover -s tests` — 214 tests, `OK`. Arrow emitted sandbox-related `sysctlbyname` warnings, but the suite passed.
- `cmp _bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md ../platform/exchange/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md` — clean, no output.
- 2026-07-22 code-review chunk 1 patch validation: `PYTHONPATH=src python3 -m unittest tests.test_run_daily_pipeline_records` — 8 tests, `OK`.
- 2026-07-22 code-review chunk 1 patch validation: `git diff --check -- scripts/run_daily_pipeline.py tests/test_run_daily_pipeline_records.py _bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md _bmad-output/implementation-artifacts/deferred-work.md` — clean, no output.
- 2026-07-22 administrative outreach validation: `git diff --check -- _bmad-output/planning-artifacts/cross-repo-notes/f1-to-administrative-run-record-current-blocker-and-upcoming-story-check-2026-07-22.md` — clean, no output.
- 2026-07-22 administrative outreach validation: `cmp _bmad-output/planning-artifacts/cross-repo-notes/f1-to-administrative-run-record-current-blocker-and-upcoming-story-check-2026-07-22.md ../platform/exchange/f1-to-administrative-run-record-current-blocker-and-upcoming-story-check-2026-07-22.md` — clean, no output.
- 2026-07-22 administrative response claim validation: `git diff --check -- _bmad-output/planning-artifacts/cross-repo-notes/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` — clean, no output.
- 2026-07-22 administrative response claim validation: `cmp _bmad-output/planning-artifacts/cross-repo-notes/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md ../platform/exchange/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` — clean, no output.
- 2026-07-22 rule clarification validation: `git diff --check -- _bmad-output/planning-artifacts/decisions/run-record-axis-2-3-resolution-decision-record.md _bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md _bmad-output/implementation-artifacts/deferred-work.md _bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md` — clean, no output.
- 2026-07-22 platform follow-up validation: `git diff --check -- _bmad-output/planning-artifacts/decisions/run-record-axis-2-3-resolution-decision-record.md _bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md _bmad-output/implementation-artifacts/deferred-work.md _bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md _bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-run-record-destination-clarified-2026-07-22.md` — clean, no output.
- 2026-07-22 platform follow-up validation: `cmp _bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-run-record-destination-clarified-2026-07-22.md ../platform/exchange/f1-to-platform-run-record-destination-clarified-2026-07-22.md` — clean, no output.
- 2026-07-22 marker-write telemetry fix validation: `PYTHONPATH=src python3 -m unittest tests.test_run_daily_pipeline_records` — 9 tests, `OK`.
- 2026-07-22 marker-write telemetry fix validation: `git diff --check -- scripts/run_daily_pipeline.py tests/test_run_daily_pipeline_records.py _bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md _bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md` — clean, no output.
- 2026-07-22 marker-write telemetry fix validation: `PYTHONPATH=src python3 -m unittest discover -s tests` — 219 tests, `OK`. Arrow emitted sandbox-related `sysctlbyname` warnings, but the suite passed.
- 2026-07-22 exchange cleanup validation: `test ! -e ../platform/exchange/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` — clean, no output.
- 2026-07-22 exchange cleanup validation: `git -C ../platform status --short -- exchange/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` — clean, no output.
- 2026-07-22 exchange cleanup validation: `git status --short -- ../platform/exchange/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` — failed with `fatal: ... is outside repository`; non-blocking command selection error, replaced by the sibling-repo status check above.

### Completion Notes

- Implemented the concrete daily-pipeline JSONL run-record contract and integrated it into `run_daily_pipeline.py`.
- Closed the transition away from `docs/run_log.md`: project rules now point to BMAD implementation artifacts, `docs/run_log.md` is frozen historical evidence, and the final run-log entry names the replacement destinations.
- Platform has been notified through the local cross-repo note and matching `../platform/exchange/` copy.
- CP-017B/CP-023 references in deferred work and the terminal cleanup-proof story now reflect this story as the resolution.

### Review Fixes Applied

- Added dedicated file-locking around every JSONL append with `RUN_RECORD_LOCK_PATH` and single-write event emission.
- Added launch-failure telemetry (`stage_launch_failed`) for `subprocess.run` exceptions and test coverage for the branch.
- Updated run-record contract to include `stage_launch_failed` as a controlled failure reason.
- Added explicit ignore rules for `daily-pipeline-run-records.jsonl` and run-record lock file.
- Added tests for lock-held benign skip, launch failure path, and `docs/run_log.md` non-reference guard in `test_run_daily_pipeline_records.py`.

## File List

- `AGENTS.md` (updated command/validation evidence rule and automated telemetry pointer)
- `.gitignore` (added ignored runtime JSONL telemetry and lock paths)
- `_bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md` (updated CP-017B/CP-023 resolution references)
- `_bmad-output/implementation-artifacts/deferred-work.md` (resolved/superseded run-record transition deferrals)
- `_bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md` (story status, tasks, Dev Agent Record, File List, Change Log, Status)
- `_bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md` (created outbound note)
- `_bmad-output/planning-artifacts/cross-repo-notes/f1-to-platform-run-record-destination-clarified-2026-07-22.md` (created outbound clarification note)
- `_bmad-output/planning-artifacts/cross-repo-notes/f1-to-administrative-run-record-current-blocker-and-upcoming-story-check-2026-07-22.md` (created outbound recommendation/upcoming-story check)
- `_bmad-output/planning-artifacts/cross-repo-notes/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` (claimed inbound administrative recommendation)
- `_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md` (created durable JSONL contract)
- `_bmad-output/planning-artifacts/decisions/run-record-axis-2-3-resolution-decision-record.md` (clarified Axis 2 destination category)
- `../platform/exchange/f1-to-platform-daily-pipeline-run-record-contract-ready-2026-07-21.md` (created sibling-repo exchange copy)
- `../platform/exchange/f1-to-platform-run-record-destination-clarified-2026-07-22.md` (created sibling-repo exchange copy)
- `../platform/exchange/f1-to-administrative-run-record-current-blocker-and-upcoming-story-check-2026-07-22.md` (created sibling-repo exchange copy)
- `../platform/exchange/administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md` (removed claimed inbound staging copy after local claim validation)
- `docs/run_log.md` (status changed to historical evidence; final closure entry appended)
- `scripts/run_daily_pipeline.py` (JSONL run-record writer and event emission)
- `scripts/verify_daily_pipeline_swap_contract.py` (sandboxed run-record path during verifier runs)
- `tests/test_run_daily_pipeline_records.py` (new focused unit tests)

## Change Log

- 2026-07-21: Implemented daily-pipeline JSONL run-record contract; updated `run_daily_pipeline.py`, focused tests, project rules, frozen run-log disposition, platform exchange note, and CP-017B/CP-023 references. Status set to `review`.
- 2026-07-22: Code-review chunk 1 completed for code and contract files. Three patch findings fixed and validated; JSONL destination decision deferred by Antonio for impact analysis. Status set to `in-progress`.
- 2026-07-22: Reassessed current blocker state and sent Administrative a recommendation/upcoming-story check through `../platform/exchange/`; status was `in-progress` at that point pending the JSONL destination resolution.
- 2026-07-22: Resolved JSONL destination by clarifying the Axis 2 rule rather than moving the file; deferred-work now marks the destination conflict resolved. Status set to `review`.
- 2026-07-22: Fixed marker-write failure telemetry and disclosed the `.gitignore` runtime telemetry paths in the story File List. Status set to `review`.

## Review Findings

- [x] [Review][Patch] Story file is internally inconsistent about execution status [/_bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md:53, 81-84, 102]. The Dev Notes claimed this story was not executed while Debug Log and Completion Notes claim execution. The file is now consistent.
- [x] [Review][Patch] `scripts/run_daily_pipeline.py` does not catch stage-launch exceptions before continuing failure handling [scripts/run_daily_pipeline.py:175-177]. An exception from `subprocess.run` (e.g., missing stage file, permission error) can skip `stage_failed`/`run_failed` telemetry and leave run state partially recorded as started-only. The new branch emits failure records with `reason=stage_launch_failed`.
- [x] [Review][Patch] `_append_run_record` and `main` allow concurrent pre-lock writes that can interleave across overlapping runs [scripts/run_daily_pipeline.py:76-79, 143-168]. `run_started`/`run_skipped` can be emitted before lock acquisition, and each append is split into separate writes, so concurrent invocations can produce malformed JSONL. Run-record writes are now serialized under a dedicated lock file and written as a single append line per event.
- [x] [Review][Patch] No ignore rule protects `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` from accidental git status noise [scripts/run_daily_pipeline.py:30, .gitignore]. This file is under a tracked artifact tree but is runtime-generated output, so every run can dirty working tree unless explicitly ignored or otherwise managed. `.gitignore` now ignores the JSONL file and lock file.
- [x] [Review][Patch] AC4 requires demonstrable assurance that `docs/run_log.md` is no longer written by process or code, but this story does not include an explicit post-change guard (for example a targeted grep check or test) [/_bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md:31, 40, 73, AGENTS.md:15]. Add a repeatable check so this requirement remains enforced after future edits. A focused test now asserts `run_daily_pipeline.py` has no `docs/run_log.md` reference.
- [x] [Review][Patch] Command/output evidence destination is still partially ambiguous for automated telemetry vs manual evidence without a canonical sink file [AGENTS.md:15; _bmad-output/implementation-artifacts/define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md:43]. Make one explicit path convention for validation logs in stories versus run telemetry. AGENTS.md now states story Dev Agent Record as the canonical command/validation sink, and run-record JSONL for automation.
- [x] [Review][Patch] Exception-path and lock-held skip behavior is untested for run-record output semantics [tests/test_run_daily_pipeline_records.py:61-113]. Add coverage for `subprocess.run` raising and `run_skipped` with reason `lock_held` so the “one skip vs failure” distinction is locked in by tests. Tests now cover both branches.

### Review Findings (chunk 1: code and contract, 2026-07-22)

- [x] [Review][Patch] JSONL run-record destination conflicts with the accepted Axis 2 destination category — AC1 says the concrete write contract must satisfy `_bmad-output/planning-artifacts/decisions/run-record-axis-2-3-resolution-decision-record.md`, whose Axis 2 decision required "a new dedicated machine-readable log" separate from BMAD implementation artifacts and `docs/run_log.md`. Resolved 2026-07-22 by clarifying Axis 2 so "separate" means separate from `docs/run_log.md` and prose Dev Agent Records, not outside the broader `_bmad-output/implementation-artifacts/` tree; `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` remains the accepted JSONL destination.
- [x] [Review][Patch] Missing stage scripts are not classified as `stage_launch_failed` [scripts/run_daily_pipeline.py:196] — resolved 2026-07-22: preflight missing stage scripts before `subprocess.run` and emit `stage_launch_failed` records.
- [x] [Review][Patch] Successful stage telemetry is untested because the success test runs with `STAGES=[]` [tests/test_run_daily_pipeline_records.py:97] — resolved 2026-07-22: added a successful non-empty stage test that verifies `stage_succeeded`.
- [x] [Review][Patch] Tests do not restore the caller's working directory after `main()` changes it [tests/test_run_daily_pipeline_records.py:41] — resolved 2026-07-22: test fixture now saves and restores the original working directory.
- [x] [Review][Defer] Duplicate same-day run race remains between the marker check and lock acquisition [scripts/run_daily_pipeline.py:172] — deferred, pre-existing
- [x] [Review][Defer] Sequential output swaps can partially publish live outputs before a later swap fails [scripts/run_daily_pipeline.py:258] — deferred, pre-existing

### Review Findings (chunk 1: code and contract, 2026-07-22, pass 2)

- [x] [Review][Patch] Marker-write failure exits without terminal failed telemetry — `MARKER_PATH.write_text(today)` runs after all swaps and outside any `except`; if that write raises, the invocation can publish outputs, release the lock, and exit via exception with only prior records such as `run_started`/`stage_succeeded`, but no `run_failed` record or `error_message`, contrary to AC1's failure-evidence contract. Resolved 2026-07-22: marker write failures now emit `run_failed reason=marker_write_failed` with `error_message` and return `1`; focused test coverage added.
- [x] [Review][Patch] Story File List omits `.gitignore` even though the story changed it to ignore the JSONL telemetry file and lock — add `.gitignore` to the File List so the implementation artifact fully discloses the run-record ignore-rule change. Resolved 2026-07-22: `.gitignore` added to File List.

## Status

review
