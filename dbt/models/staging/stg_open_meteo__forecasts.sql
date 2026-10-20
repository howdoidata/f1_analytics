-- One row per forecast file per hour, typed. The kind (e.g. day_before) is the
-- folder; season and round come from the <season>-<RR>.json file name.
-- The hourly arrays are unnested side by side, so each row keeps its hour's values.
with files as (
    select
        regexp_extract(filename, '([^/\\]+)[/\\](\d+)-(\d+)\.json$', 1) as kind,
        try_cast(regexp_extract(filename, '([^/\\]+)[/\\](\d+)-(\d+)\.json$', 2) as bigint) as season,
        try_cast(regexp_extract(filename, '([^/\\]+)[/\\](\d+)-(\d+)\.json$', 3) as bigint) as round,
        endpoint,
        try_cast(fetched_at as timestamp) as fetched_at,
        try_cast(race_start_utc as timestamp) as race_start_utc,
        response.hourly as hourly
    from {{ source('open_meteo', 'forecasts') }}
),

hours as (
    select
        kind,
        season,
        round,
        endpoint,
        fetched_at,
        race_start_utc,
        unnest(hourly."time") as hour_raw,
        unnest(hourly.precipitation) as precipitation_mm,
        unnest(hourly.precipitation_probability) as precipitation_probability_pct,
        unnest(hourly.temperature_2m) as air_temp
    from files
)

select
    kind,
    season,
    round,
    endpoint,
    fetched_at,
    race_start_utc,
    try_cast(hour_raw as timestamp) as hour_utc,
    precipitation_mm,
    precipitation_probability_pct,
    air_temp
from hours
