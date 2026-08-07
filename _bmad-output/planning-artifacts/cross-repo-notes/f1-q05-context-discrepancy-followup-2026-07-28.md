---
date: 2026-07-29
from: f1_analytics
to: gatherer
status: response
responds_to: gatherer-q05-context-discrepancy-followup-2026-07-28.md
source_scope: user_provided
---

# Q05 Context And Discrepancy Follow-Up

This follow-up payload may be read by Gatherer as user_provided exchange input. It does not authorize Gatherer to read F1, Platform, parent, or sibling repository paths.

## Scope

This is a narrow exchange-staged disposition reply covering all six items Gatherer listed. It tells Gatherer which items should block only a higher-fidelity narrative/portfolio layer, which scoring definition F1's answer field uses, and how the retirement-lap item resolves.

Superseded-by notice: the dispositions in this note were staged to Gatherer as `f1-q05-context-discrepancy-disposition-2026-07-29.md`, and the retirement-lap disposition in that staged copy was subsequently corrected by `f1-q05-context-discrepancy-erratum-2026-07-29.md`. This note is F1's durable, corrected record of the reply.

Path-looking strings below are source labels and provenance labels only.

## Disposition Summary

| Item | Disposition | Current handoff effect | Missing source / future expectation |
|---|---|---|---|
| Incident context for the Lap 1 collision with Ollie Bearman | `explicitly_out_of_scope` | This should not block the current `raw_evidence` handoff level. The current handoff can preserve the known-answer narrative as user-provided context, but F1 is not source-backing the collision narrative in this packet. | Source-backed incident context would require a separate source-coverage story against an authorized narrative/race-control source, such as OpenF1 `race_control`, FIA documents, official race notes, or another approved narrative source. F1 does not expect to supply this in the current Epic 7 exchange-response work unless separately requested and planned. |
| Front-wing change evidence | `explicitly_out_of_scope` | This should not block the current `raw_evidence` handoff level. F1 is not source-backing the front-wing-change narrative in this packet. | Source-backed front-wing change evidence would require a separate source-coverage story against an authorized narrative, race-control, team, FIA, or other approved source. F1 does not expect to supply this in the current Epic 7 exchange-response work unless separately requested and planned. |
| Restart context | `explicitly_out_of_scope` | This should not block the current `raw_evidence` handoff level. OpenF1 stints show a `HARD` stint beginning at lap 2, but F1 is not treating that as source-backed restart evidence. | Source-backed restart context would require a separate source-coverage story against race-control/session-status or official narrative evidence. F1 does not expect to supply this in the current Epic 7 exchange-response work unless separately requested and planned. |
| Weather/session-condition context | `explicitly_out_of_scope` | This should not block the current `raw_evidence` handoff level. F1 is not source-backing weather/session-condition context in this packet. | Source-backed weather/session-condition context would require a separate source-coverage story against an authorized weather/session source, such as OpenF1 `weather` or another approved source. F1 does not expect to supply this in the current Epic 7 exchange-response work unless separately requested and planned. |
| First tyre-change-lap scoring definition | `source_backed` | F1's `first_tyre_change_lap` answer field means the **pit-stop event lap**, which is lap `1` for Q05. F1 derives it from the scoped `raw_jolpica_pitstops` row's `lap` field, so lap `2` (first lap run on the new compound) is not the value this answer field carries. The component's readiness remains `PARTIAL`/`DERIVABLE` because Jolpica records pit stops without tyre-change compound or stint context, so the definition is settled while the fact itself is not yet final. | None for the definition. Making the component final requires stint-level compound-change evidence, which is separate from this scoring-definition question. |
| Retirement-lap discrepancy: Jolpica `laps=43`, `status=Retired` vs known-answer narrative | `source_backed` | Resolved, and no longer a discrepancy. The known-answer narrative value F1 previously carried, `retired on Lap 45`, was erroneous and has been corrected in F1's own catalog to `retired after 43 completed laps`. Source and known-answer now agree at `43` completed laps, so F1's coverage entry reports `available`/`computed` rather than `discrepant_needs_review`. | None. This item no longer needs a future source-coverage story. |

## Carried-Over Evidence Basis

The dispositions above are grounded in the following already-exchanged or already-generated F1 evidence labels:

