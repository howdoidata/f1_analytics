# Deferred Work

### DW-1: `docs/decisions.md` carries an undefined `TARGET_DIR` placeholder, out-of-order entries, and unflagged abandoned-initiative content

origin: migrated from legacy ledger ("Deferred from: code review of story-1.3 (2026-08-07)"), 2026-08-08
location: docs/decisions.md
reason: The restored historical document has 3 undefined `TARGET_DIR` placeholder occurrences (e.g. "Direct verification against `TARGET_DIR` (2026-07-10) confirms..."), non-chronological entry ordering (two 2026-07-07 entries interleaved between the 07-08/07-09 blocks), and unflagged content about an abandoned "multi-project platform bootstrap" initiative that is inconsistent with the current single-repo rebuild direction. Deferred because these are pre-existing characteristics of a verbatim-restored salvaged document: this story's own precedent (AD-10, and its explicit decision not to fix trailing-blank-line formatting in `recovery/reference/`) argues against editing salvaged content, and a future doc-hygiene pass could annotate or redact if `docs/decisions.md` ever becomes actively referenced.
status: open

### DW-2: `conftest.py`'s `connect_ex` override breaks the real method's contract

origin: migrated from legacy ledger ("Deferred from: code review of story-1.4 (2026-08-07)"), 2026-08-08
location: tests/conftest.py:15-16
reason: The network-blocking fixture makes `connect_ex` raise, but production `connect_ex` never raises — it returns an errno int — so code written against the real contract would see the wrong failure mode under test. Currently unreachable: no code in the repo calls `connect_ex`.
status: open

### DW-3: The network-blocking fixture does not cover connectionless UDP sends

origin: migrated from legacy ledger ("Deferred from: code review of story-1.4 (2026-08-07)"), 2026-08-08
location: tests/conftest.py:19-27
reason: The fixture only patches `connect`/`connect_ex`, so a connectionless UDP socket's `sendto`/`send` would escape the guard and reach the network. Currently unreachable: no UDP usage exists in the repo.
status: open

### DW-4: A spawned `multiprocessing` or `subprocess` child escapes the socket monkeypatch guard

origin: migrated from legacy ledger ("Deferred from: code review of story-1.4 (2026-08-07)"), 2026-08-08
location: tests/conftest.py:19-27
reason: A `multiprocessing` (spawn) worker or a `subprocess` re-imports `socket` fresh in a new interpreter and never sees the `monkeypatch` guard, leaving that child free to open network connections during a test run. No test spawns child processes today.
status: open

### DW-5: README's open-ended "uv 0.12+" may conflict with the `uv_build<0.13` build-backend pin

origin: migrated from legacy ledger ("Deferred from: code review of story-1.4 (2026-08-07)"), 2026-08-08
location: README.md:7, pyproject.toml:11
reason: README states "uv 0.12+" (open-ended) while `pyproject.toml` pins the build backend to `uv_build<0.13`, a potential mismatch for a reader who installs a newer `uv`. Not confirmed to actually break `uv sync`.
status: open

### DW-6: Nothing enforces "builds identically from a bare checkout" on an ongoing basis

origin: migrated from legacy ledger ("Deferred from: code review of story-1.4 (2026-08-07)"), 2026-08-08
location: repo-wide
reason: There is no CI workflow that re-verifies the bare-checkout build claim as the repo changes, so the guarantee holds only as of the manual check. Likely Story 1.8's ("Advisory Build Validation, Logged") territory rather than the scaffolding story's.
status: done 2026-08-08
resolution: already resolved: .github/workflows/ci.yml's `test` job (added commit 7d55ac0) runs a bare `actions/checkout@v4` then `uv sync` + `uv run pytest` on every push to main and every pull request, so the builds-from-a-bare-checkout claim is now re-verified continuously rather than only as of a manual check.

### DW-7: `requirements.txt` is an orphaned, contradictory dependency manifest

