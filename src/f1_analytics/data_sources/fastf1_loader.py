"""Main-env FastF1 loader: id-map, derive, and verify (Story 1.6).

No `fastf1` import here -- this module only reads the plain `laps.csv`/
`weather.csv`/`counts.json` that the isolated-env `fastf1_fetch.py` half
already dumped under `data/raw/fastf1/<race_label>/`. That split keeps every
function here offline-testable against small fixture CSVs (AD-11).

Every row is mapped to `driver_id`/`constructor_id` by the FastF1 `Driver`
code / `Team` name -- never by `DriverNumber` (car number) -- against the
curated `drivers`/`constructors` tables Story 1.5 already landed (AD-14),
mirroring `kaggle_csv.py`'s drop_duplicates + `.map()` reconciliation
pattern. An unresolved name raises `UnmappedFastF1NameError` naming the
exact unmatched FastF1 string.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


LAPS_FILENAME = "laps.csv"
WEATHER_FILENAME = "weather.csv"
COUNTS_FILENAME = "counts.json"

# Second sanctioned name->id reconciliation under AD-14: exactly these
# four 2026 FastF1 `Team` strings don't exactly match their curated
# `constructors.name`. Resolution order in map_constructor_ids(): (1) exact
# name match, (2) this alias table, (3) UnmappedFastF1NameError -- never a
# fuzzy match.
FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES = {
    "Alpine": "alpine",
    "Cadillac": "cadillac",
    "Racing Bulls": "rb",
    "Red Bull Racing": "red_bull",
}

# Third sanctioned name->id reconciliation under AD-14: these curated
# `drivers.code` values are ambiguous (each matches two curated driver_id
# rows -- F1 codes are reused across eras). Consulted only when a code is
# ambiguous; resolution order in map_driver_ids(): (1) unique code match,
# (2) this override table, (3) AmbiguousFastF1DriverCodeError -- never a
# heuristic like "most recent" or "has a car number."
FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES = {
    "VER": "max_verstappen",
    "ALB": "albon",
}


class UnmappedFastF1NameError(ValueError):
    """A FastF1 `Driver`/`Team` string has no curated drivers/constructors match."""


class AmbiguousFastF1DriverCodeError(ValueError):
    """A FastF1 `Driver` code matches more than one curated `driver_id`."""


class UnassignedFastF1StintError(ValueError):
    """A lap has no FastF1 `Stint` assignment, so it cannot be safely grouped into one."""


class IncompleteFastF1DataError(ValueError):
    """Landed FastF1 rows undercount the session's own reported totals."""


class FastF1RaceLoadError(Exception):
    """One race's fetch-dump-to-landed-frames pipeline failed.

    Wraps the named underlying error with the race label attached, so the
    orchestrator (`scripts/pull_fastf1_data.py`) can report a per-race
    statused failure without aborting the remaining races (AD-13).
    """


