# Story 1.2: FastF1 Adoption Spike

Status: in-progress

## Story

As the ingestion epic's owner,
I want FastF1's three adoption legs verified against reality,
so that AD-6's source-role binding rests on evidence rather than documentation.

## Acceptance Criteria

1. **Given** a scratch environment with Python 3.13, pandas 3.0.x, and FastF1 3.8.x, **when** session, lap, and stint data are loaded for the 2026 Melbourne, Miami, Canada, Barcelona, and Silverstone races with the cache enabled, **then** a PRD §9 source-decision record records the pandas-3 compatibility result (pass/fail and the exact failing surface), per-race data presence for every fact class, and Kaggle dataset re-download availability.
2. **And given** any adoption leg fails, **when** the decision record is finalized, **then** it names the fallback taken: a pandas pin below 3.0 with an Architecture Spine amendment, or an alternate historical source. A failed spike is successful only when the complete decision is recorded.
3. **And** the decision record includes the PRD §9 fields—access model, cost, license/terms risk, authentication, and maintenance burden—and a named runnable spike script is committed. The script must make its cache location, runtime versions, target races, and each result observable.

## Tasks / Subtasks

- [ ] Create a narrow, named live-adoption spike. (AC: 1, 3)
  - [ ] Add `scripts/spike_fastf1_adoption.py` (or an equally explicit snake_case name) as a standalone evidence script; do not create a production loader or DuckDB tables.
  - [ ] Preflight Python, pandas, FastF1, cache-directory, and Kaggle credential requirements. Report a named failure and stop the affected leg; never report an unverified partial result as a pass.
  - [ ] Pin or otherwise print the exact resolved Python, pandas, FastF1, and KaggleHub versions in the output and decision record.
  - [ ] Enable FastF1's managed cache at `data/raw/fastf1_cache/` before every FastF1 load. Do not disable it and do not commit cache payloads.
- [ ] Exercise the three adoption legs and preserve evidence. (AC: 1)
  - [ ] First test whether the declared Python 3.13 + pandas 3.0.x + FastF1 3.8.x environment resolves and imports. Capture the resolver/import failure surface verbatim if it does not.
  - [ ] Only if a compatible FastF1 environment is explicitly selected for exploratory data presence, load Race sessions for Melbourne, Miami, Canada, Barcelona, and Silverstone with `Session.load(laps=True, telemetry=False, weather=True, messages=False)`.
  - [ ] For each race, record session metadata, lap presence/count, stint/compound presence/count derived from laps, and weather presence/count. Preserve counts of `FastF1Generated` and `IsAccurate` laps; neither flag is proof that the fact class is absent or fully reliable.
  - [ ] Run a cache-replay check using FastF1 offline mode after the cache is populated. Record whether the five sessions replay without fresh network requests; do not make a second live request loop merely to test the cache.
  - [ ] Test Kaggle re-download availability for `patelris/formula-1-complete-dataset-1950-2026` using the documented local Kaggle credential and a disposable destination. Record availability and any credential/access failure; do not treat a downloaded dataset as current-season truth.
- [ ] Record and close the source decision. (AC: 1, 2, 3)
  - [ ] Add `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` with the exact commands, timestamp, environment, cache result, five-race × fact-class matrix, Kaggle outcome, and raw exception summaries.
  - [ ] Record all five PRD §9 decision fields: access model, cost, license/terms risk, authentication, and maintenance burden.
  - [ ] State an explicit adoption decision. If pandas 3 compatibility fails, do not force-install FastF1 and call it compatible; select and record either the pandas pin/spine-amendment path or the alternate-source path.
  - [ ] Record the script commands and validation results in this story's Dev Agent Record, as required by `AGENTS.md`.

## Dev Notes

### Scope and sequencing

- This is a risk gate whose deliverables are evidence, a runnable live spike, and a durable decision record—not production ingestion. It precedes the project foundation (Story 1.4) and FastF1 landing layer (Story 1.6), so do not fabricate `pyproject.toml`, a package harness, raw tables, fixtures, or pytest coverage here.
- Do not add `raw_fastf1_laps`, `raw_fastf1_stints`, `raw_fastf1_weather`, `src/f1_analytics/data_sources/` loader code, DuckDB writes, retry implementation, or entity mapping. Those are Story 1.6 responsibilities after this decision gate.
- Do not use legacy OpenF1 documentation as a current implementation precedent. The surviving `docs/data_sources.md` account is historical evidence from before the rebuild; AD-10 makes old source modules and prior completion claims reference material, not binding contracts.
- The activation-referenced `_bmad-output/project-context.md` is absent in the rebuilt repository. Treat `PROJECT.md`, the current Architecture Spine, PRD, epics, and this story as the active context.

### Technical requirements and guardrails

- FastF1 3.8.3 is compatible with Python 3.13 but declares `pandas>=2.1.1,<3.0.0`. The required pandas 3.0.x leg is therefore expected to expose a resolver conflict. Record the failure honestly; never bypass dependency resolution or claim forced installation proves compatibility.
- The minimum public API is `fastf1.Cache.enable_cache(...)`, `fastf1.get_session(year, event, "R")`, and `session.load(...)`. Use public FastF1 APIs only; do not call private `fastf1.api` internals.
- Cache-then-parse is mandatory. FastF1's internal limiter may soft-throttle and then raise `RateLimitExceededError`; capture the condition as a failure. Do not add a hot retry loop. Full bounded backoff/retry and completeness enforcement are Story 1.6 work.
- Future production FastF1 records must map at the ingestion boundary to Ergast/Jolpica-style `driver_id` and `constructor_id` by name, never car number. Do not implement that mapping in this spike.
- Live network access belongs only in this explicitly named spike script. Pytest must remain completely offline and use recorded cache fixtures when Story 1.6 adds tests.
- Kaggle is the authoritative curated source for facts it covers. FastF1's prospective role is lap timing, tyre/stint, and weather facts, plus Ergast-compatible Jolpica access; no paid source may be introduced by default.
- Preserve recovery constraints: never run `git gc`, `git prune`, `git repack`, `git restore .`, or `git checkout -- .`.

