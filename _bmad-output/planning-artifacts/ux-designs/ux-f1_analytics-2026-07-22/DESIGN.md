---
name: "f1_analytics Analyst Outputs"
description: "Visual contract for local Formula 1 analysis artifacts: Markdown reports, notebooks, CSV-backed tables, Plotly figures, and dashboard-ready exports."
status: final
created: 2026-07-22
updated: 2026-07-23
sources:
  - "_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/UX-INTAKE.md"
  - "_bmad-output/planning-artifacts/prds/prd-f1_analytics-2026-07-17/prd.md"
  - "_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-07-17/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/decisions/dataset-precedence-decision-record.md"
  - "_bmad-output/planning-artifacts/decisions/question-backtest-mode-and-scoring-decision-record.md"
  - "_bmad-output/planning-artifacts/epics.md"
colors:
  surface-base: "#F7F7F4"
  surface-raised: "#FFFFFF"
  surface-muted: "#ECECEA"
  surface-info: "#EEF5FF"
  surface-success: "#E6F3EC"
  surface-warning: "#FFF4DE"
  surface-blocked: "#FBE7E8"
  surface-discrepancy: "#F0E9F8"
  surface-manual: "#E8F0FA"
  ink-primary: "#181A1B"
  ink-secondary: "#555B60"
  ink-muted: "#747A80"
  border-subtle: "#D8DAD8"
  border-info: "#BBD2F0"
  racing-red: "#C41230"
  timing-purple: "#6E3FA9"
  source-green: "#177245"
  warning-amber: "#B36B00"
  blocked-red: "#9F1D20"
  info-blue: "#2364AA"
  neutral-gray: "#636A70"
typography:
  title:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 28px
    fontWeight: "700"
    lineHeight: "1.2"
    letterSpacing: 0
  section:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 20px
    fontWeight: "700"
    lineHeight: "1.3"
    letterSpacing: 0
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: "400"
    lineHeight: "1.55"
    letterSpacing: 0
  table:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: "400"
    lineHeight: "1.45"
    letterSpacing: 0
  code:
    fontFamily: "SFMono-Regular, Consolas, monospace"
    fontSize: 13px
    fontWeight: "400"
    lineHeight: "1.45"
    letterSpacing: 0
rounded:
  sm: 4px
  md: 6px
  lg: 8px
spacing:
  "1": 4px
  "2": 8px
  "3": 12px
  "4": 16px
  "5": 24px
  "6": 32px
components:
  report-summary:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    radius: "{rounded.md}"
  evidence-link:
    foreground: "{colors.info-blue}"
    underline: "always"
  question-intake-brief:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    required-accent: "{colors.racing-red}"
    radius: "{rounded.md}"
  question-catalog-row:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    status-column: "{colors.ink-secondary}"
    radius: "{rounded.sm}"
  reuse-and-extension-review:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    decision-accent: "{colors.info-blue}"
    radius: "{rounded.md}"
  source-coverage-matrix:
    header-background: "{colors.surface-muted}"
    border: "{colors.border-subtle}"
    text: "{colors.ink-primary}"
    radius: "{rounded.sm}"
  analysis-mode-boundary:
    background: "{colors.surface-info}"
    foreground: "{colors.info-blue}"
    border: "{colors.border-info}"
    radius: "{rounded.md}"
  target-store-review:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    value-accent: "{colors.racing-red}"
    radius: "{rounded.sm}"
  actual-answer-component:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    value-accent: "{colors.racing-red}"
    radius: "{rounded.sm}"
  scoring-and-baseline-review:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    radius: "{rounded.md}"
  output-bundle-checklist:
    background: "{colors.surface-raised}"
    border: "{colors.border-subtle}"
    ready-accent: "{colors.source-green}"
    blocked-accent: "{colors.blocked-red}"
    radius: "{rounded.md}"
  portfolio-summary:
    background: "{colors.surface-raised}"
    foreground: "{colors.ink-primary}"
    answer-accent: "{colors.racing-red}"
    border: "{colors.border-subtle}"
    radius: "{rounded.md}"
  implementation-handoff:
    background: "{colors.surface-muted}"
    foreground: "{colors.ink-primary}"
    border: "{colors.border-subtle}"
    radius: "{rounded.md}"
  status-badge-computed:
    background: "{colors.surface-success}"
    foreground: "{colors.source-green}"
    radius: "{rounded.sm}"
  status-badge-partial:
    background: "{colors.surface-warning}"
    foreground: "{colors.warning-amber}"
    radius: "{rounded.sm}"
  status-badge-source-blocked:
    background: "{colors.surface-blocked}"
    foreground: "{colors.blocked-red}"
    radius: "{rounded.sm}"
  status-badge-discrepant-needs-review:
    background: "{colors.surface-discrepancy}"
    foreground: "{colors.timing-purple}"
    radius: "{rounded.sm}"
  status-badge-user-manual-option:
    background: "{colors.surface-manual}"
    foreground: "{colors.info-blue}"
    radius: "{rounded.sm}"
  status-badge-user-manual-approved:
    background: "{colors.surface-manual}"
    foreground: "{colors.info-blue}"
    border: "{colors.info-blue}"
    radius: "{rounded.sm}"
  status-badge-pending:
    background: "{colors.surface-muted}"
    foreground: "{colors.neutral-gray}"
    radius: "{rounded.sm}"
  discrepancy-panel:
    background: "{colors.surface-discrepancy}"
    foreground: "{colors.ink-primary}"
    border: "{colors.timing-purple}"
    radius: "{rounded.md}"
