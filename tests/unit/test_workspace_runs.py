"""Workspace runs: the request a run executes, its log read back as progress, retries, estimate, outcome."""

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from bns.app import workspace_runs as wr
from bns.geospatial.grid import Grid
from bns.simulation.cache import PathGainCache
from bns.simulation.jobs import Antenna, Mechanisms, PropagationJob


def job(x, scene="scene", rays=int(1e8)):
    return PropagationJob(scene, None, 1.8e9, (x, 0.0, 30.0), Antenna("tr38901", "V", (0.0, 0.1, 0.0)),
                          Grid((0.0, 0.0), (100.0, 100.0), 10.0, 1.5),
                          Mechanisms(2, True, True, True, False, False, False), rays, (1,),
                          {"variant": "llvm_ad_mono_polarized"})


def folder_with(tmp_path, lines, *, pid=999999):
    f = tmp_path / "run"
    f.mkdir(parents=True)
    (f / "request.json").write_text(json.dumps({"pid": pid, "started_utc": datetime.now(timezone.utc).isoformat(),
                                                "experiment": {"id": "exp-1", "name": "E"}}), encoding="utf-8")
    (f / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def test_a_finished_run_reports_workload_progress_trace_time_and_its_output(tmp_path):
    f = folder_with(tmp_path, ['WORKLOAD {"jobs": 3, "cached": 1, "to_trace": 2}',
                               'PLAN {"batch_size": 1, "expected_seconds": 80.0, "basis": "scene"}',
                               'CURRENT {"scenario": "lte_1800", "station": "S1", "sector": 2}',
                               "PROGRESS 1/2 75.0 s",
                               'ATTEMPT {"batch": 1, "jobs": 1, "attempt": 1, "exit_code": 0, "seconds": 80.0}',
                               'CURRENT {"scenario": "nr_3500", "station": "S1", "sector": 1}',
                               "PROGRESS 2/2 81.0 s",
                               'ATTEMPT {"batch": 2, "jobs": 1, "attempt": 1, "exit_code": 0, "seconds": 86.0}',
                               "EVALUATING", "OUTPUT D:/x/outputs/runs/development/multi_site-x",
                               'DONE {"trace_seconds": 166.0, "wall_seconds": 171.0}'])
    s = wr.state(f)
    assert not s.running and s.execution == "Completed"
    assert (s.workload["cached"], s.done, s.total, s.committed, s.retries) == (1, 2, 2, 2, 0)
    assert s.current is None and s.output.name == "multi_site-x"
    assert s.trace_seconds == 166.0 and s.wall_seconds == 171.0


def test_a_retry_is_counted_and_progress_never_goes_backwards(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "_alive", lambda pid, started: True)
    s = wr.state(folder_with(tmp_path, ['WORKLOAD {"jobs": 3, "cached": 0, "to_trace": 3}',
                                        'PLAN {"batch_size": null, "expected_seconds": 8.0, "basis": "scene"}',
                                        "PROGRESS 1/3 7 s", "PROGRESS 2/3 7 s", "PROGRESS 3/3 7 s",
                                        'ATTEMPT {"batch": 1, "jobs": 3, "attempt": 1, "exit_code": 3221226505, '
                                        '"seconds": 25}',
                                        "PROGRESS 1/3 7 s"]))
    assert s.retries == 1 and s.committed == 0
    assert s.done == 3                       # the highest count reached; the retry is reported, not hidden
    assert s.attempts[-1]["exit_code"] == 3221226505


def test_the_estimate_uses_this_runs_traces_and_adds_worker_start_up(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "_alive", lambda pid, started: True)
    s = wr.state(folder_with(tmp_path, ['WORKLOAD {"jobs": 4, "cached": 0, "to_trace": 4}',
                                        'PLAN {"batch_size": 1, "expected_seconds": 80.0, "basis": "scene"}',
                                        "PROGRESS 1/4 190.0 s",
                                        'ATTEMPT {"batch": 1, "jobs": 1, "attempt": 1, "exit_code": 0, "seconds": 195}']))
    # 3 traces left at this run's own 190 s, and 2 more workers to start (the third is running)
    assert s.remaining_seconds == pytest.approx(3 * 190.0 + 2 * wr.WORKER_START_SECONDS)


def test_before_any_trace_the_estimate_uses_the_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "_alive", lambda pid, started: True)
    s = wr.state(folder_with(tmp_path, ['WORKLOAD {"jobs": 2, "cached": 0, "to_trace": 2}',
                                        'PLAN {"batch_size": null, "expected_seconds": 8.0, "basis": "scene"}']))
    assert s.remaining_seconds == pytest.approx(2 * 8.0)
    assert wr.state(folder_with(tmp_path / "b", ['WORKLOAD {"jobs": 1, "cached": 0, "to_trace": 1}'])) \
        .remaining_seconds is None


