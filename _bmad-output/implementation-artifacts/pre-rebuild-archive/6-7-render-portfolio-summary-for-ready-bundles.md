---
story_key: 6-7-render-portfolio-summary-for-ready-bundles
created: 2026-07-27
source_decision: _bmad-output/planning-artifacts/epics.md#Epic-6
working_tree_baseline: >-
  Uncommitted Story 6.6 (Render Analysis Mode Boundary Surface) implementation on top of commit
  cf32663, including its code-review docstring patch, plus sprint-status.yaml/deferred-work.md
  updates from Story 6.6's code review. Nothing from Story 6.6 is committed yet (see Working Tree
  State below) — do not stash, reset, or otherwise discard it.
baseline_commit: cf32663e37589b6b7276de87b66a407bf542c1f1
---

# Story 6.7: Render Portfolio Summary for Ready Bundles

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Antonio,
I want a Portfolio Summary surface for finished output bundles,
so that a public-facing reader (hiring reviewer or downstream agent) understands the question, answer, why it matters, source/cutoff basis, and limitation for each supplied question without inspecting raw tables — and so an overclaim is blocked from public-story use before it ships.

## Scope Decision

This story implements UX-DR7 (Portfolio Summary), the seventh and **final** Track 1 surface named in `deferred-work.md`'s "analyst-environment UX contract coverage gap" entry: "Portfolio Summary — public-facing 'why it matters' layer (answer, limitation, suggested story angle) over a finished output bundle." The `IMPLEMENTATION_HANDOFF_REGISTRY`'s own "Portfolio Summary" entry (`question_workflow_surfaces.py:388-400`, currently `HandoffStatus.OPEN` — the only remaining Open entry) says the same thing in its `acceptance_criteria_implication`: "Story 6.7 must render a Portfolio Summary section stating question, answer, why it matters, source/cutoff basis, limitation, and suggested public-story angle over a finished, portfolio-ready output bundle."

**Why this story's shape differs from Stories 6.1–6.6, and why that's correct, not scope creep.** Every prior Epic 6 story rendered exactly ONE already-existing computed contract (Epic 3's feature-availability contract, Epic 2's tyre/pit coverage matrix, etc.) essentially verbatim. Portfolio Summary is different: `deferred-work.md`'s own framing of item 7 ("public-facing 'why it matters' layer... over a finished output bundle") is deliberately looser than items 1–6's "surface the X contract already built in Epic Y" framing, because no single existing contract already computes "why it matters" or "a suggested public-story angle" — this story composes those two fields, once, from fields several already-existing bundle surfaces already carry (see below), and gates rendering on a boolean (`portfolio_ready`) the bundle already computes. It does **not** invent new domain logic (no new leakage rule, scoring rule, or persistence write) — it narrates and synthesizes across already-computed surfaces, which is what AD-1 permits renderers to do.

**What already exists and must be reused, not recomputed:**
- `_bundle_portfolio_ready()` (`question_workflow_surfaces.py:1567-1587`) already computes a single bundle-wide `portfolio_ready: bool` from four already-computed gates (`output_checklist`, `intake_briefs`, `catalog_rows`, `source_coverage`, `source_status_limitations`). This story's builder takes that **already-computed** boolean as a parameter — it must never call `_bundle_portfolio_ready()` itself or reimplement any of its four gate checks.
- `ReportSummary` (`report_summary.py`, already wired into this bundle as `bundle.report_summaries`) already carries, per Question ID (`subject`): `question`, `answer_display` (always `None` today — no Actual Answer Components are wired into this bundle yet, see `build_report_summaries()`'s own comment at `question_workflow_surfaces.py:710-713`), `source_and_cutoff_basis`, `reason`, `stale_basis_reason`. Reuse every one of these verbatim; do not reformat the source/cutoff basis text or reinvent an answer-display fallback (`ANSWER_NOT_COMPUTED_TEXT`, already imported at line 40, is the existing fallback — reuse it, do not invent a second one).
- `QuestionIntakeBriefSurface.intended_output` (`question_workflow_surfaces.py:77-96`) is an existing, already-populated per-question field — the analyst's own stated purpose for the question at intake time — and is not yet surfaced anywhere public-facing today (it feeds no other surface's rendered output). This is the correct, already-computed source for `why_it_matters`: reusing an existing field under new framing, exactly like Story 6.6 reused `feature_snapshot_boundary_summary` under new framing.
- `QuestionIntakeBriefSurface.blocking_reasons`, `QuestionCatalogRowSurface.blocking_reasons`, and `SourceCoverageMatrixSurfaceRow.reason` (on rows whose `target_readiness_gate`/`score_readiness_gate` are not `"ready"`) are the already-computed, per-question explanations for why a question isn't ready. `OutputBundleChecklistItem.failure_reason` and the bundle's own `source_status_limitations` tuple are the bundle-wide equivalents. This story's "why is this question not portfolio-ready" text is assembled entirely from these four already-computed sources — it adds no new blocking-reason logic.

