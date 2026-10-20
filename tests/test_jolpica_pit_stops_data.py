"""Real-data checks on the committed `data/raw/jolpica/pit_stops.csv`.

The per-race counts are pinned from the forge probe
(`forge-pit-stop-counts.md`, captured 2026-10-19 from Jolpica's
`<season>/<round>/pitstops` endpoint). Offline: reads committed CSVs only.
"""

from __future__ import annotations

import pytest

from f1_analytics.config import JOLPICA_RAW_DIR
from f1_analytics.data_sources import jolpica_fetch as jf


COUNTS_2026 = {1: 32, 2: 19, 3: 29, 4: 22, 5: 34, 6: 86, 7: 48, 8: 41, 9: 51, 10: 28, 11: 45, 12: 65, 13: 30,
               14: 25, 15: 36, 16: 73, 17: 25}
# COTA (`circuitId == "americas"`) by season; no race there in 2020.
COUNTS_COTA = {2012: 24, 2013: 27, 2014: 36, 2015: 47, 2016: 43, 2017: 25, 2018: 24, 2019: 33, 2021: 41,
               2022: 36, 2023: 36, 2024: 23, 2025: 21}

# Rounds from 2011 to 2026 R17 that have results but no stop rows in Jolpica.
ALLOWLIST: dict[tuple[int, int], str] = {
    (2021, 12): "Belgian GP: run behind the safety car for a few laps and red-flagged, so no "
                "racing pit stops were recorded; Jolpica's 2021/12/pitstops returns total 0",
}

LAST_CHECKED = (2026, 17)


@pytest.fixture(scope="module")
def stop_counts() -> dict[tuple[int, int], int]:
    stops = jf.read_raw_table(JOLPICA_RAW_DIR, "pit_stops")
    keys = zip(stops["season"].astype(int), stops["round"].astype(int))
    counts: dict[tuple[int, int], int] = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    return counts


def test_2026_round_counts_match_the_forge_probe(stop_counts):
    assert {round_: stop_counts.get((2026, round_), 0) for round_ in COUNTS_2026} == COUNTS_2026
    assert sum(COUNTS_2026.values()) == 689


def test_cota_counts_match_the_forge_probe(stop_counts):
    races = jf.read_raw_table(JOLPICA_RAW_DIR, "races")
    cota = races[(races["circuitId"] == "americas") & races["season"].astype(int).between(2012, 2025)]
    rounds = {int(season): int(round_) for season, round_ in zip(cota["season"], cota["round"])}
    assert set(rounds) == set(COUNTS_COTA)
    assert {season: stop_counts.get((season, round_), 0) for season, round_ in rounds.items()} == COUNTS_COTA
    assert sum(COUNTS_COTA.values()) == 416


def test_every_round_with_results_from_2011_has_stops_unless_allowlisted(stop_counts):
    results = jf.read_raw_table(JOLPICA_RAW_DIR, "results")
    with_results = {
        (int(season), int(round_))
        for season, round_ in zip(results["season"], results["round"])
        if jf.PIT_STOPS_FIRST_SEASON <= int(season) and (int(season), int(round_)) <= LAST_CHECKED
    }
    missing = {key for key in with_results if key not in stop_counts}
    assert missing == set(ALLOWLIST)
    # Stops only for rounds that have results.
    assert set(stop_counts) <= with_results | {key for key in stop_counts if key > LAST_CHECKED}


def test_pit_stops_csv_has_the_raw_columns_and_starts_in_2011():
    stops = jf.read_raw_table(JOLPICA_RAW_DIR, "pit_stops")
    assert list(stops.columns) == jf.RAW_COLUMNS["pit_stops"]
    assert int(stops["season"].astype(int).min()) == jf.PIT_STOPS_FIRST_SEASON
    assert stops[["driverId", "stop", "lap"]].notna().all().all()