- Story 7.4 OpenF1 stints follow-up: `f1-q05-openf1-stints-followup-2026-07-28.md`.
- Generated Q05 workflow surface: `question_workflow_surfaces:insight_package:v1`.
- Local source-coverage labels: `raw_jolpica_pitstops`, `raw_jolpica_laps`, `raw_jolpica_results`, `OpenF1`.

Relevant carried-over findings:

- Starting compound is source-backed from the Story 7.4 OpenF1 stints excerpt as `MEDIUM`.
- First pit-stop lap is source-backed from Jolpica pit-stop evidence as lap `1`.
- Current local Q05 source coverage states that `raw_jolpica_pitstops`, `raw_jolpica_laps`, and `raw_jolpica_results` do not expose collision/race-control incident context, front-wing change evidence, restart/race-control context, or weather/session-condition evidence.
- First tyre-change lap is derived from the pit-stop event lap (`raw_jolpica_pitstops.lap`), giving lap `1`; readiness stays `PARTIAL` because Jolpica carries no compound/stint context.
- Current local Q05 result evidence states `laps=43`, `status=Retired`. The known-answer narrative has been corrected from the erroneous `retired on Lap 45` to `retired after 43 completed laps`, so source and known-answer agree and F1 no longer treats this as a retirement-lap discrepancy. F1 also repaired the comparison that enforces this: the known-answer parser previously recognized only the `retired on Lap N` phrasing, so immediately after the catalog correction the discrepancy check silently stopped running instead of confirming agreement. The parser now reads both phrasings, and a regression test covers the disagreement path.

## Provenance

| Evidence/disposition section | Source label | Observed/produced time | Copied or summarized | Producer run id |
|---|---|---|---|---|
| Gatherer request | `gatherer-q05-context-discrepancy-followup-2026-07-28.md` | Request dated `2026-07-28`; read during Story 7.5 implementation | Summarized request requirements | `story-7.5-request-read-2026-07-29` |
| Prior OpenF1/Jolpica follow-up continuity | `f1-q05-openf1-stints-followup-2026-07-28.md` | Prior packet dated `2026-07-28`; re-read during Story 7.5 implementation | Summarized carried-over conclusions; no new OpenF1 endpoints queried | `story-7.5-prior-packet-read-2026-07-29` |
| Current Q05 source coverage state | `outputs/reports/question_workflow_surfaces.md`; `outputs/tables/question_workflow_surfaces.csv`; `question_workflow_surfaces:insight_package:v1` | Workflow output regenerated `2026-07-30T03:44:19+00:00` during Story 7.5 implementation | Summarized status and limitations | `question_workflow_surfaces:insight_package:v1`; `story-7.5-source-coverage-review-2026-07-29` |
| Q05 retirement-lap coverage entry | `raw_jolpica_results` via `question_tyre_pit_coverage:retirement_lap` | Regenerated `2026-07-30T03:44:19+00:00` | Copied entry status and reason text | `story-7.5-retirement-lap-recheck-2026-07-29` |
| First tyre-change-lap definition | `raw_jolpica_pitstops` via `question_tyre_pit_coverage:first_tyre_change_lap` | Regenerated `2026-07-30T03:44:19+00:00` | Summarized the definition F1's answer field implements | `story-7.5-scoring-definition-read-2026-07-29` |
| Known-answer comparison repair | `src/f1_analytics/analysis/question_tyre_pit_coverage.py` (`_known_answer_retirement_lap`) | Changed `2026-07-29`; full suite 382 tests passing | Code fix, not evidence | `story-7.5-known-answer-parser-fix-2026-07-29` |
| Disposition decisions | F1 Story 7.5 exchange-response implementation | Produced `2026-07-29` | New summary disposition; retirement-lap item now source-backed | `story-7.5-context-discrepancy-disposition-2026-07-29` |

## Handling Notes

- Treat this as `user_provided` exchange input.
- For the current `raw_evidence` handoff level, Gatherer may treat incident context, front-wing change, restart context, and weather/session-condition context as explicitly out of scope rather than still waiting on F1.
- Do not treat those four narrative items as source-backed facts.
- Treat the retirement-lap item as resolved at `43` completed laps with retirement/DNF status, and stop carrying it as an unresolved review item.
- Use the pit-stop event lap (`1`) for the Q05 first-tyre-change-lap answer field, not lap `2`.
- Do not infer direct-read authorization from any source label or path-looking citation in this packet.
