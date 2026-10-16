"""Shape the committed Jolpica CSVs into the curated tables.

No network and no `fastf1` here: this reads only `data/raw/jolpica/*.csv`
(Ergast field names, written by `jolpica_fetch.py`) and returns curated
frames in the column names and dtypes the analysis code reads.

Jolpica's `driverId`/`constructorId` values are the id space every curated
table uses, so ids pass through unchanged. `validate_ids` is a
defensive check that every id in results/sprint/qualifying/standings exists
in the Jolpica-built `drivers`/`constructors` reference tables.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1_analytics.data_sources.jolpica_fetch import RAW_COLUMNS, read_raw_table
from f1_analytics.data_sources.standings import compute_cumulative_standings


# Curated `results` (and `sprint_results`) columns, in order.
RESULTS_COLUMNS = [
    "season",
    "round",
    "race_name",
    "driver_id",
    "driver_name",
    "constructor_id",
    "constructor",
    "grid",
    "position",
    "points",
    "laps",
    "status",
    "time",
    "fastest_lap",
    "fastest_lap_rank",
]

# Nullable integers. `points` is fractional (half points for shortened
# races) and `fastest_lap`/`fastest_lap_rank` are DOUBLE in curated results.
NUMERIC_INT_COLUMNS = ["season", "round", "grid", "position", "laps"]
NUMERIC_FLOAT_COLUMNS = ["points", "fastest_lap", "fastest_lap_rank"]


class UnresolvedJolpicaIdError(ValueError):
    """A Jolpica `driverId`/`constructorId` has no drivers/constructors match."""


class InvalidJolpicaSeasonOrRoundError(ValueError):
    """A Jolpica row's `season`/`round` value did not coerce to a number.

    Left unchecked, such a row would vanish from every later merge on
    `["season", "round"]` instead of raising.
    """


def read_jolpica_raw(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Read every Jolpica CSV; a missing file raises `FileNotFoundError` naming it."""
    missing = [str(raw_dir / f"{table}.csv") for table in RAW_COLUMNS if not (raw_dir / f"{table}.csv").is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Jolpica raw file(s): {', '.join(missing)}")
    return {table: read_raw_table(raw_dir, table) for table in RAW_COLUMNS}


def _int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Float64")


def _str(series: pd.Series) -> pd.Series:
    return series.astype("string")


def _driver_name(given: pd.Series, family: pd.Series) -> pd.Series:
    return (given.fillna("") + " " + family.fillna("")).str.strip()


def _require_season_round(frame: pd.DataFrame, raw: pd.DataFrame, label: str) -> None:
    invalid = frame["season"].isna() | frame["round"].isna()
    if invalid.any():
        ids = sorted(
            "<missing driver_id value>" if pd.isna(value) else str(value)
            for value in raw.loc[invalid.to_numpy(), "driverId"].unique()
        ) if "driverId" in raw.columns else []
        raise InvalidJolpicaSeasonOrRoundError(
            f"{label}: {int(invalid.sum())} row(s) with a non-numeric season/round value"
            + (f" (driver_id: {', '.join(ids)})" if ids else "")
        )


def shape_results(raw: pd.DataFrame) -> pd.DataFrame:
    """Race or sprint classification rows -> curated `results` columns."""
    shaped = pd.DataFrame(
        {
            "season": _int(raw["season"]),
            "round": _int(raw["round"]),
            "race_name": _str(raw["raceName"]),
            "driver_id": _str(raw["driverId"]),
            "driver_name": _driver_name(_str(raw["givenName"]), _str(raw["familyName"])),
            "constructor_id": _str(raw["constructorId"]),
            "constructor": _str(raw["constructorName"]),
            "grid": _int(raw["grid"]),
            "position": _int(raw["position"]),
            "points": _float(raw["points"]),
            "laps": _int(raw["laps"]),
            "status": _str(raw["status"]),
            "time": _str(raw["totalRaceTime"]),
            "fastest_lap": _float(raw["fastestLapNumber"]),
            "fastest_lap_rank": _float(raw["fastestLapRank"]),
        }
    )[RESULTS_COLUMNS]
    _require_season_round(shaped, raw, "results")
    return shaped.reset_index(drop=True)


def shape_races(raw: pd.DataFrame) -> pd.DataFrame:
    races = pd.DataFrame(
        {
            "season": _int(raw["season"]),
            "round": _int(raw["round"]),
            "race_name": _str(raw["raceName"]),
            "circuit_id": _str(raw["circuitId"]),
            # DuckDB writes Python dates as DATE.
            "date": pd.to_datetime(raw["date"], errors="coerce").dt.date,
            "time": _str(raw["time"]),
            "url": _str(raw["url"]),
        }
    )
    _require_season_round(races, raw, "races")
    return races


def shape_circuits(raw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "circuit_id": _str(raw["circuitId"]),
            "circuit_name": _str(raw["circuitName"]),
            "locality": _str(raw["locality"]),
            "country": _str(raw["country"]),
            "lat": _float(raw["lat"]),
            "lng": _float(raw["long"]),
            "url": _str(raw["url"]),
        }
    )


