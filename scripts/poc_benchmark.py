"""Phase 0 benchmark: time and memory of one site on the full 1 km2 scene, CPU only.

    uv run python scripts/poc_benchmark.py                 (all groups)
    uv run python scripts/poc_benchmark.py gate threads    (selected groups)
    uv run python scripts/poc_benchmark.py --mem-cap-gb 10

Run the same command on the target laptop (on AC power) to decide the time
part of the feasibility gate. Every case runs in its own process, inside a
Windows job that caps committed memory, and reports its peak memory.

Groups
    gate       baseline settings, 10 m cells, all five bands
    threads    6 performance cores / 12 performance threads / all 16 threads
    rays       1e7, 1e8, 1e9 rays: time and memory against ray count
    grid       5 m cells (four times the cells of the gate case)
    stability  20 fresh processes in a row
    sustained  90 maps back to back in one process, each timed
    cold       first-ever run with an empty kernel cache (compilation + retries)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from bns import runtime

ROOT = runtime.PROJECT_ROOT
OUT = ROOT / "outputs" / "runs" / "phase0" / "benchmark"
SCENE = ROOT / "data" / "scenes" / "poc_full"
BANDS = {"lte_1800": 1.8e9, "nr_3500": 3.5e9, "c6g_8000": 8.0e9,
         "c6g_15000": 15.0e9, "nr_28000": 28.0e9}
MAST_HEIGHT_M = 3.0                  # provisional, same as scripts/poc_validate.py
BASE = {"cell_m": 10.0, "size_m": 1000.0, "samples": 10**8, "bands": ["nr_3500"],
        "max_depth": 2, "diffraction": True, "threads": None, "cpus": None, "repeats": 2}


def worker(case: dict, out: Path) -> None:
    info = runtime.init(threads=case["threads"], mem_cap_gb=case["mem_cap_gb"], cpus=case["cpus"])
    import numpy as np
    import psutil
    from bns.geospatial.osm_scene import indoor_mask, load_footprints, rooftop_site
    from bns.propagation.sionna_engine import Grid, Propagation, open_scene, path_gain_map

    buildings = load_footprints(SCENE)
    tx, _host = rooftop_site(buildings, MAST_HEIGHT_M, within_m=250.0)
    grid = Grid((0.0, 0.0), (case["size_m"], case["size_m"]), case["cell_m"])
    settings = Propagation(max_depth=case["max_depth"], diffraction=case["diffraction"])
    outdoor = ~indoor_mask(buildings, grid.x_centers, grid.y_centers, grid.cell_size_m)

    start = time.perf_counter()
    scene = open_scene(SCENE / "scene.xml", BANDS[case["bands"][0]])
    load_seconds = time.perf_counter() - start

    runs = []
    for band in case["bands"]:
        scene.frequency = BANDS[band]
        seconds = []
        for _ in range(case["repeats"]):
            # The timed region includes the conversion to NumPy, which is what
            # actually executes the (lazily evaluated) ray tracing.
            res = path_gain_map(scene, tx, grid, settings, case["samples"], [1])
            seconds.append(round(res.seconds_per_seed[0], 3))
        reached = res.mean[outdoor] > 0
        runs.append({"band": band, "first_call_s": seconds[0], "repeat_call_s": seconds[-1],
                     "calls_s": seconds,
                     "outdoor_cells": int(outdoor.sum()),
                     "zero_path_fraction": float(1.0 - reached.mean()),
                     "finite": bool(np.isfinite(res.mean).all())})

    memory = psutil.Process().memory_info()
    result = {"case": case, "runtime": info, "scene_load_s": round(load_seconds, 2), "runs": runs,
              "peak_commit_gb": round(memory.peak_pagefile / 2**30, 3),
              "peak_working_set_gb": round(memory.peak_wset / 2**30, 3),
              "job_peak_commit_gb": round((runtime.peak_job_commit_bytes() or 0) / 2**30, 3)}
    (out / "case.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def run_case(name: str, overrides: dict, mem_cap_gb: float, env: dict | None = None) -> dict:
    case = {**BASE, **overrides, "mem_cap_gb": mem_cap_gb, "name": name}
    final, staging = OUT / name, OUT / f"{name}.staging"
    start = time.perf_counter()
    try:
        attempts = runtime.run_isolated(
            [sys.executable, str(Path(__file__).resolve()), "--worker", json.dumps(case),
             "--out", str(staging)], staging, final, env=env)
    except RuntimeError as error:
        return {"name": name, "case": case, "failed": str(error)}
    result = json.loads((final / "case.json").read_text(encoding="utf-8"))
    result.update({"name": name, "attempts": attempts,
                   "total_wall_s": round(time.perf_counter() - start, 1)})
    return result


def build_groups(mem_cap_gb: float) -> dict:
    p_cores = runtime.performance_cpus(one_thread_per_core=True)
    p_threads = runtime.performance_cpus()
    groups = {
        "gate": [("gate_10m_all_bands", {"bands": list(BANDS)}, None)],
        "threads": [
            (f"threads_{len(p_cores)}_performance_cores", {"cpus": p_cores, "threads": len(p_cores)}, None),
            (f"threads_{len(p_threads)}_performance_threads", {"cpus": p_threads, "threads": len(p_threads)}, None),
            ("threads_all", {}, None),
        ],
        "rays": [(f"rays_1e{e}", {"samples": 10**e}, None) for e in (7, 8, 9)],
        "grid": [("grid_5m", {"cell_m": 5.0}, None)],
        "stability": [(f"stability_{i:02d}", {"samples": 10**7, "repeats": 1}, None)
                      for i in range(1, 21)],
        # Ten minutes or more of back-to-back maps: shows whether the machine
        # slows down under sustained load (cooling, power limits).
        "sustained": [("sustained_90_maps", {"repeats": 90}, None)],
    }
    cold_cache = ROOT / "data" / "cache" / f"drjit_cold_{int(time.time())}"   # created on use
    groups["cold"] = [("cold_empty_kernel_cache", {"repeats": 1},
                       {**os.environ, runtime.CACHE_ENV: str(cold_cache)})]
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("groups", nargs="*", default=[])
    parser.add_argument("--mem-cap-gb", type=float, default=10.0)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        worker(json.loads(args.worker), args.out)
        return 0
    if not (SCENE / "scene.xml").exists():
        print("Scene missing: run scripts/build_poc_scene.py first.")
        return 1

    groups = build_groups(args.mem_cap_gb)
    selected = args.groups or list(groups)
    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary["environment"] = {**runtime.versions(), "cpu_topology": runtime.cpu_topology(),
                              "mem_cap_gb": args.mem_cap_gb}
    for group in selected:
        results = []
        for name, overrides, env in groups[group]:
            if env and runtime.CACHE_ENV in env:
                Path(env[runtime.CACHE_ENV]).mkdir(parents=True, exist_ok=True)
            result = run_case(name, overrides, args.mem_cap_gb, env)
            results.append(result)
            if "failed" in result:
                print(f"{name}: FAILED {result['failed']}")
                continue
            first = result["runs"][0]
            calls = sorted(first["calls_s"])
            if len(calls) >= 10:
                print(f"{name}: {len(calls)} maps, fastest {calls[0]} s, median "
                      f"{calls[len(calls) // 2]} s, slowest {calls[-1]} s, "
                      f"total {round(sum(calls), 1)} s")
            print(f"{name}: first call {first['first_call_s']} s, repeat {first['repeat_call_s']} s, "
                  f"peak commit {result['peak_commit_gb']} GB, peak RAM {result['peak_working_set_gb']} GB, "
                  f"{len(result['attempts'])} attempt(s), exit codes "
                  f"{[a['exit_code'] for a in result['attempts']]}")
        summary[group] = results
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
