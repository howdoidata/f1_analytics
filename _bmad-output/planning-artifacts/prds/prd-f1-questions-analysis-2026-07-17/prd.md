---
title: "2026 F1 Questions Analysis And Backtesting Capability"
status: final
created: 2026-07-17
updated: 2026-07-17
source_material:
  - "_bmad-output/planning-artifacts/prd-intake/2026-f1-questions-analysis-story-candidates.md"
  - "external/f1-questions/Gmail - 2026 F1 Questions.pdf"
---

# PRD: 2026 F1 Questions Analysis And Backtesting Capability

## 0. Document Purpose

This PRD defines the next planning surface for the `f1_analytics` project: a reusable capability for turning event-specific 2026 Formula 1 prediction questions into structured questions, deterministic actual-answer extraction, normalized backtest targets, and baseline scoring outputs. It is written for Antonio and downstream BMAD planning, architecture, story, and implementation agents. Functional requirements use stable IDs, Glossary terms are used consistently, and inferred items are marked with `[ASSUMPTION]` and indexed at the end.

This PRD is based on the PRD intake artifact and the one-page Gmail PDF containing five Williams-focused 2026 F1 question/answer examples (listed above at `external/f1-questions/Gmail - 2026 F1 Questions.pdf`, moved from `docs/inbox/Gmail - 2026 F1 Questions.pdf` by Story CP-019.1, 2026-07-18). It does not replace the existing PRD for the shipped local analytics product.

## 1. Vision

`f1_analytics` already proves that local F1 data can be ingested, validated, modeled into reusable DuckDB tables, and turned into portfolio-ready analysis. The next capability should let the project handle a more question-driven workflow: given a natural-language F1 prediction question, the system should record what was being asked, identify the deterministic target variable, extract the actual answer from source data where possible, and score predictions against that actual answer.

The first version should support both pre-race and post-race analysis modes through an explicit mode flag or equivalent run setting. Post-race mode may compute Actual Answers from completed race facts; pre-race mode may generate or reconstruct Prediction Inputs from allowed pre-race data only. Switching modes should be a small configuration change, not a separate workflow.

The first version should focus on factual answer extraction, generated or reconstructed baselines, and backtest readiness, not forecasting model sophistication. If the project cannot reliably compute the actual answers, later model experiments will be hard to trust and easy to leak post-race information into. The PRD therefore treats the supplied PDF answers as seed examples to validate extraction against, not as a substitute for source-backed actuals.

The practical outcome is an internal analytics layer that can support the first five Williams-focused questions and avoid overfitting to them. It should be flexible enough for at least five additional unknown F1 questions without forcing speculative model or data-source work into the MVP.

## 2. Target User

### 2.1 Jobs To Be Done

- **JTBD-1:** As Antonio, I want F1 prediction questions converted into structured, source-backed targets so I can analyze and score them reproducibly instead of treating each one as a one-off note.
- **JTBD-2:** As Antonio, I want the system to separate pre-race prediction generation from post-race actual-answer extraction so later modeling work rests on trustworthy labels.
- **JTBD-3:** As a downstream implementation agent, I want each question type mapped to required data, validation, and scoring rules so I can build stories without reinterpreting the PDF manually.
- **JTBD-4:** As a portfolio reviewer, I want generated outputs to cite data coverage and limitations so I can trust which answers are computed, `user_manual_approved`, or currently unanswerable from available sources.

### 2.2 Non-Users (v1)

- Public end users are not the v1 audience; this is an internal portfolio analytics extension.
- Betting, gambling, odds, and wagering workflows are out of scope.
- Production ML platform operators are not the v1 audience; this remains a lightweight local analytics project.
- General motorsport audiences are secondary; the initial source set is Formula 1 and Williams-focused.

### 2.3 Key User Journeys

- **UJ-1. Antonio captures a received F1 question set.** Antonio receives a set of F1 prediction questions and known answer examples. He records each question in the Question Catalog with season, grand prix, session, team/driver scope, metric, answer type, source reference, and known answer. The value lands when the question set has stable IDs and every question can be routed to an extraction or source-coverage path.

- **UJ-2. Antonio computes actual answers for answerable questions.** Antonio runs the extraction workflow against the local DuckDB data. Results-based and lap-time questions produce Actual Answer rows with source citations and validation status. The value lands when the output either matches the PDF known answer or records a source discrepancy clearly enough for review.

