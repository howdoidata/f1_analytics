---
type: convention
title: Per-race failure isolation (AD-13)
description: Why one race's fetch/mapping failure never aborts the rest of a multi-race pipeline run
tags: [fastf1, error-handling]
verified: 2026-08-20
sources: [src/f1_analytics/data_sources/fastf1_loader.py, scripts/pull_fastf1_data.py, _bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md, _bmad-output/implementation-artifacts/1-6-fastf1-facts-landed-with-rate-discipline.md]
---
`load_and_map_race()` wraps every failure in its pipeline (missing dump file, corrupt `counts.json`, malformed CSV, an unmapped/ambiguous name, an incomplete-count mismatch) in `FastF1RaceLoadError`, naming the race. `pull_race()` (`pull_fastf1_data.py`) catches that per race and records a `"failed"` outcome with a stage and detail, never propagating past the race loop — a landed race's data ships even when a different race in the same run fails (e.g. Barcelona's future-session failure never blocks Melbourne/Miami/Canada/Silverstone from landing).

A truncated fetch is a *statused failure*, never a silently shorter table: `verify_completeness()` raises `IncompleteFastF1DataError` if landed laps/weather undercount the session's own reported totals, or if an expected driver is missing entirely.
