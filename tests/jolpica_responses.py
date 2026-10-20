"""Recorded Jolpica responses and the fixture world the update tests run against."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pandas as pd

from f1_analytics.data_sources import jolpica_fetch as jf


FIXTURE_RAW = Path(__file__).parent / "fixtures" / "jolpica_raw"

CIRCUITS = {
    "bahrain": {"circuitId": "bahrain", "circuitName": "Bahrain International Circuit", "url": "https://example.com/circuit/bahrain",
                "Location": {"lat": "26.0325", "long": "50.5106", "locality": "Sakhir", "country": "Bahrain"}},
    "jeddah": {"circuitId": "jeddah", "circuitName": "Jeddah Corniche Circuit", "url": "https://example.com/circuit/jeddah",
               "Location": {"lat": "21.6319", "long": "39.1044", "locality": "Jeddah", "country": "Saudi Arabia"}},
    "albert_park": {"circuitId": "albert_park", "circuitName": "Albert Park Grand Prix Circuit", "url": "https://example.com/circuit/albert_park",
                    "Location": {"lat": "-37.8497", "long": "144.968", "locality": "Melbourne", "country": "Australia"}},
}
DRIVERS = {
    "verstappen": {"driverId": "verstappen", "permanentNumber": "1", "code": "VER", "url": "https://example.com/driver/verstappen",
                   "givenName": "Max", "familyName": "Verstappen", "dateOfBirth": "1997-09-30", "nationality": "Dutch"},
    "hamilton": {"driverId": "hamilton", "permanentNumber": "44", "code": "HAM", "url": "https://example.com/driver/hamilton",
                 "givenName": "Lewis", "familyName": "Hamilton", "dateOfBirth": "1985-01-07", "nationality": "British"},
    "piastri": {"driverId": "piastri", "permanentNumber": "81", "code": "PIA", "url": "https://example.com/driver/piastri",
                "givenName": "Oscar", "familyName": "Piastri", "dateOfBirth": "2001-04-06", "nationality": "Australian"},
}
CONSTRUCTORS = {
    "red_bull": {"constructorId": "red_bull", "url": "https://example.com/constructor/red_bull", "name": "Red Bull", "nationality": "Austrian"},
    "mercedes": {"constructorId": "mercedes", "url": "https://example.com/constructor/mercedes", "name": "Mercedes", "nationality": "German"},
    "mclaren": {"constructorId": "mclaren", "url": "https://example.com/constructor/mclaren", "name": "McLaren", "nationality": "British"},
}

SCHEDULE_2025 = [
    (1, "Bahrain Grand Prix", "bahrain", "2025-03-01", "15:00:00", "https://example.com/race/2025/1"),
    (2, "Saudi Arabian Grand Prix", "jeddah", "2025-03-08", "17:00:00", "https://example.com/race/2025/2"),
    (3, "Australian Grand Prix", "albert_park", "2025-03-16", "04:00:00Z", "https://example.com/race/2025/3"),
]


def _race(season, round_, name, circuit, date, time, url, **rows):
    race = {"season": str(season), "round": str(round_), "url": url, "raceName": name,
            "Circuit": copy.deepcopy(CIRCUITS[circuit]), "date": date, "time": time}
    race.update(rows)
    return race


def _race_table(races, total=None, limit=100, offset=0, row_key=None):
    if total is None:
        total = sum(len(r.get(row_key, [])) for r in races) if row_key else len(races)
    return {"MRData": {"limit": str(limit), "offset": str(offset), "total": str(total), "RaceTable": {"Races": races}}}


def _result(position, driver, constructor, points, grid):
    return {"number": DRIVERS[driver]["permanentNumber"], "position": str(position), "positionText": str(position),
            "points": str(points), "Driver": copy.deepcopy(DRIVERS[driver]),
            "Constructor": copy.deepcopy(CONSTRUCTORS[constructor]), "grid": str(grid), "laps": "58",
            "status": "Finished", "Time": {"millis": "5000000", "time": "1:23:20.000" if position == 1 else "+1.000"},
            "FastestLap": {"rank": str(position), "lap": "40", "Time": {"time": "1:20.000"}}}


def _qualifying(position, driver, constructor):
    return {"number": DRIVERS[driver]["permanentNumber"], "position": str(position),
            "Driver": copy.deepcopy(DRIVERS[driver]), "Constructor": copy.deepcopy(CONSTRUCTORS[constructor]),
            "Q1": "1:16.000", "Q2": "1:15.500", "Q3": "1:15.000"}


def _pit_stop(driver, stop, lap):
    return {"driverId": driver, "lap": str(lap), "stop": str(stop), "time": f"15:{lap:02d}:00", "duration": "22.500"}


def _standings(season, round_, key, entries):
    return {"MRData": {"limit": "100", "offset": "0", "total": str(len(entries)),
                       "StandingsTable": {"season": str(season), "round": str(round_),
                                          "StandingsLists": [{"season": str(season), "round": str(round_), key: entries}]}}}


def recorded_responses(*, round3_run: bool = True, next_season: list | None = None) -> dict[str, dict]:
    """Recorded Jolpica responses for a world where 2025 R3 is the next round."""
    schedule = [_race(2025, *row) for row in SCHEDULE_2025]
    r3 = SCHEDULE_2025[2]
    results = [_result(1, "piastri", "mclaren", 25, 1), _result(2, "verstappen", "red_bull", 18, 2),
               _result(3, "hamilton", "mercedes", 15, 3)] if round3_run else []
    qualifying = [_qualifying(1, "piastri", "mclaren"), _qualifying(2, "verstappen", "red_bull"),
                  _qualifying(3, "hamilton", "mercedes")] if round3_run else []
    pit_stops = [_pit_stop("piastri", 1, 18), _pit_stop("hamilton", 1, 19), _pit_stop("verstappen", 1, 21),
                 _pit_stop("piastri", 2, 40)] if round3_run else []
    driver_entries = [
        {"position": "1", "positionText": "1", "points": "69", "wins": "1", "Driver": DRIVERS["hamilton"], "Constructors": [CONSTRUCTORS["mercedes"]]},
        {"position": "2", "positionText": "2", "points": "68", "wins": "1", "Driver": DRIVERS["verstappen"], "Constructors": [CONSTRUCTORS["red_bull"]]},
        {"position": "3", "positionText": "3", "points": "25", "wins": "1", "Driver": DRIVERS["piastri"], "Constructors": [CONSTRUCTORS["mclaren"]]},
    ]
    constructor_entries = [
        {"position": "1", "positionText": "1", "points": "69", "wins": "1", "Constructor": CONSTRUCTORS["mercedes"]},
        {"position": "2", "positionText": "2", "points": "68", "wins": "1", "Constructor": CONSTRUCTORS["red_bull"]},
        {"position": "3", "positionText": "3", "points": "25", "wins": "1", "Constructor": CONSTRUCTORS["mclaren"]},
    ]
    return {
        "2025/races": _race_table(schedule),
        "2025/3/results": _race_table([_race(2025, *r3, Results=results)] if results else [], row_key="Results"),
        "2025/3/sprint": _race_table([], row_key="SprintResults"),
        "2025/3/qualifying": _race_table([_race(2025, *r3, QualifyingResults=qualifying)] if qualifying else [], row_key="QualifyingResults"),
        "2025/3/pitstops": _race_table([_race(2025, *r3, PitStops=pit_stops)] if pit_stops else [], row_key="PitStops"),
        "2025/4/results": _race_table([], row_key="Results"),
        "2025/driverstandings": _standings(2025, 3, "DriverStandings", driver_entries),
        "2025/constructorstandings": _standings(2025, 3, "ConstructorStandings", constructor_entries),
        "2026/races": _race_table(next_season or []),
        "2026/1/results": _race_table([], row_key="Results"),
        "2026/1/qualifying": _race_table([], row_key="QualifyingResults"),
    }


class RecordedGetter:
    """Replays recorded responses keyed by path; records every call."""

    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, params: dict) -> dict:
        self.calls.append((url, dict(params)))
        assert url.startswith(jf.BASE_URL) and url.endswith(".json")
        path = url[len(jf.BASE_URL):-len(".json")]
        if path not in self.responses:
            raise AssertionError(f"unexpected request: {path}")
        return copy.deepcopy(self.responses[path])


def make_update_world(target: Path) -> Path:
    """The jolpica_raw fixture world at `target`, with 2025 R3 scheduled but not yet run."""
    shutil.copytree(FIXTURE_RAW, target)
    races = jf.read_raw_table(target, "races")
    r3 = SCHEDULE_2025[2]
    extra = pd.DataFrame([{"season": "2025", "round": "3", "raceName": r3[1], "circuitId": r3[2], "date": r3[3],
                           "time": r3[4], "url": r3[5]}])
    jf.write_raw_table(target, "races", pd.concat([races, extra]))
    circuits = jf.read_raw_table(target, "circuits")
    jf.write_raw_table(target, "circuits", pd.concat([circuits, jf.flatten_circuits([_race(2025, *r3)])]))
    return target
