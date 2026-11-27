"""Dashboard facts: no runs, a running run, completed runs; next step in workflow order."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from bns.app import dashboard

ROOT = Path(__file__).resolve().parents[2]


def empty_repo(tmp_path):
    (tmp_path / "configs").mkdir()
    for p in (ROOT / "configs").glob("*.yaml"):
        shutil.copy(p, tmp_path / "configs" / p.name)
    return tmp_path


def test_no_runs_gives_an_empty_state_and_the_first_run_as_next_step(tmp_path):
    d = dashboard.build(empty_repo(tmp_path))
    assert d.latest is None and d.running is None and d.bands == []
    assert d.next_step == "first_run"
    assert d.area["name"] == "tahrir_bab_al_sharqi_study" and d.dataset["available"] is False
    assert len(d.scenarios) == 5


def test_a_running_run_takes_precedence(tmp_path, monkeypatch):
    repo = empty_repo(tmp_path)
    folder = repo / "outputs" / "app_runs" / "r1"
    folder.mkdir(parents=True)
    (folder / "request.json").write_text(json.dumps({"pid": 1, "started_utc": datetime.now(timezone.utc).isoformat()}))
    monkeypatch.setattr(dashboard.control, "_alive", lambda pid, started: True)
    d = dashboard.build(repo)
    assert d.running is not None and d.running.execution == "Running" and d.next_step == "progress"


def test_next_step_follows_the_workflow():
    step = dashboard.next_step
    assert step(running=False, latest=True, visited=set(), validated=False) == "explore_coverage"
    assert step(running=False, latest=True, visited={"coverage"}, validated=False) == "compare"
    assert step(running=False, latest=True, visited={"coverage", "comparison"}, validated=False) == "review_limitations"
    assert step(running=False, latest=True, visited={"coverage", "comparison", "limitations"},
                validated=False) == "report"
    assert step(running=False, latest=True, visited={"coverage", "comparison", "reports"}, validated=True) \
        == "new_experiment"


def test_the_repository_dashboard_uses_saved_runs_and_the_synthetic_dataset():
    d = dashboard.build(ROOT)
    assert d.dataset["available"] and d.dataset["synthetic"] == 2507 and d.dataset["buildings"] == 2521
    if d.latest is not None:
        assert len(d.bands) == len(d.latest.scenarios) and not d.latest.invalid   # 1 to 5 carriers
        low, high = dashboard.ranges(d.bands, "coverage")
        assert 0.0 <= low <= high <= 1.0
