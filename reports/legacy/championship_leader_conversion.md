# Championship Leader Conversion At Current Season Cutoff

## Report Summary

- Question: How often did the driver or constructor leading at this point in the season go on to win the championship?
- Answer: Drivers: the cutoff leader became champion in 40 of 76 historical seasons (52.6%); constructors: 38 of 68 (55.9%).
- Source and cutoff basis: Target season 2026; cutoff round 3 (Japanese Grand Prix, 2026-03-29); the cutoff comes from completed rounds in local Kaggle `f1_results.csv`, not from scheduled future races.
- Status: [COMPUTED] — Conversion is computed from completed historical Kaggle rounds; the 2026 championship outcome is not yet known in the local results, so current-season leaders are reported separately rather than counted as converted.
- Next action: reuse_existing
- Evidence:
  - outputs/tables/driver_leader_conversion.csv
  - outputs/tables/constructor_leader_conversion.csv
  - outputs/tables/current_season_leaders.csv
  - outputs/tables/data_coverage_summary.csv

## Question

How often did the driver or constructor leading at this point in the season go on to win the championship?

## Cutoff Definition

This point in the season is defined from completed results in `f1_results.csv`, not from scheduled future races.

* Target season: 2026
* Latest completed round: 3
* Cutoff race: Japanese Grand Prix
* Cutoff race date: 2026-03-29

The local race schedule lists 22 races for 2026, while race results currently cover 3 completed rounds.

## Drivers

Across 76 historical seasons with at least 3 completed rounds, the drivers' championship leader after round 3 became champion in 40 seasons.

Conversion rate: 52.6%

Current 2026 driver leader(s) at the cutoff:

| leader_name | leader_points | leader_wins |
| --- | --- | --- |
| Andrea Kimi Antonelli | 68.0 | 2 |

## Constructors

Across 68 historical seasons with constructor standings data and at least 3 completed rounds, the constructors' championship leader after round 3 became champion in 38 seasons.

Conversion rate: 55.9%

Current 2026 constructor leader(s) at the cutoff:

| leader_name | leader_points | leader_wins |
| --- | --- | --- |
| Mercedes | 123.0 | 3 |

## Current Season Leaders

The current target-season leaders are reported separately because the 2026 championship outcome is not yet known in the local results.

| entity_type | leader_name | leader_points | leader_wins |
| --- | --- | --- | --- |
| driver | Andrea Kimi Antonelli | 68.0 | 2 |
| constructor | Mercedes | 123.0 | 3 |

## Data Limitations

* The cutoff uses the latest completed round available in the local `f1_results.csv` file.
* The local `f1_races.csv` file can include scheduled future races, so scheduled races are not treated as completed.
* Historical comparisons use the same round number as the cutoff and exclude seasons without enough completed races.
* Tied leaders are included as co-leaders when they share first place on cumulative points and wins.
* Constructors' championship conversion starts with seasons where constructor championship data exists.

## Output Tables

* `outputs/tables/driver_leader_conversion.csv`
* `outputs/tables/constructor_leader_conversion.csv`
* `outputs/tables/current_season_leaders.csv`
* `outputs/tables/data_coverage_summary.csv`
