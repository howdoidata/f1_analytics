---
title: "Project State Reconstruction — 2026-08-06"
status: draft — reconstructed from surviving artifacts after the 2026-08-01 data loss
created: 2026-08-06
purpose: >
  Single consolidated statement of where f1_analytics actually stands. The BMAD
  phases never closed out cleanly and the canonical state artifacts (epics.md,
  sprint-status.yaml, deferred-work.md, project-context.md, both architecture
  spines) are in the unrecoverable 207, so state was scattered across surviving
  story files, decision records, cross-repo notes, the git reflog, and the last
  commit message. This document reassembles it.
source_material:
  - .git/logs/HEAD (38 reflog entries; the only surviving source of epic titles)
  - _bmad-output/planning-artifacts/decisions/repository-damage-and-recovery-options-2026-08-01.md
  - _bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md (status: final)
  - _bmad-output/implementation-artifacts/6-7-render-portfolio-summary-for-ready-bundles.md
  - _bmad-output/implementation-artifacts/6-3-render-report-summary-across-generated-outputs.md
  - _bmad-output/implementation-artifacts/7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md
  - _bmad-output/implementation-artifacts/close-cleanup-proof-migration-and-archive-proof-scaffolding.md
  - _bmad-output/planning-artifacts/decisions/question-actual-answer-persistence-and-live-wiring-decision-record.md
  - _bmad-output/planning-artifacts/decisions/analyst-workflow-surfaces-epic-placement-decision-record.md
  - _bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md
  - commit 5462714 message (2026-07-30 23:08, the last commit — via reflog)
  - full read of every surviving file in _bmad-output/, docs/, src/, tests/
---

# Project State Reconstruction — 2026-08-06

## 1. Where the project actually stands

Seven epics of the "2026 F1 Questions Analysis And Backtesting Capability" PRD
were implemented and (per sprint tracking) done or effectively done, ending at
`epic-7-retrospective`. But the last commit (`5462714`, 2026-07-30 23:08,
"Record the live-wiring prerequisite and its absence from the sprint") is a
verified diagnosis that the whole stack was never connected end-to-end:

> The flagship deliverable answers none of the five questions it exists to
> answer. `build_question_workflow_surfaces.py` regenerates the bundle from
> real DuckDB and every question renders "Answer: not yet computed in this
> bundle", with `bundle.portfolio_ready=False`. This is a wiring gap, not a
> data gap. The four Epic-2 extractors exist with real entry points and
> nothing calls them outside tests. Seven epics of reporting sit on top of a
> layer that was never connected.

The fix was designed and accepted on 2026-07-28
(`question-actual-answer-persistence-and-live-wiring-decision-record.md`: two
append-only DuckDB tables — `question_actual_answer_components`,
`question_feature_availability_contract` — plus a new
`scripts/build_question_actual_answers.py`), explicitly "epic-sized, not
story-sized", with the instruction to create it via `bmad-create-epics-and-stories`.
That epic was never created. The recommended first slice was **Q01 and Q04
end-to-end**, both dependent on the lap evidence Story 7.8 rebuilt on 2026-07-30.

Then, on 2026-08-01, the iCloud relocation destroyed 207 tracked files —
including every `question_*` module, every script, every test that mattered,
the DuckDB database, and the four canonical state artifacts. **The last-commit
recommendation is no longer executable as written**: the code it would wire
together no longer exists.

## 2. Reconstructed epic/story map

Epic titles are verbatim from `.git/logs/HEAD` (the reflog survived as plain
text even though git history does not traverse). ✅ = story artifact survives
on disk; ❌ = artifact in the unrecoverable 207 (name recovered from the git
index).

### Scheme A — current (PRD: prd-f1-questions-analysis-2026-07-17)