### Expected project structure

| Path | Action | Purpose |
| --- | --- | --- |
| `scripts/spike_fastf1_adoption.py` | NEW | Explicitly named live evidence script; replace the filename only with an equally clear name. |
| `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` | NEW | Durable source decision, adoption outcome, and all evidence required by PRD §9. |
| `_bmad-output/implementation-artifacts/1-2-fastf1-adoption-spike.md` | UPDATE | Record commands, results, deviations, and final file list. |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | UPDATE | Move this story to `in-progress` when development starts, then `review` when implementation is ready for review. |

Do not modify `requirements.txt` merely to make the project appear pinned: Story 1.4 owns reproducible project packaging. A scratch-specific requirement declaration is acceptable only if it makes the spike command reproducible and the decision record explains why it is not the application dependency contract.

### Validation

- Run the documented live spike command from the repository root. It must either produce the complete evidence matrix or halt with named findings for every failed leg.
- Verify the decision record contains exactly the five PRD §9 fields and the three required adoption outcomes.
- Verify cache replay occurs in offline mode and reports no fresh request attempt.
- Run `git diff --check` after documentation and script edits.
- Do not run pytest as a proxy for this live spike; network access in pytest is prohibited.

### Previous story and Git intelligence

- The only file whose name resembles Story 1.1 is a pre-loss historical artifact for a different deletion-authorization plan. The current sprint tracker explicitly says surviving old story files are historical reference only. Do not reuse its requirements, paths, run-log mutation pattern, or claimed completion.
- The current clean rebuild lineage has the loss-record and Story 1.1 completion commits; it establishes no FastF1 implementation pattern. Follow the final 2026-08-06 Architecture Spine instead.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.2 and Story 1.6]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` — AD-6, AD-10 through AD-14, structural seed]
- [Source: `_bmad-output/planning-artifacts/prds/prd-f1-questions-analysis-2026-07-17/prd.md` — §9 Data Governance and Source Decisions]
- [Source: `docs/data_sources.md` — Kaggle source and historical-source caveat]
- [Source: `docs/local_setup.md` — Kaggle credential setup]
- [Source: FastF1 3.8.3 package metadata](https://pypi.org/pypi/fastf1/3.8.3/json)
- [Source: FastF1 session API](https://docs.fastf1.dev/core.html)
- [Source: FastF1 cache and rate-limit API](https://docs.fastf1.dev/fastf1.html)

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Story context created 2026-08-06 after analysis of the active epics, PRD, Architecture Spine, UX contract, repository state, historical artifacts, recent git history, and FastF1 official documentation.
- Confirmed the active tracker treats old story artifacts as historical only and that no project-level `pyproject.toml`, FastF1 dependency, loader, script directory, or cache directory currently exists.
- Confirmed FastF1 3.8.3 metadata conflicts with the story's pandas 3.0.x compatibility leg (`pandas<3.0.0`); this is a required decision-gate observation, not a reason to force installation.

### Completion Notes List

- Added the bounded live-evidence script `scripts/spike_fastf1_adoption.py`; it uses only public FastF1 APIs, enables `data/raw/fastf1_cache/` before each load, and prints machine-readable evidence.
- Ran `python3 -m py_compile scripts/spike_fastf1_adoption.py` successfully.
- Ran `uv run --isolated --python 3.13 --with pandas==3.0.5 --with fastf1==3.8.3 python -c 'import fastf1, pandas; print(fastf1.__version__, pandas.__version__)'`; the resolver failed honestly because FastF1 3.8.3 declares `pandas>=2.1.1,<3.0.0`.
- Ran the named spike in its compatible FastF1 3.8.3 / pandas 2.3.3 environment. Melbourne, Miami, Canada, and Silverstone loaded and replayed from the managed cache in offline mode. Barcelona resolved to a future 2026-09-13 event and reported `DataNotLoadedError`; no zero facts were fabricated.
- The disposable KaggleHub re-download attempt found a non-empty local credential but failed with `KaggleApiHTTPError: 400 Client Error: Bad Request`; no credential or payload was recorded. This requires a Kaggle operator action before it can be reverified.
- Selected the explicit pandas-<3.0 FastF1 environment fallback and amended the Architecture Spine. The durable decision record contains the five required PRD §9 fields.

### Validation

- `python3 -m py_compile scripts/spike_fastf1_adoption.py` — pass.
- `python3 -m json.tool /tmp/fastf1-adoption-spike-20260806.json` — pass; completed evidence capture is valid JSON.
- `rg -n '^### (access model|cost|license/terms risk|authentication|maintenance burden)$' _bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` — exactly five required headings found.
- `git diff --check` — pass.

### File List

- `_bmad-output/implementation-artifacts/1-2-fastf1-adoption-spike.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md`
- `scripts/spike_fastf1_adoption.py`