origin: migrated from legacy ledger ("Deferred from: code review of story-1.4 (2026-08-07)"), 2026-08-08
location: requirements.txt
reason: `requirements.txt` lists 6 unpinned packages while `pyproject.toml` declares zero dependencies, so the repo carries two contradictory dependency manifests. Deferred per user decision 2026-08-07: Story 1.5 adds `pandas`/`duckdb`/`kagglehub` as real `pyproject.toml` dependencies (confirmed in epics.md), making `requirements.txt` naturally redundant then, so it should be reconciled or removed as part of that story rather than now.
status: done 2026-08-08
resolution: already resolved: requirements.txt was deleted in commit 86d43dc and `git ls-files requirements.txt` returns nothing; pyproject.toml now declares pandas>=3.0/duckdb>=1.5/kagglehub>=1.0 as real dependencies, which is exactly the Story 1.5 reconciliation this entry was deferred to.

### DW-8: `add_standing_rank()` produces dense ranks rather than standard competition ranks after a tie

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/data_sources/standings.py:24-29
reason: Ranks come out 1,2,2,3 instead of 1,2,2,4 after a tie — verified against the real dataset (1956 round 4). Left as-is because the function is byte-identical to the salvaged reference this story was directed to adapt from, not redesign; a future story should decide the intended ranking convention for per-round standings questions and, if standard ranking is wanted, fix it in the one shared function. Not currently blocking: confirmed 2026-08-08 that none of Epic 2/3's five target questions read per-round rank (only points/position from results-level status fields) — re-check this entry if a future question ever keys on rank.
status: open
decision: 2026-08-08 Switch to standard competition ranking — Replace the cumsum-of-tie-changes with a standard competition rank over cumulative points then wins within each season/round group, so the position after a tie skips (1, 2, 2, 4). Update tests/test_standings.py to pin the skip behavior explicitly, and verify the 1956 round 4 case now ranks as expected. The change lands in the one shared function, so both curated and combined standings tables inherit it.

### DW-9: Tie-detection in `add_standing_rank()` is not NaN-safe

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/data_sources/standings.py:25-26
reason: `group.ne(group.shift())` relies on equality comparison, and `NaN != NaN` in pandas, so consecutive NaN values would be scored as distinct rather than tied. Not triggered by any real or fixture data today; identical to the salvaged reference.
status: open

### DW-10: `write_dataframe()` leaves `source_df` registered on the connection when the write raises

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/database/duckdb_io.py:28-30
reason: There is no `try`/`finally` around the registration, so a raising `conn.execute` leaves the temporary `source_df` view bound to the connection for the rest of its life. Identical to the salvaged reference.
status: open

### DW-11: `write_dataframe()` interpolates `table_name` into raw SQL with no identifier quoting

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/database/duckdb_io.py:29
reason: The table name is interpolated unescaped into the statement text rather than being quoted as an identifier. Not reachable today (every call site passes a hardcoded literal); identical to the salvaged reference.
status: open

### DW-12: Constructor name→id reconciliation would silently keep the first-seen id on a collision

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/data_sources/kaggle_csv.py:82-93
reason: `drop_duplicates(subset=["constructor"])` keeps the first row, so one free-text `constructor` name ever bound to two different `constructor_id`s would silently lose the second mapping. Verified zero such collisions in the real dataset today; identical to the salvaged reference, and hard validation of reconciliation edge cases is explicitly Story 1.8's territory.
status: open

### DW-13: No column-presence validation for malformed CSVs and no merge-fanout guard on `races.csv`

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/data_sources/kaggle_csv.py
reason: Loading does not verify that expected columns are present, and nothing guards against duplicate `(season, round)` rows in `races.csv` fanning out the merge. Identical to the salvaged reference; explicitly assigned to Story 1.8 ("Advisory Build Validation, Logged").
status: open

### DW-14: `connect_duckdb()` binds `DUCKDB_PATH` as an import-time default parameter

origin: migrated from legacy ledger ("Deferred from: code review of story-1.5 (2026-08-07)"), 2026-08-08
location: src/f1_analytics/database/duckdb_io.py:13-14
reason: The default parameter captures `DUCKDB_PATH` at import time, so patching the config constant after import has no effect on callers that rely on the default. Identical to the salvaged reference.
status: open

### DW-15: `.bmad-loop/policy.toml` hides project-wide orchestration policy behind a blanket gitignore

