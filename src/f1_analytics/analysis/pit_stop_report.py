"""The pit-stop forecast page: every value, sentence and table it shows.

The page (`reports/<date>-<slug>/report.qmd` for a team and race) calls
`build_report` once with its parameters and prints what this module returns,
so the `.qmd` computes nothing itself. Every figure comes from
`f1_analytics.analysis.pit_stops`; this module only reads the scenario file,
checks it is current, and words and formats the results. No team, driver or
circuit is named here: they come from the page's parameters and the marts.
"""

from __future__ import annotations

import html
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from f1_analytics.analysis.data import PitStopTables, load_pit_stop_tables
from f1_analytics.analysis.formatting import num, share
from f1_analytics.analysis.pit_stops import (
    MODEL_NOTES,
    SCENARIO_COLUMNS,
    Backtest,
    CountModel,
    Forecast,
    PracticeWear,
    backtest,
    circuit_stop_history,
    fit_count_model,
    forecast,
    incident_chance,
    practice_wear_vs_history,
    race_weather,
    scenario_grid,
    team_split_check,
)
from f1_analytics.analysis.pit_stops.backtest import CARS_PER_TEAM
from f1_analytics.analysis.pit_stops.history import HISTORY_START_SEASON, STOP_TYPES
from f1_analytics.analysis.pit_stops.model import DRAWS, WEATHER_FALLBACK
from f1_analytics.analysis.pit_stops.weather import LIVE, WEATHER_CATEGORIES
from f1_analytics.config import DUCKDB_PATH, PROCESSED_DATA_DIR


NOT_EXPECTED = "not expected under the current forecast"
PRACTICE_NOT_LOADED = "Friday practice not loaded yet"
METHOD_LABELS = {"model": "Model", "circuit_history": "Circuit history", "season_form": "Season form"}
MAE_DECIMALS = 2
HIT_RATE_TARGET = 0.8
SCENARIOS_DIR = PROCESSED_DATA_DIR / "scenarios"


class ScenarioFileError(RuntimeError):
    """The scenario file is missing or differs from `scenario_grid` on the current database."""


# --------------------------------------------------------------------------
# Scenario file
# --------------------------------------------------------------------------


def scenarios_command(constructor_id: str, season: int, round: int) -> str:
    return f"uv run scenarios --constructor {constructor_id} --season {season} --round {round}"


def scenario_path(scenarios_dir: Path, constructor_id: str, season: int, round: int) -> Path:
    """`<dir>/<s>-<RR>-<constructor>.csv`, as `uv run scenarios` writes it."""
    return Path(scenarios_dir) / f"{season}-{round:02d}-{constructor_id}.csv"


def _as_written(grid: pd.DataFrame) -> pd.DataFrame:
    """The grid as `uv run scenarios` writes it (preset as lowercase true/false), read back."""
    text = grid.assign(preset=grid["preset"].map({True: "true", False: "false"})).to_csv(index=False)
    return pd.read_csv(io.StringIO(text))


def read_scenarios(
    tables: PitStopTables, path: Path, constructor_id: str, circuit_id: str, season: int, round: int
) -> pd.DataFrame:
    """The scenario file, after checking it equals `scenario_grid` on `tables` written the same way.

    Raises `ScenarioFileError` naming the `uv run scenarios` command when the
    file is missing or differs.
    """
    command = scenarios_command(constructor_id, season, round)
    path = Path(path)
    if not path.exists():
        raise ScenarioFileError(f"no scenario file {path}; write it with `{command}`")
    saved = pd.read_csv(path)
    expected = _as_written(scenario_grid(tables, constructor_id, circuit_id, season, round))
    try:
        pd.testing.assert_frame_equal(saved, expected)
    except AssertionError as error:
        raise ScenarioFileError(
            f"the scenario file {path} differs from the scenario grid on the current database "
            f"(stale, or edited); rewrite it with `{command}`"
        ) from error
    return saved.astype({"preset": "bool"})[SCENARIO_COLUMNS]


# --------------------------------------------------------------------------
# The page's values
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Race:
    season: int
    round: int
    race_name: str
    circuit_id: str
    circuit_name: str
    date: str
    team_name: str


@dataclass(frozen=True)
class ForecastReport:
    """Everything the page shows, from one `fit_count_model` (the scenario check and backtest fit their own)."""

    constructor_id: str
    race: Race
    compounds: Mapping[str, str]
    scenarios: pd.DataFrame
    preset: pd.Series
    model: CountModel
    air_temp: float
    incident_chance: float
    preset_forecast: Forecast
    clean: Forecast
    incident: Forecast
    backtest: Backtest | None
    untested_rounds: tuple[int, ...]
    split_check: pd.DataFrame
    circuit_history: pd.DataFrame
    practice: PracticeWear


