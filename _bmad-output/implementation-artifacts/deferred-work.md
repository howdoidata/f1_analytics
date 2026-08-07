# Deferred Work

## Deferred from: code review of story-1.3 (2026-08-07)

- `docs/decisions.md` carries an undefined `TARGET_DIR` placeholder (3 occurrences, e.g. "Direct verification against `TARGET_DIR` (2026-07-10) confirms..."), non-chronological entry ordering (two 2026-07-07 entries interleaved between 07-08/07-09 blocks), and unflagged content about an abandoned "multi-project platform bootstrap" initiative that is inconsistent with the current single-repo rebuild direction. Deferred: pre-existing characteristics of the verbatim-restored historical document — this story's own precedent (AD-10, and its explicit decision not to fix trailing-blank-line formatting in `recovery/reference/`) argues against editing salvaged content; a future doc-hygiene pass could annotate or redact if `docs/decisions.md` becomes actively referenced. [docs/decisions.md]

## Deferred from: code review of story-1.4 (2026-08-07)

- `conftest.py`'s `connect_ex` override breaks the real method's contract (production `connect_ex` never raises — it returns an errno int). Currently unreachable: no code in the repo calls `connect_ex`. [tests/conftest.py:15-16]
- The network-blocking fixture only patches `connect`/`connect_ex`; a connectionless UDP socket's `sendto`/`send` would escape it. Currently unreachable: no UDP usage exists in the repo. [tests/conftest.py:19-27]
- A `multiprocessing` (spawn) worker or `subprocess` re-imports `socket` fresh and escapes the `monkeypatch` guard. No test spawns child processes today. [tests/conftest.py:19-27]
- README states "uv 0.12+" (open-ended) while `pyproject.toml` pins the build backend to `uv_build<0.13` — potential mismatch for a reader who installs a newer `uv`. Not confirmed to actually break `uv sync`. [README.md:7, pyproject.toml:11]
- Nothing enforces "builds identically from a bare checkout" on an ongoing basis (no CI workflow). Likely Story 1.8's ("Advisory Build Validation, Logged") territory, not this scaffolding story's. [repo-wide]
- `requirements.txt` (6 unpinned packages) is now an orphaned, contradictory dependency manifest since `pyproject.toml` declares zero deps. Deferred per user decision 2026-08-07: Story 1.5 adds `pandas`/`duckdb`/`kagglehub` as real `pyproject.toml` dependencies (confirmed in epics.md), making `requirements.txt` naturally redundant then; reconcile/remove it as part of that story rather than now. [requirements.txt]

## Deferred from: code review of story-1.5 (2026-08-07)

- `add_standing_rank()` produces dense ranks (1,2,2,3) rather than standard competition ranks (1,2,2,4) after a tie — verified against the real dataset (1956 round 4). Byte-identical to the salvaged reference this story was directed to adapt from, not redesign; a future story should decide the intended ranking convention for per-round standings questions and, if standard ranking is wanted, fix it in the one shared function. [src/f1_analytics/data_sources/standings.py:24-29]
- Tie-detection (`group.ne(group.shift())`) in `add_standing_rank()` is not NaN-safe (`NaN != NaN` in pandas). Not triggered by any real or fixture data today; identical to reference. [src/f1_analytics/data_sources/standings.py:25-26]
- `write_dataframe()` leaves `source_df` registered on the connection if `conn.execute` raises (no `try`/`finally`). Identical to reference. [src/f1_analytics/database/duckdb_io.py:28-30]
- `write_dataframe()` interpolates `table_name` unescaped into raw SQL with no identifier quoting. Not reachable today (every call site passes a hardcoded literal); identical to reference. [src/f1_analytics/database/duckdb_io.py:29]
- Constructor name→id reconciliation (`drop_duplicates(subset=["constructor"])`) would silently keep the first-seen id if one free-text `constructor` name were ever bound to two different `constructor_id`s. Verified zero such collisions in the real dataset today; identical to reference. Hard validation of reconciliation edge cases is explicitly Story 1.8's territory. [src/f1_analytics/data_sources/kaggle_csv.py:82-93]
- No column-presence validation for malformed CSVs and no merge-fanout guard against duplicate `(season, round)` rows in `races.csv`. Identical to reference; explicitly assigned to Story 1.8 ("Advisory Build Validation, Logged"). [src/f1_analytics/data_sources/kaggle_csv.py]
- `connect_duckdb()` binds `DUCKDB_PATH` as a mutable default parameter at import time, so patching the config constant after import has no effect on callers relying on the default. Identical to reference. [src/f1_analytics/database/duckdb_io.py:13-14]
