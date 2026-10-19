select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    driverId as driver_id,
    constructorId as constructor_id,
    try_cast(position as bigint) as position,
    Q1 as q1,
    Q2 as q2,
    Q3 as q3
from {{ source('jolpica', 'qualifying') }}
