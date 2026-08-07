"""Championship leader conversion analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1_analytics.config import DUCKDB_PATH, REPORTS_DIR, TABLES_DIR
from f1_analytics.database.duckdb_io import connect_duckdb


REPORT_PATH = REPORTS_DIR / "championship_leader_conversion.md"
FOLLOWUP_REPORT_PATH = REPORTS_DIR / "championship_leader_followup.md"
TABLE_DIR = TABLES_DIR
FIGURE_DIR = REPORTS_DIR.parent / "figures"


def read_table(conn, table_name: str) -> pd.DataFrame:
    """Read a DuckDB table into a DataFrame.

    Assumes the caller supplies a trusted table name from project-owned code.
    Raises the underlying DuckDB exception if the table does not exist.
    """
    return conn.execute(f"SELECT * FROM {table_name}").df()


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
    are compared to the current Kaggle-baseline point in the season.
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


def summarize_conversion(conversion: pd.DataFrame) -> dict[str, object]:
    """Summarize conversion rows into converted count, total count, and rate."""
    total = len(conversion)
    converted = int(conversion["converted"].sum()) if total else 0
    rate = converted / total if total else 0
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


def build_coverage_summary(
    races: pd.DataFrame,
    results: pd.DataFrame,
    target_season: int,
    cutoff_round: int,
) -> pd.DataFrame:
    """Summarize scheduled and completed target-season race coverage."""
    target_races = races[races["season"] == target_season]
    target_results = results[results["season"] == target_season]
    completed_rounds = sorted(target_results["round"].dropna().astype(int).unique().tolist())
    scheduled_rounds = sorted(target_races["round"].dropna().astype(int).unique().tolist())

    return pd.DataFrame(
        [
            {"metric": "target_season", "value": str(target_season)},
            {"metric": "cutoff_round", "value": str(cutoff_round)},
            {"metric": "scheduled_races_target_season", "value": str(len(scheduled_rounds))},
            {"metric": "completed_result_rounds_target_season", "value": str(len(completed_rounds))},
            {"metric": "latest_completed_round_target_season", "value": str(max(completed_rounds))},
            {"metric": "scheduled_rounds_target_season", "value": ", ".join(map(str, scheduled_rounds))},
            {"metric": "completed_rounds_target_season", "value": ", ".join(map(str, completed_rounds))},
        ]
    )


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a simple Markdown table without extra dependencies."""
    if frame.empty:
        return "_No rows available._"

    display = frame.copy()
    for column in display.columns:
        display[column] = display[column].map(lambda value: "" if pd.isna(value) else str(value))

    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def format_report_date(value: object) -> str:
    """Format dates consistently for user-facing Markdown reports."""
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return str(value)
    return timestamp.date().isoformat()


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


