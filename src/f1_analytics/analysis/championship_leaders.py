"""Championship leader conversion analysis.

How often does the driver or constructor leading the championship after a
given round go on to win it? Every function here takes DataFrames shaped like
the standings tables (`driver_standings_by_round`,
`constructor_standings_by_round`, `final_driver_standings`,
`final_constructor_standings`) and returns a DataFrame or a dict. None of them
reads from DuckDB or the filesystem; callers load the tables.
"""

from __future__ import annotations

import pandas as pd


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
