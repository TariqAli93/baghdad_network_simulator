"""Run a workspace experiment in the background and follow it (no UI code).

A run is scripts/run_workspace.py in its own process. It traces the missing path gains through
bns.simulation.propagation (isolated workers, retries, the path-gain cache), evaluates the radio
system for every requested carrier and writes a run in the existing multi-site format
(bns.app.run_record), so it appears in the history and the reports. Its state lives in
outputs/app_runs/workspace/<id>/ (request.json, log.txt, cancel), apart from the Run Simulation
page's runs, so it survives page reloads. Cancelling creates the cancel file: the worker in
progress is stopped and its traces are discarded; every committed trace stays in the cache and a new
run reuses it.

Commit granularity. A worker's traces enter the cache only when that worker exits cleanly
(bns.runtime.run_isolated). Slow traces (expected ≥ 30 s) therefore get one worker each, so a crash at
exit or a cancellation loses at most one trace; worker start-up costs 2-5 s (docs/benchmarks.md, §12),
1-7 % of a standard trace. Fast traces keep one worker per band (start-up would be 11-70 % of them).

Log lines written by the script:
    POWER {...}             active Windows power plan (runtime.power_plan)
    WORKLOAD {"jobs": n, "cached": c, "to_trace": m}
    PLAN {"batch_size": 1|null, "expected_seconds": s|null, "basis": "scene"|"profile"|null}
    CURRENT {"scenario": ..., "station": ..., "sector": ..., "bearing_deg": ...}
    PROGRESS done/total seconds s
    ATTEMPT {"batch": b, "jobs": n, "attempt": k, "exit_code": c, "seconds": s}   (exit 0 = committed)
    EVALUATING | OUTPUT <run folder> | DONE {...} | CANCELLED ... | ERROR ...
"""

from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from bns.app.control import _alive          # one definition of "this run's process is still alive"

SCRIPT = "scripts/run_workspace.py"
SLOW_TRACE_SECONDS = 30.0         # at or above: one worker per trace
WORKER_START_SECONDS = 5.0        # measured 2.2-5.1 s per worker (docs/benchmarks.md, §12)
RECENT = 12


def folder_root(root: Path) -> Path:
    return Path(root) / "outputs" / "app_runs" / "workspace"


def batch_size(expected_seconds: float | None) -> int | None:
    """One trace per worker when traces are slow or their time is unknown; one worker per band otherwise."""
    return 1 if expected_seconds is None or expected_seconds >= SLOW_TRACE_SECONDS else None


def expected_trace_seconds(cache, jobs) -> tuple[float | None, str | None]:
    """Median of the most recent traces with the same ray count, cell size and engine variant, from the
    same scene if any (basis "scene"), else from any scene (basis "profile"); (None, None) if none."""
    if not jobs:
        return None, None
    j = jobs[0]
    rays, cell, variant = int(j.rays_per_site), float(j.grid.cell_size_m), j.engine.get("variant")
    same_scene, same_profile = [], []
    for meta in cache.root.glob("*/*.json"):
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            job = m["job"]
            if (int(job["rays_per_site"]) != rays or float(job["grid"]["cell_size_m"]) != cell
                    or job["engine"].get("variant") != variant):
                continue
            entry = (meta.stat().st_mtime, float(m["seconds"]))
        except (KeyError, ValueError, TypeError, OSError):
            continue
        same_profile.append(entry)
        if job.get("scene_fingerprint", job.get("scene")) == j.scene_fingerprint:
            same_scene.append(entry)
    for entries, basis in ((same_scene, "scene"), (same_profile, "profile")):
        if entries:
            recent = [s for _, s in sorted(entries, reverse=True)[:RECENT]]
            return float(statistics.median(recent)), basis
    return None, None


