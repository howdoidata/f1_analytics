---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/UX-INTAKE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/validation-report.md
  - _bmad-output/planning-artifacts/project-state-reconstruction-2026-08-06.md
  - _bmad-output/planning-artifacts/decisions/question-actual-answer-persistence-and-live-wiring-decision-record.md
  - _bmad-output/planning-artifacts/decisions/analyst-workflow-surfaces-epic-placement-decision-record.md
  - docs/data_sources.md
---

# f1_analytics - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for f1_analytics, decomposing the requirements from the PRD, the partial UX Design contract (DESIGN.md; EXPERIENCE.md lost 2026-08-01), and the 2026-08-06 Architecture Spine into implementable stories. This is a post-data-loss rebuild: no prior epic or story is treated as done (spine AD-10); prior artifacts inform — they do not bind.

**Process enforcement:** after story creation, `bmad-sprint-planning` emits `sprint-status.yaml` and implementation runs through the `bmad-loop` orchestrator — story lifecycle, review cycles, retrospectives, and the deferred-work ledger are enforced mechanically, not by session discipline. This is the structural answer to the prior project's phases-never-closed failure; Epic 1's loss-recording commit is also what turns `bmad-loop validate` green.

### Story Format Exemplars

Story creation follows the pattern these three exemplars demonstrate — one per story species in this plan. Required elements: a user-story sentence naming a real beneficiary; Given/When/Then acceptance criteria each traceable to an FR consequence or spine AD; an explicit "Governed by" line citing the ADs; a runnable verification line (AD-11); failure paths stated inside the ACs, not left implicit; sized to one dev-agent context.

**Exemplar A — recovery/infrastructure species:**

> ### Story 1.1: Record The Loss And Gain Offsite Protection
> As Antonio, I want the 2026-08-01 loss recorded in git on a pushable clean lineage, so that the repository is honest and every rebuild artifact survives the next machine failure.
>
> **Acceptance Criteria:**
> **Given** the working tree with 206 missing tracked files and 231 broken history objects
> **When** a fresh orphan branch is created from the current tree state, the missing paths are `git rm`'d, `.bmad-loop/policy.toml` is untracked, and the branch is committed and pushed to origin
> **Then** `git status` is clean on the new branch, the push succeeds without traversing damaged history, and `bmad-loop validate` no longer fails the clean-tree gate
> **And** no `git gc`/`prune`/`repack` ran at any point (Standing Constraints), and the damaged master lineage remains intact locally for future forensics.
>
> **Verification:** `git status --porcelain | wc -l` → 0; `git ls-remote origin <branch>` shows the pushed ref. Governed by: Standing Constraints, AR-13.

**Exemplar B — spike/risk-gate species (deliverable is a decision, not code):**

> ### Story 1.2: FastF1 Adoption Spike
> As the ingestion epic's owner, I want FastF1's three adoption legs verified against reality, so that AD-6's source-role binding rests on evidence rather than documentation.
>
> **Acceptance Criteria:**
> **Given** a scratch environment with Python 3.13, pandas 3.0.x, and fastf1 3.8.x
> **When** session, lap, and stint data are loaded for all five target 2026 races (Melbourne, Miami, Canada, Barcelona, Silverstone) with the cache enabled
> **Then** each leg's outcome is recorded in a PRD §9 source decision record: pandas-3 compatibility (pass/fail + the failing surface), per-race data presence (per race, per fact class), and Kaggle dataset re-download availability
> **And** on any failing leg, the record names the fallback taken (pandas pin-down spine amendment / alternate historical source) — a failing spike is a *successful* story if the decision record is complete.
>
> **Verification:** the decision record exists in `decisions/` with all five PRD §9 fields; spike script named and runnable. Governed by: AD-6, AD-13, AR-3.

**Exemplar C — vertical feature species (Epic 2 first-light thread):**

> ### Story 2.1: One Question End-To-End (First Light)
> As Antonio, I want one results-based question (Canadian GP highest Williams finish) to travel catalog → extractor → registered build → visible output, so that the wiring the old project never built exists before any breadth.
>
> **Acceptance Criteria:**
> **Given** `catalog/question_catalog.yaml` containing the Q03 row (all AD-15 fields; `known_answer_example: null` permitted) and Epic 1's curated tables
> **When** `uv run scripts/build_question_actual_answers.py --mode post_race` runs
> **Then** `question_actual_answer_components` holds one row keyed `(2026_pdf_q03_canadian_highest_williams_finish, <component_key from catalog>, <build_id>)` with an INTEGER position, full source citation (NFR-2), and a status from AD-3 vocabulary #1
> **And** the `build_registry` shows one `complete` build spanning both target tables (an empty-but-written feature-contract set counts), the JSONL export under `exports/` contains the row, and a minimal report renders the answer with its status — never a bare value
> **And** ambiguous Williams mapping halts with a validation status rather than guessing (FR-4).
>
> **Verification:** `uv run pytest tests/ -k q03` green offline; the report artifact exists and cites its `build_id`. Governed by: AD-4, AD-5, AD-8, AD-12, AD-15.

## Requirements Inventory

### Functional Requirements

FR-1: Capture the five supplied PDF questions as structured Question Catalog rows with stable IDs, full metadata, and extension slots for at least five unknown future questions.
FR-2: Maintain a controlled Answer Type taxonomy covering the supplied examples plus recordable future categories, each defining required fields and extraction-support status.
FR-3: Separate question capture, analysis mode, prediction inputs, and actual answers — rows exist independently of predictions/answers; mode is a run parameter, never a duplicated row.
FR-4: Identify Williams race participants for a target season/grand prix via constructor mapping with alias handling; ambiguity stops extraction with a validation status.
FR-5: Compute highest Williams finishing position for a target race, representing DNS/DNF/DSQ/no-classification explicitly, with full source citation.
FR-6: Compute combined Williams finishing position (sum of classified positions), returning a validation status rather than summing incomplete data.
FR-7: Validate source coverage for lap facts (fastest-lap time, fastest-lap number, per-lap timing) before extraction; missing/partial/stale coverage produces source-blocked or partial status.
FR-8: Compute fastest race lap time by scoped driver/team, handling ties, missing times, retirements, and partial records; store normalized units, display text, and timing provenance.
FR-9: Compute personal fastest race lap number, distinguishing personal-fastest from race-fastest, recording the extraction path used.
FR-10: Produce the tyre and pit-event Source Coverage Matrix over the controlled availability vocabulary, distinguishing deterministic from narrative facts; nothing downstream marked ready while a fact's coverage is unknown.
FR-11: Classify the British GP multi-part question as one Question ID with separate components (starting compound: controlled values; first tyre-change lap: number + event type); narrative context preserved apart from deterministic components.
FR-12: Store normalized Actual Answer Components — component order/labels, unit/precision/tolerance for numerics, controlled categoricals, full source + build citation, validation status, discrepancy notes.
FR-13: Define scoring rules by Answer Type (absolute-error lap times on official timing only, exact/absolute-error for numbers/positions, categorical compounds, multi-part component + combined scores); unscoreable targets reported as unscoreable-with-reason, never as incorrect.
FR-14: Define pre-race and post-race data boundaries per Question ID; post-race facts blocked from pre-race features; same row evaluable in either mode.
FR-15: Maintain feature availability status across the eight feature groups using the controlled availability tags.
FR-16: Generate or reconstruct leakage-safe baseline Prediction Inputs recording method, boundary, inputs, and build timestamp — or unavailable-with-reason.
FR-17: Generate question-level backtest report rows (prediction, actual, score, tolerance, source, explanation) covering all five supplied examples, distinguishing prediction-wrong from actual-unscoreable.
FR-18: Preserve portfolio-ready explanation text naming driver/team/race and source limitation, narrative in notebooks/report narrative, no betting/odds framing.
FR-19: Validate question premises during extraction; when a premise is factually incorrect, mark the component `premise_incorrect` (never scored as a wrong prediction), record the failed premise with source evidence, and capture the corrected answer under the corrected premise. (Added 2026-08-06 from the recorded Q05-class failure; generalized system-wide by spine AD-16.)
FR-20: Validate user-supplied intake at entry — schema, entity resolution against known drivers/teams/races, arithmetic consistency of expected answers, range/sanity checks; auto-correct unambiguously determinable input errors (correction applied, original preserved verbatim, correction recorded and surfaced — never silent); halt ambiguous errors with options. (Added 2026-08-06; spine AD-16 intake clause.)

