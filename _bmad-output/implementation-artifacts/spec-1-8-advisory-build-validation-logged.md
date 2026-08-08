---
title: 'Story 1.8: Advisory Build Validation, Logged'
type: 'feature'
created: '2026-08-08'
baseline_commit: 'af07f0dcd3223d738e4cea621055f021b0bbef8d'
status: 'done'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Build scripts land curated/combined tables, but nothing checks or records data quality — nulls, orphaned foreign keys, or which sources/tables a build loaded — so trust in the rebuilt data is assumed, not recorded.

**Approach:** Add a `validation/` module with pure null-rate and referential-integrity check functions, mirroring salvaged `recovery/reference/.../checks.py`, plus append-only writers for `validation_results`, `source_registry`, `source_load_log`; wire both build scripts to run these on completion and always exit 0.

## Boundaries & Constraints

**Always:**
- Checks are pure functions returning finding-row dicts; no DB access inside check functions. A separate writer persists the returned frame.
- `validation_results`/`source_registry`/`source_load_log` are append-only (`CREATE TABLE IF NOT EXISTS` + `INSERT`) — never `write_dataframe` (AD-4 class-1 replace-sync is for ingestion only).
- `validation/` imports only `database/` plus stdlib/pandas; never imported by, or importing, `analysis/`.
- Both scripts run validations only after their own prerequisite check and writes succeed; a failing check prints to stdout, `main()` still returns 0 (AD-8: advisory-and-logged).

**Never:**
- Never halt a build or change exit code on a failing check.
- Never open a DuckDB connection outside `database/connect_duckdb`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| all checks pass | curated+combined tables, no nulls/orphans | `validation_results` rows all `passed=True` | N/A |
| null violation | a checked column has ≥1 null | row logged `passed=False`, `null_count>0` | printed, build continues |
| referential orphan | child id absent from parent table | row logged `passed=False`, `orphan_count>0` | printed, build continues |

</frozen-after-approval>

## Code Map

- `src/f1_analytics/validation/__init__.py` -- existing stub (1-line docstring, no logic)
- `recovery/reference/src/f1_analytics/validation/checks.py` -- salvaged pattern to mirror: `check_null_rate`/`check_referential_integrity`/`run_kaggle_validations`, `check_id` (uuid4) + `checked_at` (UTC now) envelope; table/column names are stale, do not reuse verbatim
- `src/f1_analytics/database/duckdb_io.py:13-20` `connect_duckdb` -- reuse for the new writer; not `write_dataframe` (wrong write pattern, replace-sync)
- `scripts/pull_fastf1_data.py:186-232` `main`, writes at `:260-265` -- call validations against curated + `raw_fastf1_*` tables after existing writes; track which of `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather` this run actually wrote (each write is conditional on `if <frames_list>:`) for accurate `source_load` logging
- `scripts/build_combined_dataset.py:296-347` `main`, writes at `:329-333` -- call validations against curated + `combined_results` after writes (not the two `*_standings_by_round` tables -- no registry entry checks them; loading them for validation would be dead weight)
- `src/f1_analytics/data_sources/fastf1_loader.py:279-290` -- `raw_fastf1_laps`/`raw_fastf1_stints` columns include `season`, `round`, `driver_id`, `constructor_id`; `raw_fastf1_weather` has only `season`, `round` (no driver_id -- track-level, not per-driver)
- `src/f1_analytics/data_sources/jolpica_loader.py:34-50` `RESULTS_COLUMNS` -- `combined_results` matches curated `results`' column contract exactly (season/round/driver_id/position/points + `source`)
- `sql/kaggle_jolpica_coverage.sql` -- only existing DDL file (a view, no table-DDL precedent); new tables get inline `CREATE TABLE IF NOT EXISTS`, no `sql/` file needed
- `tests/conftest.py:19-27` `_block_network_access` -- autouse, new tests are offline by default
- `tests/fixtures/combined/kaggle/` -- flat curated-shaped CSV convention to mirror for new fixtures

## Tasks & Acceptance

