---
type: convention
title: Source-name to curated-id reconciliation (AD-14)
description: Why every FastF1/Kaggle name mismatch resolves through exactly one sanctioned, decision-recorded mechanism per source/field pairing
tags: [data-integrity, decisions, fastf1, kaggle]
verified: 2026-08-07
sources: [src/f1_analytics/data_sources/fastf1_loader.py, src/f1_analytics/data_sources/kaggle_csv.py, _bmad-output/planning-artifacts/decisions/fastf1-constructor-name-reconciliation-decision-record.md, _bmad-output/planning-artifacts/decisions/fastf1-driver-code-reconciliation-decision-record.md, _bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md]
---
AD-14 requires one sanctioned name→id reconciliation per source/field pairing — never a fuzzy/normalized-string matcher, never silently picking one match among several. Three instances exist today, each authorized by its own dated decision record:

1. Kaggle `final_driver_standings.constructor_id` (name→id lookup, `kaggle_csv.py`).
2. FastF1 `Team` → `constructor_id`: exact match, then `FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES` (`fastf1_loader.py`), else `UnmappedFastF1NameError`.
3. FastF1 `Driver` code → `driver_id`: unique match, then `FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES` for codes reused across F1 eras (e.g. `VER` = both Jean-Éric Vergne and Max Verstappen in the curated table), else `AmbiguousFastF1DriverCodeError`.

A new source/field collision must get its own decision record before extending any table — extending silently (or adding a heuristic like "prefer the most recent") defeats AD-16's fail-early rule and AD-14's audit intent.
