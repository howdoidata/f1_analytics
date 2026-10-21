"""The pit-stop forecast page: its wording helpers, the scenario-file check and the rendered HTML.

The Quarto renders (chain world, stale and missing scenario files) skip when
Quarto is absent, as in CI. The committed `report.html` checks run everywhere.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from chain_world import CHAIN_SEASON, CHAIN_TEAM, make_chain_world
from f1_analytics import cli, scenarios
from f1_analytics.analysis import pit_stop_report as pr
from f1_analytics.analysis.data import load_pit_stop_tables
from f1_analytics.analysis.pit_stops import PracticeWear
from f1_analytics.config import PROJECT_ROOT


REPORT_DIR = PROJECT_ROOT / "reports" / "2026-10-24-williams-cota-pit-stop-forecast"
CHAIN_ROUND = 3
CHAIN_CIRCUIT = "albert_park"
FORBIDDEN = re.compile(r"williams|albon|sainz|americas|\bcota\b|austin", re.IGNORECASE)
QUARTO = shutil.which("quarto")
needs_quarto = pytest.mark.skipif(QUARTO is None, reason="Quarto is not installed")


# --------------------------------------------------------------------------
# Wording
# --------------------------------------------------------------------------


def _table(model: float, circuit: float, season: float) -> pd.DataFrame:
    return pd.DataFrame({
        "method": ["model", "circuit_history", "season_form"], "mae": [model, circuit, season],
        "mae_clean": [1.0, 1.0, 1.0], "mae_incident": [2.0, 2.0, 2.0],
        "hit_rate": [0.81, np.nan, np.nan], "width": [4.18, np.nan, np.nan], "n": [187, 187, 187],
    })


def test_backtest_sentence_benchmark_lowest():
    text = pr.backtest_sentence(_table(1.697, 1.556, 1.668))
    assert text == ("Circuit history had the lowest mean absolute error, 1.56 stops, "
                    "0.14 stops below the model (1.70).")


def test_backtest_sentence_model_lowest():
    text = pr.backtest_sentence(_table(1.40, 1.556, 1.468))
    assert text == "The model had the lowest mean absolute error, 1.40 stops, 0.07 stops below season form (1.47)."


def test_backtest_sentence_equal_to_two_decimals():
    text = pr.backtest_sentence(_table(1.5551, 1.5562, 1.70))
    assert text == "The model and circuit history had the same mean absolute error to 2 decimals, 1.56 stops."


def test_backtest_sentence_makes_no_judgement():
    for table in (_table(1.697, 1.556, 1.668), _table(1.40, 1.556, 1.468)):
        assert not re.search(r"meaningful|negligible|significant|better|worse", pr.backtest_sentence(table))


def test_coverage_sentence_gives_hit_rate_target_and_width():
    assert pr.coverage_sentence(_table(1.7, 1.56, 1.67)) == (
        "The model's p10–p90 range held the actual total in 81% of the 187 team-races, against a target of 80%; "
        "the range was 4.2 stops wide on average.")


def test_no_earlier_rounds_sentence():
    assert "no earlier rounds in 2023 to test on" in pr.no_backtest_sentence(2023)


def test_untested_sentence():
    assert pr.untested_sentence(2023, ()) == ""
    assert pr.untested_sentence(2023, (1,)) == (
        "Round 1 of 2023 is left out: the model has no earlier race to be fitted on for it.")
    assert pr.untested_sentence(2023, (1, 2)).startswith("Rounds 1, 2 of 2023 are left out")


def test_chance_text_and_labels():
    assert pr.chance_text(0.0) == "0%"
    assert pr.chance_text(0.001) == "<1%"
    assert pr.chance_text(4 / 7) == "57%"
    assert pr.scenario_label("mixed", 0.0) == f"mixed: 0%, {pr.NOT_EXPECTED}"
    assert pr.scenario_label("dry", 1.0) == "dry: 100%"
    assert pr.tyre_label("SOFT|INTERMEDIATE", {"SOFT": "C4"}) == "SOFT (C4) + INTERMEDIATE"


class _Model:
    def __init__(self, minimums, weather_levels=("dry", "mixed", "wet"), team_link=0.547):
        self.minimums, self.weather_levels, self.team_link = minimums, weather_levels, team_link


def test_minimum_sentence_one_number_when_equal_else_per_weather():
    assert pr.minimum_sentence(_Model({"dry": 1, "mixed": 1, "wet": 1})) == (
        "At this race a running car makes at least 1 stop, in any weather.")
    text = pr.minimum_sentence(_Model({"dry": 2, "mixed": 1, "wet": 1}))
    assert "2 in a dry race" in text and "1 in a wet race" in text


def test_team_link_sentence_reads_the_model():
    assert "In 55% of the draws" in pr.team_link_sentence(_Model({}, team_link=0.547))
    assert "In 20% of the draws" in pr.team_link_sentence(_Model({}, team_link=0.2))


def test_unseen_weather_notes_follow_the_fitted_levels():
    assert pr.unseen_weather_notes(_Model({}, weather_levels=("dry", "mixed", "wet"))) == []
    assert pr.unseen_weather_notes(_Model({}, weather_levels=("dry", "mixed"))) == [
        "No race in the data was wet, so the wet scenarios use the mixed-weather estimate."]
    assert pr.unseen_weather_notes(_Model({}, weather_levels=("dry",))) == [
        "No race in the data was mixed, so the mixed scenarios use the dry-weather estimate.",
        "No race in the data was wet, so the wet scenarios use the dry-weather estimate."]


def test_practice_tables_when_loaded():
    wear = PracticeWear(
        practice=pd.DataFrame({"session": ["FP1", "FP2"], "team_deg_s_per_lap": [0.05, np.nan],
                               "field_deg_s_per_lap": [0.04, -0.01], "team_laps": [20, 0], "field_laps": [300, 280]}),
        history=pd.DataFrame({"season": [2025], "round": [19], "team_deg_s_per_lap": [0.0159],
                              "field_deg_s_per_lap": [-0.0049]}),
    )
    assert pr.practice_loaded(wear)
    table = pr.practice_table(wear, "Team")
    assert table["Session"].tolist() == ["FP1", "FP2"]
    assert table["Team s/lap"].tolist() == ["+0.050", "–"]
    assert pr.practice_history_table(wear, "Team")["Field s/lap"].tolist() == ["-0.005"]
    empty = PracticeWear(practice=wear.practice.iloc[0:0], history=wear.history)
    assert not pr.practice_loaded(empty)


# --------------------------------------------------------------------------
# The chain world: the scenario-file check and the controls
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chain(tmp_path_factory) -> dict[str, Path]:
    """The built chain world's DB and a current scenario file for its team at 2023 R3."""
    root = tmp_path_factory.mktemp("forecast_report_chain")
    raw = make_chain_world(root / "raw")
    db_path = root / "chain.duckdb"
    assert cli.build(["--raw-dir", str(raw), "--db", str(db_path)]) == 0
    out = root / "scenarios"
    args = ["--constructor", CHAIN_TEAM, "--season", str(CHAIN_SEASON), "--round", str(CHAIN_ROUND)]
    assert scenarios.main(args, db_path=db_path, raw_dir=raw, out_dir=out) == 0
    return {"db": db_path, "scenarios": out, "root": root}


