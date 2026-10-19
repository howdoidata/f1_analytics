select
    regexp_extract(filename, '([^/\\]+)[/\\]([^/\\]+)[/\\][^/\\]+$', 2) as race_label,
    regexp_extract(filename, '([^/\\]+)[/\\]([^/\\]+)[/\\][^/\\]+$', 1) as season_folder,
    try_cast(season_folder as bigint) as season,
    "Time",
    cast("AirTemp" as double) as "AirTemp",
    cast("Humidity" as double) as "Humidity",
    cast("Pressure" as double) as "Pressure",
    cast("Rainfall" as boolean) as "Rainfall",
    cast("TrackTemp" as double) as "TrackTemp",
    cast("WindDirection" as bigint) as "WindDirection",
    cast("WindSpeed" as double) as "WindSpeed"
from {{ source('fastf1', 'weather') }}
