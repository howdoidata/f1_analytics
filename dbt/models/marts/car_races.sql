-- One row per car per race with a FastF1 summary (story 2), typed.
select * from {{ ref('stg_fastf1_summary__car_races') }}
