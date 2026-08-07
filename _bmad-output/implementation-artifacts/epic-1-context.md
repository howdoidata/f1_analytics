# Epic 1 Context: Trustworthy Local F1 Data, Rebuilt

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Rebuild a trustworthy, locally runnable F1 data foundation after repository loss: protect the recovered work on a clean pushable lineage, restore only safe snapshot assets, establish a fresh-clone Python environment, and land complete Kaggle, FastF1, and current-season gap-fill data into DuckDB. The result gives later question-extraction work reproducible source data, explicit completeness and quality evidence, and a repository whose recovery state is honest. It deliberately establishes data foundations, not user-facing analytics.

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

- Preserve the damaged master lineage for forensics. Recovery must use a fresh orphan branch, record the missing tracked paths, remove the loop policy from tracking, and push the clean lineage before rebuilding. Never run `git gc`, `git prune`, `git repack`, or `git restore` as part of recovery.
- Restore the platform snapshot selectively: retain the seven post-pagination-fix Jolpica cache files after byte comparison, restore the V1 code only under `recovery/reference/`, and never restore the July-9 DuckDB file as truth.
- The project must bootstrap from a fresh clone with Python 3.13, uv 0.12.x conventions, an editable `src` package, and documented credentials. Kaggle needs its local token file; FastF1 and Jolpica need none. Pytest must run offline and fail loudly on network access; tests use recorded fixtures only.
- The FastF1 adoption gate must test pandas 3.0 compatibility, session/lap/stint availability for Melbourne, Miami, Canada, Barcelona, and Silverstone, and Kaggle re-download availability. Record all outcomes, including failures and the chosen fallback, in a source decision record before source-dependent implementation proceeds.
- Kaggle supplies the authoritative curated results history. Build its raw and curated race, result, driver, constructor, circuit, qualifying, enriched-result, and standings tables from source CSVs; stale or missing inputs must stop the stage with a named prerequisite failure.
- FastF1 supplies lap timing, tyre/stint, and weather facts. Cache before parsing, verify landed data against session lap/driver counts, map source rows to shared identities at the loader boundary, and treat truncated fetches as explicit failures rather than thinner data. Cache re-runs must make no network requests; 429/5xx handling uses bounded exponential backoff with named rate constants.
- Gap-fill current-season results through FastF1's Ergast-compatible Jolpica access under its request budget. Kaggle wins wherever it has results; Jolpica fills only zero-row rounds. Divergent row counts keep Kaggle data and must be reported as a deviation.
- Every build runs null-rate and referential-integrity checks, records source and load metadata plus one validation row per check, and surfaces failures without failing an otherwise completed build. Missing or ambiguous prerequisites fail early; determinable corrected facts should be recorded.
- Keep the system local, lightweight, and manually invoked with `uv run` scripts. Do not add scheduling, daily pipeline/run records, CI obligations, hosted services, paid sources, or betting-oriented output.

## Technical Decisions

- Store durable tabular state in the single local `data/processed/f1_analytics.duckdb`; source caches and the database are derived and gitignored. Ingestion tables use idempotent replace-sync writes.
- Keep source I/O in `data_sources/`, DuckDB access in `database/`, advisory checks in `validation/`, and thin stage wiring in `scripts/`. The analysis core must not import I/O, database, validation, or script modules; consumers render persisted artifacts rather than recomputing authoritative state.
- Use `raw_*` for source landings, plain curated names for Kaggle tables, and `combined_*` for current-season merged tables. Define the sole Kaggle/Jolpica comparison in the `sql/` coverage view, whose statuses are `match`, `kaggle_only`, `jolpica_only`, `row_count_diverges`, and `no_data`.
- Reuse one cumulative-standings function for every standings table. Implement the sanctioned name-to-ID reconciliation for `final_driver_standings.constructor_id`; do not create parallel derivations.
- FastF1 is adopted only through the spike and source decision record. OpenF1 is retired as an ingestion source; its prior Q05 compound finding is citable corroboration only. Any new source requires a decision record covering access, cost, license/terms, authentication, and maintenance burden.
- Use integer types end-to-end for lap numbers and positions, UTC ISO-8601 timestamps, snake_case Python modules, and no mutable module-level state in `analysis/`.

## Cross-Story Dependencies

- Recovery and offsite protection come first; snapshot salvage must preserve its clean recovery constraints.
- The FastF1 source decision gates FastF1 ingestion. The project foundation gates every executable data stage.
- Kaggle curation precedes FastF1 landing and combined-table construction. Combined tables additionally require the Jolpica raw landings and coverage view.
- Advisory validation runs after curated and combined tables exist and is invoked by each completed build.
