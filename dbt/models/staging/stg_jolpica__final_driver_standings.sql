-- A driver who raced for several teams in a season lists them in order,
-- separated by ';'. The first is kept.
select
    try_cast(season as bigint) as season,
    try_cast(position as double) as position,
    -- DECIMAL first: see the stg_jolpica_results macro.
    try_cast(try_cast(points as decimal(38, 10)) as double) as points,
    try_cast(wins as bigint) as wins,
    driverId as driver_id,
    nullif(split_part(constructorIds, ';', 1), '') as constructor_id
from {{ source('jolpica', 'final_driver_standings') }}