def build_recovery_feature_candidates() -> pd.DataFrame:
    """Return plain-language candidate features for future recovery analysis.

    This table is descriptive metadata, not a model-ready dataset. Availability
    notes distinguish fields already present in curated Kaggle tables from
    fields that require Jolpica comparison data or future feature engineering.
    """
    rows = [
        {
            "feature": "points deficit at cutoff",
            "plain_language_definition": "How many championship points the team trails the cutoff leader by.",
            "why_it_may_matter": "Larger deficits require stronger remaining-season performance or leader underperformance.",
            "current_status": "Available from constructor_standings_by_round.",
        },
        {
            "feature": "remaining races",
            "plain_language_definition": "Number of scheduled races after the cutoff round.",
            "why_it_may_matter": "More remaining races create more chances to recover points.",
            "current_status": "Available from races and the cutoff round.",
        },
        {
            "feature": "remaining points available",
            "plain_language_definition": "Approximate maximum constructor points still available after the cutoff.",
            "why_it_may_matter": "A deficit is more recoverable when enough points remain on the calendar.",
            "current_status": "Requires rules-aware feature engineering for points systems and sprint seasons.",
        },
        {
            "feature": "wins/podium trend after cutoff",
            "plain_language_definition": "Whether wins and podium-level finishes improve after the cutoff.",
            "why_it_may_matter": "A comeback usually needs a visible shift in race-winning or high-scoring form.",
            "current_status": "Wins are available from results; podium trend can be engineered from finishing position.",
        },
        {
            "feature": "teammate contribution",
            "plain_language_definition": "How much the second car contributes to constructor points after the cutoff.",
            "why_it_may_matter": "Constructors recover faster when both drivers score consistently.",
            "current_status": "Available from results and constructor/team grouping.",
        },
        {
            "feature": "qualifying position trend",
            "plain_language_definition": "Whether starting positions improve or decline over later rounds.",
            "why_it_may_matter": "Better qualifying can reduce traffic risk and improve points potential.",
            "current_status": "Available from qualifying for Kaggle-covered rounds; Jolpica can compare fresher current-season rounds.",
        },
        {
            "feature": "reliability/DNF rate",
            "plain_language_definition": "How often cars fail to finish or lose classification after the cutoff.",
            "why_it_may_matter": "A team cannot recover points if reliability prevents both cars from finishing.",
            "current_status": "Can be engineered from results status fields if exposed consistently in the source data.",
        },
        {
            "feature": "pit stop loss or gain where available",
            "plain_language_definition": "Time or position impact from pit stops during remaining races.",
            "why_it_may_matter": "Operational gains can turn marginal race pace into points recovery.",
            "current_status": "Available only from Jolpica pit stop data currently loaded separately.",
        },
        {
            "feature": "lap pace consistency where available",
            "plain_language_definition": "How stable and competitive lap times are across race stints.",
            "why_it_may_matter": "Consistent pace helps explain whether recovery came from genuine performance.",
            "current_status": "Available only from Jolpica lap data currently loaded separately.",
        },
        {
            "feature": "sprint availability where applicable",
            "plain_language_definition": "Whether sprint weekends remain after the cutoff.",
            "why_it_may_matter": "Sprint points can change recovery math in modern seasons.",
            "current_status": "Requires explicit sprint calendar and points-system handling.",
        },
        {
            "feature": "circuit mix after cutoff",
            "plain_language_definition": "The types of circuits left after the cutoff, such as street, high-speed, or high-downforce tracks.",
            "why_it_may_matter": "Car strengths vary by track profile, so remaining calendar mix can favor different teams.",
            "current_status": "Requires track attribute enrichment beyond the current curated tables.",
        },
        {
            "feature": "field concentration/points spread",
            "plain_language_definition": "How tightly points are clustered among top teams at the cutoff.",
            "why_it_may_matter": "Recovery is easier when the field is compressed and leaders can take points from each other.",
            "current_status": "Available from constructor_standings_by_round.",
        },
    ]
    return pd.DataFrame(rows)


