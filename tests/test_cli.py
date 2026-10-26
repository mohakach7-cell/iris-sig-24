import json
import sys
from pathlib import Path
from iris_harvester.cli import main

FIXTURE = Path(__file__).parents[1] / "fixtures/demo.json"

def test_cli_exit_codes_and_reports(tmp_path, monkeypatch):
    output = tmp_path / "out"
    args = ["iris", "--fixture", str(FIXTURE), "--sqlite", str(tmp_path / "demo.sqlite"),
            "--since", "2026-10-25T00:00:00Z", "--until", "2026-10-26T00:00:00Z",
            "--output", str(output)]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 2
    report = json.loads((output / "quality-report.json").read_text())
    assert report["status"] == "completed_with_rejections"
    assert len(json.loads((output / "signals.json").read_text())) == 3
    assert main() == 2
    assert json.loads((output / "quality-report.json").read_text())["written"] == 0

def test_cli_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["iris", "--fixture", "missing.json",
        "--sqlite", str(tmp_path / "db.sqlite"), "--since", "bad", "--until", "bad",
        "--output", str(tmp_path / "out")])
    assert main() == 1
    assert json.loads((tmp_path / "out/failure.json").read_text())["status"] == "failed"

