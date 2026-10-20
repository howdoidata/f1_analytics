"""Offline tests for `uv run fetch-sessions` and `fastf1_summary`.

A fake fastf1-like module (the `tests/test_fastf1_fetch.py` pattern) stands in
for FastF1, and a temp raw dir holds minimal Jolpica `races.csv` and
`results.csv`, so nothing touches the network or the committed data.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import jwt
import pandas as pd
import pytest

from f1_analytics import fetch_sessions
from f1_analytics.cli import LOGIN_COMMAND
from f1_analytics.data_sources import fastf1_summary as summary


# --------------------------------------------------------------------------
# Fake FastF1
# --------------------------------------------------------------------------


class RetryableError(Exception):
    pass


class _FakeExceptions:
    RateLimitExceededError = RetryableError


class _FakeCachedSession:
    def __init__(self) -> None:
        self.auth = None


class _FakeCache:
    def __init__(self) -> None:
        self.enable_calls: list[str] = []
        self._requests_session_cached: _FakeCachedSession | None = None

    def enable_cache(self, path: str) -> None:
        self.enable_calls.append(path)
        self._requests_session_cached = _FakeCachedSession()


class _FakeSession:
    def __init__(self, laps: pd.DataFrame, weather_data: pd.DataFrame | None = None) -> None:
        self.laps = laps
        self.weather_data = weather_data if weather_data is not None else _weather()

    def load(self, **kwargs: Any) -> None:
        pass


class _FakeFastF1:
    """`get_session` serves `sessions[(season, round, identifier)]`; a missing key is FastF1's ValueError."""

    def __init__(self, sessions: dict[tuple[int, int, str], _FakeSession] | None = None) -> None:
        self.Cache = _FakeCache()
        self.exceptions = _FakeExceptions()
        self.sessions = sessions or {}
        self.get_session_calls: list[tuple] = []

    def get_session(self, season: int, round_number: int, identifier: str) -> _FakeSession:
        self.get_session_calls.append((season, round_number, identifier))
        try:
            return self.sessions[(season, round_number, identifier)]
        except KeyError:
            raise ValueError(f"Session type '{identifier}' does not exist for this event") from None


# --------------------------------------------------------------------------
# Frames and the temp raw dir
# --------------------------------------------------------------------------

RACES = [
    # season, round, raceName, circuitId, date
    (2017, 17, "United States Grand Prix", "americas", "2017-10-22"),
    (2018, 18, "United States Grand Prix", "americas", "2018-10-21"),
    (2018, 19, "Mexican Grand Prix", "rodriguez", "2018-10-28"),
    (2026, 12, "Dutch Grand Prix", "zandvoort", "2026-08-23"),
    (2026, 13, "Italian Grand Prix", "monza", "2026-09-06"),
    (2026, 14, "Spanish Grand Prix", "madring", "2026-09-13"),
    (2026, 18, "United States Grand Prix", "americas", "2026-10-25"),
]
CARS = [("1", "max_verstappen", "red_bull"), ("44", "hamilton", "ferrari"), ("23", "albon", "williams")]


def _write_jolpica(raw_dir: Path, *, results_rounds=((2017, 17), (2018, 18), (2018, 19), (2026, 12), (2026, 13), (2026, 14))) -> None:
    jolpica = raw_dir / "jolpica"
    jolpica.mkdir(parents=True)
    pd.DataFrame(
        [{"season": s, "round": r, "raceName": n, "circuitId": c, "date": d, "time": "13:00:00Z", "url": ""} for s, r, n, c, d in RACES]
    ).to_csv(jolpica / "races.csv", index=False)
    names = {(s, r): n for s, r, n, _, _ in RACES}
    pd.DataFrame(
        [
            {"season": s, "round": r, "raceName": names[(s, r)], "number": num, "driverId": d, "constructorId": c}
            for s, r in results_rounds
            for num, d, c in CARS
        ]
    ).to_csv(jolpica / "results.csv", index=False)


def _td(seconds: float) -> pd.Timedelta:
    return pd.Timedelta(round(seconds * 1e9), unit="ns")