origin: migrated from legacy ledger ("Deferred from: bmad-build multi-goal split (2026-08-08)"), 2026-08-08
location: .bmad-loop/policy.toml, .gitignore
reason: The file is entirely gitignored but mixes genuinely machine-specific settings ([tui] pane sizes, [mux] backend — the only ones its own comments justify) with project-wide orchestration policy ([gates], [review], [scm], [adapter] CLI routing) that is therefore invisible to git and unreviewable by the team. Split from the gitignore-audit build intent because the fix is not mechanical: it needs a decision (accept per-machine diff noise by tracking the whole file, or obtain an upstream bmad-loop change that splits machine-local from project-shared config) rather than a code change.
status: open
decision: 2026-08-08 Mirror the project-wide sections into a tracked doc — Leave the generated file ignored and record the project-wide orchestration policy ([gates], [review], [scm], [adapter]) in a tracked human-readable document under docs/, stating plainly that it mirrors .bmad-loop/policy.toml and is the reviewable copy. Gets the policy under review without fighting the installer, at the cost of a mirror that can drift from the generated file.

Content read in full on 2026-08-08: no credentials, tokens, or personal paths are present today, so tracking the whole file carries no secret-exposure risk as of this writing — only future diff noise. Attempted and reverted the same day: tracking fights `bmad_loop/install.py`'s `init`, which unconditionally re-adds this exact gitignore line on every run with no suppression flag (see track-bmad-loop-policy-2026-08-08.md). The visibility gap is real but has no clean fix from this repo alone; it needs an upstream bmad-loop change that splits machine-local from project-shared config in the generated file.

### DW-16: Tracking `.memlog.md` in git creates a merge-conflict failure mode for concurrent worktree sessions

origin: migrated from legacy ledger ("Deferred from: bmad-build review of gitignore fix (2026-08-08)"), 2026-08-08
location: _bmad/scripts/memlog.py, .bmad-loop/policy.toml (scm.isolation = "worktree")
reason: Tracking `_bmad-output/**/.memlog.md` in git makes concurrent bmad-loop worktree sessions appending to the same logical memlog capable of producing real git merge conflicts — structurally impossible while the file was gitignored. Surfaced by review of the memlog-tracking decision (track-bmad-workspace-memlogs-2026-08-08.md); not caused by any code in this repo, but a new failure mode this repo can now hit. No concurrent-worktree memlog collision has occurred yet and no fix has been designed.
status: open
decision: 2026-08-08 Add a union merge driver for memlog paths — Keep memlogs tracked and add a .gitattributes rule giving `_bmad-output/**/.memlog.md` (and docs/.memlog.md) a union merge strategy, so two sessions' appends concatenate instead of conflicting. Verify the behavior with a deliberate concurrent-append merge, and note the ordering caveat union merge implies for an append-only log.

### DW-17: Full-table replace-sync of `raw_jolpica_results` can regress previously-landed rows

