-- One row per race with car_races rows: incident is true when the race had an
-- sc or red_flag period (a vsc does not count); a race with no period is clean.
with races as (
    select distinct season, round
    from {{ ref('car_races') }}
),

periods as (
    select season, round, status
    from {{ ref('stg_fastf1_summary__track_status_periods') }}
)

select
    races.season,
    races.round,
    coalesce(bool_or(periods.status in ('sc', 'red_flag')), false) as incident
from races
left join periods
    on periods.season = races.season
    and periods.round = races.round
group by races.season, races.round
