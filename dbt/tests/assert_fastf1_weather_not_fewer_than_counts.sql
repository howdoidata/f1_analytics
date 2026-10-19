-- A truncated extract: fewer weather rows landed than the session reported.
with landed as (
    select season_folder, race_label, count(*) as landed_weather
    from {{ ref('stg_fastf1__weather') }}
    group by season_folder, race_label
)

select counts.season_folder, counts.race_label, coalesce(landed.landed_weather, 0) as landed_weather, counts.weather_count
from {{ ref('stg_fastf1__counts') }} as counts
left join landed using (season_folder, race_label)
where counts.weather_count is not null and coalesce(landed.landed_weather, 0) < counts.weather_count
