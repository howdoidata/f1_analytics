-- One row per race, forecast kind and forecast hour (UTC), from every committed
-- data/raw/open_meteo/<kind>/<season>-<RR>.json file. Probability is 0-1.
select
    season,
    round,
    kind,
    hour_utc,
    endpoint,
    fetched_at,
    race_start_utc,
    precipitation_probability_pct / 100.0 as precipitation_probability,
    precipitation_mm,
    air_temp
from {{ ref('stg_open_meteo__forecasts') }}