def race_info(tables: PitStopTables, constructor_id: str, season: int, round: int) -> Race:
    """The race (name, circuit, date) from the `races` mart, the circuit's name and the team's name."""
    races = tables.races
    row = races[(races["season"] == season) & (races["round"] == round)]
    if row.empty:
        raise ValueError(f"no round {round} in season {season}")
    race = row.iloc[0]
    circuits = tables.circuits.set_index("circuit_id")["circuit_name"]
    teams = tables.constructors.set_index("constructor_id")["name"]
    if constructor_id not in teams.index:
        raise ValueError(f"unknown constructor_id '{constructor_id}'")
    return Race(
        season=season, round=round, race_name=str(race["race_name"]), circuit_id=str(race["circuit_id"]),
        circuit_name=str(circuits.get(race["circuit_id"], race["circuit_id"])),
        date=pd.Timestamp(race["date"]).date().isoformat(), team_name=str(teams[constructor_id]),
    )


def build_report(
    constructor_id: str,
    season: int,
    round: int,
    compounds: Mapping[str, str],
    db_path: str | Path | None = None,
    scenarios_dir: str | Path | None = None,
) -> ForecastReport:
    """Load the marts, check the scenario file and compute the page's forecasts, backtest and history.

    An empty or None `db_path` / `scenarios_dir` is the project's DuckDB file / `data/processed/scenarios/`.
    """
    tables = load_pit_stop_tables(Path(db_path) if db_path else DUCKDB_PATH)
    scenarios_dir = Path(scenarios_dir) if scenarios_dir else SCENARIOS_DIR
    race = race_info(tables, constructor_id, season, round)
    circuit = race.circuit_id
    path = scenario_path(scenarios_dir, constructor_id, season, round)
    scenarios = read_scenarios(tables, path, constructor_id, circuit, season, round)
    preset = scenarios[scenarios["preset"]].iloc[0]

    model = fit_count_model(tables, season, round)
    _, air_temp = race_weather(tables, season, round, kind=LIVE)
    chance = incident_chance(tables, circuit, season, round)

    def run(incident):
        return forecast(
            tables, constructor_id, circuit, season, round,
            start_compounds=str(preset["start_tyres"]).split("|"), air_temp=air_temp,
            weather=str(preset["weather"]), incident=incident, model=model,
        )

    earlier = sorted(int(r) for r in tables.races.loc[tables.races["season"] == season, "round"] if r < round)
    tested, untested = season_backtest(tables, season, earlier)
    return ForecastReport(
        constructor_id=constructor_id, race=race, compounds=dict(compounds),
        scenarios=scenarios, preset=preset, model=model, air_temp=air_temp, incident_chance=chance,
        preset_forecast=run(None), clean=run(False), incident=run(True),
        backtest=tested, untested_rounds=untested,
        split_check=team_split_check(model),
        circuit_history=circuit_stop_history(tables, constructor_id, circuit, season, round),
        practice=practice_wear_vs_history(tables, constructor_id, circuit, season, round),
    )


def season_backtest(tables: PitStopTables, season: int, rounds: list[int]) -> tuple[Backtest | None, tuple[int, ...]]:
    """`backtest` over `rounds`, leaving out the leading rounds with no earlier race to fit on.

    Returns the backtest (None when no round is left) and the rounds left out.
    A round with no fit races has none before it either, so only leading rounds can fail.
    """
    rounds = list(rounds)
    skipped: list[int] = []
    while rounds:
        try:
            return backtest(tables, season, rounds), tuple(skipped)
        except ValueError as error:
            if str(error) != f"no fit races before {season} round {rounds[0]}":
                raise
            skipped.append(rounds.pop(0))
    return None, tuple(skipped)


# --------------------------------------------------------------------------
# Wording
# --------------------------------------------------------------------------


def stop_range(mean: float, p10: float, p90: float) -> str:
    """'3.2 [2–6]': the mean to one decimal and the p10–p90 range."""
    return f"{num(mean)} [{_whole(p10)}–{_whole(p90)}]"


def _whole(value: float) -> str:
    return f"{float(value):g}"


def headline(report: ForecastReport) -> str:
    """The preset scenario's total and range, from the scenario file."""
    p = report.preset
    return stop_range(p["mean"], p["p10"], p["p90"])


def range_text(result: Forecast) -> str:
    return stop_range(result.total.mean, result.total.p10, result.total.p90)


