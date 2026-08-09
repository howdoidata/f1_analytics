"""Main-env Jolpica loader: shape, verify, and id-validate landed race results (Story 1.7).

No `fastf1` import here -- this module only reads the plain `race_results.csv`/
`counts.json` that the isolated-env `jolpica_fetch.py` half already dumped
under `data/raw/jolpica/<season>/`. That split keeps every function here
offline-testable against small fixture CSVs (AD-11), mirroring
`fastf1_loader.py`'s split from `fastf1_fetch.py`.

Jolpica's `driverId`/`constructorId` values already ARE the Ergast/Jolpica
id space that Kaggle's curated `driver_id`/`constructor_id` columns also
use (AD-14, row-level verified) -- no name-based reconciliation table is
needed here, unlike FastF1's raw telemetry `Driver`/`Team` strings. This
loader's job is: (1) shape Jolpica's raw Ergast column names into the exact
column set curated `results` uses, so `combined_results` is a straight
concatenation (per `kaggle_csv.build_curated_tables`), and (2) a defensive
existence check against curated `drivers`/`constructors` -- an id absent
from the curated tables raises `UnresolvedJolpicaIdError` naming it, rather
than silently landing a dangling id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RACE_RESULTS_FILENAME = "race_results.csv"
COUNTS_FILENAME = "counts.json"

# The exact column set (and order) of curated `results`
# (`kaggle_csv.build_curated_tables`) that `combined_results` must match.
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


# The raw Ergast column names `shape_results()` reads from a landed
# `race_results.csv`. Used by `empty_shaped_results()` below to build a
# zero-row frame through the same shaping path a populated one takes,
# rather than duplicating `RESULTS_COLUMNS`' dtypes by hand.
RAW_ERGAST_COLUMNS = [
    "season",
    "round",
    "race_name",
    "driverId",
    "givenName",
    "familyName",
    "constructorId",
    "constructorName",
    "grid",
    "position",
    "points",
    "laps",
    "status",
    "totalRaceTime",
    "fastestLapNumber",
    "fastestLapRank",
]


class UnresolvedJolpicaIdError(ValueError):
    """A Jolpica `driverId`/`constructorId` has no curated drivers/constructors match."""


class IncompleteJolpicaDataError(ValueError):
    """Landed Jolpica rows undercount the fetch's own reported totals."""


class JolpicaResultsLoadError(Exception):
    """One season's Jolpica fetch-dump-to-landed-frame pipeline failed.

    Wraps the named underlying error with the season attached, mirroring
    `FastF1RaceLoadError` -- so an orchestrator can report a per-season
    statused failure without it becoming an uncaught crash.
    """


class InvalidJolpicaSeasonOrRoundError(ValueError):
    """A Jolpica row's `season`/`round` value did not coerce to a number.

    `pd.to_numeric(..., errors="coerce")` silently turns a non-numeric
    `season`/`round` into null; left unchecked, that row would simply
    vanish from every later inner merge on `["season", "round"]` (e.g.
    `build_combined_dataset.build_combined_results`) instead of raising --
    a thinner, guessed result the epic's fail-early discipline (AD-16)
    forbids.
    """