---

# DESIGN.md

## Brand & Style

`f1_analytics` should read as a rigorous local analytics workspace, not a motorsport fan site and not a SaaS dashboard. The visual posture is technical, source-aware, and portfolio-ready: clear tables, restrained highlights, concise callouts, and enough Formula 1 signal to make the subject recognizable without turning analysis outputs into decoration.

The artifacts are meant to be inspected by Antonio, downstream agents, and hiring reviewers. They should make it easy to find the question, source basis, answer, confidence/status, and portfolio-ready takeaway. Visual excitement comes from the analysis result and chart selection, not from chrome.

## Colors

- **Surface tokens** (`{colors.surface-base}`, `{colors.surface-raised}`, `{colors.surface-muted}`) create quiet separation for generated Markdown, notebook sections, and exported HTML figures.
- **Status surfaces** (`{colors.surface-success}`, `{colors.surface-warning}`, `{colors.surface-blocked}`, `{colors.surface-discrepancy}`, `{colors.surface-manual}`) back status badges and panels. They exist so status combinations can be audited centrally.
- **Ink tokens** (`{colors.ink-primary}`, `{colors.ink-secondary}`, `{colors.ink-muted}`) keep text hierarchy legible across reports and notebooks.
- **Racing Red** (`{colors.racing-red}`) is the Formula 1 accent. Use it for the primary analysis result or one key chart series, never for every heading or table border.
- **Timing Purple** (`{colors.timing-purple}`) marks discrepancy or timing-specific evidence where a result differs from a known answer example.
- **Source Green** (`{colors.source-green}`) means source-backed computed success.
- **Warning Amber** (`{colors.warning-amber}`) means partial, stale, or review-needed coverage.
- **Blocked Red** (`{colors.blocked-red}`) means the current source set cannot support the requested answer.
- **Info Blue** (`{colors.info-blue}`) is reserved for links, citations, mode boundaries, and user-manual provenance.

Contrast target: body text, table text, links, badges, and status panels must meet WCAG 2.2 AA contrast. Load-bearing combinations include `{colors.ink-primary}` on `{colors.surface-base}` and `{colors.surface-raised}`, `{colors.info-blue}` on `{colors.surface-info}` and `{colors.surface-manual}`, `{colors.source-green}` on `{colors.surface-success}`, `{colors.warning-amber}` on `{colors.surface-warning}`, `{colors.blocked-red}` on `{colors.surface-blocked}`, and `{colors.timing-purple}` on `{colors.surface-discrepancy}`. Do not use color alone to communicate answer status; every badge, table row, and report section must include text.

## Typography

