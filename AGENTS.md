# AGENTS.md

Local Formula 1 data pipeline and analysis project. Python source lives in `src/f1_analytics/`, scripts in `scripts/`, the dbt project (SQL models and tests) in `dbt/`, tests in `tests/`.

Set up and run the tests with:

```bash
uv sync && uv run pytest
```

Build the DuckDB file from the committed `data/raw/` with `uv run build` (offline). `uv run refresh` needs an F1TV login; see `README.md`.

The test suite is offline: `tests/conftest.py` blocks all network access, so no credentials are needed.

Reports live in topic folders: `reports/<topic>/recurring/report.qmd` is the page re-rendered for each race (today only `team_stops`), and `reports/<topic>/editions/<date>-<slug>/report.qmd` are frozen, hand-picked editions. They only call `f1_analytics.analysis` (no plotly, SQL or computation in a `.qmd`, except a file named `explore.qmd`, below). After `uv run build`, `uv run quarto render reports` re-renders only the `recurring/` pages; an edition is never re-rendered by the project (`quarto render <edition>/report.qmd` still works by hand). Another race's `team_stops` page: `-P constructor_id:… -P season:… -P round:… -P compounds:HARD=C3,MEDIUM=C4,SOFT=C5`. A topic gets a `recurring/` folder only when it starts repeating.

Exploration: before building, a new question gets one exploratory session in an `explore.qmd` in its topic folder, beside its `report.qmd`; the reference is [the COTA explore.qmd](reports/team_stops/recurring/explore.qmd) (no template). It reads only raw and staging tables (the `staging` schema of the DuckDB file built from the committed `data/raw/`), never marts, and starts only on raw data already committed: a missing slice is a library ticket first, and no live fetch. Its SQL is exempt from mart rule 3 (`report.qmd`, `analysis/data.py` and analysis modules stay strict, and `data.py` gets no explore loaders); its evidence uses only `profile`, `compare` and `violations` from `f1_analytics.analysis.explore`. It is done when five sections are filled: question kind (forecast or history) and data used; rules and impossible answers, each backed by a `compare` or `violations` result; outliers with reasons; missing inputs from `profile` (model-used columns only); the opening-block wording plus the method in one line. No one-line method after one session → back to a forge, not to building. Benchmark and backtest belong to the build, not exploration. Commit `explore.qmd` only: it is out of the gallery and site, and its rendered `explore.html` is gitignored (`uv run quarto render reports/<topic>/…/explore.qmd`, then delete the HTML).

Question lane: once its raw slice is committed, a new question goes explore → build → published page with no epic or story files, at most one build ticket and a quick review, aiming at two working sessions (one to explore, one to build and publish). Every piece it lacks lives in its own topic folder or as its own `one_off` marts (`meta.question` naming the topic folder). New raw data (a new source or a backfill), raw ELT and `core` marts are library work, with the full story, plan and review process; the library backlog holds only existing helpers and known debt, nothing speculative. Promotion is a tag flip to `core` plus a passing mart check. A forecast's `report.qmd` shows the method against a naive benchmark, or ships `status: provisional` with "not backtested"; a report may ship with known gaps declared in `gaps`.

Every dbt mart is tagged `core` or `one_off` (with `meta.question` naming its `reports/` topic folder; a report reads `core` marts or its own topic's `one_off` marts), and `tests/test_mart_check.py` enforces rules 1–7 of the mart conventions: all report SQL lives in `analysis/data.py`, whose loaders declare their tables with `@reads(...)`.

Report frontmatter may carry the optional `status: provisional | validated` and a `gaps:` list (one known gap per `- ` line); the gallery shows both, and any other `status` fails `uv run gallery`.

`reports/README.md` and `reports/index.html` are generated: after adding a report or changing its frontmatter, run `uv run gallery` (a test fails until you do).