def chance_text(probability: float) -> str:
    """A scenario chance: a whole percentage, '<1%' for a small non-zero one, '0%' for none."""
    if probability <= 0:
        return "0%"
    if probability < 0.005:
        return "<1%"
    return share(probability)


def tyre_label(option: str, compounds: Mapping[str, str]) -> str:
    """'SOFT (C4) + MEDIUM (C3)': each start compound with its Pirelli allocation label, if any."""
    parts = []
    for compound in option.split("|"):
        label = compounds.get(compound)
        parts.append(f"{compound} ({label})" if label else compound)
    return " + ".join(parts)


def scenario_label(name: str, probability: float) -> str:
    if probability <= 0:
        return f"{name}: 0%, {NOT_EXPECTED}"
    return f"{name}: {chance_text(probability)}"


def weather_chances(scenarios: pd.DataFrame) -> dict[str, float]:
    """Each weather's chance: the sum of its scenarios' probabilities (its weather weight)."""
    return {w: float(scenarios.loc[scenarios["weather"] == w, "probability"].sum()) for w in WEATHER_CATEGORIES
            if (scenarios["weather"] == w).any()}


def controls_data(report: ForecastReport) -> dict:
    """What the page's controls need: labelled options, every scenario's shown total, and the preset."""
    scenarios = report.scenarios
    weathers = weather_chances(scenarios)
    rows = [
        {
            "weather": r.weather, "start_tyres": r.start_tyres,
            "tyre_label": scenario_label(tyre_label(r.start_tyres, report.compounds), r.probability),
            "chance": scenario_label("chance of this scenario", r.probability),
            "total": stop_range(r.mean, r.p10, r.p90),
        }
        for r in scenarios.itertuples(index=False)
    ]
    return {
        "weathers": [{"value": w, "label": scenario_label(w, p)} for w, p in weathers.items()],
        "tyres": list(dict.fromkeys(scenarios["start_tyres"])),
        "scenarios": rows,
        "preset_weather": str(report.preset["weather"]),
        "preset_tyres": str(report.preset["start_tyres"]),
    }


_CONTROLS_STYLE = (
    ".scenario-controls fieldset { border: 1px solid #e6e5e0; margin: 0.8rem 0; padding: 0.4rem 0.8rem; }"
    " .scenario-controls label { display: block; margin: 0.15rem 0; }"
    " .scenario-result { font-size: 1.1rem; }"
)

_CONTROLS_SCRIPT = """
(function () {
  var root = document.getElementById("scenario-controls");
  var data = JSON.parse(document.getElementById("scenario-data").textContent);
  function checked(name) {
    var input = root.querySelector('input[name="' + name + '"]:checked');
    return input ? data[name === "scenario-weather" ? "weathers" : "tyres"][Number(input.value)] : null;
  }
  function find(weather, tyres) {
    for (var i = 0; i < data.scenarios.length; i++) {
      var s = data.scenarios[i];
      if (s.weather === weather && s.start_tyres === tyres) { return s; }
    }
    return null;
  }
  function update() {
    var weather = checked("scenario-weather").value;
    data.tyres.forEach(function (tyres, i) {
      var s = find(weather, tyres);
      var label = document.getElementById("scenario-tyres-label-" + i);
      if (s && label) { label.textContent = s.tyre_label; }
    });
    var chosen = find(weather, checked("scenario-tyres"));
    document.getElementById("scenario-total").textContent = chosen ? chosen.total : "–";
    document.getElementById("scenario-chance").textContent = chosen ? chosen.chance : "";
  }
  root.addEventListener("change", update);
  update();
})();
"""


def controls_html(report: ForecastReport) -> str:
    """The weather and start-tyre controls as one self-contained HTML block (no external script).

    The radios and the shown total start on the preset, so the page opens on it
    without running the script; the inline script switches the shown total and
    the tyre options' chances when a control changes. All values come from
    `controls_data`, embedded as JSON.
    """
    data = controls_data(report)
    preset = find_scenario(data, data["preset_weather"], data["preset_tyres"])
    esc = html.escape
    weather_inputs = "\n".join(
        f'<label><input type="radio" name="scenario-weather" value="{i}"'
        f'{" checked" if w["value"] == data["preset_weather"] else ""}> {esc(w["label"])}</label>'
        for i, w in enumerate(data["weathers"])
    )
    tyre_labels = {s["start_tyres"]: s["tyre_label"] for s in data["scenarios"] if s["weather"] == data["preset_weather"]}
    tyre_inputs = "\n".join(
        f'<label><input type="radio" name="scenario-tyres" value="{i}"'
        f'{" checked" if t == data["preset_tyres"] else ""}> '
        f'<span id="scenario-tyres-label-{i}">{esc(tyre_labels.get(t, t))}</span></label>'
        for i, t in enumerate(data["tyres"])
    )
    payload = json.dumps(data).replace("</", "<\\/")
    return (
        f"<style>{_CONTROLS_STYLE}</style>\n"
        '<div id="scenario-controls" class="scenario-controls">\n'
        f'<fieldset><legend>Weather</legend>\n{weather_inputs}\n</fieldset>\n'
        f'<fieldset><legend>Start tyres</legend>\n{tyre_inputs}\n</fieldset>\n'
        f'<p class="scenario-result">Total stops: <strong id="scenario-total">{esc(preset["total"])}</strong> '
        f'(<span id="scenario-chance">{esc(preset["chance"])}</span>)</p>\n'
        "</div>\n"
        f'<script type="application/json" id="scenario-data">{payload}</script>\n'
        f"<script>{_CONTROLS_SCRIPT}</script>"
    )


