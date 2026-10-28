# Validation performed — updated 2026-10-28

Environment: Windows, Python 3.12.0. Exact installed dependency versions are in
requirements-tested.txt.

## Executed

Command: `python -m pytest -q --basetemp ../../work/pytest-validation`

Initial run on 2026-10-26: **44 passed, 1 skipped**.
The skipped integration test was subsequently executed successfully; see below.
The work directory was used for test temporary files because the execution environment
prevented atomic file replacement in its default Windows temporary directory. No file
permission workaround was added to application behavior.

Coverage includes event/country/voltage filters, dates and timezone normalization,
invalid and incomplete coordinates, a known UTM central-meridian projection, duplicate
and stale-record handling, separate source identities, transaction rollback after a
later page failure, empty pages, cursor loops, page limits, malformed JSON/contracts,
timeouts, connection failures, retry exhaustion and non-retryable HTTP statuses.
CLI tests verify exit codes, report files and end-to-end replay.

The fixture CLI was also executed twice against the same SQLite database.

| Metric | First run | Repeat |
| --- | ---: | ---: |
| Pages | 2 | 2 |
| Inputs | 11 | 11 |
| Inserted/updated | 3 | 0 |
| Unchanged/stale observations | 1 | 4 |
| Filtered | 4 | 4 |
| Rejected | 3 | 3 |
| Unresolved-location warnings | 1 | 1 |
| Stored signals | 3 | 3 |

Actual outputs are in examples/first and examples/rerun.
The sample failures are deliberate: invalid latitude, missing title and a non-object
record. Filters exclude low voltage, an older publication, France and a generation unit.
The missing-coordinate signal is retained with NULL geometry and a warning.

## PostgreSQL/PostGIS integration — 2026-10-28

Executed by the user in Windows PowerShell against the local Docker container
using postgis/postgis:16-3.4, after Docker reported the container healthy.

Command: `..\..\work\venv\Scripts\python.exe -m pytest tests/test_postgres.py -v`

Result visible in the user-provided terminal screenshot: **1 passed in 12.34s**.
The passing test is `test_postgis_rerun_geometry_and_rollback`. It checks PostgreSQL
16 and PostGIS 3.4 versions, ingestion, repeat-run idempotency, EPSG:25832 geometry,
NULL geometry for unresolved locations, and transaction rollback on a later page failure.
This result was observed from the screenshot, not independently rerun by the assistant.

Across the two separate runs, all 45 tests have passed. This is not a claim of a
single combined 45-test execution or of live MaStR connectivity.

## Not executed / not established

- Live authenticated MaStR acquisition and production event-field mapping.
- Real HTTP gateway behavior: the adapter is tested using mocks, not a deployed endpoint.
- Existing IRIS staging compatibility: the schema is proposed, not supplied by IRIS.
- Production scale, scheduler behavior and full national-border validation.

This is a fixture fallback demonstration. Do not describe it as a verified real-time
production integration or claim the synthetic examples came from MaStR.
