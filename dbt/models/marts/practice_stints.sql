-- One row per practice stint, from every committed practice stints file.
select * from {{ ref('stg_fastf1_practice__stints') }}
