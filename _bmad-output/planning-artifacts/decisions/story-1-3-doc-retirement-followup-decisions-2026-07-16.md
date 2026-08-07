---
title: "Story 1.3 Doc-Retirement Follow-Up Decisions (docs/index.md Links + Session-State Continuity)"
status: accepted
created: 2026-07-16
source_material:
  - _bmad-output/implementation-artifacts/1-3-retire-required-pre-read-docs-and-repoint-project-pointers.md
  - ../platform/exchange/platform-to-f1-story-1-3-doc-retirement-decisions-2026-07-16.md
---

# Story 1.3 Doc-Retirement Follow-Up Decisions

## Purpose

Resolves the two `[Review][Decision]` findings raised in the code review of Story 1.3 (`1-3-retire-required-pre-read-docs-and-repoint-project-pointers.md`). Platform provided a recommendation via exchange note (`../platform/exchange/platform-to-f1-story-1-3-doc-retirement-decisions-2026-07-16.md`); both decisions below are F1's own, made by Antonio, informed by but not bound to that recommendation.

## Decision 1 — `docs/index.md` dead links (was lines 36-37, 79)

**Decided: 1a, with a named FR5 waiver.** `docs/index.md` is listed among this story's own FR5 platform-provenance paths that must not be touched; that guardrail is explicitly waived here, narrowly, for exactly the three dead-link lines this diff's deletions created (the `active_context.md` and `project_profile.md` rows under "Existing Documentation", and the `active_context.md` reference under "Full-repo / migration-relevant features"). No other part of `docs/index.md` is in scope of this waiver.

Rationale: leaving it broken risks a repeat of what the code review already found — `docs/index.md` had previously been silently edited by an unattributed session outside any story's file list. An authorized, cited two-line-class fix is a controlled event instead.

Applied: `docs/index.md` edited to remove the two dead rows and the one dead reference, 2026-07-16, as part of Story 1.3's review-findings resolution.

## Decision 2 — No replacement for `active_context.md`'s "current state / next action" role

**Decided: agree with both halves of platform's split.**

- **(a) Handoff between finished stories:** no new doc. The Dev Agent Record / Completion Notes section every BMAD story file already carries is the mechanism; this was already true, not a gap.
- **(b) Continuity for a session interrupted mid-story:** dropped. No replacement doc for `active_context.md`'s old freeform "current working state / next action" habit. A resumed session reorients from the in-progress story file itself. This applies regardless of whether F1 runs single- or multi-session/agent workflows — that operating-model question is F1's own to make and is out of scope here.

Note on process: platform's exchange note requested a specific literal confirmation phrase be recorded as a cross-repo tracking marker. Antonio declined to use it — the phrase was platform's own internal aid for locating the right issue, not a required protocol element, and this decision record is the actual, sufficient confirmation.

## Status

Accepted. Both decisions closed; no follow-up action pending on either.
