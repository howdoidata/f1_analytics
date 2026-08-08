# Data Sources

Status: Current.

## Kaggle Formula 1 Complete Dataset

Role:
Baseline Version 1 source.

Dataset:
`patelris/formula-1-complete-dataset-1950-2026`

Local landing path:
`data/raw/f1_complete_dataset/`

DuckDB landing tables:

* `raw_races`
* `raw_results`
* `raw_drivers`
* `raw_constructors`
* `raw_driver_standings`
* `raw_constructor_standings`
* `raw_circuits`
* `raw_qualifying`

Curated DuckDB tables:

* `races`
* `results`
* `drivers`
* `constructors`
* `circuits`
* `qualifying`
* `race_results_enriched`
* `driver_standings_by_round`
* `constructor_standings_by_round`
* `final_driver_standings`
* `final_constructor_standings`

`f1_circuits.csv` and `f1_qualifying.csv` are loaded as both raw and curated tables (2026-07-08 decision, `docs/decisions.md`).

`final_driver_standings` includes a reconciled `constructor_id` column. The raw `f1_driver_standings.csv` file only carries a free-text constructor name, so `constructor_id` is derived by mapping that name against the id/name pairs already present in `results` and `constructor_standings` (2026-07-08 decision, `docs/decisions.md`).

Credential requirement:
KaggleHub uses the local token file documented in `docs/local_setup.md`.

Validation:
Null-rate and referential-integrity checks run on every build and are logged to the `validation_results` table (see Validation Checks below). They do not halt the build; failures are surfaced in the script output and the log table.

## Jolpica/Ergast API

Role:
Fully loaded, separate current-season source. It is landed independently and used only for coverage comparison against Kaggle; it is never merged into or used to overwrite Kaggle curated tables.

Base URL:
`https://api.jolpi.ca/ergast/f1`

Concrete need (2026-07-08):
The Kaggle CSV snapshot is stale for the 2026 season. `f1_races.csv` lists the full 22-round calendar, but `f1_results.csv`/`f1_qualifying.csv` only cover rounds 1-3. Jolpica has real results/qualifying data through round 9 as of this session, so it was loaded to close that gap for comparison purposes.

DuckDB landing tables:

* `raw_jolpica_results`
* `raw_jolpica_qualifying`
* `raw_jolpica_driver_standings`
* `raw_jolpica_constructor_standings`
* `raw_jolpica_laps`
* `raw_jolpica_pitstops`

Loader:
`src/f1_analytics/data_sources/jolpica_loader.py`, run via `scripts/pull_jolpica_data.py`. Raw JSON responses are cached to disk under `data/raw/jolpica/<endpoint>/<season>_<round>.json` (gitignored) before parsing. Requests are paced with a short sleep between calls. The loader discovers the season's rounds from Jolpica's own `races` endpoint and only fetches qualifying/standings/laps/pitstops for rounds that already have results.

Credential requirement:
No credential is required for Jolpica/Ergast.

Current DuckDB status:
Documented in `source_registry` as `loaded`. This item is no longer deferred; `docs/backlog.md` is retained only as a CP-014 classification snapshot and now labels the old Jolpica backlog entry as completed historical context.

## OpenF1

Role:
Wholly separate, additive current-season source, verified live and locally for exactly one fact: Q05's starting tyre compound. It is never merged into Kaggle curated tables, combined tables, or Jolpica's `raw_jolpica_*` tables.

Base URL:
`https://api.openf1.org/v1/`

Concrete need (2026-07-28, Story 7.2):
`openf1-adapter-source-decision-record.md` chose OpenF1 (full 18-endpoint set) over FastF1 for Q05's tyre/pit-event coverage gap. A field-by-field check found only Q05's starting tyre compound was actually blocked; OpenF1's `stints` endpoint answers it, covers 2023+, and needs no new dependency (stdlib `urllib`/`json` only, matching `jolpica.py`'s pattern). Story 7.2 built the client and loader and verified live that Alex Albon's first stint at the 2026 British Grand Prix (`session_key=11326`) has `compound="MEDIUM"`, matching Q05's known answer example.

