"""PostGIS destination and an explicitly labeled SQLite offline demonstration."""
import json
import sqlite3
from contextlib import contextmanager

DDL = """
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
"""


class SQLiteStore:
    """Stores JSON; does NOT validate PostgreSQL or PostGIS behavior."""
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS signals (
            source TEXT, source_id TEXT, updated_at TEXT, payload_hash TEXT, record TEXT,
            PRIMARY KEY(source, source_id))""")
        self.conn.commit()

    @contextmanager
    def transaction(self):
        with self.conn:
            yield

    def upsert(self, r):
        cursor = self.conn.execute("""INSERT INTO signals VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, source_id) DO UPDATE SET updated_at=excluded.updated_at,
            payload_hash=excluded.payload_hash, record=excluded.record
            WHERE excluded.updated_at >= signals.updated_at
            AND excluded.payload_hash <> signals.payload_hash""",
            (r["source"], r["source_id"], r["updated_at"], r["payload_hash"], json.dumps(r)))
        return cursor.rowcount == 1

    def records(self):
        return [json.loads(row[0]) for row in self.conn.execute(
            "SELECT record FROM signals ORDER BY source, source_id")]

    def close(self):
        self.conn.close()


class PostgresStore:
    def __init__(self, dsn):
        import psycopg
        self.conn = psycopg.connect(dsn, autocommit=True, connect_timeout=10)

    def initialize(self):
        with self.conn.transaction():
            self.conn.execute(DDL)

    def transaction(self):
        return self.conn.transaction()

    def upsert(self, r):
        from psycopg.types.json import Jsonb
        params = dict(r)
        params["warnings"], params["raw"] = Jsonb(r["warnings"]), Jsonb(r["raw"])
        result = self.conn.execute("""INSERT INTO iris_staging.signal_ingest AS old
            (source, source_id, kind, title, published_at, updated_at, source_url,
             country, voltage_kv, geometry, warnings, payload_hash, raw)
            VALUES (%(source)s, %(source_id)s, %(kind)s, %(title)s, %(published_at)s,
             %(updated_at)s, %(source_url)s, %(country)s, %(voltage_kv)s,
             CASE WHEN %(x)s::double precision IS NULL THEN NULL ELSE
             ST_SetSRID(ST_MakePoint(%(x)s::double precision, %(y)s::double precision),25832) END,
             %(warnings)s, %(payload_hash)s, %(raw)s)
            ON CONFLICT(source, source_id) DO UPDATE SET
             kind=excluded.kind, title=excluded.title, published_at=excluded.published_at,
             updated_at=excluded.updated_at, source_url=excluded.source_url,
             country=excluded.country, voltage_kv=excluded.voltage_kv,
             geometry=excluded.geometry, warnings=excluded.warnings,
             payload_hash=excluded.payload_hash, raw=excluded.raw,
             ingested_at=CURRENT_TIMESTAMP
            WHERE excluded.updated_at >= old.updated_at AND excluded.payload_hash <> old.payload_hash
            RETURNING source_id""", params)
        return result.fetchone() is not None

    def close(self):
        self.conn.close()

