# Source assessment — checked 2026-10-26

## Findings

The assignment names a "Marktstammdatenregister Daily Delta API" with REST/Delta.
No matching public REST contract was established during this investigation.
This is an unresolved assumption, not proof that no such private gateway exists.

The [official Webdienst help](https://www.marktstammdatenregister.de/MaStRHilfe/subpages/webdienst.html)
publishes WSDL/XSD descriptions and requires a web-service key for data operations.
It describes delta retrieval of new **or modified** objects. A modification therefore
cannot by itself establish a new connection request.

The [official generated API documentation, version 26.2.189](https://www.marktstammdatenregister.de/MaStRHilfe/files/webdienst/Funktionen_MaStR_Webdienste_V26.2.189.html)
documents connection-point structures and network-operator-specific operations.
This does not establish a public feed of newly filed high-voltage requests or newly
registered substations. Event semantics and access permissions still need confirmation.
A planned connection point is not automatically a filed request.

The [official download page](https://www.marktstammdatenregister.de/MaStR/Datendownload)
offers public XML snapshots, normally refreshed daily. This is not a REST event stream.
Snapshot comparison can detect newly observed assets; it cannot establish when a
connection request was filed. No multi-gigabyte snapshot was downloaded.

The [reference repository](https://github.com/amaurisantosjr/iris-sample), inspected at
commit 76d448eb8953488e55bc4c3ba193629d534a7bb8, uses
GetVerkleinerteOeffentlicheEinheitStromerzeugung in app/config/data_sources.py.
Its MaStR scraper fetches a bounded number of pages and its energy asset model targets
iris_core with EPSG:4326. No iris_staging.signal_ingest schema was found.
The repository's PostgreSQL 17/PostGIS 3.5 container differs from the assignment's 16/3.4.

## Decision and alternative

Use the assignment's fixture fallback. Demonstrate the requested event filtering,
normalization, geometry, pagination, idempotency, errors and proposed loading behavior
without misrepresenting source access. Every fixture is authored synthetic data;
English field names belong to our demo contract, not the MaStR data dictionary.

Preferred route for a live collector: obtain the intended authorized REST gateway,
its data dictionary and sample responses from IRIS. If they mean the official SOAP
service, agree on the changed integration pattern and verify whether their access
actually exposes the two event types before implementing an adapter.

A manually obtained public XML snapshot is a justified alternative only if IRIS accepts
the different signal "newly observed registered asset". It is not equivalent to the
requested events. No access controls are bypassed and no production feed is claimed.

## Questions to resolve with IRIS

1. What is the exact Daily Delta REST endpoint and authentication process?
2. Which fields prove a new high-voltage connection request or substation registration?
3. Is geography all Germany or NRW only? Is the minimum voltage 110 kV for both types?
4. Can you provide the existing signal_ingest schema or approve the proposed one?
5. If the named feed is unavailable, is this documented fixture fallback acceptable?

These questions are prepared for review; no email has been sent.