@dataclass
class RunState:
    folder: Path
    request: dict
    running: bool
    workload: dict | None
    plan: dict | None
    power: dict | None
    done: int
    total: int
    current: dict | None
    trace_times: list[float]
    attempts: list[dict]
    evaluating: bool
    output: Path | None
    trace_seconds: float | None
    wall_seconds: float | None
    cancelled: bool
    error: str | None
    finished: bool
    log_tail: list[str] = field(default_factory=list)

    @property
    def execution(self) -> str:
        if self.running:
            return "Running"
        if self.finished and self.output:
            return "Completed"
        return "Cancelled" if self.cancelled else "Failed"

    @property
    def committed(self) -> int:
        """Traces committed to the cache in this run (by clean worker exits)."""
        return sum(int(a.get("jobs", 0)) for a in self.attempts if a.get("exit_code") == 0)

    @property
    def retries(self) -> int:
        return sum(1 for a in self.attempts if a.get("exit_code") not in (0, None))

    @property
    def elapsed_seconds(self) -> float:
        if self.wall_seconds is not None:
            return self.wall_seconds
        started = datetime.fromisoformat(self.request["started_utc"])
        return (datetime.now(timezone.utc) - started).total_seconds()

    @property
    def remaining_seconds(self) -> float | None:
        """Estimate, not a promise: traces still to compute at this run's own mean trace time (else the
        plan's expected time), plus start-up of the workers still to launch. Retries are not included."""
        per = statistics.fmean(self.trace_times) if self.trace_times else (self.plan or {}).get("expected_seconds")
        if per is None or not self.running:
            return None if per is None else 0.0
        left = max(self.total - self.done, 0)
        size = (self.plan or {}).get("batch_size")
        open_batches = math.ceil(max(self.total - self.committed, 0) / size) if size else 0
        to_start = max(open_batches - (1 if self.done > self.committed or self.trace_times else 0), 0) if size else 0
        return left * per + to_start * WORKER_START_SECONDS


def start(root: Path, experiment: dict, carrier_ids: list[str], *, target: float | None = None) -> Path:
    """Start a run of `experiment` (a bns.app.experiments configuration) for the given carriers."""
    root = Path(root)
    folder = folder_root(root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    request = {"experiment": experiment, "carriers": list(carrier_ids), "coverage_target": target}
    (folder / "run.json").write_text(json.dumps(request, indent=1, ensure_ascii=False), encoding="utf-8")
    argv = [sys.executable, str(root / SCRIPT), "--request", str(folder / "run.json"),
            "--cancel-file", str(folder / "cancel")]
    log = open(folder / "log.txt", "w", encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags)
    (folder / "request.json").write_text(json.dumps({
        "experiment": {"id": experiment.get("experiment_id"), "name": experiment.get("name")},
        "carriers": list(carrier_ids), "argv": argv, "pid": proc.pid,
        "started_utc": datetime.now(timezone.utc).isoformat()}, indent=2, ensure_ascii=False), encoding="utf-8")
    return folder


def cancel(folder: Path) -> None:
    (Path(folder) / "cancel").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def state(folder: Path) -> RunState:
    folder = Path(folder)
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    lines = (folder / "log.txt").read_text(encoding="utf-8", errors="replace").splitlines() \
        if (folder / "log.txt").exists() else []
    workload = plan = power = current = output = trace_s = wall_s = error = None
    done = total = 0
    times, attempts = [], []
    cancelled = finished = evaluating = False
    for line in lines:
        head, _, rest = line.partition(" ")
        try:
            if head == "WORKLOAD":
                workload = json.loads(rest)
                total = int(workload.get("to_trace", 0))
            elif head == "PLAN":
                plan = json.loads(rest)
            elif head == "POWER":
                power = json.loads(rest)
            elif head == "CURRENT":
                current = json.loads(rest)
            elif head == "PROGRESS":
                d, t = rest.split()[0].split("/")
                done, total = max(done, int(d)), int(t)          # a retried batch counts again from its start
                seconds = rest.split()[1] if len(rest.split()) > 1 else None
                if seconds not in (None, "None"):
                    times.append(float(seconds))
            elif head == "ATTEMPT":
                attempts.append(json.loads(rest))
            elif head == "EVALUATING":
                evaluating, current = True, None
            elif head == "OUTPUT":
                output = Path(rest.strip())
            elif head == "DONE":
                finished, current = True, None
                payload = json.loads(rest or "{}")
                trace_s, wall_s = payload.get("trace_seconds"), payload.get("wall_seconds")
            elif head == "CANCELLED":
                cancelled, current = True, None
            elif head == "ERROR":
                error, current = rest, None
            elif head == "Traceback":
                error, current = "the run failed; see the log", None
        except (ValueError, IndexError):
            continue
    running = not (finished or cancelled or error) and "pid" in request \
        and _alive(int(request["pid"]), request["started_utc"])
    return RunState(folder, request, running, workload, plan, power, done, total, current if running else None,
                    times, attempts, evaluating and running, output, trace_s, wall_s, cancelled, error, finished,
                    lines[-30:])


def history(root: Path) -> list[Path]:
    base = folder_root(root)
    return sorted((d for d in base.iterdir() if (d / "request.json").exists()), reverse=True) if base.exists() else []


def active(root: Path) -> RunState | None:
    """The run in progress, if any (one at a time: they share the CPU)."""
    for folder in history(root)[:5]:
        try:
            s = state(folder)
        except (OSError, ValueError, KeyError):
            continue
        if s.running:
            return s
    return None
