select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    raceName as race_name,
    circuitId as circuit_id,
    try_cast(date as date) as date,
    time,
    url
from {{ source('jolpica', 'races') }}