def _scenario_file(chain) -> Path:
    return pr.scenario_path(chain["scenarios"], CHAIN_TEAM, CHAIN_SEASON, CHAIN_ROUND)


def test_current_scenario_file_reads(chain):
    tables = load_pit_stop_tables(chain["db"])
    frame = pr.read_scenarios(tables, _scenario_file(chain), CHAIN_TEAM, CHAIN_CIRCUIT, CHAIN_SEASON, CHAIN_ROUND)
    assert frame["preset"].dtype == bool and frame["preset"].sum() == 1


def _stale_copy(chain, tmp_path: Path) -> Path:
    frame = pd.read_csv(_scenario_file(chain), dtype={"preset": str})
    frame.loc[0, "mean"] = frame.loc[0, "mean"] + 0.1
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = pr.scenario_path(tmp_path, CHAIN_TEAM, CHAIN_SEASON, CHAIN_ROUND)
    frame.to_csv(path, index=False)
    return tmp_path


def test_stale_and_missing_scenario_files_name_the_command(chain, tmp_path):
    tables = load_pit_stop_tables(chain["db"])
    command = f"uv run scenarios --constructor {CHAIN_TEAM} --season {CHAIN_SEASON} --round {CHAIN_ROUND}"
    stale = pr.scenario_path(_stale_copy(chain, tmp_path), CHAIN_TEAM, CHAIN_SEASON, CHAIN_ROUND)
    with pytest.raises(pr.ScenarioFileError, match=re.escape(command)):
        pr.read_scenarios(tables, stale, CHAIN_TEAM, CHAIN_CIRCUIT, CHAIN_SEASON, CHAIN_ROUND)
    with pytest.raises(pr.ScenarioFileError, match=re.escape(command)):
        pr.read_scenarios(tables, tmp_path / "none.csv", CHAIN_TEAM, CHAIN_CIRCUIT, CHAIN_SEASON, CHAIN_ROUND)