**What genuinely is new in this story (and the only new logic it introduces):** a new dataclass field `portfolio_status` with exactly three surface-only values — `"portfolio_ready"`, `"overclaim_detected"`, `"not_portfolio_ready"` — and the small amount of glue that decides which of the three applies to a given question from already-computed facts:
- `"not_portfolio_ready"`: whenever `bundle.portfolio_ready` is `False` (the live case for all five supplied PDF questions today — confirmed live via the generated report's `Portfolio-ready: no` line).
- `"overclaim_detected"`: whenever `bundle.portfolio_ready` is `True` **but** that specific question's `ReportSummary.answer_display` is still `None` — i.e., the bundle claims the whole set is ready while a specific question has no computed answer to show. This directly implements AC2's "a claim... would overstate... certainty": claiming portfolio-readiness without an actual answer for a question is the overclaim. **Not reachable with today's live data** (since `portfolio_ready` is always `False` today), exactly like Story 6.6's `boundary_status == "leakage_safe"` was not reachable with today's live data — the code must not hard-code today's always-`False` value, and a test must construct a synthetic bundle to exercise this branch.
- `"portfolio_ready"`: whenever `bundle.portfolio_ready` is `True` **and** that question's `ReportSummary.answer_display` is present. Also not reachable with today's live data, for the same reason. A test must construct a synthetic bundle to exercise this branch too.
- `suggested_public_story_angle` is composed **only** in the `"portfolio_ready"` case, as a single deterministic sentence built from three already-computed `ReportSummary` fields (`question`, `answer_display`, `source_and_cutoff_basis`) — no new judgment, no new source, pure string composition (narration, per AD-1). It is an empty string in the other two states.

**AC2's "never uses betting, odds, gambling, or wagering framing" clause is enforced by the existing, file-wide `_neutralize_public_text()` sanitizer** (`question_workflow_surfaces.py:1743-1749`, `FORBIDDEN_PUBLIC_FRAMING_TERMS` already imported at line 15) — this story adds no new sanitizer. Unlike Story 6.6's `analysis_mode_boundary_surface_to_record()` (which left its `blocked_fact_groups` tuple unneutralized — a gap recorded in `deferred-work.md`'s Story 6.6 entry), this story's `portfolio_summary_surface_to_record()` must neutralize **every** free-text field, matching `report_summary_to_record()`'s own thorough precedent (`question_workflow_surfaces.py:938-952`, which neutralizes `question`, `answer_display`, and `source_and_cutoff_basis`, not just `reason`-shaped fields) — do not repeat Story 6.6's narrower gap a second time.

**Out of scope — do not do these:**
- Do not import or call anything from `question_predictions.py`, `question_backtest_scoring.py`, `question_backtest_report.py`, or `question_backtest_explanations.py` beyond the two enum re-exports and one constant this module already borrows (`ReportRowOutcome`, `Scoreability`, `FORBIDDEN_PUBLIC_FRAMING_TERMS`). Confirmed live: no `build_supplied_pdf_...`-style, no-argument entry point exists anywhere in the repo chaining baseline Predictions → scoring → backtest report rows → portfolio explanations for the five supplied questions — every function in those four modules requires caller-constructed `PredictionInput`/`ActualAnswerComponent` values that no live extractor or persisted store produces today (confirmed by `tests/test_question_backtest_report.py`'s own synthetic fixture helpers being the only place such values are built). Wiring that chain in is exactly the still-open epic-3 persistence-surface decision and epic-5 live-DuckDB-wiring decision (`sprint-status.yaml` action_items) — it is why `IMPLEMENTATION_HANDOFF_REGISTRY`'s "Target Store Review", "Scoring and Baseline Review", and "Discrepancy Panel" entries stay `HandoffStatus.BLOCKED` in the very same registry this story's own entry sits in as the last Track 1 (buildable-now) surface. Building that chain would fabricate a live-wiring dependency this bundle doesn't actually have.
- Do not touch `_bundle_portfolio_ready()`'s logic, inputs, or signature. This story reads its already-computed `bool` result (passed as a parameter into the new builder) — it does not change how that boolean is computed, and does not add a fifth gate to it.
- Do not call `render_status_badge()` inside `portfolio_summary_surface_to_record()` — every existing `_to_record()` function in this file emits the raw, unbracketed status value; only the Markdown renderer applies the badge (same convention Story 6.6 followed).
- Do not fabricate a fourth `portfolio_status` value, an icon table, or a numeric "confidence score" — the three values above are exhaustive for this surface's actual shape (ready-with-answer, ready-without-answer, not-ready).
- Do not reorder any existing `## ` section heading in `render_analyst_workflow_surface_markdown()`. Insert `## Portfolio Summary` as one new block only, immediately before `## Implementation Handoff` (matching `EXPERIENCE.md`'s Information Architecture table, where Portfolio Summary is listed directly before Implementation Handoff, line 41 vs. line 42).
- Do not add a "portfolio-ready" CLI flag or mode switch to `build_question_workflow_surfaces.py` or `build_supplied_pdf_analyst_workflow_surface_bundle()` — AC1/AC3 both require the surface to render the correct state for whatever the bundle's already-computed `portfolio_ready` happens to be, not a runtime toggle.
- Do not touch `question_predictions.py`, `question_backtest_scoring.py`, `question_backtest_report.py`, `question_backtest_explanations.py`, `question_feature_availability.py`, `question_catalog.py`, `report_summary.py`, `status_badge.py`, `evidence_link.py`, or `question_answers.py`. Verify none of them need a change before writing code; if one turns out to, say so in the Dev Agent Record rather than silently widening the diff.
- Do not touch `IMPLEMENTATION_HANDOFF_REGISTRY`'s `status_rule` or `acceptance_criteria_implication` text for the Portfolio Summary entry — both already accurately describe the satisfied behavior; only `implemented_module_or_script` and `handoff_status` change (same pattern Stories 6.5/6.6 used for their own registry entries).

## Acceptance Criteria

1. Given a cataloged question's Report Summary, Source Coverage Matrix, Output Bundle Checklist, Question Intake Brief, and Question Catalog Row surfaces all indicate the bundle is portfolio-ready (`bundle.portfolio_ready is True`) and that question's Report Summary carries a computed `answer_display`, when the Portfolio Summary surface is generated for it, then it states the question, answer, why it matters (from the question's own intake `intended_output`), source/cutoff basis, limitation, and a suggested public-story angle — composed entirely from already-computed bundle surfaces, with no new leakage, scoring, or persistence logic added.
2. Given the bundle is marked portfolio-ready but a specific question's Report Summary has not yet computed an `answer_display` (still `None`), when the Portfolio Summary is evaluated for that question, then an overclaim is detected (`portfolio_status == "overclaim_detected"`), it blocks public-story use by naming the missing-answer condition in that question's `blocking_reasons`, and the rendered summary never uses betting, odds, gambling, or wagering framing (enforced by the existing file-wide `_neutralize_public_text()` sanitizer).
3. Given a question is not yet portfolio-ready (`bundle.portfolio_ready is False` — the live case for all five supplied PDF questions today), when the Portfolio Summary surface is evaluated for it, then it does not render a `"portfolio_ready"` summary for that question, and instead states which already-computed surface or status is blocking readiness — drawn first from that question's own Question Intake Brief / Question Catalog Row / Source Coverage Matrix blocking signals, falling back to the bundle-wide Output Bundle Checklist failure reasons and source-status limitations only when no question-specific signal exists.
4. Given the surface is generated, when output is written, then it extends the existing `scripts/build_question_workflow_surfaces.py` script; module-level code extends `question_workflow_surfaces.py` with focused new functions (no new file — matching the single-module convention every prior Epic 6 story has used); and it writes to `outputs/reports/` and/or `outputs/tables/`.

## Tasks / Subtasks

- [x] Add the `PortfolioSummarySurface` dataclass. (AC: 1, 2, 3)
  - [x] In `src/f1_analytics/analysis/question_workflow_surfaces.py`, insert a new `@dataclass(frozen=True)` immediately after `ImplementationHandoffSurface` (currently ends ~line 209) and before `AnalystWorkflowSurfaceBundle` (currently starts ~line 212) — it is the last per-surface dataclass, matching its position as the last surface-record field in the bundle:
    ```python
    @dataclass(frozen=True)
    class PortfolioSummarySurface:
        """Portfolio Summary surface for one Question ID's finished (or not-yet-finished) bundle."""

        question_id: str
        portfolio_status: str
        question: str
        answer_display: str
        why_it_matters: str
        source_and_cutoff_basis: str
        limitation: str
        suggested_public_story_angle: str
        blocking_reasons: tuple[str, ...]

        def to_record(self) -> dict[str, object]:
            """Return a deterministic plain-value record for CSV/report use."""
            return portfolio_summary_surface_to_record(self)
    ```

- [x] Add `build_portfolio_summary_surfaces()`. (AC: 1, 2, 3)
  - [x] Insert it immediately after `build_implementation_handoff_surfaces()` (currently ends ~line 763) and before `build_supplied_pdf_analyst_workflow_surface_bundle()` (currently starts ~line 764) — it is the last `build_*` surface function, since it synthesizes over every other already-built surface:
    ```python
    def build_portfolio_summary_surfaces(
        intake_briefs: Iterable[QuestionIntakeBriefSurface],
        catalog_rows: Iterable[QuestionCatalogRowSurface],
        source_coverage: Iterable[SourceCoverageMatrixSurfaceRow],
        output_checklist: Iterable[OutputBundleChecklistItem],
        report_summaries: Iterable[ReportSummary],
        portfolio_ready: bool,
        source_status_limitations: tuple[str, ...],
    ) -> tuple[PortfolioSummarySurface, ...]:
        """Build one Portfolio Summary per Question ID from already-built bundle surfaces.

        Reuses the bundle's own already-computed `portfolio_ready` gate (from
        `_bundle_portfolio_ready()`, passed in rather than recomputed) as the single
        readiness signal applied to every question, exactly like
        `build_analysis_mode_boundary_surfaces()` reuses one aggregate contract across
        every row. Composes `why_it_matters` from the question's own
        `QuestionIntakeBriefSurface.intended_output` and `suggested_public_story_angle`
        from the question's own `ReportSummary` fields — narration over already-computed
        facts, not a new domain computation. Adds no new leakage, scoring, or persistence
        logic, and calls nothing in `question_predictions.py`, `question_backtest_scoring.py`,
        `question_backtest_report.py`, or `question_backtest_explanations.py`: those all
        require live Actual Answer Components / baseline Predictions this bundle does not
        have (see the epic-3 persistence and epic-5 live-wiring decisions that keep Target
        Store Review / Scoring and Baseline Review / Discrepancy Panel BLOCKED in
        `IMPLEMENTATION_HANDOFF_REGISTRY`).

        `portfolio_status` is a new, minimal, three-value surface vocabulary:
        `"portfolio_ready"` (bundle ready and this question has a computed answer — not
        reachable today, since `portfolio_ready` is always `False` for the current
        5-question bundle, but the code must not hard-code that), `"overclaim_detected"`
        (bundle claims ready but this question's `ReportSummary.answer_display` is still
        `None` — also not reachable today for the same reason, but a real defensive check
        against the bundle-level gate and the per-question answer ever disagreeing), and
        `"not_portfolio_ready"` (the live case today, for all five supplied questions).

        Args:
            intake_briefs, catalog_rows, source_coverage, output_checklist, report_summaries:
                the bundle's own already-built surfaces for the same question scope.
            portfolio_ready: the bundle's own already-computed `_bundle_portfolio_ready()`
                result — passed in, never recomputed here.
            source_status_limitations: the bundle's own already-computed bundle-wide
                source-status limitation strings.

        Returns:
            One `PortfolioSummarySurface` per entry in `report_summaries`, in that order.

        Failure behavior: adds no new validation; a `question_id` present in
        `report_summaries` but absent from `intake_briefs` degrades to an empty
        `why_it_matters` rather than raising, matching this file's general
        trust-the-caller-supplied-scope convention for internal builder inputs.
        """
        intake_by_id = {surface.question_id: surface for surface in intake_briefs}
        catalog_by_id = {surface.question_id: surface for surface in catalog_rows}
        coverage_by_id: dict[str, list[SourceCoverageMatrixSurfaceRow]] = {}
        for row in source_coverage:
            coverage_by_id.setdefault(row.question_id, []).append(row)
        artifact_blocking_reasons = tuple(
            f"{item.artifact_label}: {item.failure_reason}"
            for item in output_checklist
            if not item.portfolio_ready and _has_summary_text(item.failure_reason)
        )

        surfaces = []
        for summary in report_summaries:
            question_id = summary.subject
            intake = intake_by_id.get(question_id)
            catalog = catalog_by_id.get(question_id)

            question_blocking_reasons: list[str] = []
            if intake is not None and intake.intake_status != "ready":
                question_blocking_reasons.extend(intake.blocking_reasons)
            if catalog is not None and catalog.metadata_validation_status != "valid":
                question_blocking_reasons.extend(catalog.blocking_reasons)
            for coverage_row in coverage_by_id.get(question_id, ()):
                if coverage_row.target_readiness_gate != "ready" or coverage_row.score_readiness_gate != "ready":
                    question_blocking_reasons.append(f"{coverage_row.fact_label}: {coverage_row.reason}")

            answer_display = (
                summary.answer_display if _has_summary_text(summary.answer_display) else ANSWER_NOT_COMPUTED_TEXT
            )
            why_it_matters = intake.intended_output if intake is not None else ""
            limitation = (
                summary.reason
                or summary.stale_basis_reason
                or "No limitation currently recorded for this question."
            )

            # `portfolio_ready` is a bundle-wide `all(...)` gate (see `_bundle_portfolio_ready()`),
            # so when it is True every question's own intake/catalog/source-coverage checks above
            # are already guaranteed empty — `question_blocking_reasons` is reset explicitly in
            # both branches below anyway, so this never silently carries over a stale reason.
            if not portfolio_ready:
                portfolio_status = "not_portfolio_ready"
                suggested_public_story_angle = ""
                if not question_blocking_reasons:
                    question_blocking_reasons = list(artifact_blocking_reasons) + list(source_status_limitations)
            elif not _has_summary_text(summary.answer_display):
                portfolio_status = "overclaim_detected"
                suggested_public_story_angle = ""
                question_blocking_reasons = [
                    f"Bundle is marked portfolio-ready but {question_id} has no computed answer yet."
                ]
            else:
                portfolio_status = "portfolio_ready"
                suggested_public_story_angle = (
                    f"{summary.question} — {summary.answer_display}, based on {summary.source_and_cutoff_basis}."
                )
                question_blocking_reasons = []

            surfaces.append(
                PortfolioSummarySurface(
                    question_id=question_id,
                    portfolio_status=portfolio_status,
                    question=summary.question,
                    answer_display=answer_display,
                    why_it_matters=why_it_matters,
                    source_and_cutoff_basis=summary.source_and_cutoff_basis,
                    limitation=limitation,
                    suggested_public_story_angle=suggested_public_story_angle,
                    blocking_reasons=tuple(question_blocking_reasons),
                )
            )
        return tuple(surfaces)
    ```
  - [x] Reuse `_has_summary_text()` (~line 1729, already used by `report_summary_to_record()` for this exact "is this optional text present" check) and `ANSWER_NOT_COMPUTED_TEXT` (already imported at line 40) — do not write a second "is answer present" helper or a second not-yet-computed literal.
  - [x] `summary.subject` is the question ID (confirmed: `build_report_summaries()` sets `subject=row.question_id`, `report_summary.py`'s own docstring: "`subject` names what the summary is about — a Question ID..."). Do not look up `question_id` any other way.

- [x] Add `portfolio_summary_surface_to_record()`. (AC: 1, 2, 4)
  - [x] Insert it immediately after `report_summary_to_record()` (currently ends ~line 952) and before `analyst_workflow_surface_bundle_to_records()` (currently starts ~line 955):
    ```python
    def portfolio_summary_surface_to_record(surface: PortfolioSummarySurface) -> dict[str, object]:
        """Serialize one Portfolio Summary surface into plain Python values.

        Neutralizes every free-text field, matching `report_summary_to_record()`'s
        thorough precedent (not just `reason`-shaped fields) — unlike Story 6.6's
        `analysis_mode_boundary_surface_to_record()`, whose unneutralized
        `blocked_fact_groups` tuple was recorded as deferred debt; this surface does
        not repeat that gap.
        """
        return {
            "question_id": surface.question_id,
            "portfolio_status": surface.portfolio_status,
            "question": _neutralize_public_text(surface.question),
            "answer_display": _neutralize_public_text(surface.answer_display),
            "why_it_matters": _neutralize_public_text(surface.why_it_matters),
            "source_and_cutoff_basis": _neutralize_public_text(surface.source_and_cutoff_basis),
            "limitation": _neutralize_public_text(surface.limitation),
            "suggested_public_story_angle": _neutralize_public_text(surface.suggested_public_story_angle),
            "blocking_reasons": tuple(_neutralize_public_text(reason) for reason in surface.blocking_reasons),
        }
    ```
  - [x] Do not call `render_status_badge()` here — see the "Out of scope" note above.

- [x] Wire the new surface into the bundle dataclass and builder. (AC: 1, 3, 4)
  - [x] In `AnalystWorkflowSurfaceBundle` (~lines 212-224), add a new field `portfolio_summary: tuple[PortfolioSummarySurface, ...]` — place it immediately after `report_summaries` and before `portfolio_ready` (the two remaining fields are bundle-level scalars, not surface-record tuples, so the new tuple field belongs with the other surface-record tuples above them).
  - [x] In `build_supplied_pdf_analyst_workflow_surface_bundle()` (~lines 764-815), add `portfolio_summary = build_portfolio_summary_surfaces(intake_briefs, catalog_row_surfaces, source_coverage, output_checklist, report_summaries, portfolio_ready, source_status_limitations)` **immediately after** `portfolio_ready = _bundle_portfolio_ready(...)` is computed (this function needs that boolean as an input) and pass `portfolio_summary=portfolio_summary` into the returned `AnalystWorkflowSurfaceBundle(...)` call, in the same field position (after `report_summaries=report_summaries,`, before `portfolio_ready=portfolio_ready,`).

- [x] Wire the new surface into serialization and the flat CSV. (AC: 4)
  - [x] In `analyst_workflow_surface_bundle_to_records()` (~lines 955-976), add:
    ```python
    "portfolio_summary": tuple(
        portfolio_summary_surface_to_record(surface) for surface in bundle.portfolio_summary
    ),
    ```
    placed after the `"report_summaries"` entry (this dict has no keys for `portfolio_ready`/`source_status_limitations`, so `"portfolio_summary"` becomes the new last key).
  - [x] In `_flat_surface_records()` (~lines 1610-1632), add `"portfolio_summary"` to the surface-type iteration tuple, immediately after `"report_summaries"` (the new last entry). Update the comment directly above the tuple (currently lines 1613-1616, "Report Summary leads the Markdown report... but stays last here...") to note that Portfolio Summary is the one exception that comes after it, since it synthesizes over every other surface's already-computed status **including** Report Summary's — e.g., append: "Portfolio Summary is the sole exception placed after it, since it synthesizes over every other surface here, Report Summary included, and must therefore build (and serialize) last."
  - [x] In `_status_field_for_surface_type()` (~lines 1635-1645), add `"portfolio_summary": "portfolio_status",` to the mapping dict, as the new last entry.

- [x] Render the new Markdown section. (AC: 1, 2, 3)
  - [x] In `render_analyst_workflow_surface_markdown()` (~lines 997-1104), insert a new block immediately after the `## Reuse And Extension Review` loop (~ends line 1090) and before the `## Implementation Handoff` heading (~line 1091) — matching `EXPERIENCE.md`'s Information Architecture table, where Portfolio Summary is listed directly before Implementation Handoff:
    ```python
    lines.extend(["", "## Portfolio Summary"])
    for surface in bundle.portfolio_summary:
        lines.extend(
            [
                f"- {surface.question_id}",
                f"  - Status: {render_status_badge(surface.portfolio_status)}",
                f"  - Question: {surface.question}",
                f"  - Answer: {surface.answer_display}",
                f"  - Why it matters: {surface.why_it_matters}",
                f"  - Source/cutoff basis: {surface.source_and_cutoff_basis}",
                f"  - Limitation: {surface.limitation}",
                f"  - Suggested public-story angle: "
                f"{surface.suggested_public_story_angle or 'Not available — see blocking reasons.'}",
                f"  - Blocking reasons: {_limitations_text(surface.blocking_reasons)}",
            ]
        )
    ```
  - [x] Do not manually call `_neutralize_public_text()` on the scalar fields here (`question`, `answer_display`, `why_it_matters`, `source_and_cutoff_basis`, `limitation`, `suggested_public_story_angle`) — matching every other section's convention in this renderer (e.g. Analysis Mode Boundary's `- Reason:` line), the whole rendered document is passed through one final `_neutralize_public_text()` call at the end of this function. `_limitations_text()` for `blocking_reasons` already neutralizes each item itself (it always has, for every other tuple-of-reasons field this renderer uses it for) — reuse it as-is, do not write a second joiner.
  - [x] This satisfies AC2 directly: the `- Status:` badge (`[OVERCLAIM_DETECTED]`) plus the `- Blocking reasons:` line naming the missing-answer condition makes clear that public-story use is not claimed for that question; the final blanket neutralization pass guarantees no forbidden framing term survives into the rendered output regardless of which upstream free-text field it came from.

- [x] Move the `IMPLEMENTATION_HANDOFF_REGISTRY`'s "Portfolio Summary" entry from Open to Satisfied. (AC: 4)
  - [x] In `IMPLEMENTATION_HANDOFF_REGISTRY` (~line 259), move the `"Portfolio Summary"` tuple (currently in the `# --- Open ---` block, ~lines 388-400) into the `# --- Satisfied ---` block, immediately after "Analysis Mode Boundary" (the current last satisfied entry). Set `implemented_module_or_script` to `"question_workflow_surfaces.build_portfolio_summary_surfaces / question_workflow_surfaces.render_analyst_workflow_surface_markdown"` and `handoff_status` to `HandoffStatus.SATISFIED`. Leave `status_rule` and `acceptance_criteria_implication` text unchanged — both already describe the satisfied behavior accurately.
  - [x] Since Portfolio Summary was the only entry in the `# --- Open: Track 1... ---` block, that comment line (currently ~line 387, `# --- Open: Track 1, buildable now, not yet implemented (remaining Epic 6 stories) ---`) becomes dead — remove it (there is nothing left under it once the tuple moves), so the tuple sequence goes directly from the last Satisfied entry into the `# --- Blocked: Track 2... ---` comment.
  - [x] Update the registry header comment (currently, verbatim):
    ```
    # Registry of all 13 Implementation Handoff entries: 9 satisfied (Epic 5 + Stories 6.1, 6.3, 6.4,
    # 6.5, and 6.6), 1 open Track 1 surface (Story 6.7, the remaining Epic 6 story), 3 blocked Track 2
    # surfaces (gated on open sprint-status.yaml action_items). See deferred-work.md's
    # "analyst-environment UX contract coverage gap" entry (2026-07-22) for the Track 1 / Track 2 split
    # this registry mirrors.
    ```
    to:
    ```
    # Registry of all 13 Implementation Handoff entries: 10 satisfied (Epic 5 + Stories 6.1, 6.3, 6.4,
    # 6.5, 6.6, and 6.7 — all seven Track 1 surfaces now implemented), 0 open Track 1 surfaces, 3
    # blocked Track 2 surfaces (gated on open sprint-status.yaml action_items). See deferred-work.md's
    # "analyst-environment UX contract coverage gap" entry (2026-07-22) for the Track 1 / Track 2 split
    # this registry mirrors.
    ```
  - [x] Update the inline block comment immediately above the Satisfied block, from `# --- Satisfied: Epic 5 / Stories 6.1, 6.3, 6.4, 6.5, and 6.6, already implemented ---` to `# --- Satisfied: Epic 5 / Stories 6.1, 6.3, 6.4, 6.5, 6.6, and 6.7, already implemented ---`.
  - [x] **Required regression fix:** in `tests/test_question_workflow_surfaces.py` (`ImplementationHandoffSurfaceTests`, ~lines 406-424), move `"Portfolio Summary"` from `OPEN_UX_SURFACES` to `SATISFIED_UX_SURFACES`. `OPEN_UX_SURFACES` becomes `()` (empty tuple) — this is expected, not a mistake; **do not delete** `test_open_track_one_surfaces_are_ready_without_an_implementation_yet` (it becomes a vacuous pass over an empty tuple, which is correct: it preserves the test's shape for any future Track 1 surface a later epic might add). The total-count assertion (`test_registry_returns_exactly_thirteen_unique_surfaces`) stays at 13; the satisfied/open/blocked split becomes 10/0/3.

- [x] Extend the `__all__` export list. (AC: 4)
  - [x] Add `"PortfolioSummarySurface"`, `"build_portfolio_summary_surfaces"`, and `"portfolio_summary_surface_to_record"` to `__all__` (~lines 1787-1829), placed near each name's alphabetical neighbors — the list is roughly, not strictly, alphabetical already, and no test enforces `__all__` ordering.

- [x] Extend the script's row-count summary. (AC: 4)
  - [x] In `scripts/build_question_workflow_surfaces.py`, add `"portfolio_summary"` to the `for surface_type in (...)` print loop (currently lines 54-63), as the new last entry (after `"implementation_handoff"`). No other change to this script is needed: `build_supplied_pdf_analyst_workflow_surface_bundle()` and `write_analyst_workflow_surface_bundle()` are called with the same arguments and same output paths as before — the new surface rides along inside the existing bundle/write calls.

- [x] **Required regression fix:** update the bundle-serialization key-set assertion. (AC: 4)
  - [x] In `tests/test_question_workflow_surfaces.py::AnalystWorkflowSurfaceSerializationTests::test_bundle_serialization_uses_plain_values_and_controlled_status_strings` (~lines 787-825, the exact-key-set assertion around line 801-810), add `"portfolio_summary"` to the expected key set or this test will fail as soon as the new surface type is wired in — this is not optional cleanup, it is a required fix caused directly by this story's own change.

- [x] **Required regression fix:** update the "Report Summary stays last in the flat CSV" test. (AC: 4)
  - [x] `tests/test_question_workflow_surfaces.py::ReportSummarySurfaceTests::test_flat_csv_keeps_report_summaries_last_and_appends_their_columns` (~line 741) asserts `self.assertEqual(["report_summaries"] * 5, surface_types[-5:])` — this **will fail** once `"portfolio_summary"` is appended after `"report_summaries"` in `_flat_surface_records()`'s iteration tuple, because the flat CSV's actual last 5 rows become `portfolio_summary` rows, not `report_summaries` rows. Update the assertion to check both blocks, e.g. `self.assertEqual(["report_summaries"] * 5, surface_types[-10:-5])` and `self.assertEqual(["portfolio_summary"] * 5, surface_types[-5:])`, and update the test's explanatory comment (currently: "The Report Summary leads the Markdown report but must not reorder the CSV...") to note Portfolio Summary is now the sole surface type appended after it. This is a required fix caused directly by this story's own change, not optional cleanup — the same category as the two regression fixes above.

- [x] Add tests for the new surface. (AC: 1-4)
  - [x] In `tests/test_question_workflow_surfaces.py`, add `PortfolioSummarySurface`, `build_portfolio_summary_surfaces`, `portfolio_summary_surface_to_record` to the existing `from f1_analytics.analysis.question_workflow_surfaces import (...)` block, keeping alphabetical order. The file currently imports only `ANSWER_NOT_COMPUTED_TEXT` from `report_summary.py` (not `ReportSummary` the dataclass, and not `build_report_summary` — confirm before writing fixtures) — add `from f1_analytics.analysis.report_summary import ReportSummary, build_report_summary` (or extend the existing `report_summary` import line) since the new tests construct `ReportSummary` fixtures directly.
  - [x] New test class `PortfolioSummarySurfaceTests`, placed after `ReportSummarySurfaceTests` (~ends line 786) and before `AnalystWorkflowSurfaceSerializationTests` (~starts line 787):
    - `test_live_supplied_bundle_reports_not_portfolio_ready_for_every_question` (AC3): call `build_supplied_pdf_analyst_workflow_surface_bundle()` with no raw-data arguments (matching every other live-bundle test in this file), assert `len(bundle.portfolio_summary) == 5`, assert every surface has `portfolio_status == "not_portfolio_ready"`, and assert every surface's `blocking_reasons` is non-empty (confirmed live: all five supplied questions currently have real per-question blocking reasons from intake/catalog/source-coverage — this is the one branch reachable with today's live data, unlike the other two).
    - `test_overclaim_detected_when_bundle_is_ready_but_answer_is_not_computed` (AC2): construct a synthetic `PortfolioSummarySurface` scenario by calling `build_portfolio_summary_surfaces()` directly with hand-built `intake_briefs`/`catalog_rows`/`source_coverage`/`output_checklist`/`report_summaries` fixtures (a single question, `report_summaries` containing one `ReportSummary` with `answer_display=None`) and `portfolio_ready=True`; assert `portfolio_status == "overclaim_detected"`, assert `blocking_reasons` names the missing-answer condition, and assert `suggested_public_story_angle == ""`.
    - `test_portfolio_ready_composes_suggested_public_story_angle_from_existing_fields` (AC1): same direct-call approach, `portfolio_ready=True` with a `ReportSummary` whose `answer_display` is a non-blank string; assert `portfolio_status == "portfolio_ready"`, assert `blocking_reasons == ()`, and assert `suggested_public_story_angle` contains the fixture's `question`, `answer_display`, and `source_and_cutoff_basis` substrings (proving it's composed from those three fields, not fabricated).
    - `test_serialization_neutralizes_every_free_text_field` (AC2): build a fixture whose `intended_output` (feeding `why_it_matters`) contains a forbidden term (e.g. `"informs betting decisions"`); call `portfolio_summary_surface_to_record()`; assert none of `record["why_it_matters"]`, `record["question"]`, `record["answer_display"]`, `record["source_and_cutoff_basis"]`, `record["limitation"]`, `record["suggested_public_story_angle"]`, or any string in `record["blocking_reasons"]` contains any of `FORBIDDEN_PUBLIC_FRAMING_TERMS`; assert `record["blocking_reasons"]` is a `tuple`.
  - [x] In `AnalystWorkflowSurfaceSerializationTests`, extend `test_writer_creates_markdown_and_csv_artifacts_with_status_near_surface_summary` (or add a new assertion) confirming the written Markdown contains `"## Portfolio Summary"` and, within that section, a `"- Blocking reasons:"` line for at least one question (regression lock for AC3's live-reachable path).
  - [x] In `StatusBadgeRenderingTests`, add `test_portfolio_summary_status_lines_use_the_controlled_three_value_vocabulary`: render the bundle, extract the `## Portfolio Summary` section (same `markdown.split("## Portfolio Summary", 1)[1].split("## ", 1)[0]` pattern already used for other sections), assert every `- Status:` line in that section matches `{"[PORTFOLIO_READY]", "[OVERCLAIM_DETECTED]", "[NOT_PORTFOLIO_READY]"}`.
  - [x] Add `test_flat_csv_portfolio_summary_status_column_stays_unbracketed`, mirroring the equivalent Analysis Mode Boundary test: write the bundle, read the CSV, filter rows where `surface_type == "portfolio_summary"`, assert none of their `status` values contain `"["`.

- [x] Verify and log the result in this story's Dev Agent Record. (AC: 1-4)
  - [x] `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces`
  - [x] `PYTHONPATH=src python3 -m unittest discover -s tests` (full regression; baseline confirmed at story-creation time is **329 tests passing** — expect 329 + however many new tests were added, all passing)
  - [x] `python3 -m compileall src/f1_analytics`
  - [x] `PYTHONPATH=src python3 scripts/build_question_workflow_surfaces.py` — inspect `outputs/reports/question_workflow_surfaces.md`: confirm a `## Portfolio Summary` section exists with 5 entries (one per supplied question), all `[NOT_PORTFOLIO_READY]` given today's live data, each with a non-empty `- Blocking reasons:` line; confirm `outputs/tables/question_workflow_surfaces.csv` has 5 rows with `surface_type == "portfolio_summary"` and an unbracketed `status` column.
  - [x] `git diff --check` on all touched tracked files.

### Review Findings

- [ ] [Review][Decision — BLOCKING] "Why it matters" always renders a hardcoded literal, not real per-question content — `why_it_matters = intake.intended_output` (`src/f1_analytics/analysis/question_workflow_surfaces.py:864`) sources from `QuestionIntakeBriefSurface.intended_output`, but `build_question_intake_brief_surfaces()` defaults that field to the literal `"markdown_report_and_csv_table"` (`question_workflow_surfaces.py:468`) and the live call site (`question_workflow_surfaces.py:921`) never overrides it. Confirmed live: running `scripts/build_question_workflow_surfaces.py` renders the identical line `- Why it matters: markdown_report_and_csv_table` for all 5 supplied questions (Melbourne lap time, Miami finish, etc.) — an internal output-format label, not an explanation of why the question matters. This contradicts the story's own Scope Decision characterization of `intended_output` as "the analyst's own stated purpose for the question at intake time," and undercuts AC1's stated purpose for this surface. No other existing field in `QuestionIntakeBriefSurface` (or elsewhere reused by this story) carries genuine per-question "why it matters" narrative, so a code-only fix isn't available without either adding a new data source (new scope) or accepting this as a known live-data limitation. **Resolution (2026-07-27, Antonio): treat as blocking — story stays `in-progress`, not `done`, until follow-up work supplies real per-question "why it matters" content.** Tracked as a new epic-6 action item in `sprint-status.yaml` (see below); a follow-up story must add genuine per-question intake authoring (or an equivalent already-computed source) for `intended_output`/`why_it_matters` before this surface can be considered complete.
- [x] [Review][Patch] `blocking_reasons` can render empty (`"none"`) for a `not_portfolio_ready` question with no ultimate fallback [src/f1_analytics/analysis/question_workflow_surfaces.py:873-879]. If a question's own intake/catalog/source-coverage checks are all clean but the bundle is still not portfolio-ready (e.g. another question is blocking) and `output_checklist`/`source_status_limitations` are also both empty, `question_blocking_reasons` stays `()`. The renderer then prints `- Status: [NOT_PORTFOLIO_READY]` immediately above `- Blocking reasons: none` and `- Suggested public-story angle: Not available — see blocking reasons.` — pointing the reader at an explanation that isn't there. Not reachable with today's 5-question live bundle (every question currently carries its own real blocking reason, per `test_live_supplied_bundle_reports_not_portfolio_ready_for_every_question`'s own assertion), but the fallback chain has no terminal default, unlike `limitation`'s equivalent composition which does. **Fixed:** added a terminal default string when all three reason sources are empty; added `test_not_ready_falls_back_to_output_checklist_failure_reasons_when_question_has_none`, `test_not_ready_prefers_question_specific_reasons_over_bundle_wide_fallback`, and `test_not_ready_uses_terminal_default_when_no_reason_exists_anywhere`.
- [x] [Review][Patch] `limitation` composition uses plain truthiness instead of the file's own `_has_summary_text()` convention [src/f1_analytics/analysis/question_workflow_surfaces.py:865-868]: `summary.reason or summary.stale_basis_reason or "No limitation currently recorded..."` would treat a whitespace-only `reason`/`stale_basis_reason` as present (Python truthiness), rendering blank/whitespace instead of falling through to the default text — inconsistent with `answer_display`'s and `artifact_blocking_reasons`'s use of `_has_summary_text()` a few lines above in this same function for the identical "is this optional text present" check. **Fixed:** rewrote as explicit `_has_summary_text()` checks; added `test_limitation_falls_through_whitespace_only_reason_to_stale_basis_reason`.
- [x] [Review][Patch] Unused `ReportSummary` import in `tests/test_question_workflow_surfaces.py:19` — `from f1_analytics.analysis.report_summary import ANSWER_NOT_COMPUTED_TEXT, ReportSummary, build_report_summary` imports the `ReportSummary` dataclass, but every new `PortfolioSummarySurfaceTests` fixture constructs summaries via the `build_report_summary()` factory instead; `ReportSummary` appears nowhere else in the file. **Fixed:** removed the unused import.
- [x] [Review][Defer] `suggested_public_story_angle`'s composed sentence unconditionally appends a trailing period after `summary.source_and_cutoff_basis` [src/f1_analytics/analysis/question_workflow_surfaces.py:889] — if that already-computed, freeform field ever ends in its own punctuation, the sentence would read with doubled punctuation. Not reachable today (the `portfolio_ready` branch is unreachable with live data, since `bundle.portfolio_ready` is always `False` for the current 5-question bundle) — deferred, pre-existing branch-reachability limitation shared with the rest of this story's unreachable-today branches.
- [x] [Review][Defer] `overclaim_detected`/`portfolio_ready` classification is based solely on `ReportSummary.answer_display` presence (`_has_summary_text(summary.answer_display)`), not on `ReportSummary.status` [src/f1_analytics/analysis/question_workflow_surfaces.py:878,886] — a `PARTIAL`/`DISCREPANT_NEEDS_REVIEW`/`USER_MANUAL_OPTION`-status answer with non-empty `answer_display` would classify as `"portfolio_ready"` rather than `"overclaim_detected"` once that branch becomes reachable with real data, since nothing in `report_summary.py` cross-validates `status` against `answer_display` presence. This matches the story's own literal spec text verbatim (not a deviation from AC1/AC2 as written), so not a code defect against this story — deferred as a design note for whoever wires real Actual Answer Components into this bundle and makes the `portfolio_ready`/`overclaim_detected` branches reachable.
- [x] [Review][Defer] A duplicate `question_id` across `intake_briefs`/`catalog_rows` would silently misattribute Portfolio Summary content via last-wins dict lookups [src/f1_analytics/analysis/question_workflow_surfaces.py:835-836] — `intake_by_id`/`catalog_by_id` are built via `{surface.question_id: surface for surface in ...}`, keeping only the last surface for a duplicate ID. Not reachable with today's live data (5 unique supplied-PDF question IDs), and if a duplicate ever entered the catalog, `build_question_catalog_row_surfaces()`'s own `_duplicate_question_ids()` check already flags both rows `metadata_validation_status="blocked"`, which drives `_bundle_portfolio_ready()` to `False` bundle-wide — so the practical effect is a misattributed `why_it_matters` narrative for an already-correctly-reported not-portfolio-ready question, never a false "ready" claim. Matches this file's existing last-wins-by-`question_id` join convention used elsewhere; fixing it would add caller-input validation this function's own docstring explicitly disclaims ("adds no new validation... trust-the-caller-supplied-scope convention"). Revisit only as part of a broader sweep if this join pattern is ever tightened file-wide.
- [x] [Review][Defer] `_bundle_portfolio_ready()` does not consult the new Analysis Mode Boundary surface [src/f1_analytics/analysis/question_workflow_surfaces.py:1770-1790] — the four-gate check (intake, catalog, source coverage, output checklist) was not extended to also require every question's pre_race `boundary_status == "leakage_safe"`. Not reachable today (every pre_race row is `leakage_risk` live), but if the other four gates ever all pass, a question could be marked `"portfolio_ready"` in the Portfolio Summary while its own Analysis Mode Boundary entry, a few sections earlier in the same generated report, still reads `[LEAKAGE_RISK]`. Both Story 6.6 and this story explicitly forbid touching `_bundle_portfolio_ready()`'s logic/inputs/signature, so this is correctly out of scope here. Revisit once portfolio-readiness gating is reconsidered as part of the still-open epic-3/epic-5 live-wiring decisions.
- [x] [Review][Defer] Analysis Mode Boundary's "per Question ID" framing is decorative — content is byte-identical across all 5 supplied questions today [src/f1_analytics/analysis/question_workflow_surfaces.py:563-624]. `blocked_fact_groups`, `boundary_status`, `reason`, and (per current data) `feature_snapshot_boundary_summary` are computed once from a single bundle-wide aggregate `FeatureAvailabilityContract` and applied identically to every row; confirmed live via the generated report, which repeats the same ~1,500-character blocked-groups text five times, and the flat CSV, which embeds the same JSON blob in all 5 `analysis_mode_boundary` rows. Inherent to Epic-3's aggregate contract design (explicitly documented in the function's own docstring as intentional reuse, not new logic), so correctly out of scope for this diff. Revisit only if a future story needs genuinely per-question boundary detail.
- [x] [Review][Defer] `IMPLEMENTATION_HANDOFF_REGISTRY`'s "Portfolio Summary" entry is `HandoffStatus.SATISFIED` with `blocking_reasons=()` even though the surface's own flagship "why it matters" field is a known, tracked placeholder [src/f1_analytics/analysis/question_workflow_surfaces.py:407-420] — the very reason `sprint-status.yaml` keeps this story `in-progress` rather than `done`. This matches the registry's established convention elsewhere in the file (e.g., "Report Summary" is also `SATISFIED` despite its own `answer_display` always being `None` live) — `SATISFIED` means "the surface is code-implemented," not "the live data is complete," so this is not a deviation from file convention. Flagged only because this is specifically the surface meant to catch this exact kind of claim/reality mismatch. Revisit if the registry's `SATISFIED` semantics are ever tightened to require zero known content gaps.

## Dev Notes

### Working Tree State — read this before touching anything

`git status --short` at story-creation time shows the **complete, uncommitted implementation of Story 6.6** already in the working tree (dataclass, builder, wiring, tests, plus a code-review docstring patch), and updated `sprint-status.yaml`/`deferred-work.md` from Story 6.6's code review. `HEAD` is still `cf32663e37589b6b7276de87b66a407bf542c1f1` ("Story 6.5: Standardize status badge rendering") — none of Story 6.6's work has been committed yet. This is expected, not a broken state: **do not stash, reset, discard, or otherwise "clean up" these changes.** All line numbers cited throughout this story are measured against this current, Story-6.6-inclusive working tree — that is Story 6.7's real starting point. `PYTHONPATH=src python3 -m unittest discover -s tests` passes **329 tests** from this exact working-tree state, confirmed live at story-creation time.

### Current Project State To Preserve

- **`src/f1_analytics/analysis/question_workflow_surfaces.py` (1829 lines including Story 6.6's uncommitted work).** Read it completely before editing. Structures you touch: the frozen-dataclass block (~lines 73-224, `PortfolioSummarySurface` goes at its end, right before `AnalystWorkflowSurfaceBundle`); the `build_*` function block (~lines 446-815, `build_portfolio_summary_surfaces()` goes at its end, right before the top-level bundle builder); the `*_to_record()` block (~lines 816-976, `portfolio_summary_surface_to_record()` goes right after `report_summary_to_record()`); `IMPLEMENTATION_HANDOFF_REGISTRY` (~lines 248-421); `render_analyst_workflow_surface_markdown()` (~lines 997-1104); `_flat_surface_records()` / `_status_field_for_surface_type()` (~lines 1610-1645); and `__all__` (~lines 1787-1829). Structures you must **not** touch: every other surface's `build_*`/`*_to_record()` function, `_bundle_portfolio_ready()` itself (~lines 1567-1587 — see the explicit "out of scope" note above), and anything in `question_predictions.py`, `question_backtest_scoring.py`, `question_backtest_report.py`, `question_backtest_explanations.py`, `question_feature_availability.py`, or `question_catalog.py`.
- **`ReportSummary`/`report_summary.py` is Epic 6 Story 6.3's contract — already implemented, tested, and correct.** It is deliberately dependency-light (stdlib plus `ActualAnswerStatus` and `status_badge` only, per its own module docstring: "it must not reach back into either of those stacks") — this story reads its already-built `bundle.report_summaries` tuple, it does not add a new import to `report_summary.py` itself.
- **The exact gap this story closes, verbatim from the Track 1 deferred-work entry:** "Portfolio Summary — public-facing 'why it matters' layer (answer, limitation, suggested story angle) over a finished output bundle." [`_bmad-output/implementation-artifacts/deferred-work.md:128`]
- **Confirmed live at story-creation time:** `build_supplied_pdf_analyst_workflow_surface_bundle()` called with no raw-data arguments produces `bundle.portfolio_ready == False` (the generated report's top line reads `Portfolio-ready: no`), and every one of the five supplied questions' `ReportSummary.answer_display` is `None` (no Actual Answer Components are wired into this bundle — the epic-5 live-DuckDB-wiring decision is still open). This means the `"not_portfolio_ready"` branch is the only one of the three `portfolio_status` values reachable through the live no-argument bundle today; `"overclaim_detected"` and `"portfolio_ready"` both require a synthetic, directly-constructed call to `build_portfolio_summary_surfaces()` in tests, exactly like Story 6.6's `"leakage_safe"` branch required constructing an unreachable-by-default scenario.
- **No `build_supplied_pdf_...`-style end-to-end entry point exists for backtest/portfolio-explanation content** — confirmed live by grepping `question_backtest_report.py`, `question_backtest_scoring.py`, `question_backtest_explanations.py`, and `question_predictions.py` for `"supplied_pdf"` (zero matches in all four). Do not build one as part of this story; see "Out of scope" above.

### Architecture Compliance

- Reusable logic lives under `src/f1_analytics/`; `scripts/*.py` stay thin orchestration wrappers; renderers narrate already-computed facts. [Source: `ARCHITECTURE-SPINE.md#AD-1---Layer-Ownership-For-Reproducible-Analytics-ADOPTED`] — `suggested_public_story_angle`'s composition from three already-computed `ReportSummary` fields is exactly this kind of narration, not new computation.
- No DuckDB reads inside `src/f1_analytics/analysis/` for this surface — same boundary every 6.x story has held; `build_portfolio_summary_surfaces()` operates only on already-built surface dataclasses passed in as arguments.
- This story does **not** engage AD-8 (leakage boundary) or AD-9 (scoring source-grade facts) directly — it reads the bundle-level `portfolio_ready` gate that already accounts for those upstream rules via the surfaces that already compute them (source coverage, output checklist), rather than re-deriving anything from AD-8/AD-9 itself.

### UX Contract Requirements

- Component pattern: "Portfolio Summary | Explain a finished analysis | States question, answer, why it matters, source/cutoff basis, limitation, and suggested public-story angle." [Source: `EXPERIENCE.md#Component-Patterns`, line 77]
- IA row: "Portfolio Summary | Output bundle / README or public story prep | Confirm the result is understandable without raw-table inspection and does not overclaim source coverage." [Source: `EXPERIENCE.md#Information-Architecture`, line 41] — note the IA table places Portfolio Summary directly before Implementation Handoff (line 42), which this story's Markdown section placement follows.
- State patterns: "Portfolio-ready | Output Bundle Checklist / Portfolio Summary | Report, table(s), limitation note, and explanation can stand without raw-table inspection." and "Overclaim detected | Portfolio Summary | Block public-story use until the claim is narrowed or the limitation is moved near the answer." [Source: `EXPERIENCE.md#State-Patterns`, lines 112-113] — rendered as `portfolio_status == "portfolio_ready"` and `portfolio_status == "overclaim_detected"` respectively.
- Surface-to-component map: `components.portfolio-summary`. [Source: `EXPERIENCE.md#Surface-to-component-Map`, line 297]
- Voice and tone: "Portfolio-facing reports should be concise and plain. They should name the question, answer, source basis, limitation, and next action without asking the reader to infer trust level." [Source: `EXPERIENCE.md#Voice-and-Tone`, line 58]
- Anti-pattern: "Rejected - betting or odds framing: analysis may evaluate predictions and backtests, but not wagering use cases." [Source: `EXPERIENCE.md#Anti-patterns`, line 200] — this is the source of AC2's forbidden-framing clause, already enforced by `_neutralize_public_text()`.
- Handoff rule: "Portfolio summaries are required for selected showcase analyses and any public-facing artifact; they are optional for internal source-coverage or validation-only outputs." [Source: `EXPERIENCE.md#Handoff-Rules`, line 309]
- Visual/color spec: `DESIGN.md#Components` (line 246): "Portfolio Summary - Public-facing summary block for a finished analysis. Uses `components.portfolio-summary`." Token definition at `DESIGN.md` lines 138-143 (`background: surface-raised`, `foreground: ink-primary`, `answer-accent: racing-red`, `border: border-subtle`). **Same as every prior 6.x story: this repo has no rendering path that ever applies real color** (Markdown/CSV only) — only the "text plus a stable marker" branch of the accessibility floor is implementable here; do not add HTML/CSS.

### Previous Story Intelligence

- **This story exists because the Track 1 deferred-work entry names it explicitly** (`deferred-work.md:128`, item 7 of 7), the same pattern every 6.x story has followed since Story 6.4 was born from Story 6.3's own deferred finding. Unlike items 1-6, item 7's own phrasing ("public-facing 'why it matters' layer... over a finished output bundle") signals this story synthesizes across several existing surfaces rather than rendering one single contract — see the Scope Decision section above for why that's still "no new logic," just broader reuse.
- **Story 6.6 established the exact mechanical pattern this story reuses almost verbatim**: add a dataclass, a `build_*()` function, a `*_to_record()` function, wire all three into the bundle/serialization/flat-CSV/render sites, then flip the registry entry from Open to Satisfied and fix the tests that assert exact surface-name sets. This story needs a **third** required regression fix beyond 6.6's usual two, because — unlike every prior surface, which was inserted mid-tuple in `_flat_surface_records()` — Portfolio Summary is appended *after* `"report_summaries"`, the one surface type an existing test (`test_flat_csv_keeps_report_summaries_last_and_appends_their_columns`) specifically asserts stays last in the flat CSV (see the task note above). This story is also the **last** one to flip an Open registry entry — `OPEN_UX_SURFACES` goes from one entry to zero, which is new: do not delete the now-vacuous test that iterates it.
- **Story 6.6's whitespace-handling lesson** (`render_status_badge()`'s `reason` parameter treats a whitespace-only string as absent) does not apply here — this story's `portfolio_status` values are non-blank literals passed with no `reason=` kwarg, matching Story 6.6's own resolution of the same non-issue.
- **Story 6.6's code-review finding, corrected here rather than repeated**: `analysis_mode_boundary_surface_to_record()` left its `blocked_fact_groups` tuple unneutralized while neutralizing `reason` (recorded as deferred debt in `deferred-work.md`'s Story 6.6 entry, 2026-07-27). This story's `portfolio_summary_surface_to_record()` must neutralize **every** free-text field including the `blocking_reasons` tuple, matching `report_summary_to_record()`'s more thorough precedent instead.
- **Story 6.6's "do not fabricate" lesson, same shape again**: don't invent a fourth `portfolio_status` value or a numeric "confidence score" — the three values above are exhaustive for this surface's actual two-condition-times-readiness shape.

### File Structure Requirements

Files this story modifies (no new files are created):
- `src/f1_analytics/analysis/question_workflow_surfaces.py` — new `PortfolioSummarySurface` dataclass, new `build_portfolio_summary_surfaces()` function, new `portfolio_summary_surface_to_record()` function, new field on `AnalystWorkflowSurfaceBundle`, new wiring in `build_supplied_pdf_analyst_workflow_surface_bundle()` / `analyst_workflow_surface_bundle_to_records()` / `_flat_surface_records()` / `_status_field_for_surface_type()`, new `## Portfolio Summary` block in `render_analyst_workflow_surface_markdown()`, `IMPLEMENTATION_HANDOFF_REGISTRY`'s "Portfolio Summary" entry moved to Satisfied plus header/inline comment updates (and removal of the now-empty "Open: Track 1" comment line), `__all__` additions.
- `scripts/build_question_workflow_surfaces.py` — one new entry in the row-count print loop.
- `tests/test_question_workflow_surfaces.py` — new imports (including `ReportSummary`/`build_report_summary` from `report_summary.py`), new `PortfolioSummarySurfaceTests` class, `OPEN_UX_SURFACES`/`SATISFIED_UX_SURFACES` move (the former becomes empty), the required bundle-serialization key-set fix, the required flat-CSV "report summaries last" ordering fix, one new Markdown-content assertion, one new `StatusBadgeRenderingTests` test, one new flat-CSV-unbracketed test.

Do not edit `question_predictions.py`, `question_backtest_scoring.py`, `question_backtest_report.py`, `question_backtest_explanations.py`, `question_feature_availability.py`, `question_catalog.py`, `report_summary.py`, `status_badge.py`, `evidence_link.py`, or `question_answers.py` — verify none of them need a change before writing code; if one turns out to, say so in the Dev Agent Record rather than silently widening the diff.

Generated, gitignored output (existing paths, not new):
- `outputs/reports/question_workflow_surfaces.md`, `outputs/tables/question_workflow_surfaces.csv`

### Testing Requirements

- Standard-library `unittest`, matching the existing suite. `PYTHONPATH=src python3 -m unittest discover -s tests` is the regression command; baseline confirmed at story-creation time (2026-07-27) is **329 tests passing**, from the Story-6.6-inclusive working tree described above.
- No live DuckDB in unit tests. `build_portfolio_summary_surfaces()` operates only on already-built surface dataclasses and a `bool`/`tuple[str, ...]` — no database access anywhere in this story.
- The live no-argument bundle only reaches `"not_portfolio_ready"` today — the other two `portfolio_status` values must be exercised by directly calling `build_portfolio_summary_surfaces()` with hand-constructed fixtures (not the raw-data-less top-level builder), exactly as Story 6.6 had to do for its own unreachable-today branch. This is intentional, not a flake to work around.

### Git Intelligence

`HEAD` at story creation is `cf32663e37589b6b7276de87b66a407bf542c1f1` — "Story 6.5: Standardize status badge rendering" — but see **Working Tree State** above: the actual starting point for this story's diff is the current working tree, which already contains Story 6.6's complete, uncommitted implementation (dataclass, builder, wiring, tests, and its own code-review docstring patch).

- `cf32663` Story 6.5: Standardize status badge rendering
- `225608c` Story 6.4: Attach evidence links to sourced claims
- `4629295` Epic 5+6: Analyst Workflow Surfaces (Story 5.1, Stories 6.1-6.3)
- `3950405` Epic 4: Backtest Reporting And Portfolio Explanation (Stories 4.1-4.2)

None of these commits touch `report_summary.py`, `question_backtest_report.py`, `question_backtest_scoring.py`, or `question_backtest_explanations.py` beyond their original Epic 4/6 implementations — confirmed via full-file reads at story-creation time, zero uncommitted changes pending against any of the four.

### Latest Technical Information

No new libraries, versions, or external APIs. Stdlib only. Stack per `ARCHITECTURE-SPINE.md#Stack`: Python 3.13.7 — none of this story's code touches pandas or DuckDB.

### Project Context Reference

`_bmad-output/project-context.md` — the rules that bind this story:
- Reusable logic in `src/f1_analytics/`; `scripts/*.py` stay thin CLI wrappers.
- No linter/formatter config exists — match the surrounding module style: type-annotated signatures, module-level docstrings, `from __future__ import annotations` (already present at the top of `question_workflow_surfaces.py`; no change needed there).
- Public/reused functions document purpose, key inputs, return value, assumptions, and failure behavior — `build_portfolio_summary_surfaces()`'s docstring must state its "takes the already-computed `portfolio_ready` boolean as a parameter, never recomputes it" assumption and its deliberate three-value `portfolio_status` vocabulary, exactly as drafted in the task list above.

### References

- `_bmad-output/planning-artifacts/epics.md#Epic-6` (Story 6.7 section, lines 871-898 — source of the Acceptance Criteria above)
- `_bmad-output/implementation-artifacts/deferred-work.md:114-136` (the "analyst-environment UX contract coverage gap" entry naming this story as Track 1 item 7) and `:185-189` (Story 6.6's carried-forward findings, including the neutralization gap this story deliberately does not repeat)
- `_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/EXPERIENCE.md` (Information Architecture line 41, Component Patterns line 77, State Patterns lines 112-113, Surface-to-component Map line 297, Voice and Tone line 58, Anti-patterns line 200, Handoff Rules line 309)
- `_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md` (Components line 246, token block lines 138-143)
- `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md` (AD-1, Capability Map line 197)
- `_bmad-output/implementation-artifacts/6-6-render-analysis-mode-boundary-surface.md` (preceding story; established the dataclass/builder/to_record/wiring/registry-flip mechanical pattern this story reuses, and the neutralization gap this story corrects)
- `_bmad-output/implementation-artifacts/6-3-render-report-summary-across-generated-outputs.md` (built `ReportSummary`/`report_summary.py`, the primary reuse target for this story's `question`/`answer_display`/`source_and_cutoff_basis`/`reason` fields)
- `src/f1_analytics/analysis/question_workflow_surfaces.py`, `src/f1_analytics/analysis/report_summary.py`
- `scripts/build_question_workflow_surfaces.py`
- `tests/test_question_workflow_surfaces.py`, `tests/test_question_backtest_report.py` (confirms the synthetic-fixture-only shape of `PredictionInput`/`ActualAnswerComponent` this story must not depend on)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (epic-3 and epic-5 open action items — why this story must not wire baseline predictions/scoring/backtest report rows in)

### Open Questions

- None blocking. This is the final Track 1 surface — once it's done, `IMPLEMENTATION_HANDOFF_REGISTRY`'s Open section is empty and every remaining registry entry is either Satisfied or Blocked (Track 2, gated on the still-open epic-3/epic-5 decisions). A future epic would need to resolve those two decisions before any of Target Store Review / Scoring and Baseline Review / Discrepancy Panel can become buildable — that decision belongs to whoever plans the next epic, not to this story.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5), via the `bmad-dev-story` workflow.

### Debug Log References

- `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces` — 65 tests, OK.
- `PYTHONPATH=src python3 -m unittest discover -s tests` — 335 tests, OK (baseline 329 + 6 new: 4 in
  `PortfolioSummarySurfaceTests`, 2 new `StatusBadgeRenderingTests` cases).
- `python3 -m compileall src/f1_analytics` — no errors.
- `PYTHONPATH=src python3 scripts/build_question_workflow_surfaces.py` — ran clean; printed
  `portfolio_summary rows: 5`. Inspected `outputs/reports/question_workflow_surfaces.md`: a
  `## Portfolio Summary` section with 5 entries, all `[NOT_PORTFOLIO_READY]` (today's live case),
  each with a non-empty `- Blocking reasons:` line. Inspected
  `outputs/tables/question_workflow_surfaces.csv`: 5 rows with `surface_type == "portfolio_summary"`
  and an unbracketed `status` column (`not_portfolio_ready`).
- `git diff --check` on all touched tracked files — clean.

### Completion Notes List

- Implemented `PortfolioSummarySurface`, `build_portfolio_summary_surfaces()`, and
  `portfolio_summary_surface_to_record()` in `question_workflow_surfaces.py` exactly per the
  story's drafted code — a new three-value `portfolio_status` vocabulary
  (`portfolio_ready` / `overclaim_detected` / `not_portfolio_ready`) composed from already-built
  bundle surfaces (`QuestionIntakeBriefSurface.intended_output` for `why_it_matters`,
  `ReportSummary` fields for `suggested_public_story_angle`), reusing the bundle's own
  already-computed `portfolio_ready` boolean rather than recomputing it. No new leakage, scoring,
  or persistence logic added; no changes made to `_bundle_portfolio_ready()` or to any of the
  out-of-scope modules named in the story (verified none needed a change).
- Wired the new surface into `AnalystWorkflowSurfaceBundle` (new `portfolio_summary` field, placed
  after `report_summaries`), `build_supplied_pdf_analyst_workflow_surface_bundle()`,
  `analyst_workflow_surface_bundle_to_records()`, `_flat_surface_records()` (appended after
  `report_summaries`, the sole exception to that tuple's "Report Summary stays last" rule — updated
  the explanatory comment accordingly), and `_status_field_for_surface_type()`.
- Rendered a new `## Portfolio Summary` Markdown block immediately before `## Implementation
  Handoff`, matching `EXPERIENCE.md`'s Information Architecture order; reused `_limitations_text()`
  for `blocking_reasons` and relied on the renderer's existing single trailing
  `_neutralize_public_text()` pass for the scalar fields, per the story's explicit instruction not
  to double-neutralize.
- `portfolio_summary_surface_to_record()` neutralizes every free-text field including the
  `blocking_reasons` tuple — deliberately more thorough than Story 6.6's
  `analysis_mode_boundary_surface_to_record()`, whose unneutralized `blocked_fact_groups` gap was
  recorded as deferred debt; this story does not repeat it.
- Moved the `IMPLEMENTATION_HANDOFF_REGISTRY`'s "Portfolio Summary" entry from Open to Satisfied
  (now naming `build_portfolio_summary_surfaces` / `render_analyst_workflow_surface_markdown` as
  its implementation), removed the now-dead "Open: Track 1" comment line, and updated the registry
  header/inline comments to 10 satisfied / 0 open / 3 blocked. `status_rule` and
  `acceptance_criteria_implication` text left unchanged, as instructed.
- Required regression fixes applied exactly as anticipated: moved `"Portfolio Summary"` from
  `OPEN_UX_SURFACES` to `SATISFIED_UX_SURFACES` in the registry test (the now-empty
  `OPEN_UX_SURFACES` tuple leaves `test_open_track_one_surfaces_are_ready_without_an_implementation_yet`
  passing vacuously, kept as-is); added `"portfolio_summary"` to the bundle-serialization key-set
  assertion; and split `test_flat_csv_keeps_report_summaries_last_and_appends_their_columns`'s
  last-5-rows assertion into a `report_summaries` block at `[-10:-5]` and a new `portfolio_summary`
  block at `[-5:]`.
- Added `PortfolioSummarySurfaceTests` (4 tests covering AC1-AC3: the live not-portfolio-ready
  path, a synthetic overclaim-detected path, a synthetic portfolio-ready path with composed
  `suggested_public_story_angle`, and full free-text neutralization including `blocking_reasons`),
  one Markdown-content assertion added to the existing writer test, and two new
  `StatusBadgeRenderingTests` (controlled three-value status vocabulary in the rendered section;
  unbracketed `status` column in the flat CSV). Full regression: 329 → 335 tests, all passing.
- Confirmed no changes were needed to `question_predictions.py`, `question_backtest_scoring.py`,
  `question_backtest_report.py`, `question_backtest_explanations.py`,
  `question_feature_availability.py`, `question_catalog.py`, `report_summary.py`,
  `status_badge.py`, `evidence_link.py`, or `question_answers.py`.

### File List

- `src/f1_analytics/analysis/question_workflow_surfaces.py` (modified)
- `scripts/build_question_workflow_surfaces.py` (modified)
- `tests/test_question_workflow_surfaces.py` (modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — story status)

## Change Log

- 2026-07-27: Story context created by `bmad-create-story`; status set to `ready-for-dev`.
- 2026-07-27: Implemented Portfolio Summary surface (dataclass, builder, serializer, bundle/CSV/
  Markdown wiring, registry flip to Satisfied, required regression fixes, new tests); status set to
  `review`.
- 2026-07-27: Code review (`bmad-code-review`). 1 decision-needed (blocking — "why it matters"
  renders a hardcoded literal, not real per-question content), 3 patch findings fixed
  (`blocking_reasons` terminal fallback, `limitation` `_has_summary_text()` consistency, unused test
  import), 2 deferred to `deferred-work.md`. Full regression: 339/339 passing. Status set to
  `in-progress` pending a follow-up story for real per-question "why it matters" content.
- 2026-07-27: Second code review pass (`bmad-code-review`, three parallel adversarial layers:
  Blind Hunter, Edge Case Hunter, Acceptance Auditor). 0 new decision-needed, 0 new patch findings,
  5 new deferred to `deferred-work.md` (duplicate-`question_id` last-wins misattribution in
  `build_portfolio_summary_surfaces()`; `_bundle_portfolio_ready()` not consulting the new Analysis
  Mode Boundary surface; Analysis Mode Boundary's per-question framing being decorative given
  today's identical live data; `IMPLEMENTATION_HANDOFF_REGISTRY`'s Portfolio Summary entry reading
  `SATISFIED`/no-blocking-reasons alongside a still-open content gap). 8 additional findings
  dismissed as already tracked, matching documented design intent, or matching established file
  convention (verified against source, not assumed). No new AC/scope/do-not-touch violations found
  by the Acceptance Auditor. Status remains `in-progress` — the original blocking decision (real
  per-question "why it matters" content) is still unresolved.
