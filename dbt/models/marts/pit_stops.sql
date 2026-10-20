-- The stop count of record (W1): one row per Jolpica pit stop.
--   constructor_id: from the results row of the same season, round and driver.
--   stop_type:      unknown  -- the race has no car_races row (no FastF1 summary)
--                   red_flag -- lap inside a red_flag period (beats sc/vsc)
--                   sc_vsc   -- lap inside an sc or vsc period
--                   normal   -- every other stop, penalty stops included
--   A period includes its start_lap and end_lap.
with stops as (
    select * from {{ ref('stg_jolpica__pit_stops') }}
),

results as (
    select season, round, driver_id, constructor_id from {{ ref('results') }}
),

summarised_races as (
    select distinct season, round from {{ ref('car_races') }}
),

period_hits as (
    select
        stops.season,
        stops.round,
        stops.driver_id,
        stops.stop,
        bool_or(periods.status = 'red_flag') as in_red_flag,
        bool_or(periods.status in ('sc', 'vsc')) as in_sc_vsc
    from stops
    inner join {{ ref('stg_fastf1_summary__track_status_periods') }} as periods
        on periods.season = stops.season
        and periods.round = stops.round
        and stops.lap between periods.start_lap and periods.end_lap
    group by all
)

select
    stops.season,
    stops.round,
    stops.driver_id,
    results.constructor_id,
    stops.stop,
    stops.lap,
    stops.time,
    stops.duration_s,
    case
        when summarised_races.season is null then 'unknown'
        when period_hits.in_red_flag then 'red_flag'
        when period_hits.in_sc_vsc then 'sc_vsc'
        else 'normal'
    end as stop_type
from stops
left join results
    on results.season = stops.season
    and results.round = stops.round
    and results.driver_id = stops.driver_id
left join summarised_races
    on summarised_races.season = stops.season
    and summarised_races.round = stops.round
left join period_hits
    on period_hits.season = stops.season
    and period_hits.round = stops.round
    and period_hits.driver_id = stops.driver_id
    and period_hits.stop = stops.stop
