---
story_key: 6-3-render-report-summary-across-generated-outputs
created: 2026-07-23
source_decision: _bmad-output/planning-artifacts/epics.md#Epic-6
baseline_commit: b0ba67b9b410ed001c839dc2b83076d173b903cd
---

# Story 6.3: Render Report Summary Across Generated Outputs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Antonio,
I want every generated report, notebook answer section, or HTML export to lead with a Report Summary,
so that a reader sees question, answer, source/cutoff basis, status, and next action before any supporting detail.

## Scope Decision

This story implements UX-DR3 (Report Summary), the third of Epic 6's seven Track 1 surfaces. Unlike Stories 6.1 and 6.2 — which added a self-contained surface to one bundle — **this story has a second, cross-family deliverable**: it must retrofit the already-shipped championship-leader reports, which live in a module (`championship_leaders.py`) that has nothing to do with the question-backtest stack. That cross-family reach is the reason this story creates a companion module instead of only extending `question_workflow_surfaces.py`.

In scope:
- A new, dependency-light companion module `src/f1_analytics/analysis/report_summary.py` owning the reusable Report Summary contract (dataclass, field order, reason-required validation, Markdown renderer).
- A per-question Report Summary surface wired into `AnalystWorkflowSurfaceBundle` as a **7th** surface type, rendered **first** in the generated Markdown.
- Retrofit of both championship-leader reports (`write_report`, `write_followup_report`) to lead with a Report Summary section, preserving every existing section.
- Updating the Story 6.2 Implementation Handoff registry row for "Report Summary" from `OPEN` to `SATISFIED` (with its now-real implementing module), plus the test that asserts the open/satisfied split.

Out of scope — do **not** do these:
- **Do not invent an answer.** No Actual Answer Components are wired into the surface bundle (the epic-5 live-DuckDB-extractor-wiring decision is still open in `sprint-status.yaml`). The five supplied questions therefore render `Answer: not yet computed in this bundle` with their real `pending`/coverage status. This is the single highest-risk failure mode in this story — see Previous Story Intelligence.
- **Do not render the Known Answer Example as the answer.** AD-4 makes the PDF known answer a validation input, never the authority. A summary whose `answer` field equals the row's `known_answer_example` is a defect, and a test locks this.
- **Do not add a new status value.** AC2 lists `stale` and `unscoreable`, which are *not* in the 7-value controlled vocabulary. Model them as separate fields (`stale_basis_reason`, `unscoreable`), never as status strings. Status Badge consistency itself is Story 6.5's job, not this one's.
- Notebook (`notebooks/championship_leader_combined_analysis.ipynb`) and HTML-export retrofits. The notebook is a tracked artifact carrying executed cell outputs; retrofitting it means a full re-execution and an outputs diff that this story's ACs do not require. `render_report_summary_markdown()` is deliberately the reusable primitive a future notebook cell or HTML export calls — say so, do not silently claim the notebook was covered.
- Any new persistence, live extractor wiring, or DuckDB read inside `src/f1_analytics/analysis/`.
- Changing `_bundle_portfolio_ready()`'s existing gating rules.

## Acceptance Criteria

1. Given a generated report, notebook section, or HTML export presents an answer, when the Report Summary surface renders it, then it leads with question, answer, source/cutoff basis, status, and next action, in that order, before supporting detail.
2. Given the answer status is partial, source_blocked, discrepant_needs_review, stale, or unscoreable, when the Report Summary is rendered, then the reason for that status appears in the summary itself, not only in a later section.
3. Given the existing championship-leader report and the five supplied PDF question report rows, when the Report Summary surface is applied to them, then each retrofit report leads with the summary fields, and no existing report loses previously reported source-limitation detail.
4. Given the summary is generated, when output is written, then it extends the existing `scripts/build_question_workflow_surfaces.py` script; module-level code extends `question_workflow_surfaces.py` with focused new functions or a companion module if a single file would grow unwieldy, and it writes to `outputs/reports/` and/or `outputs/tables/`.

## Tasks / Subtasks

- [x] Create the reusable Report Summary contract in a new companion module. (AC: 1, 2)
  - [x] Create `src/f1_analytics/analysis/report_summary.py` with a module docstring and `from __future__ import annotations`, matching the style of the newer analysis modules.
  - [x] **Import discipline is load-bearing — read this before writing the imports.** This module may import `ActualAnswerStatus` from `f1_analytics.analysis.question_answers` (the controlled 7-status vocabulary must not be redefined) and stdlib only. It must **not** import `question_workflow_surfaces` (that module will import *this* one — a cycle), and must **not** import `question_backtest_explanations` / `question_backtest_report` / `question_backtest_scoring` (that would make `championship_leaders.py`, a Kaggle-baseline module, transitively depend on the whole question-backtest stack for no functional reason).
  - [x] Add `REPORT_SUMMARY_FIELD_ORDER: tuple[str, ...] = ("Question", "Answer", "Source and cutoff basis", "Status", "Next action")` as the single source of truth for AC1's ordering. The renderer iterates this constant; tests assert against it. Do not hardcode the labels a second time in the renderer.
  - [x] Add `STATUSES_REQUIRING_REASON: frozenset[ActualAnswerStatus]` = `{PENDING, PARTIAL, SOURCE_BLOCKED, DISCREPANT_NEEDS_REVIEW, USER_MANUAL_OPTION, USER_MANUAL_APPROVED}`. `USER_MANUAL_APPROVED` is included deliberately: AD-5 requires manual provenance to stay labeled and excluded from computed-source success, so it always owes the reader a reason. Only `COMPUTED` may omit one.
  - [x] Add a frozen dataclass `ReportSummary` with fields: `subject: str` (what the summary is about — a Question ID, or a report key such as `"championship_leader_conversion"`), `question: str`, `answer_display: str | None`, `source_and_cutoff_basis: str`, `status: ActualAnswerStatus | str`, `next_action: str`, `reason: str | None = None`, `stale_basis_reason: str | None = None`, `unscoreable: bool = False`, `evidence_paths: tuple[str, ...] = ()`.
    - `next_action` is typed `str`, **not** `SurfaceNextAction` — that enum lives in `question_workflow_surfaces.py` and importing it here would create the cycle named above. Callers pass the already-coerced string value.
    - `evidence_paths` carries generated/source artifact paths only. Do not build an Evidence Link abstraction here; UX-DR4 is Story 6.4's surface, and this field is just the paths this summary already knows.
  - [x] Add `build_report_summary(...) -> ReportSummary` that constructs the dataclass and **raises `ValueError`** when a reason is required but absent — i.e. when `status` coerces into `STATUSES_REQUIRING_REASON`, or `unscoreable is True`, or `stale_basis_reason` is set, and `reason` is empty/whitespace. The message must name which trigger fired (e.g. `"reason is required for status 'source_blocked'"`). This raise is what makes AC2 enforceable rather than aspirational; follow the precedent of `build_portfolio_question_explanation()` raising `ValueError` on a contract violation.
  - [x] Add `render_report_summary_markdown(summary: ReportSummary, *, heading_level: int = 2, heading_text: str = "Report Summary") -> str` returning a Markdown block that emits the five `REPORT_SUMMARY_FIELD_ORDER` fields as bullets in order, with:
    - `Answer:` rendering `answer_display` when present and the exact literal `not yet computed in this bundle` when it is `None` (do not print `None`; that is a live defect already logged in `deferred-work.md` for the intake section).
    - `Status:` rendering the status value plus, on the same line, `— <reason>` whenever `reason` is set, so the reason cannot drift into a later section (AC2).
    - stale and unscoreable rendered as their own lines **inside** the summary block, after `Status` and before `Next action`, only when set.
    - `evidence_paths` rendered after `Next action` when non-empty.
    - No trailing-whitespace lines; return text ending in a single `\n`.
