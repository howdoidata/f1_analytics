"""Williams' combined finishing position at the 2026 Dutch GP (pre-race analysis, R1-R11 data).

The estimate is a judgement made in the original report (section 5), not a
computed answer. It is kept here as named constants; `estimate` returns it
together with the computed inputs it was weighed from.
"""

from __future__ import annotations

import pandas as pd

from f1_analytics.analysis.results import (
    combined_by_round,
    non_finish_note,
    race_label,
    race_mask,
    season_rows,
    season_summary,
    team_mask,
)


SEASON = 2026
TEAM = "williams"
LAST_ROUND = 11  # the data the pre-race report used
RACE_ROUND = 12  # the 2026 Dutch Grand Prix
RACE = "dutch"
HISTORY_SEASONS = (2021, 2025)

# A judgement (Zandvoort report, section 5), not a computed answer.
ESTIMATE = 31
ESTIMATE_RANGE = (29, 33)
ESTIMATE_LABEL = "judgement"

# Also judgements: how the estimate would move once qualifying is known.
REVISE_WHEN_QUALIFYING = (
    ("Both cars in the top 12", "26–28"),
    ("Grid sum near 32 (typical)", "31"),
    ("Both cars 17th or worse again", "34–36"),
)


def lap_text(td: pd.Timedelta) -> str:
    """A lap time as m:ss.fff."""
    total = td.total_seconds()
    minutes = int(total // 60)
    return f"{minutes}:{total - 60 * minutes:06.3f}"


def team_rows(results: pd.DataFrame, season: int = SEASON, last_round: int = LAST_ROUND, team: str = TEAM) -> pd.DataFrame:
    """The team's `with_change` rows, `season` R1 to `last_round`."""
    rows = season_rows(results, season, last_round)
    return rows[team_mask(rows["constructor_id"], team)]


def round_table(team: pd.DataFrame) -> pd.DataFrame:
    """Per round: race, grid sum, both finishes, combined total and a non-finish note."""
    by_round = combined_by_round(team)
    rows = []
    for rnd, group in team.sort_values("position").groupby("round", sort=True):
        rows.append(
            {
                "round": int(rnd),
                "race": race_label(group["race_name"].iloc[0]),
                "grid_sum": int(by_round.loc[rnd, "grid_sum"]),
                "result": " + ".join(f"P{int(p)}" for p in group["position"]),
                "combined": int(by_round.loc[rnd, "combined"]),
                "best": int(by_round.loc[rnd, "best"]),
                "any_non_finish": bool(by_round.loc[rnd, "any_non_finish"]),
                "note": non_finish_note(group["status"]),
            }
        )
    return pd.DataFrame(rows)


def season_stats(table: pd.DataFrame) -> dict[str, float]:
    """`season_summary` of the combined totals."""
    return season_summary(table["combined"])


def window_means(table: pd.DataFrame, windows=(6, 4)) -> pd.DataFrame:
    """Mean combined total over all rounds and over the last `windows` rounds."""
    rounds = table["round"].tolist()
    rows = [{"window": f"All {len(table)} rounds", "values": "—", "mean": float(table["combined"].mean()), "last": None}]
    for k in windows:
        tail = table.tail(k)
        rows.append(
            {
                "window": f"Last {k} (R{rounds[-k]}–R{rounds[-1]})",
                "values": ", ".join(str(v) for v in tail["combined"]),
                "mean": float(tail["combined"].mean()),
                "last": k,
            }
        )
    return pd.DataFrame(rows)


def validation_answers(results: pd.DataFrame, laps: pd.DataFrame, season: int = SEASON, team: str = TEAM) -> dict[str, object]:
    """The three independently supplied answers: Miami combined, Canada best finish, Melbourne fastest lap."""
    rows = season_rows(results, season)
    team_only = rows[team_mask(rows["constructor_id"], team)]
    by_round = combined_by_round(team_only)
    miami = team_only[team_only["round"] == 4].sort_values("position")

    mel = laps[(laps["season"] == season) & (laps["round"] == 1) & team_mask(laps["constructor_id"], team)].copy()
    mel["lap"] = pd.to_timedelta(mel["LapTime"])
    best = mel.loc[mel["lap"].idxmin()]
    return {
        "miami_combined": int(by_round.loc[4, "combined"]),
        "miami_parts": " + ".join(f"{d.title()} P{int(p)}" for d, p in zip(miami["driver_id"], miami["position"])),
        "canada_best": f"P{int(by_round.loc[5, 'best'])}",
        "melbourne_fastest_lap": lap_text(best["lap"]),
        "melbourne_fastest_driver": best["driver_id"],
    }


def _race_history(results: pd.DataFrame, seasons=HISTORY_SEASONS, race: str = RACE) -> pd.DataFrame:
    lo, hi = seasons
    return results[race_mask(results["race_name"], race) & results["season"].between(lo, hi)]


def race_history(results: pd.DataFrame, seasons=HISTORY_SEASONS, race: str = RACE, team: str = TEAM) -> pd.DataFrame:
    """The team at `race` each season: both grids, both finishes and the combined total."""
    rows = []
    history = _race_history(results, seasons, race)
    history = history[team_mask(history["constructor_id"], team)]
    for season, group in history.sort_values("position").groupby("season", sort=True):
        rows.append(
            {
                "season": int(season),
                "grid": "+".join(str(int(g)) for g in group["grid"]),
                "result": " + ".join(f"P{int(p)}" for p in group["position"]),
                "combined": int(group["position"].sum()),
            }
        )
    return pd.DataFrame(rows)


def race_volatility(results: pd.DataFrame, seasons=HISTORY_SEASONS, race: str = RACE) -> dict[str, float]:
    """All teams at `race`, grid > 0: starts, median and mean |position change|, starts moving 5+ places."""
    rows = _race_history(results, seasons, race)
    rows = rows[rows["grid"] > 0]
    moved = (rows["position"] - rows["grid"]).abs()
    starts = int(len(rows))
    big = int((moved >= 5).sum())
    return {
        "starts": starts,
        "median_change": float(moved.median()),
        "mean_change": float(moved.mean()),
        "moved_5_plus": big,
        "moved_5_plus_pct": big / starts * 100 if starts else float("nan"),
    }


def standings_after(standings: pd.DataFrame, round_: int = LAST_ROUND, season: int = SEASON) -> pd.DataFrame:
    """Constructor standings after `round_`, in rank order."""
    rows = standings[(standings["season"] == season) & (standings["round"] == round_)]
    return rows.sort_values("standing_rank")[["standing_rank", "constructor_id", "constructor", "cumulative_points"]].reset_index(drop=True)


def team_standing(table: pd.DataFrame, team: str = TEAM) -> dict[str, object]:
    """The team's rank, field size and points in a `standings_after` table."""
    row = table[team_mask(table["constructor_id"], team)].iloc[0]
    return {"rank": int(row["standing_rank"]), "of": int(len(table)), "points": float(row["cumulative_points"])}


def estimate(results: pd.DataFrame, standings: pd.DataFrame) -> dict[str, object]:
    """The stated estimate (a judgement) and the computed inputs it was weighed from."""
    team = team_rows(results)
    table = round_table(team)
    stats = season_stats(table)
    last4 = team[team["round"] > LAST_ROUND - 4]
    standing = team_standing(standings_after(standings))
    history = race_history(results)
    last_history = history[history["season"] == HISTORY_SEASONS[1]]
    lo, hi = ESTIMATE_RANGE
    return {
        "estimate": ESTIMATE,
        "range": ESTIMATE_RANGE,
        "label": ESTIMATE_LABEL,
        "text": f"{ESTIMATE} ({lo}–{hi})",
        "inputs": {
            "season_median": stats["median"],
            "last_4_mean": float(table["combined"].tail(4).mean()),
            "rounds_with_non_finish": int(table["any_non_finish"].sum()),
            "rounds": int(len(table)),
            "mean_grid_season": float(team["grid"].mean()),
            "mean_grid_last_4": float(last4["grid"].mean()),
            "standing_rank": standing["rank"],
            "standing_of": standing["of"],
            "standing_points": standing["points"],
            "race_median_change": race_volatility(results)["median_change"],
            "last_race_combined": int(last_history["combined"].iloc[0]) if len(last_history) else None,
            "last_race_season": HISTORY_SEASONS[1],
        },
    }


def actual_result(results: pd.DataFrame, season: int = SEASON, round_: int = RACE_ROUND, team: str = TEAM) -> dict[str, object]:
    """The team's real combined finish at the race, or `raced: False` when it has no results yet."""
    rows = results[(results["season"] == season) & (results["round"] == round_)]
    rows = rows[team_mask(rows["constructor_id"], team)].sort_values("position")
    if rows.empty:
        return {"raced": False, "text": "not yet raced"}
    combined = int(rows["position"].sum())
    return {
        "raced": True,
        "race_name": rows["race_name"].iloc[0],
        "combined": combined,
        "result": " + ".join(f"P{int(p)}" for p in rows["position"]),
        "grid_sum": int(rows["grid"].sum()),
        "note": non_finish_note(rows["status"]),
        "text": str(combined),
        "vs_estimate": combined - ESTIMATE,
        "in_range": ESTIMATE_RANGE[0] <= combined <= ESTIMATE_RANGE[1],
    }


# --------------------------------------------------------------------------
# Display tables (strings, ready for `formatting.markdown_table`)
# --------------------------------------------------------------------------


def rounds_display(table: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Round": [f"R{r}" for r in table["round"]],
            "Race": table["race"],
            "Grid sum": table["grid_sum"],
            "Result": table["result"],
            "Total": table["combined"],
            "Note": table["note"],
        }
    )