def _laps(
    cars=("1", "44", "23"),
    n_laps: int = 8,
    compound: str = "MEDIUM",
    status: dict[int, str] | None = None,
    pit_lap: int | None = None,
    second_compound: str = "HARD",
) -> pd.DataFrame:
    """`n_laps` laps per car; an optional pit at the end of `pit_lap` starts stint 2 on `second_compound`."""
    status = status or {}
    rows = []
    for car in cars:
        start = 3600.0
        stint, tyre_life = 1, 0
        for lap in range(1, n_laps + 1):
            tyre_life += 1
            lap_time = 90.0 + 0.1 * tyre_life
            rows.append(
                {
                    "Driver": f"D{car}",
                    "DriverNumber": car,
                    "LapNumber": float(lap),
                    "Stint": float(stint),
                    "PitInTime": start + lap_time if lap == pit_lap else float("nan"),
                    "PitOutTime": start if pit_lap and lap == pit_lap + 1 else float("nan"),
                    "Compound": compound if stint == 1 else second_compound,
                    "TyreLife": float(tyre_life),
                    "LapTime": _td(lap_time),
                    "LapStartTime": _td(start),
                    "Time": _td(start + lap_time),
                    "TrackStatus": status.get(lap, "1"),
                    "IsAccurate": lap != 1,
                }
            )
            start += lap_time
            if lap == pit_lap:
                stint, tyre_life = 2, 0
    frame = pd.DataFrame(rows)
    # FastF1's pit columns are timedeltas even when every value is missing.
    for column in ("PitInTime", "PitOutTime"):
        frame[column] = pd.to_timedelta(frame[column], unit="s")
    return frame


def _weather() -> pd.DataFrame:
    return pd.DataFrame(
        {
            # The first row is before the race start, so it is out of the means.
            "Time": [_td(0), _td(3700), _td(4000)],
            "AirTemp": [10.0, 20.0, 22.0],
            "TrackTemp": [15.0, 30.0, 34.0],
            "Rainfall": [False, False, False],
        }
    )


def _token(path: Path, *, exp: float | None = None) -> Path:
    path.write_text(jwt.encode({"exp": int(exp if exp is not None else time.time() + 3600)}, "test-secret-of-at-least-32-bytes!", algorithm="HS256"))
    return path


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    _write_jolpica(raw)
    return raw


@pytest.fixture
def token_path(tmp_path: Path) -> Path:
    return _token(tmp_path / "f1auth.json")


def _run(argv, raw_dir: Path, token_path: Path | None, fake: _FakeFastF1 | None = None) -> int:
    return fetch_sessions.main(
        argv, token_path=token_path, raw_dir=raw_dir, cache_dir=raw_dir / "fastf1_cache", fastf1_module=fake or _FakeFastF1()
    )


