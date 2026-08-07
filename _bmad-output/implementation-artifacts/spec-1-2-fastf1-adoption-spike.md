---
title: 'FastF1 adoption spike'
type: 'feature'
created: '2026-08-06T00:00:00-05:00'
status: 'awaiting-operator'
operator_actions:
  - 'Refresh or authorize the Kaggle API credential for patelris/formula-1-complete-dataset-1950-2026, then rerun the named spike.'
  - 'Rerun the named spike after the 2026 Barcelona race has occurred to capture its FastF1 session evidence.'
baseline_revision: '1db1beb16693a21f7bf9b26b0f07bfd465dc8d03'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/PROJECT.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/1-2-fastf1-adoption-spike.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** FastF1 is the planned source for lap timing, tyre/stint, and weather facts, but its pandas-3 compatibility, 2026 target-race availability, cache replay, and Kaggle re-download access have not been verified in this rebuilt repository.

**Approach:** Add one named, runnable live-evidence script and a durable PRD §9 decision record. Run the bounded spike honestly, then select and record the required adoption fallback if an adoption leg fails.

## Boundaries & Constraints

**Always:** Use public FastF1 APIs only; enable the managed cache at `data/raw/fastf1_cache/` before every FastF1 load; make resolved versions, targets, results, exceptions, and cache status observable; keep live networking solely in this named script; record command and validation evidence in the existing story artifact. The decision record must contain exactly the five PRD §9 decision fields: access model, cost, license/terms risk, authentication, and maintenance burden.

**Block If:** The repository no longer has a usable scratch Python environment, access to the documented Kaggle credential cannot be tested, or the live service prevents a required leg after the script reports its named failure. If Kaggle credential creation is the only remaining outside-repository action, finish all other work and use `awaiting-operator` with non-empty imperative `operator_actions`, rather than `blocked`.

**Never:** Do not force FastF1 to install with pandas 3 and call it compatible; do not create production loaders, DuckDB tables, package configuration, tests, fixtures, retry loops, or ID mapping; do not change `requirements.txt`; do not commit cache/download payloads; do not call FastF1 private APIs; do not make a second live request loop for cache testing.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Compatibility gate | Scratch resolver requests Python 3.13, `pandas==3.0.x`, `fastf1==3.8.x` | Emit resolved versions and pass/fail with raw resolver/import surface | Preserve conflict verbatim; select an explicit fallback, never force-install |
| Exploratory source leg | Compatible FastF1 environment and each of five 2026 race selectors | Cache enabled then one live load per selector; emit metadata plus laps, stints/compounds, weather, and quality-flag counts | Record a named per-race failure and continue only where safe; no hot retries |
| Cache replay | Live cache populated | Offline-mode single replay of all five sessions with no fresh request | Record replay exception/missing cache as a failure; restore online mode |
| Kaggle redownload | Private `~/.kaggle/access_token` and disposable destination | Record KaggleHub version and availability for the named dataset | Report absent credential/access/download failure; never commit the token or payload |

</intent-contract>

## Code Map

- `scripts/spike_fastf1_adoption.py` -- new standalone, bounded live-evidence entry point.
- `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` -- durable source decision and execution evidence.
- `_bmad-output/implementation-artifacts/1-2-fastf1-adoption-spike.md` -- existing Dev Agent Record for commands, results, deviations, and file list.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- lifecycle state for this story.
- `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` -- amend only if selecting the pandas-<3 pin fallback.

## Tasks & Acceptance

**Execution:**

- [x] `scripts/spike_fastf1_adoption.py` -- create the single live spike with explicit preflight, machine-readable/visible evidence, scratch pandas-3 resolver/import probe, compatible-environment exploratory loads, offline cache replay, and disposable Kaggle re-download -- establishes reproducible evidence without becoming production ingestion.
- [x] `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` -- record timestamp, exact commands, versions, raw exceptions, cache result, five-race × fact-class matrix, Kaggle outcome, all five PRD §9 fields, and an explicit adoption/fallback decision -- closes the source gate even on a failed leg.
- [x] `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` -- amend the FastF1 environment expectation and cite the decision record only if the chosen fallback is a pandas pin below 3.0 -- keeps the architecture truthful.
- [x] `_bmad-output/implementation-artifacts/1-2-fastf1-adoption-spike.md`, `_bmad-output/implementation-artifacts/sprint-status.yaml` -- move lifecycle state and append the actual commands, results, deviations, validation, and file list -- preserves durable run evidence.

**Acceptance Criteria:**

- Given Python 3.13, pandas 3.0.x, and FastF1 3.8.x are requested in a scratch environment, when the named script runs, then it records the exact compatibility outcome and failing surface, each target race's session/lap/stint/weather presence, and Kaggle dataset re-download availability.
- Given a compatible exploratory FastF1 environment is selected, when it loads Melbourne, Miami, Canada, Barcelona, and Silverstone race sessions, then cache is enabled before each load; lap and quality-flag counts, compound/stint counts derived from laps, and weather counts are recorded; one offline replay reports all five results without another live loop.
- Given any adoption leg fails, when the decision record is finalized, then it names either the pandas-<3 spine-amendment path or the alternate historical-source path and never represents forced installation as compatibility.
- Given the source decision is finalized, when it is inspected, then it contains the five required PRD §9 fields, source roles, costs/terms/authentication/maintenance evidence, cache location/result, raw exception summaries, and the runnable script command.

## Spec Change Log

- 2026-08-06: Completed all agent-executable Story 1.2 work. Set `awaiting-operator` because Kaggle re-download access requires an operator refresh/authorization and Barcelona's 2026 race was still future-dated at the evidence run.

## Review Triage Log

## Design Notes

The expected `fastf1==3.8.3` dependency metadata excludes pandas 3.0. The script therefore separates the required compatibility gate from evidence-only exploration in an explicitly selected compatible environment; a successful exploratory load does not change the compatibility result.

Race labels remain human-readable in the output while mapping to FastF1's public event selectors. Stint and compound evidence comes from the loaded laps table, so the record distinguishes missing columns from zero usable values. Kaggle is tested in a temporary destination and remains authoritative only for the curated facts it covers, not as current-season truth.

## Verification

**Commands:**

- `python3 scripts/spike_fastf1_adoption.py` -- expected: emits a complete result document or named outcome for every adoption leg.
- `rg -n 'access model|cost|license/terms risk|authentication|maintenance burden' _bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` -- expected: exactly the five PRD §9 field headings are present.
- `git diff --check` -- expected: exits zero after script and documentation edits.
