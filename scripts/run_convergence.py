"""How many rays a map needs at 25, 10 and 5 m cells: several sites, bands and scenes.

    uv run python scripts/run_convergence.py --area tahrir_bab_al_sharqi_v2

Each case traces one site at 5 m cells with increasing ray counts and compares it with a
1-billion-ray map of the same case; the 10 m and 25 m results are the same maps averaged
over 2x2 and 5x5 cells. A second 1-billion-ray map with another seed measures the noise
floor. Results: outputs/runs/convergence/<area>/summary.json and summary.md. All maps go
through the production pipeline and stay in the path-gain cache.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from bns.core.units import linear_to_db
from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline, sites
from bns.geospatial.grid import outdoor_mask
from bns.geospatial.study_area import load_study_areas
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache
from bns.simulation.jobs import Antenna
from bns.simulation.setup import SimulationConfig, site_jobs

ROOT = Path(__file__).resolve().parents[1]
RAYS = (10**6, 3 * 10**6, 10**7, 3 * 10**7, 10**8)
REFERENCE = 10**9
BANDS = {"nr_3500": 3.5e9, "nr_28000": 28e9}
CRITERIA = {25: (3.0, 0.02), 10: (2.0, 0.01), 5: (2.0, 0.01)}   # p95 |dB|, missed share


def aggregate(a: np.ndarray, k: int) -> np.ndarray:
    return a.reshape(a.shape[0] // k, k, a.shape[1] // k, k).mean(axis=(1, 3))


def compare(test, ref, mask) -> dict:
    t, r = test[mask], ref[mask]
    reached = r > 0
    both = reached & (t > 0)
    diff = np.abs(linear_to_db(t[both] / r[both]))
    return {"missed_share": float((reached & (t <= 0)).sum() / max(reached.sum(), 1)),
            "median_abs_db": float(np.median(diff)), "p95_abs_db": float(np.percentile(diff, 95)),
            "max_abs_db": float(diff.max())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    args = parser.parse_args()
    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")
    config = SimulationConfig.load(ROOT / "configs" / "simulation.yaml")
    config = replace(config, seeds=(1,))
    data, meta = osm_source.load_snapshot(ROOT / "data" / "raw" / "osm", area.snapshot)

    # Two scene variants: OSM heights with the 9 m placeholder, and a wider height spread.
    models = ht.load_height_models(ROOT / "configs" / "height_models.yaml")
    variants = {"osm": None, "mixed_1_to_8-seed1": models["mixed_1_to_8"]}
    scenes = {}
    for name, model in variants.items():
        folder = ROOT / "data" / "scenes" / area.name / name
        if not (folder / "scene.xml").exists():
            pipeline.build_dataset(area, data, folder, policy, meta["sha256"], height_model=model,
                                   seed=1 if model else None)
        scenes[name] = folder

    buildings = pipeline.load_buildings(scenes["osm"], area)
    inside = [b for b in buildings if area.receiver_box().contains(b.polygon.representative_point())]
    candidates = sites.rooftop_candidates(inside, mast_height_m=3.0, min_height_m=10.0, min_area_m2=0.0,
                                          min_spacing_m=150.0, max_candidates=8,
                                          categories=(ht.OBSERVED, ht.ESTIMATED))
    chosen = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    grid = area.receiver_grid(5.0, height_m=1.5)
    outdoor5 = outdoor_mask(grid, [b.polygon for b in buildings])
    masks = {5: outdoor5, 10: aggregate(outdoor5.astype(float), 2) == 1.0,
             25: aggregate(outdoor5.astype(float), 5) == 1.0}
    antenna = Antenna("iso", config.polarization, (0.0, 0.0, 0.0))

    cases = [(v, c, b) for b in BANDS for c in chosen for v in ["osm"]]
    cases += [("mixed_1_to_8-seed1", chosen[0], b) for b in BANDS]
    jobs, plan = [], []
    for variant, site, band in cases:
        position = (site.x, site.y, site.z)
        per_rays = {}
        for rays in RAYS + (REFERENCE,):
            [job] = site_jobs(scenes[variant], BANDS[band], position, [antenna], grid, config, rays)
            per_rays[rays] = job
            jobs.append(job)
        [floor] = site_jobs(scenes[variant], BANDS[band], position, [antenna], grid,
                            replace(config, seeds=(2,)), REFERENCE)
        jobs.append(floor)
        plan.append((variant, site, band, per_rays, floor))

    start = time.perf_counter()
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    maps = prop.compute(jobs, cache, work_dir=ROOT / "data" / "cache" / "work",
                        on_progress=lambda d, t, i: print(f"traced {d}/{t} ({i.get('seconds')} s)", flush=True))
    wall = time.perf_counter() - start

    results = []
    for variant, site, band, per_rays, floor in plan:
        ref = maps[per_rays[REFERENCE].key()]
        row = {"variant": variant, "site": site.candidate_id, "building": site.building_id,
               "antenna_height_m": site.z, "band": band, "by_rays": {}, "floor": {}}
        for k, cell in ((1, 5), (2, 10), (5, 25)):
            r = aggregate(ref, k) if k > 1 else ref
            f = aggregate(maps[floor.key()], k) if k > 1 else maps[floor.key()]
            row["floor"][cell] = compare(f, r, masks[cell])
            for rays in RAYS:
                t = maps[per_rays[rays].key()]
                row["by_rays"].setdefault(str(rays), {})[cell] = compare(aggregate(t, k) if k > 1 else t,
                                                                          r, masks[cell])
        seconds = {str(rays): cache.get(per_rays[rays].key())[1].get("seconds")
                   for rays in RAYS + (REFERENCE,)}
        row["seconds"] = seconds
        results.append(row)

    def meets(rays, cell):
        p95, missed = CRITERIA[cell]
        return all(r["by_rays"][str(rays)][cell]["p95_abs_db"] <= p95
                   and r["by_rays"][str(rays)][cell]["missed_share"] <= missed for r in results)

    smallest = {cell: next((rays for rays in RAYS if meets(rays, cell)), None) for cell in (25, 10, 5)}
    out = ROOT / "outputs" / "runs" / "convergence" / area.name
    out.mkdir(parents=True, exist_ok=True)
    summary = {"area": area.name, "osm_snapshot_sha256": meta["sha256"], "criteria": CRITERIA,
               "reference_rays": REFERENCE, "smallest_rays_meeting_criteria": smallest,
               "wall_seconds_this_run": round(wall, 1), "cases": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [f"# Ray-count convergence: {area.name}", "",
             "Each value: share of outdoor cells within the given difference from a 1-billion-ray map "
             "of the same case, as the 95th percentile of |difference| in dB, and the share of cells "
             "the reference reaches but the cheaper map misses.", ""]
    for cell in (25, 10, 5):
        p95, missed = CRITERIA[cell]
        lines += [f"## {cell} m cells (criterion: 95 % within {p95} dB, at most {100 * missed:g} % missed)", "",
                  "| Scene | Site (antenna height) | Band | " + " | ".join(f"{r:.0e} rays" for r in RAYS)
                  + " | 2nd 1e9 map (floor) |",
                  "|---|---|---|" + "---|" * (len(RAYS) + 1)]
        for r in results:
            cells = " | ".join(f"{r['by_rays'][str(n)][cell]['p95_abs_db']:.2f} dB, "
                               f"{100 * r['by_rays'][str(n)][cell]['missed_share']:.1f} %" for n in RAYS)
            fl = r["floor"][cell]
            lines.append(f"| {r['variant']} | {r['site']} ({r['antenna_height_m']:.0f} m) | {r['band']} | "
                         f"{cells} | {fl['p95_abs_db']:.2f} dB, {100 * fl['missed_share']:.1f} % |")
        lines += ["", f"Smallest tested ray count meeting the criterion in every case: "
                      f"{'none' if smallest[cell] is None else f'{smallest[cell]:.0e}'}.", ""]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wall time {wall:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
