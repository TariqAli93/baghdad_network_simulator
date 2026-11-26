"""Why are cells near a site uncovered? Pattern, own-roof shadow or both (no new traces).

    uv run python scripts/diagnose_near_site.py RUN_DIR [--scenario nr_28000] [--radius 250]

For every outdoor cell within --radius of the site of a saved single-site run, the
traced best-sector path gain (from the cache) is compared with two references:
  free space + pattern  Friis over the 3-D distance plus the TR 38.901 element gain of
                        the best sector towards the cell (closed form, no ray tracing);
  own-roof shadow       whether the straight line from the antenna to the cell passes
                        below the host roof's edge, i.e. the host building itself blocks
                        the line of sight (geometry of the footprint and the mast height).
A cell whose traced gain is close to "free space + pattern" is explained by the
pattern; a cell far below it, and behind the roof edge, is shadowed by the host roof.
Nothing is tuned. Writes near_site_<scenario>.md and .png into RUN_DIR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point

from bns.core.units import free_space_path_gain, linear_to_db
from bns.geospatial import pipeline
from bns.geospatial.grid import Grid
from bns.geospatial.study_area import load_study_areas
from bns.simulation.cache import PathGainCache
from bns.validation.analytic import tr38901_element_gain_dbi

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--scenario", default="nr_28000")
    parser.add_argument("--radius", type=float, default=250.0)
    args = parser.parse_args()

    manifest = json.loads((args.run / "manifest.json").read_text(encoding="utf-8"))
    from bns.analysis import classification
    run_label = classification.from_manifest(manifest).label   # scientific class of the source run
    arrays = np.load(args.run / "bands.npz")
    g = manifest["grid"]
    grid = Grid(tuple(g["center_xy"]), tuple(g["size_xy"]), g["cell_size_m"], g["height_m"])
    site = manifest["site"]["candidate"]
    tx = np.array(manifest["site"]["position_m"], dtype=float)
    sc = next(s for s in manifest["scenarios"] if s["id"] == args.scenario)
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    jobs = [j for j in manifest["jobs"] if j["scenario"] == args.scenario]
    stack = np.stack([cache.get(j["key"])[0] for j in jobs])
    orientations = [tuple(j["sector_orientation_rad"]) for j in jobs]
    covered = arrays[f"{args.scenario}_covered"]
    outdoor = arrays["outdoor"]

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[manifest["area"]["name"]]
    host = next(b for b in pipeline.load_buildings(ROOT / "data" / "scenes" / area.name / manifest["area"]["variant"], area)
                if b.building_id == site["building_id"])
    roof = host.height.height_m
    edge = host.polygon.exterior

    xs, ys = np.meshgrid(grid.x_centers, grid.y_centers)
    horizontal = np.hypot(xs - tx[0], ys - tx[1])
    rows = []
    for iy, ix in zip(*np.nonzero(outdoor & (horizontal <= args.radius)), strict=True):
        rx = np.array([xs[iy, ix], ys[iy, ix], grid.height_m])
        d = rx - tx
        dist = float(np.linalg.norm(d))
        gains = [tr38901_element_gain_dbi(d, o) for o in orientations]
        traced = stack[:, iy, ix]
        best = int(np.argmax(traced))
        reference = linear_to_db(free_space_path_gain(dist, sc["frequency_hz"])) + max(gains)
        # where does the ray leave the host footprint, and how high is it there?
        crossing = LineString([(tx[0], tx[1]), (rx[0], rx[1])]).intersection(edge)
        pts = [crossing] if isinstance(crossing, Point) else list(getattr(crossing, "geoms", []))
        if pts:
            run = max(np.hypot(p.x - tx[0], p.y - tx[1]) for p in pts)
            z_at_edge = tx[2] + (rx[2] - tx[2]) * run / float(np.hypot(*d[:2]))
            shadowed = z_at_edge < roof
        else:
            run, shadowed = float("nan"), False
        rows.append({"horizontal_m": float(horizontal[iy, ix]),
                     "depression_deg": float(np.degrees(np.arctan2(tx[2] - rx[2], np.hypot(*d[:2])))),
                     "best_pattern_gain_dbi": max(gains), "traced_db": float(linear_to_db(traced[best])),
                     "reference_db": float(reference), "shadowed_by_own_roof": bool(shadowed),
                     "edge_distance_m": run, "covered": bool(covered[iy, ix])})

    def share(sel, key):
        v = [r[key] for r in sel]
        return f"{100 * np.mean(v):.0f} %" if v else "—"

    def med(sel, key):
        v = [r[key] for r in sel if np.isfinite(r[key])]
        return f"{np.median(v):+.1f}" if v else "—"

    groups = {"all near cells": rows,
              "uncovered": [r for r in rows if not r["covered"]],
              "covered": [r for r in rows if r["covered"]],
              "behind own roof edge": [r for r in rows if r["shadowed_by_own_roof"]],
              "line of sight clears own roof": [r for r in rows if not r["shadowed_by_own_roof"]]}
    for r in rows:
        r["excess_db"] = r["reference_db"] - r["traced_db"]
    lines = [f"# {run_label}", "",
             f"## Near-site diagnosis, {sc['label']} ({sc['frequency_hz'] / 1e9:g} GHz), run {manifest['run_id']}", "",
             f"Site on {site['building_id']}: roof {roof:g} m, antenna {tx[2]:g} m ({tx[2] - roof:g} m mast), "
             f"{len(orientations)} sectors, downtilt {np.degrees(orientations[0][1]):g} deg. "
             f"Outdoor cells within {args.radius:g} m: {len(rows)}. "
             "Reference = Friis + TR 38.901 element gain of the best sector (no buildings); "
             "excess loss = reference - traced best-sector path gain.", "",
             "| Group | Cells | Uncovered | Behind own roof edge | Median best-sector pattern gain | Median excess loss |",
             "|---|---|---|---|---|---|"]
    for name, sel in groups.items():
        lines.append(f"| {name} | {len(sel)} | {share([{'u': not r['covered']} for r in sel], 'u')} | "
                     f"{share(sel, 'shadowed_by_own_roof')} | {med(sel, 'best_pattern_gain_dbi')} dBi | "
                     f"{med(sel, 'excess_db')} dB |")
    bins = [0, 50, 100, 150, 200, 250, 400]
    lines += ["", "| Distance from site | Cells | Uncovered | Behind own roof edge | Median pattern gain | Median excess loss |",
              "|---|---|---|---|---|---|"]
    for lo, hi in zip(bins[:-1], bins[1:], strict=True):
        sel = [r for r in rows if lo <= r["horizontal_m"] < hi]
        if sel:
            lines.append(f"| {lo}-{hi} m | {len(sel)} | {share([{'u': not r['covered']} for r in sel], 'u')} | "
                         f"{share(sel, 'shadowed_by_own_roof')} | {med(sel, 'best_pattern_gain_dbi')} dBi | "
                         f"{med(sel, 'excess_db')} dB |")
    (args.run / f"near_site_{args.scenario}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.run / f"near_site_{args.scenario}.json").write_text(json.dumps(rows), encoding="utf-8")

    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt
    style.apply()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for flag, colour, name in ((True, "#c0504d", "behind own roof edge"), (False, "#2a78d6", "clears own roof")):
        sel = [r for r in rows if r["shadowed_by_own_roof"] == flag]
        ax.scatter([r["horizontal_m"] for r in sel], [r["excess_db"] for r in sel], s=8, color=colour, label=name,
                   alpha=0.6)
    ax.set(xlabel="horizontal distance from site [m]", ylabel="excess loss over free space + pattern [dB]",
           title=f"{sc['label']}: near-site cells")
    ax.legend()
    fig.suptitle(run_label, x=0.05, ha="left", fontsize=9)
    fig.savefig(args.run / f"near_site_{args.scenario}.png")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