def test_report_on_the_chain_world(chain):
    report = pr.build_report(CHAIN_TEAM, CHAIN_SEASON, CHAIN_ROUND, {"SOFT": "C3"}, chain["db"], chain["scenarios"])
    preset = report.preset
    assert pr.headline(report) == pr.stop_range(preset["mean"], preset["p10"], preset["p90"])
    # The preset forecast is the preset row of the scenario file.
    assert report.preset_forecast.total.mean == preset["mean"]
    assert report.clean.total.raw_mean <= report.preset_forecast.total.raw_mean <= report.incident.total.raw_mean
    # Round 1 has no earlier race to fit on, so the backtest is round 2's three teams.
    assert report.untested_rounds == (1,)
    assert report.backtest is not None and set(report.backtest.table["n"]) == {3}
    assert pr.backtest_table(report.backtest.table)["MAE, clean races"].tolist() == ["–", "–", "–"]
    html = pr.controls_html(report)
    assert 'src="' not in html and "http" not in html
    assert html.count('name="scenario-weather"') == len(pr.weather_chances(report.scenarios))


# --------------------------------------------------------------------------
# Quarto renders (skipped without Quarto)
# --------------------------------------------------------------------------


def _render(chain, tmp_path: Path, scenarios_dir: Path) -> subprocess.CompletedProcess:
    """Render a copy of the page (in a copy of the reports project) for the chain world."""
    project = tmp_path / "reports"
    page = project / REPORT_DIR.name
    page.mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / "reports" / "_quarto.yml", project / "_quarto.yml")
    shutil.copy(REPORT_DIR / "report.qmd", page / "report.qmd")
    return subprocess.run(
        [QUARTO, "render", str(page / "report.qmd"),
         "-P", f"constructor_id:{CHAIN_TEAM}", "-P", f"season:{CHAIN_SEASON}", "-P", f"round:{CHAIN_ROUND}",
         "-P", f"db_path:{chain['db']}", "-P", f"scenarios_dir:{scenarios_dir}",
         "-M", "title:Team pit stops", "-M", "subtitle:Chain world"],
        capture_output=True, text=True, cwd=project, timeout=600,
    )


@needs_quarto
def test_other_team_render_names_no_williams_or_cota(chain, tmp_path):
    result = _render(chain, tmp_path, chain["scenarios"])
    assert result.returncode == 0, result.stderr[-3000:]
    html = (tmp_path / "reports" / REPORT_DIR.name / "report.html").read_text(encoding="utf-8")
    assert not (tmp_path / "reports" / REPORT_DIR.name / "report.pdf").exists()
    assert FORBIDDEN.findall(html) == []
    assert "Mercedes" in html and pr.PRACTICE_NOT_LOADED in html
    assert _external_assets(html) == []


