-- A FastF1 Driver code (or a missing one) that matches no Jolpica drivers.code.
select code, matched_driver_count
from {{ ref('stg_fastf1__driver_code_map') }}
where matched_driver_count = 0
