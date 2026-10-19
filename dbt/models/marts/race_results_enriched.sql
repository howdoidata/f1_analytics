-- results with their race's date, start time, circuit and URL (a left join).
select
    results.*,
    races.date,
    races.time as time_race,
    races.circuit_id,
    races.url
from {{ ref('results') }} as results
left join {{ ref('races') }} as races
    on races.season = results.season and races.round = results.round