origin: migrated from legacy ledger ("Deferred from: code review of story-1.7 (2026-08-08)"), 2026-08-08
location: scripts/build_combined_dataset.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-7-current-season-combined-tables-and-the-coverage-arbiter.md`
reason: `write_dataframe` performs `CREATE OR REPLACE TABLE` unconditionally from the current run's in-memory result, including the empty-shaped degrade path, with no merge against what is already durable — so a run whose live fetch degrades or fails can regress previously-landed Jolpica rows. Story 1.6's review log already flagged this regression class and explicitly deferred it "for a Story 1.7/1.8 follow-up"; 1.7 inherited the pattern via the shared AD-4 `write_dataframe` writer its Boundaries required it to use, rather than resolving it.
status: done 2026-08-08
resolution: already resolved: write_dataframe's refuse_regression guard (src/f1_analytics/database/duckdb_io.py:52-58) is wired into all four live-fetched tables at scripts/build_combined_dataset.py:366-369 (which also re-reads the preserved table so downstream builds use last-known-good data) and scripts/pull_fastf1_data.py:199-216, proven by tests/test_duckdb_io.py:52-81, tests/test_build_combined_dataset.py:357 and tests/test_pull_fastf1_data.py:193.

Update (2026-08-08 correct-course): `write_dataframe()` gained an opt-in `refuse_regression` guard (raises `WriteRegressionError`, leaving the existing table untouched) with no change to its default unguarded behavior, so AD-4's adopted "idempotent CREATE OR REPLACE sync" contract and its existing test stay intact. It was wired into all 4 live-fetched tables: `raw_jolpica_results` (`build_combined_dataset.py`, which also re-reads the preserved table back into memory so `combined_results`/standings are computed from last-known-good data rather than degrading to it) and `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather` (`pull_fastf1_data.py`). Proven by `tests/test_duckdb_io.py`, `tests/test_build_combined_dataset.py::test_main_reuses_previous_jolpica_data_when_a_later_fetch_regresses`, and `tests/test_pull_fastf1_data.py::test_a_later_run_landing_fewer_races_does_not_shrink_the_table`. Kaggle-sourced tables (Story 1.5) were intentionally excluded — `docs/kaggle-raw-data-is-static.md` confirms they read static local CSVs, not a live fetch, so this regression class cannot occur there.

### DW-18: `combined_results.time` mixes two incompatible time formats depending on which source won a round

origin: migrated from legacy ledger ("Deferred from: code review of story-1.7 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/data_sources/jolpica_loader.py (shape_results)
source_spec: `_bmad-output/implementation-artifacts/spec-1-7-current-season-combined-tables-and-the-coverage-arbiter.md`
reason: `jolpica_loader.shape_results` casts Jolpica's `totalRaceTime` straight to `.astype("string")` without reformatting to Kaggle's compact `"1:31:44.742"`/`"+5.023"` convention (the code's own comment already flags this as "best-effort"), so downstream consumers see Kaggle's clock/gap format or a raw pandas-Timedelta string depending on which source won a given round; no test asserts the `time` value's format. Not fixed inline because the exact target format needs a decision rather than a guess — the same reasoning as the `add_standing_rank()` ranking-convention deferral from Story 1.5's review. Not currently blocking: confirmed 2026-08-08 that Epic 2's lap-time questions (Q01/Q04, Story 2.4) source from `raw_fastf1_laps`, not `combined_results` — re-check this entry if a future question ever sources timing from `combined_results.time`.
status: open
decision: 2026-08-08 Normalize Jolpica time to Kaggle's convention — Reformat `totalRaceTime` inside shape_results to Kaggle's existing convention — absolute clock time for the winner, "+gap" for everyone else — so `combined_results.time` reads identically regardless of which source won a round. Add tests pinning the rendered format for both a Kaggle-won and a Jolpica-won round, which nothing asserts today.

### DW-19: Jolpica's 500 req/hour budget is tracked per invocation, not against the real wall-clock hour

origin: migrated from legacy ledger ("Deferred from: code review of story-1.7 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/data_sources/jolpica_fetch.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-7-current-season-combined-tables-and-the-coverage-arbiter.md`
reason: `HOURLY_REQUEST_CAP`/`request_count` (a module-local counter inside `fetch_all_race_result_pages`) reset to 0 on every subprocess invocation of the isolated-env fetch script, and nothing persists request counts across repeated or retried runs within the same real clock hour. A single season fetch uses only a handful of requests (pagination is ~1-5 pages for a ~24-round season), so the realistic risk of exceeding Jolpica's actual hourly cap through repeated manual runs is low today, but AD-13's "budgeted against the 500/hour cap" claim only holds per-invocation, not per real hour.
status: open

### DW-20: Combined tables rebuild all of history on every run despite the story's current-season framing

origin: migrated from legacy ledger ("Deferred from: code review of story-1.7 (2026-08-08)"), 2026-08-08
location: scripts/build_combined_dataset.py, sql/kaggle_jolpica_coverage.sql
source_spec: `_bmad-output/implementation-artifacts/spec-1-7-current-season-combined-tables-and-the-coverage-arbiter.md`
reason: `combined_results`/`combined_driver_standings_by_round`/`combined_constructor_standings_by_round` rebuild from 1950-2026 on every run; verified live that `combined_results` holds 26,115 rows, of which 25,939 (99.3%) are Kaggle's full all-time history rewritten via full replace-sync every build, while only 176 rows are the genuine 2026 `jolpica_only` gap-fill the story's Intent describes. Deferred per user decision 2026-08-08 rather than patched to a season filter now: before resolving this narrowly, validate whether FastF1's Jolpica/Ergast client can itself serve full historical (pre-2026) results and standings data, since if it can, that opens a path to FastF1 fully replacing Kaggle as the historical source and would reframe this scoping question (and possibly the whole curated/combined split) rather than being settled by a one-line season filter. Needs a dedicated spike, likely modeled on Story 1.2's FastF1 adoption spike.
status: open
decision: 2026-08-08 Run the FastF1 historical-coverage spike — Probe FastF1 3.8.3's Ergast-compatible client for pre-2026 results and standings coverage, modeled on scripts/spike_fastf1_adoption.py — same isolated pandas-<3 subprocess environment, same evidence-document output. Report concretely which historical seasons and entities it can and cannot serve, and record the finding as a decision record so the season-scoping question (and the larger Kaggle-as-historical-source question) can be settled on evidence rather than assumption. Do not change the combined build in this session.

