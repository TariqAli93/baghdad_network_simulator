"""Workspace trace runs: the job file a run traces, and its log read back as progress and outcome."""

import json
from datetime import datetime, timezone

from bns.app import workspace_runs as wr
from bns.geospatial.grid import Grid
from bns.simulation.jobs import Antenna, Mechanisms, PropagationJob


def job(x):
    return PropagationJob("scene", None, 1.8e9, (x, 0.0, 30.0), Antenna("tr38901", "V", (0.0, 0.1, 0.0)),
                          Grid((0.0, 0.0), (100.0, 100.0), 10.0, 1.5),
                          Mechanisms(2, True, True, True, False, False, False), int(1e8), (1,),
                          {"variant": "llvm_ad_mono_polarized"})


def folder_with(tmp_path, lines, *, pid=999999):
    f = tmp_path / "run"
    f.mkdir(parents=True)
    (f / "request.json").write_text(json.dumps({"pid": pid, "started_utc": datetime.now(timezone.utc).isoformat(),
                                                "scope": "all", "jobs": 3}), encoding="utf-8")
    (f / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def test_the_job_file_round_trips_every_job_and_its_label(tmp_path):
    jobs = [job(0.0), job(5.0)]
    labels = {j.key(): {"scenario": "lte_1800", "station": "S1", "sector": n + 1} for n, j in enumerate(jobs)}
    path = tmp_path / "jobs.json"
    wr.write_jobs(path, jobs, labels)
    back, back_labels = wr.read_jobs(path)
    assert [j.key() for j in back] == [j.key() for j in jobs]
    assert back_labels == labels


def test_a_finished_run_reports_workload_progress_and_trace_time(tmp_path):
    f = folder_with(tmp_path, ['WORKLOAD {"jobs": 3, "cached": 1, "to_trace": 2}',
                               'CURRENT {"scenario": "lte_1800", "station": "S1", "sector": 2}',
                               "PROGRESS 1/2 7.5 s",
                               'CURRENT {"scenario": "nr_3500", "station": "S1", "sector": 1}',
                               "PROGRESS 2/2 8.0 s",
                               'DONE {"trace_seconds": 15.5, "wall_seconds": 31.0}'])
    s = wr.state(f)
    assert not s.running and s.execution == "Completed"
    assert (s.workload["cached"], s.done, s.total) == (1, 2, 2)
    assert s.current is None                     # nothing is being traced once the run is done
    assert s.trace_seconds == 15.5 and s.wall_seconds == 31.0


def test_a_retried_batch_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "_alive", lambda pid, started: True)
    s = wr.state(folder_with(tmp_path, ["PROGRESS 1/3 7 s", "PROGRESS 2/3 7 s", "PROGRESS 3/3 7 s",
                                        'RETRY {"from": 0}', "PROGRESS 1/3 7 s"]))
    assert s.retries == 1 and (s.done, s.total) == (1, 3)


def test_a_cancelled_or_failed_run_says_so(tmp_path):
    assert wr.state(folder_with(tmp_path / "a", ["PROGRESS 1/4 7 s", "CANCELLED finished traces stay cached"])
                    ).execution == "Cancelled"
    failed = wr.state(folder_with(tmp_path / "b", ["ERROR the scene is missing"]))
    assert failed.execution == "Failed" and failed.error == "the scene is missing"
    crashed = wr.state(folder_with(tmp_path / "c", ["Traceback (most recent call last):", "  boom"]))
    assert crashed.execution == "Failed" and crashed.error


def test_a_running_run_names_the_job_being_traced(tmp_path, monkeypatch):
    monkeypatch.setattr(wr, "_alive", lambda pid, started: True)
    s = wr.state(folder_with(tmp_path, ['WORKLOAD {"jobs": 15, "cached": 0, "to_trace": 15}',
                                        'CURRENT {"scenario": "nr_3500", "station": "S2", "sector": 3}',
                                        "PROGRESS 4/15 7.9 s"]))
    assert s.running and s.execution == "Running"
    assert s.current == {"scenario": "nr_3500", "station": "S2", "sector": 3}
    assert (s.done, s.total) == (4, 15)


def test_runs_are_listed_newest_first_and_kept_apart_from_the_run_simulation_page(tmp_path):
    base = wr.folder_root(tmp_path)
    assert base.parent.name == "app_runs" and base.name == "workspace"
    for name in ("20261127T100000000000Z", "20261127T110000000000Z"):
        (base / name).mkdir(parents=True)
        (base / name / "request.json").write_text("{}", encoding="utf-8")
    assert [p.name for p in wr.history(tmp_path)] == ["20261127T110000000000Z", "20261127T100000000000Z"]
