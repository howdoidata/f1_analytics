---
title: "Analyst Workflow Surfaces Epic Placement Decision Record"
status: accepted
created: 2026-07-23
source_material:
  - "_bmad-output/implementation-artifacts/epic-4-retro-2026-07-22-1751-cdt.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/EXPERIENCE.md"
  - "_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md"
  - "_bmad-output/planning-artifacts/epics.md"
---

# Analyst Workflow Surfaces Epic Placement Decision Record

## Decision

Create a new Epic 5, "Analyst Workflow Surfaces And Output Bundle", for the first implementation story that turns the UX contract's analyst workflow surfaces into reusable local artifacts.

Do not reopen Epic 4. Epic 4 is complete as reusable report-row and portfolio-explanation capability, and its retrospective explicitly records the remaining gap as a future story. Epic 5 owns the follow-on report-first workflow surface layer: Question Intake Brief, Question Catalog Row, Source Coverage Matrix, and Output Bundle Checklist.

## Rationale

- Sprint tracking marks Epics 1 through 4 as done.
- The UX contract was created after the original 4-epic question/backtest roadmap and now names additional analyst-experience surfaces that were not in the original epics.
- The Epic 4 retrospective calls out the missing live/report-first workflow story while also stating that no Epic 5 existed yet.
- A new epic avoids changing the meaning of completed Epic 4 while keeping the UX-contract implementation traceable.

## Consequences

- Story `5-1-build-report-first-analyst-workflow-surfaces` is the next ready-for-dev story.
- Sprint status gains `epic-5`, story `5-1-build-report-first-analyst-workflow-surfaces`, and `epic-5-retrospective`.
- The existing Epic 4 action item to create the separate follow-on story is satisfied by this story creation, not by implementation completion.
- The story remains local-first and artifact-first. It does not authorize a hosted UI, dashboard shell, FastF1 adoption, forecast model work, or manual-provenance promotion.
