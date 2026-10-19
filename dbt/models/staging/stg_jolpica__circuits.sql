select
    circuitId as circuit_id,
    circuitName as circuit_name,
    locality,
    country,
    try_cast(lat as double) as lat,
    try_cast(long as double) as lng,
    url
from {{ source('jolpica', 'circuits') }}
