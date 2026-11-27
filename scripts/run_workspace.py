"""Run a workspace experiment: trace what is missing, evaluate every carrier, write the run.

    uv run python scripts/run_workspace.py --request RUN.json [--cancel-file FILE]

RUN.json holds {"experiment": <bns.app.experiments configuration>, "carriers": [ids], "coverage_target": t}
(written by bns.app.workspace_runs). Path gains are traced exactly as every experiment script traces
them (bns.simulation.propagation: isolated workers, retries, publish on a clean exit); slow traces get
one worker each so that a crash or a cancellation loses at most one trace. The radio system is then
evaluated from the cache (bns.app.workspace) and the run is written in the multi-site format
(bns.app.run_record). Progress lines are described in bns.app.workspace_runs.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import psutil

from bns import runtime
from bns.app import experiments as xp
from bns.app import run_record
from bns.app import workspace as ws
from bns.app import workspace_runs as wr
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache

ROOT = Path(__file__).resolve().parents[1]


def emit(head: str, payload=None) -> None:
    text = head if payload is None else f"{head} {payload if isinstance(payload, str) else json.dumps(payload)}"
    print(text, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--cancel-file", type=Path, help="stop cleanly when this file appears")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        experiment = xp.Experiment.from_dict(request["experiment"])
        ctx = xp.context(ROOT, experiment)
        stations, radio = xp.stations(experiment), xp.radio(experiment)
        # the network: every selected carrier transmits; results for the requested ones (that a station is on),
        # tracing also the carriers that overlap them (their interference is part of the result)
        network_carriers = [c for c in experiment.carriers if c.get("selected", True)
                            or c["id"] in set(request["carriers"])]
        carriers = [c for c in network_carriers if c["id"] in set(request["carriers"]) and ws.transmitting(stations, c["id"])]
        if not carriers or not any(s.enabled for s in stations):
            raise ValueError("nothing to simulate: no carrier or no transmitting station")
        traced = [c for c in network_carriers
                  if any(c["id"] == r["id"] or ws.overlap(r, c) > 0 for r in carriers)]
        target = float(request.get("coverage_target") or ctx.exp.system.require("coverage_target", mode="development"))
    except Exception as exc:                        # unreadable request, missing dataset, invalid values
        emit("ERROR", str(exc))
        return 1
    emit("POWER", runtime.power_plan() or {})
    design = ws.jobs(ctx, stations, traced)
    labels = ws.job_labels(design, stations)
    all_jobs = [sj.job for js in design.values() for sj in js]
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    unique = {j.key(): j for j in all_jobs}
    missing = [j for k, j in unique.items() if not cache.has(k)]
    workload = {"jobs": len(unique), "cached": len(unique) - len(missing), "to_trace": len(missing)}
    emit("WORKLOAD", workload)
    expected, basis = wr.expected_trace_seconds(cache, missing)
    size = wr.batch_size(expected) if missing else None
    emit("PLAN", {"batch_size": size, "expected_seconds": expected, "basis": basis})
    order = [j for batch in prop._batches(missing, size) for j in batch]     # the order compute() traces in

    def current(n: int) -> None:
        if n < len(order):
            emit("CURRENT", labels.get(order[n].key(), {}))

    def progress(done: int, total: int, info: dict) -> None:
        emit("PROGRESS", f"{done}/{total} {info.get('seconds')} s")
        current(done)

    current(0)
    cancel = (lambda: args.cancel_file.exists()) if args.cancel_file else None
    trace_start = time.perf_counter()
    try:
        prop.compute(all_jobs, cache, work_dir=ROOT / "data" / "cache" / "work", should_cancel=cancel,
                     on_progress=progress, on_attempt=lambda r: emit("ATTEMPT", r), batch_size=size)
    except runtime.Cancelled:
        emit("CANCELLED", "committed traces stay cached; run again to resume.")
        return 2
    except Exception as exc:                        # a worker that never exits cleanly, a missing engine
        emit("ERROR", str(exc))
        return 1
    trace_seconds = time.perf_counter() - trace_start

    emit("EVALUATING")
    memo: dict = {}

    def load(key):
        if key not in memo:
            memo[key] = cache.get(key)
        return memo[key]

    try:
        evaluations = {c["id"]: ws.evaluate(ctx, stations, c, radio, load, network_carriers) for c in carriers}
        more = {c["id"]: run_record.extras(ctx, stations, c, radio, load, target, network_carriers) for c in carriers}
        on = [s for s in stations if s.enabled]
        job_records = []
        for c in traced:                            # every traced job, interfering carriers included
            for sj in design[c["id"]]:
                meta = load(sj.job.key())[1]
                job_records.append({"scenario": c["id"], "site": on[sj.station].station_id, "key": sj.job.key(),
                                    "sector_orientation_rad": sj.job.antenna.orientation_rad,
                                    "trace_seconds": meta.get("seconds"),
                                    "worker_peak_commit_gb": meta.get("worker_peak_commit_gb"),
                                    "power_plan": (meta.get("runtime") or {}).get("power_plan")})
        memory = psutil.Process().memory_info()
        timing = {"trace_wall_seconds": round(trace_seconds, 1),
                  "total_wall_seconds": round(time.perf_counter() - started, 1), "batch_size": size,
                  "script_peak_commit_gb": round(getattr(memory, "peak_pagefile", 0) / 2**30, 3)}
        out = run_record.write(ROOT, ctx, experiment.to_dict(), stations, carriers, radio, evaluations, more,
                               network_carriers=network_carriers,
                               job_records=job_records, workload=workload, target=target, timing=timing,
                               versions=runtime.versions())
    except Exception as exc:                        # noqa: BLE001 - reported; the traces stay cached
        emit("ERROR", f"evaluation or writing failed: {exc}")
        return 1
    emit("OUTPUT", str(out))
    emit("DONE", {"trace_seconds": round(trace_seconds, 1), "wall_seconds": round(time.perf_counter() - started, 1)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
