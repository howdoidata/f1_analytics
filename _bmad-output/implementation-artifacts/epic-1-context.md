# Epic 1 Context: Trustworthy Local F1 Data, Rebuilt

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Re-establish a trustworthy, reproducible local F1 data foundation before question extraction begins. The epic protects the recovered repository, proves FastF1 is viable for the required 2026 lap, stint, and weather facts, rebuilds curated and current-season data with explicit source precedence, and records advisory quality evidence so later answer components can be trusted rather than inferred from incomplete or stale data.

## Stories

- Story 1.1: Record The Loss And Gain Offsite Protection
- Story 1.2: FastF1 Adoption Spike
- Story 1.3: Salvage The Platform Snapshot Under The Merge Rules
- Story 1.4: Project Foundation That Survives A Fresh Clone
- Story 1.5: Kaggle Curated Layer, Rebuilt
- Story 1.6: FastF1 Facts Landed With Rate Discipline
- Story 1.7: Current-Season Combined Tables And The Coverage Arbiter
- Story 1.8: Advisory Build Validation, Logged

## Requirements & Constraints

- The foundation must run locally from a fresh clone through documented `uv run` commands. It uses Python 3.13, pandas 3.0.x, FastF1 3.8.x, DuckDB 1.5.x, and an offline pytest suite. Kaggle credentials must be documented; FastF1 and Jolpica require none.
- Before FastF1 becomes a dependency, perform and record a three-part adoption spike: pandas-3 compatibility (including any failing surface), session/lap/stint availability for Melbourne, Miami, Canada, Barcelona, and Silverstone, and Kaggle dataset re-download availability. The source decision record must cover access model, cost, license/terms risk, authentication, and maintenance burden. A failing leg succeeds only when its explicit fallback is recorded.
- Ingestion must cache raw source payloads before parsing. Every loader exhausts pagination, checks published source totals where available, and treats truncation, missing prerequisites, or exhausted retries as named, statused failures—not partial success. Tests use recorded fixtures and never access a network.
- FastF1's managed cache is mandatory at `data/raw/fastf1_cache/`; an immediate second run must not make fresh requests. Use named rate-limit constants, plan Jolpica runs below its 4 requests/second and 500 requests/hour ceilings, use bounded exponential backoff for 429/5xx responses, and avoid hot retries.
- Rebuild Kaggle CSVs into raw and curated DuckDB tables, including results, entities, circuits, qualifying, enriched results, and standings. A missing or stale source file must fail before a thinner table is produced. Reuse a single cumulative-standings computation and use the sole allowed name-to-id reconciliation for `final_driver_standings.constructor_id`.
- Current-season combined data must apply one coverage arbiter: Kaggle wins where it has results, Jolpica fills only absent rounds, and overlapping count divergence retains Kaggle while surfacing the deviation. The coverage comparison lives in one SQL view.
- Run advisory null-rate and referential-integrity validation at build completion. Persist a row per check in `validation_results`, plus source inventory/load metadata; report failed checks without failing an otherwise completed build. Validation may read only through the database layer.
- Preserve recovery safety: never run `git gc`, `git prune`, `git repack`, or blanket `git restore .`. Snapshot code and documents are salvage only; its pre-pagination-fix data cannot overwrite the seven surviving live Jolpica cache files, and its July-9 DuckDB file is never restored as truth.
- Every unit validates preconditions before work. Source/content ambiguity, missing data, partial data, and conflicts must be explicit findings; code must not silently substitute or guess.

## Technical Decisions

- Use a local DuckDB store with table classes `raw_*`, curated bare tables, `combined_*`, future `question_*` tables, and append-only metadata logs. Views live under `sql/`; generated artifacts live under `outputs/`; raw cache and the derived database are gitignored.
- Source roles are fixed: Kaggle is authoritative for curated results; FastF1 supplies lap timing, stints, weather, and Ergast-compatible Jolpica access for current-season gap fill. OpenF1 is retired and its one verified Q05 compound fact remains citation-only evidence. No new source, including paid data, may be used without a five-field decision record.
- Map all external records at loader boundaries into the Ergast/Jolpica-style `driver_id` and `constructor_id` space. FastF1 mapping is name-derived, never car-number-derived.
- Keep the package in `src/f1_analytics/`, with `data_sources/`, `database/`, `analysis/`, and `validation/` packages. Scripts are thin entry points; database helpers own storage interactions; validation is imported by scripts rather than analysis.
- Record raw payloads and run offline tests against fixture copies. Live-source verification belongs only in explicitly named spike or ingestion scripts.

## Cross-Story Dependencies

- Story 1.1's offsite-protected clean lineage precedes all recovery work; Story 1.3 selectively restores usable snapshot assets without violating cache safeguards.
- Story 1.2's decision record gates Story 1.6. Story 1.4 establishes the package, invocation, and offline-test conventions consumed by Stories 1.5–1.8.
- Story 1.5's curated layer is a prerequisite for FastF1 loading and combined data. Story 1.6's verified FastF1 facts and Story 1.5's curated tables feed Story 1.7; Stories 1.5 and 1.7 feed Story 1.8 validation.
- Epic 2 relies on the curated/combined results, verified FastF1 lap and stint tables, source coverage outcomes, and validation evidence produced here.
