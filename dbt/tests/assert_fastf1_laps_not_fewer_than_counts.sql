-- A truncated extract: fewer laps landed than the session reported.
with landed as (
    select season_folder, race_label, count(*) as landed_laps
    from {{ ref('stg_fastf1__laps') }}
    group by season_folder, race_label
)

select counts.season_folder, counts.race_label, coalesce(landed.landed_laps, 0) as landed_laps, counts.lap_count
from {{ ref('stg_fastf1__counts') }} as counts
left join landed using (season_folder, race_label)
where counts.lap_count is not null and coalesce(landed.landed_laps, 0) < counts.lap_count
