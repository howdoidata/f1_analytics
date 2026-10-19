"""Race-result helpers shared by the reports: places gained, finishes and summaries.

Pure functions over frames shaped like the `results` mart.
"""

from __future__ import annotations

import pandas as pd


FINISHED_STATUSES = ("Finished", "Lapped")


def with_change(results: pd.DataFrame) -> pd.DataFrame:
    """Add `change` (grid - position; positive = places gained) and `finished`."""
    out = results.copy()
    out["change"] = out["grid"].astype(int) - out["position"].astype(int)
    out["finished"] = out["status"].isin(FINISHED_STATUSES)
    return out


def season_rows(results: pd.DataFrame, season: int, last_round: int | None = None) -> pd.DataFrame:
    """`with_change` rows of one season, optionally up to and including `last_round`."""
    rows = results[results["season"] == season]
    if last_round is not None:
        rows = rows[rows["round"] <= last_round]
    return with_change(rows)


def team_mask(constructor_ids: pd.Series, team: str) -> pd.Series:
    """Rows whose constructor id contains `team` (case-insensitive)."""
    return constructor_ids.str.contains(team, case=False, na=False)


def race_mask(race_names: pd.Series, race: str) -> pd.Series:
    """Rows whose race name contains `race` (case-insensitive)."""
    return race_names.str.contains(race, case=False, na=False)


def change_summary(driver_rows: pd.DataFrame) -> dict[str, float]:
    """Means of the change over finishes, non-finishes and all starts, plus mean grid."""
    finished = driver_rows["finished"]
    return {
        "starts": int(len(driver_rows)),
        "finishes": int(finished.sum()),
        "non_finishes": int((~finished).sum()),
        "mean_change_finished": float(driver_rows.loc[finished, "change"].mean()),
        "mean_change_non_finished": float(driver_rows.loc[~finished, "change"].mean()),
        "mean_change_all": float(driver_rows["change"].mean()),
        "mean_grid": float(driver_rows["grid"].mean()),
    }


def combined_by_round(team_rows: pd.DataFrame) -> pd.DataFrame:
    """Per round: combined classified position (plain sum, no exclusion), grid sum, best finish, any non-finish."""
    grouped = team_rows.groupby("round")
    return pd.DataFrame(
        {
            "combined": grouped["position"].sum().astype(int),
            "grid_sum": grouped["grid"].sum().astype(int),
            "cars": grouped.size(),
            "best": grouped["position"].min().astype(int),
            "any_non_finish": grouped["status"].apply(lambda s: bool((~s.isin(FINISHED_STATUSES)).any())),
        }
    ).sort_index()


def season_summary(values: pd.Series) -> dict[str, float]:
    """n, min, max, mean, median and sample stdev."""
    return {
        "n": int(values.count()),
        "min": int(values.min()),
        "max": int(values.max()),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "stdev": float(values.std(ddof=1)),
    }


def field_non_finish_rate(season_rows: pd.DataFrame) -> float:
    """Non-finish rate over every car in `season_rows` (the Singapore report's "field rate of 21%")."""
    return float((~season_rows["finished"]).mean())


def race_label(race_name: str) -> str:
    """'Australian Grand Prix' -> 'Australian'; 'Bahrain Grand Prix in Malaysia' -> 'Bahrain in Malaysia'."""
    return " ".join(race_name.replace("Grand Prix", " ").split())


def non_finish_note(statuses: pd.Series) -> str:
    """The distinct non-finish statuses of a group of rows ('' when every car finished)."""
    notes = [s for s in dict.fromkeys(statuses) if s not in FINISHED_STATUSES]
    return ", ".join(notes)
