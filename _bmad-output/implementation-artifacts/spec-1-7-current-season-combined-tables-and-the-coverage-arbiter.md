---
title: 'Story 1.7: Current-Season Combined Tables And The Coverage Arbiter'
type: 'feature'
created: '2026-08-08'
baseline_commit: '4a9288cae9334174e30e38cfcc1b0fdc1c455907'
status: 'in-progress'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Current-season race results and standings exist only in Kaggle's curated tables, which can lag or be incomplete for the current season, and nothing today resolves a Kaggle-vs-Jolpica conflict consistently — any consumer touching current-season data must trust a possibly-incomplete table or hand-roll its own source comparison.

**Approach:** Build `kaggle_jolpica_coverage`, a SQL view that is the single arbiter tagging every season/round with the AD-2 status vocabulary (`match | kaggle_only | jolpica_only | row_count_diverges | no_data`), then `combined_results` and combined driver/constructor standings tables that apply that precedence via a new `scripts/build_combined_dataset.py` — Kaggle rows win everywhere except `jolpica_only` rounds.

## Boundaries & Constraints

**Always:**
- Kaggle wins any season/round with ≥1 results row; Jolpica fills only `jolpica_only` (zero-Kaggle-row) rounds (AD-2).
- `row_count_diverges` rounds keep the Kaggle rows; the build's own output names the diverging season/round explicitly — never silently resolved.
- `kaggle_jolpica_coverage` is the only place the Kaggle-vs-Jolpica comparison is computed; `combined_results`/combined standings read its status tags, never recompute.
- Missing curated prerequisite tables (`results`, `races`) fail fast with a named error, mirroring `require_curated_tables()` in `scripts/pull_fastf1_data.py`.
- Jolpica calls are budgeted against the 500 req/hour / 4 req/sec cap (AD-13) and run only inside the isolated pandas-<3 FastF1 environment already established by Story 1.2/1.6 — same subprocess-fetch / main-env-load split as `fastf1_fetch.py` / `fastf1_loader.py`.
- `combined_*` tables write via the existing `write_dataframe` replace-sync helper (AD-4); the view's DDL lives as a `.sql` file under `sql/`.
- Combined standings reuse `standings.compute_cumulative_standings()` — no parallel standings computation.
- Every Jolpica-touching test injects a fake fetch function; the repo-wide network-blocking fixture in `tests/conftest.py` must never be bypassed.

**Ask First:** If FastF1 3.8.3's Ergast-compatible client does not expose current-season results and standings the way AD-6/the source-adoption decision record assumes, HALT and report — do not substitute a direct HTTP client against Jolpica.

**Never:**
- Never call Jolpica outside the isolated FastF1 subprocess environment.
- Never write to `raw_fastf1_laps`/`stints`/`weather` — those are Story 1.6/Epic 2 scope, not this story's.
- Never let `combined_results` silently drop a `row_count_diverges` round instead of naming it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| match | season/round has ≥1 row in both Kaggle results and loaded Jolpica results, counts equal | view tags `match`; `combined_results` uses Kaggle rows, `source='kaggle'` | N/A |
| kaggle_only | round has ≥1 Kaggle row, zero Jolpica rows | view tags `kaggle_only`; `combined_results` uses Kaggle rows | N/A |
| jolpica_only | round has zero Kaggle rows, ≥1 Jolpica rows | view tags `jolpica_only`; `combined_results` filled from Jolpica, `source='jolpica'` | N/A |
| row_count_diverges | both sources have rows but counts differ | view tags `row_count_diverges`; `combined_results` keeps Kaggle rows | build output names the season/round as a documented deviation |
| no_data | neither source has rows for a season/round | view tags `no_data` | round absent from `combined_results` |
| missing curated prerequisite | `results`/`races` curated tables absent from DuckDB | script raises a named error before any write | fail-fast, no partial write |

</frozen-after-approval>

## Code Map