- **UJ-3. Antonio evaluates an answer type that may need a new source.** Antonio checks a tyre or incident-context question. The system records which facts are available from current data, which require supplemental data, and whether a `user_manual_option` exists. The value lands when the question is classified as computed, `user_manual_option`, `user_manual_approved`, or blocked by source coverage before model work begins.

- **UJ-4. Antonio compares predictions against actuals.** Antonio runs generated or reconstructed Prediction Inputs through a baseline backtest report. The report shows question, prediction, actual answer, scoring rule, score, source, and explanation. The value lands when the report can distinguish a wrong prediction from an unscoreable target.

## 3. Glossary

- **Question Set** - A collection of related F1 prediction questions from one source artifact or intake event.
- **Question Catalog** - A structured table or file containing one row per question, with stable IDs and metadata needed for extraction and scoring.
- **Question ID** - A stable identifier for one natural-language question in the Question Catalog.
- **Answer Type** - The controlled category of answer a question expects, such as lap time, lap number, finishing position, combined finishing position, tyre compound, pit/change lap, or multi-part answer.
- **Known Answer Example** - The answer text supplied in the PDF. It is used for validation and reconciliation, not treated as the final source-backed actual by itself.
- **Actual Answer** - A computed or explicitly sourced answer used as the target for scoring.
- **Actual Answer Component** - One component of a multi-part Actual Answer, such as tyre compound and first tyre-change lap for the British GP question.
- **Backtest Target Store** - A normalized table or file linking Question IDs to Actual Answer Components, source citations, units, tolerances, and validation status.
- **Prediction Input** - A predicted answer supplied or reconstructed for a Question ID before scoring.
- **Analysis Mode** - The run mode for a question workflow: `pre_race` uses only facts available before the event boundary, while `post_race` can compute Actual Answers from completed event data.
- **Generated Baseline Prediction** - A simple project-generated or reconstructed Prediction Input used for backtesting before model experiments exist.
- **Scoring Rule** - The comparison method used for an Answer Type, such as exact match, absolute error, categorical match, or multi-part component scoring.
- **Feature Snapshot** - The pre-race data boundary that defines which facts are allowed for future model features without leakage.
- **Data Leakage** - Use of post-race or post-event facts in a feature set intended to represent what was knowable before the race.
- **Combined dataset** - The repo's additive current-season `combined_results` and combined standings tables built from Kaggle plus Jolpica under the source precedence rule.
- **Source precedence rule** - Kaggle wins for any season/round where Kaggle has results rows; Jolpica fills only where Kaggle has zero rows; divergent overlaps must be surfaced rather than silently resolved.
- **Source Coverage Matrix** - A decision artifact showing whether each required fact is available, derivable, `user_manual_option`, `user_manual_approved`, or blocked by missing data.

## 4. Features

### 4.1 Question Catalog And Answer Schema

**Description:** The system records the PDF questions as structured Question Catalog entries with stable IDs, metadata, Answer Types, known examples, and extraction/scoring routing. This realizes UJ-1 and supports all downstream features.

**Functional Requirements:**

#### FR-1: Capture supplied questions as structured catalog rows

Antonio can create Question Catalog rows for the five supplied PDF questions: Melbourne fastest Williams lap time, Miami combined Williams finishing positions, Canadian highest Williams finishing position, Barcelona Carlos Sainz personal fastest lap number, and British GP Alex Albon starting tyre compound plus first tyre-change lap.

**Consequences (testable):**
- Each supplied PDF question has exactly one Question ID.
- Each row records season, grand prix, race/session context, team scope, driver scope where applicable, natural-language prompt, source artifact path, and Known Answer Example.
- The British GP question is represented as one Question ID with multiple Actual Answer Components, not as unrelated questions.
- Empty placeholder rows or extension slots exist for at least five additional unknown questions without requiring implementation of their extractors.

#### FR-2: Maintain a controlled Answer Type taxonomy

The system can classify questions using a controlled Answer Type taxonomy that covers the supplied examples and future extension categories.

