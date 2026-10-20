-- Jolpica pit stops, typed. `duration` is `ss.fff`, `m:ss.fff` or `mm:ss.fff`
-- (one bare `24`); it is parsed in DECIMAL so 1:29.401 is exactly 89.401 s.
-- An empty duration stays NULL.
select
    try_cast(season as bigint) as season,
    try_cast(round as bigint) as round,
    driverId as driver_id,
    try_cast(stop as bigint) as stop,
    try_cast(lap as bigint) as lap,
    time,
    try_cast(
        case
            when duration like '%:%'
                then try_cast(split_part(duration, ':', 1) as decimal(18, 3)) * 60
                    + try_cast(split_part(duration, ':', 2) as decimal(18, 3))
            else try_cast(duration as decimal(18, 3))
        end
        as double
    ) as duration_s
from {{ source('jolpica', 'pit_stops') }}