def write_constructor_comeback_figure(
    comeback_cases: pd.DataFrame,
    cutoff_round: int,
    figure_path: Path = FIGURE_DIR / "constructor_comeback_cases.html",
) -> Path | None:
    """Write a simple Plotly bar chart for the largest constructor comebacks.

    Returns the figure path when a useful chart is created. Returns None when
    there are no positive deficit-overcome cases. Plotly import failures are
    surfaced to the caller because Plotly is a declared project dependency.
    """
    positive_cases = comeback_cases[comeback_cases["points_deficit_overcome"] > 0].head(10).copy()
    if positive_cases.empty:
        return None

    import plotly.express as px

    positive_cases["case_label"] = (
        positive_cases["season"].astype(str) + " " + positive_cases["champion_constructor"].astype(str)
    )
    ordered = positive_cases.sort_values("points_deficit_overcome", ascending=True)

    fig = px.bar(
        ordered,
        x="points_deficit_overcome",
        y="case_label",
        orientation="h",
        text="points_deficit_overcome",
        labels={
            "points_deficit_overcome": "Points behind cutoff leader",
            "case_label": "Constructor champion",
        },
        title=(
            f"Largest constructors' championship comebacks after round {cutoff_round}<br>"
            "<sup>Kaggle baseline curated tables; cutoff matches the current local results snapshot.</sup>"
        ),
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig.update_layout(
        margin={"l": 140, "r": 40, "t": 80, "b": 60},
        yaxis_title="",
        xaxis_title="Points deficit overcome",
    )

    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(figure_path, include_plotlyjs="cdn")
    return figure_path


def write_report(
    target_season: int,
    cutoff_round: int,
    cutoff_race_name: str,
    cutoff_race_date: str,
    coverage: pd.DataFrame,
    driver_conversion: pd.DataFrame,
    constructor_conversion: pd.DataFrame,
    current: pd.DataFrame,
    report_path: Path = REPORT_PATH,
) -> None:
    driver_summary = summarize_conversion(driver_conversion)
    constructor_summary = summarize_conversion(constructor_conversion)

    driver_current = current[current["entity_type"] == "driver"]
    constructor_current = current[current["entity_type"] == "constructor"]

    report = f"""# Championship Leader Conversion At Current Season Cutoff

## Question

How often did the driver or constructor leading at this point in the season go on to win the championship?

## Cutoff Definition

This point in the season is defined from completed results in `f1_results.csv`, not from scheduled future races.

* Target season: {target_season}
* Latest completed round: {cutoff_round}
* Cutoff race: {cutoff_race_name}
* Cutoff race date: {cutoff_race_date}

The local race schedule lists {coverage.loc[coverage["metric"] == "scheduled_races_target_season", "value"].iloc[0]} races for {target_season}, while race results currently cover {coverage.loc[coverage["metric"] == "completed_result_rounds_target_season", "value"].iloc[0]} completed rounds.

## Drivers

Across {driver_summary["total"]} historical seasons with at least {cutoff_round} completed rounds, the drivers' championship leader after round {cutoff_round} became champion in {driver_summary["converted"]} seasons.

Conversion rate: {driver_summary["rate"]:.1%}

Current {target_season} driver leader(s) at the cutoff:

{markdown_table(driver_current[["leader_name", "leader_points", "leader_wins"]])}

## Constructors

Across {constructor_summary["total"]} historical seasons with constructor standings data and at least {cutoff_round} completed rounds, the constructors' championship leader after round {cutoff_round} became champion in {constructor_summary["converted"]} seasons.

Conversion rate: {constructor_summary["rate"]:.1%}

Current {target_season} constructor leader(s) at the cutoff:

{markdown_table(constructor_current[["leader_name", "leader_points", "leader_wins"]])}

## Current Season Leaders

The current target-season leaders are reported separately because the {target_season} championship outcome is not yet known in the local results.

{markdown_table(current[["entity_type", "leader_name", "leader_points", "leader_wins"]])}

## Data Limitations

* The cutoff uses the latest completed round available in the local `f1_results.csv` file.
* The local `f1_races.csv` file can include scheduled future races, so scheduled races are not treated as completed.
* Historical comparisons use the same round number as the cutoff and exclude seasons without enough completed races.
* Tied leaders are included as co-leaders when they share first place on cumulative points and wins.
* Constructors' championship conversion starts with seasons where constructor championship data exists.

## Output Tables

* `outputs/tables/driver_leader_conversion.csv`
* `outputs/tables/constructor_leader_conversion.csv`
* `outputs/tables/current_season_leaders.csv`
* `outputs/tables/data_coverage_summary.csv`
"""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def write_followup_report(
    target_season: int,
    cutoff_round: int,
    cutoff_race_name: str,
    cutoff_race_date: str,
    coverage: pd.DataFrame,
    driver_conversion: pd.DataFrame,
    constructor_conversion: pd.DataFrame,
    current: pd.DataFrame,
    comeback_cases: pd.DataFrame,
    feature_candidates: pd.DataFrame,
    figure_path: Path | None,
    report_path: Path = FOLLOWUP_REPORT_PATH,
) -> None:
    """Write the follow-up Markdown report for comeback and recovery analysis."""
    driver_summary = summarize_conversion(driver_conversion)
    constructor_summary = summarize_conversion(constructor_conversion)
    driver_current = current[current["entity_type"] == "driver"]
    constructor_current = current[current["entity_type"] == "constructor"]

    positive_comebacks = comeback_cases[comeback_cases["points_deficit_overcome"] > 0].copy()
    largest = positive_comebacks.iloc[0] if not positive_comebacks.empty else None
    top_comebacks = positive_comebacks.head(10)[
        [
            "season",
            "champion_constructor",
            "cutoff_points",
            "cutoff_leader_points",
            "points_deficit_overcome",
            "cutoff_rank",
            "final_points",
            "final_wins",
        ]
    ]
    selected_features = feature_candidates[["feature", "plain_language_definition", "current_status"]]
    figure_text = (
        f"* `outputs/figures/{figure_path.name}`"
        if figure_path is not None
        else "* No figure generated because there were no positive comeback cases."
    )

    largest_text = (
        "No positive constructor comeback cases were available at this cutoff."
        if largest is None
        else (
            f"The largest historical constructor points deficit overcome after round {cutoff_round} "
            f"was {largest['points_deficit_overcome']:.0f} points: {largest['season']} "
            f"{largest['champion_constructor']} trailed the cutoff leader "
            f"{largest['cutoff_leader_points']:.0f} to {largest['cutoff_points']:.0f} "
            "and still won the constructors' championship."
        )
    )

    report = f"""# Championship Leader Follow-Up: Comebacks And Recovery Factors

## Data Sources

This follow-up uses the existing Kaggle-baseline curated DuckDB tables:

* `races`
* `results`
* `driver_standings_by_round`
* `constructor_standings_by_round`
* `final_driver_standings`
* `final_constructor_standings`

Jolpica/Ergast is loaded separately for current-season coverage comparison, but it is not merged into the Kaggle curated analysis in this report.

## Current Cutoff

The cutoff is the latest completed round available in local Kaggle `f1_results.csv`, not the latest Jolpica round and not the full scheduled calendar.

* Target season: {target_season}
* Cutoff round: {cutoff_round}
* Cutoff race: {cutoff_race_name}
* Cutoff race date: {cutoff_race_date}
* Scheduled target-season races: {coverage.loc[coverage["metric"] == "scheduled_races_target_season", "value"].iloc[0]}
* Completed Kaggle result rounds: {coverage.loc[coverage["metric"] == "completed_result_rounds_target_season", "value"].iloc[0]}

## Current Conversion Answers

Driver championship leaders after round {cutoff_round} became champion in {driver_summary["converted"]} of {driver_summary["total"]} historical seasons, a {driver_summary["rate"]:.1%} conversion rate.

Current {target_season} driver leader at the cutoff:

{markdown_table(driver_current[["leader_name", "leader_points", "leader_wins"]])}

Constructor championship leaders after round {cutoff_round} became champion in {constructor_summary["converted"]} of {constructor_summary["total"]} historical seasons, a {constructor_summary["rate"]:.1%} conversion rate.

Current {target_season} constructor leader at the cutoff:

{markdown_table(constructor_current[["leader_name", "leader_points", "leader_wins"]])}

## Largest Constructor Comeback

{largest_text}

Top historical constructor comeback cases at this same cutoff:

{markdown_table(top_comebacks)}

## Candidate Recovery Features

These candidate features can help explain whether a points recovery is plausible or how it happened historically. They are definitions for future explanatory analysis or modeling, not a trained model.

{markdown_table(selected_features)}

## Outputs

* `outputs/reports/championship_leader_conversion.md`
* `outputs/reports/championship_leader_followup.md`
* `outputs/tables/driver_leader_conversion.csv`
* `outputs/tables/constructor_leader_conversion.csv`
* `outputs/tables/current_season_leaders.csv`
* `outputs/tables/data_coverage_summary.csv`
* `outputs/tables/constructor_comeback_cases.csv`
* `outputs/tables/recovery_feature_candidates.csv`
{figure_text}

## Limitations

* The cutoff remains Kaggle-baseline round {cutoff_round}; Jolpica currently extends current-season coverage but is not merged into Kaggle curated tables.
* Constructor comeback calculations use historical seasons with constructor championship final standings and cutoff-round constructor standings.
* The points systems, sprint formats, and season lengths vary across eras, so raw point deficits are useful for narrative comparison but should be normalized before heavier modeling.
* Candidate recovery features describe analytical directions; several require additional feature engineering or source enrichment before they can be used in a model-ready table.
"""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def run_analysis(
    *,
    db_path: Path = DUCKDB_PATH,
    report_path: Path = REPORT_PATH,
    followup_report_path: Path = FOLLOWUP_REPORT_PATH,
    table_dir: Path = TABLE_DIR,
    figure_dir: Path = FIGURE_DIR,
) -> dict[str, object]:
    """Run the championship leader conversion and follow-up analysis.

    Assumes `db_path` points to a DuckDB file built by `build_f1_dataset.py`.
    Writes Markdown reports, supporting CSVs, and a small Plotly HTML summary.
    Raises FileNotFoundError when the database is missing.
    """
    if not db_path.is_file():
        raise FileNotFoundError(f"DuckDB database missing: {db_path}. Run scripts/build_f1_dataset.py first.")

    table_dir.mkdir(parents=True, exist_ok=True)

    with connect_duckdb(db_path, read_only=True) as conn:
        races = read_table(conn, "races")
        results = read_table(conn, "results")
        driver_standings = read_table(conn, "driver_standings_by_round")
        constructor_standings = read_table(conn, "constructor_standings_by_round")
        driver_final = read_table(conn, "final_driver_standings")
        constructor_final = read_table(conn, "final_constructor_standings")

    target_season = int(results["season"].max())
    cutoff_round = int(results.loc[results["season"] == target_season, "round"].max())
    cutoff_race = races[(races["season"] == target_season) & (races["round"] == cutoff_round)].iloc[0]
    cutoff_race_name = str(cutoff_race["race_name"])
    cutoff_race_date = format_report_date(cutoff_race["date"])

    driver_conversion = build_conversion_table(
        driver_standings,
        driver_final,
        cutoff_round,
        target_season,
        id_column="driver_id",
        name_column="driver_name",
    )
    constructor_conversion = build_conversion_table(
        constructor_standings,
        constructor_final,
        cutoff_round,
        target_season,
        id_column="constructor_id",
        name_column="constructor",
    )
    current = pd.concat(
        [
            current_leaders(driver_standings, target_season, cutoff_round, "driver_id", "driver_name", "driver"),
            current_leaders(
                constructor_standings,
                target_season,
                cutoff_round,
                "constructor_id",
                "constructor",
                "constructor",
            ),
        ],
        ignore_index=True,
    )
    coverage = build_coverage_summary(races, results, target_season, cutoff_round)
    comeback_cases = build_constructor_comeback_cases(
        constructor_standings,
        constructor_final,
        cutoff_round,
        target_season,
    )
    feature_candidates = build_recovery_feature_candidates()
    figure_path = write_constructor_comeback_figure(
        comeback_cases,
        cutoff_round,
        figure_dir / "constructor_comeback_cases.html",
    )

    driver_conversion.to_csv(table_dir / "driver_leader_conversion.csv", index=False)
    constructor_conversion.to_csv(table_dir / "constructor_leader_conversion.csv", index=False)
    current.to_csv(table_dir / "current_season_leaders.csv", index=False)
    coverage.to_csv(table_dir / "data_coverage_summary.csv", index=False)
    comeback_cases.to_csv(table_dir / "constructor_comeback_cases.csv", index=False)
    feature_candidates.to_csv(table_dir / "recovery_feature_candidates.csv", index=False)

    write_report(
        target_season,
        cutoff_round,
        cutoff_race_name,
        cutoff_race_date,
        coverage,
        driver_conversion,
        constructor_conversion,
        current,
        report_path,
    )
    write_followup_report(
        target_season,
        cutoff_round,
        cutoff_race_name,
        cutoff_race_date,
        coverage,
        driver_conversion,
        constructor_conversion,
        current,
        comeback_cases,
        feature_candidates,
        figure_path,
        followup_report_path,
    )

    return {
        "target_season": target_season,
        "cutoff_round": cutoff_round,
        "cutoff_race_name": cutoff_race_name,
        "cutoff_race_date": cutoff_race_date,
        "report_path": report_path,
        "followup_report_path": followup_report_path,
        "table_dir": table_dir,
        "figure_path": figure_path,
        "largest_constructor_deficit": (
            None
            if comeback_cases[comeback_cases["points_deficit_overcome"] > 0].empty
            else float(
                comeback_cases[comeback_cases["points_deficit_overcome"] > 0]
                .iloc[0]["points_deficit_overcome"]
            )
        ),
    }
