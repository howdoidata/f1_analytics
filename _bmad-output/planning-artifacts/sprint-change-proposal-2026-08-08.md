---
date: 2026-08-08
trigger: live traceability check of Story 1.7 + accumulated deferred-work review
mode: incremental
scope: minor
status: approved, implemented
---

# Sprint Change Proposal — 2026-08-08

## 1. Issue Summary

A live traceability check run immediately after Story 1.7 (2026-08-08, uncommitted at the time) found `combined_driver_standings_by_round.race_points` disagrees with raw `results.points` for 40 rows — all 1950s shared-drive entries with duplicate result rows per driver/season/round. This prompted a broader review of `deferred-work.md`, which surfaced a related, more consequential pattern already on record but not yet "tied back" into any story's acceptance criteria:

- Story 1.6's own review log had already flagged that `write_dataframe`'s full-table `CREATE OR REPLACE` write can **regress** a live-fetched table — a later run landing less data than an earlier run silently overwrites the good prior data — and explicitly deferred it "for a Story 1.7/1.8 follow-up." Story 1.7 inherited the same pattern (`raw_jolpica_results`) without resolving it.
- The regression risk is not Jolpica-specific: `raw_fastf1_laps`, `raw_fastf1_stints`, and `raw_fastf1_weather` (Story 1.6) share the identical write pattern and feed Epic 2's Story 2.4 (Melbourne/Barcelona lap facts) and Story 2.5 (British GP stints) directly — both 2026 target races.
- None of this was reflected in Story 1.8 (Advisory Build Validation, still backlog) or in any Epic 2 story's acceptance criteria — the risk was recorded but not connected to the stories that would actually build on top of the affected data.

User framing: stories are being planned against systems/data that had known staleness and traceability issues; those issues needed to be synced into the story plan before the dependent stories get built.

## 2. Impact Analysis

**Epic impact:** None. No epic required modification, addition, removal, or resequencing. Both affected stories (1.8, 2.3/2.4/2.5) were still `backlog` — no rework of shipped code from a planning change.

**Artifact conflicts:**
- PRD: none. MVP scope (5 target 2026 questions) is unaffected — confirmed neither of the two genuinely-undecided data-quality items (ranking convention, `combined_results.time` format) is read by any of the 5 target questions.
- Architecture: none required — AR-11's advisory validation module and AD-4's write-pattern rules already anticipate this class of check; the write-layer fix (see below) stays inside AD-4's adopted "idempotent CREATE OR REPLACE sync" contract rather than amending it.
- UX: none.
- Testing strategy: extended — new tests added for the write-regression guard (see Section 4).

**Technical impact — reclassified mid-proposal:** initial impact analysis proposed advisory-only detection (log the regression, gate downstream extraction on the flag). Investigation into whether the underlying regression could be *prevented* rather than merely *detected* (user-directed) found it could, without violating AD-4 or breaking the existing `write_dataframe` contract test. This was implemented and committed as code (`2d6d24b`) before the proposal was finalized, which narrowed the remaining story-plan changes considerably.

## 3. Recommended Approach

**Direct Adjustment** (Path Forward Option 1) — low effort, low risk, additive-only. No rollback (nothing already-built needed reverting), no MVP/PRD scope change.

Two parts, executed in order:

1. **Code fix (implemented, not just planned):** `write_dataframe()` gained an opt-in `refuse_regression` guard — a write that would shrink an already-landed table below its current row count is refused (`WriteRegressionError`) instead of silently replacing good data with a degraded fetch's partial/empty result. Default behavior is unchanged (existing callers, existing test, unaffected). Wired into all 4 live-fetched raw tables: `raw_jolpica_results` (`build_combined_dataset.py` — on refusal, re-reads the preserved table back into memory so `combined_results`/standings compute from last-known-good data rather than degrading to zero) and `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather` (`pull_fastf1_data.py`). Kaggle-sourced tables were deliberately excluded — confirmed via `docs/kaggle-raw-data-is-static.md` that they read static local CSVs, not a live fetch, so this regression class cannot occur there.

   This is a genuine prevention fix, not advisory detection: the previously-landed data is what's actually used going forward, satisfying the explicit ask to "keep existing assets that may serve purpose in future" literally, not just log around the problem.

