"""Trace a list of propagation jobs into the path-gain cache (the workspace's run action).

    uv run python scripts/trace_jobs.py --jobs JOBS.json [--cancel-file FILE]

JOBS.json holds {"jobs": [PropagationJob.to_dict(), ...], "labels": {key: {...}}} (written by
bns.app.workspace_runs). Cached jobs are skipped; the rest are traced exactly as every experiment
script traces them (bns.simulation.propagation: isolated workers, retries, publish on a clean
exit). Nothing radio-related happens here: the workspace evaluates the radio system from the cache.
Progress lines are described in bns.app.workspace_runs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from bns import runtime
from bns.app.workspace_runs import read_jobs
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--cancel-file", type=Path, help="stop cleanly when this file appears")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        jobs, labels = read_jobs(args.jobs)
    except Exception as exc:                        # unreadable job file
        print(f"ERROR {exc}", flush=True)
        return 1
    missing_scenes = sorted({j.scene_dir for j in jobs if j.scene_dir and not (Path(j.scene_dir) / "scene.xml").exists()})
    if missing_scenes:
        print(f"ERROR no scene at {', '.join(missing_scenes)}", flush=True)
        return 1
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    unique = {j.key(): j for j in jobs}
    missing = [j for k, j in unique.items() if not cache.has(k)]
    print(f"WORKLOAD {json.dumps({'jobs': len(unique), 'cached': len(unique) - len(missing), 'to_trace': len(missing)})}",
          flush=True)
    # the order propagation.compute traces them in (one batch per scene and frequency), to name the current job
    order = [j for batch in prop._batches(missing, None) for j in batch]

    def current(n: int) -> None:
        if n < len(order):
            print(f"CURRENT {json.dumps(labels.get(order[n].key(), {}))}", flush=True)

    last = {"done": 0}

    def progress(done: int, total: int, info: dict) -> None:
        # a batch whose worker did not exit cleanly is traced again (bns.runtime.run_isolated): its count restarts
        if done <= last["done"]:
            print(f"RETRY {json.dumps({'from': done - 1})}", flush=True)
        last["done"] = done
        print(f"PROGRESS {done}/{total} {info.get('seconds')} s", flush=True)
        current(done)

    current(0)
    cancel = (lambda: args.cancel_file.exists()) if args.cancel_file else None
    trace_start = time.perf_counter()
    try:
        prop.compute(jobs, cache, work_dir=ROOT / "data" / "cache" / "work", should_cancel=cancel, on_progress=progress)
    except runtime.Cancelled:
        print("CANCELLED finished batches stay cached; run again to resume.", flush=True)
        return 2
    except Exception as exc:                        # a worker that never exits cleanly, a missing engine
        print(f"ERROR {exc}", flush=True)
        return 1
    print(f"DONE {json.dumps({'trace_seconds': round(time.perf_counter() - trace_start, 1), 'wall_seconds': round(time.perf_counter() - started, 1)})}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
