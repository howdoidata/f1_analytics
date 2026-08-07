---
title: "Analyst Experience Contract Intake"
status: draft
created: 2026-07-22
updated: 2026-07-22
owner: "Antonio"
agent: "Sally / UX Designer"
recommended_next_workflow: "bmad-ux"
sources:
  - "PROJECT.md"
  - "_bmad-output/project-context.md"
  - "_bmad-output/planning-artifacts/prds/prd-f1_analytics-2026-07-17/prd.md"
  - "_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/epics.md"
---

# Analyst Experience Contract Intake

## Trigger

Antonio raised a planning concern on 2026-07-22: the project has strong architecture guidance and one implemented example analysis, but there is not enough information between architecture and end users about expectations, analyst workflow, and what it should feel like to pivot to another analysis.

The project was intended to let analysts showcase different analyses without having to change too much under the hood. The reusable pieces may be shared data, shared SQL, shared source adapters, shared analysis modules, shared report patterns, or other surfaces that are not fully known yet. The immediate need is to think carefully about the next steps before adding more implementation.

## Current Gap

The current PRD, architecture spine, and epics define reusable pipeline and source-status rules, but the epic artifact explicitly notes:

> No UX design contract was included or discovered for this run.

This leaves a gap between system design and analyst expectations. Builders know where logic should live, but an analyst does not yet have a clear journey for bringing a new F1 question, discovering what can be reused, deciding what needs extension, and producing a portfolio-ready output.

## UX Problem Statement

`f1_analytics` needs an analyst-experience contract for turning a new F1 analysis idea into a reproducible, presentable output with minimal unnecessary under-the-hood change.

The contract should clarify what an analyst should expect when they:

- Bring a new F1 question or hypothesis.
- Classify the question type and required facts.
- Determine whether existing data, DuckDB tables, SQL, modules, or report patterns are reusable.
- Identify missing, partial, stale, or source-blocked data.
- Decide whether the next action is reuse, extension, source-coverage work, manual provenance review, or deferral.
- Produce a consistent output bundle suitable for portfolio, GitHub, notebook, dashboard, or public data-story use.

## Proposed Analyst Journey

The likely target journey is:

1. Analyst receives or invents a new F1 analysis question.
2. Analyst classifies the question type, grain, required facts, and expected output.
3. System or workflow shows whether existing data and analysis components can answer it.
4. Analyst chooses one path: reuse existing assets, extend an extractor/model, add source coverage, approve manual provenance, or defer.
5. System produces a repeatable output bundle with tables, report text, figures, notebook cells, or dashboard-ready files as appropriate.
6. Analyst turns the bundle into a portfolio or public-facing story with source limitations and confidence stated clearly.

## Questions For The Next UX Run

- What is the named primary user journey: Antonio as solo analyst, a future hiring reviewer exploring artifacts, or another analyst reusing the repo?
- What form factor is the analyst experience targeting first: command-line workflow, notebook-first workflow, generated reports, dashboard-ready outputs, or a lightweight local interface?
- What should a new analysis intake require before code changes begin?
- What should the system show when an analysis is answerable from existing assets versus blocked by missing facts?
- Which outputs are mandatory for every analysis: Markdown report, CSV table, figure, notebook section, portfolio summary, validation record, or source-coverage note?
- What is the minimum reusable contract for "pivoting" to another analysis without overbuilding?
- Where should future shared SQL live if it becomes useful, given current architecture notes that `sql/curated/` has no real SQL files yet?
- How should user-manual decisions be exposed so they are clearly provenance-labeled and not mistaken for computed-source success?

## Recommended Next Workflow

Run `bmad-ux` in fast-path mode and produce a full `EXPERIENCE.md` first. Keep `DESIGN.md` minimal unless the workflow discovers a concrete UI, report, notebook, or dashboard surface that needs visual identity decisions.

The UX output should become the bridge between:

- Product intent: local, reusable F1 analytics for portfolio-quality storytelling.
- Architecture: layered local analytics pipeline with reusable source, extraction, scoring, and rendering logic.
- End-user expectation: an analyst can bring the next F1 question and know what happens next.

## Suggested Scope For EXPERIENCE.md

The future UX contract should cover:

- Analyst question intake.
- Analysis classification.
- Reuse and extension decision paths.
- Source coverage and confidence states.
- Output bundle expectations.
- Portfolio-readiness criteria.
- Failure and blocked-state language.
- Handoff expectations for architecture and implementation stories.

## Non-Goals For The Next UX Pass

- Do not redesign the whole architecture.
- Do not introduce a hosted application requirement unless Antonio explicitly chooses that direction.
- Do not assume dbt, Airflow, Tableau, or a dashboard is required for the next step.
- Do not define visual design before the analyst workflow is understood.
- Do not treat the existing Williams question-backtest example as the only analysis pattern the project should support.
