"""Run propagation jobs: serve what is cached, trace the rest in isolated workers.

Jobs missing from the cache are grouped by scene and frequency (one scene load
and one set of compiled kernels per group) and traced in a fresh worker process
per batch. A batch's maps enter the cache only after its worker exits cleanly;
a crashed worker is retried and its partial output discarded (bns.runtime).
Batches finished before a cancellation or failure stay cached, so running the
same jobs again resumes where it stopped.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from bns import runtime
from bns.simulation.cache import PathGainCache
from bns.simulation.jobs import PropagationJob


def _batches(jobs: list[PropagationJob], batch_size: int | None) -> list[list[PropagationJob]]:
    groups: dict[tuple, list[PropagationJob]] = defaultdict(list)
    for job in jobs:
        groups[(job.scene_dir or "", job.frequency_hz)].append(job)
    batches = []
    for key in sorted(groups):
        group = groups[key]
        step = batch_size or len(group)
        batches += [group[i:i + step] for i in range(0, len(group), step)]
    return batches


def compute(jobs: list[PropagationJob], cache: PathGainCache, *, work_dir: Path,
            on_progress=None, should_cancel=None, max_attempts: int = 8,
            batch_size: int | None = None, threads: int | None = None,
            worker_module: str = "bns.simulation.worker") -> dict[str, np.ndarray]:
    """Path-gain maps for all jobs, keyed by job key.

    on_progress(done, total, info) is called after each traced job; total counts
    only the jobs that were not cached.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    unique = {job.key(): job for job in jobs}
    missing = [job for key, job in unique.items() if not cache.has(key)]
    done = 0

    for number, batch in enumerate(_batches(missing, batch_size), start=1):
        spec = work_dir / f"batch-{number:03d}.json"
        spec.write_text(json.dumps([job.to_dict() for job in batch]), encoding="utf-8")
        staging, finished = work_dir / f"batch-{number:03d}.staging", work_dir / f"batch-{number:03d}"
        argv = [sys.executable, "-m", worker_module, "--jobs", str(spec), "--out", str(staging)]
        if threads:
            argv += ["--threads", str(threads)]
        def on_line(line: str) -> None:
            try:
                event = json.loads(line)
            except ValueError:
                print(line, flush=True)
                return
            # "index" is the job's position in its batch, so a retried batch counts afresh
            if event.get("event") == "job_done" and on_progress is not None:
                on_progress(done + int(event["index"]), len(missing), event)

        try:
            runtime.run_isolated(argv, staging, finished, max_attempts=max_attempts,
                                 env=dict(os.environ), on_line=on_line, should_cancel=should_cancel)
        finally:
            spec.unlink(missing_ok=True)
        cache.publish(finished, [job.key() for job in batch])
        shutil.rmtree(finished, ignore_errors=True)
        done += len(batch)

    return {key: cache.get(key)[0] for key in unique}
