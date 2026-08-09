---
date: 2026-08-08
trigger: user-requested epic/story audit — prose review across all epics, reassessment of old stories, reconfirmation of the FastF1 pivot point
mode: incremental
scope: minor
status: approved, implemented
---

# Sprint Change Proposal — 2026-08-08 (2)

## 1. Issue Summary

Antonio requested a broad correct-course pass, independent of any single failing story: review every epic's prose for quality, reassess old/leftover story artifacts, and reconfirm that the FastF1 dataset still has a real pivot/decision gate now that Epic 1 is nearly closed and Epic 2 is about to start depending on it directly.

Three sub-investigations, each scoped with Antonio before executing:
- **Prose**: full editorial pass over `epics.md` (all 4 epics + Overview + FR Coverage Map).
- **Old stories**: 6 leftover story files under `implementation-artifacts/` predate the 2026-08-01 data-loss rebuild and use a numbering scheme (Epic 6, Epic 7) that no longer exists in the current 4-epic plan; two even collide in number (not slug) with current Stories 1.1 and 1.4 while describing unrelated work.
- **FastF1 pivot**: Story 1.2 (FastF1 Adoption Spike) already serves as the original go/no-go gate and is done, but its own decision record left an open follow-up condition — Barcelona's 2026 FastF1 session hadn't occurred yet (calendar-resolved to 2026-09-13) — that nothing in `epics.md` currently re-surfaces at the story (2.4) that actually needs Barcelona data for Q04.

## 2. Impact Analysis

**Epic impact:** None structurally — no epic added, removed, resequenced, or redefined. One story (2.4) gains a new acceptance-criteria clause.

