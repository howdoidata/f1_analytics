# F1 Analytics

Reproducible Formula 1 analysis: race questions answered with tested code and published as short reports.

The repo holds a copy of the public F1 results history (1950 to the latest round) and lap timing for the 2026 races. One command turns that data into a tested DuckDB database, and each report answers one question, such as "how many places will Albon gain or lose from his grid slot in Singapore?". Every number and chart in a report comes from a tested Python function, so anyone can clone the repo, rebuild the database offline and re-render the reports to check them.

It is a portfolio project. It shows the full path from raw data to a published answer: sourcing, modelling with dbt, data tests, tested analysis code and the written report. [`PROJECT.md`](PROJECT.md) describes the scope and the tools, and [`docs/decisions.md`](docs/decisions.md) explains why it is built this way.

## Reports

**[Report gallery](https://howdoidata.github.io/f1_analytics/)**: every report, newest first, rendered in the browser, with links to the Quarto source. In the repo, the same list is in [`reports/README.md`](reports/README.md).

## Prerequisites

You need these four tools to go from a fresh clone to rendered reports. Commands are for macOS and Linux; on Windows, follow each tool's own install page.

| Tool | What it is for | Install |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) 0.12 or later | Python 3.13 and every Python package | `curl -LsSf https://astral.sh/uv/install.sh \| sh`, then open a new terminal |
| [Quarto CLI](https://quarto.org/docs/get-started/) 1.10 or later | Renders the reports | macOS: `brew install --cask quarto`. Otherwise download the installer from [quarto.org](https://quarto.org/docs/get-started/) |
| TeX | The PDF version of each report | `quarto install tinytex` (after Quarto). Skip it if you already have a TeX distribution such as MacTeX or TeX Live |
| Google Chrome | Draws the static charts in the PDFs (through kaleido) | Install [Chrome](https://www.google.com/chrome/), or after `uv sync` run `uv run plotly_get_chrome -y` to download a copy for kaleido |

You also need `git`. The build and the tests need only uv; Quarto, TeX and Chrome are for rendering.

To see what you already have: `uv --version`, `quarto --version`, and `quarto check`, which reports the LaTeX it finds. `quarto list tools` shows TinyTeX as "Not installed" even when another TeX is present; that is fine.

## Quick start

```bash
git clone https://github.com/howdoidata/f1_analytics.git   # or git@github.com:howdoidata/f1_analytics.git; needs access while the repo is private
cd f1_analytics
uv sync                          # creates .venv/ with Python 3.13 and the pinned packages (needs network)
uv run pytest                    # offline test suite, about 8 minutes
uv run build                     # data/raw/ -> data/processed/f1_analytics.duckdb (offline, no credentials)
uv run scenarios --constructor williams --season 2026 --round 18   # the pit-stop page's scenario file (offline)
uv run quarto render reports     # every report to report.html and report.pdf, about 5 minutes
```

Each report is then at `reports/<date>-<slug>/report.html` and `report.pdf`. Open the HTML in a browser; it loads plotly.js from its CDN, so the charts need an internet connection. The pit-stop forecast page is the exception: it is HTML only, with everything embedded, so it works offline. It reads the scenario file `uv run scenarios` writes to `data/processed/scenarios/`, and its render stops with an error naming that command when the file is missing or out of date with the database.

The render prints Jupyter kernel warnings such as "Kernel is running over TCP without encryption"; they are expected and harmless. A render also rewrites the random chart IDs in the committed `report.html` files, so `git status` shows them as modified even when no number changed.

`uv sync` downloads Python 3.13 if you don't have it. After that, `uv run build` and the tests make no network calls and need no credentials.

## How it works

### Data

`data/raw/` is committed: the Jolpica CSVs (1950 to the latest round) and the FastF1 lap and weather extracts. See [`data/raw/NOTICE.md`](data/raw/NOTICE.md) for sources and licences.

```bash
uv run build     # data/raw/ -> data/processed/f1_analytics.duckdb (offline, no credentials)
uv run refresh   # maintainer only: append new Jolpica rounds, fetch missing FastF1 extracts, then build
uv run fetch-sessions --circuit americas --since 2018   # maintainer only: summarise FastF1 sessions into data/raw/fastf1_summary/ and fastf1_practice/ (see --help)
uv run fetch-weather --season 2026 --round 18   # maintainer only: Open-Meteo's live race-window forecast into data/raw/open_meteo/forecast/ (--day-before: the backtest's weather); no login
uv run scenarios --constructor williams --season 2026 --round 18   # the weather x start-tyre scenario file, from the built database, into data/processed/scenarios/ (offline)
```

`uv run build` runs `dbt build` on the project in `dbt/`: staging tables (schema `staging`) type the raw CSVs, the marts in `main` are the tables the analysis reads, and the dbt tests check them. It builds into a fresh temporary file and swaps it in only if every model and test passes and no guarded table (`results`, `sprint_results`, `qualifying`, `raw_fastf1_*`, `pit_stops`, `car_races`, `practice_stints`, `weather_forecasts`, `race_incidents`, `stop_rules`) has shrunk; otherwise it exits 1 and leaves the previous DuckDB file as it was. Each build's test results are in `dbt/target/run_results.json`. Paths resolve from the package location, so `uv run build` writes to this repo's `data/processed/` whatever the current directory.

To run dbt directly, from the repo root (this writes straight to `data/processed/f1_analytics.duckdb`, with no swap or shrink guard):

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt
```

The Jolpica dump was made once with `uv run python scripts/dump_jolpica.py` (already committed; about 90 minutes at the API rate limit). Pit stops (2011 onwards) were backfilled into `pit_stops.csv` with `uv run python scripts/dump_jolpica.py --only pit_stops --first 2011`, which reads the rounds from the committed `results.csv` and writes only that file. It rewrites the file with only the `--first`/`--last` range, so a partial run leaves only that range: run the full range last before committing. `uv run refresh` keeps it current.

### Reports

Each report is `reports/<date>-<slug>/report.qmd`, a Quarto document whose figures, tables and numbers all come from `f1_analytics.analysis` (tested in `tests/test_analysis_*.py`). Quarto runs the Python through the Jupyter engine in the uv environment and reads the DuckDB file read-only. If you render before `uv run build`, the render stops with an error that names the missing file and says to run `uv run build`.

The HTML is committed; the PDFs are gitignored. `reports/golden/` holds the original Singapore and Zandvoort PDF reports that the current values are compared against whenever the pipeline changes. CI runs the tests and the build but does not render.

The gallery (`reports/README.md` and `reports/index.html`) is generated from each report's frontmatter. A report may also carry the optional hand-written fields `status: provisional | validated` and a `gaps:` list of known gaps (one line each), which its gallery card shows. After adding a report or changing a title, subtitle, date, status or gaps, run:

```bash
uv run gallery
```

A test fails while the committed gallery is out of date. On each push to `main`, `.github/workflows/pages.yml` publishes the committed report HTML and the gallery to GitHub Pages; it does not render anything.

### Credentials

| Command | Credential |
| --- | --- |
| `uv run build`, `uv run pytest`, `uv run quarto render reports` | None. |
| `uv run refresh` | An F1TV subscription login for FastF1. Run `uv run python -m fastf1 auth f1tv --authenticate` first (it waits for the browser login to finish); `refresh` checks the token before doing anything and exits if it is missing or expired. Jolpica needs no credential. |

## Data and attribution

- Results, qualifying, pit stops, standings, drivers, constructors and circuits come from the [Jolpica F1 API](https://github.com/jolpica/jolpica-f1), which continues the Ergast dataset. They are licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): non-commercial use only, and derived data must be shared under the same licence.
- Race-window weather forecasts come from [Open-Meteo](https://open-meteo.com/) (its Historical Forecast and Forecast APIs), under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Weather data by Open-Meteo.com.
- Lap and weather data is Formula 1 timing data, obtained with [FastF1](https://github.com/theOehrly/Fast-F1). F1 timing data © Formula One World Championship Limited. This project is unofficial and is not associated in any way with the Formula 1 companies. The extracts are kept for non-commercial analysis only.

Details are in [`data/raw/NOTICE.md`](data/raw/NOTICE.md).

## License

The code is under the [MIT License](LICENSE). The data in `data/raw/` is not covered by it and stays under its own terms: Jolpica data under CC BY-NC-SA 4.0, Open-Meteo forecasts under CC BY 4.0, and F1 timing data owned by Formula One World Championship Limited.

## AI use

F1 Analytics is AI-assisted and human-reviewed. AI tools helped write code, tests and documentation. The author reviewed, tested and merged every change, and is responsible for everything in this repo.
