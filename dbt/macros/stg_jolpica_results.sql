{#- Race or sprint classification rows: Ergast columns typed and renamed.
    Numbers use TRY_CAST, so a non-numeric value lands NULL and the
    not_null tests on season/round catch it. Points go through DECIMAL(38, 10):
    points never have more than two decimals, and this reads float noise in the
    raw file (one `1.1400000000000001`) as the value it stands for. -#}
{% macro stg_jolpica_results(table_name) -%}
select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    raceName as race_name,
    driverId as driver_id,
    trim(coalesce(givenName, '') || ' ' || coalesce(familyName, '')) as driver_name,
    constructorId as constructor_id,
    constructorName as constructor,
    try_cast(grid as bigint) as grid,
    try_cast(position as bigint) as position,
    try_cast(try_cast(points as decimal(38, 10)) as double) as points,
    try_cast(laps as bigint) as laps,
    status,
    totalRaceTime as time,
    try_cast(fastestLapNumber as double) as fastest_lap,
    try_cast(fastestLapRank as double) as fastest_lap_rank
from {{ source('jolpica', table_name) }}
{%- endmacro %}
