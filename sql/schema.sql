
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS iris_staging;
CREATE TABLE IF NOT EXISTS iris_staging.signal_ingest (
    source text NOT NULL,
    source_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('grid_connection_request','substation_registration')),
    title text NOT NULL,
    published_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    source_url text NOT NULL,
    country text NOT NULL CHECK (country = 'DE'),
    voltage_kv double precision NOT NULL CHECK (voltage_kv >= 110),
    geometry geometry(Point,25832),
    warnings jsonb NOT NULL,
    payload_hash text NOT NULL,
    raw jsonb NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source, source_id),
    CHECK (published_at <= updated_at)
);
CREATE INDEX IF NOT EXISTS signal_ingest_geometry_idx
ON iris_staging.signal_ingest USING gist (geometry);
