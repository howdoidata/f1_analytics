---
title: "FastF1 Ambiguous Driver Code Reconciliation Decision Record"
status: active
created: 2026-08-07
source_material:
  - data/raw/fastf1/{Melbourne,Miami,Canada,Silverstone}/laps.csv (cached live FastF1 fetch, 2026-08-07)
  - data/processed/f1_analytics.duckdb (drivers table, built by Story 1.5)
  - _bmad-output/planning-artifacts/decisions/fastf1-constructor-name-reconciliation-decision-record.md
  - src/f1_analytics/data_sources/fastf1_loader.py (AmbiguousFastF1DriverCodeError, added during /bmad-code-review on 2026-08-07)
---

# FastF1 Ambiguous Driver Code Reconciliation Decision Record

## Decision

Adopt a third sanctioned name→id reconciliation under AD-14: a small static override table that resolves a FastF1 `Driver` code to a specific curated `drivers.driver_id`, consulted only when that code matches more than one curated row. Every other code continues to resolve by the existing single-match lookup, unchanged. A FastF1 `Driver` code that's ambiguous in the curated table but not named in this override table still raises `AmbiguousFastF1DriverCodeError` — this decision authorizes exactly the two named overrides below, not a general disambiguation mechanism.

This is scoped narrowly to unblock re-landing Story 1.6's FastF1 facts, currently blocked by the `AmbiguousFastF1DriverCodeError` safeguard added during code review — itself a fix for a real defect: `raw_fastf1_laps`/`raw_fastf1_stints` had already silently landed Max Verstappen's and Alexander Albon's 2026 laps under the wrong historical `driver_id` before that safeguard existed. It does not reopen or relax AD-14's "exactly one sanctioned reconciliation" rule for anything beyond this specific FastF1 driver-code case.

## Evidence

The curated `drivers` table (built by Story 1.5 from the Kaggle salvage restore) has six FastF1 3-letter codes that each match two distinct `driver_id` rows — F1 codes are reused across eras:

| code | curated row A | curated row B |
|---|---|---|
| ALB | `albers` (Christijan Albers) | `albon` (Alexander Albon) |
| DOO | `doohan` (Jack Doohan) | `doornbos` (Robert Doornbos) |
| HAR | `brendon_hartley` (Brendon Hartley) | `haryanto` (Rio Haryanto) |
| MAG | `magnussen` (Jan Magnussen) | `kevin_magnussen` (Kevin Magnussen) |
| MSC | `michael_schumacher` (Michael Schumacher) | `mick_schumacher` (Mick Schumacher) |
| VER | `vergne` (Jean-Éric Vergne) | `max_verstappen` (Max Verstappen) |

Cross-referenced against the actual `Driver` codes present in all four completed 2026 FastF1 dumps (`data/raw/fastf1/{Melbourne,Miami,Canada,Silverstone}/laps.csv`; Barcelona excluded — its session isn't run yet per the 1.2 decision record): only **VER** and **ALB** appear. DOO, HAR, MAG, and MSC never appear in any of the four races' laps and require no override today.

For both codes that do appear, FastF1's own `DriverNumber` column (present in `laps.csv`, deliberately never used as this module's join key — car numbers have their own history of reuse, per this module's existing tests) independently corroborates which curated row is correct:

| code | FastF1 `DriverNumber` (all 4 races) | curated row matching that number | curated row NOT matching |
|---|---|---|---|
| VER | 3 | `max_verstappen` (number 3.0) | `vergne` (number 25.0) |
| ALB | 23 | `albon` (number 23.0) | `albers` (number blank) |

Without this decision, `map_driver_ids`'s pre-fix behavior (`drop_duplicates(subset=["code"])`, arbitrary-first-row) had already landed real 2026 laps under the wrong id: the already-committed `raw_fastf1_laps` table contains 230 laps under `driver_id='vergne'` and 169 under `'albers'`, and zero laps under `max_verstappen` or `albon`, across all four already-landed races.

## The Override Table

```python
FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES = {
    "VER": "max_verstappen",
    "ALB": "albon",
}
```

**Resolution order** (in `fastf1_loader.py`'s `map_driver_ids()`): (1) if a FastF1 `Driver` code matches exactly one curated `driver_id`, use it, unchanged from before; (2) if it matches more than one curated `driver_id`, look up this override table; (3) if still unresolved — ambiguous and not in the table — raise `AmbiguousFastF1DriverCodeError` naming the exact code, never guessing and never preferring a heuristic like "most recent" or "has a car number." The table is keyed on the FastF1-side code (the side that's ambiguous) and points at the Kaggle-side `driver_id` that's already authoritative (AD-2), so it needs no new id space and does not touch the curated `drivers` table itself.

## Rationale

Same shape as the constructor reconciliation this mirrors: a free-text override table pointed at the *existing* `driver_id` space, not a new id scheme — AD-14's "exactly one sanctioned reconciliation" is read as one sanctioned reconciliation per source/field pairing, of which this is now the third (Story 1.5's `final_driver_standings.constructor_id`, the constructor `Team`→`constructor_id` alias, and now this). A heuristic disambiguator (e.g. "prefer whichever curated row has the more recent `dob`," or "prefer the row with a non-null `number`") was considered and rejected: it would silently produce a correct-today, wrong-tomorrow answer the moment a collision should resolve the other way, exactly the kind of hardcoded judgment call this decision makes explicitly and auditably instead. A static table is small (2 entries today), reviewable in one screen, and fails loudly (`AmbiguousFastF1DriverCodeError`, already implemented) the moment a currently-dormant collision (DOO/HAR/MAG/MSC) or a new one becomes live — exactly AD-16's fail-early rule.

## Scope And Enforcement

Applies only to `src/f1_analytics/data_sources/fastf1_loader.py`'s FastF1 `Driver` → `driver_id` mapping (`map_driver_ids()`). Does not apply to constructor mapping (already covered by the separate constructor-name reconciliation decision). Does not modify the curated `drivers` table itself.

## Follow-up Conditions

- If a currently-dormant collision (DOO, HAR, MAG, or MSC) or a brand-new one ever appears in a live FastF1 dump, `AmbiguousFastF1DriverCodeError` will name it explicitly; extend this override table with the correct `driver_id`, verified against corroborating evidence (e.g. `DriverNumber`, active-season context) the same way VER/ALB were resolved here, rather than adding a heuristic.
- Re-verify this table if Kaggle's dataset is ever successfully re-downloaded (its 400 error is still unresolved per the 1.2 decision record) — a refreshed dataset could renumber or reassign `driver_id` values and invalidate these two overrides.
- Once this decision lands in code, `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather` must be re-derived by re-running `scripts/pull_fastf1_data.py` — the currently-landed tables still carry the pre-fix wrong ids (`vergne`/`albers`) and are not corrected merely by shipping this decision.

## Authorization

Requested by Antonio (project owner) in-session on 2026-08-07, by selecting "author the driver-code reconciliation decision record" as the follow-up to `/bmad-code-review`'s finding that `map_driver_ids`'s `drop_duplicates()` pattern had already silently landed Max Verstappen's and Alexander Albon's 2026 laps under the wrong historical driver, and Antonio's in-review choice to fail loudly (`AmbiguousFastF1DriverCodeError`) rather than guess. Antonio approved this record for implementation in-session on 2026-08-07.

## Status

Accepted.
