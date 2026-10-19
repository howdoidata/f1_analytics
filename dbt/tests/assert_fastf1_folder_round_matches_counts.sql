-- The <RR> prefix of an extract folder must be the round in its counts.json.
select season_folder, race_label, round_raw
from {{ ref('stg_fastf1__counts') }}
where not regexp_full_match(split_part(race_label, '-', 1), '[0-9]+')
    or round is null
    or cast(split_part(race_label, '-', 1) as bigint) != round
