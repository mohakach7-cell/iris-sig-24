import copy
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
import requests

from iris_harvester.pipeline import harvest, normalize, timestamp
from iris_harvester.source import FixtureSource, RestSource, SourceError
from iris_harvester.storage import SQLiteStore

START = "2026-10-25T00:00:00Z"
END = "2026-10-26T00:00:00Z"
FIXTURE = Path(__file__).parents[1] / "fixtures/demo.json"


@pytest.fixture
def record():
    return json.loads(FIXTURE.read_text())[0]["items"][0]


@pytest.fixture
def store(tmp_path):
    db = SQLiteStore(tmp_path / "test.sqlite")
    yield db
    db.close()


def norm(record):
    return normalize(record, "test", timestamp(START), timestamp(END))


def test_fixture_and_rerun(store):
    first = harvest(FixtureSource(FIXTURE), store, "synthetic", START, END)
    assert first["seen"] == 11
    assert first["written"] == 3
    assert first["unchanged_or_stale"] == 1
    assert len(first["rejected"]) == 3
    assert sum(first["filtered"].values()) == 4
    assert first["warnings"] == [{"id": "DEMO-003", "issues": ["missing_coordinates"]}]
    before = store.records()
    second = harvest(FixtureSource(FIXTURE), store, "synthetic", START, END)
    assert second["written"] == 0
    assert second["unchanged_or_stale"] == 4
    assert store.records() == before


def test_projection_known_central_meridian(record):
    record.update(longitude=9, latitude=51)
    normalized, reason = norm(record)
    assert reason is None
    assert normalized["x"] == pytest.approx(500000, abs=0.01)
    assert normalized["y"] == pytest.approx(5649824.89, abs=1)
    assert normalized["srid"] == 25832


@pytest.mark.parametrize("field,value", [
    ("latitude", 999), ("longitude", float("nan")), ("longitude", float("inf")),
    ("latitude", True), ("longitude", "6.7"), ("longitude", 51), ("latitude", 6),
    ("voltage_kv", None), ("voltage_kv", -1), ("published_at", None),
    ("updated_at", "2026-10-25"), ("title", ""), ("id", None),
    ("source_url", "javascript:alert(1)")])
def test_invalid_record(record, field, value):
    record[field] = value
    with pytest.raises(ValueError):
        norm(record)


def test_invalid_partial_coordinate(record):
    record.update(longitude=None, latitude=999)
    with pytest.raises(ValueError):
        norm(record)


@pytest.mark.parametrize("field,value,reason", [
    ("kind", "generation_unit", "unsupported_event_type"),
    ("kind", [], "unsupported_event_type"),
    ("country", "FR", "outside_country"),
    ("voltage_kv", 109.9, "below_110_kv"),
    ("published_at", "2026-10-24T00:00:00Z", "older_publication"),
    ("updated_at", END, "outside_update_window"),
])
def test_filter(record, field, value, reason):
    record[field] = value
    assert norm(record) == (None, reason)


def test_time_boundaries_and_offsets(record):
    record.update(published_at=START, updated_at="2026-10-25T01:00:00+01:00")
    assert norm(record)[0] is not None
    record["published_at"] = END
    with pytest.raises(ValueError):
        norm(record)


def test_updates_and_stale_replay(store, record):
    first = norm(record)[0]
    with store.transaction():
        assert store.upsert(first)
    record.update(title="Corrected", updated_at="2026-10-25T11:00:00Z")
    newer = norm(record)[0]
    with store.transaction():
        assert store.upsert(newer)
        assert not store.upsert(first)
        assert not store.upsert(newer)
    assert len(store.records()) == 1
    assert store.records()[0]["title"] == "Corrected"


def test_namespace_separation(store, record):
    first = norm(record)[0]
    with store.transaction():
        store.upsert(first)
        store.upsert(dict(first, source="other-source"))
    assert len(store.records()) == 2


def test_page_failure_rolls_back(store, record):
    class Broken:
        def pages(self, *args):
            yield [record]
            raise SourceError("Second page failed")
    with pytest.raises(SourceError):
        harvest(Broken(), store, "test", START, END)
    assert store.records() == []


def response(status=200, items=None, cursor=None):
    r = Mock(status_code=status)
    r.json.return_value = {"contract": "iris-demo-v1", "items": items or [], "next_cursor": cursor}
    return r


def client(responses, **kwargs):
    session = Mock()
    session.get.side_effect = responses
    sleep = Mock()
    return RestSource("https://example.invalid/feed", session=session, sleep=sleep, **kwargs), session, sleep


def test_retry_and_empty_page_continuation(record):
    src, session, sleep = client([response(503), response(cursor="next"), response(items=[record])])
    assert list(src.pages(START, END)) == [[], [record]]
    assert session.get.call_count == 3
    assert sleep.call_count == 1
    assert session.get.call_args.kwargs["params"]["cursor"] == "next"
    assert session.get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("failure", [requests.Timeout(), requests.ConnectionError(), response(429), response(503)])
def test_retry_exhaustion(failure):
    src, session, sleep = client([failure, failure, failure])
    with pytest.raises(SourceError):
        list(src.pages(START, END))
    assert session.get.call_count == 3


@pytest.mark.parametrize("status", [301, 401, 403, 404])
def test_nonretryable_status(status):
    src, session, _ = client([response(status)])
    with pytest.raises(SourceError):
        list(src.pages(START, END))
    assert session.get.call_count == 1


def test_invalid_json():
    bad = response()
    bad.json.side_effect = ValueError()
    src, _, _ = client([bad])
    with pytest.raises(SourceError):
        list(src.pages(START, END))


def test_pagination_loop():
    src, _, _ = client([response(cursor="same"), response(cursor="same")])
    with pytest.raises(SourceError, match="Repeated"):
        list(src.pages(START, END))


def test_page_cap():
    src, _, _ = client([response(cursor="next")], max_pages=1)
    with pytest.raises(SourceError, match="limit"):
        list(src.pages(START, END))


def test_empty_response():
    src, _, _ = client([response()])
    assert list(src.pages(START, END)) == [[]]


def test_bad_contract():
    bad = response()
    bad.json.return_value = {"Data": []}
    src, _, _ = client([bad])
    with pytest.raises(SourceError, match="contract|iris-demo"):
        list(src.pages(START, END))


def test_fixture_truncated(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(json.dumps([{"contract": "iris-demo-v1", "items": [], "next_cursor": "missing"}]))
    with pytest.raises(SourceError):
        list(FixtureSource(path).pages(START, END))