def read_season_dump(season_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Read one season's dumped race-results CSV and its counts sidecar."""
    results_path = season_dir / RACE_RESULTS_FILENAME
    counts_path = season_dir / COUNTS_FILENAME

    missing = [path.name for path in (results_path, counts_path) if not path.is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing Jolpica dump file(s) under {season_dir}: {missing_list}")

    results = pd.read_csv(results_path)
    counts = json.loads(counts_path.read_text())
    return results, counts


def verify_completeness(results: pd.DataFrame, counts: dict) -> None:
    """Verify landed rows against the fetch's own counts sidecar (AD-13).

    A row count that doesn't exactly match the sidecar -- short OR long --
    is a statused failure, never accepted as "close enough": a truncated
    read is the obvious case, but an over-count (e.g. a corrupted or
    hand-edited dump) is just as much a mismatch against "the source's own
    published total". Mirrors `fastf1_loader.verify_completeness`.
    """
    season = counts.get("season", "season")
    expected_row_count = counts.get("row_count")
    landed_row_count = len(results)
    if expected_row_count is None:
        raise IncompleteJolpicaDataError(f"season {season}: counts sidecar is missing 'row_count'")
    if landed_row_count != expected_row_count:
        raise IncompleteJolpicaDataError(
            f"season {season}: landed {landed_row_count} row(s), fetch reported {expected_row_count}"
        )


def _driver_name(results: pd.DataFrame) -> pd.Series:
    given = results["givenName"].fillna("")
    family = results["familyName"].fillna("")
    return (given + " " + family).str.strip()


# Columns cast to a nullable integer dtype after `pd.to_numeric` coercion,
# rather than left as `float64`. `position` is the one downstream Epic 2
# Story 2.1's AC actually requires typed INTEGER end-to-end, but leaving
# the rest as float64 would make `combined_results`/combined standings'
# dtype for these columns shift depending on whether a given round's rows
# came from Kaggle (already integer-typed) or Jolpica -- `pd.concat`
# upcasts a mixed int/float column to float64 for the whole table. `points`
# is included here too, matching this fix's scope; a genuinely fractional
# points value (half-points races are rare but real in F1 history) would
# raise on the `.astype("Int64")` below rather than silently truncating --
# a loud, named failure being preferable to silently wrong data, per this
# epic's fail-early discipline (AD-16).
NUMERIC_INT_COLUMNS = ["season", "round", "grid", "position", "points", "laps", "fastest_lap", "fastest_lap_rank"]


def shape_results(results: pd.DataFrame) -> pd.DataFrame:
    """Rename/select Jolpica's raw Ergast columns into curated `results`'s shape.

    Column provenance:
    - `driver_id`/`constructor_id` <- Ergast's `driverId`/`constructorId`
      (already the AD-14 id space, no mapping table needed).
    - `driver_name` <- `givenName` + `familyName` (mirrors
      `kaggle_csv.build_curated_tables`'s own construction of `driver_name`).
    - `constructor` <- `constructorName`.
    - `time` <- `totalRaceTime` (Ergast's absolute time for P1, gap-to-leader
      for the rest) -- a best-effort carry of Kaggle's free-text `time`
      column; not used by any AD-2 precedence or standings computation.
    - `fastest_lap`/`fastest_lap_rank` <- `fastestLapNumber`/`fastestLapRank`.
    """
    shaped = pd.DataFrame(
        {
            "season": pd.to_numeric(results["season"], errors="coerce"),
            "round": pd.to_numeric(results["round"], errors="coerce"),
            "race_name": results["race_name"],
            "driver_id": results["driverId"],
            "driver_name": _driver_name(results),
            "constructor_id": results["constructorId"],
            "constructor": results["constructorName"],
            "grid": pd.to_numeric(results["grid"], errors="coerce"),
            "position": pd.to_numeric(results["position"], errors="coerce"),
            "points": pd.to_numeric(results["points"], errors="coerce"),
            "laps": pd.to_numeric(results["laps"], errors="coerce"),
            "status": results["status"],
            "time": results["totalRaceTime"].astype("string") if "totalRaceTime" in results.columns else pd.NA,
            "fastest_lap": pd.to_numeric(results.get("fastestLapNumber"), errors="coerce"),
            "fastest_lap_rank": pd.to_numeric(results.get("fastestLapRank"), errors="coerce"),
        }
    )
    shaped = shaped[RESULTS_COLUMNS]

    invalid_season_or_round = shaped["season"].isna() | shaped["round"].isna()
    if invalid_season_or_round.any():
        affected_driver_ids = sorted(
            "<missing driver_id value>" if pd.isna(value) else str(value)
            for value in shaped.loc[invalid_season_or_round, "driver_id"].unique()
        )
        raise InvalidJolpicaSeasonOrRoundError(
            f"{int(invalid_season_or_round.sum())} row(s) with a non-numeric season/round value "
            f"(driver_id: {', '.join(affected_driver_ids)})"
        )

    for column in NUMERIC_INT_COLUMNS:
        shaped[column] = shaped[column].astype("Int64")
    return shaped


def empty_shaped_results() -> pd.DataFrame:
    """A zero-row, correctly-typed `results`-shaped frame.

    Used when a season's Jolpica fetch/load degrades to "nothing landed"
    (see `build_combined_dataset.load_jolpica_results`). Routing the empty
    case through `shape_results()` itself -- rather than a bare
    `pd.DataFrame(columns=RESULTS_COLUMNS)` -- guarantees its column dtypes
    match a populated frame's exactly, so concatenating it with real Kaggle
    rows in `build_combined_results` never silently upcasts a numeric
    column (e.g. `points`) to `object` (which would then break
    `compute_cumulative_standings`'s `cumsum()`).
    """
    return shape_results(pd.DataFrame(columns=RAW_ERGAST_COLUMNS))


def validate_ids(shaped: pd.DataFrame, drivers: pd.DataFrame, constructors: pd.DataFrame) -> None:
    """Verify every `driver_id`/`constructor_id` exists in the curated tables.

    A NaN id is treated as unresolved too (named distinctly), rather than
    silently landing a null id -- mirrors `fastf1_loader.map_driver_ids`'s
    "never guesses or silently drops the row" rule.
    """
    known_driver_ids = set(drivers["driver_id"])
    unresolved_drivers = sorted(str(value) for value in set(shaped["driver_id"].dropna()) - known_driver_ids)
    if shaped["driver_id"].isna().any():
        unresolved_drivers = ["<missing driverId value>"] + unresolved_drivers
    if unresolved_drivers:
        raise UnresolvedJolpicaIdError(f"Unresolved Jolpica driver id(s): {', '.join(unresolved_drivers)}")

    known_constructor_ids = set(constructors["constructor_id"])
    unresolved_constructors = sorted(
        str(value) for value in set(shaped["constructor_id"].dropna()) - known_constructor_ids
    )
    if shaped["constructor_id"].isna().any():
        unresolved_constructors = ["<missing constructorId value>"] + unresolved_constructors
    if unresolved_constructors:
        raise UnresolvedJolpicaIdError(f"Unresolved Jolpica constructor id(s): {', '.join(unresolved_constructors)}")


def load_and_map_season_results(
    season_dir: Path,
    drivers: pd.DataFrame,
    constructors: pd.DataFrame,
    *,
    season: int,
) -> pd.DataFrame:
    """Read one season's Jolpica dump, verify it, and shape it to curated `results`'s columns.

    Any failure anywhere in this pipeline -- a missing dump file, a corrupt
    `counts.json`, an incomplete-count mismatch, or an unresolved id -- is
    wrapped in `JolpicaResultsLoadError`, naming the season, mirroring
    `fastf1_loader.load_and_map_race`'s per-unit failure wrapping.
    """
    try:
        results, counts = read_season_dump(season_dir)
        verify_completeness(results, counts)
        shaped = shape_results(results)
        validate_ids(shaped, drivers, constructors)
    except Exception as error:
        raise JolpicaResultsLoadError(f"season {season}: {error}") from error
    return shaped