def _read(raw_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(raw_dir / "fastf1_summary" / name, dtype=str, keep_default_na=False)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --------------------------------------------------------------------------
# Race list
# --------------------------------------------------------------------------


def test_race_list_comes_from_the_races_table_and_skips_races_without_results(raw_dir, token_path, capsys):
    fake = _FakeFastF1({(2018, 18, "R"): _FakeSession(_laps(compound="SUPERSOFT"))})
    rc = _run(["--circuit", "americas", "--since", "2018", "--session", "R"], raw_dir, token_path, fake)
    out = capsys.readouterr().out
    assert rc == 0
    # 2017 is before --since, Mexico is another circuit, 2026 R18 has no results.
    assert fake.get_session_calls == [(2018, 18, "R")]
    assert "[fetch-sessions] 2026 R18: no results yet, skipped" in out
    assert set(_read(raw_dir, "car_races.csv")["circuit_id"]) == {"americas"}


def test_unknown_circuit_exits_1_and_writes_nothing(raw_dir, token_path, capsys):
    before = _snapshot(raw_dir)
    fake = _FakeFastF1()
    assert _run(["--circuit", "nowhere"], raw_dir, token_path, fake) == 1
    assert "[fetch-sessions] unknown circuit_id 'nowhere'" in capsys.readouterr().err
    assert fake.get_session_calls == []
    assert _snapshot(raw_dir) == before


def test_unknown_round_exits_1_and_writes_nothing(raw_dir, token_path, capsys):
    before = _snapshot(raw_dir)
    fake = _FakeFastF1()
    assert _run(["--season", "2026", "--round", "30"], raw_dir, token_path, fake) == 1
    assert "[fetch-sessions] no round 30 in season 2026" in capsys.readouterr().err
    assert fake.get_session_calls == []
    assert _snapshot(raw_dir) == before


# --------------------------------------------------------------------------
# Token
# --------------------------------------------------------------------------


def _bad_token(kind: str, tmp_path: Path) -> Path:
    path = tmp_path / "f1auth.json"
    if kind == "missing":
        return path
    if kind == "empty":
        path.write_text("")
    elif kind == "garbage":
        path.write_text("not-a-jwt")
    elif kind == "expired":
        _token(path, exp=time.time() - 60)
    return path


@pytest.mark.parametrize("kind", ["missing", "empty", "garbage", "expired"])
def test_a_bad_token_stops_before_any_fastf1_call_and_changes_no_file(kind, raw_dir, tmp_path, capsys):
    # Existing summaries must survive byte-for-byte.
    fake_ok = _FakeFastF1({(2026, 13, "R"): _FakeSession(_laps())})
    assert _run(["--season", "2026", "--round", "13"], raw_dir, _token(tmp_path / "good.json"), fake_ok) == 0
    capsys.readouterr()
    before = _snapshot(raw_dir)

    fake = _FakeFastF1({(2026, 13, "R"): _FakeSession(_laps())})
    rc = _run(["--season", "2026", "--round", "13"], raw_dir, _bad_token(kind, tmp_path), fake)
    err = capsys.readouterr().err

    assert rc == 1
    assert fake.get_session_calls == []
    assert fake.Cache.enable_calls == []
    assert _snapshot(raw_dir) == before
    first_line = err.splitlines()[0]
    assert first_line.startswith("[fetch-sessions] ") and first_line.endswith(".")
    assert f"[fetch-sessions] Log in to F1TV, then rerun:\n\n    {LOGIN_COMMAND}\n" in err


def test_from_extracts_needs_no_token(raw_dir, tmp_path):
    _write_extract(raw_dir, 2026, 13, "italian-grand-prix")
    fake = _FakeFastF1()
    rc = _run(["--from-extracts", "--season", "2026"], raw_dir, tmp_path / "no-such-token.json", fake)
    assert rc == 0
    assert fake.get_session_calls == []


# --------------------------------------------------------------------------
# Car rows
# --------------------------------------------------------------------------


def test_car_rows_match_jolpica_results_on_car_number(raw_dir, token_path):
    fake = _FakeFastF1({(2026, 13, "R"): _FakeSession(_laps(n_laps=20, pit_lap=10))})
    assert _run(["--season", "2026", "--round", "13"], raw_dir, token_path, fake) == 0
    cars = _read(raw_dir, "car_races.csv")
    assert list(cars.columns) == summary.CAR_RACE_COLUMNS
    assert list(cars["driver_id"]) == ["albon", "hamilton", "max_verstappen"]
    albon = cars.iloc[0].to_dict()
    assert albon == {
        "season": "2026",
        "round": "13",
        "circuit_id": "monza",
        "driver_id": "albon",
        "constructor_id": "williams",
        "driver_number": "23",
        "laps_completed": "20",
        "stints": "2",
        "stops_fastf1": "1",
        "start_compound": "MEDIUM",
        "start_compound_raw": "MEDIUM",
        "compounds_used": "MEDIUM|HARD",
        "wet_laps": "0",
        # Only the rows from the first lap start to the last lap end.
        "air_temp_mean": "21.00",
        "track_temp_mean": "32.00",
        "rainfall": "false",
        # Lap time rises 0.1 s per lap of TyreLife.
        "deg_s_per_lap": "0.1000",
    }
    assert fake.get_session_calls == [(2026, 13, "R")]


def test_an_unmatched_race_car_fails_that_race_only(raw_dir, token_path, capsys):
    fake = _FakeFastF1(
        {
            (2026, 12, "R"): _FakeSession(_laps(cars=("1", "44", "23", "99"))),
            (2026, 13, "R"): _FakeSession(_laps()),
        }
    )
    rc = _run(["--season", "2026"], raw_dir, token_path, fake)
    err = capsys.readouterr().err
    assert rc == 1
    assert "[fetch-sessions] 2026 R12: car number 99 not in Jolpica results" in err
    cars = _read(raw_dir, "car_races.csv")
    assert set(cars["round"]) == {"13"}
    assert "12" not in set(_read(raw_dir, "track_status_periods.csv")["round"])


def test_a_car_with_no_laps_gets_a_zero_lap_row():
    laps = _laps(cars=("1", "44"))
    results = pd.DataFrame({"number": [n for n, _, _ in CARS], "driverId": [d for _, d, _ in CARS], "constructorId": [c for _, _, c in CARS]})
    rows = summary.car_race_rows(laps, _weather(), results, season=2026, round_number=13, circuit_id="monza")
    albon = rows[rows["driver_id"] == "albon"].iloc[0]
    assert albon["laps_completed"] == "0"
    for column in ["stints", "stops_fastf1", "start_compound", "start_compound_raw", "compounds_used", "wet_laps", "deg_s_per_lap"]:
        assert albon[column] == "", column
    assert len(rows) == 3


# --------------------------------------------------------------------------
# Compounds
# --------------------------------------------------------------------------


def test_old_compound_names_map_by_hardness_and_keep_the_raw_name(raw_dir, token_path):
    laps = _laps(n_laps=12, compound="ULTRASOFT", pit_lap=6, second_compound="SOFT")
    laps.loc[laps["DriverNumber"] == "44", "Compound"] = "SUPERSOFT"
    laps.loc[(laps["DriverNumber"] == "23") & (laps["LapNumber"] > 6), "Compound"] = "INTERMEDIATE"
    fake = _FakeFastF1({(2018, 18, "R"): _FakeSession(laps)})
    assert _run(["--circuit", "americas", "--since", "2018"], raw_dir, token_path, fake) == 0
    cars = _read(raw_dir, "car_races.csv").set_index("driver_id")
    assert cars.loc["max_verstappen", ["start_compound", "start_compound_raw", "compounds_used"]].tolist() == [
        "SOFT",
        "ULTRASOFT",
        "SOFT|HARD",
    ]
    assert cars.loc["hamilton", ["start_compound", "start_compound_raw"]].tolist() == ["MEDIUM", "SUPERSOFT"]
    assert cars.loc["albon", ["compounds_used", "wet_laps"]].tolist() == ["SOFT|INTERMEDIATE", "6"]


def test_a_pre_2019_race_without_an_allocation_is_not_written(raw_dir, token_path, capsys):
    fake = _FakeFastF1({(2018, 19, "R"): _FakeSession(_laps(compound="HYPERSOFT"))})
    rc = _run(["--season", "2018", "--round", "19"], raw_dir, token_path, fake)
    assert rc == 1
    assert "[fetch-sessions] 2018 R19: no compound allocation for a pre-2019 race" in capsys.readouterr().err
    assert not (raw_dir / "fastf1_summary" / "car_races.csv").exists()


def test_wet_compounds_pass_through_every_season():
    assert summary.normalise_compound("INTERMEDIATE", 2018, 18) == "INTERMEDIATE"
    assert summary.normalise_compound("WET", 2026, 1) == "WET"
    assert summary.normalise_compound("SOFT", 2026, 1) == "SOFT"
    assert summary.normalise_compound("UNKNOWN", 2026, 1) == ""


# --------------------------------------------------------------------------
# Track status
# --------------------------------------------------------------------------


def _status_laps(codes: dict[int, list[str]]) -> pd.DataFrame:
    """One row per (lap, car code) -- each list entry is a different car's TrackStatus."""
    return pd.DataFrame(
        [{"LapNumber": float(lap), "TrackStatus": code} for lap, per_car in codes.items() for code in per_car]
    )


def test_track_status_periods_cover_each_status_and_the_precedence():
    laps = _status_laps(
        {
            1: ["1", "1"],
            2: ["4", "1"],  # one car's lap shows SC -> the lap is sc
            3: ["4", "4"],
            4: ["671", "1"],  # VSC deployed and ending
            5: ["6", "6"],
            6: ["7", "1"],
            7: ["1", "1"],
            8: ["5", "4"],  # red over SC
            9: ["4", "6"],  # SC over VSC
            10: ["1", "1"],
            11: ["24", "1"],
        }
    )
    periods = summary.track_status_periods(laps, season=2026, round_number=13)
    assert periods.to_dict("records") == [
        {"season": "2026", "round": "13", "status": "sc", "start_lap": "2", "end_lap": "3"},
        {"season": "2026", "round": "13", "status": "vsc", "start_lap": "4", "end_lap": "6"},
        {"season": "2026", "round": "13", "status": "red_flag", "start_lap": "8", "end_lap": "8"},
        {"season": "2026", "round": "13", "status": "sc", "start_lap": "9", "end_lap": "9"},
        {"season": "2026", "round": "13", "status": "sc", "start_lap": "11", "end_lap": "11"},
    ]


def test_track_status_read_as_numbers_from_csv_keeps_its_codes():
    # A CSV read without dtype turns `671` into 671.0 when the column has gaps.
    laps = pd.DataFrame({"LapNumber": [1.0, 2.0, 3.0], "TrackStatus": [1.0, 671.0, float("nan")]})
    periods = summary.track_status_periods(laps, season=2026, round_number=1)
    assert periods[["status", "start_lap", "end_lap"]].values.tolist() == [["vsc", "2", "2"]]


def test_a_race_with_no_track_status_events_has_no_rows(raw_dir, token_path):
    fake = _FakeFastF1({(2026, 13, "R"): _FakeSession(_laps())})
    assert _run(["--season", "2026", "--round", "13"], raw_dir, token_path, fake) == 0
    periods = _read(raw_dir, "track_status_periods.csv")
    assert list(periods.columns) == summary.TRACK_STATUS_COLUMNS
    assert periods.empty


def test_the_race_command_writes_track_status_periods(raw_dir, token_path):
    fake = _FakeFastF1({(2026, 13, "R"): _FakeSession(_laps(status={3: "4", 4: "4", 6: "5"}))})
    assert _run(["--season", "2026", "--round", "13"], raw_dir, token_path, fake) == 0
    periods = _read(raw_dir, "track_status_periods.csv")
    assert periods[["status", "start_lap", "end_lap"]].values.tolist() == [["sc", "3", "4"], ["red_flag", "6", "6"]]


# --------------------------------------------------------------------------
# Reruns
# --------------------------------------------------------------------------


def test_a_rerun_replaces_the_race_rows_and_leaves_the_rest_byte_identical(raw_dir, token_path):
    sessions = {
        (2026, 12, "R"): _FakeSession(_laps(status={2: "4"})),
        (2026, 13, "R"): _FakeSession(_laps(status={3: "6"})),
        (2026, 14, "R"): _FakeSession(_laps(status={4: "5"})),
    }
    assert _run(["--season", "2026"], raw_dir, token_path, _FakeFastF1(sessions)) == 0
    car_path = raw_dir / "fastf1_summary" / "car_races.csv"
    status_path = raw_dir / "fastf1_summary" / "track_status_periods.csv"
    car_before, status_before = car_path.read_text(), status_path.read_text()

    # Same data again: nothing changes at all.
    assert _run(["--season", "2026", "--round", "13"], raw_dir, token_path, _FakeFastF1(sessions)) == 0
    assert car_path.read_text() == car_before and status_path.read_text() == status_before

    # New data for R13: only R13's lines change, and none are duplicated.
    sessions[(2026, 13, "R")] = _FakeSession(_laps(n_laps=9, status={5: "4"}))
    assert _run(["--season", "2026", "--round", "13"], raw_dir, token_path, _FakeFastF1(sessions)) == 0
    for path, before in [(car_path, car_before), (status_path, status_before)]:
        old_lines, new_lines = before.splitlines(), path.read_text().splitlines()
        assert [line for line in old_lines if not line.startswith("2026,13,")] == [
            line for line in new_lines if not line.startswith("2026,13,")
        ]
        assert len(new_lines) == len(set(new_lines))
    cars = _read(raw_dir, "car_races.csv")
    assert (cars["round"] == "13").sum() == 3
    assert set(cars.loc[cars["round"] == "13", "laps_completed"]) == {"9"}
    periods = _read(raw_dir, "track_status_periods.csv")
    assert periods.loc[periods["round"] == "13", ["status", "start_lap"]].values.tolist() == [["sc", "5"]]


# --------------------------------------------------------------------------
# From extracts
# --------------------------------------------------------------------------


def _write_extract(raw_dir: Path, season: int, round_number: int, slug: str, laps: pd.DataFrame | None = None) -> Path:
    """An extract folder written the way `fetch_race` writes one (`to_csv` of FastF1 frames)."""
    folder = raw_dir / "fastf1" / str(season) / f"{round_number:02d}-{slug}"
    folder.mkdir(parents=True)
    (laps if laps is not None else _laps(status={2: "671"})).to_csv(folder / "laps.csv", index=False)
    _weather().to_csv(folder / "weather.csv", index=False)
    (folder / "counts.json").write_text("{}")
    return folder


def test_from_extracts_summarises_every_committed_round_with_no_fastf1_call(raw_dir, tmp_path):
    _write_extract(raw_dir, 2026, 12, "dutch-grand-prix")
    _write_extract(raw_dir, 2026, 13, "italian-grand-prix", _laps(n_laps=20, pit_lap=10))
    extracts_before = _snapshot(raw_dir / "fastf1")
    fake = _FakeFastF1()

    rc = fetch_sessions.main(
        ["--from-extracts", "--season", "2026"], token_path=tmp_path / "none.json", raw_dir=raw_dir, fastf1_module=fake
    )

    assert rc == 0
    assert fake.get_session_calls == [] and fake.Cache.enable_calls == []
    cars = _read(raw_dir, "car_races.csv")
    assert sorted(set(cars["round"]), key=int) == ["12", "13"]
    albon = cars[(cars["round"] == "13") & (cars["driver_id"] == "albon")].iloc[0]
    # Extract strings ("0 days 01:00:00", "1.0") read the same as FastF1's typed frames.
    assert albon[["laps_completed", "stints", "stops_fastf1", "compounds_used", "deg_s_per_lap", "air_temp_mean"]].tolist() == [
        "20",
        "2",
        "1",
        "MEDIUM|HARD",
        "0.1000",
        "21.00",
    ]
    periods = _read(raw_dir, "track_status_periods.csv")
    # R12's extract has a `671` lap 2; R13's laps are all green.
    assert periods[["round", "status", "start_lap", "end_lap"]].values.tolist() == [["12", "vsc", "2", "2"]]
    assert _snapshot(raw_dir / "fastf1") == extracts_before


# --------------------------------------------------------------------------
# Practice
# --------------------------------------------------------------------------


def test_practice_writes_stints_and_skips_an_unmatched_rookie(raw_dir, token_path, capsys):
    laps = _laps(cars=("1", "44", "23", "38"), n_laps=14, compound="SOFT", pit_lap=7, second_compound="MEDIUM")
    fake = _FakeFastF1({(2026, 13, "FP2"): _FakeSession(laps)})
    rc = _run(["--season", "2026", "--round", "13", "--session", "FP2"], raw_dir, token_path, fake)
    captured = capsys.readouterr()
    assert rc == 0
    assert "[fetch-sessions] 2026 R13 FP2: car number 38 not in Jolpica results, skipped" in captured.err
    assert fake.get_session_calls == [(2026, 13, "FP2")]
    path = raw_dir / "fastf1_practice" / "2026" / "13-italian-grand-prix" / "FP2_stints.csv"
    stints = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(stints.columns) == summary.PRACTICE_STINT_COLUMNS
    assert len(stints) == 6  # 3 matched cars x 2 stints
    albon = stints[stints["driver_id"] == "albon"]
    assert albon[["session", "constructor_id", "driver_number", "stint", "compound", "laps", "deg_s_per_lap"]].values.tolist() == [
        ["FP2", "williams", "23", "1", "SOFT", "7", "0.1000"],
        ["FP2", "williams", "23", "2", "MEDIUM", "7", "0.1000"],
    ]
    # Practice never touches the race summaries.
    assert not (raw_dir / "fastf1_summary").exists()


def test_practice_matches_cars_on_the_latest_race_with_results(tmp_path, token_path):
    raw = tmp_path / "raw2"
    # 2026 R13 has no results yet; R12 is the latest at or before 13.
    _write_jolpica(raw, results_rounds=((2026, 12),))
    fake = _FakeFastF1({(2026, 13, "FP1"): _FakeSession(_laps(n_laps=6))})
    assert _run(["--season", "2026", "--round", "13", "--session", "FP1"], raw, token_path, fake) == 0
    stints = pd.read_csv(raw / "fastf1_practice" / "2026" / "13-italian-grand-prix" / "FP1_stints.csv", dtype=str)
    assert sorted(stints["driver_id"]) == ["albon", "hamilton", "max_verstappen"]
    # 6 laps, lap 1 excluded: 5 qualifying laps is enough for a slope.
    assert set(stints["deg_s_per_lap"]) == {"0.1000"}


def test_a_missing_session_fails_and_writes_nothing(raw_dir, token_path, capsys):
    before = _snapshot(raw_dir)
    fake = _FakeFastF1()  # no FP2: a sprint weekend
    rc = _run(["--season", "2026", "--round", "13", "--session", "FP2"], raw_dir, token_path, fake)
    assert rc == 1
    assert "[fetch-sessions] 2026 R13 FP2: session not found" in capsys.readouterr().err
    assert fake.get_session_calls == [(2026, 13, "FP2")]
    after = {k: v for k, v in _snapshot(raw_dir).items() if not k.startswith("fastf1_cache")}
    assert after == before


# --------------------------------------------------------------------------
# Tyre wear
# --------------------------------------------------------------------------


def test_tyre_wear_needs_five_green_accurate_laps_and_skips_wet_stints():
    laps = _laps(cars=("1",), n_laps=6)
    laps.loc[laps["LapNumber"] == 4, "TrackStatus"] = "12"  # not exactly "1": excluded
    prepared = summary.prepare_laps(laps, 2026, 1)
    slope, count = summary.stint_slope(prepared)
    assert (slope, count) == (None, 4)

    wet = _laps(cars=("1",), n_laps=10, compound="INTERMEDIATE")
    results = pd.DataFrame({"number": ["1"], "driverId": ["max_verstappen"], "constructorId": ["red_bull"]})
    row = summary.car_race_rows(wet, _weather(), results, season=2026, round_number=1, circuit_id="x").iloc[0]
    assert row["deg_s_per_lap"] == "" and row["wet_laps"] == "10"


def test_rain_after_the_last_lap_is_not_race_rainfall():
    laps = _laps(cars=("1",), n_laps=6)
    weather = _weather()
    # Rain only in a row after the last lap ends (as at 2026 Miami).
    weather = pd.concat(
        [weather, pd.DataFrame({"Time": [_td(9000)], "AirTemp": [20.0], "TrackTemp": [30.0], "Rainfall": [True]})],
        ignore_index=True,
    )
    results = pd.DataFrame({"number": ["1"], "driverId": ["max_verstappen"], "constructorId": ["red_bull"]})
    row = summary.car_race_rows(laps, weather, results, season=2026, round_number=4, circuit_id="miami").iloc[0]
    assert row["rainfall"] == "false"

    weather.loc[1, "Rainfall"] = True  # rain during the race counts
    row = summary.car_race_rows(laps, weather, results, season=2026, round_number=4, circuit_id="miami").iloc[0]
    assert row["rainfall"] == "true"
