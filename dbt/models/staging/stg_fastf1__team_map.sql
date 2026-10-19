-- FastF1 `Team` name -> Jolpica constructor_id.
-- (1) exact match on constructors.name; (2) the fastf1_team_aliases seed, but
-- only when its target exists in constructors; (3) anything else stays NULL and
-- fails the fastf1_team_names_resolve test. Never a fuzzy match.
with teams as (
    select distinct "Team" as team
    from {{ ref('stg_fastf1__laps') }}
),

exact as (
    select name, min(constructor_id) as constructor_id
    from {{ ref('stg_jolpica__constructors') }}
    group by name
),

aliases as (
    select aliases.team, aliases.constructor_id
    from {{ ref('fastf1_team_aliases') }} as aliases
    inner join {{ ref('stg_jolpica__constructors') }} as constructors
        on constructors.constructor_id = aliases.constructor_id
)

select
    teams.team,
    exact.constructor_id as exact_constructor_id,
    aliases.constructor_id as alias_constructor_id,
    coalesce(exact.constructor_id, aliases.constructor_id) as constructor_id
from teams
left join exact on exact.name = teams.team
left join aliases on aliases.team = teams.team