**Consequences (testable):**
- The taxonomy includes lap time, lap number, finishing position, combined finishing position, tyre compound, pit/change lap, and multi-part answer.
- The taxonomy can record future categories including qualifying rank, grid position, safety car/VSC, penalties, weather, pit-stop count, teammate comparison, points finish, fastest sector/speed trap, and constructor-vs-field ranking.
- Each Answer Type defines required catalog fields and whether extraction is currently supported, derivable, source-blocked, or deferred.

#### FR-3: Separate question capture, analysis mode, prediction, and scoring

The Question Catalog distinguishes the question being asked, the Analysis Mode, Known Answer Example, Prediction Inputs, and Actual Answers.

**Consequences (testable):**
- A Question Catalog row can exist without a Prediction Input.
- A Question Catalog row can be run in `pre_race` or `post_race` mode through a flag, configuration value, or equivalent parameter without duplicating the catalog row.
- A Question Catalog row can exist before an Actual Answer is computed, with status showing pending, computed, `user_manual_option`, `user_manual_approved`, source-blocked, or discrepancy.
- Known Answer Examples are not used as Actual Answers unless Antonio explicitly approves them as `user_manual_approved` source rows.

### 4.2 Results-Based Actual Answer Extraction

**Description:** The system computes finishing-position and combined-position Actual Answers from local F1 result data, with Williams-specific team/driver mapping and clear treatment of abnormal classifications. This realizes UJ-2.

**Functional Requirements:**

#### FR-4: Identify Williams race participants for a target race

The system can identify Williams drivers for a season and grand prix using local constructor/team mapping.

**Consequences (testable):**
- For the Miami and Canadian examples, the extractor identifies the Williams drivers expected for the target race.
- Team naming handles "Williams", "Williams F1 Team", and "Atlassian Williams F1 Team" as catalog aliases that map to the repo's constructor identity.
- Missing or ambiguous constructor mapping stops extraction with a validation status instead of guessing.

#### FR-5: Compute highest Williams finishing position

The system can compute the best Williams finishing position for a target race.

**Consequences (testable):**
- The Canadian GP example returns the highest Williams finishing position and the driver attached to it, or records a source discrepancy against the Known Answer Example.
- DNS, DNF, DSQ, no-classification, and missing-position cases are represented from source classification/status fields before any scoring rule is applied.
- The Actual Answer records source table, source row grain, and source precedence used.

#### FR-6: Compute combined Williams finishing position

The system can compute the sum of both Williams drivers' classified finishing positions for a target race.

**Consequences (testable):**
- The Miami GP example returns a combined finishing position when both Williams drivers have classified finishing positions.
- If either driver lacks a classified numeric position, the extractor returns a validation status and source classification/status details rather than silently summing incomplete data.
- The output records each contributing driver position plus the combined display answer.

### 4.3 Lap-Time Actual Answer Extraction

**Description:** The system computes fastest-lap time and fastest-lap lap-number Actual Answers from lap-level or result-level data where coverage supports it. This realizes UJ-2 and supports lap-time/lap-number scoring.

**Functional Requirements:**

#### FR-7: Validate source coverage for lap facts

The system can determine whether current local data contains the lap-level facts required for a question before attempting extraction.

**Consequences (testable):**
- The coverage check reports whether `raw_jolpica_laps`, `raw_jolpica_results`, Kaggle `results`, or another approved source contains the required season/race/driver rows.
- The coverage check distinguishes fastest-lap time, fastest-lap lap number, and per-lap timing availability.
- Missing lap rows, partial race records, and stale current-season source coverage produce a source-blocked or partial validation status.

#### FR-8: Compute fastest race lap time by scoped driver/team

The system can compute the fastest race lap time for Williams drivers in a target race.

**Consequences (testable):**
- The Melbourne GP example returns Carlos Sainz's fastest Williams lap time when source coverage exists, or records a discrepancy if source-backed extraction differs from `1:23.590`.
- The extractor handles ties, missing lap times, retired drivers, and partial race records explicitly.
- The Actual Answer stores normalized time units, original display text, source timing precision, and whether the value came from official lap timing or a calculated derivative.

#### FR-9: Compute personal fastest race lap number

The system can compute the lap number on which a specified driver set their personal fastest race lap.