Use a practical system sans-serif ramp for reports and notebooks. Headings should be compact and direct. Body text should favor short explanatory paragraphs and tables over long narrative blocks.

Use `{typography.code}` for paths, table names, question IDs, status values, and commands. Do not typeset analytical claims as code unless they are literal values.

## Layout & Spacing

Generated reports should follow a consistent sequence:

1. Question answered.
2. Source and cutoff basis.
3. Answer and status.
4. Supporting table or figure.
5. Limitation and next action.

Use `{spacing.4}` as the default internal gap for summary blocks and `{spacing.5}` to separate major report sections. Tables should remain dense enough for comparison, with row spacing no larger than needed for scanability.

## Elevation & Depth

Depth is functional only. `report-summary`, `output-bundle-checklist`, and `portfolio-summary` may sit on `{colors.surface-raised}` with a subtle border. Avoid shadows in Markdown-derived or notebook-derived artifacts; hierarchy should come from headings, tables, and status placement.

## Shapes

Use small radii. `{rounded.sm}` is for badges and table containers; `{rounded.md}` is for summary blocks and checklists. Avoid pill-heavy styling except where a downstream UI library requires it for badges.

## Components

- **Report Summary** - Top section of a Markdown, notebook, or generated HTML report. Shows question, answer, source basis, status, and next action. Uses `components.report-summary`.
- **Evidence Link** - Inline path or source citation. Must be visibly linked and use `components.evidence-link`.
- **Question Intake Brief** - Structured block for a new question. Uses `components.question-intake-brief`; required missing fields may use `{colors.racing-red}` as a left accent or label marker.
- **Question Catalog Row** - Dense table row for a structured question. Uses `components.question-catalog-row`; status belongs in a dedicated column.
- **Reuse and Extension Review** - Summary block for the reuse decision. Uses `components.reuse-and-extension-review`; decision value should be visually scannable but not oversized.
- **Source Coverage Matrix** - Table showing required fact, current source, availability, status, and next action. Uses `components.source-coverage-matrix`.
- **Analysis Mode Boundary** - Callout for `pre_race` / `post_race` and leakage boundary. Uses `components.analysis-mode-boundary`.
- **Target Store Review** - Surface-level review for Actual Answer Components, provenance, and validation status. Uses `components.target-store-review`.
- **Actual Answer Component** - Compact row or table block for a target value and provenance. Uses `components.actual-answer-component`.
- **Scoring and Baseline Review** - Table or report block comparing Prediction Inputs, Actual Answers, scoreability, and scoring outcome. Uses `components.scoring-and-baseline-review`.
- **Output Bundle Checklist** - Checklist for report/table/figure/notebook/dashboard-ready exports. Uses `components.output-bundle-checklist`.
- **Portfolio Summary** - Public-facing summary block for a finished analysis. Uses `components.portfolio-summary`.
- **Implementation Handoff** - BMAD story-ready block naming acceptance criteria, validation commands, generated artifacts, and unresolved status decisions. Uses `components.implementation-handoff`.
- **Status Badge** - Compact label for `pending`, `computed`, `partial`, `source_blocked`, `discrepant_needs_review`, `user_manual_option`, and `user_manual_approved`. Badge color comes from the exact matching token: `components.status-badge-pending`, `components.status-badge-computed`, `components.status-badge-partial`, `components.status-badge-source-blocked`, `components.status-badge-discrepant-needs-review`, `components.status-badge-user-manual-option`, or `components.status-badge-user-manual-approved`.
- **Discrepancy Panel** - Comparison block for source-backed value versus Known Answer Example. Uses `components.discrepancy-panel`.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Lead with the analytical question and source basis | Lead with decorative Formula 1 imagery |
| Use status badges with text and color together | Use red/green alone to imply correctness |
| Keep chart color focused on the claim being made | Color every team, driver, or table row by default |
| Show source limitations near the answer | Bury coverage caveats at the end of a report |
| Keep Markdown and notebooks visually consistent | Let each analysis invent its own output style |
| Use exact component and status names from this spine | Add synonyms for the same workflow surface |