def find_scenario(data: dict, weather: str, tyres: str) -> dict:
    return next(s for s in data["scenarios"] if s["weather"] == weather and s["start_tyres"] == tyres)


def scenario_table(report: ForecastReport) -> pd.DataFrame:
    """Every scenario: weather, start tyres, chance (0% shown), total and range; the preset marked."""
    s = report.scenarios
    return pd.DataFrame({
        "Weather": s["weather"],
        "Start tyres": [tyre_label(o, report.compounds) for o in s["start_tyres"]],
        "Chance": [chance_text(p) for p in s["probability"]],
        "Stops [p10–p90]": [stop_range(m, lo, hi) for m, lo, hi in zip(s["mean"], s["p10"], s["p90"])],
        "": ["preset" if p else "" for p in s["preset"]],
    })


def unseen_weather_notes(model: CountModel) -> list[str]:
    """For each weather the fit never saw, the sentence saying which estimate it uses instead."""
    notes = []
    for level in WEATHER_CATEGORIES:
        if level in model.weather_levels:
            continue
        nearest = next((w for w in WEATHER_FALLBACK[level] if w in model.weather_levels), model.weather_levels[0])
        notes.append(
            f"No race in the data was {level}, so the {level} scenarios use the {nearest}-weather estimate."
        )
    return notes


def benchmarks(report: ForecastReport) -> dict[str, float]:
    """This race's two benchmark totals, from the preset forecast: 2 x the circuit and the team rate."""
    return {
        "circuit_history": CARS_PER_TEAM * report.preset_forecast.circuit_rate,
        "season_form": CARS_PER_TEAM * report.preset_forecast.team_rate,
    }


def minimum_sentence(model: CountModel) -> str:
    """The race minimum, in plain words: one number when every weather has the same."""
    values = [model.minimums[w] for w in WEATHER_CATEGORIES]
    if len(set(values)) == 1:
        n = values[0]
        return f"At this race a running car makes at least {n} stop{'' if n == 1 else 's'}, in any weather."
    parts = ", ".join(f"{model.minimums[w]} in a {w} race" for w in WEATHER_CATEGORIES)
    return f"At this race a running car makes at least this many stops: {parts}."


def team_link_sentence(model: CountModel) -> str:
    return (
        f"In {share(model.team_link)} of the draws the team's two cars share one draw for their extra stops, "
        "so they tend to make the same number; in the rest each car draws its own."
    )


def split_table(split: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "The team's two cars": split["split"],
        "Model": [_share_or_dash(v) for v in split["model"]],
        "Observed": [_share_or_dash(v) for v in split["observed"]],
    })


def _share_or_dash(value: float) -> str:
    return "–" if value is None or math.isnan(value) else share(value)


def backtest_sentence(table: pd.DataFrame) -> str:
    """Which method had the lowest mean absolute error, and by how many stops (all compared at 2 decimals)."""
    mae = {row.method: round(float(row.mae), MAE_DECIMALS) for row in table.itertuples(index=False)}
    model = mae["model"]
    others = {m: v for m, v in mae.items() if m != "model"}
    best = min(others, key=lambda m: (others[m], list(others).index(m)))
    label = METHOD_LABELS[best].lower()

    def stops(v: float) -> str:
        return f"{v:.{MAE_DECIMALS}f}"

    if model == others[best]:
        return (f"The model and {label} had the same mean absolute error to {MAE_DECIMALS} decimals, "
                f"{stops(model)} stops.")
    if model < others[best]:
        return (f"The model had the lowest mean absolute error, {stops(model)} stops, "
                f"{stops(others[best] - model)} stops below {label} ({stops(others[best])}).")
    return (f"{METHOD_LABELS[best]} had the lowest mean absolute error, {stops(others[best])} stops, "
            f"{stops(model - others[best])} stops below the model ({stops(model)}).")