### NonFunctional Requirements

NFR-1: Reproducibility — all catalog, extraction, target-store, and report outputs generated from project-controlled files or local data, never hand-edited state.
NFR-2: Source transparency — every Actual Answer Component cites source artifact, table/file, and extraction method.
NFR-3: Data quality — missing, ambiguous, partial, stale, or conflicting source data produces explicit validation statuses.
NFR-4: Leakage prevention — baselines and future features honor the Feature Snapshot; post-race facts blocked for pre-race predictions.
NFR-5: Local-first operation — locally runnable and lightweight; no server, no hosted service.
NFR-6: No paid source dependency by default — paid sources require a separate PRD-level decision.
NFR-7: Extensibility without overbuilding — schema absorbs at least five unknown questions; extractors only for MVP Answer Types.

### Additional Requirements

From the Architecture Spine (architecture-f1_analytics-2026-08-06, status: final) — each is rebuild work the epics must cover, not ambient context:

- AR-1: Project foundation per AD-11 — `pyproject.toml` src layout, editable install, pytest runner, uv 0.12.x conventions (0.12.0 changed `uv init` defaults); every command runnable from a fresh clone plus documented credentials.
- AR-2: Committed Question Catalog as one tracked YAML (`catalog/question_catalog.yaml`) with the AD-15 field schema; catalog mints all `component_key`s and fact/feature-group identities; `user_manual_approved` promotions recorded here.
- AR-3: FastF1 ingestion (laps/stints/weather + Jolpica gap-fill) gated by a pandas-3.0 compatibility spike and a PRD §9 source decision record (AD-6); rate discipline, pagination-completeness verification, cache-then-parse, and budgeted runs per AD-13.
- AR-4: Storage edge per AD-4 — `question_*` DDL with INTEGER lap/position columns, replace-vs-append helper pair, `build_registry`, one `build_id` per run spanning both target tables, git-tracked JSONL export backstop under `exports/`.
- AR-5: All consumers read exactly one latest complete build per mode via the registry, citing its `build_id` (AD-5) — the live-wiring capability that closes the recorded seven-epics-over-nothing gap.
- AR-6: Five controlled vocabularies defined once (AD-3) plus the status→token module (DESIGN.md frontmatter as token authority).
- AR-7: Leakage boundary enforced by the feature-availability contract; analysis mode as run parameter recorded on builds and outputs (AD-7).
- AR-8: Publication gating per AD-8 — `(question_id, component_key)` pairing assertion, status-derived `portfolio_ready`, manual-provenance excluded from computed-success counts, type-normalized comparisons.
- AR-9: Seed-answer discipline per AD-12 — Known Answer Examples never enter the target store; source-vs-known disagreement defaults to `discrepant_needs_review`.
- AR-10: Gatherer interchange per AD-9 — producer emits HS-f1-gatherer v2-conforming packets (11 properties, correct classes, packet-standing vocabulary incl. `current`); author the in-repo contract companion from the channel declaration packet; answer gatherer's three open threads (edge-binding Q2–Q7, next-story intake, crossedge §2).
- AR-11: Build validation module — advisory null-rate/referential checks logged to `validation_results`, never halting a build (AD-4/AD-8).
- AR-12: Offline test suite — recorded fixtures cut from cached payloads; zero network in pytest (AD-11).
- AR-13: Repo recovery operations under Standing Constraints — the record-the-loss commit (206 `git rm`s + `.bmad-loop/policy.toml` untrack), selective restore from the platform snapshot (code/docs yes; the 7 post-fix Jolpica cache files always win; July-9 DuckDB never restored as truth); never `git gc`/`prune`/`repack`.
- AR-14: Universal fail-early discipline per AD-16 — every unit verifies its preconditions before doing work; a failed precondition halts that unit with an explicit finding (statused value in the core, named fast failure in shells, typed rejection at storage, pairing assertion at scoring, conformance self-check before any packet is delivered); where the true state is determinable, the finding records the corrected fact. Binds every story in every epic — this blanket rule applies regardless of whether a given story's own "Governed by" line names AD-16 locally. A local AD-16 citation marks that *this specific story* introduces a new named fail-early mechanism worth pointing at; its absence is not a signal that fail-early discipline doesn't apply there.

### UX Design Requirements

From DESIGN.md (status: final) + UX-INTAKE.md. **Partial contract:** EXPERIENCE.md (information architecture, behavior, states, journeys) is lost — component identity, tokens, and rendering rules survive; behavioral detail must be re-derived or re-decided at story time.

