-- One row per driver stint: the first constructor and compound of the stint
-- (by lap number) and its lap boundaries. A lap with no Stint fails the
-- not_null test on raw_fastf1_laps."Stint", so this model never folds
-- unassigned laps into one artificial stint.
select
    race_label,
    season,
    round,
    driver_id,
    cast("Stint" as bigint) as stint_number,
    first(constructor_id order by "LapNumber") filter (where constructor_id is not null) as constructor_id,
    first("Compound" order by "LapNumber") filter (where "Compound" is not null) as compound,
    cast(min("LapNumber") as bigint) as lap_start,
    cast(max("LapNumber") as bigint) as lap_end,
    count("LapNumber") as lap_count
from {{ ref('raw_fastf1_laps') }}
group by race_label, season, round, driver_id, "Stint"
order by season, race_label, driver_id, stint_number