**Consequences (testable):**
- The Barcelona GP example returns Carlos Sainz's fastest-lap lap number when source coverage exists, or records a discrepancy if source-backed extraction differs from lap 60.
- The extractor treats "driver's personal fastest lap" separately from "race fastest lap overall."
- The Actual Answer records whether the lap number came from lap-level timing, result-level fastest-lap fields, or a validated calculated derivative.

### 4.4 Tyre, Pit-Event, And Narrative Source Coverage

**Description:** The system determines whether tyre compound, tyre-change lap, and race-incident explanation facts are available from current sources, require supplemental sources, or require Antonio's user-manual decision. This realizes UJ-3.

**Functional Requirements:**

#### FR-10: Produce tyre and pit-event Source Coverage Matrix

The system can evaluate source coverage for starting tyre compound, stint compounds, pit-stop lap, tyre-change lap, incident context, front-wing change, restart context, and retirement lap.

**Consequences (testable):**
- The Source Coverage Matrix records current availability as available, derivable, `user_manual_option`, new-source-required, paid-source-required, or out of scope.
- The matrix distinguishes deterministic facts from narrative explanation facts.
- The matrix identifies whether current `raw_jolpica_pitstops` covers pit-stop lap but not tyre compound. `[ASSUMPTION: Current Jolpica pit-stop data does not include tyre compound; confirm during implementation with source inspection.]`
- No downstream tyre/scoring feature can be marked ready until the coverage status is not unknown.

#### FR-11: Classify the British GP multi-part question

The system can classify and store the British GP Alex Albon question as a multi-part target with separate components for starting tyre compound and first tyre-change lap.

**Consequences (testable):**
- The starting compound component supports controlled values: soft, medium, hard, intermediate, full wet, unknown, not applicable.
- The first tyre-change lap component stores a lap number and an event type where available.
- The Known Answer Example can preserve the narrative explanation that a lap 1 collision and restart changed the tyre/front wing context, but deterministic target components remain separate from narrative text.
- If facts cannot be machine-captured from free sources, the question is marked source-blocked or `user_manual_option`; the system must not present manual entry as the AI's recommended solution.

### 4.5 Backtest Target Store And Scoring Metadata

**Description:** The system stores Actual Answers in a normalized Backtest Target Store with enough metadata to score future Prediction Inputs consistently. This realizes UJ-4.

**Functional Requirements:**

#### FR-12: Store normalized Actual Answer Components

The system can store one or more Actual Answer Components per Question ID.

**Consequences (testable):**
- Single-answer questions have one component; multi-part questions have multiple components with component order and display labels.
- Numeric components store unit, precision, and tolerance metadata.
- Categorical components use controlled values.
- Every component records source table/file, source field or method, extraction timestamp or build ID, validation status, and discrepancy notes when applicable.

#### FR-13: Define scoring rules by Answer Type

The system can assign a Scoring Rule to each Actual Answer Component.

**Consequences (testable):**
- Lap times support configurable absolute-error scoring and display precision.
- Lap-time scoring uses official source lap timing where available; telemetry-derived or interpolated calculations are not scoring-grade unless validated against known lap timing and logical consistency checks.
- Lap numbers and finishing positions support exact-match and absolute-error scoring.
- Combined finishing-position scoring uses source classification/status fields to decide scoreability before applying numeric comparison.
- Tyre compounds support controlled categorical matching.
- Multi-part answers can produce component scores and a combined score.
- Unscoreable targets are reported as unscoreable with reason, not scored as incorrect.

### 4.6 Feature Snapshot Contract For Future Models

**Description:** The system defines what information may be used for future pre-race prediction models without leaking race outcomes. This PRD does not require model training in MVP, but it does require the data boundary that later models must obey.

**Functional Requirements:**

#### FR-14: Define pre-race and post-race data boundaries

The system can document which data is allowed before race start, which data is allowed after the event, and which mode is active for a run.

**Consequences (testable):**
- The Feature Snapshot defines the cutoff timestamp or session boundary for each Question ID.
- Post-race facts including results, fastest laps, pit stops, tyre changes, incidents, and retirements are blocked from pre-race model features.
- The same Question ID can be evaluated in `pre_race` mode for Prediction Inputs and `post_race` mode for Actual Answers without changing its target definition.

#### FR-15: Maintain feature availability status

The system can list candidate feature groups and their current availability.

