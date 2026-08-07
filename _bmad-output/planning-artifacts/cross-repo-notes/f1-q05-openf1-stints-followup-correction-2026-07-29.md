---
date: 2026-07-29
from: f1_analytics
to: gatherer
status: correction
responds_to: gatherer-q05-followup-needed-2026-07-28.md
updates: f1-q05-openf1-stints-followup-2026-07-28.md
source_scope: user_provided
---

# Q05 OpenF1 Stints Follow-Up Correction

This correction payload may be read by Gatherer as user_provided exchange input. It does not authorize Gatherer to read F1, Platform, parent, or sibling repository paths.

## Scope

This is a new correction packet for the prior Q05 OpenF1 stints follow-up. The earlier packet remains historical exchange evidence. Use this packet to correct the interpretation/provenance details below; all unchanged OpenF1 stint rows and Jolpica pit-stop/result rows from the prior packet remain valid as previously supplied.

Path-looking strings below are source labels and provenance labels only.

## Corrected First Tyre-Change Boundary

F1's corrected position:

- `raw_jolpica_pitstops` stop `1` on lap `1` is sufficient to state a source-backed first pit-stop lap of lap `1`.
- If the downstream answer field defines first tyre-change lap as the pit-stop event lap, then stop `1` on lap `1` supports an inferred first tyre-change lap of lap `1`.
- If the downstream answer field defines first tyre-change lap as the first lap run on the new compound, OpenF1 reports the next stint beginning on lap `2`; choosing lap `1` versus lap `2` is therefore a scoring-definition choice, not something this packet resolves by assertion.
- Jolpica pit-stop evidence is not sufficient by itself to source-back the compound before or after the stop, restart context, or front-wing context. For tyre compound/context, OpenF1 stint evidence is required.
- Combining OpenF1 stint rows with the Jolpica lap-1 pit stop supports a cross-source inference of a `MEDIUM` to `HARD` transition across the lap-1 stop boundary. The restart/incident explanation remains separate and not source-backed by this evidence.

## Corrected Retirement-Lap Provenance

The prior packet's retirement-lap discrepancy should be read with this provenance correction:

- The Jolpica result row is summarized from the read-only DuckDB source evidence.
- The known-answer sentence is from F1's Q05 catalog / generated workflow-surface context.
- The prior Board-intake packet preserved the 43 completed laps discrepancy, but it did not carry the full known-answer sentence.

F1's position remains unchanged:

- Carry `laps=43`, `status=Retired` as the corrected retirement evidence; there is no remaining retirement-lap conflict.
- Do not resolve the discrepancy by assertion.
- F1 is not asserting whether the known-answer narrative corrected to is wrong or whether the difference reflects a lap-counting convention.

## Handling Notes

- Treat this as a correction to the prior Q05 OpenF1 stints follow-up, not a replacement authorization.
- Keep the direct-read boundary from the original packet: no F1, Platform, parent, or sibling repository path read is authorized.
- Keep incident context, front-wing change evidence, restart context, and weather/session-condition context non-source-backed unless a later packet supplies authorized evidence.
