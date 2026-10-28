# IRIS-SIG-24 — Network signal harvester

**Status: tested fixture-based fallback, not a live MaStR collector.**
The brief explicitly allows fixtures when the named source is inaccessible or obsolete.
The alleged public "MaStR Daily Delta REST API" and its coverage of the requested events
have not been verified. Read [SOURCE_ASSESSMENT.md](SOURCE_ASSESSMENT.md) before evaluating this submission.

This standalone Python module demonstrates ingestion of explicit high-voltage connection
request and substation registration events into a proposed `iris_staging.signal_ingest`
schema. All bundled records are synthetic, use `example.invalid` URLs, and are labeled
`iris-sig24-synthetic`. No private access or production credentials are needed for the demo.

## Install

Python 3.12+:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[test]"
.venv/Scripts/python -m pytest -q
```

On Linux/macOS replace `.venv/Scripts/python` with `.venv/bin/python`.
The tested Windows environment is recorded in `requirements-tested.txt`.

## Offline demonstration

Run from this directory:

```powershell
.venv/Scripts/python -m iris_harvester.cli --fixture fixtures/demo.json --sqlite run/demo.sqlite --since 2026-10-25T00:00:00Z --until 2026-10-26T00:00:00Z --output run/first
.venv/Scripts/python -m iris_harvester.cli --fixture fixtures/demo.json --sqlite run/demo.sqlite --since 2026-10-25T00:00:00Z --until 2026-10-26T00:00:00Z --output run/rerun
```

Both commands intentionally exit **2** because the example contains three malformed records.
Exit 0 = completed without rejections; 2 = completed with quarantined records; 1 = failed.
Do not treat 2 as a transport failure or retry indefinitely.

Expected first run on a fresh database: 11 inputs across 2 pages; 3 inserts, 1 duplicate,
4 filtered records, 3 rejected records, 1 unresolved location.
Expected repeat: 0 writes, 4 unchanged/stale observations, still exactly 3 stored records.

The report includes rejected raw records and reasons. `signals.json` is the complete
SQLite demo snapshot. These files are synthetic examples, not anonymized production data.
SQLite demonstrates processing only; it does not establish PostGIS compatibility.

## PostgreSQL 16 / PostGIS 3.4

The schema is proposed because the reference repository contains no `signal_ingest`
definition. Do not apply it blindly to an existing IRIS database.
Credentials are supplied through environment variables, never source files.

1. Install/start Docker, set `POSTGRES_PASSWORD` to your own local password, then run
   `docker compose up -d --wait`.
2. Set `DATABASE_URL` to the local connection string:
   `postgresql://iris:<URL-encoded-password>@localhost:5434/iris`.
3. Run:

```powershell
.venv/Scripts/python -m iris_harvester.cli --fixture fixtures/demo.json --postgres --init-db --since 2026-10-25T00:00:00Z --until 2026-10-26T00:00:00Z --output run/postgres-first
.venv/Scripts/python -m iris_harvester.cli --fixture fixtures/demo.json --postgres --since 2026-10-25T00:00:00Z --until 2026-10-26T00:00:00Z --output run/postgres-rerun
```

Review `sql/schema.sql`; `--init-db` creates the extension, schema, table and index.
Run `sql/validate.sql` using a PostgreSQL SQL client.
For the opt-in integration test, set `IRIS_TEST_DATABASE_URL` to a **dedicated test**
database and run `python -m pytest tests/test_postgres.py -q`.
The test checks the required database versions, geometry, repeat ingestion and rollback.
It creates schema objects and removes only rows in its random test namespace.
The user executed the PostGIS test on 2026-10-28: **1 passed in 12.34s**,
confirmed by the supplied terminal screenshot. See VALIDATION.md for the evidence and scope.

## Mapping and assumptions

| Contract field | Destination / rule |
| --- | --- |
| id | source_id; identity is (source, source_id) |
| kind | exactly grid_connection_request or substation_registration |
| country | DE only; nationwide scope, not silently restricted to NRW |
| voltage_kv | numeric, finite, at least 110 kV for both event types |
| title, source_url | required and preserved |
| published_at | actual event publication time; never invented from a modification date |
| updated_at | source revision timestamp, timezone required |
| longitude, latitude | WGS84 x/y input; pyproj transforms to EPSG:25832 |
| other source fields | preserved in raw JSON including city / geographic context |

The 110 kV threshold and applying it to substations are conservative assumptions to
confirm with IRIS. No voltage level is inferred from a title.
Country is supplied explicitly; coordinate envelope 5.5–15.5 E, 47–55.2 N is a
coarse sanity check, not a border polygon. Missing/partial coordinates remain NULL with
a warning. Present invalid coordinates are rejected; no city-centroid guessing.

Both updated_at and published_at must fall inside [since, until) for this new-event
collector. An old publication modified today is not treated as a new request.
Consequently this is not a full historical asset synchronizer: later changes to older
signals need an overlapping publication window or a future separate update workflow.

## Reliability

- Page iteration continues through empty pages with a next cursor.
- Three attempts for connection errors, timeouts, HTTP 429 and selected 5xx responses;
  bounded backoff, connection/read timeouts and maximum page count.
- Authentication failures, redirects, malformed pages and cursor loops fail the run.
- All writes in one transaction: a page/storage failure rolls back the run.
- Parameterized SQL and unique identity prevent duplicate rows.
- Older source versions cannot overwrite newer ones. Identical payloads do not write.
  At equal update timestamps a changed payload is accepted; last encountered wins.
- Explicit windows make retry/replay deterministic. There is no automatic checkpoint
  or scheduler: an operator advances the window only after reviewing success and
  quarantines. Use overlapping windows for late arrivals.
- Output files are atomically replaced individually. Reports are written after DB commit;
  a filesystem failure can leave committed data without a report. Safe replay repairs this.
  Use a distinct output directory per run, and respect exit status instead of stale files.

## Optional REST adapter

`--gateway https://your-authorized-service/path --source your-stable-source-name`
uses an explicitly configured gateway implementing **our proposed iris-demo-v1 contract**.
No gateway is bundled or claimed to exist at MaStR. `IRIS_GATEWAY_TOKEN` is optional.
The endpoint receives `since`, `until` and an opaque `cursor`. It must provide stable,
complete pages for that window:

```json
{"contract":"iris-demo-v1","items":[],"next_cursor":null}
```

Each item follows `fixtures/demo.json`. Actual MaStR SOAP/XML requires a separately
verified mapping and authorized access before this adapter could be used with live data.

## Repository relationship and deliverables

Reference commit: `76d448eb8953488e55bc4c3ba193629d534a7bb8`.
The reference scraper retrieves generation units, and its model writes energy assets
to `iris_core`. This module stays separate so its smaller dependency set, explicit event
semantics and proposed staging schema can be reviewed independently.
No upstream source code is copied. No dashboard or OpenAI key is required.

- `iris_harvester/`: source adapters, validation, storage and command line.
- `fixtures/`, `tests/`: synthetic examples and automated checks.
- `examples/`: actual local demo output and repeat-run reports.
- `sql/`, `compose.yaml`: proposed schema, validations and required DB version.
- `SOURCE_ASSESSMENT.md`: evidence, blockers and justified alternatives.
- `VALIDATION.md`: actual checks and remaining limitations.

Before calling this a live solution: confirm the endpoint/event coverage, approve the
source mapping and schema. The local PostGIS fixture integration test has passed;
live source behavior still needs separate validation.

