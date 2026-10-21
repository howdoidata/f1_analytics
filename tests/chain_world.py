"""The chain fixture world: a raw tree for stories 4-6's end-to-end chain test.

`fixtures/chain_raw/` holds every Jolpica CSV, the FastF1 summaries and one
practice stints file for a small world kept apart from the shared
`fixtures/jolpica_raw/` (whose pins it must not move):

- red_bull, mercedes and aston_martin, two drivers each;
- 2023 R1-R3 (bahrain, jeddah, albert_park) and 2022 R1 (bahrain), so the
  chain team has three races in one season and a non-COTA circuit it raced
  at in an earlier season;
- `car_races` rows for every car of every race, and track-status periods of
  all three statuses (2023 R2 has an sc / red_flag overlap; 2023 R3 none);
- a 2023 R1 FP2 stints file;
- day-before forecasts for 2023 R1-R3 and a live forecast (kind `forecast`)
  for 2023 R3 at albert_park, rain chance 0.4 in the race window.

`make_chain_world` copies it and adds one FastF1 extract (the `normal_race`
fixture, VER/HAM/ALO) as 2023 R1, since the `fastf1` sources fail on no match.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"
CHAIN_RAW = FIXTURES / "chain_raw"
# The non-Williams team the chain test follows.
CHAIN_TEAM = "mercedes"
CHAIN_SEASON = 2023
CHAIN_ROUNDS = (1, 2, 3)
# The same non-COTA circuit, raced in an earlier season.
CHAIN_CIRCUIT = "bahrain"
CHAIN_EARLIER_SEASON = 2022
CHAIN_EXTRACT = (2023, 1, "01-bahrain-grand-prix")


def make_chain_world(target: Path) -> Path:
    """Copy the chain tree to `target` (the raw root) and add its FastF1 extract; returns `target`."""
    shutil.copytree(CHAIN_RAW, target)
    season, round_, dir_name = CHAIN_EXTRACT
    extract = target / "fastf1" / str(season) / dir_name
    shutil.copytree(FIXTURES / "fastf1_csv" / "normal_race", extract)
    counts = json.loads((extract / "counts.json").read_text())
    counts.update({"season": season, "round": round_, "race_label": dir_name})
    (extract / "counts.json").write_text(json.dumps(counts))
    return target
