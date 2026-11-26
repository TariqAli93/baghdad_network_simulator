"""Engine worker: traces a batch of propagation jobs and stages their path-gain maps.

Started by bns.simulation.propagation in a fresh process through
bns.runtime.run_isolated; never imported by the application itself. Progress is
reported as one JSON object per line on standard output.

    python -m bns.simulation.worker --jobs batch.json --out STAGING_DIR
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=None)
    args = parser.parse_args()

    from bns import runtime

    info = runtime.init(threads=args.threads)
    import psutil

    from bns.propagation.engine_settings import engine_fingerprint
    from bns.propagation.sionna_engine import Propagation, open_scene, path_gain_map
    from bns.simulation.cache import PathGainCache
    from bns.simulation.jobs import PropagationJob

    jobs = [PropagationJob.from_dict(d) for d in json.loads(args.jobs.read_text(encoding="utf-8"))]
    engine = engine_fingerprint()
    scenes = {}
    for index, job in enumerate(jobs):
        if job.engine != engine:
            raise RuntimeError(f"Job was prepared for engine {job.engine}, this worker runs {engine}.")
        scene_key = (job.scene_dir, job.frequency_hz, job.antenna.pattern, job.antenna.polarization)
        if scene_key not in scenes:
            scenes.clear()                      # keep one scene in memory at a time
            xml = None if job.scene_dir is None else Path(job.scene_dir) / "scene.xml"
            scenes[scene_key] = open_scene(xml, job.frequency_hz, job.antenna.polarization,
                                           job.antenna.pattern)
        start = time.perf_counter()
        result = path_gain_map(scenes[scene_key], job.tx_position_m, job.grid,
                               Propagation(**vars(job.mechanisms)), job.rays_per_site, job.seeds,
                               orientation_rad=job.antenna.orientation_rad)
        seconds = time.perf_counter() - start
        memory = psutil.Process().memory_info()
        PathGainCache.write_entry(args.out, job.key(), result.mean, {
            "job": job.to_dict(), "seconds": round(seconds, 3),
            "seconds_per_seed": [round(s, 3) for s in result.seconds_per_seed],
            "worker_peak_commit_gb": round(memory.peak_pagefile / 2**30, 3),
            "worker_peak_working_set_gb": round(memory.peak_wset / 2**30, 3),
            "runtime": info, "versions": runtime.versions(),
        })
        print(json.dumps({"event": "job_done", "index": index + 1, "total": len(jobs),
                          "key": job.key(), "seconds": round(seconds, 3)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
