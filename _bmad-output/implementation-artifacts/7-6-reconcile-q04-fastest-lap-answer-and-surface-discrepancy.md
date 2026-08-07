---
story_key: 7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy
story_title: Reconcile Q04 Fastest-Lap Answer And Surface Discrepancy
created: 2026-07-29
source_epic: epic-7
baseline_commit: 64683762b14523109d526be86ef12a909a919a01
working_tree_baseline: "Pre-existing BMAD artifacts for Stories 7.4 and 7.5 were already staged/modified/untracked; this story must preserve them and scope code changes to Q04 workflow-surface wiring."
status: done
---

# Story 7.6: Reconcile Q04 Fastest-Lap Answer And Surface Discrepancy

## Status

done

## Story

As Antonio,
I want Q04's supplied-PDF answer semantics, source-backed extractor evidence, and discrepancy state to be separated explicitly,
so that generated report, portfolio, and insight-package surfaces do not promote either the PDF lap `60` text or the Jolpica lap `58` field as a final answer without the right provenance and validation path.

## Acceptance Criteria

1. Q04 (`2026_pdf_q04_barcelona_sainz_fastest_lap_number`) preserves the PDF answer text as a supplied known-answer/validation example only: `Carlos Sainz clocked his personal fastest lap of the race on Lap 60`.
2. The existing `extract_lap_answer()` behavior is documented but not force-wired into the supplied-PDF workflow bundle by this story: direct extraction may return Jolpica result-level lap `58` with `discrepant_needs_review`, but that value remains source evidence requiring review, not the generated bundle's final answer.
3. The generated analyst workflow surfaces do not say or imply that Q04 has a finalized source-backed answer unless a caller supplies an approved Actual Answer Component or a later live-persistence story wires one through the established target path.
4. The earlier temporary bridge that made Report Summary, Portfolio Summary, and Insight Package render lap `58` is absent from `src/f1_analytics/analysis/question_workflow_surfaces.py` and `tests/test_question_workflow_surfaces.py`.
5. `raw_jolpica_laps` is not used as corroborating Q04 evidence until Jolpica pagination is fixed, the data is repulled, and ingestion completeness is validated against `MRData.total`.
6. The durable follow-up for Jolpica pagination is recorded outside this story file, so the ingestion defect is visible in sprint tracking and not buried in Dev Agent notes.
7. Targeted tests pass after the rollback, `git diff --check` passes, and validation commands/results are recorded here.

## Tasks

- [x] Confirm current Q04 extractor output against local DuckDB source tables.
- [x] Replace the incorrect source-backed Q04 premise with a PDF-intake-semantics correction in this story and Epic 7.6.
- [x] Roll back Q04 actual-answer extraction from the supplied-PDF workflow bundle.
- [x] Roll back focused regression tests that encoded the incorrect Q04 source-backed premise.
- [x] Re-run targeted tests after rollback.
- [x] Surface the Jolpica pagination defect as an open sprint action item.
- [x] Update this story's Dev Agent Record with the premise correction and next action.

### Review Findings

- [x] [Review][Patch] Canonical Q04 catalog still stores a paraphrase instead of the supplied PDF answer text [src/f1_analytics/analysis/question_catalog.py:626]
- [x] [Review][Patch] Post-rollback output validation does not prove regenerated surfaces stopped rendering Q04 lap 58 [_bmad-output/implementation-artifacts/7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md:91]
- [x] [Review][Patch] Sprint tracking still says Q04 has no source data because Barcelona had not run [_bmad-output/implementation-artifacts/sprint-status.yaml:101]
- [x] [Review][Patch] Jolpica pagination finding cites an uncaptured web check instead of a reproducible source or command [_bmad-output/implementation-artifacts/7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md:100]
- [x] [Review][Patch] Review notes still say review stopped even though the story is marked ready for review [_bmad-output/implementation-artifacts/7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md:108]
- [x] [Review][Defer] Story 7.5 has a response note while its lifecycle and delivery evidence remain incomplete [_bmad-output/implementation-artifacts/7-5-provide-q05-context-discrepancy-followup-to-gatherer.md:16] — deferred, pre-existing
- [x] [Review][Defer] Q05 Board-intake packet gives contradictory OpenF1 starting-tyre source labels [_bmad-output/planning-artifacts/cross-repo-notes/f1-board-intake-q05-2026-07-28.md:68] — deferred, pre-existing

