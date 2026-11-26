"""Compare two built datasets building by building (for example the frozen fixture and v2).

    uv run python scripts/compare_datasets.py --a tahrir_bab_al_sharqi/osm --b tahrir_bab_al_sharqi_v2/osm

Each argument is <area>/<variant> under data/scenes/. Writes
outputs/datasets/comparison_<a>_vs_<b>.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from bns.geospatial import pipeline
from bns.geospatial.study_area import load_study_areas

ROOT = Path(__file__).resolve().parents[1]


def load(spec: str):
    area_name, variant = spec.split("/")
    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[area_name]
    folder = ROOT / "data" / "scenes" / area_name / variant
    buildings = {b.building_id: b for b in pipeline.load_buildings(folder, area)}
    meta = json.loads((folder / "scene_meta.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "quality_report.json").read_text(encoding="utf-8"))
    return area, buildings, meta, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    args = parser.parse_args()
    area_a, a, meta_a, rep_a = load(args.a)
    area_b, b, meta_b, rep_b = load(args.b)
    if (area_a.center_lat, area_a.center_lon) != (area_b.center_lat, area_b.center_lon):
        print("The two datasets cover different areas; local coordinates are not comparable.")
        return 1

    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    common = sorted(set(a) & set(b))
    changed = [(i, a[i].polygon.area, b[i].polygon.area) for i in common
               if abs(a[i].polygon.area - b[i].polygon.area) > 1.0]
    moved = [i for i in common if a[i].polygon.symmetric_difference(b[i].polygon).area > 1.0]
    kind = lambda ids: Counter(i.split("/")[0] for i in ids)
    courtyards_b = sum(len(b[i].polygon.interiors) > 0 for i in only_b)
    area_sum = lambda d, ids: sum(d[i].polygon.area for i in ids)

    lines = [
        f"# Dataset comparison: {args.a} vs {args.b}",
        "",
        f"- A: OSM snapshot {rep_a['osm_snapshot_sha256'][:12]}; B: OSM snapshot "
        f"{rep_b['osm_snapshot_sha256'][:12]}.",
        "",
        "| Quantity | A | B |",
        "|---|---|---|",
        f"| Buildings | {len(a)} | {len(b)} |",
        f"| From multipolygon relations | {kind(a).get('relation', 0)} | {kind(b).get('relation', 0)} |",
        f"| Relations read / with missing members | {rep_a['parse'].get('relations_read', 0)} / "
        f"{rep_a['parse'].get('relations_with_missing_members', 0)} | "
        f"{rep_b['parse'].get('relations_read', 0)} / {rep_b['parse'].get('relations_with_missing_members', 0)} |",
        f"| Elements skipped while reading | {rep_a['parse'].get('skipped') or 'none'} | "
        f"{rep_b['parse'].get('skipped') or 'none'} |",
        f"| Duplicate footprint pairs | {rep_a['parse'].get('duplicate_pairs', 'not checked')} | "
        f"{rep_b['parse'].get('duplicate_pairs', 'not checked')} |",
        f"| Footprint area | {rep_a['footprint_area_m2']:,.0f} m² | {rep_b['footprint_area_m2']:,.0f} m² |",
        f"| Built share of receiver area | {rep_a['built_share_of_receiver_area_percent']:.2f} % | "
        f"{rep_b['built_share_of_receiver_area_percent']:.2f} % |",
        f"| Mesh triangles / wedges | {meta_a['mesh']['triangles']} / {meta_a['mesh']['wedges']} | "
        f"{meta_b['mesh']['triangles']} / {meta_b['mesh']['wedges']} |",
        f"| Mesh defects (non-manifold edges, degenerate triangles) | "
        f"{meta_a['mesh']['non_manifold_edges']}, {meta_a['mesh']['degenerate_triangles']} | "
        f"{meta_b['mesh']['non_manifold_edges']}, {meta_b['mesh']['degenerate_triangles']} |",
        "",
        f"- Buildings only in A: {len(only_a)} ({dict(kind(only_a))}), {area_sum(a, only_a):,.0f} m².",
        f"- Buildings only in B: {len(only_b)} ({dict(kind(only_b))}), {area_sum(b, only_b):,.0f} m²; "
        f"{courtyards_b} of them have courtyards (inner rings).",
        f"- Buildings in both whose footprint changed by more than 1 m²: {len(moved)} "
        f"(area changed: {len(changed)}).",
        "",
    ]
    if only_b:
        lines += ["| Building only in B | Footprint | Courtyards | Height | Height source |",
                  "|---|---|---|---|---|"]
        for i in only_b:
            h = b[i].height
            lines.append(f"| {i} | {b[i].polygon.area:,.0f} m² | {len(b[i].polygon.interiors)} | "
                         f"{h.height_m:g} m | {h.source} |")
        lines.append("")
    if only_a:
        lines += ["| Building only in A | Footprint |", "|---|---|"]
        lines += [f"| {i} | {a[i].polygon.area:,.0f} m² |" for i in only_a]
        lines.append("")
    if changed:
        lines += ["| Building in both | Area in A | Area in B |", "|---|---|---|"]
        lines += [f"| {i} | {x:,.0f} m² | {y:,.0f} m² |" for i, x, y in changed[:40]]
    out = ROOT / "outputs" / "datasets" / (
        f"comparison_{args.a.replace('/', '-')}_vs_{args.b.replace('/', '-')}.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
