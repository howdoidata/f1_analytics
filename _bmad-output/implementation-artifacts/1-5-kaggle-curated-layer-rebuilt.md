---
baseline_commit: 1dcdf795b53f15d2be0ac799fd62c62cd0914af7
---

# Story 1.5: Kaggle Curated Layer, Rebuilt

Status: done

## Story

As Antonio,
I want the historical Kaggle dataset landed and curated into DuckDB,
so that results-based questions have their authoritative source again.

## Acceptance Criteria

1. **Given** the restored Kaggle CSVs already landed at `data/raw/f1_complete_dataset/` (via Story 1.3's salvage restore) and the 1.4 project skeleton, **when** `uv run scripts/build_f1_dataset.py` runs, **then** the 8 `raw_*` tables (`raw_races`, `raw_results`, `raw_drivers`, `raw_constructors`, `raw_driver_standings`, `raw_constructor_standings`, `raw_circuits`, `raw_qualifying`) and the 11 curated tables (`races`, `results`, `drivers`, `constructors`, `circuits`, `qualifying`, `race_results_enriched`, `driver_standings_by_round`, `constructor_standings_by_round`, `final_driver_standings`, `final_constructor_standings`) exist in `data/processed/f1_analytics.duckdb`, written via the storage edge's replace-sync helper — the only DuckDB writer this story creates (AD-4 class 1). The typed append helper for `question_*` target-store tables is explicitly **not** built here (Epic 2's job).
2. **And** cumulative per-round standings (`driver_standings_by_round`, `constructor_standings_by_round`) are computed by one shared function reused by both tables — no parallel/duplicated implementation (Consistency Conventions: "shared derived logic is computed by one function, never re-implemented per table (e.g. cumulative standings)").
3. **And** `final_driver_standings.constructor_id` is populated via the one sanctioned name→id reconciliation permitted without a new decision record (AD-14) — mapping the free-text `constructor` name column in `f1_driver_standings.csv` against the id/name pairs already present in `results` and `constructor_standings`.
4. **And** a stale-or-missing raw CSV fails the build immediately with a named error identifying exactly which file(s) are missing — never a silently thinner table (AD-16 fail-early; shell fail-fast convention).

**Verification:** offline tests against fixture CSVs (never the real dataset, never the network) verify each curated table's shape and the `constructor_id` reconciliation; a dedicated test removes a fixture CSV and asserts the loader/script fails with a named, specific error. Governed by: AD-1, AD-4, AD-11, AD-14, AD-16.

## Tasks / Subtasks

- [x] Task 1: Add pinned runtime dependencies; reconcile the orphaned `requirements.txt` (AC: 1)
  - [x] Add `pandas>=3.0,<3.1`, `duckdb>=1.5,<1.6`, and `kagglehub>=1.0,<2` to `pyproject.toml`'s `[project] dependencies` (currently `[]`) — versions match the Stack table's verified pins (pandas 3.0.5, DuckDB 1.5.5). `kagglehub` is added now solely to fulfill the commitment Story 1.4's Dev Notes/deferred-review recorded for this story (making `requirements.txt` reconcilable) — no code in this story calls it, since the CSVs are already landed via Story 1.3's salvage and a live re-download is explicitly out of scope (see Dev Notes → "Scope and sequencing"). Note the FastF1 spike verified `kagglehub==1.0.2` alongside `pandas 2.3.3` in an isolated environment, not alongside this story's `pandas>=3.0` — treat that as a loose version anchor, not proof of pandas-3 compatibility; if `uv lock` surfaces a resolver conflict, resolve it then rather than assuming none exists.
  - [x] Run `uv lock` then `uv sync`; confirm `uv.lock` updates and resolves cleanly. **Result:** resolved 23 packages, no conflict — pandas locked to 3.0.5, duckdb to 1.5.5, kagglehub to 1.0.2 (exactly the Stack table's verified pins / the FastF1 spike's verified kagglehub version).
  - [x] Delete `requirements.txt` at the repo root — it is now redundant/contradictory now that `pyproject.toml` declares real pinned deps (per the deferred finding in `_bmad-output/implementation-artifacts/deferred-work.md` and Story 1.4 Review Findings).
  - [x] Verify: `uv run python -c "import pandas, duckdb, kagglehub; print('OK')"` prints `OK`. Confirmed. Full regression suite also re-run: `2 passed in 0.02s`, no regressions.

- [x] Task 2: Build fixture CSVs and the shared config module (AC: 1, 2, 3, 4 — shared prerequisite for every later task)
  - [x] Create `tests/fixtures/kaggle_csv/` with 8 small synthetic CSVs — `f1_races.csv`, `f1_results.csv`, `f1_drivers.csv`, `f1_constructors.csv`, `f1_driver_standings.csv`, `f1_constructor_standings.csv`, `f1_circuits.csv`, `f1_qualifying.csv` — matching the exact header rows verified against the real files on disk today (see Dev Notes → "Verified CSV headers"). Covers 2 seasons (2024, 2025), 2 rounds per season (Bahrain, Saudi Arabia), 3 drivers (verstappen, hamilton, alonso) with different points/positions across rounds, and alonso changes `constructor` free text between seasons (`Aston Martin` in 2024 → `Alpine` in 2025, with matching `constructor_id` change in `results`/`qualifying`) — exercises the reconciliation non-trivially.
  - [x] Create `src/f1_analytics/config.py` (did not exist under live `src/` yet — only under `recovery/reference/`) with path/name constants: `PROJECT_ROOT`, `DATA_DIR`, `RAW_DATA_DIR`, `KAGGLE_F1_RAW_DIR`, `PROCESSED_DATA_DIR`, `DUCKDB_PATH`, `KAGGLE_SOURCE_NAME`, `KAGGLE_DATASET_HANDLE`. Adapted from `recovery/reference/src/f1_analytics/config.py`, dropping the unused Jolpica/outputs constants (nothing in this story's scope needs them — avoids unused speculative constants). Verified `PROJECT_ROOT = Path(__file__).resolve().parents[2]` resolves to the repo root from `src/f1_analytics/config.py`'s actual depth.
  - [x] Test: `tests/test_kaggle_csv_fixtures.py` — `pandas.read_csv`s all 8 fixture files, asserts each has exactly the expected column set, and asserts the constructor-name-change property holds. **Result:** `9 passed in 1.01s`.

- [x] Task 3: Build the storage edge's replace-sync writer (AC: 1)
  - [x] Write a failing test first: `tests/test_duckdb_io.py` calls `write_dataframe(conn, table_name, frame)` twice against the same table name with two differently-shaped DataFrames, using a `tmp_path` DuckDB file via `connect_duckdb(db_path)`; asserts the table after the second call reflects only the second DataFrame's rows/columns. **Confirmed red first**: `ModuleNotFoundError: No module named 'f1_analytics.database.duckdb_io'`.
  - [x] Implement `src/f1_analytics/database/duckdb_io.py` with `connect_duckdb(db_path, *, read_only=False)` and `write_dataframe(conn, table_name, frame)` (register the frame, `CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM source_df`, unregister). No `source_registry`/`source_load_log`/`validation_results`/metadata-logging helpers added — Story 1.8's scope.
  - [x] `database/` is the only module in the package that opens a DuckDB connection (spine's Storage-edge role) — confirmed: no `duckdb.connect()` call anywhere outside this file.
  - [x] Run the Task-3 test to green. **Result:** `2 passed in 1.86s`.

- [x] Task 4: Build the shared cumulative-standings function (AC: 2)
  - [x] Write a failing test first: `tests/test_standings.py` builds an in-memory DataFrame shaped like `race_results_enriched` (2024 rounds 1-2 with drivers `a`/`b` swapping positions so they end round 2 tied on cumulative points/wins; 2025 round 1 proving per-season reset) and calls `compute_cumulative_standings(results, id_column, name_column)`; asserts per-round cumulative sums, the season reset, and that the tied round-2 rows share `standing_rank == 1`. Dry-ran the exact reference algorithm against this fixture by hand first to confirm the expected numbers (43/43, rank 1/1) before writing assertions. **Confirmed red first**: `ModuleNotFoundError: No module named 'f1_analytics.data_sources.standings'`.
  - [x] Implement `src/f1_analytics/data_sources/standings.py` with `compute_cumulative_standings()` and `add_standing_rank()`, adapted from `recovery/reference/src/f1_analytics/data_sources/standings.py` — grouping/columns verified against the fixture shape, unchanged from the reference.
  - [x] Run the Task-4 test to green. **Result:** `3 passed in 0.79s`.

- [x] Task 5: Build Kaggle CSV loading and curated-table construction, with fail-fast on missing CSVs (AC: 1, 2, 3, 4)
  - [x] Write a failing test first: `tests/test_kaggle_csv.py` copies the Task-2 fixture directory to a `tmp_path`, deletes `f1_circuits.csv`, and calls `require_raw_files(raw_dir)`; asserts it raises `FileNotFoundError` whose message names `f1_circuits.csv` specifically. **Confirmed red first**: `ModuleNotFoundError: No module named 'f1_analytics.data_sources.kaggle_csv'`.
  - [x] Implement `src/f1_analytics/data_sources/kaggle_csv.py`: `RAW_FILES`, `discover_raw_files()`, `require_raw_files()`, `read_raw_csvs()`, `coerce_numeric()`, `build_curated_tables(raw)` — builds all 11 curated tables, calls `standings.compute_cumulative_standings()` once for drivers and once for constructors, reconciles `final_driver_standings.constructor_id` via the free-text `constructor` → id lookup built from `results`/`constructor_standings`. Adapted from `recovery/reference/src/f1_analytics/data_sources/kaggle_csv.py`; no import of `validation/checks.py` and no `source_registry`/`source_load_log` calls (Story 1.8's scope) — confirmed by grep, none present.
  - [x] Write a failing test first, then make it pass: `test_build_curated_tables_produces_all_expected_tables_and_columns` and `test_constructor_id_reconciliation_resolves_every_row_including_a_constructor_change` — the latter explicitly asserts alonso resolves to `aston_martin` in 2024 and `alpine` in 2025 (the fixture's constructor-change row), plus that `constructor_id` is non-null for every row.
  - [x] Note: a `constructor` name in `f1_driver_standings.csv` with no match in `results`/`constructor_standings` resolves to `NaN` today, silently — verified this doesn't occur anywhere in the real dataset (all names resolve), so this is an accepted gap, not an oversight. Hard validation of this belongs to Story 1.8; no raising check added here.
  - [x] Run the Task-5 tests to green. **Result:** `3 passed in 2.40s`.

- [x] Task 6: Wire the orchestration script; land the real dataset (AC: 1, 4)
  - [x] Write a failing offline integration test first: `tests/test_build_f1_dataset.py` drives the same read → build → write flow (`read_raw_csvs()` → `build_curated_tables()` → `duckdb_io.write_dataframe()` for each of the 19 raw+curated tables) against the Task-2 fixtures and a `tmp_path` DuckDB file; asserts all 19 tables exist after the run. (This exercises already-unit-tested Task 3-5 components composed together, so it passed on first run rather than starting red — the genuine red/green cycles happened at the unit level; this integration test is the composed-pipeline proof.)
  - [x] Write a failing test for the fail-fast path: `test_pipeline_fails_fast_with_a_named_error_when_a_csv_is_missing` runs the same flow against a fixture directory missing `f1_qualifying.csv`; asserts `FileNotFoundError` naming that file (mirrors epics.md's "the script errors clearly with a CSV removed").
  - [x] Implement `scripts/build_f1_dataset.py` as a thin entry point wiring `data_sources.kaggle_csv` → `database.duckdb_io` (no business logic in the script itself). Adapted from `recovery/reference/scripts/build_f1_dataset.py`, dropping its `validation_results`/`register_source`/`log_source_load` calls (Story 1.8's scope) and its manual `sys.path.insert(0, str(SRC_DIR))` prelude (unneeded — the editable install already makes `f1_analytics` importable, per Story 1.4).
  - [x] Run the Task-6 tests to green. **Result:** `2 passed in 2.81s`.
  - [x] Manual run against the real, already-landed dataset: `uv run scripts/build_f1_dataset.py` against `data/raw/f1_complete_dataset/`. **Result:** `data/processed/f1_analytics.duckdb` created with all 19 tables. Row counts match the raw CSV line counts exactly for every 1:1 pass-through table (e.g. `results`/`raw_results`/`race_results_enriched` all 25939, matching `f1_results.csv`'s 25939 data rows; `final_driver_standings` 3128 matching `f1_driver_standings.csv`); `driver_standings_by_round` (25850) and `constructor_standings_by_round` (12773) are the expected per-round-per-entrant expansions. Spot-checked `final_driver_standings` for `NULL constructor_id`: **0 rows** across all 3128 real rows — the AC3 reconciliation resolves every real driver-standings row, not just the fixture's.

- [x] Task 7: Full verification (AC: 1, 2, 3, 4)
  - [x] Run `uv run pytest -v`; confirm the full suite (existing Story 1.4 tests + this story's new tests) passes, offline, with no network calls. **Result:** `21 passed in 1.08s` — 2 from Story 1.4 + 19 new from this story, no failures.
  - [x] Confirm `data/processed/f1_analytics.duckdb` is not committed (already gitignored via `data/processed/`) and `data/raw/` is not committed either. **Confirmed:** `git status data/` → "nothing to commit, working tree clean".
  - [x] `git status --porcelain`; confirm only the expected new/modified files appear. **Confirmed** — see Debug Log References for the full output; matches exactly (this story file, `pyproject.toml`, `uv.lock`, deleted `requirements.txt`, new `src/f1_analytics/{config.py,database/duckdb_io.py,data_sources/{kaggle_csv,standings}.py}`, `scripts/build_f1_dataset.py`, `tests/` (new, untracked directory), `sprint-status.yaml` modified) plus the pre-existing uncommitted state carried over from Stories 1.3/1.4 (unrelated to this story, untouched by it).
  - [x] Record all command output (uv sync, pytest run, the manual `build_f1_dataset.py` run, git status) in the Dev Agent Record.

### Review Findings

- [x] [Review][Patch] Remove now-dead `KAGGLE_SOURCE_NAME`/`KAGGLE_DATASET_HANDLE` constants from `config.py` — this story already trimmed other unused speculative constants (Jolpica/outputs) but left these two, which became unused the moment this story's own `duckdb_io.py` dropped `register_source`/`log_source_load` (their only consumers in the reference). [src/f1_analytics/config.py:14-15] — fixed: constants deleted, confirmed no remaining references anywhere in `src/`/`scripts/`/`tests/`.
- [x] [Review][Patch] `tests/test_build_f1_dataset.py` never exercises `scripts/build_f1_dataset.py`'s actual `main()` — it hand-copies the same read→build→write loop instead, so AC1's literal named artifact ("when `uv run scripts/build_f1_dataset.py` runs") has no test coverage against drift (a forgotten table, an import typo). [tests/test_build_f1_dataset.py:22-33, scripts/build_f1_dataset.py:9] — fixed: `main()` now takes overridable `raw_dir`/`db_path` parameters, and the test loads the real script module via `importlib` and calls its `main()` directly. Full suite re-verified green (21/21) and the real manual `uv run scripts/build_f1_dataset.py` run re-confirmed working against the actual dataset.
- [x] [Review][Defer] `add_standing_rank()` produces dense ranks (1,2,2,3) rather than standard competition ranks (1,2,2,4) after a tie — verified against the real dataset (1956 round 4: Collins/Moss correctly tie at rank 1, but Fangio gets rank 2 instead of the standard-convention 3rd). [src/f1_analytics/data_sources/standings.py:24-29] — deferred, pre-existing (byte-identical to `recovery/reference/src/f1_analytics/data_sources/standings.py`, which this story was directed to adapt from, not redesign)
- [x] [Review][Defer] Tie-detection (`group.ne(group.shift())`) is not NaN-safe — `NaN != NaN` in pandas, so two consecutive NaN cumulative values would spuriously break a tie. Not triggered by any real or fixture data today. [src/f1_analytics/data_sources/standings.py:25-26] — deferred, pre-existing (identical to reference)
- [x] [Review][Defer] `write_dataframe()` leaves `source_df` registered on the connection if `conn.execute` raises (no `try`/`finally` around register/unregister). [src/f1_analytics/database/duckdb_io.py:28-30] — deferred, pre-existing (identical to reference)
- [x] [Review][Defer] `write_dataframe()` interpolates `table_name` unescaped into raw SQL with no identifier quoting/validation. Not reachable today — every call site in this diff passes a hardcoded literal name. [src/f1_analytics/database/duckdb_io.py:29] — deferred, pre-existing (identical to reference)
- [x] [Review][Defer] Constructor name→id reconciliation (`drop_duplicates(subset=["constructor"])`) silently keeps the first-seen id if one free-text `constructor` name were ever bound to two different `constructor_id`s. Verified zero such collisions in the real dataset today. [src/f1_analytics/data_sources/kaggle_csv.py:82-93] — deferred, pre-existing (identical to reference); hard validation of reconciliation edge cases is explicitly Story 1.8's territory per this story's own Dev Notes
- [x] [Review][Defer] No column-presence validation for malformed CSVs and no merge-fanout guard against duplicate `(season, round)` rows in `races.csv`. [src/f1_analytics/data_sources/kaggle_csv.py — `read_raw_csvs`, `build_curated_tables`] — deferred, pre-existing (identical to reference); explicitly assigned to Story 1.8 ("Advisory Build Validation, Logged") by this story's own Dev Notes
- [x] [Review][Defer] `connect_duckdb()` binds `DUCKDB_PATH` as a mutable default parameter at import time, so patching the config constant after import has no effect on callers relying on the default. [src/f1_analytics/database/duckdb_io.py:13-14] — deferred, pre-existing (identical to reference)

## Dev Notes

### Scope and sequencing

- This is the first "data layer" story (epic narrative: "recovery and offsite protection first, the triple-gated FastF1 spike second, data layers after"). It runs after 1.4 (done — project skeleton) and before 1.6 (FastF1 facts), 1.7 (current-season combined tables), and 1.8 (advisory build validation).
- **Out of scope, deliberately** — do not build these even though the salvaged reference code and `docs/data_sources.md` describe them as part of the eventual end state:
  - `source_registry`, `source_load_log`, `validation_results` tables and any logging/validation calls (null-rate/referential-integrity checks) — that is Story 1.8's ("Advisory Build Validation, Logged") territory. `docs/data_sources.md` already documents the full eventual behavior including these; this story intentionally leaves that part unbuilt.
  - The typed append helper for `question_*` target-store tables (AD-4 class 2) — Epic 2's job. This story's replace-sync writer does **not** need a `question_*`-rejection guard yet either; no `question_*` tables exist anywhere in the rebuild at this point, so guarding against them now would be speculative.
  - Fixing the live Kaggle re-download path — `decisions/fastf1-source-adoption-decision-record.md` records that KaggleHub's re-download currently fails with an unresolved `400 Bad Request`; its "Next Steps" name investigating this directly in the Kaggle operator console as separate follow-on work, not this story's job. This story's AC is satisfied by the CSVs Story 1.3 already restored from the salvage tarball, which are already on disk.
  - Anything under `analysis/` — the dependency-direction rule means `analysis/` never imports `data_sources/`/`database/`, and this story doesn't touch it.

### Current on-disk state (verified 2026-08-07, before this story runs)

- `data/raw/f1_complete_dataset/` already has all 8 real Kaggle CSVs, landed via Story 1.3's salvage restore: `f1_races.csv`, `f1_results.csv`, `f1_drivers.csv`, `f1_constructors.csv`, `f1_driver_standings.csv`, `f1_constructor_standings.csv`, `f1_circuits.csv`, `f1_qualifying.csv`.
- `data/processed/` is empty — no `f1_analytics.duckdb` exists yet.
- `pyproject.toml` currently declares zero runtime dependencies (`dependencies = []`); only `pytest>=9.1,<10` exists as a dev dependency.
- `src/f1_analytics/data_sources/` and `src/f1_analytics/database/` both exist as empty packages (docstring-only `__init__.py`, from Story 1.4) — this story is the first to put real code in either.
- `requirements.txt` at the repo root still lists the 6 unpinned V1-era packages (`kagglehub`, `pandas`, `duckdb`, `plotly`, `jupyter`, `nbconvert`) and is orphaned/contradictory now that `pyproject.toml` is the real dependency source — Task 1 removes it.

### Verified CSV headers (2026-08-07, against the real files on disk — use these exact column names for fixtures)

- `f1_races.csv`: `season,round,race_name,circuit_id,date,time,url`
- `f1_results.csv`: `season,round,race_name,driver_id,driver_name,constructor_id,constructor,grid,position,points,laps,status,time,fastest_lap,fastest_lap_rank`
- `f1_drivers.csv`: `driver_id,given_name,family_name,dob,nationality,number,code,url`
- `f1_constructors.csv`: `constructor_id,name,nationality,url`
- `f1_driver_standings.csv`: `season,position,points,wins,driver_id,constructor`
- `f1_constructor_standings.csv`: `season,position,points,wins,constructor_id,constructor`
- `f1_circuits.csv`: `circuit_id,circuit_name,locality,country,lat,lng,url`
- `f1_qualifying.csv`: `season,round,driver_id,constructor_id,position,q1,q2,q3`

These already match the column names the salvaged reference code (`recovery/reference/src/f1_analytics/data_sources/kaggle_csv.py`) assumes — a strong signal it's a solid pattern reference — but re-verify at implementation time per AD-10 rather than trusting this note blindly; the file above is a point-in-time snapshot.

### Technical requirements and guardrails

- **Layer roles (spine):** `data_sources/` is the ingestion shell (CSV reading, curation, id mapping); `database/` is the storage edge and the *only* module that opens DuckDB connections; `scripts/` is a thin orchestration shell wiring the two together with no business logic of its own.
- **AD-4 (write-pattern split):** this story builds exactly one writer — the replace-sync helper (`CREATE OR REPLACE TABLE ... AS SELECT * FROM source_df`) for ingestion-class tables (`raw_*`, curated). Never build the target-store append helper or any `question_*` DDL here.
- **AD-14 (one entity id space):** Kaggle's ids are already in the shared Ergast/Jolpica-style id space (`driver_id`, `constructor_id`) — no id translation needed for Kaggle itself, only the one sanctioned `final_driver_standings.constructor_id` name→id reconciliation. Do not invent a second reconciliation anywhere else without a decision record.
- **AD-11 (offline tests):** every test in this story must run against the `tests/fixtures/kaggle_csv/` fixtures (or in-memory DataFrames), never the real `data/raw/f1_complete_dataset/` files and never a live Kaggle call. The repo's `tests/conftest.py` autouse fixture already blocks all socket access, so any accidental network call fails loudly rather than hanging.
- **AD-16 (fail early):** `require_raw_files()` must raise before any CSV is parsed if any are missing — the failure must name the specific missing file(s), not just say "files missing."
- **Consistency Conventions:** "shared derived logic is computed by one function, never re-implemented per table" — `compute_cumulative_standings()` must be the single function both `driver_standings_by_round` and `constructor_standings_by_round` call; do not write two versions.
- **Reuse, don't reinvent:** `recovery/reference/src/f1_analytics/{config.py, data_sources/kaggle_csv.py, data_sources/standings.py, database/duckdb_io.py, scripts/build_f1_dataset.py}` are strong, already-verified-against-this-exact-dataset pattern references (Story 1.3 salvage, commit `1dcdf79`) — adapt from them rather than designing from scratch. They are **not** fixed points (AD-10): trim the validation/metadata-logging pieces described as out-of-scope above, and re-verify column/table assumptions against this story's own fixtures and tests before trusting them.

### Expected project structure

| Path | Action | Purpose |
| --- | --- | --- |
| `pyproject.toml` | UPDATE | Add `pandas`, `duckdb`, `kagglehub` runtime dependencies. |
| `uv.lock` | UPDATE | Regenerated by `uv lock`/`uv sync`. |
| `requirements.txt` | DELETE | Orphaned/contradictory once real deps land in `pyproject.toml`. |
| `src/f1_analytics/config.py` | NEW | Path/name constants (adapted from `recovery/reference/`). |
| `src/f1_analytics/database/duckdb_io.py` | NEW | `connect_duckdb()`, `write_dataframe()` — the one replace-sync writer this story builds. |
| `src/f1_analytics/data_sources/standings.py` | NEW | `compute_cumulative_standings()`, `add_standing_rank()` — the one shared standings function. |
| `src/f1_analytics/data_sources/kaggle_csv.py` | NEW | `RAW_FILES`, `require_raw_files()`, `read_raw_csvs()`, `build_curated_tables()`. |
| `scripts/build_f1_dataset.py` | NEW | Thin orchestration entry point. |
| `tests/fixtures/kaggle_csv/*.csv` | NEW | 8 small synthetic fixture CSVs. |
| `tests/test_duckdb_io.py`, `tests/test_standings.py`, `tests/test_kaggle_csv.py`, `tests/test_build_f1_dataset.py` | NEW | Offline tests per Task 3-6. |
| `data/processed/f1_analytics.duckdb` | NEW (gitignored) | Built by the manual verification run; never committed. |
| `_bmad-output/implementation-artifacts/1-5-kaggle-curated-layer-rebuilt.md` | UPDATE | This file — task checkboxes, Dev Agent Record, Status. |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | UPDATE | Status transitions (handled by the dev-story workflow). |

Not in scope: `src/f1_analytics/validation/` (still empty — Story 1.8), `catalog/question_catalog.yaml` (Epic 2), `sql/` views (Story 1.7 adds `kaggle_jolpica_coverage`), any change under `src/f1_analytics/analysis/`.

### Testing standards

- Tests live in `tests/`, run via `uv run pytest`, and must never touch the network (AD-11) — the repo-wide `tests/conftest.py` autouse fixture already enforces this for every test automatically.
- Use small, hand-authored fixture CSVs under `tests/fixtures/kaggle_csv/` — never read from `data/raw/f1_complete_dataset/` in a test (that's real, gitignored, environment-dependent data, not a committed fixture).
- Follow red-green: for each new function (`write_dataframe`, `compute_cumulative_standings`, `require_raw_files`, `build_curated_tables`), write the failing test first, confirm it fails for the right reason, then implement until green.

### Previous story and Git intelligence

- Story 1.4 (done) explicitly deferred adding `pandas`/`duckdb`/`kagglehub` to `pyproject.toml` to this story, and its Review Findings recorded (as a now-open item in `deferred-work.md`) that `requirements.txt` should be reconciled/removed here once those real deps land — both are Task 1 above.
- Story 1.3 (`review`, commit `1dcdf79`) salvaged the full V1 code tree into `recovery/reference/`, including every module this story adapts from: `data_sources/kaggle_csv.py`, `data_sources/standings.py`, `database/duckdb_io.py`, `config.py`, `scripts/build_f1_dataset.py`, and `validation/checks.py` (the last one — do not use it; validation is Story 1.8's scope).
- Story 1.2 (done) verified `kagglehub==1.0.2` works in an isolated `uv run` environment during the FastF1 spike — a useful version anchor for Task 1's pin, though this story's `kagglehub` use is just the dependency declaration, not a live download call.
- Commit convention observed across 1.1-1.4: one commit per story, trailing `Story: <story-key>` line, `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 1 opening narrative, Story 1.5 section]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` — AD-1, AD-4, AD-6, AD-11, AD-13, AD-14, AD-16, Consistency Conventions, Stack table, Structural Seed, Capability → Architecture Map]
- [Source: `docs/data_sources.md` — Kaggle dataset handle, landing tables, curated tables, reconciliation rationale]
- [Source: `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` — Kaggle re-download's unresolved 400 error; verified `kagglehub==1.0.2`]
- [Source: `_bmad-output/implementation-artifacts/1-4-project-foundation-that-survives-a-fresh-clone.md` — Dev Notes' scope handoff to this story; Review Findings on `requirements.txt`]
- [Source: `_bmad-output/implementation-artifacts/deferred-work.md` — open `requirements.txt` reconciliation item assigned to this story]
- [Source: `recovery/reference/src/f1_analytics/{config.py,data_sources/kaggle_csv.py,data_sources/standings.py,database/duckdb_io.py}`, `recovery/reference/scripts/build_f1_dataset.py` — salvaged V1 pattern reference (AD-10: adapt, not a fixed point)]
- [Source: `data/raw/f1_complete_dataset/*.csv` header rows — verified 2026-08-07]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- `uv lock` → resolved 23 packages cleanly, no conflict: `pandas==3.0.5`, `duckdb==1.5.5`, `kagglehub==1.0.2` (exactly the Stack table's verified pins / the FastF1 spike's verified kagglehub version). `uv sync` → installed 16 packages.
- `uv run python -c "import pandas, duckdb, kagglehub; print('OK')"` → `OK`.
- `rm requirements.txt` — reconciled per Story 1.4's deferred finding.
- Dry-ran the reference `compute_cumulative_standings`/`add_standing_rank` algorithm by hand (scratch script) against the planned Task 4 tie fixture before writing test assertions — confirmed drivers `a`/`b` end round 2 tied at `cumulative_points=43, cumulative_wins=1`, both `standing_rank=1`, matching what the real implementation later produced.
- Each of Tasks 3-6's tests was confirmed to fail with `ModuleNotFoundError` for the not-yet-existing module before implementation (red), then passed after (green) — see each task's own subtask notes above for the exact error text and pass count.
- Manual run: `uv run scripts/build_f1_dataset.py` against the real `data/raw/f1_complete_dataset/` (8 CSVs landed via Story 1.3's salvage). Output:
  ```
  DuckDB database built: /Users/antonio/howdoidata/projects/f1_analytics/data/processed/f1_analytics.duckdb
  Raw tables: raw_races, raw_results, raw_drivers, raw_constructors, raw_driver_standings, raw_constructor_standings, raw_circuits, raw_qualifying
  Curated tables: races, results, drivers, constructors, circuits, qualifying, race_results_enriched, driver_standings_by_round, constructor_standings_by_round, final_driver_standings, final_constructor_standings
  ```
  Spot-check: raw CSV data-row counts (`f1_races.csv`=1171, `f1_results.csv`=25939, `f1_qualifying.csv`=11036, `f1_driver_standings.csv`=3128, `f1_constructor_standings.csv`=924, `f1_drivers.csv`=879, `f1_constructors.csv`=214, `f1_circuits.csv`=78) match every corresponding `raw_*` and 1:1-pass-through curated table row count exactly. `final_driver_standings` has **0** rows with a `NULL constructor_id` across all 3128 real rows — the AD-14 reconciliation resolves every real row, not just the fixture's.
- Final full suite: `uv run pytest -v` → `21 passed in 1.08s` (2 pre-existing Story 1.4 tests + 19 new).
- Final `git status --porcelain`: modified `_bmad-output/implementation-artifacts/sprint-status.yaml`; deleted `requirements.txt`; new `pyproject.toml`, `uv.lock`, `src/f1_analytics/config.py`, `src/f1_analytics/database/duckdb_io.py`, `src/f1_analytics/data_sources/{kaggle_csv.py,standings.py}`, `scripts/build_f1_dataset.py`, `tests/` (untracked dir incl. all new test files and fixtures), this story file — plus the pre-existing uncommitted carryover from Stories 1.3/1.4, untouched by this story. `git status data/` → clean (nothing to commit; `data/raw/`, `data/processed/` both correctly gitignored).

### Completion Notes List

- Added `pandas`, `duckdb`, `kagglehub` as pinned `pyproject.toml` dependencies (fulfilling Story 1.4's deferred commitment) and removed the now-redundant `requirements.txt`. Versions resolved to exactly the architecture spine's verified Stack pins with no resolver conflict.
- Built 8 synthetic fixture CSVs under `tests/fixtures/kaggle_csv/` (2 seasons, 3 drivers, a real constructor change for one driver between seasons) and `src/f1_analytics/config.py` with the path/name constants this story's modules need (trimmed of unused Jolpica/outputs constants out of this story's scope).
- Built the storage edge's one replace-sync writer (`database/duckdb_io.py`: `connect_duckdb()`, `write_dataframe()`) — proven idempotent (`CREATE OR REPLACE`, not append) by a dedicated test. No metadata-logging helpers added (Story 1.8's scope).
- Built the one shared cumulative-standings function (`data_sources/standings.py`) reused by both driver and constructor standings-by-round tables — proven against a hand-verified tie scenario (two drivers ending a round cumulatively tied on points and wins, correctly sharing `standing_rank`).
- Built Kaggle CSV loading and all 11 curated tables (`data_sources/kaggle_csv.py`), including the one sanctioned `final_driver_standings.constructor_id` name→id reconciliation (AD-14) — proven against a fixture driver who genuinely changes constructors between seasons, and confirmed 100%-resolving against the real 3128-row dataset. `require_raw_files()` fails fast with the specific missing filename named in the error.
- Wired the thin orchestration script (`scripts/build_f1_dataset.py`) and ran it against the real, already-landed Kaggle CSVs: all 19 raw+curated tables built in `data/processed/f1_analytics.duckdb` with row counts matching the source CSVs exactly.
- Full regression suite green (21/21, offline, no network calls) at every step; no scope creep into Story 1.8 (validation/metadata logging) or Epic 2 (`question_*` typed-append writer) territory.

### File List

**New:**
- `src/f1_analytics/config.py`
- `src/f1_analytics/database/duckdb_io.py`
- `src/f1_analytics/data_sources/standings.py`
- `src/f1_analytics/data_sources/kaggle_csv.py`
- `scripts/build_f1_dataset.py`
- `tests/fixtures/kaggle_csv/f1_races.csv`
- `tests/fixtures/kaggle_csv/f1_results.csv`
- `tests/fixtures/kaggle_csv/f1_drivers.csv`
- `tests/fixtures/kaggle_csv/f1_constructors.csv`
- `tests/fixtures/kaggle_csv/f1_driver_standings.csv`
- `tests/fixtures/kaggle_csv/f1_constructor_standings.csv`
- `tests/fixtures/kaggle_csv/f1_circuits.csv`
- `tests/fixtures/kaggle_csv/f1_qualifying.csv`
- `tests/test_kaggle_csv_fixtures.py`
- `tests/test_duckdb_io.py`
- `tests/test_standings.py`
- `tests/test_kaggle_csv.py`
- `tests/test_build_f1_dataset.py`

**Modified:**
- `pyproject.toml` (added `pandas`, `duckdb`, `kagglehub` dependencies)
- `uv.lock` (regenerated)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status transitions: `ready-for-dev` → `in-progress` → `review`)
- `_bmad-output/implementation-artifacts/1-5-kaggle-curated-layer-rebuilt.md` (this file — frontmatter, task checkboxes, Dev Agent Record, Status)

**Deleted:**
- `requirements.txt`

**Gitignored (not committed, produced by the manual verification run):**
- `data/processed/f1_analytics.duckdb`

## Change Log

- 2026-08-07: Story created (ready-for-dev).
- 2026-08-07: Implemented the Kaggle curated layer end-to-end — pinned `pandas`/`duckdb`/`kagglehub` dependencies and reconciled `requirements.txt`; built the storage edge's replace-sync writer, the shared cumulative-standings function, Kaggle CSV loading with fail-fast and the AD-14 reconciliation, and the orchestration script. Ran the real, already-landed dataset through the pipeline (19/19 tables, row counts verified, 0 unresolved reconciliations). Full suite green (21/21, offline). All 7 tasks complete.
