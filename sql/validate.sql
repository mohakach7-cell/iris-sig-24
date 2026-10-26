-- Run against the dedicated assignment database.
SELECT version(), postgis_full_version();
SELECT source, count(*) AS signals,
       count(*) FILTER (WHERE geometry IS NULL) AS unresolved
FROM iris_staging.signal_ingest GROUP BY source;
-- Expected: zero rows.
SELECT source, source_id, count(*)
FROM iris_staging.signal_ingest GROUP BY source, source_id HAVING count(*) > 1;
-- Expected: zero rows.
SELECT source_id FROM iris_staging.signal_ingest
WHERE geometry IS NOT NULL AND (ST_SRID(geometry) <> 25832 OR NOT ST_IsValid(geometry));
-- Inspect traceability and quality.
SELECT source_id, title, published_at, source_url, ST_AsText(geometry), warnings
FROM iris_staging.signal_ingest ORDER BY source, source_id;

