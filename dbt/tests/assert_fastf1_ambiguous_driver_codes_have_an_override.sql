-- A FastF1 Driver code that matches several Jolpica drivers and has no row in
-- the fastf1_driver_code_overrides seed. Never resolved by a heuristic.
select code, matched_driver_count
from {{ ref('stg_fastf1__driver_code_map') }}
where matched_driver_count > 1 and override_driver_id is null