**Execution:**
- [x] `src/f1_analytics/validation/checks.py` -- NEW: `NULL_RATE_CHECKS`/`REFERENTIAL_CHECKS` registries covering curated tables (`results`: season/round/driver_id/position/points; `drivers.driver_id`; `constructors.constructor_id`; `final_driver_standings.constructor_id`; referential: results→drivers, results→constructors, races→circuits) **and** `combined_results` (same columns/referential pairs as curated `results`) **and** `raw_fastf1_laps`/`raw_fastf1_stints` (season/round/driver_id; referential: →drivers, →constructors) **and** `raw_fastf1_weather` (season/round only). `check_null_rate`, `check_referential_integrity`, `run_validations(...)` mirror recovery reference's pure-function/`check_id`/`checked_at` shape. `check_referential_integrity` must guard a missing child/parent column exactly like `check_null_rate` already guards a missing column -- return a failing finding row, never raise (an uncaught `KeyError` here would violate "never halt a build")
- [x] `src/f1_analytics/validation/store.py` -- NEW: `log_validation_results(conn, frame)`, `log_source_load(conn, source, table_name, row_count)` append-only writers (AD-4 class-3), distinct from `write_dataframe`
- [x] `src/f1_analytics/validation/runner.py` -- NEW: `load_present_tables(conn, table_names)` and `print_validation_findings(label, frame)` -- shared helpers so both scripts import one implementation instead of duplicating it
- [x] `scripts/pull_fastf1_data.py` -- MODIFY: after writes, run curated+`raw_fastf1_*` validations via the shared `runner` helpers; log `source_load` rows only for `raw_fastf1_*` tables this run's own writes actually touched (not whatever `SHOW TABLES` currently returns) -- a run where every race fails must not re-log a stale row count from a prior run; print failures, keep `return 0`
- [x] `scripts/build_combined_dataset.py` -- MODIFY: after writes, run curated+`combined_results` validations via the shared `runner` helpers, log `source_load` rows for kaggle+jolpica; print failures, keep `return 0`
- [x] `tests/fixtures/validation/` -- NEW: `null_violation/`, `orphan_referential/` scenario dirs (curated-shaped, mirroring `tests/fixtures/combined/kaggle/`'s CSV shape) plus a `combined_results`-shaped CSV addition so both scripts' integration tests can assert a combined-table violation is logged, not only a curated-table one
- [x] `tests/test_validation_checks.py` -- NEW: offline unit tests per check function against the fixtures, including the new combined/raw-table registry entries and the missing-column guard
- [x] `tests/test_validation_store.py` -- NEW: `log_validation_results`/`log_source_load` append-only behavior across two calls (rows accumulate, never overwrite), `log_source_load`'s `ValueError` for an unregistered source name
- [x] `tests/test_pull_fastf1_data.py`, `tests/test_build_combined_dataset.py` -- MODIFY: seeded-violation test asserting logged failure rows plus `exit_code == 0`; `test_pull_fastf1_data.py` also gets a test reproducing "every race fails after a prior successful run," asserting `source_load_log` gains no stale `fastf1` row

**Acceptance Criteria:**
- Given curated tables, `combined_results`, or `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather` after either build script completes, when validations run, then null-rate and referential-integrity checks each log one row to `validation_results` and the script still exits 0
- Given a build run, when it completes, then `source_registry` and `source_load_log` each gain new rows documenting only the sources and tables this run actually involved

## Spec Change Log

- **Finding (review_loop_iteration 1, 2026-08-08):** all three review layers (blind-hunter, edge-case-hunter, verification-gap) independently confirmed the shipped `NULL_RATE_CHECKS`/`REFERENTIAL_CHECKS` registries named only curated tables, even though both scripts' own Code Map entries and in-code comments said validation ran "against curated + combined tables" / "curated + raw_fastf1_* tables" -- `combined_results` and the three `raw_fastf1_*` tables were loaded into memory for validation and then silently never checked by any registry entry. Root cause: the Tasks & Acceptance execution bullet for `checks.py` enumerated only curated-table entries, under-specifying what the Code Map already promised.
- **Also folded in (same review pass, to avoid a second loopback):** `check_referential_integrity` had no missing-column guard (unlike `check_null_rate`), risking an uncaught `KeyError` that would violate the frozen "never halt a build" boundary; `pull_fastf1_data.py`'s `log_source_load` read table presence via `SHOW TABLES` rather than tracking this run's actual writes, so a run where every race fails would re-log a stale row count from a previous run as a fresh load; `_load_present_tables`/`print_validation_findings` were duplicated verbatim between the two scripts; no dedicated test existed for `validation/store.py`'s append-only guarantee or its `ValueError` path.
- **What was amended:** Code Map and Tasks & Acceptance above now name `combined_results`/`raw_fastf1_*` registry entries explicitly (with real column names, verified against `fastf1_loader.py`/`jolpica_loader.py`), require the missing-column guard, require `pull_fastf1_data.py` to track actually-written tables for `source_load` logging, move the two duplicated helpers into a new `validation/runner.py`, and add `tests/test_validation_store.py`. `combined_driver_standings_by_round`/`combined_constructor_standings_by_round` were deliberately dropped from what `build_combined_dataset.py` loads for validation (rather than adding registry entries for them) -- validating those tables is better scoped to the already-deferred `race_points_mismatch` follow-up story, which targets exactly those `*_standings_by_round` tables.
- **Known-bad state avoided:** a build script that claims (in its own log output and code comments) to validate combined/raw data quality while actually only ever checking curated tables -- silently defeating a chunk of this story's stated purpose (AD-8's "trust recorded, not assumed").
- **KEEP (verified good in the reverted implementation, must survive re-derivation):** `checks.py`'s pure-function shape and envelope exactly as built (`check_null_rate`, `check_referential_integrity`, `run_validations()` returning a DataFrame with `check_id` uuid4 inserted at position 0, `check_type`, `table_name`, `column_name`, `ref_table_name`, `row_count`, `null_count`, `null_rate`, `orphan_count`, `passed`, `checked_at` UTC; a registry entry naming an absent table is skipped, never a `KeyError`). `store.py`'s append-only design verbatim: `CREATE TABLE IF NOT EXISTS` + parameterized `INSERT`, the `_clean()` NaN/Timestamp-normalization helper, the `SOURCE_METADATA` dict (`kaggle`/`jolpica`/`fastf1` -> role/access_model). The `tests/fixtures/validation/{null_violation,orphan_referential}/` flat curated-column CSV convention and the existing curated-only unit tests in `test_validation_checks.py` (still valid -- the amended scope is a superset). The `_seed_curated_tables`-based integration-test pattern already added to both scripts' test files -- extend it, don't replace it.
- **Not carried forward from review (see `deferred-work.md`, "code review of story-1.8"):** a NULL in `results.constructor_id`/`races.circuit_id` is invisible to both check types at once (dropna'd out of the referential check, never in `NULL_RATE_CHECKS`) -- this matches the original epics.md AC and the salvaged recovery reference exactly, so it is a scope decision for a future story, not a defect in this one.
- **Round 2 (2026-08-08, patch, no further loopback):** re-review of the re-derived implementation confirmed all three round-1 fixes landed correctly (verified independently by all three review layers). One new finding rose to patch-worthy: `pull_fastf1_data.py`'s `raw_fastf1_*` validation wiring (`VALIDATION_TABLES` + the registry entries added in round 1) had no integration test proving it fires through `main()` -- only unit-tested via direct `run_validations()` calls, asymmetric with `build_combined_dataset.py`'s covered `combined_results` path, and flagged by the verification-gap reviewer as carrying the same silent-regression risk round 1 exists to catch. Fixed by re-engaging the same implementation agent (context intact) to add `test_main_logs_an_orphan_in_raw_fastf1_laps_reached_through_the_real_mapping_pipeline`, which seeds a real orphan via two sequential `main()` runs through the actual fetch->map->write pipeline (not a synthetic bypass) -- 147 tests pass. Three lower-severity findings from this round were logged to `deferred-work.md` ("code review of story-1.8") rather than triggering a third loopback: the constructor_id null-blind-spot now also covers `combined_results`/`raw_fastf1_laps`/`raw_fastf1_stints`; `raw_jolpica_results` has no registry entry (partially, not fully, covered transitively via `combined_results`); `log_source_load()` inserts a `source_registry` row per call rather than once per source per build, so `pull_fastf1_data.py`'s per-table loop over-logs `source_registry` (not `source_load_log`, which is correctly one row per table).

## Design Notes

`validation_results` envelope (mirrors recovery reference): `check_id` (uuid4), `check_type`, `table_name`, `column_name`, `ref_table_name`, `row_count`, `null_count`, `null_rate`, `orphan_count`, `passed`, `checked_at` (UTC).

`source_registry`/`source_load_log` append fresh rows every build, per AD-4's "per-build metadata... append-per-build log rows" (not deduplicated). `source_registry`: `source_name`, `role`, `access_model`, `recorded_at`. `source_load_log`: `source_name`, `table_name`, `row_count`, `loaded_at`. A row here asserts "this build loaded this table" -- it must reflect this run's own writes, never a table's mere presence from an earlier run.

Two later amendments (`regression_refused` logging, `race_points_mismatch` reconciliation) were split to `deferred-work.md` ("multi-goal split of story-1.8") for token budget — follow-up once this module exists.

## Verification

**Commands:**
- `uv run pytest -v` -- expected: full suite green, offline
- `uv run scripts/build_combined_dataset.py` and `uv run scripts/pull_fastf1_data.py` -- expected (manual, live): print findings, exit 0; `validation_results`/`source_registry`/`source_load_log` populated

## Suggested Review Order

**Validation engine (what gets checked, and why)**

- Entry point: which tables/columns each check type covers, including the round-1 fix extending coverage to `combined_results`/`raw_fastf1_*`.
  [`checks.py:24`](../../src/f1_analytics/validation/checks.py#L24)

- The missing-column guard (round-1 fix) -- degrades to a failing finding instead of an uncaught `KeyError`, preserving "never halt a build".
  [`checks.py:65`](../../src/f1_analytics/validation/checks.py#L65)

- Orchestrates both check types over whatever tables are actually present; a registry entry naming an absent table is skipped, never raised.
  [`checks.py:101`](../../src/f1_analytics/validation/checks.py#L101)

**Append-only logging (AD-4 class 3)**

- `CREATE TABLE IF NOT EXISTS` + parameterized `INSERT`, never `write_dataframe`'s replace-sync -- a build's findings accumulate, never get overwritten.
  [`store.py:59`](../../src/f1_analytics/validation/store.py#L59)

- `source_registry`/`source_load_log` writer; `SOURCE_METADATA` fixes each source's role/access_model once.
  [`store.py:89`](../../src/f1_analytics/validation/store.py#L89)

**Script wiring (where validation actually runs, and what it logs)**

- Shared helpers both scripts import instead of duplicating -- table loading and advisory-findings printing.
  [`runner.py:9`](../../src/f1_analytics/validation/runner.py#L9)

- `write_table_unless_regressed` now returns whether the write landed (round-1 fix) -- `source_load` logging below only fires for tables this run actually touched.
  [`pull_fastf1_data.py:199`](../../scripts/pull_fastf1_data.py#L199)

- `written_tables` tracks this run's actual writes; validation runs against curated + `raw_fastf1_*`; `source_load` logs only what `written_tables` names -- the fix for the stale-row bug a prior run's leftover table would otherwise cause.
  [`pull_fastf1_data.py:256`](../../scripts/pull_fastf1_data.py#L256)

- Same pattern for `build_combined_dataset.py`: validation against curated + `combined_results` (not the two `*_standings_by_round` tables -- deliberately unchecked, see Design Notes); `source_load` logged from this run's own freshly-computed row counts.
  [`build_combined_dataset.py:363`](../../scripts/build_combined_dataset.py#L363)

**Tests (peripherals)**

- Proves the `raw_fastf1_*` wiring fires end-to-end through `main()`, not just via `run_validations()` in isolation (round-2 fix) -- seeds a real orphan across two runs through the actual fetch/map/write pipeline.
  [`test_pull_fastf1_data.py:265`](../../tests/test_pull_fastf1_data.py#L265)

- Reproduces the exact stale-`source_load_log` scenario round 1 found and confirms it no longer happens.
  [`test_pull_fastf1_data.py:354`](../../tests/test_pull_fastf1_data.py#L354)

- Proves `combined_results` validation fires end-to-end in `build_combined_dataset.py`.
  [`test_build_combined_dataset.py:462`](../../tests/test_build_combined_dataset.py#L462)

- Unit coverage for every check function and registry entry, including the missing-column guard.
  [`test_validation_checks.py`](../../tests/test_validation_checks.py)

- Append-only accumulation and the unregistered-source `ValueError` path.
  [`test_validation_store.py`](../../tests/test_validation_store.py)