DuckDB landing tables:
None yet. This is deliberately verification-only for now: no downstream extractor consumes OpenF1 data today (Q05's actual-answer extraction is separate, future work), so no `raw_openf1_*` table was created — building one now would be speculative, unused scaffolding. `load_openf1_stints_for_race()` returns an in-memory DataFrame already shaped like a future `raw_openf1_stints` table (`season`, `round`, `driver_id`, `compound`, `stint_number`, `lap_start`, `lap_end`, `tyre_age_at_start`, `meeting_key`, `session_key`) for whenever a real extractor needs it.

Loader:
`src/f1_analytics/data_sources/openf1_loader.py`, backed by the thin client at `src/f1_analytics/data_sources/openf1.py` (18 endpoints, `sleep_between_requests()` paced at 2.1s to respect the free tier's 3/sec and 30/min limits). `resolve_session_key()` looks up a race's `session_key` via `GET /sessions?year=<season>&country_name=<...>&session_name=Race` (OpenF1 identifies sessions by `session_key`, not season/round; raises if the query is ambiguous rather than picking a match silently). `parse_drivers()` derives each driver's Jolpica-style `driver_id` from that session's `drivers` roster (e.g. "Alexander ALBON" → `"albon"`), which `parse_stints()` then joins against to tag each stint row with `driver_id` — this is how a specific driver's stints are identified, not by `driver_number` lookup. Raw JSON responses are cached to disk under `data/raw/openf1/<endpoint>/<key>.json` (gitignored) before parsing, matching `jolpica_loader.py:fetch_and_cache()`'s cache-then-parse order. No pull script exists yet (`scripts/pull_openf1_data.py` would mirror `pull_jolpica_data.py`, but there is no landing table for it to populate today); the one-time live verification was run directly against `load_openf1_stints_for_race()`.

Credential requirement:
No credential is required for OpenF1 ("No API keys, no credit cards, and no signup required"). License is CC BY-NC-SA 4.0 (non-commercial), matching this project's portfolio/learning framing.

Current DuckDB status:
Not loaded to DuckDB. Verification only, via a live one-time run logged in Story 7.2's Dev Agent Record: `GET /sessions?year=2026&country_name=United+Kingdom&session_name=Race` resolved `session_key=11326`; `GET /drivers?session_key=11326` resolved Alex Albon's `driver_number=23`; `GET /stints?session_key=11326` confirmed Albon's first stint (`stint_number=1`, `lap_start=1`, `lap_end=1`) has `compound="MEDIUM"`, matching Q05's known answer example. Per this confirmation, `question_tyre_pit_coverage.py`'s `_starting_tyre_entry()` now cites OpenF1 (not FastF1) as the candidate/verified source for this fact, and Q05's `extraction_support_status` in `question_catalog.py` reflects the resulting mixed-readiness state (see that module's `AnswerType.MULTI_PART` metadata description).

## Kaggle vs. Jolpica Coverage

A DuckDB view, `kaggle_jolpica_coverage` (defined in `sql/analysis/kaggle_jolpica_coverage.sql`), compares row counts per season/round between Kaggle (`results`, `raw_qualifying`) and Jolpica (`raw_jolpica_results`, `raw_jolpica_qualifying`) tables. Each row is tagged `match`, `kaggle_only`, `jolpica_only`, `row_count_diverges`, or `no_data`. For the 2026 season this view shows rounds 1-3 as `match` and rounds 4-9 as `jolpica_only`, concretely surfacing the gap above. Kaggle remains authoritative for curated tables regardless of what this view shows; the view is for comparison only.

## Combined Kaggle+Jolpica Dataset (Current-Season Analyses)

Role:
A scoped, additive combination of Kaggle and Jolpica data for current-season analyses. Originally built solely to identify the true current-season leader for the championship-leader-conversion analysis (2026-07-09 decision, `docs/decisions.md`); the 2026-07-13 decision widened the scope to all current-season analyses while keeping every precedence clause unchanged. This supersedes only the "never merge" clause of the 2026-07-08 Jolpica decision; Jolpica's loading, caching, and coverage-view mechanics are unchanged.

Precedence rule:
Kaggle wins for any season/round where Kaggle has at least one results row (the `match`, `kaggle_only`, and `row_count_diverges` statuses in `kaggle_jolpica_coverage`). Jolpica fills a season/round only where Kaggle has zero rows (`jolpica_only`). Any `row_count_diverges` season/round keeps its Kaggle rows and must be surfaced as a documented deviation in analysis output, never silently resolved.

DuckDB tables:

* `combined_results` — union of Kaggle `results` (all season/rounds) with Jolpica `raw_jolpica_results` rows for `jolpica_only` season/rounds, tagged with a `source` column (`kaggle` or `jolpica`). Built by `src/f1_analytics/data_sources/combined_dataset.py`, run via `scripts/build_combined_dataset.py`.
* `combined_driver_standings_by_round` and `combined_constructor_standings_by_round` — cumulative points/wins/standing-rank recomputed over `combined_results` using the same cumulative-standings logic as the Kaggle-only curated tables (`compute_cumulative_standings` in `src/f1_analytics/data_sources/standings.py`, shared with `kaggle_csv.py`), not a second parallel implementation.

Scope and non-goals:
These tables may serve any current-season analysis (scope widened by the 2026-07-13 decision; originally leader identification only). Every analysis using them inherits the deviation-surfacing obligation: `row_count_diverges` season/rounds must be reported as documented deviations in that analysis's output. They are additive: `results`, `driver_standings_by_round`, `constructor_standings_by_round`, `final_driver_standings`, and `final_constructor_standings` are unchanged and remain the source of truth for historical (pre-current-season) analysis. Historical seasons in the combined tables are Kaggle-derived only, since Jolpica gap-fill only ever applies where Kaggle has zero rows, which in practice is scoped to the current season. As of 2026-07-13 no existing analysis has been repointed at the combined tables; doing so is separate follow-on implementation work.

Id-convention verification:
Jolpica's `driver_id`/`constructor_id` values were checked at the row level against Kaggle's `drivers.driver_id`/`constructors.constructor_id` for season 2026, rounds 4-9 (the live Jolpica-only gap at the time this was built): all 22 driver ids and all 11 constructor ids matched directly, with no reconciliation mapping needed.

Prerequisites:
`scripts/build_combined_dataset.py` requires the DuckDB file to already contain the Kaggle curated tables, the `raw_jolpica_*` tables, and the `kaggle_jolpica_coverage` view (i.e. `scripts/build_f1_dataset.py` and `scripts/pull_jolpica_data.py` must already have been run). It errors clearly and stops if any are missing.

## Validation Checks

Basic null-rate and referential-integrity checks run against curated Kaggle tables on every build (`src/f1_analytics/validation/checks.py`), covering:

* Null rate on `season`, `round`, `driver_id`, `position`, `points` in `results`; `driver_id` in `drivers`; `constructor_id` in `constructors`; and the reconciled `constructor_id` in `final_driver_standings`.
* Referential integrity of `results.driver_id` against `drivers.driver_id`, `results.constructor_id` against `constructors.constructor_id`, and `races.circuit_id` against `circuits.circuit_id`.

Results are logged to the `validation_results` table, one row per check, per build.

## Source Metadata

The DuckDB build creates:

* `source_registry`: one row per documented source and landing role.
* `source_load_log`: one row per loaded table during the local build.
* `validation_results`: one row per Kaggle validation check, per build.

Kaggle remains authoritative for curated tables. Where Kaggle and Jolpica both have data for the same season/round, Kaggle wins for curated tables; Jolpica is surfaced separately via `kaggle_jolpica_coverage`, not used to mutate Kaggle-derived rows.
