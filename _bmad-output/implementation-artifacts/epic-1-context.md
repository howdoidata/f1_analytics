# Epic 1 Context: Trustworthy Local F1 Data, Rebuilt

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This is a post-data-loss rebuild epic: Antonio needs to be able to reconstruct the complete local F1 dataset from a fresh clone using one documented command per stage — Kaggle curated tables, FastF1 lap/stint/weather facts, and a gap-filled current season — with completeness verified against each source's own totals, rate limits respected and budgeted, data-quality checks logged (never blocking), and the repository itself made honest again after the 2026-08-01 loss. It opens with recovery operations (getting the rebuild onto a pushable, offsite-protected lineage and salvaging what the old platform snapshot still offers) and a gated FastF1 adoption spike, before any data layer is built — no prior epic or story is treated as done; surviving artifacts inform the rebuild, they don't bind it. Epic 1 covers no FRs directly but is the enabling prerequisite for the source-backed extraction FRs (FR-4..FR-11) in Epic 2.

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

- Reproducibility: every catalog/table/report output must be generated from project-controlled files or local data via a documented `uv run` command from a fresh clone plus documented per-source credentials — never hand-edited state. Kaggle needs a local token file; FastF1 and Jolpica need no credential.
- Local-first, no paid sources by default: no server/hosted database, no paid API without a separate decision record.
- Ingestion completeness and rate discipline bind every loader: pagination must be exhausted and verified against the source's own published total; a truncated fetch is a named statused failure, never a silently shorter table; every client encodes its source's rate limits as named constants; 429/5xx responses get bounded exponential backoff with a retry cap, never a hot retry loop or silent skip; cache-then-parse so re-runs never re-hit the network.
- Tests must never touch the network — loaders are tested against recorded fixtures cut from cached payloads; live-API verification happens only in explicitly named spike scripts.
- Data-quality validation is advisory only: checks are logged, a failing check surfaces in output, but the build still completes.
- Standing recovery constraints (binding until lifted): never run `git gc`/`prune`/`repack` in this repo; never blanket `git restore .`; the platform snapshot's data predates a pagination fix, so any live/current cache file wins over a snapshot-restored version, and its July-9 DuckDB is disposable scaffolding, never treated as truth.

## Technical Decisions

- Single local DuckDB store (`data/processed/f1_analytics.duckdb`) is the only durable tabular state; ingestion tables (`raw_*`, curated, `combined_*`) are derived/rebuildable and written via idempotent `CREATE OR REPLACE` sync; metadata tables (`build_registry`, `source_registry`, `source_load_log`, `validation_results`) are append-per-build logs. The storage edge (`database/`) is the only module that opens DuckDB connections and owns all DDL.
- Source roles are fixed and exclusive: Kaggle is authoritative for curated historical results; FastF1 supplies lap timing, tyre/stint, and weather facts plus Ergast-compatible Jolpica access for current-season gap-fill. Any source binds only after its own gate (FastF1's gate: the pandas-3 compatibility spike plus a decision record); no new source without one.
- Kaggle-vs-Jolpica precedence has a single arbiter: a `kaggle_jolpica_coverage` view tags every season/round (`match | kaggle_only | jolpica_only | row_count_diverges | no_data`); Kaggle wins any round with ≥1 results row, Jolpica fills only zero-row rounds, and a `row_count_diverges` round keeps Kaggle rows and must be named as a documented deviation — never silently resolved. This precedence does not apply to lap/stint/weather facts, which have no Kaggle counterpart.
- One entity id space: every loader maps its rows onto the Ergast/Jolpica-style `driver_id`/`constructor_id` space at the loader boundary; FastF1 rows are mapped by name-derived id, never by car number. There are now **two** sanctioned name→id reconciliations under this rule (adding a third would need its own decision record): (1) `final_driver_standings.constructor_id`, built in Story 1.5; (2) a small static alias table in `fastf1_loader.py` (Story 1.6) mapping FastF1's `Team` string to `constructor_id` for exactly the 4 of 11 2026 teams whose FastF1 name doesn't exact-match Kaggle's `constructors.name` — `Alpine`, `Cadillac`, `Racing Bulls`, `Red Bull Racing`. Resolution order: exact match against `constructors.name` → alias-table lookup → `UnmappedFastF1NameError` naming the unresolved string (never a fuzzy match, never a guess). Scoped exclusively to `fastf1_loader.py`; does not touch driver mapping (FastF1's 3-letter codes already match `drivers.code` exactly) or `constructors.name` itself.
- Fail-early binds every story: each unit verifies its preconditions before doing work; a failed precondition halts that unit with an explicit named finding (shells fail fast on missing prerequisites; the storage edge does typed rejection).
- Decision record (Story 1.2, FastF1 adoption): adopt FastF1 3.8.3 in an explicitly **separate** environment pinned to `pandas<3.0` for lap/stint/weather/Jolpica ingestion — this is a source-environment boundary only, not a change to the project's own pandas-3.0.x baseline. Do not claim pandas-3 compatibility for FastF1. Kaggle's dataset re-download failed (`400 Bad Request`, root cause undetermined) and needs direct operator investigation in the Kaggle console before future Kaggle ingestion relies on that credential.
- Build validation (`validation/`) reads only via `database/`, is imported only by `scripts/`, never by `analysis/`, and logs null-rate and referential-integrity checks per build without ever halting it.
- Structural seed relevant to this epic: `src/f1_analytics/{data_sources,database,validation}/`, `scripts/`, `sql/` (views), `data/raw/` (gitignored source caches incl. `fastf1_cache/`), `data/processed/` (gitignored DuckDB).

## Cross-Story Dependencies

- Story 1.1 (offsite push) is the first action in the epic and unblocks everything after it.
- Story 1.2 (FastF1 spike + decision record) gates Story 1.6 — no FastF1 ingestion code depends on FastF1 until the spike's decision record exists.
- Story 1.3 (snapshot salvage) supplies the restored/re-downloaded Kaggle CSVs that Story 1.5 consumes.
- Story 1.4 (project foundation) must exist before Stories 1.5–1.8 can build or test against it.
- Story 1.5 (Kaggle curated layer) is a direct prerequisite for Story 1.6 ("Given the spike's decision record (1.2) and the 1.5 curated layer") and for Story 1.7's combined dataset build.
- Story 1.7 (combined tables + coverage arbiter) depends on Story 1.5's curated tables and budgeted Jolpica access.
- Story 1.8 (advisory validation) runs against the curated and combined tables produced by Stories 1.5 and 1.7.
- Outside this epic: Epic 2's extraction stories (results-based, lap-based, and British GP multi-part) depend on this epic's curated Kaggle tables (1.5) and FastF1 tables (1.6) as their source layer.
