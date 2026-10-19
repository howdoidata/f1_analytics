-- Every FastF1 lap with its Jolpica driver_id/constructor_id. `round` comes
-- from the extract's counts.json.
select
    laps.race_label,
    laps.season,
    counts.round,
    laps."Time",
    laps."Driver",
    laps."DriverNumber",
    laps."LapTime",
    laps."LapNumber",
    laps."Stint",
    laps."PitOutTime",
    laps."PitInTime",
    laps."Sector1Time",
    laps."Sector2Time",
    laps."Sector3Time",
    laps."Sector1SessionTime",
    laps."Sector2SessionTime",
    laps."Sector3SessionTime",
    laps."SpeedI1",
    laps."SpeedI2",
    laps."SpeedFL",
    laps."SpeedST",
    laps."IsPersonalBest",
    laps."Compound",
    laps."TyreLife",
    laps."FreshTyre",
    laps."Team",
    laps."LapStartTime",
    laps."LapStartDate",
    laps."TrackStatus",
    laps."Position",
    laps."Deleted",
    laps."DeletedReason",
    laps."FastF1Generated",
    laps."IsAccurate",
    driver_map.driver_id,
    team_map.constructor_id
from {{ ref('stg_fastf1__laps') }} as laps
left join {{ ref('stg_fastf1__counts') }} as counts
    on counts.season_folder = laps.season_folder and counts.race_label = laps.race_label
left join {{ ref('stg_fastf1__driver_code_map') }} as driver_map
    on driver_map.code = laps."Driver"
left join {{ ref('stg_fastf1__team_map') }} as team_map
    on team_map.team = laps."Team"
order by laps.season, laps.race_label
