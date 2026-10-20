"""Small committed summaries of FastF1 sessions, built from plain DataFrames.

Pure functions only: nothing here imports `fastf1` or touches the network, so
the logic is tested with hand-made frames. `fetch_sessions` feeds them either a
loaded FastF1 session or a committed `data/raw/fastf1/` extract.

- `car_race_rows` -- one row per Jolpica results row of a race (matched on car
  number), the `car_races.csv` Interface columns.
- `track_status_periods` -- SC / VSC / red-flag lap periods from the per-lap
  `TrackStatus` codes.
- `practice_stint_rows` -- one row per car per stint of a practice session.
- `upsert_race_rows` / `write_rows` -- write CSVs with a stable sort, replacing
  only the rows of the race being written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


CAR_RACE_COLUMNS = [
    "season",
    "round",
    "circuit_id",
    "driver_id",
    "constructor_id",
    "driver_number",
    "laps_completed",
    "stints",
    "stops_fastf1",
    "start_compound",
    "start_compound_raw",
    "compounds_used",
    "wet_laps",
    "air_temp_mean",
    "track_temp_mean",
    "rainfall",
    "deg_s_per_lap",
]
TRACK_STATUS_COLUMNS = ["season", "round", "status", "start_lap", "end_lap"]
PRACTICE_STINT_COLUMNS = [
    "season",
    "round",
    "session",
    "driver_id",
    "constructor_id",
    "driver_number",
    "stint",
    "compound",
    "laps",
    "deg_s_per_lap",
]

DRY_COMPOUNDS = frozenset({"SOFT", "MEDIUM", "HARD"})
WET_COMPOUNDS = frozenset({"INTERMEDIATE", "WET"})
# FastF1's placeholders for a compound it does not know.
MISSING_COMPOUNDS = frozenset({"", "UNKNOWN", "TEST_UNKNOWN", "NAN", "NONE"})
# From 2019 Pirelli names the race's three dry compounds SOFT, MEDIUM, HARD.
# Before that each race had its own three, mapped here by hardness.
FIRST_RELATIVE_NAMING_SEASON = 2019
PRE_2019_ALLOCATIONS: dict[tuple[int, int], dict[str, str]] = {
    # 2018 United States GP (COTA).
    (2018, 18): {"ULTRASOFT": "SOFT", "SUPERSOFT": "MEDIUM", "SOFT": "HARD"},
}

# Tyre-wear slope (epic Notes, tyre-wear Assumption).
MIN_DEG_LAPS = 5
GREEN_STATUS = "1"
STATUS_CODES = {"red_flag": ("5",), "sc": ("4",), "vsc": ("6", "7")}
STATUS_PRECEDENCE = ("red_flag", "sc", "vsc")


class SummaryError(ValueError):
    """A session can't be summarised as the Interface requires; the message is the log line's tail."""


# --------------------------------------------------------------------------
# Value normalising (FastF1 frames hold typed values, extracts hold strings)
# --------------------------------------------------------------------------


def car_number(value) -> str:
    """`1`, `1.0`, `"1"` -> `"1"`; missing -> `""`."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    text = str(value).strip()
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def status_string(value) -> str:
    """A `TrackStatus` value as its code string (`671`); a float read from CSV loses its `.0`."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def _bool_series(series: pd.Series) -> pd.Series:
    return series.map(lambda v: str(v).strip().lower() in {"true", "1", "1.0"} if not pd.isna(v) else False)


def _seconds(series: pd.Series) -> pd.Series:
    return pd.to_timedelta(series, errors="coerce").dt.total_seconds()


def normalise_compound(raw, season: int, round_number: int) -> str:
    """One naming for every season: SOFT/MEDIUM/HARD by hardness, INTERMEDIATE/WET unchanged.

    Returns `""` for a missing or unknown compound. A pre-2019 race needs an
    entry in `PRE_2019_ALLOCATIONS`.
    """
    name = "" if raw is None or (not isinstance(raw, str) and pd.isna(raw)) else str(raw).strip().upper()
    if name in MISSING_COMPOUNDS:
        return ""
    if name in WET_COMPOUNDS:
        return name
    if season >= FIRST_RELATIVE_NAMING_SEASON:
        return name
    allocation = PRE_2019_ALLOCATIONS.get((season, round_number))
    if allocation is None:
        raise SummaryError("no compound allocation for a pre-2019 race")
    if name not in allocation:
        raise SummaryError(f"compound {name} not in the race's allocation {sorted(allocation)}")
    return allocation[name]


def raw_compound(raw) -> str:
    name = "" if raw is None or (not isinstance(raw, str) and pd.isna(raw)) else str(raw).strip().upper()
    return "" if name in MISSING_COMPOUNDS else name


# --------------------------------------------------------------------------
# Laps
# --------------------------------------------------------------------------


def prepare_laps(laps: pd.DataFrame, season: int, round_number: int) -> pd.DataFrame:
    """Typed copy of a FastF1 laps frame: numbers, seconds, status strings, both compound names."""
    frame = pd.DataFrame(laps).copy()
    out = pd.DataFrame(index=frame.index)
    out["driver_number"] = frame["DriverNumber"].map(car_number)
    out["lap_number"] = pd.to_numeric(frame["LapNumber"], errors="coerce")
    out["stint"] = pd.to_numeric(frame["Stint"], errors="coerce")
    out["pit_in"] = frame["PitInTime"].notna()
    out["pit_out"] = frame["PitOutTime"].notna()
    out["compound_raw"] = frame["Compound"].map(raw_compound)
    out["compound"] = frame["Compound"].map(lambda v: normalise_compound(v, season, round_number))
    out["tyre_life"] = pd.to_numeric(frame["TyreLife"], errors="coerce")
    out["lap_seconds"] = _seconds(frame["LapTime"])
    out["lap_start_s"] = _seconds(frame["LapStartTime"])
    out["time_s"] = _seconds(frame["Time"])
    out["track_status"] = frame["TrackStatus"].map(status_string)
    out["is_accurate"] = _bool_series(frame["IsAccurate"])
    out = out[out["lap_number"].notna()]
    return out.sort_values(["driver_number", "lap_number"], kind="stable").reset_index(drop=True)


def _deg_laps(car_laps: pd.DataFrame) -> pd.DataFrame:
    """The laps the tyre-wear slope uses: green (`1` exactly), accurate, no pit in/out, not lap 1."""
    keep = (
        (car_laps["track_status"] == GREEN_STATUS)
        & car_laps["is_accurate"]
        & ~car_laps["pit_in"]
        & ~car_laps["pit_out"]
        & (car_laps["lap_number"] != 1)
        & car_laps["lap_seconds"].notna()
        & car_laps["tyre_life"].notna()
    )
    return car_laps[keep]


def stint_slope(stint_laps: pd.DataFrame) -> tuple[float | None, int]:
    """(least-squares s/lap on `TyreLife`, qualifying lap count); slope is None under 5 laps."""
    qualifying = _deg_laps(stint_laps)
    count = len(qualifying)
    if count < MIN_DEG_LAPS or qualifying["tyre_life"].nunique() < 2:
        return None, count
    slope = float(np.polyfit(qualifying["tyre_life"].to_numpy(float), qualifying["lap_seconds"].to_numpy(float), 1)[0])
    return slope, count


def _stint_compound(stint_laps: pd.DataFrame, column: str) -> str:
    values = [v for v in stint_laps.sort_values("lap_number")[column] if v]
    if not values:
        return ""
    counts = pd.Series(values).value_counts(sort=False)
    # Most common name in the stint; ties go to the first one seen.
    return str(counts.idxmax())


def _stints(car_laps: pd.DataFrame) -> list[tuple[int, pd.DataFrame]]:
    with_stint = car_laps[car_laps["stint"].notna()]
    return [(int(stint), group) for stint, group in with_stint.groupby("stint", sort=True)]


def _fmt(value, digits: int) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{round(float(value), digits):.{digits}f}"


# --------------------------------------------------------------------------
# car_races.csv
# --------------------------------------------------------------------------


def race_weather(weather: pd.DataFrame | None, laps: pd.DataFrame) -> dict[str, str]:
    """Race means of air and track temperature (rows from the first lap start to the last lap end), and any rain."""
    empty = {"air_temp_mean": "", "track_temp_mean": "", "rainfall": ""}
    if weather is None or len(weather) == 0:
        return empty
    frame = pd.DataFrame(weather)
    times = _seconds(frame["Time"])
    start, end = laps["lap_start_s"].min(), laps["time_s"].max()
    if pd.notna(start) and pd.notna(end):
        window = frame[(times >= start) & (times <= end)]
    else:
        window = frame
    return {
        "air_temp_mean": _fmt(pd.to_numeric(window["AirTemp"], errors="coerce").mean(), 2),
        "track_temp_mean": _fmt(pd.to_numeric(window["TrackTemp"], errors="coerce").mean(), 2),
        "rainfall": "true" if bool(_bool_series(frame["Rainfall"]).any()) else "false",
    }


def _car_values(car_laps: pd.DataFrame) -> dict[str, str]:
    stints = _stints(car_laps)
    weighted, weights = 0.0, 0
    for _, stint_laps in stints:
        if _stint_compound(stint_laps, "compound") not in DRY_COMPOUNDS:
            continue
        slope, count = stint_slope(stint_laps)
        if slope is not None:
            weighted += slope * count
            weights += count
    return {
        "laps_completed": str(int(car_laps["lap_number"].max())),
        "stints": str(len(stints)),
        "stops_fastf1": str(int(car_laps["pit_in"].sum())),
        "start_compound": _stint_compound(stints[0][1], "compound") if stints else "",
        "start_compound_raw": _stint_compound(stints[0][1], "compound_raw") if stints else "",
        "compounds_used": "|".join(c for c in (_stint_compound(g, "compound") for _, g in stints) if c),
        "wet_laps": str(int(car_laps["compound"].isin(WET_COMPOUNDS).sum())),
        "deg_s_per_lap": _fmt(weighted / weights, 4) if weights else "",
    }


def car_race_rows(
    laps: pd.DataFrame,
    weather: pd.DataFrame | None,
    results: pd.DataFrame,
    *,
    season: int,
    round_number: int,
    circuit_id: str,
) -> pd.DataFrame:
    """One row per Jolpica `results` row of the race, matched on car number.

    Raises `SummaryError` for a FastF1 car number with no Jolpica row, or a
    compound the race's naming can't map. A car with no laps gets
    `laps_completed` 0 and empty lap-derived fields.
    """
    prepared = prepare_laps(laps, season, round_number)
    numbers = {car_number(n): (str(d), str(c)) for n, d, c in zip(results["number"], results["driverId"], results["constructorId"])}
    for number in sorted(set(prepared["driver_number"]) - {""}, key=lambda n: (len(n), n)):
        if number not in numbers:
            raise SummaryError(f"car number {number} not in Jolpica results")
    weather_values = race_weather(weather, prepared)
    rows = []
    for number, (driver_id, constructor_id) in numbers.items():
        car_laps = prepared[prepared["driver_number"] == number]
        row = {
            "season": str(season),
            "round": str(round_number),
            "circuit_id": circuit_id,
            "driver_id": driver_id,
            "constructor_id": constructor_id,
            "driver_number": number,
        }
        if len(car_laps):
            row.update(_car_values(car_laps))
        else:
            row.update({column: "" for column in CAR_RACE_COLUMNS if column not in row})
            row["laps_completed"] = "0"
        row.update(weather_values)
        rows.append(row)
    return sort_rows(pd.DataFrame(rows, columns=CAR_RACE_COLUMNS), ["driver_id"])


# --------------------------------------------------------------------------
# track_status_periods.csv
# --------------------------------------------------------------------------


def lap_status(codes: Iterable[str]) -> str | None:
    """`red_flag` over `sc` over `vsc`, from the union of one lap number's code strings."""
    joined = "".join(codes)
    for status in STATUS_PRECEDENCE:
        if any(code in joined for code in STATUS_CODES[status]):
            return status
    return None


