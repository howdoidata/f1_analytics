-- SC, VSC and red-flag periods per race, by lap; both end laps belong to the period.
select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    status,
    try_cast(start_lap as bigint) as start_lap,
    try_cast(end_lap as bigint) as end_lap
from {{ source('fastf1_summary', 'track_status_periods') }}
