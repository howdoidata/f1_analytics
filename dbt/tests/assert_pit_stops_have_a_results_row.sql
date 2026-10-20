-- A Jolpica pit stop with no results row of the same season, round and driver:
-- its constructor_id would be unknown. Selects the stop's key so the build names it.
select stops.season, stops.round, stops.driver_id, stops.stop
from {{ ref('stg_jolpica__pit_stops') }} as stops
where not exists (
    select 1
    from {{ ref('results') }} as results
    where results.season = stops.season
        and results.round = stops.round
        and results.driver_id = stops.driver_id
)
