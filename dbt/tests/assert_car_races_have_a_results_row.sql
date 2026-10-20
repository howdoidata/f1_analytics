-- A car_races row with no results row of the same race, driver and constructor.
select cars.season, cars.round, cars.driver_id, cars.constructor_id
from {{ ref('car_races') }} as cars
where not exists (
    select 1
    from {{ ref('results') }} as results
    where results.season = cars.season
        and results.round = cars.round
        and results.driver_id = cars.driver_id
        and results.constructor_id = cars.constructor_id
)
