"""Field-observation package: prioritised worklist, CSV template, printable map, guide.

    uv run python scripts/fieldwork_package.py --area tahrir_bab_al_sharqi_study --variant osm+fp_3d_globfp
        [--near-site-m 150] [--search-min-area-m2 1000]

Reads the observation worklist (scripts/height_worklist.py) and the built dataset, and writes
outputs/datasets/<area>/fieldwork/:
  observation_priorities.csv  every worklist building with its priority and why it is listed
  observation_template.csv    the file to fill in (one row per building, priority order)
  fieldwork_map.png / .pdf    printable A3 map, numbered buildings by priority
(README.md in that folder, the observation guide, is maintained by hand.)

Priorities (plain geometry, no new optimisation):
  P0  tall buildings (20 m or more by any source)
  P1  candidate transmitter rooftops
  P2  the worklist buildings that, at their current heights, cast 90 % of the shadow around the
      candidate sites: for each roof-edge antenna (configs/site_rule.yaml) and each outdoor point
      every 10 m within --near-site-m, the first building that cuts the straight line
  P3  the remaining worklist buildings (their uncertainty is carried by the height
      sensitivity analysis)
  S   PROPOSAL, not in the approved worklist: large placeholder buildings in the receiver area
      (footprint >= --search-min-area-m2) whose storeys would reveal further candidate roofs (A4)
Which priorities are mandatory is set in configs/study_area.yaml (observations); the approved
method today requires the whole worklist (P0-P3).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHY = {
    "P0": "tall building: dominates shadowing and can host a site; its height must be known",
    "P1": "candidate transmitter rooftop: sets the antenna height (roof + 3 m mast)",
    "P2": "casts much of the shadow around a candidate site at its current height: decides coverage there",
    "P3": "near a candidate site but casts little shadow first; covered by the height sensitivity analysis",
    "S": "large building of unknown height: its storey count may make it a candidate roof (A4)",
}
COLOURS = {"P0": "#c0392b", "P1": "#e67e22", "P2": "#2a78d6", "P3": "#9ec5f4", "S": "#5b8c3a"}
TEMPLATE_FIELDS = ["building_id", "priority", "map_no", "method_class", "height_m", "storeys", "method", "source",
                   "date", "uncertainty_m", "observer", "notes"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--near-site-m", type=float, default=150.0)
    parser.add_argument("--search-min-area-m2", type=float, default=1000.0)
    args = parser.parse_args()

    import numpy as np
    import yaml
    from shapely.geometry import Point

    from bns.geospatial import pipeline
    from bns.geospatial.sites import edge_positions, shadowing_buildings
    from bns.geospatial.study_area import load_study_areas

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    out_dir = ROOT / "outputs" / "datasets" / area.name / "fieldwork"
    worklist_path = ROOT / "outputs" / "datasets" / area.name / "height_worklist.csv"
    if not worklist_path.exists():
        print(f"No worklist {worklist_path}: run scripts/height_worklist.py first.")
        return 1
    rows = list(csv.DictReader(worklist_path.open(encoding="utf-8")))
    ids = [r["building_id"] for r in rows]
    if len(ids) != len(set(ids)):
        print("The worklist has duplicate building ids.")
        return 1
    buildings = pipeline.load_buildings(ROOT / "data" / "scenes" / area.name / args.variant, area)
    by_id = {b.building_id: b for b in buildings}
    missing = [i for i in ids if i not in by_id]
    if missing:
        print(f"{len(missing)} worklist ids are not in the dataset {args.variant}: {missing[:5]}")
        return 1

    candidates = [r["building_id"] for r in rows if "candidate rooftop" in r["reasons"]]
    radio = yaml.safe_load((ROOT / "configs" / "radio_system.yaml").read_text(encoding="utf-8"))["parameters"]
    rule = yaml.safe_load((ROOT / "configs" / "site_rule.yaml").read_text(encoding="utf-8"))
    mast, rx_h = float(radio["antenna_height_above_roof_m"]["value"]), float(radio["rx_height_m"]["value"])
    from shapely.strtree import STRtree
    tree = STRtree([b.polygon for b in buildings])
    hits: dict[str, int] = {}
    for cid in candidates:
        host = by_id[cid]
        p = host.polygon.representative_point()
        z = host.height.height_m + mast
        antennas = [(x, y, z) for x, y in edge_positions(host.polygon, p.x, p.y, list(np.radians([0, 120, 240])),
                                                         float(rule.get("edge_inset_m", 1.0)))]
        grid = [(p.x + dx, p.y + dy) for dx in np.arange(-args.near_site_m, args.near_site_m + 1, 10.0)
                for dy in np.arange(-args.near_site_m, args.near_site_m + 1, 10.0)
                if dx * dx + dy * dy <= args.near_site_m ** 2]
        outdoor = [(x, y) for x, y in grid if len(tree.query(Point(x, y), predicate="intersects")) == 0]
        for bid, n in shadowing_buildings(buildings, antennas, outdoor, rx_h).items():
            hits[bid] = hits.get(bid, 0) + n
    worklist_ids = {r["building_id"] for r in rows}
    ranked = sorted(((n, bid) for bid, n in hits.items() if bid in worklist_ids and bid not in candidates), reverse=True)
    total = sum(n for n, _ in ranked)
    p2, acc = set(), 0
    for n, bid in ranked:
        if total and acc >= 0.9 * total:
            break
        p2.add(bid)
        acc += n
    off_list = sorted(((n, bid) for bid, n in hits.items() if bid not in worklist_ids and bid not in candidates),
                      reverse=True)

    def priority(r):
        if "tall" in r["reasons"]:
            return "P0"
        if "candidate rooftop" in r["reasons"]:
            return "P1"
        return "P2" if r["building_id"] in p2 else "P3"

    receiver = area.receiver_box()
    listed = set(ids)
    search = sorted((b for b in buildings if b.building_id not in listed and b.height.category == "placeholder"
                     and b.polygon.area >= args.search_min_area_m2
                     and receiver.contains(b.polygon.representative_point())),
                    key=lambda b: -b.polygon.area)
    transformer = area.transformer()
    out = []
    for r in rows:
        b = by_id[r["building_id"]]
        out.append({"building_id": r["building_id"], "priority": priority(r), "reasons": r["reasons"],
                    "shadow_lines": hits.get(r["building_id"], 0), "b": b})
    for b in search:
        out.append({"building_id": b.building_id, "priority": "S", "reasons": "candidate search (proposal)",
                    "shadow_lines": 0, "b": b})
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "S": 4}
    out.sort(key=lambda o: (order[o["priority"]], -o["shadow_lines"], -o["b"].polygon.area, o["building_id"]))
    for n, o in enumerate(out, start=1):
        o["map_no"] = n

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "observation_priorities.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["map_no", "building_id", "priority", "why", "reasons", "shadow_lines",
                    "current_height_m", "current_category", "current_source", "footprint_m2", "x_m", "y_m",
                    "lat", "lon", "osm_url"])
        for o in out:
            b = o["b"]
            p = b.polygon.representative_point()
            lon, lat = transformer.transform(p.x, p.y, direction="INVERSE")
            kind = b.building_id.split("/")[0]
            url = (f"https://www.openstreetmap.org/{b.building_id.split('#')[0]}" if kind in ("way", "relation")
                   else "")
            w.writerow([o["map_no"], b.building_id, o["priority"], WHY[o["priority"]], o["reasons"],
                        o["shadow_lines"], b.height.height_m, b.height.category, b.height.source,
                        round(b.polygon.area), round(p.x, 1), round(p.y, 1), f"{lat:.6f}", f"{lon:.6f}", url])
    with (out_dir / "observation_template.csv").open("w", newline="", encoding="utf-8") as f:
        f.write("# Fill in one row per building you observed; leave the others empty. method_class: measured | "
                "documented | visual_estimate | storey_count. See README.md. Do not invent values.\n")
        w = csv.DictWriter(f, fieldnames=TEMPLATE_FIELDS)
        w.writeheader()
        for o in out:
            w.writerow({"building_id": o["building_id"], "priority": o["priority"], "map_no": o["map_no"]})

    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    style.apply()
    fig, ax = plt.subplots(figsize=(11.7, 13.5))                     # A3 portrait (map + legend)
    for b in buildings:
        if receiver.buffer(60).intersects(b.polygon):
            for poly in getattr(b.polygon, "geoms", [b.polygon]):
                xs, ys = poly.exterior.xy
                ax.fill(xs, ys, color="#e4e3dd", linewidth=0.2, edgecolor="#a6a59c")
    for o in sorted(out, key=lambda o: -order[o["priority"]]):          # highest priority drawn last, on top
        for poly in getattr(o["b"].polygon, "geoms", [o["b"].polygon]):
            xs, ys = poly.exterior.xy
            ax.fill(xs, ys, color=COLOURS[o["priority"]], linewidth=0.3, edgecolor="#333")
        if o["priority"] in ("P0", "P1", "P2", "S"):
            p = o["b"].polygon.representative_point()
            ax.annotate(str(o["map_no"]), (p.x, p.y), fontsize=6.5, ha="center", va="center", color="#000",
                        fontweight="bold")
    rx, ry = receiver.exterior.xy
    ax.plot(rx, ry, color="#c0392b", linestyle="--", linewidth=1)
    ax.set_aspect("equal")
    ax.set(xlabel="x east [m] (origin 33.3280 N, 44.4085 E)", ylabel="y north [m]",
           xlim=(receiver.bounds[0] - 60, receiver.bounds[2] + 60), ylim=(receiver.bounds[1] - 60, receiver.bounds[3] + 60))
    counts = {k: sum(o["priority"] == k for o in out) for k in COLOURS}
    ax.legend(handles=[Patch(color=COLOURS[k], label=f"{k} ({counts[k]}): {WHY[k].split(':')[0]}") for k in COLOURS],
              loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2, fontsize=8, frameon=False)
    ax.set_title(f"Building-height fieldwork, {area.name}\n"
                 "Numbers = map_no in observation_template.csv (P3 shown, not numbered)", fontsize=11)
    fig.text(0.01, 0.005, "Footprints © OpenStreetMap contributors (ODbL) and 3D-GloBFP (CC BY 4.0). "
             "Observe only from public space; never enter roofs or restricted areas.", fontsize=7)
    fig.savefig(out_dir / "fieldwork_map.png", dpi=200)
    fig.savefig(out_dir / "fieldwork_map.pdf")
    plt.close(fig)
    print(f"{out_dir}: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f"; {len(out)} rows")
    print(f"shadow lines: {sum(hits.values())}; P2 covers {acc} of {total} lines blocked by worklist buildings; "
          f"{len(off_list)} blocking buildings are not on the worklist (largest: {off_list[:3]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
