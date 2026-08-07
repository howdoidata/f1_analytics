---
title: 'Story 1.6: FastF1 Facts Landed With Rate Discipline'
type: 'feature'
created: '2026-08-07'
baseline_revision: 'f02dcb7b71610a75005a80cc6fa1536ffd42e139'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md'
warnings: ['oversized']
deferred:
  - summary: >-
      Full-table replace-sync in pull_fastf1_data.py can regress (drop previously-landed
      races) if a later run lands fewer races than an earlier one.
    evidence: |-
      main() writes raw_fastf1_laps/stints/weather via CREATE OR REPLACE TABLE sourced
      only from the current run's in-memory laps_frames/stints_frames/weather_frames,
      never merged against what's already in the database. If a race that landed on a
      prior run fails on a later run for any transient reason, its previously-verified
      rows vanish from the table on that run's write, violating AD-13's "never a
      shorter table" across separate invocations (not just within one race's fetch).
      Doesn't manifest under this story's own deterministic usage (Barcelona fails
      deterministically until its 2026 session date arrives; the other four succeed
      deterministically once cached), but is a real structural gap. Fixing it needs new
      merge/upsert-by-race-label write semantics in database/duckdb_io.py, which is
      AD-4-governed (write-pattern split enforced at the storage edge) and bigger than
      a same-pass patch.
    location: >-
      scripts/pull_fastf1_data.py:main
    severity: medium
  - summary: >-
      TARGETS (the five target races) is duplicated rather than imported between
      spike_fastf1_adoption.py and pull_fastf1_data.py.
    evidence: |-
      Two independent literal copies of the same race-label/event tuple exist, which
      can silently drift. Importing from spike_fastf1_adoption.py was rejected as the
      fix because that script is explicitly documented as a throwaway spike, not an
      importable module — coupling production code to it would be worse than the
      duplication, and its own docstring says so. Left as-is with the existing comment
      crediting the source.
    location: >-
      scripts/pull_fastf1_data.py:38-44
    severity: low
  - summary: >-
      run_fetch_subprocess() would crash with AttributeError if the fetch
      subprocess's stdout decoded as valid JSON that isn't a dict.
    evidence: |-
      result.get("status") assumes result is always a dict. fetch_race() (the only
      thing that prints to that stdout) always returns/prints a dict today, so this
      isn't demonstrated as reachable — flagged by the edge-case-hunter review layer
      as a defensive hardening opportunity, not a confirmed live defect.
    location: >-
      scripts/pull_fastf1_data.py:run_fetch_subprocess
    severity: low
---

<intent-contract>

## Intent

**Problem:** Lap timing, tyre/stint, and weather facts for the five target 2026 races have no verified local source — Epic 2's lap/tyre questions (Q01, Q04, Q05) have nothing to extract from, and FastF1's only prior use was the throwaway adoption spike (1.2).

**Approach:** A two-phase `scripts/pull_fastf1_data.py`: an isolated pandas-<3.0 subprocess fetches+caches each race's FastF1 session and dumps plain CSVs; the main pandas-3.0 environment reads those CSVs, maps every row to the shared `driver_id`/`constructor_id` space, verifies completeness, and lands `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather` via the existing replace-sync writer.

## Boundaries & Constraints