@needs_quarto
def test_stale_scenario_file_fails_the_render(chain, tmp_path):
    result = _render(chain, tmp_path, _stale_copy(chain, tmp_path / "stale"))
    assert result.returncode != 0
    assert "uv run scenarios" in result.stdout + result.stderr


@needs_quarto
def test_missing_scenario_file_fails_the_render(chain, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _render(chain, tmp_path, empty)
    assert result.returncode != 0
    assert "uv run scenarios" in result.stdout + result.stderr


# --------------------------------------------------------------------------
# The committed page (runs in CI)
# --------------------------------------------------------------------------


class _Assets(HTMLParser):
    """Every script `src` and stylesheet/preload `href` that loads from the network."""

    def __init__(self) -> None:
        super().__init__()
        self.external: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        url = None
        if tag == "script":
            url = attrs.get("src")
        elif tag == "link" and any(r in (attrs.get("rel") or "").split() for r in ("stylesheet", "preload", "modulepreload")):
            url = attrs.get("href")
        if url and re.match(r"^(https?:)?//", url.strip(), re.IGNORECASE):
            self.external.append(url)


def _external_assets(html: str) -> list[str]:
    parser = _Assets()
    parser.feed(html)
    return parser.external


def test_committed_page_has_no_external_script_or_stylesheet():
    html = (REPORT_DIR / "report.html").read_text(encoding="utf-8")
    assert _external_assets(html) == []
    assert "@import" not in html
    assert 'id="scenario-controls"' in html


def test_external_asset_check_catches_a_cdn():
    assert _external_assets('<script src="https://cdn.jsdelivr.net/x.js"></script>') == [
        "https://cdn.jsdelivr.net/x.js"]
    assert _external_assets('<link rel="stylesheet" href="//cdn.example/x.css">') == ["//cdn.example/x.css"]
    assert _external_assets('<a href="https://open-meteo.com/">credit</a>') == []


def test_page_frontmatter_is_html_only():
    text = (REPORT_DIR / "report.qmd").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    assert "embed-resources: true" in frontmatter
    assert "pdf" not in frontmatter
    assert "ojs" not in text


def test_page_body_names_no_team_or_circuit_outside_the_parameters():
    """Only the frontmatter title/subtitle and the parameters cell may name the team or circuit."""
    text = (REPORT_DIR / "report.qmd").read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    body = re.sub(r"```\{python\}\n#\| tags: \[parameters\]\n.*?```", "", body, count=1, flags=re.DOTALL)
    assert FORBIDDEN.findall(body) == []


# --------------------------------------------------------------------------
# The real database (skips without it)
# --------------------------------------------------------------------------


def test_real_db_minimum_link_and_incident_line():
    from f1_analytics.config import DUCKDB_PATH
    from f1_analytics.analysis.pit_stops import fit_count_model, forecast, incident_chance, race_weather
    from f1_analytics.analysis.pit_stops.weather import LIVE

    if not Path(DUCKDB_PATH).exists():
        pytest.skip("real DuckDB not built; run uv run build")
    tables = load_pit_stop_tables(DUCKDB_PATH)
    if not ((tables.weather_forecasts["season"] == 2026) & (tables.weather_forecasts["round"] == 18)
            & (tables.weather_forecasts["kind"] == LIVE)).any():
        pytest.skip("no live forecast for 2026 R18 in the database")
    model = fit_count_model(tables, 2026, 18)
    assert pr.minimum_sentence(model) == "At this race a running car makes at least 1 stop, in any weather."
    assert "In 55% of the draws" in pr.team_link_sentence(model)
    chance = incident_chance(tables, "americas", 2026, 18)
    assert 0 < chance < 1
    _, air_temp = race_weather(tables, 2026, 18, kind=LIVE)
    runs = [
        forecast(tables, "williams", "americas", 2026, 18, start_compounds=["SOFT", "MEDIUM"], air_temp=air_temp,
                 weather="dry", incident=incident, model=model).total.raw_mean
        for incident in (False, None, True)
    ]
    assert runs == sorted(runs) and not any(math.isnan(r) for r in runs)