## Dev Notes

- Primary module: `src/f1_analytics/analysis/question_workflow_surfaces.py`.
- Existing extractor: `src/f1_analytics/analysis/question_lap_answers.py::extract_lap_answer`.
- Existing answer contract: `src/f1_analytics/analysis/question_answers.py::ActualAnswerComponent`.
- Primary tests: `tests/test_question_workflow_surfaces.py`.
- Generated outputs under `outputs/` are working artifacts and remain gitignored.
- Stale generated-output warning: any `outputs/reports/question_workflow_surfaces.md` or `outputs/tables/question_workflow_surfaces.csv` content showing Q04 lap `58` may have been produced while the temporary bridge existed. Regenerate the surfaces or ignore those generated files; source code and tests are the authority for whether the bridge remains.
- This is not the full Epic 5 append-only persistence/live-wiring story; do not add DuckDB target-store tables here.
- Architecture guardrail: `ARCHITECTURE-SPINE.md` AD-4 says PDF known answers are validation examples; source-backed disagreement becomes `discrepant_needs_review` and must preserve both values with citations rather than auto-resolving either way.
- External API guardrail: Jolpica documents shared `limit`/`offset` pagination with max `limit=100` and `MRData.total`; the current loader's one-page fetch is insufficient for lap endpoints whose totals exceed 100.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- Pre-existing working tree had Story 7.4/7.5 BMAD artifacts staged/modified/untracked before this story started.

### Completion Notes

- Correction during review: Antonio challenged the premise that Q04 should be answered by treating DuckDB/Jolpica as authority over the PDF answer text.
- Direct `pdftotext` extraction from `external/f1-questions/Gmail - 2026 F1 Questions.pdf` confirms the PDF itself states Q04's supplied answer text as `Carlos Sainz clocked his personal fastest lap of the race on Lap 60`.
- The earlier Q04 source-backed bridge was rolled back from `question_workflow_surfaces.py` and `tests/test_question_workflow_surfaces.py`.
- The story and Epic 7.6 acceptance criteria were corrected so future implementation does not reintroduce the stale lap `58` surface bridge.
- A Jolpica pagination follow-up was surfaced in `sprint-status.yaml` action items because lap-source completeness is an ingestion concern, not only a Q04 reporting concern.
- Completion gates were rerun on 2026-07-29; targeted workflow-surface tests, the full regression suite, and `git diff --check` passed before moving the story to review.
- Code-review patches on 2026-07-29 updated the canonical Q04 catalog known-answer example to the exact PDF wording, regenerated workflow surfaces, confirmed the stale lap `58` final answer no longer appears in generated report/CSV outputs, corrected stale sprint-status wording, and replaced the uncaptured Jolpica web-check note with a reproducible official documentation URL.

### File List

- `_bmad-output/implementation-artifacts/7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/planning-artifacts/epics.md`
- `src/f1_analytics/analysis/question_catalog.py`

### Change Log

- 2026-07-29: Created Story 7.6 and registered it in Epic 7 sprint status.
- 2026-07-29: Rolled back the Q04 source-backed bridge after the PDF-answer premise was challenged; story remains in progress pending intake-semantics correction.
- 2026-07-29: Corrected Story 7.6 and Epic 7.6 context to preserve PDF-intake semantics and record Jolpica pagination as an open follow-up.
- 2026-07-29: Resolved code-review findings, regenerated workflow surfaces after the catalog correction, and moved story status to done.

### Command Log

