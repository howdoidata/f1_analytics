-- FastF1 `Driver` code -> Jolpica driver_id, never by DriverNumber.
-- (1) a code matching exactly one driver_id resolves to it; (2) a code matching
-- several (codes are reused across eras) resolves through the
-- fastf1_driver_code_overrides seed; (3) anything else stays NULL and fails the
-- fastf1_driver_codes_* tests.
with codes as (
    select distinct "Driver" as code
    from {{ ref('stg_fastf1__laps') }}
),

matches as (
    select
        code,
        count(distinct driver_id) as matched_driver_count,
        min(driver_id) as matched_driver_id
    from {{ ref('stg_jolpica__drivers') }}
    where code is not null
    group by code
)

select
    codes.code,
    coalesce(matches.matched_driver_count, 0) as matched_driver_count,
    overrides.driver_id as override_driver_id,
    case
        when matches.matched_driver_count = 1 then matches.matched_driver_id
        when matches.matched_driver_count > 1 then overrides.driver_id
    end as driver_id
from codes
left join matches on matches.code = codes.code
left join {{ ref('fastf1_driver_code_overrides') }} as overrides on overrides.code = codes.code