def windows_display(windows: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"Window": windows["window"], "Values": windows["values"], "Mean": [f"{m:.1f}" for m in windows["mean"]]})


def history_display(history: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"Season": history["season"], "Grid": history["grid"], "Result": history["result"], "Total": history["combined"]}
    )


def estimate_inputs_display(est: dict[str, object]) -> pd.DataFrame:
    """The computed inputs of the estimate, one row each."""
    i = est["inputs"]
    rows = [
        ("Season median combined total", f"{i['season_median']:g}"),
        ("Last 4 rounds mean", f"{i['last_4_mean']:.1f}"),
        ("Rounds with a DNF or DNS", f"{i['rounds_with_non_finish']} of {i['rounds']}"),
        ("Mean grid slot, season (both cars)", f"{i['mean_grid_season']:.1f}"),
        ("Mean grid slot, last 4 rounds (both cars)", f"{i['mean_grid_last_4']:.1f}"),
        (
            f"Constructors' standings after R{LAST_ROUND}",
            f"P{i['standing_rank']} of {i['standing_of']}, {i['standing_points']:g} pts",
        ),
        ("Zandvoort median position change", f"{i['race_median_change']:g} places"),
        (f"{i['last_race_season']} Zandvoort combined total", str(i["last_race_combined"])),
    ]
    return pd.DataFrame(rows, columns=["Input (computed)", "Value"])


def revise_display() -> pd.DataFrame:
    return pd.DataFrame(REVISE_WHEN_QUALIFYING, columns=["If Williams qualify", "Then estimate (judgement)"])


def standings_display(table: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Rank": [f"P{r}" for r in table["standing_rank"]],
            "Constructor": table["constructor"],
            "Points": [f"{p:g}" for p in table["cumulative_points"]],
        }
    )


def actual_text(actual: dict[str, object]) -> str:
    """'33 (P16 + P17; Retired)', or 'not yet raced'."""
    if not actual["raced"]:
        return "not yet raced"
    note = f"; {actual['note']}" if actual["note"] else ""
    return f"{actual['combined']} ({actual['result']}{note})"
