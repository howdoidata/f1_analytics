-- The official season-end driver standings, with constructor and driver names.
select
    standings.season,
    standings.position,
    standings.points,
    standings.wins,
    standings.driver_id,
    constructors.name as constructor,
    trim(coalesce(drivers.given_name, '') || ' ' || coalesce(drivers.family_name, '')) as driver_name,
    standings.constructor_id
from {{ ref('stg_jolpica__final_driver_standings') }} as standings
left join {{ ref('constructors') }} as constructors
    on constructors.constructor_id = standings.constructor_id
left join {{ ref('drivers') }} as drivers
    on drivers.driver_id = standings.driver_id