**Always:**
- FastF1's mandatory cache at `data/raw/fastf1_cache/` is enabled before every session load; a second run against an already-cached race shows zero fresh HTTP requests (AD-13).
- Every lap/stint row is mapped to `driver_id`/`constructor_id` by name (never `DriverNumber`/car number) against the curated `drivers`/`constructors` tables Story 1.5 already landed (AD-14); an unresolved name raises a named error naming the exact unmatched FastF1 string.
- Each of the five target races (Melbourne, Miami, Canada, Barcelona, Silverstone — `spike_fastf1_adoption.py`'s already-verified `TARGETS`) is attempted independently: one race's failure never aborts the others, and a race that DOES load is verified against its own session lap/driver totals before being accepted (never a silently shorter table).
- Rate/retry constants (backoff base, retry cap) live as named values beside the fetch client; a `RateLimitExceededError` or request failure retries with bounded exponential backoff, then becomes a statused failure — never a silent skip, never a hot loop (AD-13).
- `database/duckdb_io.write_dataframe()` stays the only writer used; the isolated fetch subprocess never opens DuckDB (`database/` stays the sole connection-opening module).

**Block If:** none — FastF1 needs no credential, and the isolated-environment approach is fixed by the 1.2 decision record.

**Never:**
- Never relax the project's `pandas>=3.0,<3.1` baseline to accommodate FastF1 — the decision record's fallback is an isolated subprocess environment, not a project-wide downgrade.
- Never treat Barcelona's still-future 2026 session as a bug to route around — an empty/`DataNotLoadedError` outcome for it is an expected, statused, non-fatal failure this run (re-verifying it is explicit 1.2 follow-up work, not this story's).
- Never build `source_registry`/`source_load_log`/`validation_results` writes (Story 1.8) or Jolpica gap-fill (Story 1.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | 5 target races, empty FastF1 cache | `raw_fastf1_laps/stints/weather` populated for every race that loads, all rows id-mapped | No error expected |
| Cache replay | Same races, cache already populated | Identical landed row counts; 0 fresh HTTP requests | No error expected |
| Future/unavailable session | Barcelona 2026 (not yet run) | Barcelona absent from the three tables; run names its failure explicitly; the other four still land | Statused failure logged, run continues |
| Transient rate/5xx failure | Fetch raises `RateLimitExceededError` or a request error | Bounded exponential backoff up to the named retry cap | Cap exhaustion -> statused failure for that race, never a hot loop |
| Unmapped driver/team name | A FastF1 `Driver`/`Team` string has no curated-table match | Named error identifying the exact unresolved string | Raises; never guesses or silently drops the row |
| Incomplete lap count | Session loads but its landed rows undercount its own session totals | Detected against that session's own count | Statused failure for that race, never accepted as a shorter table |

</intent-contract>

## Code Map

- `scripts/spike_fastf1_adoption.py` -- proven isolated-subprocess pattern to reuse verbatim: `TARGETS` tuple, cache-enable-before-load order, `uv run --isolated --python 3.13 --with fastf1==3.8.3 python ...` (fastf1 pins `pandas>=2.1.1,<3.0.0`, so the resolver lands on a compatible pandas without forcing a version)
- `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` -- verified evidence this story must account for: pandas-3 resolver conflict, Barcelona's still-future session, per-race lap/stint/weather counts already observed live
- `src/f1_analytics/config.py` -- add the FastF1 cache dir (`data/raw/fastf1_cache/`, already used by the spike) and a raw-intermediate-CSV dir constant here, beside existing `DUCKDB_PATH`/`RAW_DATA_DIR`
- `src/f1_analytics/database/duckdb_io.py:connect_duckdb,write_dataframe` -- the only writer this story's main-env loader may call; open a `read_only=True` connection to read curated `drivers`/`constructors` for name mapping
- `src/f1_analytics/data_sources/kaggle_csv.py:82-94` -- the established free-text-name -> id reconciliation pattern (`drop_duplicates` + `.map()`) to mirror for FastF1 driver/team name mapping
- `tests/conftest.py` -- autouse fixture blocks all sockets in tests; every loader/mapping/derivation function must be testable against small fixture CSVs with zero network (AD-11)

## Tasks & Acceptance

**Execution:**
- `src/f1_analytics/data_sources/fastf1_fetch.py` -- NEW: isolated-env-only module (stdlib + fastf1 + pandas, no `f1_analytics`-internal imports) that enables the mandatory cache, loads one race's session (laps + weather), retries rate/request failures with named bounded-backoff constants, and dumps `laps.csv`/`weather.csv` plus a small counts sidecar (the session's own total lap count and driver roster) per race under `data/raw/fastf1/<race_label>/` -- this is the isolated-subprocess half of the pull
- `src/f1_analytics/data_sources/fastf1_loader.py` -- NEW: main-env module reading the dumped per-race CSVs, mapping `Driver`/`Team` strings to `driver_id`/`constructor_id` via curated `drivers`/`constructors` (named error on an unresolved name), deriving `raw_fastf1_stints` from the laps rows (grouped by driver + stint number, one row per stint with compound/lap_start/lap_end), and verifying each race's landed counts against its counts sidecar -- the offline-testable half; no `fastf1` import here
- `scripts/pull_fastf1_data.py` -- NEW: thin orchestration entry point; for each of the five target races, subprocess-invokes `fastf1_fetch.py` in the isolated environment, then calls `fastf1_loader.py` to build the three DataFrames and writes them via `duckdb_io.write_dataframe()`; one race's fetch/mapping failure is caught, reported by name, and never stops the remaining races
- `tests/fixtures/fastf1_csv/` -- NEW: small synthetic per-race laps/weather CSVs (matching the fetch step's dumped shape) covering a normal race, an unmapped driver name, and a lap count short of its counts sidecar
- `tests/test_fastf1_loader.py` -- NEW: offline tests for name mapping (incl. the unmapped-name error), stint derivation from laps, and completeness verification against the counts sidecar
- `tests/test_pull_fastf1_data.py` -- NEW: offline test driving the per-race orchestration loop against fixture CSVs (the isolated-subprocess call is a seam, monkeypatched), asserting one race's simulated failure doesn't stop the others

**Acceptance Criteria:**
- Given the five target 2026 races and an empty FastF1 cache, when `uv run scripts/pull_fastf1_data.py` runs, then `raw_fastf1_laps`, `raw_fastf1_stints`, and `raw_fastf1_weather` exist in `data/processed/f1_analytics.duckdb` via `write_dataframe`, every row carries `driver_id`/`constructor_id`, and each landed race's counts are verified against that session's own totals
- Given the same command run a second time with the cache now populated, when it completes, then the FastF1 HTTP cache shows zero fresh network requests for every previously-loaded race
- Given Barcelona's 2026 session is not yet available, when the script runs, then Barcelona is absent from the three tables, its failure is named explicitly in the run's output, and the other four races still land
- Given a fetch call exhausts its retry cap on a rate/request error, when the run continues, then that race is recorded as a statused failure and the script proceeds to the next race rather than crashing or looping

## Spec Change Log

## Review Triage Log

### 2026-08-07 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 12 (high 7, medium 3, low 2)
- defer: 3 (medium 1, low 2)
- reject: 0
- addressed_findings:
  - `[high]` `[patch]` `verify_completeness()` compared landed rows only against a `counts.json` sidecar derived from the exact same in-memory `laps`/`weather` objects `fetch_race()` also dumped to CSV — tautological, could never catch real FastF1-side truncation. Fixed: `fetch_race()` now sources expected lap/driver counts from `session.results` (an independent FastF1 endpoint), not `session.laps`. Live-verified the sidecar now genuinely differs from the raw CSV row count for all four landed races.
  - `[medium]` `[patch]` `verify_completeness()` never checked landed weather rows against the sidecar's `weather_count`. Added.
  - `[high]` `[patch]` A 0-row (non-`None`) weather DataFrame was accepted as `status: "pass"`, contradicting the code's own comment that weather is required for the happy path. Fixed: `fetch_race()` now treats `None` or empty weather identically as a statused failure.
  - `[high]` `[patch]` `fetch_race()`'s own branches (empty session, missing/empty weather, CSV dump) had zero test coverage, including the exact weather-`None`-shape bug already fixed once this story. Added an injectable-`fastf1`-module seam and 4 new offline tests covering pass/weather-None/weather-empty/empty-session.
  - `[high]` `[patch]` `map_driver_ids()` silently produced a null `driver_id` for a NaN `Driver` value instead of raising (the `.notna()` guard excluded NaN rows from the unresolved check). Fixed to raise `UnmappedFastF1NameError` naming a missing value distinctly.
  - `[high]` `[patch]` `map_constructor_ids()` had the identical NaN-`Team` bug, including in the alias-fallback path. Fixed.
  - `[low]` `[patch]` `pull_race()`'s `status: "empty"` case dumped the raw fetch-result dict into `detail` instead of a clean message. Fixed with a dedicated message.
  - `[medium]` `[patch]` `raw_fastf1_laps`/`stints`/`weather` carried no `round` column (only `race_label`/`season`), leaving Story 1.7/Epic 2 to re-derive a label→round mapping FastF1 already reports directly (`session.event["RoundNumber"]`). Added.
  - `[high]` `[patch]` `load_and_map_race()`'s except clause only caught 3 named exception types; a corrupt `counts.json` or malformed CSV would escape unwrapped and crash the whole run instead of being isolated to one race. Broadened to `except Exception`.
  - `[high]` `[patch]` Only 1 of the 4 sanctioned FastF1→constructor aliases (`Red Bull Racing`) was actually exercised via the alias-fallback code path — the shared test fixture's simplified constructor names masked `Alpine`/`Cadillac`/`Racing Bulls`. Added a dedicated test against the real curated names from the decision record's evidence table, asserting all 4.
  - `[low]` `[patch]` `epic-1-context.md` was stale relative to the new constructor-reconciliation decision record. Recompiled (twice — the first recompile was inadvertently deleted mid-review by the same patch pass; recreated).
  - `[medium]` `[patch]` No named precondition error when curated `drivers`/`constructors` tables don't exist (raw DuckDB exception instead), unlike Story 1.5's `require_raw_files()` precedent. Added `require_curated_tables()`.
  - `[medium]` `[defer]` Full-table replace-sync can regress (drop previously-landed races) if a later run lands fewer races than an earlier one — real, but fixing it needs new merge/write semantics in `database/duckdb_io.py` (AD-4-governed, bigger than a same-pass patch) and doesn't manifest under this story's own deterministic usage (Barcelona fails deterministically until its date arrives; the other four succeed deterministically once cached). Flagged for a Story 1.7/1.8 follow-up.
  - `[low]` `[defer]` `TARGETS` is duplicated (not imported) between `spike_fastf1_adoption.py` and `pull_fastf1_data.py` — importing from a script explicitly documented as a throwaway spike would be worse coupling than the existing sourcing comment; left as-is.
  - `[low]` `[defer]` The fetch subprocess's stdout decoding to valid-but-non-dict JSON would crash with `AttributeError` — plausible but not demonstrated reachable (`fetch_race()` always returns a dict); not urgent.

## Design Notes

Two-phase split mirrors `spike_fastf1_adoption.py`'s already-proven isolated-subprocess pattern. `fastf1_fetch.py` runs only inside `uv run --isolated --python 3.13 --with fastf1==3.8.3 python ...` and never touches DuckDB, so `database/` stays the sole DuckDB-opening module (spine rule) — the isolated process can only hand off plain CSVs. `fastf1_loader.py` and the DuckDB write both run in the normal project environment, so every mapping/derivation/verification function is unit-testable offline against fixture CSVs with no `fastf1` import and no subprocess; only `pull_fastf1_data.py`'s live orchestration needs a manual run, same as Story 1.5's real-dataset verification step.

## Verification

**Commands:**
- `uv run pytest -v` -- expected: full suite green, offline, no network calls
- `uv run scripts/pull_fastf1_data.py` (manual, live) -- expected: 4/5 races land with mapped ids and verified counts; Barcelona reported as a named, non-fatal failure
- Immediate re-run of the same command -- expected: 0 fresh FastF1 HTTP requests logged for the four already-cached races

## Auto Run Result

Status: done

**Summary:** Lands `raw_fastf1_laps`, `raw_fastf1_stints`, and `raw_fastf1_weather` for the five target 2026 races via a two-phase pull: an isolated `pandas<3.0` subprocess (`fastf1_fetch.py`) fetches+caches each race and dumps plain CSVs plus an independently-sourced `counts.json`; the main `pandas 3.0` environment (`fastf1_loader.py`) reads those CSVs, maps every row to `driver_id`/`constructor_id`/`round` by name (never car number), verifies completeness against the session's own independent totals, derives stints, and lands the three tables via the existing `duckdb_io.write_dataframe()` writer. `scripts/pull_fastf1_data.py` orchestrates all five races independently, so one race's failure never aborts the others.

Mid-story, the live run surfaced a real blocker: FastF1's 2026 `Team` strings for 4 of 11 teams (`Alpine`, `Cadillac`, `Racing Bulls`, `Red Bull Racing`) don't exactly match Story 1.5's curated Kaggle `constructors.name` values. Per AD-14 this required a new decision record before a second name→id reconciliation could be added; the project owner authorized a 4-entry static alias table in-session, which is now recorded at `_bmad-output/planning-artifacts/decisions/fastf1-constructor-name-reconciliation-decision-record.md` and implemented with a fixed exact-match → alias-table → named-error resolution order (never fuzzy matching).

**Files changed:**
- `src/f1_analytics/config.py` — added `FASTF1_CACHE_DIR`, `FASTF1_RAW_DIR`
- `src/f1_analytics/data_sources/fastf1_fetch.py` (new) — isolated-env fetch worker: mandatory cache, bounded-backoff retry (`retry_with_backoff`, dependency-injection-tested), independent completeness sidecar sourced from `session.results`/`session.event`, statused failure on empty/missing weather or empty session
- `src/f1_analytics/data_sources/fastf1_loader.py` (new) — main-env id-mapping (driver by code, constructor by name+alias table), stint derivation, completeness verification, `round`-tagged output; no `fastf1` import
- `scripts/pull_fastf1_data.py` (new) — per-race orchestration, named precondition check for missing curated tables, never crashes the run on one race's failure
- `tests/fixtures/fastf1_csv/*`, `tests/test_fastf1_fetch.py`, `tests/test_fastf1_loader.py`, `tests/test_pull_fastf1_data.py` (new, 27 tests total)
- `_bmad-output/planning-artifacts/decisions/fastf1-constructor-name-reconciliation-decision-record.md` (new) — the AD-14 exception decision, with an explicit in-session authorization note
- `_bmad-output/implementation-artifacts/epic-1-context.md` (regenerated) — now reflects both AD-14 reconciliations

**Review findings breakdown:** 4 layers (blind-hunter, edge-case-hunter, verification-gap, intent-alignment) run over the full diff since baseline. 12 patches applied (7 high, 3 medium, 2 low — see Review Triage Log for the full list, covering a tautological completeness check, silently-dropped NaN driver/team rows, an untested weather-None regression, an over-narrow exception boundary that could crash the whole run, and under-tested constructor aliases, among others). 3 findings deferred (1 medium, 2 low — a full-table-replace regression risk across separate runs, a duplicated `TARGETS` constant, and a non-dict-JSON edge case). 0 rejected, 0 intent gaps, 0 bad-spec loopbacks.

**Follow-up review recommendation:** `true` — this pass patched 7 high-severity findings.

**Verification performed:**
- `uv run pytest -v`: 55/55 passed, fully offline, no network calls (independently re-confirmed).
- Live `uv run scripts/pull_fastf1_data.py`: Melbourne (1006 laps), Miami (1040), Canada (1211), Silverstone (1113) all land with zero null `driver_id`/`constructor_id`/`round`; Barcelona is the one clean, non-fatal `DataNotLoadedError` at the fetch stage (its 2026 session hasn't run yet, per the 1.2 decision record).
- Immediate re-run: identical outcome; per-endpoint cache logging confirmed zero fresh FastF1 HTTP requests for all four landed races.
- Live-verified the completeness check is now genuinely independent: each race's `counts.json` lap count (e.g. Melbourne 1003) now differs from its raw landed lap count (1006), proving it no longer just compares data against itself.

**Residual risks:** the 3 deferred items above (see `deferred` frontmatter and Review Triage Log for full evidence). Most notable: a later run that lands fewer races than an earlier one would shrink the DuckDB tables rather than merge, since the write is a full replace-sync sourced only from that run's in-memory results — not triggered by this story's own normal usage, but worth resolving before Story 1.7/1.8 build further on this write pattern.