def shape_drivers(raw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "driver_id": _str(raw["driverId"]),
            "given_name": _str(raw["givenName"]),
            "family_name": _str(raw["familyName"]),
            "dob": _str(raw["dateOfBirth"]),
            "nationality": _str(raw["nationality"]),
            "number": _float(raw["permanentNumber"]),
            "code": _str(raw["code"]),
            "url": _str(raw["url"]),
        }
    )


def shape_constructors(raw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "constructor_id": _str(raw["constructorId"]),
            "name": _str(raw["name"]),
            "nationality": _str(raw["nationality"]),
            "url": _str(raw["url"]),
        }
    )


def shape_qualifying(raw: pd.DataFrame) -> pd.DataFrame:
    qualifying = pd.DataFrame(
        {
            "season": _int(raw["season"]),
            "round": _int(raw["round"]),
            "driver_id": _str(raw["driverId"]),
            "constructor_id": _str(raw["constructorId"]),
            "position": _int(raw["position"]),
            "q1": _str(raw["Q1"]),
            "q2": _str(raw["Q2"]),
            "q3": _str(raw["Q3"]),
        }
    )
    _require_season_round(qualifying, raw, "qualifying")
    return qualifying


def shape_final_driver_standings(
    raw: pd.DataFrame, drivers: pd.DataFrame, constructors: pd.DataFrame
) -> pd.DataFrame:
    """Official season-end driver standings, in the curated column order.

    A driver who raced for several teams in a season lists them in order;
    the first is kept, as the curated table always did.
    """
    names = drivers.assign(driver_name=_driver_name(drivers["given_name"], drivers["family_name"]))
    constructor_id = _str(raw["constructorIds"]).str.split(";").str[0].replace("", pd.NA)
    shaped = pd.DataFrame(
        {
            "season": _int(raw["season"]),
            "position": _float(raw["position"]),
            "points": _float(raw["points"]),
            "wins": _int(raw["wins"]),
            "driver_id": _str(raw["driverId"]),
            "constructor_id": constructor_id.astype("string"),
        }
    )
    shaped["constructor"] = shaped["constructor_id"].map(
        constructors.set_index("constructor_id")["name"]
    ).astype("string")
    shaped["driver_name"] = shaped["driver_id"].map(names.set_index("driver_id")["driver_name"]).astype("string")
    return shaped[
        ["season", "position", "points", "wins", "driver_id", "constructor", "driver_name", "constructor_id"]
    ]


def shape_final_constructor_standings(raw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": _int(raw["season"]),
            "position": _float(raw["position"]),
            "points": _float(raw["points"]),
            "wins": _int(raw["wins"]),
            "constructor_id": _str(raw["constructorId"]),
            "constructor": _str(raw["constructorName"]),
        }
    )


def validate_ids(shaped: pd.DataFrame, drivers: pd.DataFrame, constructors: pd.DataFrame, *, label: str = "") -> None:
    """Every `driver_id`/`constructor_id` present in `shaped` must exist in the reference tables.

    A null id is unresolved too, rather than landing silently.
    """
    prefix = f"{label}: " if label else ""
    for column, reference, ref_column in (
        ("driver_id", drivers, "driver_id"),
        ("constructor_id", constructors, "constructor_id"),
    ):
        if column not in shaped.columns:
            continue
        known = set(reference[ref_column].dropna())
        unresolved = sorted(str(value) for value in set(shaped[column].dropna()) - known)
        if shaped[column].isna().any():
            unresolved = [f"<missing {column} value>"] + unresolved
        if unresolved:
            kind = "driver" if column == "driver_id" else "constructor"
            raise UnresolvedJolpicaIdError(f"{prefix}Unresolved Jolpica {kind} id(s): {', '.join(unresolved)}")


def build_curated_tables(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Every curated table built from the Jolpica CSVs."""
    races = shape_races(raw["races"])
    circuits = shape_circuits(raw["circuits"])
    drivers = shape_drivers(raw["drivers"])
    constructors = shape_constructors(raw["constructors"])
    results = shape_results(raw["results"])
    sprint_results = shape_results(raw["sprint_results"])
    qualifying = shape_qualifying(raw["qualifying"])
    final_driver = shape_final_driver_standings(raw["final_driver_standings"], drivers, constructors)
    final_constructor = shape_final_constructor_standings(raw["final_constructor_standings"])

    for label, frame in (
        ("results", results),
        ("sprint_results", sprint_results),
        ("qualifying", qualifying),
        ("final_driver_standings", final_driver[["driver_id"]]),
        ("final_constructor_standings", final_constructor[["constructor_id"]]),
    ):
        validate_ids(frame, drivers, constructors, label=label)

    race_results = results.merge(
        races[["season", "round", "date", "time", "circuit_id", "url"]],
        on=["season", "round"],
        how="left",
        suffixes=("", "_race"),
    )

    return {
        "races": races,
        "results": results,
        "sprint_results": sprint_results,
        "drivers": drivers,
        "constructors": constructors,
        "circuits": circuits,
        "qualifying": qualifying,
        "race_results_enriched": race_results,
        "driver_standings_by_round": compute_cumulative_standings(
            results, "driver_id", "driver_name", races=races, sprint_results=sprint_results
        ),
        "constructor_standings_by_round": compute_cumulative_standings(
            results, "constructor_id", "constructor", races=races, sprint_results=sprint_results
        ),
        "final_driver_standings": final_driver,
        "final_constructor_standings": final_constructor,
    }