- [x] Wire a per-question Report Summary surface into the existing bundle as the 7th surface type. (AC: 1, 2, 4)
  - [x] In `src/f1_analytics/analysis/question_workflow_surfaces.py`, import `ReportSummary`, `build_report_summary`, and `render_report_summary_markdown` from `report_summary`.
  - [x] Add `build_report_summaries(catalog_rows=None, source_coverage=None) -> tuple[ReportSummary, ...]` returning one summary per supplied catalog row, in catalog-row order, derived **only** from data the bundle actually holds:
    - `subject` = `row.question_id`; `question` = `row.natural_language_prompt`.
    - `answer_display` = `None` for every supplied question in this bundle. Add a short comment stating why (no Actual Answer Components are wired; the epic-5 live-wiring decision is open) so a future reader does not "fix" it by reaching for `known_answer_example`.
    - `source_and_cutoff_basis` = the question's coverage source plus its feature-snapshot boundary — reuse `_feature_snapshot_boundary_summary(row.feature_snapshot_boundary)` (already in this file) and the coverage row's `candidate_or_current_source`. Do not recompute either.
    - `status` = the question's coverage `readiness_status` (already an `ActualAnswerStatus`); for the four non-Q05 questions that is `PENDING` via `_pending_source_coverage_surface()`.
    - `next_action` = `_enum_value(coverage_row.next_action)`.
    - `reason` = the coverage row's `reason` (never empty for a non-`computed` status — that is why `build_report_summary()` will not raise here).
    - Reuse `_coverage_rows_by_question()` and `_default_reuse_review_source_coverage()` for the coverage lookup exactly as `build_reuse_and_extension_review_surfaces()` does; when a question maps to several coverage rows (Q05), select with the existing `_primary_blocked_coverage_row()` helper and fall back to the first row when every row is `available`.
  - [x] Add `report_summary_to_record(summary: ReportSummary) -> dict[str, object]` **in `question_workflow_surfaces.py`** (not in `report_summary.py`), applying `_neutralize_public_text()` to `question`, `answer_display`, `source_and_cutoff_basis`, `reason`, and `stale_basis_reason`, and `_enum_value()` to `status`. Rationale to preserve: `report_summary.py` is deliberately sanitizer-free so it stays importable by `championship_leaders.py`; the public-framing gate belongs to the bundle's serialization layer, where every other `*_to_record()` already applies it.
  - [x] Add `report_summaries: tuple[ReportSummary, ...]` to `AnalystWorkflowSurfaceBundle` and populate it in `build_supplied_pdf_analyst_workflow_surface_bundle()` from the already-built `rows` and `source_coverage` (do not rebuild coverage).
  - [x] Update every place that enumerates surface types — missing one of these is the known regression for this file: `analyst_workflow_surface_bundle_to_records()`, the hardcoded tuple in `_flat_surface_records()`, and `_status_field_for_surface_type()` (map `"report_summaries"` → `"status"`).
  - [x] In `render_analyst_workflow_surface_markdown()`, emit the `## Report Summary` section **first — immediately after the portfolio-ready/limitations header and before `## Question Intake Brief`**, delegating each entry to `render_report_summary_markdown(summary, heading_level=3, heading_text=summary.subject)` or an equivalent per-entry block. This is a deliberate, story-authorized change to the generated report's section order (UX contract: "Report stability: generated Markdown and CSV outputs should keep stable column names and section order unless a story explicitly changes the output contract"). Appending it at the bottom like Stories 6.1/6.2 did would directly contradict UX-DR3's "before supporting detail".
  - [x] Do **not** fold `report_summaries` into `_bundle_portfolio_ready()`. It renders statuses that other surfaces already gate on; adding it as a gate would double-count. Extend the existing comment above `_bundle_portfolio_ready()` so it names all three excluded surfaces (`reuse_and_extension_review`, `implementation_handoff`, `report_summaries`).
  - [x] Add `ReportSummary`, `build_report_summaries`, `report_summary_to_record`, and `render_report_summary_markdown` to `__all__`, keeping the list alphabetized as it is today.
- [x] Correct the Implementation Handoff registry — Report Summary is no longer an open handoff. (AC: 3, 4)
  - [x] In `IMPLEMENTATION_HANDOFF_REGISTRY`, move the `"Report Summary"` entry from the "Open" block to the "Satisfied" block: set `implemented_module_or_script` to the real implementation (e.g. `"report_summary.render_report_summary_markdown / question_workflow_surfaces.build_report_summaries"`) and `handoff_status` to `HandoffStatus.SATISFIED`. Keep the registry's declared order stable otherwise. Leaving it `OPEN` would make the handoff surface assert that unimplemented work is unimplemented while its own module implements it — the exact "fabricated/stale readiness" failure Story 6.2 was written to prevent, inverted.
  - [x] **Required regression fix:** in `tests/test_question_workflow_surfaces.py`, move `"Report Summary"` from `ImplementationHandoffSurfaceTests.OPEN_UX_SURFACES` to `SATISFIED_UX_SURFACES`. The count assertion stays at 13; the satisfied/open split becomes 6/4/3.
