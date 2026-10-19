select
    weather.race_label,
    weather.season,
    counts.round,
    weather."Time",
    weather."AirTemp",
    weather."Humidity",
    weather."Pressure",
    weather."Rainfall",
    weather."TrackTemp",
    weather."WindDirection",
    weather."WindSpeed"
from {{ ref('stg_fastf1__weather') }} as weather
left join {{ ref('stg_fastf1__counts') }} as counts
    on counts.season_folder = weather.season_folder and counts.race_label = weather.race_label
order by weather.season, weather.race_label