def untested_sentence(season: int, rounds: tuple[int, ...]) -> str:
    """'' with no left-out round; else which earlier rounds the backtest leaves out and why."""
    if not rounds:
        return ""
    names = ", ".join(str(r) for r in rounds)
    word = "Round" if len(rounds) == 1 else "Rounds"
    verb = "is" if len(rounds) == 1 else "are"
    return f"{word} {names} of {season} {verb} left out: the model has no earlier race to be fitted on for {'it' if len(rounds) == 1 else 'them'}."


def coverage_sentence(table: pd.DataFrame) -> str:
    row = table[table["method"] == "model"].iloc[0]
    return (
        f"The model's p10–p90 range held the actual total in {share(row.hit_rate)} of the {int(row.n)} "
        f"team-races, against a target of {share(HIT_RATE_TARGET)}; the range was {num(row.width)} stops wide "
        "on average."
    )


def no_backtest_sentence(season: int) -> str:
    return f"There are no earlier rounds in {season} to test on."


def backtest_table(table: pd.DataFrame) -> pd.DataFrame:
    def fixed(v: float, decimals: int = MAE_DECIMALS) -> str:
        return "–" if math.isnan(v) else f"{v:.{decimals}f}"

    return pd.DataFrame({
        "Method": [METHOD_LABELS[m] for m in table["method"]],
        "MAE": [fixed(v) for v in table["mae"]],
        "MAE, clean races": [fixed(v) for v in table["mae_clean"]],
        "MAE, SC or red flag": [fixed(v) for v in table["mae_incident"]],
        "Hit rate": ["–" if math.isnan(v) else share(v) for v in table["hit_rate"]],
        "Range width": [fixed(v, 1) for v in table["width"]],
        "Team-races": table["n"].astype(int),
    })


def history_table(history: pd.DataFrame) -> pd.DataFrame:
    """The circuit's earlier races: cars, all stops and stops by type."""
    out = pd.DataFrame({
        "Season": history["season"].astype(int), "Round": history["round"].astype(int),
        "Cars": history["cars"].astype(int), "Stops": history["stops"].astype(int),
    })
    labels = {"normal": "Normal", "sc_vsc": "Under SC/VSC", "red_flag": "Red flag", "unknown": "Type unknown"}
    for stop_type in STOP_TYPES:
        out[labels[stop_type]] = history[stop_type].astype(int)
    return out


def practice_loaded(practice: PracticeWear) -> bool:
    return not practice.practice.empty


def _deg(value: float) -> str:
    return "–" if math.isnan(value) else f"{value:+.3f}"


def practice_table(practice: PracticeWear, team_name: str) -> pd.DataFrame:
    p = practice.practice
    return pd.DataFrame({
        "Session": p["session"],
        f"{team_name} s/lap": [_deg(v) for v in p["team_deg_s_per_lap"]],
        f"{team_name} laps": p["team_laps"].astype(int),
        "Field s/lap": [_deg(v) for v in p["field_deg_s_per_lap"]],
        "Field laps": p["field_laps"].astype(int),
    })


def practice_history_table(practice: PracticeWear, team_name: str) -> pd.DataFrame:
    h = practice.history
    return pd.DataFrame({
        "Season": h["season"].astype(int), "Round": h["round"].astype(int),
        f"{team_name} s/lap": [_deg(v) for v in h["team_deg_s_per_lap"]],
        "Field s/lap": [_deg(v) for v in h["field_deg_s_per_lap"]],
    })


__all__ = [
    "DRAWS",
    "HISTORY_START_SEASON",
    "MODEL_NOTES",
    "NOT_EXPECTED",
    "PRACTICE_NOT_LOADED",
    "ForecastReport",
    "Race",
    "ScenarioFileError",
    "backtest_sentence",
    "backtest_table",
    "benchmarks",
    "build_report",
    "chance_text",
    "controls_data",
    "controls_html",
    "coverage_sentence",
    "headline",
    "history_table",
    "minimum_sentence",
    "no_backtest_sentence",
    "practice_history_table",
    "practice_loaded",
    "practice_table",
    "race_info",
    "range_text",
    "read_scenarios",
    "scenario_label",
    "scenario_path",
    "scenario_table",
    "scenarios_command",
    "split_table",
    "team_link_sentence",
    "tyre_label",
    "season_backtest",
    "unseen_weather_notes",
    "untested_sentence",
    "weather_chances",
]
