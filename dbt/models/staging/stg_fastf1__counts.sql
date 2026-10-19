-- One row per extract: the session's own totals, written by fastf1_fetch.py.
-- `round` here is the round every FastF1 table carries.
select
    regexp_extract(filename, '([^/\\]+)[/\\]([^/\\]+)[/\\][^/\\]+$', 2) as race_label,
    regexp_extract(filename, '([^/\\]+)[/\\]([^/\\]+)[/\\][^/\\]+$', 1) as season_folder,
    try_cast(season_folder as bigint) as season,
    try_cast(round as bigint) as round,
    round as round_raw,
    try_cast(lap_count as bigint) as lap_count,
    try_cast(weather_count as bigint) as weather_count,
    drivers
from {{ source('fastf1', 'counts') }}