| Epic | Title | Stories | Status |
|---|---|---|---|
| 1 | Question Catalog And Target Contract | 1.1 ❌ · 1.2 ❌ · 1.3 ❌ · 1.4 ✅ | done (committed 2026-07-27) |
| 2 | Source-Backed Actual Answer Extraction | 2.1 ❌ · 2.2 ✅ · 2.3 ❌ · 2.4 ❌ · 2.5 ❌ | done (committed 2026-07-27) |
| 3 | Leakage-Safe Baselines And Scoring | 3.1 ❌ · 3.2 ❌ · 3.3 ❌ | done; open action item resolved as design-only (see §3) |
| 4 | Backtest Reporting And Portfolio Explanation | 4.1 ❌ · 4.2 ❌ | done; retro flagged the missing live/report-first story |
| 5 | Analyst Workflow Surfaces And Output Bundle | 5.1 ❌ | done; charter survives in the epic-placement decision record |
| 6 | Track-1 UX surfaces | 6.1–6.2 ❌ · 6.3 ✅ · 6.4–6.6 ❌ · 6.7 ✅ · 6.8 ❌ | done; see 6.7 status note below |
| 7 | Gatherer Insight Package Assembly | 7.1–7.5 ❌ · 7.6 ✅ · 7.7 ❌ · 7.8 ❌ | done through 7.8 (2026-07-30 22:52, last story commit) |

