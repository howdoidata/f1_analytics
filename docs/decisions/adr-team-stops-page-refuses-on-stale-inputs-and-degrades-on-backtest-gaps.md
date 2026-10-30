# The team_stops page refuses to render on stale inputs and degrades on backtest gaps

The recurring team_stops page (`reports/team_stops/recurring/report.qmd`) is re-rendered after each race. Before this change, a missing input either crashed the render (an earlier round with no day-before forecast, start compounds or `car_races` rows broke the season backtest) or passed silently (a re-fetched live forecast not yet built into the database, or a later round rendered with the previous round's results missing, so the fit quietly used fewer rounds).

The page now splits its inputs in two. `build_report` raises `StaleDataError`, failing the render with a message that names each problem and the command that fixes it, when the target race's live forecast file is missing or not the fetch the database holds, or when an earlier round of the season has no results or no pit stops. These feed the headline forecast. The inputs the season backtest checks per round (an earlier round's `car_races` rows, its start compounds, its day-before forecast) never fail the render: `season_backtest` leaves that round out and the page names it with the missing input.

Why, as recorded: spec `spec-recurring-team-stops-report` (CAP-2, CAP-3) states that "work-in-progress analysis doesn't block the report" and that "the backtest is advisory. It never blocks the render". The story 3.2 plan fixes "a missing input never fails the render" for the backtest, and the story 3.3 plan fixes "refusals fail the render" for the forecast's inputs.

Known limits, from the epic 3 retrospective: the fit also reads `car_races`, so an earlier round with results but no `car_races` rows still drops out of the fit with only a backtest note. The user chose to keep this behavior and document it in the README rather than refuse (2026-10-30). A round whose pit stops are never published would block every later page, with no override.

Source: PR #25 (`978804c`) and PR #26 (`7491b03`), `src/f1_analytics/analysis/pit_stop_report.py` (`missing_input`, `season_backtest`, `stale_inputs`, `StaleDataError`).