- UX-DR1: Report Summary — top section of every generated report: question, answer, source basis, status, next action (`components.report-summary`).
- UX-DR2: Evidence Link — inline path/source citation, visibly linked (`components.evidence-link`).
- UX-DR3: Question Intake Brief — structured block for a new question; missing required fields accented (`components.question-intake-brief`).
- UX-DR4: Question Catalog Row — dense table row; status in a dedicated column (`components.question-catalog-row`).
- UX-DR5: Reuse and Extension Review — summary block with scannable decision value (`components.reuse-and-extension-review`).
- UX-DR6: Source Coverage Matrix — table: required fact, current source, availability, status, next action (`components.source-coverage-matrix`).
- UX-DR7: Analysis Mode Boundary — `pre_race`/`post_race` + leakage boundary callout (`components.analysis-mode-boundary`).
- UX-DR8: Actual Answer Component — compact row/table block for target value + provenance (`components.actual-answer-component`).
- UX-DR9: Output Bundle Checklist — checklist for report/table/figure/notebook exports (`components.output-bundle-checklist`).
- UX-DR10: Portfolio Summary — public-facing summary block for a finished analysis (`components.portfolio-summary`).
- UX-DR11: Implementation Handoff — BMAD story-ready block: acceptance criteria, validation commands, artifacts, unresolved statuses (`components.implementation-handoff`).
- UX-DR12: Status Badge — compact label for all eight answer statuses (including `premise_incorrect`, DESIGN.md `premise-teal`/`surface-premise`); badge color from the exact matching token; text plus color, never color alone; WCAG 2.2 AA contrast on the enumerated pairs (`components.status-badge-*`).
- UX-DR13: Discrepancy Panel — source-backed value vs Known Answer Example comparison (`components.discrepancy-panel`). Blocked until the target store is populated (spine Deferred).
- UX-DR14: Target Store Review — Actual Answer Components + provenance + validation review surface (`components.target-store-review`). Blocked until the target store is populated.
- UX-DR15: Scoring and Baseline Review — Prediction Inputs vs Actual Answers vs scoreability table (`components.scoring-and-baseline-review`). Blocked until the target store is populated.
- UX-DR16: Every report surface follows the mandatory section order (question → source/cutoff basis → answer + status → supporting table/figure → limitation and next action); limitations render near the answer, never buried.
- UX-DR17: Generated surfaces use DESIGN.md §Components names verbatim; no synonyms for the same surface; DESIGN.md frontmatter is the design-token authority.

### FR Coverage Map

FR-1: Epic 2 - Five PDF questions captured as committed catalog rows with extension slots
FR-2: Epic 2 - Controlled Answer Type taxonomy with support-status per type
FR-3: Epic 2 - Capture/mode/prediction/answer separation; mode as run parameter
FR-4: Epic 2 - Williams participant identification with alias handling
FR-5: Epic 2 - Highest Williams finishing position extraction
FR-6: Epic 2 - Combined Williams finishing position extraction
FR-7: Epic 2 - Lap-fact source coverage validation before extraction
FR-8: Epic 2 - Fastest race lap time extraction (FastF1-sourced)
FR-9: Epic 2 - Personal fastest lap number extraction (FastF1-sourced)
FR-10: Epic 2 - Tyre/pit-event Source Coverage Matrix over controlled availability vocabulary
FR-11: Epic 2 - British GP multi-part classification (compound + first tyre-change lap)
FR-12: Epic 2 - Normalized Actual Answer Components persisted append-only with build registry
FR-13: Epic 3 - Scoring rules by Answer Type; unscoreable-with-reason discipline
FR-14: Epic 2 - Pre/post-race boundaries per Question ID (catalog `analysis_boundary` field, AD-15)
FR-15: Epic 2 - Feature availability contract populated by the same orchestration build (AD-4 cross-table coherence)
FR-16: Epic 3 - Leakage-safe baseline Prediction Inputs
FR-17: Epic 3 - Question-level backtest report rows for all five questions
FR-18: Epic 3 - Portfolio-ready explanation text
FR-19: Epic 2 - Premise validation with corrected-answer capture (Story 2.8); Epic 3 inherits its scoring/rendering discipline
FR-20: Epic 2 - Intake validation with auto-correction of determinable input errors (Story 2.2a)

Additional-requirement placement: Epic 1 carries AR-1, AR-3, AR-11, AR-12, AR-13; Epic 2 carries AR-2, AR-4, AR-5, AR-6, AR-7, AR-9; Epic 3 carries AR-8 and UX-DR1..17 rendering; Epic 4 carries AR-10. AR-14 (fail-early, AD-16) binds every story in every epic.

## Epic List

