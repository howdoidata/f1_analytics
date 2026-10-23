# Decisions

The choices that shape this repo, and why. Each one is still in force in the code.

## Results come from Jolpica only

Races, results, sprint results, qualifying and the driver, constructor and circuit tables all come from the [Jolpica F1 API](https://github.com/jolpica/jolpica-f1), which continues the Ergast dataset. Using one source for results removes a whole class of work: there is no second dataset to reconcile, no rule for which source wins, and no name matching between them.

Standings after each round are derived from results, with sprint points added to race points. The season-end standings tables use Jolpica's official end-of-season standings, so the champions are the official ones.

## Raw data is committed

`data/raw/` holds the full Jolpica dump (1950 to the latest round) and the FastF1 lap and weather extracts for each completed 2026 race, about 10 MB in all. A fresh clone can therefore build everything with no network and no credentials, and nothing depends on a download that might move or disappear. The DuckDB file and the FastF1 HTTP cache are generated, so they are gitignored.

The one-time dump (`scripts/dump_jolpica.py`) and `uv run refresh` stay under Jolpica's rate limits (4 requests a second, 500 an hour). The dump caches every page, so an interrupted run resumes.

## Lap data needs an F1TV login, and only the maintainer needs it

FastF1 reads F1's live-timing archive, which now needs an F1TV token. Only `uv run refresh` fetches laps; readers build from the committed extracts. `refresh` checks the token before it does anything else and exits with login instructions if the token is missing or expired, so a lapsed login never writes anything. If one round fails to download, the rounds that worked are kept and the command exits non-zero.

FastF1 3.8.3 does not send the token the archive asks for ([Fast-F1#978](https://github.com/theOehrly/Fast-F1/issues/978)). One function in `src/f1_analytics/data_sources/fastf1_fetch.py` adds the `Authorization: Bearer` header to FastF1's cached HTTP session. When a FastF1 release fixes the issue, that function goes and the pin moves up. If the workaround fails on two race refreshes in a row, lap data switches to OpenF1. The token lasts about four days, so logging in through the browser before each refresh is an accepted cost.

The FastF1 extracts are committed with an attribution note (see `data/raw/NOTICE.md`). That is a grey area under F1's terms; if a takedown request arrives, the extracts are removed and only derived tables are committed.

## dbt shapes and tests the data, and the build is guarded

The dbt project in `dbt/` reads the raw CSVs directly. Staging models type and rename them, and the marts are the tables the analysis reads. Checks that matter, such as every result pointing at a known driver or every lap extract being complete, are dbt tests that fail the build.

`uv run build` runs `dbt build` into a fresh temporary DuckDB file and swaps it in only if every model and test passes. It also refuses the swap if a table that only ever grows (results, sprint results, qualifying, the FastF1 tables, pit stops, car races, practice stints, weather forecasts, race incidents and the stop rules) would shrink, because that means a raw file was truncated or lost. In both cases the previous DuckDB file is left as it was. The dbt project carries its own profile and has no package dependencies, so it never downloads anything.

## Reports are Quarto documents that only call `analysis/`

Each report is `reports/<date>-<slug>/report.qmd`. Every figure, table and number in it comes from a function in `src/f1_analytics/analysis/`, and those functions have tests. A report does not run SQL, import plotly or compute anything itself, so what a reader sees is what the tests cover.

The rendered HTML is committed so the reports can be read without rendering them. It loads plotly.js from its CDN rather than embedding it, which keeps each file small. The PDFs are generated locally and gitignored.

One exception: the pit-stop forecast page (`reports/2026-10-24-williams-cota-pit-stop-forecast/`) is rendered with `embed-resources: true` and to HTML only, so it is one self-contained file that works offline. It has no plotly chart, and its weather and start-tyre controls are a small inline script over data embedded in the page, not Quarto's OJS, whose runtime loads its input library from a CDN and does not run from a `file://` URL.

CI runs the test suite and the build, but it does not render the reports: rendering needs Quarto, TeX and Chrome. The reports are rendered locally from a fresh clone before they are committed.

## Golden comparison

`reports/golden/` holds the original Singapore and Zandvoort PDF reports. Whenever the pipeline changes, the values in those PDFs are regenerated from the current code and compared against them, within stated tolerances, and every difference is explained in the pull request. This keeps a refactor from silently changing a known answer. The comparison is a review step rather than a test in the suite, because its baselines are the PDFs, not code. The comparison script and its baseline values live outside the repo (they left with `golden_check.py` when the reports moved to Quarto), so the table in each pull request is the record a reader sees.

## The gallery is generated

`uv run gallery` builds `reports/README.md` and `reports/index.html` from each report's frontmatter, newest first. A test fails when the committed copies are out of date, so the gallery cannot drift from the reports.

GitHub Pages publishes only the report HTML and the gallery, through `.github/workflows/pages.yml`. A workflow is used instead of serving a branch because a branch would publish the whole repo, raw data included. The workflow copies files; it does not render.

## Orchestration is one command

`uv run build` (and `uv run refresh` for new data) is the whole pipeline. The data is small and refreshed by hand after each race, so a scheduler would add moving parts without adding value.