### DW-21: Add a `regression_refused` validation finding logged whenever the write-regression guard fires

origin: migrated from legacy ledger ("Deferred from: bmad-build multi-goal split of story-1.8 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/validation/, scripts/pull_fastf1_data.py, scripts/build_combined_dataset.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-8-advisory-build-validation-logged.md`
reason: Log a `regression_refused` validation finding whenever `write_dataframe`'s `refuse_regression` guard catches a `WriteRegressionError`, naming the table, race/season/round, and both row counts. Split from Story 1.8's spec because including it pushed that spec to 2,295 tokens (over the 1,600-token risk ceiling); the check was added to Story 1.8's scope by the 2026-08-08 correct-course amendment (epics.md AC, additive "And" clause) on top of the story's original null-rate/referential-integrity/source-registry scope, and is self-contained enough to build as its own follow-up once the base validation module exists.
status: open

### DW-22: Add a `race_points_mismatch` reconciliation check between standings and summed results points

origin: migrated from legacy ledger ("Deferred from: bmad-build multi-goal split of story-1.8 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/validation/, src/f1_analytics/data_sources/standings.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-8-advisory-build-validation-logged.md`
reason: Compare each `*_standings_by_round` row's `race_points` against summed `results.points` for that driver/season/round and log a finding per disagreement. Split from Story 1.8's spec for the same token-budget reason as the `regression_refused` entry, and also a 2026-08-08 correct-course addition on top of that story's original scope. This is the tracked follow-up for the live-verified defect (40 pre-2026 `race_points` mismatches, 0 in 2026 data) recorded separately in this ledger; that entry's tracking note should be updated once this check ships.
status: open

### DW-23: `compute_cumulative_standings()`'s `race_points` disagrees with raw `results.points` for 40 1950s rows

origin: migrated from legacy ledger ("Deferred from: live traceability check of story-1.7 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/data_sources/standings.py
reason: Verified live against the real database: `driver_standings_by_round` (Story 1.5, Kaggle-only) and `combined_driver_standings_by_round` (Story 1.7) show the identical 40 mismatches, all from 1950s shared-drive entries where one driver has two `results` rows for the same season/round (one carrying the finishing points, one carrying 0) — e.g. Fangio, 1950 round 7, has `results` rows with `points` 0.0 and 1.0 for the same key while the standings table's `race_points` is 1.0. Byte-identical behavior in both tables confirms this is pre-existing in the shared `compute_cumulative_standings()`/`add_standing_rank()` function (untouched by Story 1.7, per its Boundaries) rather than something 1.7 introduced; zero mismatches exist in 2026 data. Likely the same class of issue as the deferred dense-vs-standard ranking convention, and a future story should decide how shared-drive entries net into per-round points before `combined_driver_standings_by_round` is trusted for a question keyed on 1950s-era results.
status: open
decision: 2026-08-08 Keep summing; let the new check surface each case

Follow-up tracking (2026-08-08): a `race_points_mismatch` validation check was added to Story 1.8's scope via correct-course, then split back out to its own follow-up entry under "bmad-build multi-goal split of story-1.8" (Story 1.8 shipped only the null-rate/referential-integrity/source-registry base). It will surface every such disagreement in `validation_results` once that follow-up ships. Still not blocking Epic 2/3, since there are zero mismatches in 2026 data.

### DW-24: A NULL `*_id` checked by `REFERENTIAL_CHECKS` but not `NULL_RATE_CHECKS` is invisible to both check types

origin: migrated from legacy ledger ("Deferred from: code review of story-1.8 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/validation/checks.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-8-advisory-build-validation-logged.md`
reason: `check_referential_integrity`'s `child_values = child_frame[child_column].dropna()` deliberately treats a NULL foreign key as a null-rate concern rather than an orphan (by design, per its own test `test_check_referential_integrity_ignores_nulls_in_the_child_column`), so any `*_id` column registered in `REFERENTIAL_CHECKS` but absent from `NULL_RATE_CHECKS` has that null-rate concern never actually checked either. Confirmed for `results.constructor_id` and `races.circuit_id` (original scope) plus `combined_results.constructor_id`, `raw_fastf1_laps.constructor_id`, and `raw_fastf1_stints.constructor_id` (added when the review-loop amendment extended the registries to combined/raw tables, 2026-08-08 round 2). Not fixed inline because closing the gap is a scope decision (whether to add these five columns to `NULL_RATE_CHECKS`) rather than a defect in what was built.
status: open
decision: 2026-08-08 Add the five columns to NULL_RATE_CHECKS — Register results.constructor_id, races.circuit_id, combined_results.constructor_id, raw_fastf1_laps.constructor_id and raw_fastf1_stints.constructor_id in NULL_RATE_CHECKS so every referential-checked id also gets null-rate coverage, closing the both-blind gap. Findings stay advisory per AD-8 — new failures print and log but never fail a build — and the existing referential behavior is unchanged.

`NULL_RATE_CHECKS` checks only season/round/driver_id/position/points for `results`/`combined_results` and season/round/driver_id for `raw_fastf1_laps`/`raw_fastf1_stints` — `constructor_id` was never in scope for null-rate checking on any of them. The curated-`results` shape matches epics.md's Story 1.8 AC and the salvaged `recovery/reference/.../checks.py` registry verbatim, and the combined/raw entries were modeled on that same shape.

### DW-25: `raw_jolpica_results` has no validation registry entry and is absent from both scripts' `VALIDATION_TABLES`

origin: migrated from legacy ledger ("Deferred from: code review of story-1.8 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/validation/checks.py, scripts/build_combined_dataset.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-8-advisory-build-validation-logged.md`
reason: Story 1.7's live-fetched, `refuse_regression`-guarded raw table gets no null-rate or referential-integrity coverage at all, even though `epic-1-context.md`'s Storage paragraph groups it with `raw_fastf1_laps`/`stints`/`weather` as "every live-fetched raw table" under the write-regression guard; only the FastF1 trio got registry entries in the review-loop amendment, because round 1 flagged just `combined_results` and the FastF1 tables as loaded-but-unchecked and `raw_jolpica_results` was not loaded for validation by either script. Partially mitigated: `combined_results` (which is checked) absorbs `raw_jolpica_results`' rows verbatim for every `jolpica_only` round per Story 1.7's precedence rule, giving substantial but incomplete transitive coverage — a `raw_jolpica_results` row excluded or transformed before landing in `combined_results` (e.g. a `row_count_diverges` round, where Kaggle rows win and the Jolpica row never surfaces at all) would still be invisible to every check.
status: open

### DW-26: `log_source_load()` writes a `source_registry` row per call instead of once per source per build

origin: migrated from legacy ledger ("Deferred from: code review of story-1.8 (2026-08-08)"), 2026-08-08
location: src/f1_analytics/validation/store.py, scripts/pull_fastf1_data.py
source_spec: `_bmad-output/implementation-artifacts/spec-1-8-advisory-build-validation-logged.md`
reason: `store.log_source_load(conn, source, table_name, row_count)` unconditionally inserts into both `source_registry` and `source_load_log` on every call, and `pull_fastf1_data.py` calls it per landed table (`for table_name, row_count in written_tables.items(): log_source_load(conn, "fastf1", table_name, row_count)`), so a single run writes up to 3 near-identical "fastf1" rows into `source_registry` instead of 1. `source_load_log` correctly gets one row per table load (the intended cardinality); `source_registry`'s cardinality should be one row per source per build but is not, and `build_combined_dataset.py` avoids the issue only incidentally (one call each for kaggle/jolpica, naturally 1:1). Not fixed inline because closing it cleanly means splitting `log_source_load` into a registry-once call and a per-table load-log call, touching `store.py`, both scripts, and their tests — a real fix, but a data-hygiene/audit-log nuance (redundant rows, not wrong data) rather than a defect in what the story's AC requires ("source_registry and source_load_log each gain new rows documenting the sources and tables involved" — satisfied, just more redundantly than ideal).
status: open

### DW-27: `bmad-loop validate` permanently flags `_bmad/render/.gitignore` as tracked, but untracking it removes a deliberate defense-in-depth guard

origin: bmad-loop-setup upgrade preflight (`bmad-loop validate`), 2026-08-08
location: _bmad/render/.gitignore, .gitignore:52
severity: low
reason: `bmad-loop validate` warns "`_bmad/render/` is tracked by git; run `git rm -r --cached _bmad/render` and commit once to stop committing rendered skill output." The only tracked file under that path is `_bmad/render/.gitignore` itself (contents: `*` / `!.gitignore`), committed deliberately per `repo-remediation-2026-08-07.md` so a fresh clone gets the self-exclusion rule immediately — a second layer of protection alongside the top-level `.gitignore`'s own `_bmad/render/` line (added the same remediation), guarding against the ephemeral rendered-workflow cache being swept into git history if that top-level line is ever removed or missed. Untracking the nested file would make `validate` pass clean but drops that second layer down to the single top-level rule; leaving it tracked keeps the original intent but means this one `validate` warning never clears. Needs a human call on which property to keep — not a mechanical fix, and not caused by any code change in this session.
status: done 2026-08-08
decision: 2026-08-08 Untrack the file, accept the single-layer guard — `bmad-loop validate`'s `git.render-tracked` finding is `warn`-severity only and never affected the tool's pass/fail exit code; the installed CLI's own source comment says the check exists to catch churning rendered-output snapshots being swept into history, not static hand-committed guard files like this one, so clearing it was always cosmetic rather than a functional trade-off — human chose to clear it anyway. Confirmed no other tracked files exist under `_bmad/render/` (only `.gitignore` itself) and that installed `bmad-loop` v0.9.1 has no per-warning suppression/allowlist mechanism, so there was no third option that keeps both properties. `bmad_loop/install.py`'s `init` step unconditionally re-adds the exact `_bmad/render/` line to the top-level `.gitignore` whenever it's missing — the same self-healing mechanism DW-15 flags for a different managed line (`.bmad-loop/policy.toml`) — so the remaining single-layer guard heals itself on any project that re-runs `bmad-loop-setup`, though nothing enforces it between such runs (tracked separately as DW-28).
resolution: `git rm --cached _bmad/render/.gitignore` (staged, committed alongside this ledger update) untracks the file. In this working copy it remains on disk, now covered only by the top-level `.gitignore`'s `_bmad/render/` line (52) — confirmed via `git check-ignore -v` that every file currently under `_bmad/render/` (`config.yaml` plus the full rendered `bmad-build`/`bmad-build-auto` trees) matches that same rule. Plain `git status` shows nothing for the file once committed (it surfaces only under `git status --ignored`); on any other checkout — fresh clone, CI, a teammate's pull — the file will simply be absent rather than present-but-ignored, since git applies the removal as a normal tree change everywhere but this one working copy. Verified `bmad-loop validate` no longer emits the `git.render-tracked` finding — confirmed independently of this session's pre-existing, unrelated `git.worktree-clean` failure, since the two checks run in separate try/except blocks in `cli.py` and the render check reported clean even while worktree-clean failed. To reverse this decision later: `git add -f _bmad/render/.gitignore && git commit`.

### DW-28: Nothing asserts the top-level `.gitignore`'s `_bmad/render/` line stays present now that it is the sole guard against committing rendered skill output

origin: bmad-build review (blind-hunter) of the DW-27 fix, 2026-08-08
location: .gitignore:52
source_spec: `_bmad-output/implementation-artifacts/spec-dw-27-untrack-render-gitignore.md`
severity: low
reason: DW-27 traded the nested `_bmad/render/.gitignore` defense-in-depth guard for a clean `bmad-loop validate`, leaving the top-level `.gitignore`'s `_bmad/render/` line as the only thing preventing the ephemeral rendered-workflow cache from ever being committed — exactly the failure mode DW-27's own reasoning named as the accepted risk. Not fixed inline because designing a compensating check (test, CI step, or lint rule) is new scope beyond DW-27's narrow "which property to keep" decision. Partially mitigated today: `bmad_loop/install.py`'s `init` step unconditionally re-adds this exact line whenever it's missing, so the guard self-heals on any project that re-runs `bmad-loop-setup` — but nothing enforces it between such runs, so a manually-edited or accidentally-shrunk `.gitignore` would go unnoticed until the next install/upgrade.
status: open
