import hashlib
import json
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit
from pyproj import Transformer

PROJECT = Transformer.from_crs(4326, 25832, always_xy=True)
TYPES = {"grid_connection_request", "substation_registration"}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid ISO 8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected finite numeric value")
    return float(value)


def normalize(raw, source, since, until):
    if not isinstance(raw, dict):
        raise ValueError("Record must be an object")
    if not isinstance(raw.get("kind"), str) or raw["kind"] not in TYPES:
        return None, "unsupported_event_type"
    if raw.get("country") != "DE":
        return None, "outside_country"
    voltage = number(raw.get("voltage_kv"))
    if voltage <= 0:
        raise ValueError("Voltage must be positive")
    if voltage < 110:
        return None, "below_110_kv"
    for key in ("id", "title", "source_url"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"Missing or invalid {key}")
    url = urlsplit(raw["source_url"])
    if url.scheme not in ("https", "http") or not url.hostname or url.username:
        raise ValueError("Invalid source_url")
    updated, published = timestamp(raw.get("updated_at")), timestamp(raw.get("published_at"))
    if published > updated:
        raise ValueError("Publication time is after update time")
    if not since <= updated < until:
        return None, "outside_update_window"
    if published < since:
        return None, "older_publication"
    warnings = []
    x = y = None
    lon, lat = raw.get("longitude"), raw.get("latitude")
    # A present invalid coordinate is rejected even if its partner is missing.
    if lon is not None:
        lon = number(lon)
        if not 5.5 <= lon <= 15.5:
            raise ValueError("Longitude outside Germany sanity envelope")
    if lat is not None:
        lat = number(lat)
        if not 47 <= lat <= 55.2:
            raise ValueError("Latitude outside Germany sanity envelope")
    if lon is None or lat is None:
        warnings.append("missing_coordinates" if lon is None and lat is None else "incomplete_coordinates")
    else:
        x, y = PROJECT.transform(lon, lat, errcheck=True)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Coordinate transformation failed")
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {"source": source, "source_id": raw["id"], "kind": raw["kind"],
            "title": raw["title"], "published_at": published, "updated_at": updated,
            "source_url": raw["source_url"], "country": "DE", "voltage_kv": voltage,
            "x": x, "y": y, "srid": 25832, "warnings": warnings,
            "payload_hash": digest, "raw": raw}, None


def harvest(source, store, namespace, since, until):
    since, until = timestamp(since), timestamp(until)
    if since >= until:
        raise ValueError("since must be earlier than until")
    report = {"source": namespace, "since": since, "until": until, "pages": 0,
              "seen": 0, "written": 0, "unchanged_or_stale": 0,
              "filtered": {}, "rejected": [], "warnings": []}
    with store.transaction():
        for page in source.pages(since, until):
            report["pages"] += 1
            for raw in page:
                report["seen"] += 1
                identity = raw.get("id") if isinstance(raw, dict) else None
                try:
                    record, reason = normalize(raw, namespace, since, until)
                except (ValueError, TypeError, OverflowError) as exc:
                    report["rejected"].append({"id": identity, "reason": str(exc), "raw": raw})
                    continue
                if record is None:
                    report["filtered"][reason] = report["filtered"].get(reason, 0) + 1
                    continue
                if record["warnings"]:
                    report["warnings"].append({"id": identity, "issues": record["warnings"]})
                changed = store.upsert(record)
                report["written" if changed else "unchanged_or_stale"] += 1
    return report