- [x] Retrofit both championship-leader reports. (AC: 3)
  - [x] In `src/f1_analytics/analysis/championship_leaders.py`, import from `report_summary` only (never from `question_workflow_surfaces`).
  - [x] In `write_report()`, build a `ReportSummary` from values already computed in that function and insert its rendered block **immediately after the `# Championship Leader Conversion At Current Season Cutoff` H1, before `## Question`**:
    - `question` — reuse the existing `## Question` text: "How often did the driver or constructor leading at this point in the season go on to win the championship?"
    - `answer_display` — the driver and constructor conversion rates at the cutoff, from the existing `driver_summary` / `constructor_summary` dicts.
    - `source_and_cutoff_basis` — target season, cutoff round, cutoff race, cutoff race date, and that the cutoff comes from completed rounds in local Kaggle `f1_results.csv` (all already in scope in that function).
    - `status` — `ActualAnswerStatus.COMPUTED`.
    - `reason` — state near the answer that the target-season championship outcome is not yet known locally, matching the existing "reported separately" caveat.
    - `next_action` — `"reuse_existing"`.
    - `evidence_paths` — the four table paths already listed in the report's `## Output Tables` section.
  - [x] Do the same in `write_followup_report()`, using its own already-computed values (`largest_text` / comeback framing for the answer, its Kaggle-baseline cutoff wording for the basis) and its existing `## Outputs` paths.
  - [x] **Preserve every existing section verbatim.** `write_report()` must keep `## Question`, `## Cutoff Definition`, `## Drivers`, `## Constructors`, `## Current Season Leaders`, `## Data Limitations`, `## Output Tables`. `write_followup_report()` must keep `## Data Sources`, `## Current Cutoff`, `## Current Conversion Answers`, `## Largest Constructor Comeback`, `## Candidate Recovery Features`, `## Outputs`, `## Limitations`. The summary is additive — deleting or "consolidating" a limitations section fails AC3's second clause.
  - [x] Keep `encoding="utf-8"` on both `write_text()` calls (already present — do not drop it while editing).
- [x] Extend the thin script — no new script file. (AC: 4)
  - [x] In `scripts/build_question_workflow_surfaces.py`, add `"report_summaries"` to the printed row-count summary tuple. No new logic, no new DB reads; the bundle builder supplies it.
