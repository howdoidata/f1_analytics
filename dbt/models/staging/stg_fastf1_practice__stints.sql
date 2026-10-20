-- Every practice stints file, one row per stint, typed.
select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    session,
    driver_id,
    constructor_id,
    try_cast(driver_number as bigint) as driver_number,
    try_cast(stint as bigint) as stint,
    compound,
    try_cast(laps as bigint) as laps,
    try_cast(deg_s_per_lap as double) as deg_s_per_lap
from {{ source('fastf1_practice', 'stints') }}