2. **Story-plan sync (epics.md, backlog stories only):**
   - **Story 1.8** gains two acceptance-criteria additions: (a) every refusal from the new write guard is logged to `validation_results` as a `regression_refused` finding (audit visibility into a guard that already prevented the bad write — AR-11's "trust recorded, not assumed" doctrine), and (b) a standings-reconciliation check logging `race_points_mismatch` findings for the 40-row 1950s defect class found today.
   - **Story 2.3/2.4/2.5**: no changes. An earlier draft of this proposal added "consult `validation_results`, extract as `source_blocked` on an open finding" clauses to these stories — dropped once the write-layer fix shipped, since the data these stories read can no longer silently regress. Keeping them would have been validation for a scenario that can no longer occur.
   - **`deferred-work.md`**: forward-pointer annotations added to the two items that remain genuinely open (dense-vs-standard ranking convention; `combined_results.time` format drift) confirming neither is read by any of Epic 2/3's five target questions today, plus a `resolution:` note on the new 40-row entry pointing at Story 1.8's `race_points_mismatch` check.

**Alternatives considered:**
- *Rollback* (Option 2): not viable/not needed — nothing shipped was broken; Story 1.7 stands as designed.
- *PRD MVP review* (Option 3): not needed — confirmed no target question depends on the two items that stay deferred.

## 4. Detailed Change Proposals

### Code (implemented and committed)

| File | Change |
|---|---|
| `src/f1_analytics/database/duckdb_io.py` | Added `WriteRegressionError` + `refuse_regression: bool = False` param on `write_dataframe()`; refuses a shrinking write against an existing table, always allows a table's first write (including empty). |
| `scripts/build_combined_dataset.py` | `raw_jolpica_results` write now guarded; on refusal, re-reads the table so `combined_results`/standings use last-known-good data this run. |
| `scripts/pull_fastf1_data.py` | New `write_table_unless_regressed()` helper; used for `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather`. |
| `tests/test_duckdb_io.py` | 3 new tests: refuses a shrinking write, allows an empty first write, allows growth/equal counts. |
| `tests/test_build_combined_dataset.py` | New test: a degraded second run reuses the first run's 7-row Jolpica data instead of collapsing to 1 row. |
| `tests/test_pull_fastf1_data.py` | New test: a later run landing fewer races doesn't shrink `raw_fastf1_laps`. |

Full suite: 116/116 passing (111 pre-existing + 5 new). Commit `2d6d24b`.

### Story 1.8 — `_bmad-output/planning-artifacts/epics.md`

OLD:
```
**Then** null-rate checks (...) and referential-integrity checks (...) run and log one row per check per build to `validation_results`
**And** `source_registry` and `source_load_log` record every documented source and loaded table (...)
**And** `validation/` reads only via `database/` and is imported by scripts, never by `analysis/`.

**Verification:** offline test seeds a violation into a fixture table and asserts the logged failure row plus a zero exit code. Governed by: AD-4, AD-8, AR-11.
```

NEW: adds a `regression_refused` logging AC and a `race_points_mismatch` reconciliation AC (full text applied to epics.md; see diff). Verification line extended to cover both new checks via fixtures.

### `deferred-work.md`

- Story 1.7 section: `raw_jolpica_results` regression entry marked resolved with an `update:` note citing commit `2d6d24b` and the proving tests.
- Story 1.5 section (ranking convention) and Story 1.7 section (time format): forward-pointer notes confirming neither blocks Epic 2/3's five target questions today.
- New 40-row entry: `resolution:` note pointing at Story 1.8's forthcoming `race_points_mismatch` check.

## 5. Implementation Handoff

**Scope classification: Minor.** Confined to (a) code already implemented, tested, and committed in this session, and (b) acceptance-criteria text on one still-backlog story plus ledger annotations — no epic restructuring, no PRD/architecture change, no `sprint-status.yaml` update needed (no epics/stories added, removed, or renumbered).

**Handoff:** Developer agent, direct implementation — already executed in this session:
- Code fix: implemented, tested (116/116 green), committed (`2d6d24b`).
- `epics.md` Story 1.8: updated.
- `deferred-work.md`: annotated.

**Next steps for whoever picks up Story 1.8:** the `regression_refused` and `race_points_mismatch` checks are net-new scope on top of 1.8's existing null-rate/referential-integrity checks — size the story accordingly when it's pulled off backlog. No other epic requires action from this proposal.

**Success criteria:** met — full test suite green, `epics.md` and `deferred-work.md` reflect the current, accurate state of known data-quality risk vs. what's actually been resolved in code.
