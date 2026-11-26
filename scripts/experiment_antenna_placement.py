"""Controlled experiment: antenna position on the roof (interior point vs roof edge), nothing else changed.

    uv run python scripts/experiment_antenna_placement.py SINGLE_SITE_RUN_DIR [--bands nr_3500 nr_28000] [--inset 1.0]

Takes the site, mast height, sectors, downtilt, profile, backend and radio inputs of a saved
single-site run (whose interior-point maps are cached) and moves ONLY the sector antennas:
each sector stands at the roof edge in the direction it points, --inset metres inside the
footprint, at the same height. Reports coverage, near-site coverage (within 250 m), SINR and
rates for both placements. One controlled case to test the own-roof-shadow explanation; it
is not a choice of placement (decision A4) and nothing is tuned.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from shapely.geometry import LineString

from bns import runtime
from bns.geospatial import pipeline
from bns.simulation import experiment as ex
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache
from bns.simulation.network import network
from bns.simulation.setup import site_jobs

ROOT = Path(__file__).resolve().parents[1]


def edge_point(polygon, x, y, azimuth, inset):
    """Point `inset` m inside the footprint where the ray from (x, y) along `azimuth` leaves it."""
    far = LineString([(x, y), (x + 500 * np.cos(azimuth), y + 500 * np.sin(azimuth))])
    hit = far.intersection(polygon.exterior)
    pts = [hit] if hit.geom_type == "Point" else list(getattr(hit, "geoms", []))
    r = min(np.hypot(p.x - x, p.y - y) for p in pts)
    return x + (r - inset) * np.cos(azimuth), y + (r - inset) * np.sin(azimuth), float(r)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--bands", nargs="+", default=["nr_3500", "nr_28000"])
    parser.add_argument("--inset", type=float, default=1.0)
    args = parser.parse_args()
    started = time.perf_counter()
    m = json.loads((args.run / "manifest.json").read_text(encoding="utf-8"))
    exp = ex.load(ROOT, m["area"]["name"], m["area"]["variant"], m["profile"]["name"], m["mode"], backend="cpu")
    site = m["site"]["candidate"]
    host = next(b for b in pipeline.load_buildings(exp.scene_dir, exp.area) if b.building_id == site["building_id"])
    x0, y0, z = m["site"]["position_m"]
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    placements, jobs = {}, {}
    for k, a in enumerate(exp.antennas):
        xe, ye, r = edge_point(host.polygon, x0, y0, a.orientation_rad[0], args.inset)
        placements[k] = {"azimuth_deg": float(np.degrees(a.orientation_rad[0])), "interior_to_edge_m": r,
                         "edge_position_m": [xe, ye, z]}
    scen = {s["id"]: s for s in exp.scenarios}
    for b in args.bands:
        jobs[b] = [site_jobs(exp.scene_dir, scen[b]["frequency_hz"], placements[k]["edge_position_m"], [a], exp.grid,
                             exp.config, exp.profile.rays_per_site)[0] for k, a in enumerate(exp.antennas)]
    flat = [j for js in jobs.values() for j in js]
    print(f"WORKLOAD {json.dumps(ex.workload(flat, cache, exp.profile.rays_per_site, exp.profile.cell_size_m))}",
          flush=True)
    edge_maps = prop.compute(flat, cache, work_dir=ROOT / "data" / "cache" / "work",
                             on_progress=lambda d, t, i: print(f"PROGRESS {d}/{t} {i.get('seconds')} s", flush=True))

    xs, ys = np.meshgrid(exp.grid.x_centers, exp.grid.y_centers)
    near = exp.outdoor & (np.hypot(xs - x0, ys - y0) <= 250.0)
    results = {}
    for b in args.bands:
        sc = scen[b]
        inputs = ex.radio_inputs(exp, sc)
        interior = np.stack([cache.get(j["key"])[0] for j in m["jobs"] if j["scenario"] == b])
        edge = np.stack([edge_maps[j.key()] for j in jobs[b]])
        out = {}
        for name, stack, positions in (("interior", interior, [(x0, y0, z)] * len(exp.antennas)),
                                       ("edge", edge, [placements[k]["edge_position_m"] for k in placements])):
            loss = np.stack([ex.gas_loss_db(exp, sc, p) for p in positions])
            net = network(stack, np.zeros(len(stack), dtype=int), exp.outdoor, inputs, loss)
            s = net.radio.summary
            out[name] = {"coverage": s["coverage_fraction"],
                         "near_site_uncovered_share": float((near & ~net.radio.covered).sum() / near.sum()),
                         "sinr_median_db": s["sinr_db_median"], "sinr_p5_db": s["sinr_db_p5"],
                         "rate_p5_mbps": s["rate_p5_bps"] / 1e6, "rate_median_mbps": s["rate_median_bps"] / 1e6}
        results[b] = out

    folder = ROOT / "outputs" / "runs" / m["mode"] / (f"antenna_placement-{exp.area.name}-{m['profile']['name']}-"
                                                       f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    folder.mkdir(parents=True)
    record = {"label": exp.label, "kind": "antenna_placement", "source_run": m["run_id"], "site": site,
              "mast_height_m": z - site["roof_height_m"], "roof_area_m2": float(host.polygon.area),
              "roof_bounds_m": [float(v) for v in host.polygon.bounds], "interior_point_m": [x0, y0, z],
              "placements": placements, "inset_m": args.inset, "profile": m["profile"], "backend": "cpu",
              "edge_jobs": {b: [j.key() for j in js] for b, js in jobs.items()}, "results": results,
              "seconds": round(time.perf_counter() - started, 1), "versions": runtime.versions()}
    (folder / "manifest.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    lines = [f"# {exp.label}", "", "## Controlled experiment: antenna position on the roof", "",
             f"Site {site['building_id']} (roof {site['roof_height_m']:g} m, {host.polygon.area:.0f} m², "
             f"{z - site['roof_height_m']:g} m mast, antennas at {z:g} m). Only the sector positions change: "
             f"interior point ({x0:.0f}, {y0:.0f}) vs the roof edge in each sector's direction, {args.inset:g} m inside "
             "(distance interior → edge: " + ", ".join(f"{p['azimuth_deg']:.0f}°: {p['interior_to_edge_m']:.1f} m"
                                                        for p in placements.values()) + "). "
             f"Same sectors, downtilt, profile ({m['profile']['name']}), backend (CPU) and radio inputs.", "",
             "| Band | Placement | Coverage | Uncovered within 250 m | Median SINR | 5th-pct SINR | 5th-pct rate | Median rate |",
             "|---|---|---|---|---|---|---|---|"]
    for b, out in results.items():
        for name, r in out.items():
            lines.append(f"| {scen[b]['label']} | {name} | {100 * r['coverage']:.1f} % | "
                         f"{100 * r['near_site_uncovered_share']:.1f} % | {r['sinr_median_db']:.1f} dB | "
                         f"{r['sinr_p5_db']:.1f} dB | {r['rate_p5_mbps']:.1f} Mbit/s | {r['rate_median_mbps']:.0f} Mbit/s |")
    lines += ["", "One site, one building, placeholder heights around it: evidence for the mechanism, not a general "
                  "result. Placement remains decision A4."]
    (folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OUTPUT {folder}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
