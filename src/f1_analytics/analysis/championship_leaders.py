"""Championship leader conversion analysis.

How often does the driver or constructor leading the championship after a
given round go on to win it? Every function here takes DataFrames shaped like
the standings tables (`driver_standings_by_round`,
`constructor_standings_by_round`, `final_driver_standings`,
`final_constructor_standings`) and returns a DataFrame or a dict. None of them
reads from DuckDB or the filesystem except `leader_conversion`, which loads the
four tables through `analysis.data` and hands them to `conversion_report`.
"""

from __future__ import annotations

import math

import duckdb
import pandas as pd

from f1_analytics.analysis.data import load_standings_tables


def determine_cutoff_round(standings: pd.DataFrame, target_season: int) -> int:
    """Return the max round present for `target_season` in a standings-by-round table.

    Raises ValueError if the target season has no rows.
    """
    season_rounds = standings.loc[standings["season"] == target_season, "round"]
    if season_rounds.empty:
        raise ValueError(f"No standings rows found for season {target_season}.")
    return int(season_rounds.max())


def format_names(values: pd.Series) -> str:
    """Format non-null series values as a comma-separated string."""
    return ", ".join(str(value) for value in values.dropna().astype(str).tolist())


def build_conversion_table(
    standings: pd.DataFrame,
    champions: pd.DataFrame,
    cutoff_round: int,
    target_season: int,
    id_column: str,
    name_column: str,
) -> pd.DataFrame:
    """Build historical cutoff-leader to final-champion conversion rows.

    Inputs are cutoff standings and final standings at either driver or
    constructor grain. The cutoff round is held constant so historical seasons
    are compared at the same point in the season as the target season.
    """
    historical = standings[
        (standings["season"] < target_season)
        & (standings["round"] == cutoff_round)
        & (standings["standing_rank"] == 1)
    ].copy()
    champion_lookup = champions[champions["position"] == 1].copy()
    champion_lookup = champion_lookup[champion_lookup["season"] < target_season]

    rows = []
    for season, season_leaders in historical.groupby("season", sort=True):
        season_champions = champion_lookup[champion_lookup["season"] == season]
        if season_champions.empty:
            continue

        leader_ids = set(season_leaders[id_column].dropna().astype(str))
        champion_ids = set(season_champions[id_column].dropna().astype(str))
        rows.append(
            {
                "season": int(season),
                "cutoff_round": int(cutoff_round),
                "leader_ids": format_names(season_leaders[id_column]),
                "leader_names": format_names(season_leaders[name_column]),
                "leader_points": float(season_leaders["cumulative_points"].max()),
                "leader_wins": int(season_leaders["cumulative_wins"].max()),
                "leader_count": int(season_leaders[id_column].nunique()),
                "champion_ids": format_names(season_champions[id_column]),
                "champion_names": format_names(season_champions[name_column]),
                "converted": bool(leader_ids & champion_ids),
            }
        )

    return pd.DataFrame(rows)


def summarize_conversion(conversion: pd.DataFrame) -> dict[str, int | float | None]:
    """Summarize conversion rows into converted count, total count, and rate.

    `rate` is None when there are no rows, since no rate exists to report.
    """
    total = len(conversion)
    converted = int(conversion["converted"].sum()) if total else 0
    rate = converted / total if total else None
    return {"converted": converted, "total": total, "rate": rate}


def current_leaders(
    standings: pd.DataFrame,
    target_season: int,
    cutoff_round: int,
    id_column: str,
    name_column: str,
    entity_type: str,
) -> pd.DataFrame:
    """Return current-season leader rows at the selected cutoff round."""
    leaders = standings[
        (standings["season"] == target_season)
        & (standings["round"] == cutoff_round)
        & (standings["standing_rank"] == 1)
    ].copy()
    leaders["entity_type"] = entity_type
    return leaders[
        [
            "entity_type",
            "season",
            "round",
            "race_name",
            "date",
            id_column,
            name_column,
            "cumulative_points",
            "cumulative_wins",
            "standing_rank",
        ]
    ].rename(
        columns={
            "round": "cutoff_round",
            id_column: "leader_id",
            name_column: "leader_name",
            "cumulative_points": "leader_points",
            "cumulative_wins": "leader_wins",
        }
    )


def build_constructor_comeback_cases(
    constructor_standings: pd.DataFrame,
    constructor_final: pd.DataFrame,
    cutoff_round: int,
    target_season: int,
) -> pd.DataFrame:
    """Calculate historical constructor champions' deficits at the cutoff.

    Returns one row per historical constructor champion with cutoff data.
    Positive `points_deficit_overcome` means the eventual champion trailed the
    cutoff leader and later recovered to win the constructors' championship.
    Seasons without constructor championship final standings or cutoff-round
    constructor standings are excluded.
    """
    cutoff = constructor_standings[
        (constructor_standings["season"] < target_season)
        & (constructor_standings["round"] == cutoff_round)
    ].copy()
    champions = constructor_final[
        (constructor_final["season"] < target_season) & (constructor_final["position"] == 1)
    ].copy()

    rows = []
    for champion in champions.itertuples(index=False):
        season_cutoff = cutoff[cutoff["season"] == champion.season]
        if season_cutoff.empty:
            continue

        champion_cutoff = season_cutoff[season_cutoff["constructor_id"] == champion.constructor_id]
        if champion_cutoff.empty:
            continue

        cutoff_row = champion_cutoff.iloc[0]
        cutoff_leader_points = float(season_cutoff["cumulative_points"].max())
        cutoff_points = float(cutoff_row["cumulative_points"])
        rows.append(
            {
                "season": int(champion.season),
                "champion_constructor_id": champion.constructor_id,
                "champion_constructor": champion.constructor,
                "cutoff_round": int(cutoff_round),
                "cutoff_points": cutoff_points,
                "cutoff_leader_points": cutoff_leader_points,
                "points_deficit_overcome": cutoff_leader_points - cutoff_points,
                "cutoff_rank": int(cutoff_row["standing_rank"]),
                "final_points": float(champion.points),
                "final_wins": int(champion.wins),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "season",
                "champion_constructor_id",
                "champion_constructor",
                "cutoff_round",
                "cutoff_points",
                "cutoff_leader_points",
                "points_deficit_overcome",
                "cutoff_rank",
                "final_points",
                "final_wins",
            ]
        )

    return pd.DataFrame(rows).sort_values(
        ["points_deficit_overcome", "season", "champion_constructor"],
        ascending=[False, False, True],
    )


