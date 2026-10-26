import argparse
import json
import os
from pathlib import Path

from .pipeline import harvest
from .source import FixtureSource, RestSource
from .storage import PostgresStore, SQLiteStore


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace NaN/Infinity in quarantined payloads with explicit strings.
    clean = json.loads(json.dumps(value), parse_constant=lambda x: f"INVALID_NUMBER:{x}")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(clean, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description="IRIS fixture fallback; see SOURCE_ASSESSMENT.md")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path)
    source.add_argument("--gateway", help="Authorized HTTPS iris-demo-v1 service; NOT MaStR SOAP")
    parser.add_argument("--source", default="iris-sig24-synthetic", help="Stable source namespace")
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sqlite", type=Path, help="Offline demo only")
    target.add_argument("--postgres", action="store_true", help="Read DATABASE_URL from environment")
    parser.add_argument("--init-db", action="store_true", help="Create proposed schema; review first")
    parser.add_argument("--output", type=Path, default=Path("run"))
    args = parser.parse_args()
    store = None
    try:
        if args.fixture and args.source != "iris-sig24-synthetic":
            raise ValueError("Fixture runs must retain the synthetic namespace")
        if args.gateway and args.source == "iris-sig24-synthetic":
            raise ValueError("Gateway runs require an explicit --source namespace")
        if args.postgres:
            store = PostgresStore(os.environ["DATABASE_URL"])
            if args.init_db:
                store.initialize()
        else:
            args.sqlite.parent.mkdir(parents=True, exist_ok=True)
            store = SQLiteStore(args.sqlite)
        adapter = FixtureSource(args.fixture) if args.fixture else RestSource(
            args.gateway, token=os.environ.get("IRIS_GATEWAY_TOKEN"))
        report = harvest(adapter, store, args.source, args.since, args.until)
        report["storage"] = "postgresql-postgis" if args.postgres else "sqlite-demo"
        report["status"] = "completed_with_rejections" if report["rejected"] else "completed"
        write_json(args.output / "quality-report.json", report)
        if args.sqlite:
            write_json(args.output / "signals.json", store.records())
        print(json.dumps({k: v for k, v in report.items() if k not in ("rejected", "warnings")}))
        return 2 if report["rejected"] else 0
    except Exception as exc:
        # Driver errors can expose connection credentials: report type only.
        write_json(args.output / "failure.json", {"status": "failed", "error_type": type(exc).__name__,
                   "hint": "Check source contract, window, configuration and database connectivity. "
                           "A failure writing output may occur after database commit; rerun is safe."})
        print(f"Run failed ({type(exc).__name__}); see failure.json.")
        return 1
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())

