-- The race minimum stops by circuit (the `stop_rules_seed` seed): from `from_season`
-- on, a running car in a dry race at the circuit makes at least `dry_minimum`
-- stops. A circuit with no row uses the sporting rules' 1.
select circuit_id, from_season, dry_minimum
from {{ ref('stop_rules_seed') }}
