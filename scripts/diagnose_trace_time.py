"""Time one propagation job repeatedly in one process: compilation vs tracing, core utilisation.

    uv run python scripts/diagnose_trace_time.py [--profile standard] [--antenna iso|tr38901]
        [--height 25] [--frequency 3.5e9] [--repeats 2] [--cold] [--threads N] [--backend cpu|gpu]

Builds the TR 38.901 validation geometry (antenna in open space at the area centre) on the
development dataset and traces it --repeats times in a fresh worker process, printing per call:
wall seconds, process CPU seconds and their ratio (average busy cores). The first call includes
kernel compilation unless the kernel cache already holds the kernels; --cold uses an empty,
temporary kernel cache to measure compilation explicitly. Nothing is written to the path-gain
cache. Used for the slowdown investigation (docs/benchmarks.md §11) and laptop acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHILD = r"""
import json, sys, time
from pathlib import Path
spec = json.loads(sys.argv[1])
from bns import runtime
info = runtime.init(threads=spec["threads"], backend=spec["backend"])
import psutil
from bns.propagation.sionna_engine import Propagation, open_scene, path_gain_map
from bns.simulation.jobs import PropagationJob
job = PropagationJob.from_dict(spec["job"])
proc = psutil.Process()
t = time.perf_counter()
scene = open_scene(Path(job.scene_dir) / "scene.xml", job.frequency_hz, job.antenna.polarization, job.antenna.pattern)
print(json.dumps({"event": "scene", "seconds": round(time.perf_counter() - t, 2), "threads": info.get("threads")}), flush=True)
for k in range(spec["repeats"]):
    c0, t0 = sum(proc.cpu_times()[:2]), time.perf_counter()
    path_gain_map(scene, job.tx_position_m, job.grid, Propagation(**vars(job.mechanisms)), job.rays_per_site,
                  job.seeds, orientation_rad=job.antenna.orientation_rad)
    wall, cpu = time.perf_counter() - t0, sum(proc.cpu_times()[:2]) - c0
    print(json.dumps({"event": "call", "n": k + 1, "wall_s": round(wall, 1), "cpu_s": round(cpu, 1),
                      "busy_cores": round(cpu / wall, 1),
                      "peak_commit_gb": round(proc.memory_info().peak_pagefile / 2**30, 2)}), flush=True)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", default="tahrir_bab_al_sharqi_v2")
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--antenna", choices=("iso", "tr38901"), default="iso")
    parser.add_argument("--height", type=float, default=25.0)
    parser.add_argument("--frequency", type=float, default=3.5e9)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--cold", action="store_true", help="use an empty temporary kernel cache")
    parser.add_argument("--attempts", type=int, default=3, help="retries after a native crash")
    args = parser.parse_args()

    from bns.simulation import experiment as ex
    from bns.simulation.jobs import Antenna
    from bns.simulation.setup import site_jobs

    exp = ex.load(ROOT, args.area, "osm", args.profile, "development", backend="cpu")
    antenna = Antenna(args.antenna, exp.config.polarization, (0.0, 0.17453292519943295, 0.0) if args.antenna != "iso"
                      else (0.0, 0.0, 0.0))
    job = site_jobs(exp.scene_dir, args.frequency, (0.0, 0.0, args.height), [antenna], exp.grid, exp.config,
                    exp.profile.rays_per_site, args.backend)[0]
    spec = {"job": job.to_dict(), "repeats": args.repeats, "threads": args.threads, "backend": args.backend}
    env = dict(os.environ)
    tmp = None
    if args.cold:
        tmp = tempfile.TemporaryDirectory(prefix="bns-kernels-")
        env["DRJIT_CACHE_DIR"] = tmp.name
    print(f"profile {args.profile} ({exp.profile.rays_per_site:.0e} rays, {exp.profile.cell_size_m:g} m), antenna "
          f"{args.antenna} at {args.height:g} m, {args.frequency / 1e9:g} GHz, backend {args.backend}, "
          f"{'cold' if args.cold else 'project'} kernel cache, logical CPUs {os.cpu_count()}", flush=True)
    for attempt in range(1, args.attempts + 1):
        proc = subprocess.run([sys.executable, "-c", CHILD, json.dumps(spec)], env=env, cwd=ROOT,
                              capture_output=True, text=True)
        for line in proc.stdout.splitlines():
            print(line, flush=True)
        crashes = sum("JIT session error" in ln for ln in proc.stderr.splitlines())
        print(json.dumps({"event": "attempt", "n": attempt, "exit_code": proc.returncode,
                          "jit_errors": crashes}), flush=True)
        if proc.returncode == 0:
            break
    if tmp:
        tmp.cleanup()
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