def read_race_dump(race_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Read one race's dumped laps/weather CSVs and its counts sidecar."""
    laps_path = race_dir / LAPS_FILENAME
    weather_path = race_dir / WEATHER_FILENAME
    counts_path = race_dir / COUNTS_FILENAME

    missing = [path.name for path in (laps_path, weather_path, counts_path) if not path.is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing FastF1 dump file(s) under {race_dir}: {missing_list}")

    laps = pd.read_csv(laps_path)
    weather = pd.read_csv(weather_path)
    counts = json.loads(counts_path.read_text())
    return laps, weather, counts


def map_driver_ids(laps: pd.DataFrame, drivers: pd.DataFrame) -> pd.Series:
    """Map FastF1 `Driver` codes (e.g. 'VER') to curated `driver_id` -- never `DriverNumber`.

    A NaN `Driver` value is treated as unresolved too (named distinctly as
    `<missing Driver value>`) rather than silently landing a null
    `driver_id` -- this story's boundary is "never guesses or silently
    drops the row."

    A 3-letter code that matches more than one curated `driver_id` (real
    F1 codes are reused across eras, e.g. `VER` is both Jean-Éric Vergne
    and Max Verstappen) resolves via the sanctioned
    `FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES` table; if it's
    ambiguous and not in that table, raises
    `AmbiguousFastF1DriverCodeError` naming the code, rather than silently
    keeping an arbitrary curated row.
    """
    codes_per_driver_id = drivers.dropna(subset=["code"]).groupby("code")["driver_id"].nunique()
    ambiguous_codes = set(codes_per_driver_id[codes_per_driver_id > 1].index)
    present_ambiguous = set(laps["Driver"].dropna().unique()) & ambiguous_codes
    unresolved_ambiguous = sorted(present_ambiguous - set(FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES))
    if unresolved_ambiguous:
        raise AmbiguousFastF1DriverCodeError(
            f"FastF1 driver code(s) match more than one curated driver: {', '.join(unresolved_ambiguous)}"
        )

    lookup = drivers.drop_duplicates(subset=["code"]).set_index("code")["driver_id"]
    for code in present_ambiguous:
        lookup[code] = FASTF1_AMBIGUOUS_DRIVER_CODE_OVERRIDES[code]
    mapped = laps["Driver"].map(lookup)
    unresolved_mask = mapped.isna()
    if unresolved_mask.any():
        raw_values = laps.loc[unresolved_mask, "Driver"].unique()
        unresolved = sorted("<missing Driver value>" if pd.isna(value) else str(value) for value in raw_values)
        raise UnmappedFastF1NameError(f"Unmapped FastF1 driver code(s): {', '.join(unresolved)}")
    return mapped


def map_constructor_ids(laps: pd.DataFrame, constructors: pd.DataFrame) -> pd.Series:
    """Map FastF1 `Team` names (e.g. 'Red Bull') to curated `constructor_id`.

    Resolution order:
    (1) exact match against `constructors.name`; (2) fall back to the
    sanctioned `FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES` table; (3) still
    unresolved -> `UnmappedFastF1NameError` naming the exact string --
    never a fuzzy match.

    A NaN `Team` value is never looked up in the alias table (it can't
    match a string key) and is itself treated as unresolved -- named
    distinctly as `<missing Team value>` -- rather than silently landing a
    null `constructor_id`.

    An alias target that isn't actually present in the live `constructors`
    table (e.g. a stale entry after a curated-table refresh changes
    `constructor_id` values) is treated as unresolved too -- it falls
    through to the same `UnmappedFastF1NameError` below, naming the exact
    FastF1 `Team` string, rather than silently landing a dangling id.
    """
    name_lookup = constructors.drop_duplicates(subset=["name"]).set_index("name")["constructor_id"]
    mapped = laps["Team"].map(name_lookup)

    # Only non-null Team strings that missed the exact match are eligible
    # for the alias table -- a NaN Team is left unresolved, not aliased.
    still_unmapped = mapped.isna() & laps["Team"].notna()
    if still_unmapped.any():
        aliased = laps.loc[still_unmapped, "Team"].map(FASTF1_TEAM_TO_CONSTRUCTOR_ID_ALIASES)
        valid_constructor_ids = set(constructors["constructor_id"])
        aliased = aliased.where(aliased.isin(valid_constructor_ids))
        mapped = mapped.where(~still_unmapped, aliased)

    unresolved_mask = mapped.isna()
    if unresolved_mask.any():
        raw_values = laps.loc[unresolved_mask, "Team"].unique()
        unresolved = sorted("<missing Team value>" if pd.isna(value) else str(value) for value in raw_values)
        raise UnmappedFastF1NameError(f"Unmapped FastF1 team name(s): {', '.join(unresolved)}")
    return mapped


def map_laps_to_ids(laps: pd.DataFrame, drivers: pd.DataFrame, constructors: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `laps` with `driver_id`/`constructor_id` columns added."""
    mapped = laps.copy()
    mapped["driver_id"] = map_driver_ids(mapped, drivers)
    mapped["constructor_id"] = map_constructor_ids(mapped, constructors)
    return mapped


def derive_stints(mapped_laps: pd.DataFrame) -> pd.DataFrame:
    """One row per driver/stint: compound plus the stint's lap boundaries.

    A NaN `Stint` (FastF1 leaves some untimed/out-laps unassigned) is never
    folded into one artificial stint spanning a driver's whole session --
    that could span non-contiguous laps under a single `stint_number` --
    so it raises `UnassignedFastF1StintError` naming the affected
    driver(s) instead.
    """
    unassigned_mask = mapped_laps["Stint"].isna()
    if unassigned_mask.any():
        drivers_affected = sorted(mapped_laps.loc[unassigned_mask, "driver_id"].dropna().unique())
        raise UnassignedFastF1StintError(
            f"Lap(s) with no Stint assignment for driver(s): {', '.join(drivers_affected)}"
        )

    grouped = mapped_laps.groupby(["driver_id", "Stint"])
    stints = (
        grouped.agg(
            constructor_id=("constructor_id", "first"),
            compound=("Compound", "first"),
            lap_start=("LapNumber", "min"),
            lap_end=("LapNumber", "max"),
            lap_count=("LapNumber", "count"),
        )
        .reset_index()
        .rename(columns={"Stint": "stint_number"})
    )
    for column in ("stint_number", "lap_start", "lap_end", "lap_count"):
        stints[column] = pd.to_numeric(stints[column], errors="coerce").astype("Int64")
    return stints


def verify_completeness(mapped_laps: pd.DataFrame, weather: pd.DataFrame, counts: dict) -> None:
    """Verify landed rows against the session's own counts sidecar (AD-13).

    A truncated fetch is a statused failure, never accepted as a silently
    shorter table.
    """
    race_label = counts.get("race_label", "race")

    expected_laps = counts.get("lap_count")
    landed_laps = len(mapped_laps)
    if expected_laps is not None and landed_laps < expected_laps:
        raise IncompleteFastF1DataError(
            f"{race_label}: landed {landed_laps} laps, session reported {expected_laps}"
        )

    expected_weather = counts.get("weather_count")
    landed_weather = len(weather)
    if expected_weather is not None and landed_weather < expected_weather:
        raise IncompleteFastF1DataError(
            f"{race_label}: landed {landed_weather} weather rows, session reported {expected_weather}"
        )

    expected_drivers = set(counts.get("drivers") or [])
    landed_drivers = set(mapped_laps["Driver"].dropna().unique())
    missing_drivers = sorted(expected_drivers - landed_drivers)
    if missing_drivers:
        raise IncompleteFastF1DataError(
            f"{race_label}: missing driver(s) from landed laps: {', '.join(missing_drivers)}"
        )


def load_and_map_race(
    race_dir: Path,
    drivers: pd.DataFrame,
    constructors: pd.DataFrame,
    *,
    label: str,
    season: int,
) -> dict[str, pd.DataFrame]:
    """Read one race's dump, id-map it, verify completeness, and derive stints.

    Returns `{"laps": ..., "stints": ..., "weather": ...}`, each frame
    tagged with `race_label`/`season`/`round` so multiple races can share
    one landed table and later joins back to the curated `races` table
    (keyed on `season`+`round`, e.g. Story 1.7/Epic 2) don't need a
    label-string join. Any failure anywhere in this pipeline -- a missing
    dump file, a corrupt `counts.json`, a malformed CSV, an unmapped name,
    or an incomplete-count mismatch -- is wrapped in `FastF1RaceLoadError`,
    naming the race, for the orchestrator to catch per-race without
    aborting the run (never an uncaught crash that takes down the
    remaining races too).
    """
    try:
        laps, weather, counts = read_race_dump(race_dir)
        mapped_laps = map_laps_to_ids(laps, drivers, constructors)
        verify_completeness(mapped_laps, weather, counts)
        stints = derive_stints(mapped_laps)

        round_number = counts.get("round")
        if round_number is None:
            raise IncompleteFastF1DataError("missing round number in counts.json")

        mapped_laps = mapped_laps.copy()
        mapped_laps.insert(0, "race_label", label)
        mapped_laps.insert(1, "season", season)
        mapped_laps.insert(2, "round", round_number)

        stints = stints.copy()
        stints.insert(0, "race_label", label)
        stints.insert(1, "season", season)
        stints.insert(2, "round", round_number)

        weather = weather.copy()
        weather.insert(0, "race_label", label)
        weather.insert(1, "season", season)
        weather.insert(2, "round", round_number)
    except Exception as error:
        raise FastF1RaceLoadError(f"{label}: {error}") from error

    return {"laps": mapped_laps, "stints": stints, "weather": weather}
