{#- Cumulative standings by round, shared by the driver and constructor tables.

    Race and sprint rows are summed per season/round/race_name/date/id/name.
    Sprint points add to their round; a sprint win is not a race win. `date`
    comes from races. The running totals reset each season, and standing_rank is
    standard competition ranking ("1224") on (cumulative_points desc,
    cumulative_wins desc): points first, wins break ties, an exact tie shares
    the rank and the next row skips the consumed positions. -#}
{% macro cumulative_standings(id_column, name_column) -%}
with classified as (
    select season, round, race_name, {{ id_column }}, {{ name_column }}, points, position
    from {{ ref('results') }}
    union all
    select season, round, race_name, {{ id_column }}, {{ name_column }}, points, cast(null as bigint) as position
    from {{ ref('sprint_results') }}
),

dated as (
    select classified.*, races.date
    from classified
    left join {{ ref('races') }} as races
        on races.season = classified.season and races.round = classified.round
),

per_round as (
    select
        season,
        round,
        race_name,
        date,
        {{ id_column }},
        {{ name_column }},
        cast(coalesce(fsum(points), 0) as double) as race_points,
        cast(coalesce(bool_or(position = 1), false) as bigint) as race_wins
    from dated
    group by season, round, race_name, date, {{ id_column }}, {{ name_column }}
),

cumulative as (
    select
        *,
        sum(race_points) over season_to_date as cumulative_points,
        cast(sum(race_wins) over season_to_date as bigint) as cumulative_wins
    from per_round
    window season_to_date as (
        partition by season, {{ id_column }}
        order by round
        rows between unbounded preceding and current row
    )
)

select
    *,
    cast(rank() over (
        partition by season, round
        order by cumulative_points desc nulls last, cumulative_wins desc nulls last
    ) as bigint) as standing_rank
from cumulative
order by season, round, standing_rank, {{ id_column }}
{%- endmacro %}