- [x] Add focused tests. (AC: 1-4)
  - [x] New file `tests/test_report_summary.py` for the contract module:
    - Rendered Markdown emits `REPORT_SUMMARY_FIELD_ORDER` labels in that exact order (assert on ascending `str.index()` positions, not on a hardcoded expected string, so wording changes do not break the ordering guarantee).
    - `build_report_summary()` raises `ValueError` for each reason-requiring trigger with no reason: a status in `STATUSES_REQUIRING_REASON` (cover at least `partial`, `source_blocked`, `discrepant_needs_review`), `unscoreable=True`, and `stale_basis_reason` set. Assert the message names the trigger.
    - `status="computed"` with no reason builds successfully.
    - A reason-carrying summary renders its reason on the `Status` line (AC2 — assert the reason text appears in the summary block, not merely somewhere in the file).
    - `answer_display=None` renders `not yet computed in this bundle` and never the literal `None`.
  - [x] New file `tests/test_championship_leaders_report.py` for the retrofit (there is no existing championship-leader test file — this is new coverage, and AC3's "no existing report loses detail" clause is untestable without it):
    - Build minimal pandas fixtures and call `write_report()` / `write_followup_report()` against a `tempfile.TemporaryDirectory()` path. No DuckDB is needed — both functions take DataFrames as arguments. Required fixture shapes, verified against the current code:
      - `coverage`: columns `metric`, `value`; must include rows `scheduled_races_target_season` and `completed_result_rounds_target_season`.
      - `driver_conversion` / `constructor_conversion`: a `converted` column (`summarize_conversion()` reads only `len()` and `converted.sum()`).
      - `current`: columns `entity_type` (`"driver"` / `"constructor"`), `leader_name`, `leader_points`, `leader_wins`.
      - follow-up also needs `comeback_cases` with `points_deficit_overcome`, `season`, `champion_constructor`, `cutoff_points`, `cutoff_leader_points`, `cutoff_rank`, `final_points`, `final_wins`; and `feature_candidates` with `feature`, `plain_language_definition`, `current_status`. Pass `figure_path=None` to exercise the no-figure branch.
    - Assert the Report Summary block appears **after the H1 and before the first pre-existing `##` section** (compare `str.index()` positions).
    - Assert every pre-existing section heading listed in the retrofit task above still appears in the regenerated text — this is the regression lock for AC3's second clause.
  - [x] In `tests/test_question_workflow_surfaces.py`, add a `ReportSummarySurfaceTests` class covering:
    - `build_report_summaries()` returns exactly 5 summaries, one per supplied catalog row, with unique subjects in catalog-row order.
    - **No supplied question's `answer_display` equals its `known_answer_example`, and none has `status == ActualAnswerStatus.COMPUTED`** — the AD-4 / no-fabricated-answer lock.
    - Every summary carries a non-empty `reason` (each maps to a reason-requiring status, so this also proves `build_report_summary()` was not bypassed).
    - `report_summary_to_record()` emits plain values with the enum coerced to its string value and tuple fields preserved.
    - The rendered bundle Markdown places `## Report Summary` before `## Question Intake Brief` (AC1's "before supporting detail" at bundle level).
  - [x] Update `AnalystWorkflowSurfaceSerializationTests.test_bundle_serialization_uses_plain_values_and_controlled_status_strings` to include `"report_summaries"` in the expected key set.
  - [x] Do not write a parallel forbidden-terms test — `test_public_surface_text_excludes_forbidden_public_framing_terms` scans the whole bundle via `public_text_from_bundle()` and picks up the new surface automatically once it is in `analyst_workflow_surface_bundle_to_records()`.
- [x] Verify and log the result in this story's Dev Agent Record. (AC: 1-4)
  - [x] `PYTHONPATH=src python3 -m unittest tests.test_report_summary`
  - [x] `PYTHONPATH=src python3 -m unittest tests.test_championship_leaders_report`
  - [x] `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces`
  - [x] `PYTHONPATH=src python3 -m unittest discover -s tests` (full regression; baseline is 250 tests passing)
  - [x] `python3 -m compileall src/f1_analytics`
  - [x] `PYTHONPATH=src python3 scripts/build_question_workflow_surfaces.py` — confirm `report_summaries rows: 5` prints and inspect the generated `outputs/reports/question_workflow_surfaces.md` to confirm the summary section leads the file.
  - [x] `git diff --check` on touched tracked files, plus a direct trailing-whitespace grep for files that remain untracked.

### Review Findings

Code review 2026-07-23 (`bmad-code-review`, three parallel layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor). All four ACs were independently verified as satisfied, including a byte-diff of the pre- and post-retrofit championship reports confirming AC3's "no existing report loses detail" clause. Findings below are defects found alongside a passing acceptance audit. Every claim was re-verified against the code before being recorded; 8 further findings were dismissed as false positives or spec-authorized design.

Findings are grouped by cause: **genuine defects** (wrong with valid inputs), **input hardening** (only reachable via malformed input), and **content and wording** (text, no logic). 14 of 19 were applied; the 5 unapplied input-hardening guards were accepted as non-blocking at story close and moved to `deferred-work.md`.

Regression after the applied patches: **293 tests, OK** (280 before review, +13 new locking the fixed behaviors). Both generation scripts re-run; the conversion report is byte-identical to its pre-patch output and the follow-up differs only by the narrowed question line.

#### Genuine defects — all applied

- [x] [Review][Patch] Report Summary rows carry no `question_id` in the flat CSV, so per-question joins silently drop all five — every other surface type populates it; the ID was present only in the trailing `subject` column. **Fixed:** `report_summary_to_record()` now emits `question_id` mirroring `subject`, with `subject` kept as the contract field name (it may hold a report key for callers outside the bundle). Verified in the regenerated CSV [src/f1_analytics/analysis/question_workflow_surfaces.py:817]
- [x] [Review][Patch] `"report_summaries"` placed first in `_flat_surface_records()` shifted every existing CSV row down by 5 and inserted 7 new columns mid-header; the story authorized an output-contract change for the Markdown report only, and Markdown order is set independently in the renderer. **Fixed:** moved to last in the tuple with a comment recording why, restoring the CSV row and column contract. Markdown still leads with the summary [src/f1_analytics/analysis/question_workflow_surfaces.py:1450]
- [x] [Review][Patch] Two serialization inconsistencies in `report_summary_to_record()`: `_neutralize_public_text(None)` returned `""`, so `reason`/`stale_basis_reason` serialized as empty where every other surface's absent field becomes the `"null"` sentinel; and `answer_display or ANSWER_NOT_COMPUTED_TEXT` was a falsy test while the renderer used `_has_text()`, so a whitespace-only answer would print the fallback in Markdown but a blank cell in CSV. **Fixed:** added `_neutralize_optional_public_text()` preserving `None`, and `_has_summary_text()` for the answer test [src/f1_analytics/analysis/question_workflow_surfaces.py:819, :823]
- [x] [Review][Patch] The em dash in the Status line made the bundle Markdown write locale-dependent — `report_output_path.write_text(...)` had no `encoding=`, and pre-6.3 that file was pure ASCII so the write could not fail. Under a non-UTF-8 locale it raised `UnicodeEncodeError`. **Fixed:** `encoding="utf-8"` added with a comment naming the em dash as the reason. This deliberately touches a pre-existing `deferred-work.md` item, because this story is what made it live [src/f1_analytics/analysis/question_workflow_surfaces.py:862]
- [x] [Review][Patch] When no positive comeback cases exist, the follow-up summary rendered `Answer: No positive constructor comeback cases were available at this cutoff.` with `Status: computed` — absence of data published as a computed answer. **Fixed:** `build_followup_report_summary()` takes `has_comeback_case` and reports `partial` with a reason naming the absence; the prose is unchanged [src/f1_analytics/analysis/championship_leaders.py:477, :483]
- [x] [Review][Patch] A zero-row conversion frame rendered `Answer: … 0 of 0 historical seasons (0.0%)` with `Status: computed` — `summarize_conversion()` returns `rate=0` when `total==0`. **Fixed:** the status is now derived from the sample, reporting `partial` and naming the empty side when either conversion frame is empty. No effect on real data — the regenerated conversion report is byte-identical [src/f1_analytics/analysis/championship_leaders.py:438, :449]
- [x] [Review][Patch] `REPORT_SUMMARY_FIELD_ORDER` was not actually the single source of truth — the five labels were restated in `_summary_field_values()` and two more hardcoded in the renderer body, so renaming a constant entry raised `KeyError` at render time rather than renaming the field. Directly contradicted the story's "Do not hardcode the labels a second time in the renderer". **Fixed:** added positionally-aligned `_FIELD_KEYS`; the renderer branches on keys and takes labels from the constant. A test now patches the constant and asserts a rename flows through [src/f1_analytics/analysis/report_summary.py:132, :137, :147]

#### Input hardening — 2 applied, 5 accepted as non-blocking

The five unapplied guards were **accepted by Antonio at story close (2026-07-23)** rather than left as open work: no current caller produces the inputs that reach them, and the story's guidance is not to widen the diff for theoretical cases. They are recorded in `deferred-work.md` under "Input-hardening guards accepted at story close" so they survive this story closing. Revisit if `report_summary.py` gains callers beyond this repo's two.

- [x] [Review][Patch] Off-vocabulary status strings silently bypassed the mandatory-reason contract — **Decision resolved 2026-07-23 (Antonio): raise `ValueError` on any status outside the controlled vocabulary.** `_coerce_status()` swallowed the `ValueError` and `_reason_triggers()` required `isinstance(coerced, ActualAnswerStatus)` before adding a trigger, so `status="Partial"` (casing typo), `"source-blocked"`, or a wrong enum built with **no reason** and rendered verbatim, then flowed into the "controlled status" CSV column — defeating AC2's enforcement with a one-character typo. **Fixed:** `_coerce_status()` now raises naming the vocabulary, and the docstring that documented the old leniency was rewritten to match the enforced contract [src/f1_analytics/analysis/report_summary.py:98, :164, :173]
- [x] [Review][Patch] `_report_summary_reason()` guarded with `or` rather than a whitespace-aware check, giving two failures on one line: a whitespace-only coverage reason raised `ValueError` out of `build_report_summary()` and aborted the **entire bundle build**, and an empty reason on an existing row emitted "No source coverage row exists for this question" — false about a row that does exist. Applied despite being input-driven because it is reachable through analyst-authored coverage data and its blast radius is the whole bundle. **Fixed:** whitespace-aware check plus a distinct `_UNRECORDED_COVERAGE_ROW_REASON` message [src/f1_analytics/analysis/question_workflow_surfaces.py:1129]
- [ ] [Review][Patch] Only `answer_display` has an empty-value fallback; blank `question`, `source_and_cutoff_basis`, or `next_action` render as bullets ending in a trailing space, breaking the renderer docstring's own "Produces no trailing-whitespace lines" guarantee. Reachable through the bundle if a catalog row ever lacks a prompt — a case `_intake_blocking_reasons()` anticipates elsewhere. Suggested fix: validate the three required fields in `build_report_summary()`, matching the reason-validation precedent [src/f1_analytics/analysis/report_summary.py:143]
- [ ] [Review][Patch] A newline in any field value terminates the Markdown bullet list — trailing text renders at column 0 and every later field becomes a separate list. All five values are unvalidated caller-supplied free text; the ordering tests would still pass on a structurally broken document. Suggested fix: collapse whitespace per bullet value [src/f1_analytics/analysis/report_summary.py:131]
- [ ] [Review][Patch] `_has_text()` raises `AttributeError` on a non-str value at render time instead of failing at build time; the project's own `question_answers._has_text()` guards with `isinstance(value, str)` and this copy dropped it. Callers interpolate numeric analysis results, so a raw numeric would blow up inside `write_report()` after all six CSVs are written [src/f1_analytics/analysis/report_summary.py:188]
- [ ] [Review][Patch] `heading_level` is clamped at the bottom (`max(1, …)`) but not the top, so `heading_level=9` emits `######### Report Summary`, which is not a heading in CommonMark and renders as literal text. Current callers pass 2 and 3 [src/f1_analytics/analysis/report_summary.py:129]
- [ ] [Review][Patch] `evidence_paths` passed as a bare string instead of a tuple emits one evidence bullet per character — `tuple(evidence_paths)` accepts any iterable [src/f1_analytics/analysis/report_summary.py:111]

#### Content and wording — all applied

- [x] [Review][Patch] The `"Report Summary"` handoff row was `SATISFIED` but still carried forward-looking text — "Story 6.3 **must** render a Report Summary section … extending question_workflow_surfaces.py **and its Markdown renderer**" — phrased as pending work (unlike every sibling satisfied row) and factually wrong about where the renderer lives, emitted verbatim into the generated report directly beneath `Status: satisfied`. **Fixed:** rewritten descriptively; verified in the regenerated report [src/f1_analytics/analysis/question_workflow_surfaces.py:312]
- [x] [Review][Patch] `FOLLOWUP_REPORT_QUESTION` asked two things ("how large a deficit … **and which recovery factors could explain it?**") but `answer_display` states only the deficit. **Fixed:** the constant now asks only what the answer delivers; recovery factors keep their own `## Candidate Recovery Features` section. This is the only content change to either regenerated championship report [src/f1_analytics/analysis/championship_leaders.py:33, :477]
- [x] [Review][Patch] The conversion question text existed twice — as `CONVERSION_REPORT_QUESTION` and as a re-typed literal in the `## Question` section. **Fixed:** the section interpolates the constant; a test asserts both occurrences match [src/f1_analytics/analysis/championship_leaders.py:24, :534]
- [x] [Review][Patch] `markdown_path_bullets()` is a new public function with a one-line docstring, missing the inputs/return/assumptions/failure-behavior documentation the project context requires. **Fixed** [src/f1_analytics/analysis/championship_leaders.py:415]
- [x] [Review][Patch] The registry's in-block marker still read `# --- Satisfied: Epic 5 / Story 6.1, already implemented ---` after Story 6.3's entry moved into that block, contradicting the updated header comment above it. **Fixed** [src/f1_analytics/analysis/question_workflow_surfaces.py:242]

#### Deferred

- [x] [Review][Defer] `evidence_paths` is never populated by `build_report_summaries()`, so the field is defined, rendered, and unit-tested but dead in the only place it ships — all five bundle summaries carry `()`, no `- Evidence:` line appears in the generated report, and the CSV column is `[]` for every row. `QuestionCatalogRow.source_artifact_path` is available and already used elsewhere in the module [src/f1_analytics/analysis/question_workflow_surfaces.py:606] — deferred, Story 6.4 (Evidence Link, UX-DR4) owns this surface

## Dev Notes

### Current Project State To Preserve

**`src/f1_analytics/analysis/question_workflow_surfaces.py` (1516 lines).** Read it completely before editing. It owns the Epic 5 + Story 6.1 + Story 6.2 surface/bundle contract. The structures you extend:

- `AnalystWorkflowSurfaceBundle` (line ~184) is a frozen dataclass with 6 surface-type fields today (`intake_briefs`, `catalog_rows`, `source_coverage`, `output_checklist`, `reuse_and_extension_review`, `implementation_handoff`) plus `portfolio_ready` and `source_status_limitations`. A 7th field requires updating all four enumeration points: `analyst_workflow_surface_bundle_to_records()` (~line 760), `_flat_surface_records()`'s hardcoded tuple (~line 1328), `_status_field_for_surface_type()`'s dict (~line 1344), and `render_analyst_workflow_surface_markdown()` (~line 796).
- Helpers to reuse, not re-derive: `_feature_snapshot_boundary_summary()`, `_coverage_rows_by_question()`, `_default_reuse_review_source_coverage()`, `_primary_blocked_coverage_row()`, `_enum_value()`, `_neutralize_public_text()`, `_limitations_text()`.
- `_pending_source_coverage_surface()` is what produces the four non-Q05 coverage rows: `controlled_status="pending"`, `readiness_status=ActualAnswerStatus.PENDING`, a populated `reason`, and `next_action=ADD_SOURCE_COVERAGE`. That is exactly the input your summaries consume — nothing else in the bundle carries an answer.
- `render_analyst_workflow_surface_markdown()` ends with `return _neutralize_public_text("\n".join(lines) + "\n")`, so anything you add to `lines` is neutralized on the way out. The CSV path is *not* neutralized by that call, which is why `report_summary_to_record()` must apply `_neutralize_public_text()` itself.

**`src/f1_analytics/analysis/championship_leaders.py` (660 lines).** The largest analysis module. `write_report()` (line 385) and `write_followup_report()` (line 465) each build one big f-string and `write_text(..., encoding="utf-8")`. They take DataFrames as parameters and touch no database — that is what makes them unit-testable without DuckDB. `run_analysis()` (line 596) is the only DuckDB caller and is invoked from `scripts/analyze_championship_leaders.py`. Per the project context rule, prefer a focused new helper over growing these functions further.

**Blast radius of changing the championship reports — checked, and it is small.** `scripts/run_daily_pipeline.py` and `scripts/verify_daily_pipeline_swap_contract.py` reference `championship_leader_conversion.md` / `championship_leader_followup.md` **only as file paths to atomically swap**; neither reads or asserts on report content, so a new leading section cannot break the swap contract or the marker/run-record telemetry. Historical MD5-checksum comparisons of these reports appear in `docs/run_log.md` as past evidence entries only — they are not an executing check. No test, notebook, or module parses these reports' text today.

**`tests/test_question_workflow_surfaces.py` (556 lines).** Defines `row_by_id()` and `public_text_from_bundle()` helpers reused across classes. `ImplementationHandoffSurfaceTests` carries the `SATISFIED_UX_SURFACES` / `OPEN_UX_SURFACES` / `BLOCKED_UX_SURFACES` class constants you must edit. Note the whole `tests/` suite is still untracked in git — do not take ownership of, revert, or normalize unrelated files in it.

### Architecture Compliance

- Reusable logic lives under `src/f1_analytics/`; `scripts/*.py` stay thin orchestration wrappers; renderers narrate already-computed facts. [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md#AD-1---Layer-Ownership-For-Reproducible-Analytics-ADOPTED`]
- "A renderer may display a friendly answer **only after preserving the component statuses**." This story is precisely that renderer — the status and its reason travel with the answer, never instead of it. [Source: `ARCHITECTURE-SPINE.md#AD-3---Question-Answers-Are-Statused-Targets-Not-Free-Text-ADOPTED`]
- PDF Known Answer Examples are validation inputs, not authority; a mismatch becomes `discrepant_needs_review` with both values preserved and is never auto-resolved. Do not surface a known answer as the computed answer. [Source: `ARCHITECTURE-SPINE.md#AD-4---PDF-Known-Answers-Are-Validation-Examples-ADOPTED`]
- `user_manual_approved` targets stay provenance-labeled and do not count as computed-source success — the reason for that status is therefore mandatory in a summary. [Source: `ARCHITECTURE-SPINE.md#AD-5---Source-Coverage-Before-User-Manual-Approval-ADOPTED`]
- Answer status vocabulary is fixed at the seven values "until a later decision changes the status vocabulary". [Source: `ARCHITECTURE-SPINE.md#Consistency-Conventions`]
- No DuckDB reads inside `src/f1_analytics/analysis/` for this surface — it renders already-loaded data, consistent with Stories 5.1 / 6.1 / 6.2.

### UX Contract Requirements

- Component pattern: "Report Summary — Start any generated report, notebook answer section, or HTML export — Always shows question, answer, source/cutoff basis, status, and next action before supporting detail. If the answer is partial, blocked, discrepant, stale, or unscoreable, the reason appears here." [Source: `EXPERIENCE.md#Component-Patterns`]
- IA row: "Report Summary | Analysis/report render | Lead any generated answer artifact with question, source/cutoff basis, answer, status, and next action." [Source: `EXPERIENCE.md#Information-Architecture`]
- State pattern: "Stale cutoff or source basis — Report Summary / Output Bundle Checklist — State stale basis near the answer and preserve generated path for audit." — this is why `ReportSummary` carries both `stale_basis_reason` and `evidence_paths`. [Source: `EXPERIENCE.md#State-Patterns`]
- Interaction primitives: "Status-first review: every generated output that contains an answer must show answer status near the answer" and "Report stability: generated Markdown and CSV outputs should keep stable column names and section order unless a story explicitly changes the output contract" — this story is that explicit change for the workflow-surfaces report and the two championship-leader reports. [Source: `EXPERIENCE.md#Interaction-Primitives`]
- Accessibility floor: "Status is always text plus color, never color alone." In Markdown/CSV the text *is* the badge — emit the status value as text; do not add emoji or color-only markers. [Source: `EXPERIENCE.md#Accessibility-Floor`]
- Output Bundle Contract, Markdown report row: must include "Question, answer, status, source/cutoff basis, limitation, and next action." [Source: `EXPERIENCE.md#Output-Bundle-Contract`]
- Voice: "Computed from `combined_results`; Kaggle row kept for this round." — not "Answer found." Reason text should name the artifact and the limitation, not hedge. [Source: `EXPERIENCE.md#Voice-and-Tone`]
- Layout sequence for generated reports: 1. Question answered. 2. Source and cutoff basis. 3. Answer and status. 4. Supporting table or figure. 5. Limitation and next action. The AC1 field order (question → answer → basis → status → next action) is the authority where these two orderings differ; `DESIGN.md` is the visual reference, `EXPERIENCE.md` and the ACs are the behavioral contract. [Source: `DESIGN.md#Layout--Spacing`, `DESIGN.md#Components`]
- Deferred-work origin of this story: "Report Summary — retrofit generated reports (new and existing, e.g. the championship-leader reports) to lead with question/answer/source-basis/status/next-action." The championship-leader retrofit is the named deliverable, not an optional extra. [Source: `_bmad-output/implementation-artifacts/deferred-work.md`, "analyst-environment UX contract coverage gap", 2026-07-22]

### Previous Story Intelligence

- **Story 6.1's review found four patch-level findings with one shared root cause: something was marked ready/generated/reused before it was verified against real state.** Story 6.2 was written to avoid repeating it and did. The equivalent trap here is the answer field: the bundle has no Actual Answer Components, so the only way to make the summary "look complete" is to borrow the Known Answer Example — which AD-4 forbids and a test now locks. Render `not yet computed in this bundle` and move on.
- **Story 6.2's review produced 7 applied patches; three are directly instructive here.** (1) The Markdown renderer omitted the one field the surface existed to deliver — so verify by eye that every `REPORT_SUMMARY_FIELD_ORDER` field actually reaches the generated file, not only the dataclass. (2) A multi-value field was modeled as a `"; "`-joined string while every sibling field used a tuple — `evidence_paths` is a `tuple[str, ...]` for that reason. (3) A blocking-reason helper asserted fields were missing without checking their actual values — derive, never assume.
- Story 6.2's wiring checklist for adding a surface type to this bundle is the exact checklist this story repeats for a 7th type: dataclass + `*_to_record()` + builder + `AnalystWorkflowSurfaceBundle` + `analyst_workflow_surface_bundle_to_records()` + `_flat_surface_records()` + `_status_field_for_surface_type()` + Markdown renderer + `__all__` + the bundle-keys test. The one deviation: this surface renders **first**, not last.
- Story 6.2 chose to keep everything in `question_workflow_surfaces.py` rather than split. This story splits — not for line count, but because `championship_leaders.py` is a second consumer and must not inherit the question-backtest import chain.
- `deferred-work.md` carries 16 open pre-existing findings against `question_workflow_surfaces.py` (missing `encoding="utf-8"` on writes, `_csv_value()` encoding `None` as `"null"`, unguarded enum coercion, `_neutralize_public_text()` garbling rewritten sentences, and others). **They are out of scope.** Do not opportunistically fix them; if one blocks you, note it in the Dev Agent Record rather than widening the diff.

### File Structure Requirements

Files this story creates:

- `src/f1_analytics/analysis/report_summary.py` — the reusable Report Summary contract (dataclass, field order, reason validation, Markdown renderer). Stdlib + `ActualAnswerStatus` only.
- `tests/test_report_summary.py`
- `tests/test_championship_leaders_report.py`

Files this story modifies:

- `src/f1_analytics/analysis/question_workflow_surfaces.py` — `build_report_summaries()`, `report_summary_to_record()`, bundle/renderer/CSV wiring, the `"Report Summary"` handoff-registry row, `__all__`.
- `src/f1_analytics/analysis/championship_leaders.py` — Report Summary section prepended in `write_report()` and `write_followup_report()`.
- `scripts/build_question_workflow_surfaces.py` — `"report_summaries"` added to the printed row-count tuple.
- `tests/test_question_workflow_surfaces.py` — `ReportSummarySurfaceTests`, the bundle-keys assertion, and the `OPEN_UX_SURFACES` → `SATISFIED_UX_SURFACES` move.

Do not edit `src/f1_analytics/analysis/__init__.py` — it remains a bare docstring module with no explicit exports adopted.

Generated, gitignored output (existing paths, not new):

- `outputs/reports/question_workflow_surfaces.md`, `outputs/tables/question_workflow_surfaces.csv`
- `outputs/reports/championship_leader_conversion.md`, `outputs/reports/championship_leader_followup.md`

### Testing Requirements

- Standard-library `unittest`, matching the existing suite. `PYTHONPATH=src python3 -m unittest discover -s tests` is the regression command; the baseline before this story is **250 tests passing**. The `daily_pipeline` scenario tests intentionally print `FAILED ...` lines while exercising their own failure paths — the overall result is still `OK`; do not "fix" them.
- No live DuckDB in unit tests. `write_report()` / `write_followup_report()` take DataFrames, so pandas fixtures suffice; the script smoke test writes under gitignored `outputs/`.
- Also re-run pipeline validation expectations per the project context rule if you touch anything data-adjacent — this story does not, so `validation/checks.py` is not exercised here.

### Git Intelligence

HEAD at story creation is `b0ba67b`, the same baseline as Stories 6.1 and 6.2:

- `b0ba67b Fix marker-write run telemetry`
- `963dfec docs: clarify daily pipeline run-record destination`
- `af1ce1c Record run-record administrative recommendation`
- `f47e84e Implement daily pipeline run telemetry contract`
- `20bb6f6 docs: record story 4.3 platform exchange`

These commits concern the daily-pipeline run-record telemetry contract. They matter here only as the blast-radius check documented above: the pipeline swaps the championship report files by path and never inspects their contents. Stories 6.1 and 6.2 remain uncommitted in the working tree along with the whole untracked `tests/` suite; the working tree also carries a large unrelated `docs/` deletion set. **Touch only the files this story names.**

### Latest Technical Information

No new libraries, versions, or external APIs are introduced. This story is stdlib + existing project modules only (`pandas` is already used by `championship_leaders.py`; the new `report_summary.py` needs neither pandas nor duckdb). Stack per `ARCHITECTURE-SPINE.md#Stack` and the live-verified project context: Python 3.13.7, pandas 3.0.3, DuckDB 1.5.4 — none of which this story's code depends on beyond what the touched modules already import.

### Project Context Reference

`_bmad-output/project-context.md` (2026-07-13, real unattended run) — the rules that bind this story:

- Reusable logic in `src/f1_analytics/`; `scripts/*.py` stay thin CLI wrappers (all 5 pipeline scripts are 27-55 lines).
- No linter/formatter config exists — match the surrounding module style: type-annotated signatures, module-level docstrings, `from __future__ import annotations`.
- `championship_leaders.py` is the repo's largest analysis module; **prefer a focused new function over growing existing ones further**, following how `combined_championship_leaders.py` was factored out rather than appended.
- Generated Markdown reports go under `outputs/reports/`, tabular exports under `outputs/tables/`; `outputs/` is gitignored and its contents are never committed.
- Public/reused functions document purpose, key inputs, return value, assumptions, and failure behavior.

### References

- `_bmad-output/planning-artifacts/epics.md#Epic-6` (Story 6.3 section — source of the Acceptance Criteria above)
- `_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/EXPERIENCE.md` (Information Architecture, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Output Bundle Contract)
- `_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md` (Components, Layout & Spacing)
- `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md` (AD-1, AD-3, AD-4, AD-5, Consistency Conventions)
- `_bmad-output/implementation-artifacts/deferred-work.md` ("analyst-environment UX contract coverage gap", 2026-07-22 — Track 1 item 3 is this story; plus the 16 open pre-existing findings that are explicitly out of scope)
- `_bmad-output/implementation-artifacts/6-2-build-implementation-handoff-surface.md` (preceding story; wiring checklist and review learnings)
- `_bmad-output/implementation-artifacts/6-1-build-reuse-and-extension-review-surface.md` (established the surface-extension convention)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (epic-5 open action item: live DuckDB extractor wiring — why no answers exist in the bundle)
- `src/f1_analytics/analysis/question_workflow_surfaces.py`, `src/f1_analytics/analysis/championship_leaders.py`, `src/f1_analytics/analysis/question_answers.py`
- `scripts/build_question_workflow_surfaces.py`, `scripts/run_daily_pipeline.py`, `scripts/verify_daily_pipeline_swap_contract.py`
- `tests/test_question_workflow_surfaces.py`

### Open Questions

- None blocking. Two notes for later stories, recorded so they are not silently absorbed here: (1) once the epic-5 live-wiring decision lands and real Actual Answer Components reach the bundle, `build_report_summaries()` gains a real `answer_display` and `status` per question — the contract is already shaped for it, no redesign needed. (2) `question_backtest_report.QuestionReportRow` / `question_backtest_explanations.PortfolioQuestionExplanation` already carry answer, status, and source metadata for scored questions, but nothing generates a Markdown report from them today; when a story adds that renderer, it should call `render_report_summary_markdown()` rather than inventing a second summary format.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Code `bmad-dev-story`)

### Debug Log References

Commands run from the repo root, in order:

- `PYTHONPATH=src python3 -m unittest discover -s tests` — pre-change baseline: **250 tests, OK**.
- `PYTHONPATH=src python3 -m unittest tests.test_report_summary` — 15 tests, OK (failed with `ModuleNotFoundError` before the module existed; red-green confirmed).
- `PYTHONPATH=src python3 -m unittest tests.test_championship_leaders_report` — 7 tests, OK (5 errors before the retrofit; the 2 section-survival tests passed first, which validated the pandas fixtures against the unretrofitted reports).
- `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces` — 39 tests, OK (`ImportError: cannot import name 'build_report_summaries'` before the wiring).
- `PYTHONPATH=src python3 -m unittest discover -s tests` — post-change regression: **280 tests, OK** (250 baseline + 30 new). The `FAILED swap: ...` line printed mid-run is the daily-pipeline scenario test exercising its own failure path, as the story predicted; overall result is `OK`.
- `python3 -m compileall src/f1_analytics` — clean.
- `PYTHONPATH=src python3 scripts/build_question_workflow_surfaces.py` — prints `report_summaries rows: 5`; `## Report Summary` is section 1 of the generated report (line 19, before `## Question Intake Brief` at line 61).
- `PYTHONPATH=src .venv/bin/python3 scripts/analyze_championship_leaders.py` — regenerated both championship reports. System `python3` lacks `plotly`, so the project `.venv` interpreter was used for this script only; the unit tests need no Plotly and ran on system `python3`.
- `git diff --check` (exit 0) plus a trailing-whitespace/tab grep across all seven touched files (untracked ones included) — clean.

### Completion Notes List

- **AC1 (summary leads, fields in contract order).** `REPORT_SUMMARY_FIELD_ORDER` is the single source of truth; `render_report_summary_markdown()` iterates it, and tests assert ascending `str.index()` positions rather than a hardcoded string. In the bundle report the `## Report Summary` section is emitted immediately after the portfolio-ready/limitations header and before `## Question Intake Brief` — the story-authorized change to that report's section order. Both championship reports carry the block between the H1 and their first pre-existing `##` section.
- **AC2 (reason inside the summary).** `build_report_summary()` raises `ValueError` naming every trigger that fired (status in `STATUSES_REQUIRING_REASON`, `unscoreable=True`, or `stale_basis_reason` set) when no reason is supplied, so AC2 is enforced rather than aspirational. The renderer prints the reason on the `Status` line itself (`- Status: source_blocked — <reason>`), and stale/unscoreable render as their own lines between `Status` and `Next action`.
- **AC3 (retrofit loses no detail) — verified by diff, not by assertion.** The pre-retrofit reports were snapshotted and re-generated against live DuckDB: the only change to either file is the added Report Summary block. Every pre-existing line is byte-identical, including both limitations sections. The `## Output Tables` / `## Outputs` bullet lists are now rendered from `CONVERSION_REPORT_TABLE_PATHS` / `FOLLOWUP_REPORT_OUTPUT_PATHS` (the same tuples feeding `evidence_paths`), which produces identical text and removes the chance of the evidence list drifting from the section it mirrors.
- **AC4 (extends the existing script and module).** `scripts/build_question_workflow_surfaces.py` gained one tuple entry and no logic. Module code split across `report_summary.py` (contract) and `question_workflow_surfaces.py` (bundle wiring) per the story's companion-module decision; outputs still go to `outputs/reports/` and `outputs/tables/`.
- **No fabricated answers.** All five supplied questions render `Answer: not yet computed in this bundle` with their real `pending` / `source_blocked` coverage status and reason. A test locks that no `answer_display` equals its row's `known_answer_example` and that no supplied question claims `computed` (AD-4). Q05 correctly picks up the `source_blocked` starting-tyre-compound row and names FastF1 as the candidate source.
- **Import discipline held.** `report_summary.py` imports stdlib plus `ActualAnswerStatus` only, and a test asserts the question-backtest/surface modules never appear in its source. `championship_leaders.py` imports from `report_summary` only — `ActualAnswerStatus` is re-exported through `report_summary.__all__` so that module needs no second import path, mirroring how `question_workflow_surfaces.__all__` already re-exports it.
- **Serialization decision worth flagging.** `report_summary_to_record()` serializes an absent answer as the shared `ANSWER_NOT_COMPUTED_TEXT` literal rather than an empty string, so the CSV never shows a blank answer cell that a reader could mistake for "no limitation". The sanitizer (`_neutralize_public_text`) is applied in this record function, not in `report_summary.py`, keeping the contract module sanitizer-free and importable by the Kaggle-baseline stack.
- **Not covered, by design.** The notebook (`notebooks/championship_leader_combined_analysis.ipynb`) and HTML exports were **not** retrofitted — out of scope per the story. `render_report_summary_markdown()` is the reusable primitive a future notebook cell or HTML export should call. The 16 pre-existing `deferred-work.md` findings against `question_workflow_surfaces.py` were left untouched; none blocked this work.
- **Registry correction.** The `"Report Summary"` handoff entry moved from the Open block to the Satisfied block with its real implementing modules; the registry comment and the test split were updated to 6 satisfied / 4 open / 3 blocked, count unchanged at 13.
- `report_summaries` is deliberately excluded from `_bundle_portfolio_ready()`; the comment above that function now names all three excluded surfaces, and a test asserts bundle readiness is unchanged by the new surface.

### File List

Created:

- `src/f1_analytics/analysis/report_summary.py`
- `tests/test_report_summary.py`
- `tests/test_championship_leaders_report.py`

Modified:

- `src/f1_analytics/analysis/question_workflow_surfaces.py`
- `src/f1_analytics/analysis/championship_leaders.py`
- `scripts/build_question_workflow_surfaces.py`
- `tests/test_question_workflow_surfaces.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story status tracking)
- `_bmad-output/implementation-artifacts/6-3-render-report-summary-across-generated-outputs.md` (this file)

Regenerated, gitignored output (existing paths, not new):

- `outputs/reports/question_workflow_surfaces.md`, `outputs/tables/question_workflow_surfaces.csv`
- `outputs/reports/championship_leader_conversion.md`, `outputs/reports/championship_leader_followup.md`
- `outputs/tables/*.csv`, `outputs/figures/constructor_comeback_cases.html` (rewritten unchanged by the championship analysis run)

## Change Log

- 2026-07-23: Story context created by `bmad-create-story`; status set to `ready-for-dev`.
- 2026-07-23: Implemented Story 6.3 — new `report_summary.py` contract module (field order, reason-required validation, Markdown renderer); Report Summary wired into `AnalystWorkflowSurfaceBundle` as a 7th surface rendered first; both championship-leader reports retrofitted to lead with the summary; `"Report Summary"` handoff entry moved OPEN → SATISFIED; 30 new tests added (regression 250 → 280, all passing). Status set to `review`.
- 2026-07-23: Code review (`bmad-code-review`) — all four ACs verified satisfied by an independent acceptance audit; 19 patch findings raised, 8 dismissed, 1 deferred to Story 6.4. 14 patches applied: the flat CSV regained `question_id` and its original row/column order, absent optional fields serialize as `null` again, the Markdown write is UTF-8 explicit, both championship summaries now report `partial` instead of `computed` when their sample is empty, `REPORT_SUMMARY_FIELD_ORDER` genuinely drives the renderer, the status vocabulary is enforced (Antonio's decision), and the stale `SATISFIED` handoff text was rewritten. 13 new tests lock the fixed behaviors (regression 280 → 293, all passing). 5 input-hardening guards accepted as non-blocking and recorded in `deferred-work.md`. Status set to `done`.
