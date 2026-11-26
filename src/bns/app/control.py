"""Start, follow and cancel experiment runs from the application.

A run is the experiment script in its own process (which itself traces in
isolated workers, bns.runtime). Its state lives in a folder under
outputs/app_runs/<id>/ (request.json, log.txt, cancel), so it survives page
reloads and the application restarting. Cancelling creates the cancel file; the
script stops after the current worker and keeps every finished trace cached.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psutil

SCRIPT = "scripts/run_multi_site.py"


@dataclass
class RunState:
    folder: Path
    request: dict
    running: bool
    returncode: int | None
    progress: tuple[int, int] | None        # traced, to trace
    workload: dict | None
    output: Path | None                     # result folder when finished
    error: str | None
    cancelled: bool
    log_tail: list[str]


def build_argv(root: Path, request: dict) -> list[str]:
    argv = [sys.executable, str(Path(root) / SCRIPT), "--area", request["area"], "--variant", request["variant"],
            "--profile", request["profile"], "--mode", request["mode"],
            "--backend", request.get("backend", "cpu")]
    if request.get("buildings"):
        argv += ["--buildings", *request["buildings"]]
    else:
        argv += ["--sites", str(int(request["sites"])), "--min-height", str(float(request["min_height_m"])),
                 "--min-spacing", str(float(request["min_spacing_m"]))]
    return argv


def start(root: Path, request: dict) -> Path:
    root = Path(root)
    folder = root / "outputs" / "app_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    argv = build_argv(root, request) + ["--cancel-file", str(folder / "cancel")]
    log = open(folder / "log.txt", "w", encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags)
    (folder / "request.json").write_text(json.dumps({**request, "argv": argv, "pid": proc.pid,
                                                      "started_utc": datetime.now(timezone.utc).isoformat()},
                                                     indent=2), encoding="utf-8")
    return folder


def cancel(folder: Path) -> None:
    (Path(folder) / "cancel").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")


def _alive(pid: int, started_utc: str) -> bool:
    try:
        p = psutil.Process(pid)
        started = datetime.fromisoformat(started_utc).timestamp()
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE and abs(p.create_time() - started) < 30
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False


def state(folder: Path) -> RunState:
    folder = Path(folder)
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    lines = (folder / "log.txt").read_text(encoding="utf-8", errors="replace").splitlines() \
        if (folder / "log.txt").exists() else []
    progress = workload = output = error = None
    cancelled = False
    for line in lines:
        if line.startswith("PROGRESS "):
            done, total = line.split()[1].split("/")
            progress = (int(done), int(total))
        elif line.startswith("WORKLOAD "):
            workload = json.loads(line[len("WORKLOAD "):])
        elif line.startswith("OUTPUT "):
            output = Path(line[len("OUTPUT "):].strip())
        elif line.startswith("ERROR "):
            error = line[len("ERROR "):]
        elif line.startswith("CANCELLED"):
            cancelled = True
        elif line.startswith("Traceback"):
            error = "the run failed; see the log"
    running = _alive(int(request["pid"]), request["started_utc"])
    returncode = None if running else (0 if output else (2 if cancelled else 1))
    return RunState(folder, request, running, returncode, progress, workload, output, error, cancelled, lines[-40:])


def history(root: Path) -> list[Path]:
    folder = Path(root) / "outputs" / "app_runs"
    return sorted((d for d in folder.iterdir() if (d / "request.json").exists()), reverse=True) \
        if folder.exists() else []