- `src/f1_analytics/data_sources/kaggle_csv.py:48` `build_curated_tables` -- curated `results`/`races`/`drivers`/`constructors` column names that `combined_results` must match
- `src/f1_analytics/data_sources/standings.py:33` `compute_cumulative_standings` -- reuse for combined standings; do not reimplement
- `src/f1_analytics/database/duckdb_io.py` `connect_duckdb`, `write_dataframe` -- no CREATE VIEW helper exists; callers issue raw SQL via `conn.execute()` directly (e.g. `scripts/pull_fastf1_data.py:116`)
- `scripts/pull_fastf1_data.py:106-118` `require_curated_tables` -- fail-fast pattern to mirror for this story's prerequisite check
- `scripts/pull_fastf1_data.py` -- two-phase isolated-subprocess-fetch / main-env-load orchestration and the module-level `SEASON = 2026` constant precedent to mirror
- `src/f1_analytics/data_sources/fastf1_fetch.py` -- isolated-env subprocess pattern (`RETRY_CAP`, `BACKOFF_BASE_SECONDS` module constants, `uv run --isolated --python 3.13 --with fastf1==3.8.3`) to reuse for the new Jolpica fetch module
- `src/f1_analytics/data_sources/fastf1_loader.py:246-290` `load_and_map_race` -- the `round` column precedent (`session.event["RoundNumber"]` via `counts.json`, null-round named error); combined tables join curated/Jolpica data on `(season, round)`
- `sql/curated/README.md` -- confirms `sql/` is the intended home for view DDL; no view files exist yet
- `tests/conftest.py:19` `_block_network_access` -- all Jolpica fetch calls must be dependency-injected in tests, mirroring `pull_fastf1_data.py`'s `fetch: FetchFn | None = None`
- `tests/fixtures/fastf1_csv/` -- fixture-per-scenario directory pattern to mirror under `tests/fixtures/combined/`

## Tasks & Acceptance

