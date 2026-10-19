-- A FastF1 Team name (or a missing one) with no exact constructors.name match
-- and no alias whose target exists in constructors.
select team
from {{ ref('stg_fastf1__team_map') }}
where constructor_id is null
