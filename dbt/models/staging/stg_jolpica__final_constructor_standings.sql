select
    try_cast(season as bigint) as season,
    try_cast(position as double) as position,
    -- DECIMAL first: see the stg_jolpica_results macro.
    try_cast(try_cast(points as decimal(38, 10)) as double) as points,
    try_cast(wins as bigint) as wins,
    constructorId as constructor_id,
    constructorName as constructor
from {{ source('jolpica', 'final_constructor_standings') }}
