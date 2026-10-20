-- story 2's per-car-per-race summary, typed. Values pass through as written:
-- stops_fastf1 is not the stop count and deg_s_per_lap is not fuel-corrected.
select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    circuit_id,
    driver_id,
    constructor_id,
    try_cast(driver_number as bigint) as driver_number,
    try_cast(laps_completed as bigint) as laps_completed,
    try_cast(stints as bigint) as stints,
    try_cast(stops_fastf1 as bigint) as stops_fastf1,
    start_compound,
    start_compound_raw,
    compounds_used,
    try_cast(wet_laps as bigint) as wet_laps,
    try_cast(air_temp_mean as double) as air_temp_mean,
    try_cast(track_temp_mean as double) as track_temp_mean,
    try_cast(rainfall as boolean) as rainfall,
    try_cast(deg_s_per_lap as double) as deg_s_per_lap
from {{ source('fastf1_summary', 'car_races') }}