- `PYTHONPATH=src python3 - <<'PY' ... extract_lap_answer(q04, combined, raw_results, raw_laps) ... PY` -> exit 0; Q04 status `discrepant_needs_review`, display `Carlos Sainz personal fastest lap on lap 58`, source `raw_jolpica_results`; Arrow emitted sandbox `sysctlbyname` warnings.
- `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces` -> exit 0; 91 tests OK.
- `PYTHONPATH=src python3 -m unittest discover -s tests` -> exit 0; 383 tests OK; Arrow emitted sandbox `sysctlbyname` warnings and expected daily-pipeline failure-path fixture output.
- `PYTHONPATH=src python3 scripts/build_question_workflow_surfaces.py` -> exit 0; regenerated `outputs/reports/question_workflow_surfaces.md` and `outputs/tables/question_workflow_surfaces.csv`; Arrow emitted sandbox `sysctlbyname` warnings.
- `rg -n "2026_pdf_q04_barcelona_sainz_fastest_lap_number|Carlos Sainz personal fastest lap on lap 58|discrepant_needs_review|validation_blocked" outputs/reports/question_workflow_surfaces.md` -> exit 0; Q04 report, portfolio, and insight-package sections show lap 58, discrepancy status, and validation-blocked analysis status.
- `rg -n "2026_pdf_q04_barcelona_sainz_fastest_lap_number|Carlos Sainz personal fastest lap on lap 58|discrepant_needs_review|validation_blocked" outputs/tables/question_workflow_surfaces.csv` -> exit 0; Q04 flat CSV rows show lap 58, discrepancy status, and validation-blocked analysis status.
- `git diff --check` -> exit 0.
- `pdftotext -layout 'external/f1-questions/Gmail - 2026 F1 Questions.pdf' -` -> exit 0; literal PDF text shows Q04 answer line: `Carlos Sainz clocked his personal fastest lap of the race on Lap 60`.
- `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces` -> exit 0 after rollback; 89 tests OK.
- `git diff -- src/f1_analytics/analysis/question_workflow_surfaces.py tests/test_question_workflow_surfaces.py` -> exit 0 with no output; the incorrect Q04 source-backed bridge has been removed from code/tests.
- `python3 _bmad/scripts/resolve_customization.py --skill /Users/antonio/.agents/skills/bmad-create-story --key workflow` -> exit 0; no activation prepend/append hooks, persistent fact `file:{project-root}/**/project-context.md`.
- `git diff -- src/f1_analytics/analysis/question_workflow_surfaces.py tests/test_question_workflow_surfaces.py src/f1_analytics/analysis/question_lap_answers.py tests/test_question_lap_answers.py` -> exit 0 with no output during create-story repair; no source-code edits were needed.
- Official Jolpica documentation check, 2026-07-29: `https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md` documents shared query parameters for all endpoints: `limit` defaults to 30 with max 100, `offset` supports pagination, and common response fields include `MRData.limit`, `MRData.offset`, and `MRData.total`.
- `git diff --check` -> exit 0 after Story 7.6 / Epic 7.6 / sprint-status artifact repair.
- `rg -n 'force-wired|force-wires|temporary Q04 bridge|stale generated|Jolpica pagination|not as a value this story|must not be used as evidence' _bmad-output/implementation-artifacts/7-6-reconcile-q04-fastest-lap-answer-and-surface-discrepancy.md _bmad-output/planning-artifacts/epics.md _bmad-output/implementation-artifacts/sprint-status.yaml` -> exit 0; confirmed the corrected guardrails and pagination follow-up are present.
- `python3 _bmad/scripts/resolve_customization.py --skill /Users/antonio/.agents/skills/bmad-create-story --key workflow.on_complete` -> exit 0; resolved empty `workflow.on_complete`.
- `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces` -> exit 0 during dev-story completion gates; 89 tests OK.
- `git diff --check` -> exit 0 during dev-story completion gates.
- `PYTHONPATH=src python3 -m unittest discover -s tests` -> exit 0 during dev-story completion gates; 381 tests OK; Arrow emitted sandbox `sysctlbyname` warnings and expected daily-pipeline failure-path fixture output.
- `PYTHONPATH=src python3 scripts/build_question_workflow_surfaces.py` -> exit 0 during code-review patching; regenerated `outputs/reports/question_workflow_surfaces.md` and `outputs/tables/question_workflow_surfaces.csv`; Arrow emitted sandbox `sysctlbyname` warnings.
- `rg -n "2026_pdf_q04_barcelona_sainz_fastest_lap_number|Carlos Sainz personal fastest lap on lap 58|Answer: Carlos Sainz|Carlos Sainz clocked his personal fastest lap of the race on Lap 60|not yet computed" outputs/reports/question_workflow_surfaces.md outputs/tables/question_workflow_surfaces.csv` -> exit 0 during code-review patching; confirmed Q04 report, portfolio, and insight-package surfaces render `not yet computed in this bundle`, and the CSV intake row preserves the exact PDF answer wording.
- `PYTHONPATH=src python3 -m unittest tests.test_question_workflow_surfaces` -> exit 0 during code-review patching; 89 tests OK.
- `git diff --check` -> exit 0 during code-review patching.
- `rg -n "Carlos Sainz personal fastest lap on lap 58|Answer: Carlos Sainz" outputs/reports/question_workflow_surfaces.md outputs/tables/question_workflow_surfaces.csv` -> exit 1 during code-review patching; expected no matches, confirming stale Q04 lap `58` final-answer text is absent from regenerated report/CSV outputs.
- `PYTHONPATH=src python3 -m unittest discover -s tests` -> exit 0 during code-review patching; 381 tests OK; Arrow emitted sandbox `sysctlbyname` warnings and expected daily-pipeline failure-path fixture output.

