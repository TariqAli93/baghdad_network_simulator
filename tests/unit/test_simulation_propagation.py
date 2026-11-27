"""The propagation runner with a stand-in worker: grouping, caching, failure, cancellation."""

import os
import textwrap

import pytest

from bns import runtime
from bns.geospatial.grid import Grid
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache
from bns.simulation.jobs import Antenna, Mechanisms, PropagationJob

FAKE_WORKER = textwrap.dedent("""
    import argparse, json, os, sys
    from pathlib import Path
    import numpy as np
    from bns.simulation.cache import PathGainCache
    from bns.simulation.jobs import PropagationJob
    p = argparse.ArgumentParser(); p.add_argument("--jobs"); p.add_argument("--out")
    p.add_argument("--threads", type=int, default=None)
    a = p.parse_args()
    log = Path(os.environ["FAKE_LOG"])
    jobs = [PropagationJob.from_dict(d) for d in json.loads(Path(a.jobs).read_text())]
    with open(log, "a") as f:
        f.write(f"batch {len(jobs)}\\n")
    crash_flag = Path(os.environ["FAKE_LOG"] + ".crash")
    for i, job in enumerate(jobs):
        PathGainCache.write_entry(Path(a.out), job.key(), np.full(job.grid.shape, job.frequency_hz), {})
        print(json.dumps({"event": "job_done", "index": i + 1, "total": len(jobs), "key": job.key()}),
              flush=True)
        if crash_flag.exists():
            crash_flag.unlink()
            os._exit(3)
    import time
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
""")


def make_job(freq, x=0.0, scene="s1"):
    return PropagationJob(scene, None, freq, (x, 0.0, 30.0), Antenna("iso", "V", (0.0, 0.0, 0.0)),
                          Grid((0.0, 0.0), (20.0, 20.0), 10.0, 1.5),
                          Mechanisms(2, True, True, True, False, False, False), 1000, (1,),
                          {"engine": "test"})


@pytest.fixture
def fake(tmp_path, monkeypatch):
    package = tmp_path / "fakepkg"
    package.mkdir()
    (package / "fake_worker.py").write_text(FAKE_WORKER)
    log = tmp_path / "log.txt"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("PYTHONPATH", str(package) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return {"cache": PathGainCache(tmp_path / "cache"), "work": tmp_path / "work", "log": log}


def run(fake, jobs, **kwargs):
    return prop.compute(jobs, fake["cache"], work_dir=fake["work"], worker_module="fake_worker",
                        **kwargs)


def test_missing_jobs_are_traced_once_and_then_served_from_the_cache(fake):
    jobs = [make_job(1.8e9), make_job(1.8e9, x=50.0), make_job(28e9)]
    progress = []
    maps = run(fake, jobs, on_progress=lambda done, total, info: progress.append((done, total)))
    assert set(maps) == {j.key() for j in jobs}
    assert maps[jobs[2].key()][0, 0] == 28e9
    assert fake["log"].read_text().splitlines() == ["batch 2", "batch 1"]   # grouped by frequency
    assert progress[-1] == (3, 3)
    again = run(fake, jobs + [jobs[0]])
    assert set(again) == set(maps)
    assert len(fake["log"].read_text().splitlines()) == 2                    # nothing re-traced


def test_a_crashing_batch_publishes_nothing_until_a_clean_retry(fake):
    jobs = [make_job(3.5e9), make_job(3.5e9, x=10.0)]
    (fake["log"].parent / "log.txt.crash").write_text("1")
    progress = []
    maps = run(fake, jobs, on_progress=lambda done, total, info: progress.append(done))
    assert set(maps) == {j.key() for j in jobs}
    assert fake["log"].read_text().splitlines() == ["batch 2", "batch 2"]    # retried whole batch
    assert max(progress) == 2 and progress[-1] == 2      # a retry restarts the count, never exceeds it


def test_cancelling_keeps_finished_batches_and_publishes_nothing_else(fake, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "2")                # each batch takes about 2 s
    jobs = [make_job(1.8e9), make_job(28e9)]

    def cancel_in_second_batch():
        return fake["log"].exists() and len(fake["log"].read_text().splitlines()) >= 2

    with pytest.raises(runtime.Cancelled):
        run(fake, jobs, should_cancel=cancel_in_second_batch)
    cached = [fake["cache"].has(j.key()) for j in jobs]
    assert cached == [True, False]                       # first batch kept, second discarded
    assert not any(p.name.endswith(".staging") for p in fake["work"].iterdir())


def test_a_worker_error_is_reported_and_nothing_is_cached(fake, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "")                 # the fake worker cannot be imported
    with pytest.raises(RuntimeError):
        run(fake, [make_job(1.8e9)], max_attempts=2)
    assert not fake["cache"].has(make_job(1.8e9).key())


def test_two_runs_sharing_a_work_folder_do_not_collide(fake, monkeypatch):
    # defect seen in Phase 7: a second run deleted the first run's batch-001.json
    import threading

    monkeypatch.setenv("FAKE_SLEEP", "1")
    errors, maps = [], {}

    def go(name, freq):
        try:
            maps[name] = run(fake, [make_job(freq)])
        except Exception as exc:                         # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(n, f)) for n, f in (("a", 1.8e9), ("b", 28e9))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [] and set(maps) == {"a", "b"}
    assert list(fake["work"].iterdir()) == []            # each run cleans up its own folder


def test_one_worker_per_trace_commits_each_trace_and_a_cancel_keeps_the_committed_ones(fake, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "1")
    jobs = [make_job(3.5e9, x=float(x)) for x in range(3)]          # one band: one batch unless batch_size=1
    attempts = []

    def cancel_after_two_commits():
        return sum(a["exit_code"] == 0 for a in attempts) >= 2

    with pytest.raises(runtime.Cancelled):
        run(fake, jobs, batch_size=1, should_cancel=cancel_after_two_commits, on_attempt=attempts.append)
    assert [fake["cache"].has(j.key()) for j in jobs] == [True, True, False]
    assert [(a["batch"], a["jobs"], a["exit_code"]) for a in attempts] == [(1, 1, 0), (2, 1, 0)]
    before = len(fake["log"].read_text().splitlines())
    run(fake, jobs, batch_size=1)                                   # resume: only the missing trace
    assert fake["log"].read_text().splitlines()[before:] == ["batch 1"]
    assert all(fake["cache"].has(j.key()) for j in jobs)


def test_a_failed_attempt_is_reported_and_its_output_never_cached(fake):
    jobs = [make_job(8e9), make_job(8e9, x=10.0)]
    (fake["log"].parent / "log.txt.crash").write_text("1")          # the first attempt dies after one trace
    attempts = []
    run(fake, jobs, on_attempt=attempts.append)
    assert [a["exit_code"] for a in attempts] == [3, 0]
    assert all(fake["cache"].has(j.key()) for j in jobs)            # from the clean retry only