### Epic 1: Trustworthy Local F1 Data, Rebuilt
Antonio can rebuild the complete local dataset from a fresh clone with one documented command per stage — Kaggle curated tables, FastF1 lap/stint/weather facts, gap-filled current season — with completeness verified against source totals, rate limits respected and budgeted, validation logged, and the repository made honest. **Opening stories, in order:** (1) the recovery operations — the loss-recording commit lands on a **fresh orphan branch** (clean lineage; the damaged history's 231 broken objects make a normal push of master unviable) and pushes to origin immediately, so every rebuild artifact gains offsite protection before anything else; selective snapshot restore follows under the Standing Constraints. (2) The FastF1 spike, whose acceptance criteria are threefold: pandas-3.0 compatibility, **per-race 2026 data presence for all five target races** (Melbourne, Miami, Canada, Barcelona, Silverstone), and Kaggle dataset re-download availability — with fallbacks recorded (pandas pin-down spine amendment; alternate historical source) if any leg fails.
**FRs covered:** none directly — enables the sources for FR-4..FR-11. Carries AR-1, AR-3, AR-11, AR-12, AR-13.

### Epic 2: The Five Questions, Answered From Sources
Antonio records the five PDF questions in the committed catalog (`catalog/question_catalog.yaml`) and runs one orchestration command that extracts source-backed Actual Answer Components for all five — results-based, lap-based, and the British GP multi-part via FastF1 stint data — persisted append-only under a registered build, with honest statuses and the seed-answer discipline (source-vs-known disagreement renders `discrepant_needs_review`, never a picked value). The one orchestration command populates **both** target tables — answer components and the feature-availability contract (FR-14/FR-15, boundaries from the catalog's `analysis_boundary` field) — coherently under one `build_id` (AD-4). Catalog → extraction → persisted store lands as one wired vertical slice. **Story ordering rule (first light):** the epic's first thread takes ONE results-based question (simplest extraction path) end-to-end — catalog row → extractor → registered build → visible output — before any breadth across the other four; momentum over completeness. **External dependency (reconciliation only):** catalog rows may carry `known_answer_example: null` with an honest status, so extraction and persistence never wait on the original PDF's answer key (lost in the 2026-08-01 event; only the values quoted directly in PRD text survive) — only the AD-12 reconciliation story gates on Antonio supplying the five Known Answer Examples (surviving in PRD text: Melbourne `1:23.590`, Barcelona lap 60).
**FRs covered:** FR-1..FR-12, FR-14, FR-15, FR-19, FR-20. Carries AR-2, AR-4, AR-5, AR-6, AR-7, AR-9.

### Epic 3: Scored Backtests And Portfolio-Ready Reports
Antonio compares leakage-safe baseline predictions against the persisted actuals and gets the full backtest report — scoring rules per answer type, baselines generated against the persisted feature-availability contract (consumption only; the contract is populated in Epic 2), portfolio explanations, status badges, and every report surface in the mandated section order. Publication gating (AD-8) hardens before the first portfolio-ready render.
**FRs covered:** FR-13, FR-16..FR-18. Carries AR-8, UX-DR1..17.

### Epic 4: Gatherer Handoff, Conforming And Current
Gatherer receives HS-f1-gatherer-v2-conforming insight packages built from a single cited build; the interchange contract lives in-repo as a companion doc sourced from the channel declaration packet; and f1's three unanswered gatherer threads (edge-binding Q2–Q7, next-story intake, crossedge §2) are answered, unblocking gatherer's epic sequencing. **Known limitation f1 does not own:** gatherer's validator still recognizes only its retired `platform/exchange/` folder as the exchange channel, so delivered packets may not be citable by gatherer stories until gatherer fixes that coupling — Epic 4 does not gate on their fix; naming the defect via a channel packet is a story deliverable here. **Scope cap:** this epic delivers exactly the three named thread answers, the package producer, the defect-notice packet, and the in-repo companion — any further cross-project protocol negotiation requires a new decision record and is out of scope (the prior project drowned in governance work; this one does not).
**FRs covered:** none (capability added beyond PRD §7 per the spine's scope note). Carries AR-10. The package-producer stories build on Epics 2–3 for real content; the **thread-answer stories have no such dependency and are unblocked as soon as Epic 1's push story lands** (the intake answer only needs this epic plan, which now exists). Standalone as a capability.

## Epic 1: Trustworthy Local F1 Data, Rebuilt

Antonio can rebuild the complete local dataset from a fresh clone with one documented command per stage, with completeness verified, rate limits respected and budgeted, validation logged, and the repository made honest — recovery and offsite protection first, the triple-gated FastF1 spike second, data layers after.

### Story 1.1: Record The Loss And Gain Offsite Protection

As Antonio,
I want the 2026-08-01 loss recorded in git on a pushable clean lineage,
So that the repository is honest and every rebuild artifact survives the next machine failure.

**Acceptance Criteria:**

**Given** the working tree with 206 missing tracked files and 231 broken history objects
**When** a fresh orphan branch is created from the current tree state, the missing paths are `git rm`'d, `.bmad-loop/policy.toml` is untracked, and the branch is committed and pushed to origin
**Then** `git status` is clean on the new branch, the push succeeds without traversing damaged history, and `bmad-loop validate` no longer fails the clean-tree gate
**And** no `git gc`/`prune`/`repack` ran at any point (Standing Constraints), and the damaged master lineage remains intact locally for future forensics.

**Verification:** `git status --porcelain | wc -l` → 0; `git ls-remote origin <branch>` shows the pushed ref. Governed by: Standing Constraints, AR-13.

### Story 1.2: FastF1 Adoption Spike

As the ingestion epic's owner,
I want FastF1's three adoption legs verified against reality,
So that AD-6's source-role binding rests on evidence rather than documentation.

**Acceptance Criteria:**

**Given** a scratch environment with Python 3.13, pandas 3.0.x, and fastf1 3.8.x
**When** session, lap, and stint data are loaded for all five target 2026 races (Melbourne, Miami, Canada, Barcelona, Silverstone) with the cache enabled
**Then** each leg's outcome is recorded in a PRD §9 source decision record: pandas-3 compatibility (pass/fail + the failing surface), per-race data presence (per race, per fact class), and Kaggle dataset re-download availability
**And** on any failing leg, the record names the fallback taken (pandas pin-down spine amendment / alternate historical source) — a failing spike is a *successful* story if the decision record is complete.

**Verification:** the decision record exists in `decisions/` with all five PRD §9 fields; spike script named and runnable. Governed by: AD-6, AD-13, AR-3.

### Story 1.3: Salvage The Platform Snapshot Under The Standing Constraints

As Antonio,
I want the snapshot's recoverable assets restored without regressing corrected data,
So that the rebuild starts from everything that survived.

**Acceptance Criteria:**

**Given** the protective tarball `recovery/platform-external-f1_analytics-snapshot-2026-07-09.tar.gz`
**When** the salvage runs
**Then** `data/raw/` gains the snapshot's 8 Kaggle CSVs and 67 Jolpica JSONs EXCEPT the 7 files where a post-pagination-fix live version exists — byte-compared, live wins, and the comparison result is recorded
**And** `docs/decisions.md` (the pre-questions-era decision log) is restored to `docs/`, the V1 reference code lands under `recovery/reference/` — never under `src/` (AD-10: salvage, not fixed points) — and the July-9 `f1_analytics.duckdb` is NOT restored (disposable scaffolding, never truth)
**And** no `git restore`, `gc`, `prune`, or `repack` ran (Standing Constraints).

**Verification:** the 7 protected filenames match their pre-salvage checksums; `data/processed/` remains empty. Governed by: Standing Constraints, AD-13, AR-13.

### Story 1.4: Project Foundation That Survives A Fresh Clone

As a downstream dev agent,
I want the package skeleton, invocation convention, and offline-test harness committed,
So that every later story builds and tests identically from a bare checkout.

**Acceptance Criteria:**

**Given** a fresh clone plus the documented Kaggle credential
**When** `uv sync` and `uv run pytest` run
**Then** the environment builds against `pyproject.toml` (src layout, editable install, uv 0.12 conventions per its changed `uv init` defaults) and an initial test passes, offline
**And** the `src/f1_analytics/` skeleton matches the spine's Structural Seed (empty `data_sources/`, `database/`, `analysis/`, `validation/` packages), and a repo-wide autouse pytest fixture blocks network access so any test touching a socket fails loudly (AD-11)
**And** the README-level run instructions name every credential per source (Kaggle: token file; FastF1/Jolpica: none).

**Verification:** `uv run pytest` green on a scratch clone; a deliberately network-touching test fails. Governed by: AD-11, AR-1, AR-12.

### Story 1.5: Kaggle Curated Layer, Rebuilt

As Antonio,
I want the historical Kaggle dataset landed and curated into DuckDB,
So that results-based questions have their authoritative source again.

**Acceptance Criteria:**

**Given** the restored/re-downloaded Kaggle CSVs and the 1.4 skeleton
**When** `uv run scripts/build_f1_dataset.py` runs
**Then** the `raw_*` and curated tables (races, results, drivers, constructors, circuits, qualifying, enriched results, standings-by-round, final standings) exist via the storage edge's replace-sync helper — the only writer this story creates (AD-4 class 1; the append helper is NOT built here)
**And** cumulative standings are computed by one shared function reused by every standings table (conventions: no parallel implementations), and the one sanctioned name→id reconciliation (`final_driver_standings.constructor_id`) is implemented as specified (AD-14)
**And** a stale-or-missing CSV fails fast with a named prerequisite error (shell fail-fast convention), never a silently thinner table.

**Verification:** offline tests against fixture CSVs verify table shapes + the reconciliation; the script errors clearly with a CSV removed. Governed by: AD-1, AD-4, AD-14.

### Story 1.6: FastF1 Facts Landed With Rate Discipline

As Antonio,
I want lap timing, tyre stints, and weather for the five target races landed from FastF1 without a single rate-limit error,
So that the lap/tyre questions have a verified source.

**Acceptance Criteria:**

**Given** the spike's decision record (1.2) and the 1.5 curated layer
**When** `uv run scripts/pull_fastf1_data.py` runs for the five target races
**Then** `raw_fastf1_laps`, `raw_fastf1_stints`, and `raw_fastf1_weather` are landed with every row mapped to the shared id space at the loader boundary (AD-14, name-derived, never car number), completeness verified against the session's own lap/driver counts, and a truncated fetch recorded as a statused failure — never a shorter table (AD-13)
**And** FastF1's cache is enabled at `data/raw/fastf1_cache/` and a second run completes from cache with zero network requests
**And** any 429/5xx path goes through bounded exponential backoff with a retry cap, and rate constants live as named values beside the client.

**Verification:** offline tests on recorded fixtures; a live run followed by an immediate re-run shows zero fresh requests in the second. Governed by: AD-6, AD-13, AD-14.

### Story 1.7: Current-Season Combined Tables And The Coverage Arbiter

As Antonio,
I want the current season gap-filled and the precedence arbiter live,
So that every consumer resolves Kaggle-vs-gap-fill conflicts identically.

**Acceptance Criteria:**

**Given** curated Kaggle tables and FastF1's Ergast-compatible Jolpica access (budgeted per AD-13: run planned against the 500/hour cap)
**When** `uv run scripts/build_combined_dataset.py` runs
**Then** the `kaggle_jolpica_coverage` view (defined in `sql/`) tags every season/round with the AD-2 vocabulary, and `combined_results` + combined standings exist with a `source` column, Jolpica-sourced rows filling ONLY `jolpica_only` season/rounds
**And** any `row_count_diverges` round keeps Kaggle rows and the build output names it as a documented deviation
**And** missing prerequisites (curated tables absent) fail fast with a named error.

**Verification:** offline tests cover match/kaggle_only/jolpica_only/diverges cases from fixtures; the view is the only place the comparison is computed. Governed by: AD-2, AD-13, AD-14.

### Story 1.8: Advisory Build Validation, Logged

As Antonio,
I want every build's data quality checked and logged without ever halting a build,
So that trust in the rebuilt data is recorded, not assumed.

**Acceptance Criteria:**

**Given** the curated + combined tables
**When** any build script completes
**Then** null-rate checks (results season/round/driver_id/position/points; drivers/constructors ids; the reconciled constructor_id) and referential-integrity checks (results→drivers, results→constructors, races→circuits) run and log one row per check per build to `validation_results`
**And** when a live-fetched table's write is refused by `write_dataframe`'s regression guard (`refuse_regression`), that refusal is logged as a `regression_refused` finding in `validation_results` naming the table, race/season/round, and both row counts — visibility into a guard that already prevented the bad write from landing, per AR-11's advisory-log design (Added 2026-08-08: guard shipped in commit `2d6d24b`)
**And** a standings-reconciliation check compares each `*_standings_by_round` row's `race_points` against the sum of that driver/season/round's `results.points` rows and logs a `race_points_mismatch` finding per disagreement (Added 2026-08-08: defect class verified live against `combined_driver_standings_by_round` — 40 pre-2026 rows, zero in 2026 data)
**And** `source_registry` and `source_load_log` record every documented source and loaded table (AD-4 metadata class, append-per-build), and a failing check surfaces in script output while the build still completes (advisory, AD-8)
**And** `validation/` reads only via `database/` and is imported by scripts, never by `analysis/`.

**Verification:** offline test seeds a violation into a fixture table and asserts the logged failure row plus a zero exit code, PLUS a fixture asserting a refused-write event lands as a `regression_refused` finding, PLUS a fixture with a duplicate shared-drive result row asserting the `race_points_mismatch` finding. Governed by: AD-4, AD-8, AR-11.

## Epic 2: The Five Questions, Answered From Sources

Antonio records the five PDF questions in the committed catalog and runs one orchestration command that extracts source-backed Actual Answer Components for all five, persisted append-only under a registered build — first light on one question before any breadth, both target tables coherent per build, the human-input gate isolated to reconciliation, and premises verified before any computation.

### Story 2.1: One Question End-To-End (First Light)

As Antonio,
I want one results-based question (Canadian GP highest Williams finish) to travel catalog → extractor → registered build → visible output,
So that the wiring the old project never built exists before any breadth.

**Acceptance Criteria:**

**Given** `catalog/question_catalog.yaml` containing the Q03 row (all AD-15 fields; `known_answer_example: null` permitted) and Epic 1's curated tables
**When** `uv run scripts/build_question_actual_answers.py --mode post_race` runs
**Then** `question_actual_answer_components` holds one row keyed `(2026_pdf_q03_canadian_highest_williams_finish, <component_key from catalog>, <build_id>)` with an INTEGER position, full source citation (NFR-2), and a status from AD-3 vocabulary #1
**And** the `build_registry` shows one `complete` build spanning both target tables (an empty-but-written feature-contract set counts), the JSONL export under `exports/` contains the row, and a minimal report renders the answer with its status — never a bare value
**And** ambiguous Williams mapping halts with a validation status rather than guessing (FR-4).

**Verification:** `uv run pytest tests/ -k q03` green offline; the report artifact exists and cites its `build_id`. Governed by: AD-4, AD-5, AD-8, AD-12, AD-15.

### Story 2.2: The Full Catalog, Taxonomy, And Boundaries

As Antonio,
I want all five questions cataloged with the complete Answer Type taxonomy and per-question boundaries,
So that every downstream story consumes one identity authority.

**Acceptance Criteria:**

**Given** the 2.1 catalog loader
**When** `catalog/question_catalog.yaml` is completed
**Then** all five questions exist as rows with every AD-15 field (`known_answer_example: null` permitted pending Antonio's input), the British GP question is ONE row with two components minted here (compound; first-change lap), and ≥5 extension slots exist without extractor obligations (FR-1, NFR-7)
**And** the taxonomy covers the seven MVP answer types plus the recordable future categories, each declaring required fields and `extraction_support_status` (FR-2), and the remaining controlled vocabularies (coverage availability, feature availability, feature groups) are defined once in `analysis/` (AD-3 #2–4)
**And** each row carries its `analysis_boundary` (FR-14) and a schema-invalid catalog fails the loader with named errors, never a partial parse (AD-16)

**Verification:** offline tests: round-trip load, five rows + slots, invalid-catalog rejection, vocabulary imports from one module. Governed by: AD-3, AD-7, AD-15, AD-16.

### Story 2.2a: Intake Validation With Auto-Correction

As Antonio,
I want new-question intake batches validated and unambiguous errors auto-corrected at entry,
So that a bad intake row is caught before it ever reaches the committed catalog.

**Acceptance Criteria:**

**Given** an intake batch (`catalog/intake/*.yaml`) targeting the 2.2 catalog schema
**When** the intake validator runs
**Then** each row is checked against schema, entity resolution against known drivers/teams/races, arithmetic consistency of expected answers (e.g. P9+P10=19), and range/sanity checks (FR-20)
**And** unambiguously determinable input errors are auto-corrected — the correction applied, the original value preserved verbatim, and the correction recorded and surfaced, never silent — while ambiguous errors halt that row with the candidate options (AD-16 intake clause).

**Verification:** offline tests: schema-valid pass-through, entity-resolution failure, arithmetic-consistency auto-correction with preserved original, ambiguous-input halt. Governed by: AD-16, FR-20.

**Split note (2026-08-08, sprint-planning readiness pass):** originally a fourth "And"-clause on Story 2.2, matching the exact density pattern (≥3 "And"-clauses) that forced Story 1.8 into a mid-build spec split. Pulled out now, pre-build, to avoid repeating that split live. No decision content changed — the acceptance criteria text is unedited, only relocated.

### Story 2.3: Results-Based Extraction — Miami And Canada Complete

As Antonio,
I want Williams participants resolved and both results-based questions computed,
So that Q02 and Q03 carry source-backed components.

**Acceptance Criteria:**

**Given** the combined tables (1.7) and the full catalog (2.2)
**When** the orchestration runs in `post_race` mode
**Then** participant resolution maps "Williams"/"Williams F1 Team"/"Atlassian Williams F1 Team" aliases to the constructor identity, and ambiguous or missing mapping halts that question with a validation status — never a guess (FR-4, AD-16)
**And** Q03's highest finish and Q02's combined finish are computed with DNS/DNF/DSQ/no-classification represented from source status fields before any arithmetic — an unclassified driver makes the combined answer a statused non-sum (FR-5, FR-6)
**And** every component records source table, row grain, and the AD-2 precedence path used, as INTEGER positions.

**Verification:** offline tests cover classified, DNF-one-driver, and ambiguous-mapping fixtures. Governed by: AD-2, AD-8, AD-14, AD-16.

### Story 2.4: Lap Facts — Melbourne And Barcelona Complete

As Antonio,
I want lap coverage validated and both lap questions computed from FastF1 timing,
So that Q01 and Q04 carry source-backed components.

**Acceptance Criteria:**

**Given** `raw_fastf1_laps` (1.6) and the catalog
**When** the orchestration runs
**Then** the coverage check classifies fastest-lap-time, fastest-lap-number, and per-lap availability per question BEFORE extraction, emitting `source_blocked`/`partial` where rows are missing (FR-7, AD-16)
**And** Q01 returns the fastest Williams lap at Melbourne (normalized units, display text, timing provenance; ties and retirements handled explicitly — FR-8) and Q04 returns Sainz's personal fastest lap number at Barcelona, distinguished from the race-fastest lap, as INTEGER (FR-9)
**And** extraction never silently substitutes a result-level field for lap-level timing without recording which path produced the value
**And** before extracting Q04, Barcelona's leg of the 1.2 spike decision record is re-verified live — if the 2026-09-13 session still hasn't occurred (or `raw_fastf1_laps` otherwise carries no real Barcelona rows), Q04 renders `source_blocked` naming the future date, never a stale cache or partial substitute passed off as complete (AD-13's "never a shorter table"; the Q04 failure class AD-12 exists to prevent, per the pre-rebuild Jolpica-pagination lesson it was written from).

**Verification:** offline tests: tie case, missing-laps case, personal-vs-race distinction fixture, Barcelona-not-yet-occurred fixture asserting `source_blocked` over a stale/partial cache. Governed by: AD-6, AD-8, AD-12, AD-13, AD-16.

### Story 2.5: The Coverage Matrix And The British GP Multi-Part

As Antonio,
I want the tyre/pit coverage matrix rendered and Q05's two components computed from stint data,
So that the question that was source-blocked for the entire prior project finally has source-backed answers.

**Acceptance Criteria:**

**Given** `raw_fastf1_stints` (1.6) and the catalog
**When** the orchestration and the matrix render run
**Then** the Source Coverage Matrix artifact (outputs/, per UX-DR6 shape) classifies starting compound, stint compounds, pit-stop lap, tyre-change lap, incident context, front-wing change, restart context, and retirement lap over the AD-3 #2 vocabulary, separating deterministic from narrative facts (FR-10)
**And** Q05's starting-compound component (controlled values: soft/medium/hard/intermediate/full_wet/unknown/not_applicable) and first-tyre-change-lap component (INTEGER + event type) are computed from stints, with the narrative (lap-1 collision/restart) preserved as a note, never a component (FR-11)
**And** the 2026-07-28 OpenF1 verification (compound=MEDIUM) enters as a cited corroborating fact, not a data row (AD-5); a stint gap renders `partial`, never a guess.

**Verification:** offline tests on stint fixtures incl. a missing-stint case; the matrix artifact exists with no `unknown` left silent. Governed by: AD-3, AD-5, AD-6, AD-15.

### Story 2.6: The Feature Contract, Written By The Same Build

As the future modeling epic's owner,
I want feature-group availability evaluated and persisted in the same build as the answers,
So that the leakage boundary is data, not discipline.

**Acceptance Criteria:**

**Given** the catalog boundaries and current table inventory
**When** the orchestration completes a build
**Then** `question_feature_availability_contract` holds one row per (question, feature group) for all eight AD-3 #4 groups, tagged from the AD-3 #3 vocabulary, under the SAME `build_id` as the answer components (AD-4 coherence)
**And** post-race fact groups are marked forbidden for `pre_race` runs and the contract enforces it: a `pre_race` build refuses forbidden-group inputs and records the refusal (AD-7, FR-14/15, AD-16)
**And** the JSONL export covers both tables' rows for the build.

**Verification:** offline tests: one build writes both tables under one id; a pre_race run with a forbidden group input yields the refusal record. Governed by: AD-4, AD-5, AD-7, AD-16.

### Story 2.7: Known-Answer Reconciliation (Gates On Antonio's Input)

As Antonio,
I want the supplied Known Answer Examples reconciled against computed components under the default-deny rule,
So that agreement is evidence and disagreement is a review item — never a silent pick.

**Acceptance Criteria:**

**Given** Antonio's five Known Answer Examples entered into the catalog (the external dependency; Melbourne `1:23.590` and Barcelona lap 60 already survive in PRD text)
**When** the reconciliation pass runs against the latest complete build
**Then** each component's status reflects the comparison: agreement stays `computed`; disagreement becomes `discrepant_needs_review` with both values recorded (the expected Q04 60-vs-source case must land as exactly this)
**And** no Known Answer Example value ever enters `question_actual_answer_components` as an answer (AD-12); any `user_manual_option`/`user_manual_approved` promotion path exists only as a recorded catalog edit by Antonio
**And** the discrepancy detail renders in the report near the answer (conventions), naming both values and their provenances.

**Verification:** offline tests: agree, disagree, and null-known cases; assertion that no catalog answer value reaches the store writer. Governed by: AD-3, AD-12.

### Story 2.8: Premise Validation With Corrected Answers

As Antonio,
I want every question's premises verified before extraction, with the correct answer captured whenever a premise proves false,
So that a wrongly-premised question fails early with the truth attached instead of surfacing garbage or hanging open (the Q05 retirement-lap failure class).

**Acceptance Criteria:**

**Given** catalog components carrying declared checkable premises (AD-15: e.g. "the driver participated in the race", "a tyre change occurred", "the driver retired") and a completed build's source tables
**When** extraction runs for any question
**Then** each declared premise is verified BEFORE computation (AD-16); a false premise halts that component immediately with status `premise_incorrect`, recording `premise_finding` (the failed premise + source evidence) and `corrected_answer` (the answer under the corrected premise) in the store row and JSONL export
**And** a `premise_incorrect` component is excluded from wrong-prediction scoring downstream (it is neither correct nor incorrect — the question was), renders with its own badge token (the recorded DESIGN.md eighth-token delta), and shows the premise correction near the answer
**And** the mechanism is exercised by at least one real fixture reproducing a false-premise case (e.g. a retirement-lap question where the source shows the driver was classified), and premise checks compose with the other fail-early gates without double-reporting.

**Verification:** offline tests: true-premise pass-through, false-premise with corrected answer, and no-declared-premise (vacuous pass) cases. Governed by: AD-3, AD-12, AD-15, AD-16.

## Epic 3: Scored Backtests And Portfolio-Ready Reports

Antonio compares leakage-safe baseline predictions against the persisted actuals and gets the full backtest report — scoring, baselines, explanations, badges, workflow surfaces, and the now-unblocked Track-2 review surfaces (the UX-DR13/14/15 surfaces deferred pending the target store) — with publication gating hardened before the first portfolio-ready render.

### Story 3.1: Scoring Rules Over One Complete Build

As Antonio,
I want every component scored by its answer type's rule against the latest complete build,
So that scores are reproducible and mispairing is impossible.

**Acceptance Criteria:**

**Given** a complete build in the registry and Prediction Inputs
**When** scoring runs
**Then** each answer type applies its rule — configurable absolute-error for lap times (official timing only), exact/absolute-error for lap numbers and positions, controlled categorical for compounds, component + combined scores for multi-part (FR-13)
**And** every prediction↔actual pairing asserts `(question_id, component_key)` equality before comparison (AD-8, AD-16), comparisons normalize types first (no float-promotion fabrications), and unscoreable targets report unscoreable-with-reason — `premise_incorrect` components are excluded from wrong-prediction scoring as their own reason class (FR-19)
**And** scoring reads exactly one `build_id` and stamps it on every score row.

**Verification:** offline tests per answer type + the mispairing rejection + the premise-excluded case. Governed by: AD-3, AD-5, AD-8, AD-16.

### Story 3.2: Leakage-Safe Baseline Predictions

As Antonio,
I want baseline Prediction Inputs generated only from leakage-safe features,
So that backtests rest on honest predictions.

**Acceptance Criteria:**

**Given** the persisted feature-availability contract (Epic 2.6)
**When** `uv run scripts/build_question_baseline_predictions.py --mode pre_race` runs
**Then** baselines are generated per question recording method, feature boundary, source inputs, and build timestamp (FR-16), consuming only feature groups the contract marks usable for `pre_race`
**And** a question with no leakage-safe baseline path is marked unavailable-with-reason — never a baseline built on forbidden facts (AD-7, AD-16 precondition check before generation)
**And** baselines are stored citably so scoring can consume them without hand-carried data (AD-5 pattern).

**Verification:** offline tests: usable-group baseline, forbidden-group refusal, unavailable-with-reason. Governed by: AD-5, AD-7, AD-16.

### Story 3.3: The Backtest Report, All Five Questions

As Antonio,
I want one report showing prediction vs actual vs score for every question,
So that the flagship deliverable finally answers what it exists to answer.

**Acceptance Criteria:**

**Given** scored components (3.1) and the build registry
**When** `uv run scripts/build_backtest_report.py` runs
**Then** the report renders one row per Question ID — prediction, actual, score, tolerance, source, explanation — covering all five supplied questions (FR-17), each row showing its AD-3 status and the single `build_id`
**And** "prediction-wrong" and "actual-unscoreable" are visually and semantically distinct, `discrepant_needs_review` rows show both values near the answer, and `premise_incorrect` rows show the premise correction with the corrected answer
**And** `portfolio_ready` derives from validation status AND the mode boundary; `user_manual_approved` rows are excluded from computed-success counts with provenance shown on every aggregate (AD-8).

**Verification:** offline golden-file test of the rendered report from fixture store rows covering every status. Governed by: AD-3, AD-5, AD-8, AD-12.

### Story 3.4: Portfolio Explanations With The Framing Guardrail

As a portfolio reviewer,
I want each question's outcome explained in plain prose citing its source limits,
So that I can trust what I read without inspecting tables.

**Acceptance Criteria:**

**Given** report rows (3.3)
**When** explanation text is generated
**Then** each explanation names the driver/team/race and the governing source limitation without requiring raw-table inspection (FR-18), narrative context (e.g. the British GP incident) lives in report narrative citing the status it explains — never inside deterministic components
**And** generated text containing betting/odds/gambling/wagering framing fails generation loudly (conventions guardrail, AD-16 as a pre-emit check)
**And** truncation, missing fields, and unscoreable cases produce complete sentences, not template fragments.

**Verification:** offline tests incl. a forbidden-term injection that must fail. Governed by: AD-8, AD-16, conventions.

### Story 3.5: Status Badges And The Report Surface System

As Antonio,
I want every surface rendering status identically from one token authority,
So that the outputs read as one system.

**Acceptance Criteria:**

**Given** the AD-3 vocabularies
**When** any surface renders a status
**Then** one module owns status→token mapping sourced from DESIGN.md frontmatter — including the recorded eighth token for `premise_incorrect` added to DESIGN.md (UX-DR12 + the UX delta) — with text plus color always, never color alone, and AA contrast on the enumerated pairs
**And** every report surface follows the mandated section order (question → source/cutoff basis → answer + status → supporting table/figure → limitation and next action) with limitations near the answer (UX-DR16), and the Report Summary, Evidence Link, and Analysis Mode Boundary components render per their DESIGN.md contracts (UX-DR1, 2, 7)
**And** surface names match DESIGN.md §Components verbatim (UX-DR17).

**Verification:** offline snapshot tests per component; a contrast assertion on badge pairs. Governed by: AD-3, conventions, UX-DR1/2/7/12/16/17.

### Story 3.6: Analyst Workflow Surfaces

As Antonio,
I want the intake, catalog, reuse, and handoff surfaces rendered from the persisted store,
So that working a new question has a visible workflow again.

**Acceptance Criteria:**

**Given** the catalog and a complete build
**When** the workflow surfaces render
**Then** the Question Intake Brief (missing required fields accented), Question Catalog Row table (status in its dedicated column), Reuse and Extension Review, and Implementation Handoff blocks render per their DESIGN.md contracts (UX-DR3, 4, 5, 11)
**And** every surface reads from persisted artifacts only (AD-5) and renders honestly for empty/pending states (a question with no build renders `pending`, never an error or blank)
**And** the Actual Answer Component block (UX-DR8) renders value + provenance for each component.

**Verification:** offline snapshot tests incl. the no-build state. Governed by: AD-5, UX-DR3/4/5/8/11.

### Story 3.7: The Output Bundle And Portfolio Summary

As Antonio,
I want the publication-facing bundle gated and summarized,
So that what leaves this project is exactly what the gates passed.

**Acceptance Criteria:**

**Given** rendered reports and surfaces
**When** the output bundle builds
**Then** the Output Bundle Checklist (UX-DR9) tracks each export's presence and status, and the Portfolio Summary (UX-DR10) renders only from `portfolio_ready` rows — a bundle with zero ready rows renders honestly as not-portfolio-ready, never an empty success
**And** the "why it matters" content per question is genuine per-question prose (the recorded 6.7/6.8 hardcoded-literal failure must be impossible: a literal repeated across questions fails the build)
**And** every bundle artifact cites its `build_id`.

**Verification:** offline tests: zero-ready bundle, repeated-literal rejection, checklist completeness. Governed by: AD-5, AD-8, UX-DR9/10.

### Story 3.8: Track-2 Review Surfaces (Now Unblocked)

As Antonio,
I want the Target Store Review, Scoring and Baseline Review, and Discrepancy Panel live,
So that the review surfaces the old project could only design are finally built on the store that now exists.

**Acceptance Criteria:**

**Given** a populated target store with ≥2 builds
**When** the Track-2 surfaces render
**Then** Target Store Review shows components + provenance + validation status across the store (UX-DR14), Scoring and Baseline Review compares predictions/actuals/scoreability (UX-DR15), and the Discrepancy Panel shows source-backed vs Known Answer values preserving both across re-runs (UX-DR13) — the Q04 case renders here
**And** the Discrepancy Panel is the SOLE surface reading across builds (AD-5's exception), every other surface stays single-build
**And** all three render honestly when the store has one build or no discrepancies.

**Verification:** offline tests with two-build fixtures; an assertion that only the panel's query spans builds. Governed by: AD-4, AD-5, UX-DR13/14/15.

## Epic 4: Gatherer Handoff, Conforming And Current

Gatherer receives v2-conforming insight packages built from a single cited build, the interchange contract lives in-repo, and f1's three unanswered threads are answered — scope-capped to exactly these deliverables; further protocol negotiation requires a new decision record.

### Story 4.1: The In-Repo Interchange Companion

As a downstream dev agent,
I want the full HS-f1-gatherer v2 contract inlined into a tracked reference doc,
So that the producer can be built without reading a repo AD-9 forbids reading.

**Acceptance Criteria:**

**Given** the channel declaration packet (`gatherer-handoff-spec-item-set-declaration-2026-07-30.md`) — never a cross-repo read
**When** the companion doc is authored under `docs/`
**Then** it inlines the 11 evidence-delivery key names with one-line obligations, the three packet classes with their selection tests, the correction rules (frontmatter-only supersession, authority statement, total restatement of the receiver-owned 14-item Q05 set), the packet-standing vocabulary including `current`, and the envelope frontmatter contract with `authored_at` semantics
**And** the spine's `[ASSUMPTION]` on the sourcing-packet restatement column is resolved against the authority packet's three-column form and recorded
**And** the doc pins v2 and states the re-check trigger (any new declaration packet).

**Verification:** every claim in the companion carries a channel-packet citation; zero cross-repo paths referenced. Governed by: AD-9, AD-16.

### Story 4.2: Answer The Three Threads And Name The Defects

As gatherer's counterparty,
I want f1's three open threads answered and the channel defects named,
So that gatherer's Epic 4 sequencing unblocks and the leaky channel gets fixed on the record.

**Acceptance Criteria:**

**Given** the epic plan (which makes the next-story answer scopeable) and the companion (4.1)
**When** the packets are authored into the shared exchange folder
**Then** three conforming packets answer: edge-binding Q2–Q7 (restating the durable Q1 answer — `observable_paths.f1` = `[]` permanently), the next-story intake (Expected/Needs-clarification/Enhancement form), and the crossedge §2 question — each on its proper `thread`, correct `packet_class` semantics, full envelope frontmatter, `body_sha256`
**And** a fourth packet names the two channel defects: gatherer's `platform/exchange/` code coupling (with the three-lost-packets evidence) and the README's stale §1 path — stated as observations, no directives (AD-9's `to:` standing discipline)
**And** every packet passes the AD-16 conformance self-check before delivery, and none is ever edited after delivery.

**Verification:** self-check output per packet; filenames match the f1-owned convention. Governed by: AD-9, AD-16.

### Story 4.3: The Insight-Package Producer, Rebuilt To v2

As Antonio,
I want insight packages generated from a single cited build with all 11 required properties,
So that what f1 hands gatherer is mechanically conforming before it moves.

**Acceptance Criteria:**

**Given** a complete build with scored, statused components (Epics 2–3)
**When** `uv run scripts/build_insight_packages.py` runs
**Then** each package states the 11 v2 properties by their spec key names (`source_scope: user_provided`, `authorization` with the explicit denial sentence, `portfolio_status`, `analysis_status`, `decision_question`, `evidence_refs` with labels-vs-paths stated, `findings` separating facts from unresolved discrepancies, `assumptions`, `known_gaps`, `handoff_level`, `producer_run_id`), with Package ID `{question_id}:{producer_run_id}` and every value drawn from the build — internal AD-3 statuses translated, never emitted raw
**And** the producer runs the AD-16 conformance self-check and refuses to write a non-conforming package (fail early, with the failing key named)
**And** packages are staged locally (`outputs/packages/`), not delivered — delivery is a separate, deliberate act (4.4).

**Verification:** offline tests: conforming package golden file; a package missing `known_gaps` refuses with the key named; the denial sentence present. Governed by: AD-5, AD-9, AD-16.

### Story 4.4: First Conforming Delivery

As Antonio,
I want the rebuilt packages delivered to the shared folder with the correct class semantics,
So that gatherer's record of f1's questions becomes current again.

**Acceptance Criteria:**

**Given** staged packages (4.3) and the prior Q05 disposition on record
**When** delivery runs (an explicit, per-package human-confirmed act — packets are outward-facing)
**Then** the Q05 update goes as a **new `evidence_delivery` at a declared handoff level** — not a correction — because changed evidence never travels as a correction (AD-9 reopening rule), while any pure erratum against f1's own prior packets uses `correction` class with frontmatter supersession and the full 14-item restatement using the packet-standing vocabulary
**And** each delivered file follows the f1 filename convention with `authored_at` in the authoring zone, passes the self-check, and is recorded as immutable (a delivery log notes name + `body_sha256`)
**And** f1's lost-packet situation is stated inside the packages' `assumptions`/`known_gaps` where relevant (e.g. conformance to v2 as authority, f1's copy of the original response lost).

**Verification:** delivered filenames + hashes logged; class-selection test cases offline. Governed by: AD-9, AD-16.
