-- Every extract folder has a non-empty laps.csv, a weather.csv and a counts.json.
with laps as (select distinct season_folder, race_label from {{ ref('stg_fastf1__laps') }}),
weather as (select distinct season_folder, race_label from {{ ref('stg_fastf1__weather') }}),
counts as (select distinct season_folder, race_label from {{ ref('stg_fastf1__counts') }}),
folders as (
    select * from laps
    union
    select * from weather
    union
    select * from counts
)

select
    folders.season_folder,
    folders.race_label,
    laps.race_label is not null as has_laps,
    weather.race_label is not null as has_weather,
    counts.race_label is not null as has_counts
from folders
left join laps using (season_folder, race_label)
left join weather using (season_folder, race_label)
left join counts using (season_folder, race_label)
where laps.race_label is null or weather.race_label is null or counts.race_label is null