def conversion_report(
    tables: dict[str, pd.DataFrame],
    cutoff_round: int | None = None,
    target_season: int | None = None,
) -> dict[str, object]:
    """Driver and constructor conversion at the cutoff, plus the current leaders.

    `tables` holds the four standings marts (keys as in
    `analysis.data.load_standings_tables`). `target_season` defaults to the
    latest season in the driver standings, and `cutoff_round` to its latest
    round (`determine_cutoff_round`).
    """
    drivers = tables["driver_standings"]
    constructors = tables["constructor_standings"]
    if target_season is None:
        target_season = int(drivers["season"].max())
    if cutoff_round is None:
        cutoff_round = determine_cutoff_round(drivers, target_season)

    cutoff_rows = drivers[(drivers["season"] == target_season) & (drivers["round"] == cutoff_round)]
    if cutoff_rows.empty:
        raise ValueError(f"No {target_season} driver standings after round {cutoff_round}.")

    driver_table = build_conversion_table(
        drivers, tables["driver_final"], cutoff_round, target_season, "driver_id", "driver_name"
    )
    constructor_table = build_conversion_table(
        constructors, tables["constructor_final"], cutoff_round, target_season, "constructor_id", "constructor"
    )
    leaders = pd.concat(
        [
            current_leaders(drivers, target_season, cutoff_round, "driver_id", "driver_name", "driver"),
            current_leaders(constructors, target_season, cutoff_round, "constructor_id", "constructor", "constructor"),
        ],
        ignore_index=True,
    )
    first = cutoff_rows.iloc[0]
    return {
        "target_season": int(target_season),
        "cutoff_round": int(cutoff_round),
        "cutoff_race": first["race_name"],
        "cutoff_date": pd.Timestamp(first["date"]).date().isoformat(),
        "drivers": driver_table,
        "constructors": constructor_table,
        "driver_summary": summarize_conversion(driver_table),
        "constructor_summary": summarize_conversion(constructor_table),
        "current_leaders": leaders,
    }


def leader_conversion(
    con: duckdb.DuckDBPyConnection,
    cutoff_round: int | None = None,
    target_season: int | None = None,
) -> dict[str, object]:
    """Load the four standings marts from `con` and run `conversion_report`."""
    return conversion_report(load_standings_tables(con), cutoff_round, target_season)


def conversion_display(conversion: pd.DataFrame) -> pd.DataFrame:
    """A conversion table as report strings."""
    return pd.DataFrame(
        {
            "Season": conversion["season"],
            "Leader(s) at cutoff": conversion["leader_names"],
            "Points": [f"{p:g}" for p in conversion["leader_points"]],
            "Wins": conversion["leader_wins"],
            "Champion": conversion["champion_names"],
            "Converted": ["yes" if c else "no" for c in conversion["converted"]],
        }
    )


def leaders_display(leaders: pd.DataFrame) -> pd.DataFrame:
    """Current leaders as report strings."""
    return pd.DataFrame(
        {
            "Championship": leaders["entity_type"],
            "Leader": leaders["leader_name"],
            "Points": [f"{p:g}" for p in leaders["leader_points"]],
            "Wins": leaders["leader_wins"],
        }
    )


def rate_text(summary: dict[str, int | float | None]) -> str:
    """'25 of 28 (89.3%)', or 'no seasons' when there are none."""
    if not summary["total"]:
        return "no seasons"
    return f"{summary['converted']} of {summary['total']} ({summary['rate'] * 100:.1f}%)"


def wilson_interval(converted: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval for `converted` of `total` (95% with the default `z`), as 0-1 fractions."""
    if total <= 0:
        raise ValueError("wilson_interval needs at least one season")
    p = converted / total
    denominator = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return max(0.0, centre - half_width), min(1.0, centre + half_width)


def rate_range_text(summary: dict[str, int | float | None]) -> str:
    """'89% of 28 seasons (95% interval 73–96%)', or 'no seasons' when there are none."""
    total = summary["total"]
    if not total:
        return "no seasons"
    low, high = wilson_interval(summary["converted"], total)
    noun = "season" if total == 1 else "seasons"
    return f"{summary['rate'] * 100:.0f}% of {total} {noun} (95% interval {low * 100:.0f}–{high * 100:.0f}%)"