def track_status_periods(laps: pd.DataFrame, *, season: int, round_number: int) -> pd.DataFrame:
    """Each run of consecutive lap numbers with one status is one `start_lap,end_lap` row."""
    frame = pd.DataFrame(laps)
    lap_numbers = pd.to_numeric(frame["LapNumber"], errors="coerce")
    statuses = frame["TrackStatus"].map(status_string)
    per_lap: dict[int, str | None] = {}
    for lap, group in statuses.groupby(lap_numbers):
        per_lap[int(lap)] = lap_status(group)
    rows: list[dict[str, str]] = []
    current: dict | None = None
    for lap in sorted(per_lap):
        status = per_lap[lap]
        if current and status == current["status"] and lap == current["end"] + 1:
            current["end"] = lap
            continue
        if current:
            rows.append(current)
        current = {"status": status, "start": lap, "end": lap} if status else None
    if current:
        rows.append(current)
    return pd.DataFrame(
        [
            {"season": str(season), "round": str(round_number), "status": r["status"], "start_lap": str(r["start"]), "end_lap": str(r["end"])}
            for r in rows
        ],
        columns=TRACK_STATUS_COLUMNS,
    )


# --------------------------------------------------------------------------
# Practice stints
# --------------------------------------------------------------------------


def practice_stint_rows(
    laps: pd.DataFrame,
    results: pd.DataFrame,
    *,
    season: int,
    round_number: int,
    session: str,
) -> tuple[pd.DataFrame, list[str]]:
    """(one row per car per stint, car numbers skipped because Jolpica `results` lacks them)."""
    prepared = prepare_laps(laps, season, round_number)
    numbers = {car_number(n): (str(d), str(c)) for n, d, c in zip(results["number"], results["driverId"], results["constructorId"])}
    skipped = sorted(set(prepared["driver_number"]) - set(numbers) - {""}, key=lambda n: (len(n), n))
    rows = []
    for number, (driver_id, constructor_id) in numbers.items():
        car_laps = prepared[prepared["driver_number"] == number]
        for stint, stint_laps in _stints(car_laps):
            slope, _ = stint_slope(stint_laps)
            rows.append(
                {
                    "season": str(season),
                    "round": str(round_number),
                    "session": session,
                    "driver_id": driver_id,
                    "constructor_id": constructor_id,
                    "driver_number": number,
                    "stint": str(stint),
                    "compound": _stint_compound(stint_laps, "compound"),
                    "laps": str(len(stint_laps)),
                    "deg_s_per_lap": _fmt(slope, 4),
                }
            )
    frame = pd.DataFrame(rows, columns=PRACTICE_STINT_COLUMNS)
    return sort_rows(frame, ["driver_id", "stint"]), skipped


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def _sort_key(column: pd.Series) -> pd.Series:
    if column.name in {"season", "round", "start_lap", "end_lap", "stint"}:
        return pd.to_numeric(column, errors="coerce")
    return column


def sort_rows(frame: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """Stable sort by season, round (numerically), then `key`."""
    return frame.sort_values(["season", "round", *key], key=_sort_key, kind="stable").reset_index(drop=True)


def read_rows(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=columns, dtype="object")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def write_rows(path: Path, frame: pd.DataFrame, columns: list[str]) -> None:
    """Atomic CSV write of string values in `columns` order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame[columns].to_csv(tmp, index=False, lineterminator="\n")
    tmp.replace(path)


def upsert_race_rows(path: Path, rows: pd.DataFrame, *, season: int, round_number: int, columns: list[str], key: list[str]) -> None:
    """Replace the race's rows in `path` with `rows`; every other row keeps its exact text."""
    existing = read_rows(path, columns)
    if list(existing.columns) != columns:
        raise SummaryError(f"{path} has columns {list(existing.columns)}, expected {columns}")
    keep = existing[~((existing["season"] == str(season)) & (existing["round"] == str(round_number)))]
    combined = pd.concat([keep, rows[columns].astype(str)], ignore_index=True) if len(rows) else keep
    write_rows(path, sort_rows(combined, key), columns)
