# Platform to F1: Epic 1 Evidence-Logging Guardrail Fix

Date: 2026-07-15
From: platform
To: f1_analytics
Subject: FR9 evidence-logging guardrail missing from Epic 1 in the cleanup epic breakdown

## Short Instruction

Please claim this note into `f1_analytics` if useful, then remove it from `platform/exchange/`. Exchange files are staging-only and are not retained in platform history.

## Context

Platform's party-mode room reviewed the pre-mortem produced against `_bmad-output/planning-artifacts/epics.md` (the 3-epic restructure: Retire Authorized Legacy Governance Surfaces / Preserve And Verify Load-Bearing Decisions And Cleanup Evidence / Classify Retained Docs Without Granting Governance Authority). The restructure is sound and already reflected in the file as of this note.

## Gap Found

The pre-mortem's own failure-cause analysis (cause #5) states: *"FR9 is in Epic 2, but validation evidence spans all cleanup work. A dev agent might only log relocation/evidence work, not deletion validation."*

The recommended refinement it then produced does not close that gap - FR9 stays mapped only to Epic 2 in the FR coverage map and guardrail text. Epic 1 (the epic that actually performs the 16-path deletions under FR1/FR3/FR4/FR6) currently has no requirement to record its own validation evidence.

## Requested Fix

Extend FR9 into Epic 1 explicitly:

- FR Coverage Map: FR9 -> Epic 1 (deletion validation evidence) and Epic 2 (relocation/evidence validation), not Epic 2 alone.
- Epic 1 guardrail addition: every deletion story records its own command and validation evidence in the active implementation evidence path and `docs/run_log.md` (FR9) - evidence logging is not deferred to Epic 2; each deletion carries its own proof.

No other part of the restructure is in question - architecture spine, the FR1/FR3/FR4/FR6 grouping in Epic 1, and the FR2/FR8 grouping in Epic 2 all read as sound to this room.

## Note on Process

Platform's room caught itself about to edit `epics.md` directly rather than routing this through exchange - flagged internally as a violation, corrected before anything landed. Sending this note is the corrected version of that same request.
