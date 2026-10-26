"""Opt-in test: use a dedicated PostgreSQL 16/PostGIS 3.4 test database."""
import json
import os
import uuid
from pathlib import Path
import pytest
from iris_harvester.pipeline import harvest
from iris_harvester.source import FixtureSource, SourceError
from iris_harvester.storage import PostgresStore

@pytest.mark.skipif(not os.environ.get("IRIS_TEST_DATABASE_URL"), reason="No dedicated PostgreSQL/PostGIS test database")
def test_postgis_rerun_geometry_and_rollback():
    store = PostgresStore(os.environ["IRIS_TEST_DATABASE_URL"])
    namespace = "test-" + uuid.uuid4().hex
    fixture = Path(__file__).parents[1] / "fixtures/demo.json"
    try:
        assert store.conn.execute("SHOW server_version_num").fetchone()[0].startswith("16")
        assert store.conn.execute("SELECT postgis_lib_version()").fetchone()[0].startswith("3.4")
        store.initialize()
        a = harvest(FixtureSource(fixture), store, namespace, "2026-10-25T00:00:00Z", "2026-10-26T00:00:00Z")
        b = harvest(FixtureSource(fixture), store, namespace, "2026-10-25T00:00:00Z", "2026-10-26T00:00:00Z")
        assert a["written"] == 3 and b["written"] == 0
        rows = store.conn.execute("""SELECT source_id, ST_SRID(geometry), ST_X(geometry),
            ST_Y(geometry) FROM iris_staging.signal_ingest WHERE source=%s ORDER BY source_id""",
            (namespace,)).fetchall()
        assert len(rows) == 3
        assert rows[0][1] == 25832 and 300000 < rows[0][2] < 400000
        assert rows[2][1:] == (None, None, None)
        record = json.loads(fixture.read_text())[0]["items"][0]
        record["id"] = "rollback-only"
        class Broken:
            def pages(self, *args):
                yield [record]
                raise SourceError("failure")
        with pytest.raises(SourceError):
            harvest(Broken(), store, namespace, "2026-10-25T00:00:00Z", "2026-10-26T00:00:00Z")
        assert store.conn.execute("SELECT count(*) FROM iris_staging.signal_ingest WHERE source=%s",
                                  (namespace,)).fetchone()[0] == 3
    finally:
        store.conn.execute("DELETE FROM iris_staging.signal_ingest WHERE source=%s", (namespace,))
        store.close()

