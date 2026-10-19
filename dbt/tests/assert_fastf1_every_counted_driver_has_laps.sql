-- A driver listed in counts.json with no lap in the extract.
with expected as (
    select season_folder, race_label, unnest(drivers) as driver_code
    from {{ ref('stg_fastf1__counts') }}
),

landed as (
    select distinct season_folder, race_label, "Driver" as driver_code
    from {{ ref('stg_fastf1__laps') }}
)

select expected.season_folder, expected.race_label, expected.driver_code
from expected
left join landed using (season_folder, race_label, driver_code)
where landed.driver_code is null