**Story 6.7 status note:** the on-disk artifact reads `Status: in-progress`
with its BLOCKING finding ("why it matters" renders a hardcoded literal)
unchecked. That is stale. Story 6.8 was created and committed to close exactly
that gap (`aabff7c`), and commit `9566e89` ("Epic 6/7: flip stale in-progress
epic status") reconciled statuses in the now-lost sprint-status.yaml. Treat
6.7 as done-after-6.8.

**Epic 6 shape:** seven Track-1 surfaces (6.1–6.7) + one follow-up (6.8). The
full 15-component surface inventory survives in
`ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md` §Components — the only
surviving enumeration now that `EXPERIENCE.md` is lost.

### Scheme B — superseded cleanup epic numbering (2026-07-15 PRD, lost)

A separate, earlier epic numbering from the doc-cleanup PRD explains the
duplicate `1-1-*`/`1-2-*`/`1-3-*`/`3-3-*` artifact names. That track is closed
and archived as historical evidence (CP-001). Its 27 doc deletions were
deliberate — dangling references to those paths in old notes are pre-existing
debt, not new damage.

### CP-* cleanup-proof track

All 41 CP rows have a terminal bucket in
`close-cleanup-proof-migration-and-archive-proof-scaffolding.md` (lines 43–83)
— the best surviving governance state table. A few rows bucketed
`move_to_durable_home` are now moot because their source files are themselves
in the 207 (CP-015 `docs/questions.md`, CP-017G `docs/analysis_output_standards.md`,
CP-018A/B `docs/inbox/*story-4-3*`).

## 3. Open work, consolidated

### Epic-sized, unscheduled

1. **Live-wiring / persistence epic** — designed and accepted 2026-07-28,
   never created as epic/stories. This was THE next thing. Post-loss, it now
   implies rebuilding its prerequisites first (see §5).
2. **Wiring hazard recorded in `5462714`:** eleven deferred-work entries were
   unreachable while every answer was pending, and all become reachable at
   once when wiring lands. Four produce wrong output rather than cosmetic
   defects: DW-92 (`portfolio_ready` classifies on answer presence, not
   status — a PARTIAL/DISCREPANT answer publishes as ready), DW-94
   (`portfolio_ready` ignores the Analysis Mode Boundary), DW-112 (pandas
   `.df()` float64 promotion fabricates a `43.0 != 43` lap discrepancy),
   DW-32 (no `question_id` cross-check before scoring). Wiring-first without
   hardening means the first real published answers could be overclaims.

### Story-level, visible on disk

3. `define-run-daily-pipeline-evidence-write-contract-and-close-run-log.md` —
   `status: review`, all findings resolved, never advanced to done. The only
   story left mid-workflow independent of the data loss.
4. Story 6.3 — five unchecked `[Review][Patch]` items against
   `report_summary.py` (now lost; items only matter if/when it is rebuilt).

### Product decisions still open (PRD §10)

5. Williams-only, or any team/driver from the start?
6. May source-backed Actual Answers auto-override a PDF Known Answer on
   disagreement, or is manual review required?
7. Portfolio display bands for lap-time score explanations?
8. Exact approval mechanism promoting `user_manual_option` →
   `user_manual_approved`?

### Data/answer integrity

9. **Q04 fastest-lap discrepancy** — PDF says lap 60; Jolpica result-level
   field says 58, `discrepant_needs_review`. Story 7.6 rolled back the bridge
   that rendered 58 as final; any output showing 58 is stale.
10. **Q05 retirement-lap discrepancy** — deliberately `leave_open`
    (`raw_jolpica_results.laps=43/status=Retired` vs known-answer narrative);
    needs a new source-coverage story to resolve.
11. **Jolpica pagination** — defect analysis survives in 7.6; the fix (Story
    7.8, `jolpica_loader.py`) is lost code. The 7 surviving live cache files
    are post-fix vintage; the platform snapshot's 67 are pre-fix. Any restore
    must not regress them (see §5 merge rules).

### Cross-repo

12. `gatherer-f1-next-story-intake-2026-07-30` — unanswered; accurate answer
    per the damage record: "F1's next story is not scopeable" until the
    catalog work is rebuilt.
13. `f1-to-gatherer-insight-package-input-requirements-question-2026-07-28` —
    Gatherer's response file is in the 207; whether it was answered is
    unverifiable from inside F1.
14. `body_sha256: pending` in `f1-r3-position-updated-and-prior-instance-2026-07-30.md`
    — one-line fix.
15. F1's council-directive acknowledgement exists only in retired exchange
    folders — F1's own defect to fix.
16. Two administrative-authored packets survive ONLY inside F1
    (`administrative-to-f1-project-authority-boundary-...-2026-07-21.md`,
    `...-run-record-destination-clarification-...-2026-07-22.md`) — F1 is
    their custodian now.

### Paused planning thread

17. The 2026-07-24 brainstorming session ("next direction") paused
    mid-Question-Storming and never converged. Its canonical `.memlog.md` is
    lost; only `session-checkpoint.md` survives. It carries the ecosystem
    reframing (f1_analytics as one node integrating with gatherer + social
    media projects; narrative moved out of this project) that `PROJECT.md`
    does not yet reflect.

## 4. What is lost vs what survives

### Lost, unrecoverable from any known source (verified)

- All four canonical state artifacts: `epics.md`, `sprint-status.yaml`,
  `deferred-work.md` (freshly DW-migrated one commit before the loss),
  `project-context.md`. No `DW-<n>` id survives anywhere on disk.
- Both `ARCHITECTURE-SPINE.md` versions and all architecture reviews.
- The entire question-era code: 16 `src/f1_analytics/` modules
  (`question_catalog.py`, `question_answers.py`, `question_workflow_surfaces.py`,
  `report_summary.py`, `evidence_link.py`, `openf1*.py`, both backtest
  modules, …), all 9 `scripts/`, 18 of 22 tests. Searched the whole home
  directory by filename: zero copies exist.
- 13 of 19 decision records (incl. `dataset-precedence`,
  `question-backtest-mode-and-scoring`, `openf1-adapter-source`,
  `q05-retirement-lap-known-answer-correction`).
- The Gmail questions PDF (`external/f1-questions/` is empty),
  `docs/questions.md`, `docs/backlog.md`, `docs/run_log.md`.
- Git history itself: 231 broken objects, history does not traverse from
  `ae7fd68`. All `baseline_commit:` citations in story files are uncheckable.

### Survives on disk (the spine to rebuild from)

- PRD `prd-f1-questions-analysis-2026-07-17/prd.md` (`status: final`,
  FR-1…FR-18, SM-1…SM-8, glossary) + its validation report.
- `docs/data_sources.md` — precedence rule, all three sources, DuckDB table
  inventory. `docs/index.md` (mostly dead links but records architecture).
- 6 decision records incl. the live-wiring design and Epic-5 charter.
- 13 implementation artifacts incl. the two 50–75 KB Epic-6 story files that
  quote the lost `epics.md`, `deferred-work.md`, and `sprint-status.yaml`
  line-by-line, and 7.6 with the full pagination finding.
- UX `DESIGN.md` (15-component inventory) + `UX-INTAKE.md` + validation
  reports.
- Code: `status_badge.py` (imports clean),
  `question_feature_availability.py` (645 lines, intact, blocked on lost
  `question_catalog`), `question_backtest_explanations.py` (404 lines,
  intact, blocked on lost `question_backtest_report`).
- `.git/logs/HEAD` — 38 reflog entries with full commit subjects: the epic
  titles and completion timeline.
- The damage assessment itself (`repository-damage-and-recovery-options-2026-08-01.md`).

### Partial recovery source — platform snapshot (NEW FIND, 2026-08-06)

`/Users/antonio/howdoidata/projects/platform/external/f1_analytics/` is an
intact 2026-07-07→09 byte-real snapshot (185 files, 16 MB) containing **38 of
the lost files**:

- The entire V1 pipeline layer: 14 lost `src/` files — `config.py`, both
  package `__init__.py`s, all 6 `data_sources/*` loaders, `duckdb_io.py`,
  both `validation/*`, both championship-leader analysis modules.
- 5 of 9 lost scripts (`build_f1_dataset.py`, `build_combined_dataset.py`,
  `pull_jolpica_data.py`, `download_kagglehub_f1_data.py`,
  `analyze_championship_leaders.py`), both `sql/analysis/` files, the
  notebook, `docs/decisions.md` (+15 other lost docs).
- `data/processed/f1_analytics.duckdb` (12 MB, 2026-07-09 build), complete
  `data/raw/` (all 8 Kaggle CSVs, all 67 Jolpica JSON), 6 lost output CSVs.

All 22 `.py` files parse cleanly and the snapshot is dependency-closed; line
counts match the 2026-07-12 census exactly.

**Caveats:** (1) it predates the question era entirely — no `question_*`
module, no tests; (2) its Jolpica cache and DuckDB are PRE-pagination-fix —
restoring them over the 7 surviving post-fix cache files would regress Story
7.8's corrections; (3) the snapshot itself is gitignored inside platform's
damaged repo — unbacked. **Protective copy made 2026-08-06:**
`recovery/platform-external-f1_analytics-snapshot-2026-07-09.tar.gz` (this repo).

### Standing handling constraints (from the damage record — still live)

- Do NOT run `git gc`, `git prune`, or `git repack` (231 broken objects).
- Do NOT run blanket `git restore .` (it would fail on the 207 and can mask
  what is deliberately kept).
- `/Users/antonio/dev/howdoidata/` is a structure-only skeleton — never
  restore from it.
- iCloud "Recently Deleted" remains the only avenue for the 207 question-era
  files, on a rolling purge window — Antonio's to pursue, urgently if at all.

## 5. Recommended restart path

Ordered so each step unblocks the next; nothing here executes without
Antonio's go-ahead.

1. **Record the loss in git.** `git rm` the 206 missing tracked paths (+
   `git rm --cached .bmad-loop/policy.toml`, now gitignored) in one
   "record the 2026-08-01 loss" commit on a fresh branch off master. This
   makes the tree honest, un-blocks `bmad-loop validate`'s clean-tree gate,
   and protects the survivors going forward. (Push to origin after.)
2. **Selective restore from the platform snapshot** — code and docs YES,
   data caches CAREFULLY: restore the 14 `src/` files, 5 scripts, sql,
   notebook, and `docs/decisions.md`; restore `data/raw/` EXCEPT the 7
   files where a post-fix live version exists (live wins); treat the July-9
   DuckDB as disposable scaffolding to be rebuilt, not truth.
3. **Rebuild the planning layer from this document:** regenerate `epics.md`
   (epics 1–7 marked done with evidence pointers, plus the new live-wiring
   epic from the accepted decision record), then run `bmad-sprint-planning`
   to emit a fresh `sprint-status.yaml`. Seed a new `deferred-work.md` with
   the reconstructable entries (§3 items 2, 4, 9–11).
4. **Rebuild the question-era code as the live-wiring epic, test-first.**
   The PRD (FR-1…FR-18), the two intact-but-blocked modules (which pin the
   exact symbol contracts of `question_catalog` and
   `question_backtest_report`), the accepted persistence design, and the
   surviving story files give unusually strong specs for a rebuild. First
   slice stays Q01 + Q04 end-to-end — now including their prerequisites.
   Harden the four wrong-output DW items (§3.2) BEFORE first publication.
5. **Answer Gatherer** (§3.12) once step 3 makes the next story scopeable.
