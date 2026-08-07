-- Per season/round coverage comparison between the Kaggle baseline and the
-- Jolpica/Ergast supplemental source. Surfaces where one source has data the
-- other lacks, or where row counts diverge, without merging either source.
CREATE OR REPLACE VIEW kaggle_jolpica_coverage AS
WITH all_rounds AS (
    SELECT DISTINCT season, round FROM results
    UNION
    SELECT DISTINCT season, round FROM raw_jolpica_results
),
kaggle_results AS (
    SELECT season, round, COUNT(*) AS kaggle_result_rows
    FROM results
    GROUP BY season, round
),
jolpica_results AS (
    SELECT season, round, COUNT(*) AS jolpica_result_rows
    FROM raw_jolpica_results
    GROUP BY season, round
),
kaggle_qualifying AS (
    SELECT season, round, COUNT(*) AS kaggle_qualifying_rows
    FROM raw_qualifying
    GROUP BY season, round
),
jolpica_qualifying AS (
    SELECT season, round, COUNT(*) AS jolpica_qualifying_rows
    FROM raw_jolpica_qualifying
    GROUP BY season, round
)
SELECT
    ar.season,
    ar.round,
    COALESCE(kr.kaggle_result_rows, 0) AS kaggle_result_rows,
    COALESCE(jr.jolpica_result_rows, 0) AS jolpica_result_rows,
    COALESCE(kq.kaggle_qualifying_rows, 0) AS kaggle_qualifying_rows,
    COALESCE(jq.jolpica_qualifying_rows, 0) AS jolpica_qualifying_rows,
    CASE
        WHEN COALESCE(kr.kaggle_result_rows, 0) = 0 AND COALESCE(jr.jolpica_result_rows, 0) = 0 THEN 'no_data'
        WHEN COALESCE(kr.kaggle_result_rows, 0) = 0 THEN 'jolpica_only'
        WHEN COALESCE(jr.jolpica_result_rows, 0) = 0 THEN 'kaggle_only'
        WHEN kr.kaggle_result_rows = jr.jolpica_result_rows THEN 'match'
        ELSE 'row_count_diverges'
    END AS results_coverage_status
FROM all_rounds ar
LEFT JOIN kaggle_results kr ON ar.season = kr.season AND ar.round = kr.round
LEFT JOIN jolpica_results jr ON ar.season = jr.season AND ar.round = jr.round
LEFT JOIN kaggle_qualifying kq ON ar.season = kq.season AND ar.round = kq.round
LEFT JOIN jolpica_qualifying jq ON ar.season = jq.season AND ar.round = jq.round
ORDER BY ar.season, ar.round;