def test_a_cancelled_or_failed_run_says_so(tmp_path):
    assert wr.state(folder_with(tmp_path / "a", ["PROGRESS 1/4 7 s", "CANCELLED finished traces stay cached"])
                    ).execution == "Cancelled"
    failed = wr.state(folder_with(tmp_path / "b", ["ERROR the scene is missing"]))
    assert failed.execution == "Failed" and failed.error == "the scene is missing"
    crashed = wr.state(folder_with(tmp_path / "c", ["Traceback (most recent call last):", "  boom"]))
    assert crashed.execution == "Failed" and crashed.error


def test_a_running_run_names_the_job_being_traced_and_the_power_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "_alive", lambda pid, started: True)
    s = wr.state(folder_with(tmp_path, ['POWER {"guid": "a1841308-3541-4fab-bc81-f71556f20b4a", "name": "Power saver", '
                                        '"power_saver": true}',
                                        'WORKLOAD {"jobs": 15, "cached": 0, "to_trace": 15}',
                                        'CURRENT {"scenario": "nr_3500", "station": "S2", "sector": 3}',
                                        "PROGRESS 4/15 7.9 s"]))
    assert s.running and s.execution == "Running" and s.power["power_saver"]
    assert s.current == {"scenario": "nr_3500", "station": "S2", "sector": 3}


@pytest.mark.parametrize(("expected", "size"), [(None, 1), (8.0, None), (29.0, None), (30.0, 1), (190.0, 1)])
def test_slow_traces_get_one_worker_each(expected, size):
    assert wr.batch_size(expected) == size


def test_the_expected_trace_time_prefers_recent_traces_of_the_same_scene(tmp_path):
    cache = PathGainCache(tmp_path / "cache")
    staging = tmp_path / "staging"
    staging.mkdir()
    for n, (scene, seconds) in enumerate([("other", 20.0), ("scene", 80.0), ("scene", 90.0), ("scene", 100.0)]):
        j = job(float(n), scene)
        PathGainCache.write_entry(staging, j.key(), np.zeros((10, 10)), {"job": j.to_dict(), "seconds": seconds})
        cache.publish(staging, [j.key()])
    seconds, basis = wr.expected_trace_seconds(cache, [job(99.0, "scene")])
    assert seconds == pytest.approx(90.0) and basis == "scene"
    seconds, basis = wr.expected_trace_seconds(cache, [job(99.0, "new-scene")])
    assert seconds == pytest.approx(85.0) and basis == "profile"
    assert wr.expected_trace_seconds(cache, [job(99.0, "scene", rays=int(1e9))]) == (None, None)


def test_runs_are_listed_newest_first_and_kept_apart_from_the_run_simulation_page(tmp_path):
    base = wr.folder_root(tmp_path)
    assert base.parent.name == "app_runs" and base.name == "workspace"
    for name in ("20261127T100000000000Z", "20261127T110000000000Z"):
        (base / name).mkdir(parents=True)
        (base / name / "request.json").write_text("{}", encoding="utf-8")
    assert [p.name for p in wr.history(tmp_path)] == ["20261127T110000000000Z", "20261127T100000000000Z"]