**Execution:**
- [x] `src/f1_analytics/data_sources/jolpica_fetch.py` -- NEW: isolated-env-only module (mirrors `fastf1_fetch.py`) using FastF1 3.8.3's Ergast-compatible client to pull current-season race results, rate-limited under AD-13's caps, dumping to CSV under `data/raw/jolpica/<season>/` -- the current-season gap-fill source (driver/constructor standings are derived separately, from `combined_results`, via the existing `standings.compute_cumulative_standings()` -- no separate Jolpica standings fetch, per this story's Boundaries)
- [x] `src/f1_analytics/data_sources/jolpica_loader.py` -- NEW: main-env module reading dumped Jolpica CSVs, mapping to `driver_id`/`constructor_id` via curated `drivers`/`constructors` (named error on unresolved) -- offline-testable, no `fastf1` import
- [x] `sql/kaggle_jolpica_coverage.sql` -- NEW: view DDL computing per-`(season, round)` row counts from curated `results` vs. loaded Jolpica results, tagging AD-2's 5-status vocabulary
- [x] `scripts/build_combined_dataset.py` -- NEW: `require_curated_tables`-style prerequisite check; orchestrates `jolpica_fetch`/`jolpica_loader`; creates the coverage view; builds `combined_results` (Kaggle rows for `match`/`kaggle_only`/`row_count_diverges`, Jolpica rows for `jolpica_only`) and combined standings via `compute_cumulative_standings`; writes via `write_dataframe`; prints named `row_count_diverges` deviations
- [x] `tests/fixtures/combined/` -- NEW: small fixture Kaggle+Jolpica result sets covering the four coverage scenarios
- [x] `tests/test_build_combined_dataset.py` -- NEW: offline tests for coverage-view tagging and combined-table construction against fixtures, plus the missing-prerequisite fail-fast case

**Acceptance Criteria:**
- Given curated Kaggle tables and FastF1's Ergast-compatible Jolpica access budgeted per AD-13, when `uv run scripts/build_combined_dataset.py` runs, then `kaggle_jolpica_coverage` tags every season/round with the AD-2 vocabulary and `combined_results`/combined standings exist with a `source` column, Jolpica rows filling only `jolpica_only` rounds
- Given a `row_count_diverges` round, when the build completes, then `combined_results` keeps the Kaggle rows for that round and the script's output names the round explicitly
- Given curated tables are absent, when the script runs, then it fails fast with a named error before any write

### Review Findings

- [x] [Review][Defer] Combined tables/standings aren't scoped to the current season — `combined_results` and both `combined_*_standings_by_round` tables are rebuilt from an unfiltered `SELECT * FROM results`/`races` on every run, with no season filter anywhere in `scripts/build_combined_dataset.py` or `sql/kaggle_jolpica_coverage.sql`. Verified against the live DB: `combined_results` holds 26,115 rows spanning seasons 1950–2026, of which 25,939 (99.3%) are Kaggle's full all-time history rewritten via full replace-sync every build; only 176 rows are the genuine 2026 `jolpica_only` gap-fill. Deferred per user decision 2026-08-08: pending validation of whether FastF1's Jolpica/Ergast client can itself serve full historical (pre-2026) results/standings data — a potential path to FastF1 fully replacing Kaggle as the historical source, which would reframe this current-vs-full-history scoping question entirely rather than being resolved by a narrow patch now.
- [x] [Review][Patch] `run_fetch_subprocess` only catches `TimeoutExpired`/`OSError` from `subprocess.run` [scripts/build_combined_dataset.py:140-150] — any other exception (e.g. `UnicodeDecodeError` from non-UTF8 subprocess output, since the call uses `text=True`) propagates uncaught through `main()`'s unguarded `fetch(season, season_dir)` call, aborting the whole build instead of degrading gracefully as the module's own docstring promises.
- [x] [Review][Patch] A legitimate zero-round/empty season gets misreported as `status: "failed"` instead of `"empty"` [src/f1_analytics/data_sources/jolpica_fetch.py:193] — `total_expected = int(pages[0].total_results) if pages else None` guards on `pages` being non-empty (always true), not on `total_results is not None` (the documented empty-season signal); when it's `None`, `int(None)` raises `TypeError`, which the enclosing `except Exception` in `fetch_season_results` catches and reports as `"failed"` with a confusing TypeError message rather than reaching the intended `"empty"` branch below it.
- [x] [Review][Patch] `fastf1.Cache.enable_cache()` [src/f1_analytics/data_sources/jolpica_fetch.py:250] and the output-write block (`output_dir.mkdir`/`combined.to_csv`/`counts.json` write) [src/f1_analytics/data_sources/jolpica_fetch.py:283-288] aren't wrapped in try/except like their sibling calls in the same function, breaking `fetch_season_results`'s own "never raises for live-service failures" docstring contract at the unit level. Mitigated at the system level by `build_combined_dataset.py`'s subprocess stdout-fallback (an uncaught subprocess crash still degrades to a statused failure one level up), so it doesn't currently abort a live build, but the function's own promise and unit-testability are broken.
- [x] [Review][Patch] `verify_completeness()` silently no-ops (never raises) when `counts.json` is missing the `row_count` key [src/f1_analytics/data_sources/jolpica_loader.py:121-131] — `if expected_row_count is not None and ...` short-circuits to `False`, contradicting its own docstring ("never accepted as close enough"). Currently unreachable via the real write path since `jolpica_fetch.py` always includes `row_count` when it writes `counts.json`, but a latent contract gap if the sidecar format ever changes or a dump is hand-edited.
- [x] [Review][Patch] `build_combined_standings()` assumes `races` has `date`/`time`/`circuit_id`/`url` columns with no schema validation [scripts/build_combined_dataset.py:252] — `require_curated_tables()` only checks table names exist, not columns, so an incomplete `races` table raises a raw `KeyError` instead of the story's own "fail fast with a named error before any write" contract. Worse, this happens after `raw_jolpica_results` and `combined_results` have already been written to the DB in the same `main()` run — a partial-write-then-crash rather than a clean pre-write failure.
- [x] [Review][Patch] `jolpica_fetch.py`'s `main()` returns exit code 1 for the legitimate `"empty"` status, identical to `"failed"` [src/f1_analytics/data_sources/jolpica_fetch.py:306] — currently harmless since the only caller (`run_fetch_subprocess`) parses stdout JSON rather than checking the exit code, but misleading for direct/manual CLI use. No test exercises `main()`/`parse_args()` at all, so nothing would catch this.
- [x] [Review][Patch] `load_jolpica_results()` prints the same failure-toned "did not land season {season} data" message for both the legitimate `"empty"` status and a genuine `"failed"` status [scripts/build_combined_dataset.py:183] — a normal not-yet-started season is indistinguishable from a real crash in the build's own log output.
- [x] [Review][Patch] `kaggle_jolpica_coverage.sql`'s defensive "row reported by a source but absent from `races`" backstop UNION branch [sql/kaggle_jolpica_coverage.sql:34-42] has zero test coverage — the scenario it's explicitly written to guard against is never exercised.
- [x] [Review][Patch] The Tasks & Acceptance checklist entry for `jolpica_fetch.py` (above) claims it fetches "driver/constructor standings" in addition to race results; the actual (spec-compliant) implementation only fetches race results — standings are derived separately via `standings.compute_cumulative_standings()`, matching the frozen Boundary. Doc-only inaccuracy, not a functional defect.
- [x] [Review][Defer] Jolpica's 500 req/hour budget is tracked in-memory per script invocation, not against the real wall-clock hour [src/f1_analytics/data_sources/jolpica_fetch.py `HOURLY_REQUEST_CAP`/`request_count`] — deferred, pre-existing. Repeated manual runs within the same real hour aren't jointly budgeted against Jolpica's actual hourly cap, only each individual run's own request count.

## Spec Change Log

## Design Notes

Mirror Story 1.6's two-phase split exactly: `jolpica_fetch.py` runs only inside the isolated FastF1 subprocess environment and never touches DuckDB; `jolpica_loader.py` and the DuckDB writes run in the main environment and are fully offline-testable. The coverage view is pure SQL over already-landed tables (`results` plus the newly-loaded Jolpica results table) — it never calls either source live, so it can be recreated cheaply whenever either table changes.

## Verification

**Commands:**
- `uv run pytest -v` -- expected: full suite green, offline, no network calls
- `uv run scripts/build_combined_dataset.py` -- expected (manual, live): coverage view built, combined tables populated, any `row_count_diverges` rounds printed by name

## Suggested Review Order

**Coverage arbiter (the AD-2 precedence engine)**

- The single place the Kaggle-vs-Jolpica row-count comparison happens -- everything downstream just reads its tag.
  [`kaggle_jolpica_coverage.sql:50`](../../sql/kaggle_jolpica_coverage.sql#L50)

- Reads the view's tags to split rows by source; deliberately never recomputes the comparison itself.
  [`build_combined_dataset.py:199`](../../scripts/build_combined_dataset.py#L199)

- Names every `row_count_diverges` round explicitly instead of resolving it silently (a frozen "Never").
  [`build_combined_dataset.py:256`](../../scripts/build_combined_dataset.py#L256)

**Live Jolpica ingestion (rate discipline & pagination)**

- Initial page call sits outside the pagination loop's `except ValueError`, so a real fetch failure can't be mistaken for "season has zero rounds."
  [`jolpica_fetch.py:163`](../../src/f1_analytics/data_sources/jolpica_fetch.py#L163)

- Continuation loop treats `ValueError` from `get_next_result_page()` as the library's own end-of-pages signal.
  [`jolpica_fetch.py:188`](../../src/f1_analytics/data_sources/jolpica_fetch.py#L188)

- Hourly request budget now counts every retry attempt, not just one per page turn (post-review fix).
  [`jolpica_fetch.py:147`](../../src/f1_analytics/data_sources/jolpica_fetch.py#L147)

- Isolated-subprocess handoff to the FastF1/Ergast environment, hardened against `OSError` and non-dict JSON on stdout.
  [`build_combined_dataset.py:84`](../../scripts/build_combined_dataset.py#L84)

**Id-mapping & schema shaping**

- Null `season`/`round` now raises by name instead of the row silently vanishing in a later merge (post-review fix).
  [`jolpica_loader.py:195`](../../src/f1_analytics/data_sources/jolpica_loader.py#L195)

- Numeric columns cast to nullable `Int64` so `position` stays an integer regardless of which source supplied a round (post-review fix).
  [`jolpica_loader.py:206`](../../src/f1_analytics/data_sources/jolpica_loader.py#L206)

- Named error on any driver/constructor id Jolpica reports that curated tables don't recognize (AD-14).
  [`jolpica_loader.py:226`](../../src/f1_analytics/data_sources/jolpica_loader.py#L226)

**Fail-fast prerequisites**

- A missing-entirely or incomplete DuckDB file both fail with one clean, named error (post-review fix unified the two paths).
  [`build_combined_dataset.py:271`](../../scripts/build_combined_dataset.py#L271)

**Tests**

- All five AD-2 statuses and the missing-prerequisite case, against a fixture season built for exactly this purpose.
  [`test_build_combined_dataset.py`](../../tests/test_build_combined_dataset.py)

- Pagination, hourly-budget, and retry/`ValueError` edge cases for the live Jolpica fetch path.
  [`test_jolpica_fetch.py`](../../tests/test_jolpica_fetch.py)

- Id-mapping, schema-shaping, and completeness edge cases for the main-env loader.
  [`test_jolpica_loader.py`](../../tests/test_jolpica_loader.py)
