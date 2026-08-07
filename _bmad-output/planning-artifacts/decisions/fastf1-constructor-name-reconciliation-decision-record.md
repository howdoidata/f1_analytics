---
title: "FastF1-to-Kaggle Constructor Name Reconciliation Decision Record"
status: active
created: 2026-08-07
source_material:
  - data/raw/fastf1/{Melbourne,Miami,Canada,Silverstone}/laps.csv (live FastF1 fetch, 2026-08-07)
  - data/processed/f1_analytics.duckdb (constructors table, built by Story 1.5)
  - _bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md
---

# FastF1-to-Kaggle Constructor Name Reconciliation Decision Record

## Decision

Adopt a second sanctioned name→id reconciliation under AD-14: a small static alias table mapping FastF1's live `Team` string to the existing curated `constructors.constructor_id` Story 1.5 already landed, for the four 2026 teams whose FastF1 name doesn't exactly match their Kaggle curated name. Every other team continues to resolve by an exact `Team` == `constructors.name` match, unchanged. An FastF1 `Team` string that matches neither the exact-name path nor the alias table still raises `UnmappedFastF1NameError` — this decision authorizes exactly the four named aliases below, not a fuzzy-matching or auto-correcting mechanism.

This is scoped narrowly to unblock Story 1.6 (FastF1 Facts Landed With Rate Discipline); it does not reopen or relax AD-14's "exactly one sanctioned reconciliation" rule for anything beyond this specific FastF1↔constructor case.

## Evidence

Live `fastf1_fetch.py` runs against Melbourne, Miami, Canada, and Silverstone (2026-08-07; Barcelona excluded — its session isn't run yet per the 1.2 decision record) all landed the identical 11-team `Team` column:

`Alpine, Aston Martin, Audi, Cadillac, Ferrari, Haas F1 Team, McLaren, Mercedes, Racing Bulls, Red Bull Racing, Williams`

Cross-referenced against the curated `constructors` table (`SELECT constructor_id, name FROM constructors`, built by Story 1.5 from the Kaggle salvage restore):

| `constructor_id` | Kaggle `constructors.name` | FastF1 `Team` string | Exact match? |
|---|---|---|---|
| `alpine` | Alpine F1 Team | Alpine | No — alias needed |
| `aston_martin` | Aston Martin | Aston Martin | Yes |
| `audi` | Audi | Audi | Yes |
| `cadillac` | Cadillac F1 Team | Cadillac | No — alias needed |
| `ferrari` | Ferrari | Ferrari | Yes |
| `haas` | Haas F1 Team | Haas F1 Team | Yes |
| `mclaren` | McLaren | McLaren | Yes |
| `mercedes` | Mercedes | Mercedes | Yes |
| `rb` | RB F1 Team | Racing Bulls | No — alias needed |
| `red_bull` | Red Bull | Red Bull Racing | No — alias needed |
| `williams` | Williams | Williams | Yes |

`Cadillac` — the 2026 grid's new eleventh entrant — is already present in the curated table (`cadillac` / "Cadillac F1 Team"); it is not a missing-entrant problem, only a naming one. 7 of 11 teams already resolve by exact string match today; only the 4 rows above need the alias.

## The Alias Table

```python
FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES = {
    "Alpine": "alpine",
    "Cadillac": "cadillac",
    "Racing Bulls": "rb",
    "Red Bull Racing": "red_bull",
}
```

**Resolution order** (in `fastf1_loader.py`'s constructor-mapping function): (1) exact match against `constructors.name`; (2) if no exact match, look up the FastF1 `Team` string in this alias table; (3) if neither resolves, raise `UnmappedFastF1NameError` naming the exact unresolved string — never guess, never fuzzy-match. The alias table is keyed on the FastF1-side string (the side that varies) and points at the Kaggle-side `constructor_id` that's already authoritative (AD-2), so it needs no new id space and does not touch `constructors.name` itself.

## Rationale

AD-14 exists to prevent per-source id schemes and unstable joins; a free-text alias table pointed at the *existing* `constructor_id` space is the same shape as Story 1.5's already-sanctioned `final_driver_standings.constructor_id` reconciliation (also a small free-text-name → id lookup), not a new id scheme. A fuzzy/normalized-string matcher was considered and rejected: F1 team names routinely share substrings across eras and sister teams (e.g. a normalized match could not safely tell "Red Bull Racing" from "Red Bull" apart from a hypothetical future "Red Bull Junior" without the same kind of hardcoded judgment call this alias table already makes explicitly and auditably). A static table is small (4 entries), reviewable in one screen, and fails loudly (named error) the moment FastF1 or Kaggle renames a team again — exactly AD-16's fail-early rule.

## Scope And Enforcement

Applies only to `src/f1_analytics/data_sources/fastf1_loader.py`'s FastF1 `Team` → `constructor_id` mapping (Story 1.6). Does not apply to driver mapping (FastF1's `Driver` 3-letter code already matches curated `drivers.code` exactly for all 20 2026 drivers — no reconciliation needed there). Does not modify `constructors.name` or any Kaggle curated table.

## Follow-up Conditions

- If a mid-season team rename, sale, or new entrant introduces a `Team` string not covered above, `UnmappedFastF1NameError` will name it explicitly; extend the alias table (or add a new curated `constructors` row if it's a genuinely new entrant) rather than loosening the matching strategy.
- Re-verify this table if Kaggle's dataset is ever successfully re-downloaded (its 400 error is still unresolved per the 1.2 decision record) — a refreshed dataset could change `constructors.name` spellings and invalidate specific alias entries.

## Authorization

Requested and approved by Antonio (project owner) in-session on 2026-08-07, in direct response to Story 1.6's implementation halting on this exact constructor-name mismatch: "Author a decision record admitting a second FastF1↔constructor reconciliation (an alias table keyed on Kaggle's existing constructor_ids is the lightest fix)." The alias table and resolution order above implement that instruction verbatim against the verified evidence.

## Status

Accepted.
