# Epic 1 Context: Trustworthy Local F1 Data, Rebuilt

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

After the 2026-08-01 data loss (206 tracked files permanently unrecoverable locally, 231 broken git history objects), Epic 1 rebuilds the complete local F1 dataset from a fresh clone with one documented command per pipeline stage: git recovery and offsite protection first, a gated FastF1 source-adoption spike second, then the Kaggle curated layer, FastF1 lap/stint/weather facts, current-season gap-fill, and advisory validation. Nothing from before the loss is presumed done — prior modules are salvage to adapt or replace, never fixed contracts. This epic covers no FRs directly, but it is the enabling substrate every extraction FR (FR-4..FR-11) and every later epic reads from; its recovery story is also what unblocks Epic 4's thread-answer work and turns the project's mechanical validation gate green.

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

- No FR is scored directly against this epic, but Epic 1's tables are the only source for the extraction FRs (FR-4..FR-11) that Epic 2 implements — table shape and completeness here determine what Epic 2 can compute.
- Reproducibility: every catalog/ingestion/report output must come from project-controlled files or local data, never hand-edited state.
- Local-first: no server, no hosted service, no scheduler, no daily pipeline, no CI obligation — every stage is a manually invoked `uv run` script.
- No paid source may be adopted without a separate source decision record; any new source (free or paid) needs one before code depends on it.
- Success is measured by: a fresh clone building and testing offline; ingestion completeness verified against each source's own published totals; rate limits respected and budgeted, not merely handled reactively; every build's data-quality checks logged, never silently skipped.

## Technical Decisions

**Rebuild posture:** prior module APIs (lost or surviving) do not bind this rebuild — surviving code is reference material only, lands under `recovery/reference/`, never `src/`. A capability exists only once this rebuild's own tests prove it.

**Foundation (1.4):** `pyproject.toml`, src layout, editable install, uv 0.12.x conventions (0.12.0 changed `uv init` defaults). pytest is the runner; a repo-wide autouse fixture blocks all network access so a socket-touching test fails loudly. Loaders are tested only against recorded fixtures; live calls are confined to named spike scripts. Credentials named per source: Kaggle needs a local token file, FastF1/Jolpica need none.

**Storage (1.5 builds the first writer):** one local DuckDB store at `data/processed/f1_analytics.duckdb`, no second store. Ingestion tables (`raw_*`, curated, `combined_*`) use an idempotent replace-sync write pattern; this story builds only that helper — the append-only writer for target-store tables belongs to Epic 2. `database/` is the only module that opens DuckDB connections.

**Entity identity (binds every loader):** all sources resolve to the Ergast/Jolpica id space (`driver_id`, `constructor_id`) at the loader boundary; FastF1 rows map on entry by name-derived id, never car number. Reconciliations sanctioned during Epic 1: `final_driver_standings.constructor_id` (1.5); a 4-entry FastF1 `Team`→`constructor_id` alias table for names that don't match Kaggle exactly (Alpine, Cadillac, Racing Bulls→`rb`, Red Bull Racing→`red_bull`); a 2-entry FastF1 `Driver`-code override for codes matching more than one curated driver (`VER`→`max_verstappen`, `ALB`→`albon` — codes are reused across eras). Both tables live in `fastf1_loader.py`; anything outside them raises a named error, never a guess or fuzzy-match. A pre-fix version of the driver mapping silently landed real 2026 laps under the wrong historical driver — any already-landed FastF1 tables need re-pulling after the fix, not trusting.

**FastF1 adoption (gates 1.6, resolved by 1.2's spike):** FastF1 3.8.3 is adopted for lap/tyre/stint/weather plus Ergast-compatible Jolpica gap-fill, but it is **not** pandas-3 compatible. Fallback: a separate, explicitly pandas-<3.0 environment for FastF1 only — a source-environment boundary, not a change to the project's pandas-3 baseline elsewhere. Kaggle's dataset re-download currently fails (400 Bad Request, cause undetermined) and needs operator investigation in the Kaggle console; existing curated CSVs remain the working source meanwhile. All five target races load except Barcelona (its FastF1-resolved date fell after the spike ran) — treat that as a statused, future-session failure, not zero data, and re-run once the race occurs.

**Ingestion discipline (binds every loader):** pagination must be exhausted and verified against the source's own published total; a truncated fetch is a statused failure, never a shorter table. Cache-then-parse under `data/raw/<source>/` so re-runs serve from cache. Rate constants live beside each client: Jolpica is 4 req/sec burst / 500 req/hour sustained and states limits will decrease, so budget a whole run against the hourly cap up front; FastF1's cache is mandatory at `data/raw/fastf1_cache/`. 429/5xx responses use bounded exponential backoff with a retry cap, never a hot retry loop.

**Source precedence for gap-fill (1.7):** Kaggle wins any season/round with ≥1 results row; Jolpica fills only zero-row rounds; a `row_count_diverges` round keeps Kaggle rows and must be named as a deviation, never silently resolved. The `kaggle_jolpica_coverage` view (`sql/`) is the single arbiter — every consumer reads its status tags rather than recomputing the comparison.

**Build validation (1.8):** null-rate and referential-integrity checks are advisory and logged — a failing check surfaces in output but the build still completes; nothing halts a build here. `validation/` reads only through `database/`, and is imported by scripts, never by `analysis/`.

**Fail-early discipline (every story):** every unit checks its preconditions before doing work; a failed precondition halts that unit immediately with a named finding — never a thinner or guessed result.

**Standing Constraints (binds the recovery stories, 1.1 and 1.3):** never `git gc`/`prune`/`repack` (231 broken history objects); never a blanket `git restore .`; `/Users/antonio/dev/howdoidata/` is a structure-only skeleton, never a restore source; the platform snapshot tarball predates a pagination fix, so any live cache file wins over it, and its bundled DuckDB file is disposable, never truth.

**Stack pins:** Python 3.13, DuckDB 1.5.x, pandas 3.0.x baseline (FastF1 runs in its own pandas-<3.0 environment), FastF1 3.8.3, pytest 9.x.

## Cross-Story Dependencies

Intended order: 1.1 (offsite push) before 1.3 (salvage) — the Standing Constraints and clean-lineage requirement depend on 1.1 landing. 1.2's spike gates 1.6, which must use the separate pandas-<3.0 FastF1 environment and treat Barcelona as source-blocked. 1.4's skeleton and offline harness must exist before 1.5–1.8 can build or test. 1.5's curated tables (`constructors`, `drivers`) are a prerequisite for 1.6's id reconciliation and for 1.7's combined-table build. 1.7 depends on both 1.5 and the Jolpica access established in the 1.2/1.6 line. 1.8 checks the tables 1.5 and 1.7 produce, so it lands last.

Outside the epic: Epic 2's first-light and results-based extraction stories read Epic 1's curated/combined tables directly; Epic 2's lap-fact and coverage-matrix stories read Epic 1's `raw_fastf1_laps`/`raw_fastf1_stints`. Epic 4's thread-answer stories unblock as soon as Story 1.1's push lands, independent of the rest of this epic.