**Consequences (testable):**
- Feature groups include results form, qualifying form, track history, driver history, constructor performance, pit/tyre tendencies, weather/session conditions, and source freshness.
- Each feature group is tagged already available, derivable from current tables, requires new source, user-supplied, or out of scope.
- The contract is usable by later architecture and story work without specifying a final model algorithm.

#### FR-16: Generate or reconstruct baseline Prediction Inputs

The system can create baseline Prediction Inputs for cataloged questions before forecast-model work exists.

**Consequences (testable):**
- Generated or reconstructed baselines record method, feature boundary, source inputs, and build timestamp.
- Baseline generation runs only in `pre_race` mode or against a feature snapshot that excludes post-race facts.
- If a baseline cannot be generated without leakage or unsupported assumptions, the Prediction Input is marked unavailable with reason.

### 4.7 Baseline Backtest Report

**Description:** The system produces a compact report that compares Prediction Inputs against Actual Answers and explains source coverage, scoreability, and discrepancies. This realizes UJ-4 and supports portfolio storytelling.

**Functional Requirements:**

#### FR-17: Generate question-level backtest report rows

The system can output a report row per Question ID with prediction, actual answer, score, tolerance, source, and explanation.

**Consequences (testable):**
- The report can include all five supplied examples.
- Each row shows whether the Actual Answer was computed, `user_manual_approved`, source-blocked, or discrepant.
- The report distinguishes "prediction wrong" from "actual answer unscoreable."

#### FR-18: Preserve portfolio-ready explanation text

The system can generate concise explanation text for each scored or unscoreable question.

**Consequences (testable):**
- Explanation text names the relevant driver/team/race and source limitation without requiring the reader to inspect raw tables.
- Narrative context, such as the British GP incident/restart note, should live in notebooks or report narrative when possible and cite the target/source status it explains.
- The report avoids betting/odds framing.

## 5. Cross-Cutting Non-Functional Requirements

- **NFR-1: Reproducibility.** Question catalog, extraction outputs, target store, and reports must be generated from project-controlled files or local data sources, not hand-edited notebook state.
- **NFR-2: Source transparency.** Every Actual Answer Component must cite source artifact, table/file, and extraction method.
- **NFR-3: Data quality.** Missing, ambiguous, partial, stale, or conflicting source data must produce explicit validation statuses.
- **NFR-4: Leakage prevention.** Any generated baseline or future model-facing feature work must honor the Feature Snapshot and block post-race facts for pre-race predictions.
- **NFR-5: Local-first operation.** MVP must remain locally runnable and lightweight, consistent with the project v1 direction.
- **NFR-6: No paid source dependency by default.** Paid data sources require a separate PRD-level decision before becoming required for MVP.
- **NFR-7: Extensibility without overbuilding.** The schema must handle at least five additional unknown questions, but extractors are only required for MVP Answer Types.

## 6. Constraints And Guardrails

- The existing Source precedence rule remains unchanged.
- Current-season results and standings may use the Combined dataset, but raw Jolpica laps and pit stops are not currently part of the Combined dataset.
- Forecast model experiments are post-MVP unless the actual-answer layer and leakage contract are complete.
- Tyre compound data is not assumed available until the Source Coverage Matrix proves it.
- Manual entry is a user decision only. The system may expose `user_manual_option` status after source coverage checks, but the AI must not present manual entry as its solution to missing data.
- No betting, odds, gambling, paid API, heavy infrastructure, hosted application, or production ML platform is in scope for MVP.

## 7. MVP Scope

### 7.1 In Scope

- Structured Question Catalog for the five supplied PDF questions plus extension capacity for five unknown future questions.
- Controlled Answer Type taxonomy and required-field rules.
- Results-based extraction for highest Williams finishing position and combined Williams finishing position.
- Lap-time/lap-number source coverage checks and extraction where current data supports it.
- Tyre/pit/narrative Source Coverage Matrix and British GP answerability assessment.
- Backtest Target Store with component-level metadata and validation status.
- Scoring metadata for supported Answer Types.
- Feature Snapshot contract to prevent data leakage in later model work.
- Generated or reconstructed baseline Prediction Inputs.
- Baseline Backtest Report format for question-level scoring and source status.

### 7.2 Out of Scope for MVP