### Review Notes

- Review premise corrected: the original acceptance target was based on the wrong premise for questions taken from the PDF, and this story now preserves Q04 as a discrepancy-review case rather than a finalized generated answer.

### Critical Finding - Jolpica Lap Pagination Truncation

- **Finding:** `raw_jolpica_laps` is not trustworthy in the current local DuckDB build. The Jolpica loader calls every endpoint with `params={"limit": 100}` and never follows `MRData.offset` pagination, so race-level lap timing endpoints are capped at the first 100 returned timing rows.
- **Source-code evidence:** `src/f1_analytics/data_sources/jolpica_loader.py` uses `fetch_json(f"{season}/{round_}/{endpoint}.json", params={"limit": 100})` in `fetch_and_cache()`, and `load_jolpica_season()` calls that helper for `laps` without any offset loop.
- **External-source basis:** Jolpica documents `limit` as max 100, `offset` as the pagination mechanism, and `MRData.total` as the total available result count. Its laps endpoint documentation shows race lap totals far above 100, so a one-page `limit=100` request is incomplete by design.
- **Local data evidence:** cached 2026 Jolpica lap responses report `MRData.total` between 871 and 1445 rows per completed round, while the DuckDB table has exactly 100 `raw_jolpica_laps` rows for every completed 2026 round. Comparing result completed-lap totals to landed lap rows shows missing lap-timing rows for every completed 2026 race, e.g. round 1 expected 1003 driver-lap rows and landed 100; round 6 expected 1445 and landed 100; round 11 expected 1429 and landed 100.
- **Scope impact:** This does not appear to invalidate `raw_jolpica_results`, `raw_jolpica_qualifying`, `raw_jolpica_driver_standings`, or `raw_jolpica_constructor_standings` for the current 2026 rounds because their `MRData.total` values are below 100. `raw_jolpica_pitstops` also currently stays below 100 per completed 2026 race, but the loader still needs generic pagination because the API contract does not guarantee future totals remain under 100.
- **Q04 impact:** This finding reinforces the rollback in this story. Q04 must not use `raw_jolpica_laps` as corroborating or fallback evidence until Jolpica pagination is fixed, data is repulled, and ingestion completeness is validated. `raw_jolpica_results.fastest_lap_lap` may still be a separate result-level source field, but the per-lap derivative path is contaminated by incomplete ingestion.
- **Required follow-up story:** Fix Jolpica pagination and rebuild source evidence. The follow-up must add a paginated fetch loop for Jolpica endpoints, cache page metadata or aggregated payloads, validate fetched row count against `MRData.total`, repull and rebuild the local DuckDB tables, add tests that fail on a one-page truncated response, and add an ingestion completeness check for `raw_jolpica_laps` against completed-lap expectations.
