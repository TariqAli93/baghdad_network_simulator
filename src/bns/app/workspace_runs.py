"""Trace the missing path gains of a workspace design in the background (no UI code).

A trace run is scripts/trace_jobs.py in its own process; it traces through
bns.simulation.propagation (isolated workers, retries, the path-gain cache) and nothing else:
the workspace evaluates the radio system itself from the cache once the traces exist. Its state
lives in outputs/app_runs/workspace/<id>/ (request.json, jobs.json, log.txt, cancel), apart from
the Run Simulation page's runs, so it survives page reloads. Cancelling creates the cancel file;
the worker is stopped and every batch finished before stays cached.

Log lines written by the script:
    WORKLOAD {"jobs": n, "cached": c, "to_trace": m}
    CURRENT {"scenario": ..., "station": ..., "sector": ..., "bearing_deg": ...}   job being traced
    PROGRESS done/total seconds s
    RETRY {"from": n}       the batch's worker did not exit cleanly; it is traced again (bns.runtime)
    DONE {"trace_seconds": ..., "wall_seconds": ...}
    CANCELLED ... | ERROR ...
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bns.app.control import _alive          # one definition of "this run's process is still alive"
from bns.simulation.jobs import PropagationJob

SCRIPT = "scripts/trace_jobs.py"


def folder_root(root: Path) -> Path:
    return Path(root) / "outputs" / "app_runs" / "workspace"


def write_jobs(path: Path, jobs: list[PropagationJob], labels: dict[str, dict]) -> None:
    Path(path).write_text(json.dumps({"jobs": [j.to_dict() for j in jobs], "labels": labels}, indent=1),
                          encoding="utf-8")


def read_jobs(path: Path) -> tuple[list[PropagationJob], dict[str, dict]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [PropagationJob.from_dict(d) for d in data["jobs"]], data.get("labels") or {}


@dataclass
class TraceRun:
    folder: Path
    request: dict
    running: bool
    workload: dict | None
    done: int
    total: int
    current: dict | None
    trace_seconds: float | None
    wall_seconds: float | None
    cancelled: bool
    error: str | None
    finished: bool
    log_tail: list[str]
    retries: int = 0

    @property
    def execution(self) -> str:
        if self.running:
            return "Running"
        if self.finished:
            return "Completed"
        return "Cancelled" if self.cancelled else "Failed"

    @property
    def elapsed_seconds(self) -> float:
        if self.wall_seconds is not None:
            return self.wall_seconds
        started = datetime.fromisoformat(self.request["started_utc"])
        return (datetime.now(timezone.utc) - started).total_seconds()


def start(root: Path, jobs: list[PropagationJob], labels: dict[str, dict], request: dict) -> Path:
    """Start tracing `jobs` (cached ones are skipped by the script); returns the run folder."""
    root = Path(root)
    folder = folder_root(root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    write_jobs(folder / "jobs.json", jobs, labels)
    argv = [sys.executable, str(root / SCRIPT), "--jobs", str(folder / "jobs.json"),
            "--cancel-file", str(folder / "cancel")]
    log = open(folder / "log.txt", "w", encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags)
    (folder / "request.json").write_text(json.dumps({**request, "jobs": len(jobs), "argv": argv, "pid": proc.pid,
                                                      "started_utc": datetime.now(timezone.utc).isoformat()},
                                                     indent=2), encoding="utf-8")
    return folder


def cancel(folder: Path) -> None:
    (Path(folder) / "cancel").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def state(folder: Path) -> TraceRun:
    folder = Path(folder)
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    lines = (folder / "log.txt").read_text(encoding="utf-8", errors="replace").splitlines() \
        if (folder / "log.txt").exists() else []
    workload = current = trace_s = wall_s = error = None
    done = total = 0
    cancelled = finished = False
    retries = 0
    for line in lines:
        if line.startswith("WORKLOAD "):
            workload = json.loads(line[len("WORKLOAD "):])
            total = int(workload.get("to_trace", 0))
        elif line.startswith("CURRENT "):
            current = json.loads(line[len("CURRENT "):])
        elif line.startswith("PROGRESS "):
            d, t = line.split()[1].split("/")
            done, total = int(d), int(t)
        elif line.startswith("RETRY"):
            retries += 1
        elif line.startswith("DONE"):
            finished, current = True, None
            payload = json.loads(line[len("DONE"):].strip() or "{}")
            trace_s, wall_s = payload.get("trace_seconds"), payload.get("wall_seconds")
        elif line.startswith("CANCELLED"):
            cancelled, current = True, None
        elif line.startswith("ERROR "):
            error, current = line[len("ERROR "):], None
        elif line.startswith("Traceback"):
            error, current = "the trace run failed; see the log", None
    running = not (finished or cancelled or error) and "pid" in request \
        and _alive(int(request["pid"]), request["started_utc"])
    return TraceRun(folder, request, running, workload, done, total, current if running else None, trace_s, wall_s,
                    cancelled, error, finished, lines[-30:], retries)


def history(root: Path) -> list[Path]:
    base = folder_root(root)
    return sorted((d for d in base.iterdir() if (d / "request.json").exists()), reverse=True) if base.exists() else []


def active(root: Path) -> TraceRun | None:
    """The trace run in progress, if any (one at a time: they share the CPU)."""
    for folder in history(root)[:5]:
        s = state(folder)
        if s.running:
            return s
    return None