- Forecast model training, model selection, or ML experiment tracking.
- Weather/session enrichment beyond availability assessment.
- Tyre/stint enrichment unless a viable free source is selected or Antonio explicitly chooses `user_manual_approved` provenance.
- Dashboard or hosted UI.
- Automated email/Gmail ingestion.
- Generalization beyond Formula 1.
- Betting/odds predictions or wagering-oriented analysis.
- Paid APIs or heavy infrastructure.

## 8. Success Metrics

**Primary**

- **SM-1:** Catalog completeness - 5 of 5 supplied PDF questions are represented with valid Question IDs, Answer Types, and Known Answer Examples. Validates FR-1, FR-2, FR-3.
- **SM-2:** Computed-answer readiness - all results-based supplied questions produce Actual Answer Components or explicit validation statuses from source-backed extraction. Validates FR-4, FR-5, FR-6, FR-12.
- **SM-3:** Lap fact coverage clarity - each supplied lap-time/lap-number question is classified as computed, partial, discrepant, or source-blocked with source details. Validates FR-7, FR-8, FR-9.
- **SM-4:** Tyre answerability decision - the British GP question has a documented Source Coverage Matrix outcome before any scorer or model depends on tyre data. Validates FR-10, FR-11.
- **SM-5:** Leakage-safe model foundation - the Feature Snapshot blocks post-race facts from pre-race model features for every Question ID. Validates FR-14, FR-15.
- **SM-6:** Baseline readiness - each supplied question has a generated/reconstructed Prediction Input or an unavailable-with-reason status that proves no leakage-safe baseline exists. Validates FR-16.

**Secondary**

- **SM-7:** Backtest report usefulness - the baseline report can render all five supplied examples with scoreable, `user_manual_approved`, discrepant, or unscoreable status. Validates FR-13, FR-17, FR-18.
- **SM-8:** Extension readiness - the taxonomy and catalog can represent at least five unknown future questions without schema redesign. Validates FR-2, FR-12.

**Counter-metrics (do not optimize)**

- **SM-C1:** Number of forecasts generated - generating more predictions is not success if Actual Answers are not source-backed. Counterbalances SM-6.
- **SM-C2:** Number of new data sources added - adding sources is not success if it increases maintenance burden or violates the lightweight local-first constraint. Counterbalances SM-4.
- **SM-C3:** User-manual answer coverage - `user_manual_approved` entries should not be optimized upward and must not be presented as AI-computed success. Counterbalances SM-2 and SM-3.

## 9. Data Governance And Source Decisions

- The Question Catalog and Backtest Target Store are project-owned analytics artifacts and should be reproducible from files or tables committed to the appropriate project path.
- Prediction Inputs are generated or reconstructed project artifacts; they must preserve method, mode, source boundary, and leakage status.
- Generated data under `data/` and `outputs/` remains gitignored unless a later decision changes artifact tracking.
- Source artifacts from the PDF should remain cited by path but not duplicated in generated outputs beyond short extracts needed for traceability.
- Any new external source for tyre compounds, stint data, weather, incidents, penalties, or safety car/VSC facts needs an explicit source decision recording access model, cost, license/terms risk, authentication, and maintenance burden.
- If Antonio chooses a `user_manual_approved` source, the target row must preserve that provenance and cannot be counted as computed-source success.
- Narrative explanation belongs in notebooks or report narrative when possible; the target store should hold deterministic components and the minimum notes needed to preserve source/status traceability.

## 10. Open Questions

1. Should the first version remain Williams-only, or should the catalog/extractors support any team/driver from the start?
2. Should the source-backed Actual Answer be allowed to override a PDF Known Answer Example automatically when they differ, or should discrepancies require manual review?
3. What portfolio display bands should be used for lap-time score explanations after source-precision and validation rules are applied?
4. What exact user-approval mechanism should promote a `user_manual_option` target to `user_manual_approved`?

## 11. Assumptions Index

- §4.4 FR-10 - `[ASSUMPTION: Current Jolpica pit-stop data does not include tyre compound; confirm during implementation with source inspection.]`
- Global - `[ASSUMPTION: The capability is an internal portfolio analytics extension for Antonio and downstream agents, not a public-facing product.]`
- Global - `[ASSUMPTION: The supplied PDF answers are seed Known Answer Examples, while source-backed extraction remains the authoritative target when available.]`