**Artifact conflicts:**
- PRD: none.
- Architecture: none — the new Story 2.4 clause cites existing AD-12/AD-13, doesn't amend them.
- UX: none.
- `epics.md`: 12 prose defects fixed (comma splice, an invented alternate name for "Standing Constraints," a plural/singular mismatch, an unexplained "lost PDF" reference, a beneficiary-rule violation on Story 2.6, live-diagnostic-session prose patched into Story 1.8's prescriptive AC text, an undefined `DW-32` citation, a capitalization inconsistency on "Prediction Inputs," a hyphenation mismatch between Story 3.3 and FR-17, an undefined "Track-2" term, "channel declaration" vs. "channel authority" packet naming drift, and "eleven" vs. "11" within one story).
- `implementation-artifacts/`: 6 pre-rebuild files (old Epic 6/7 numbering, zero current references, confirmed dead) moved to a new `pre-rebuild-archive/` subfolder with a README explaining provenance; one live cross-reference to the moved `1-1-confirm-deletion-authorization...` file (in the current Story 1.3 implementation artifact) updated to point at the new location.
- `sprint-status.yaml`: no change needed — no epic/story was added, removed, or renumbered (checklist item 6.4 confirmed N/A).

**Technical impact:** None — this proposal is documentation-only. No code changed.

## 3. Recommended Approach

**Direct Adjustment** (Path Forward Option 1) — low effort, low risk, additive/corrective only. No rollback needed (nothing shipped was broken), no PRD/MVP scope change.

On the FastF1 pivot specifically: Antonio confirmed the gate should stay live at the point of actual consumption (Story 2.4, Epic 2) rather than requiring a new standalone story or living only inside the 1.2 decision record's prose, where a future story-picker could easily miss it. This is consistent with the project's own AD-16 fail-early doctrine — the check belongs at the unit that would otherwise silently trust stale/absent data, not at a point already closed and forgotten.

**Alternatives considered:**
- *Leave the Barcelona condition only in the 1.2 decision record* — rejected by Antonio; too easy to miss when Story 2.4 is eventually picked up, and Q04 has already produced one silent-wrong-answer defect via the old Jolpica pagination bug (`7-6-reconcile-q04...`, now archived).
- *New standalone Epic-2 story for the re-verification* — not proposed; the check is a precondition of Story 2.4's own extraction, not independent deliverable work, so it belongs as an AC on that story rather than a new one.

## 4. Detailed Change Proposals

### `epics.md` — 12 prose fixes (see Section 2 for the full list; each applied verbatim, no semantic scope change)

### `epics.md` — Story 2.4 (Epic 2), new acceptance criteria

OLD:
```
**And** extraction never silently substitutes a result-level field for lap-level timing without recording which path produced the value.

**Verification:** offline tests: tie case, missing-laps case, personal-vs-race distinction fixture. Governed by: AD-6, AD-8, AD-13, AD-16.
```

NEW:
```
**And** extraction never silently substitutes a result-level field for lap-level timing without recording which path produced the value
**And** before extracting Q04, Barcelona's leg of the 1.2 spike decision record is re-verified live — if the 2026-09-13 session still hasn't occurred (or `raw_fastf1_laps` otherwise carries no real Barcelona rows), Q04 renders `source_blocked` naming the future date, never a stale cache or partial substitute passed off as complete (AD-13's "never a shorter table"; the Q04 failure class AD-12 exists to prevent, per the pre-rebuild Jolpica-pagination lesson it was written from).

**Verification:** offline tests: tie case, missing-laps case, personal-vs-race distinction fixture, Barcelona-not-yet-occurred fixture asserting `source_blocked` over a stale/partial cache. Governed by: AD-6, AD-8, AD-12, AD-13, AD-16.
```

Rationale: closes the gap between the 1.2 decision record's open follow-up condition and the story that actually consumes Barcelona data, without inventing new architecture — AD-12 and AD-13 already cover exactly this failure class.

### `implementation-artifacts/` — archival

- Created `pre-rebuild-archive/` with a `README.md` explaining what's there and why.
- Moved (git mv, history preserved): `1-1-confirm-deletion-authorization-and-evidence-path.md`, `1-4-define-analysis-mode-and-feature-snapshot-boundary.md`, `2-2-extract-results-based-williams-finishing-answers.md`, `6-3-render-report-summary-across-generated-outputs.md`, `6-7-render-portfolio-summary-for-ready-bundles.md`, `7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md`.
- Updated one stale in-folder reference in `1-3-salvage-the-platform-snapshot-under-the-merge-rules.md` to point at the new location.
- Left `project-state-reconstruction-2026-08-06.md` untouched — it's a dated historical snapshot correctly citing where those files were on 2026-08-06; moving them later doesn't retroactively invalidate that citation.

### Epic 1 code-vs-documentation gaps (reviewed, no `epics.md` change required)

Cross-referenced all 8 Epic 1 stories' implementation artifacts against `epics.md` and `deferred-work.md`. Findings are almost entirely already tracked in `deferred-work.md` at appropriate severity (e.g., a residual cross-run race-drop gap in `pull_fastf1_data.py` not fully covered by the 2026-08-08 regression guard; three FastF1 reconciliation decision records now on record: source adoption, constructor-name alias, driver-code override — the last of which caught a real defect, 2026 laps landing under retired drivers' historical IDs, before it shipped). Story 1.8's two "shipped 2026-08-08" AC clauses are correctly still open, not contradictions — 1.8 is `review`, not `done`. No action needed beyond the prose fix already applied (Section 2).

## 5. Implementation Handoff

**Scope classification: Minor.** Confined to `epics.md` prose/AC edits and an `implementation-artifacts/` file reorganization — no code, no PRD/architecture change, no `sprint-status.yaml` change.

**Handoff:** Developer agent, direct implementation — already executed in this session:
- All 12 prose fixes applied to `epics.md`.
- Story 2.4's Barcelona/Q04 gate AC added to `epics.md`.
- 6 dead pre-rebuild files archived with a README; one stale cross-reference fixed.

**Next steps for whoever picks up Story 2.4:** the new Barcelona re-verification AC needs a live check (re-running the 1.2 spike's Barcelona leg, or an equivalent freshness check against `raw_fastf1_laps`) before Q04 extraction proceeds — size the story's dev pass accordingly; as of this proposal Barcelona's FastF1 session has not yet occurred.

**Success criteria:** met — `epics.md` prose is clean against the doc's own established voice, the FastF1 pivot point is now visible at the exact story that depends on it, and the implementation-artifacts folder no longer mixes two unrelated eras of the project under overlapping numbers.
