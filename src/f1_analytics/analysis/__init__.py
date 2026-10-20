"""Analysis for the reports.

`data` is the only module that reads DuckDB (read-only). The rest are pure
functions over DataFrames (`results`, `simulation`, `singapore`, `zandvoort`,
`championship_leaders` and the `pit_stops` subpackage), text formatting
(`formatting`) and Plotly figures (`figures`).
"""
