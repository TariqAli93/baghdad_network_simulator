"""Compare an external building-height extract with the OpenStreetMap buildings of an area.

    uv run python scripts/evaluate_height_dataset.py --dataset 3d_globfp --area tahrir_bab_al_sharqi_v2

Writes outputs/datasets/<area>/<dataset>_evaluation.md and <dataset>_buildings.csv
(one row per OSM building). The dataset is evaluated, not trusted: nothing here
changes any building height.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from bns.geospatial import height_datasets as hd
from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline
from bns.geospatial.study_area import load_study_areas

ROOT = Path(__file__).resolve().parents[1]
MIN_COVERAGE = 0.5
TOWER = "way/919688856"     # the one tagged high-rise in the area (14 storeys, 55 m)


def stats(values, unit: str = " m", digits: int = 1) -> str:
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return "none"
    p5, p50, p95 = np.percentile(v, [5, 50, 95])
    f = f"{{:.{digits}f}}"
    return (f"n={v.size}, min {f.format(v.min())}, p5 {f.format(p5)}, median {f.format(p50)}, "
            f"p95 {f.format(p95)}, max {f.format(v.max())}{unit}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--area", required=True)
    args = parser.parse_args()

    spec = yaml.safe_load((ROOT / "configs" / "height_datasets.yaml").read_text(encoding="utf-8"))
    spec = spec["datasets"][args.dataset]
    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")
    data, meta = osm_source.load_snapshot(ROOT / "data" / "raw" / "osm", area.snapshot)
    buildings, _, _ = pipeline.provenance_buildings(area, data, policy, meta["sha256"])
    extract_path = ROOT / "data" / "raw" / "heights" / args.dataset / f"{area.name}.geojson"
    external = [e for e in hd.load_extract(extract_path, area) if e.polygon.intersects(area.clip_box())]
    result = hd.match_footprints(buildings, external, MIN_COVERAGE)
    by_id = {m.building_id: m for m in result.matches}

    rows = []
    for b in buildings:
        tags = b.tags
        levels = osm_source_number(tags.get("building:levels"))
        m = by_id.get(b.building_id)
        rows.append({
            "building_id": b.building_id,
            "footprint_area_m2": round(b.polygon.area, 1),
            "osm_height_tag": tags.get("height", ""),
            "osm_levels_tag": tags.get("building:levels", ""),
            "osm_levels_x_storey_m": "" if levels is None else round(levels * policy.storey_height_m, 1),
            "dataset_height_m": "" if m is None else round(m.height_m, 2),
            "dataset_max_height_m": "" if m is None else round(m.max_height_m, 2),
            "match_kind": "unmatched" if m is None else m.kind,
            "coverage": "" if m is None else round(m.coverage, 3),
            "iou": "" if m is None else round(m.iou, 3),
            "dataset_footprints": "" if m is None else " ".join(m.footprint_ids),
        })

    out_dir = ROOT / "outputs" / "datasets" / area.name
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{args.dataset}_buildings.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    kinds = Counter(m.kind for m in result.matches)
    one = [m for m in result.matches if m.kind == "one-to-one"]
    receiver = area.receiver_box()
    ext_in_receivers = [e for e in external if receiver.contains(e.polygon.representative_point())]
    import shapely
    from scipy.stats import spearmanr
    osm_tree = shapely.STRtree([b.polygon for b in buildings])
    lonely = [e for e in external if len(osm_tree.query(e.polygon, predicate="intersects")) == 0]
    area_height_rho = float(spearmanr([e.polygon.area for e in external],
                                      [e.height_m for e in external]).statistic)

    # Buildings with an OSM height or storey count, against the dataset.
    tagged = []
    for r in rows:
        reference = r["osm_height_tag"] and osm_source_number(r["osm_height_tag"])
        if not reference and r["osm_levels_x_storey_m"] != "":
            reference = r["osm_levels_x_storey_m"]
        if reference and r["dataset_height_m"] != "":
            tagged.append((r, float(reference), float(r["dataset_height_m"])))

    tower = by_id.get(TOWER)
    tower_building = next((b for b in buildings if b.building_id == TOWER), None)
    tower_overlaps = []
    if tower_building is not None:
        for e in external:
            share = tower_building.polygon.intersection(e.polygon).area
            if share > 0:
                tower_overlaps.append((e.footprint_id, e.height_m, share / tower_building.polygon.area,
                                       e.polygon.area))

    lines = [
        f"# {spec['name']} against OpenStreetMap: {area.name}",
        "",
        f"Dataset: {spec['name']}, {spec['version']}, DOI {spec['doi']}, licence {spec['licence']}. "
        f"Heights are model estimates for {spec['year_of_heights']}. OSM snapshot "
        f"{meta['sha256'][:12]} ({meta['fetched_utc']}). Generated by "
        "`scripts/evaluate_height_dataset.py`; per-building table in "
        f"`{args.dataset}_buildings.csv`.",
        "",
        "## Footprint matching",
        "",
        f"A building counts as matched when dataset footprints cover at least {100 * MIN_COVERAGE:.0f} % "
        "of its OSM footprint.",
        "",
        "| Quantity | Count |",
        "|---|---|",
        f"| OSM buildings (after repair and clipping) | {len(buildings)} |",
        f"| Dataset footprints in the area | {len(external)} |",
        f"| Matched one-to-one | {kinds.get('one-to-one', 0)} |",
        f"| Matched, OSM building split into several dataset footprints | {kinds.get('split', 0)} |",
        f"| Matched, dataset footprint spans several OSM buildings | {kinds.get('merged', 0)} |",
        f"| OSM buildings without a match | {len(result.osm_unmatched)} |",
        f"| Dataset footprints matched to no OSM building | {len(result.external_unmatched)} |",
        f"| Dataset footprint pairs overlapping by 90 % or more (duplicates) | {len(result.external_duplicates)} |",
        "",
        f"- Matched share of OSM buildings: {100 * len(result.matches) / len(buildings):.1f} %; "
        f"of OSM footprint area: "
        f"{100 * sum(b.polygon.area for b in buildings if b.building_id in by_id) / sum(b.polygon.area for b in buildings):.1f} %.",
        f"- Overlap quality of one-to-one matches (IoU): {stats([m.iou for m in one], '', 2)}.",
        f"- Coverage of matched buildings: {stats([m.coverage for m in result.matches], '', 2)}.",
        f"- Footprint size, OSM: {stats([b.polygon.area for b in buildings], ' mÂ²', 0)}.",
        f"- Footprint size, dataset: {stats([e.polygon.area for e in external], ' mÂ²', 0)}.",
        f"- Dataset footprints overlapping no OSM building at all: {len(lonely)} "
        f"({sum(e.polygon.area for e in lonely):,.0f} mÂ²); these are buildings missing from OSM "
        "or footprints of non-buildings.",
        "",
        "## Heights",
        "",
        f"- Dataset, all footprints in the receiver area: {stats([e.height_m for e in ext_in_receivers])}.",
        f"- Dataset, assigned to matched OSM buildings: {stats([m.height_m for m in result.matches])}.",
        f"- Dataset, only one-to-one matches with IoU at least 0.5: "
        f"{stats([m.height_m for m in one if m.iou >= 0.5])}.",
        "- Dataset, by match kind (median): "
        + ", ".join(f"{k} {np.median([m.height_m for m in result.matches if m.kind == k]):.1f} m"
                    for k in ("one-to-one", "split", "merged") if kinds.get(k)) + ".",
        f"- Correlation between dataset footprint area and height (Spearman): {area_height_rho:.2f}.",
        f"- Dataset footprints below 3 m: {sum(e.height_m < 3 for e in external)}; above 30 m: "
        f"{sum(e.height_m > 30 for e in external)}.",
        "",
        "### Against the OSM buildings that carry a height or storey tag",
        "",
        "| OSM building | OSM tag | OSM-derived height | Dataset height | Difference | Match |",
        "|---|---|---|---|---|---|",
    ]
    for r, ref, est in tagged:
        tag = f"height={r['osm_height_tag']}" if r["osm_height_tag"] else f"levels={r['osm_levels_tag']}"
        lines.append(f"| {r['building_id']} | {tag} | {ref:.1f} m | {est:.1f} m | {est - ref:+.1f} m | "
                     f"{r['match_kind']} (IoU {r['iou']}) |")
    if tagged:
        diff = np.array([est - ref for _, ref, est in tagged])
        lines += ["", f"Over these {len(tagged)} buildings: mean difference {diff.mean():+.1f} m, "
                      f"RMSE {np.sqrt((diff ** 2).mean()):.1f} m. Several tagged objects are monuments "
                      "or walls rather than ordinary buildings, and the sample is far too small to "
                      "estimate the dataset's accuracy here."]
    lines += ["", f"### The tagged tower ({TOWER}: 14 storeys, height tag 55 m)", ""]
    if tower_building is None:
        lines.append("Not present in this dataset build.")
    else:
        lines.append(f"OSM footprint {tower_building.polygon.area:.0f} mÂ². Dataset footprints overlapping it:")
        lines.append("")
        lines.append("| Dataset footprint | Height | Share of the tower footprint | Its own area |")
        lines.append("|---|---|---|---|")
        for fid, h, share, area_m2 in sorted(tower_overlaps, key=lambda t: -t[2]):
            lines.append(f"| {fid} | {h:.1f} m | {100 * share:.0f} % | {area_m2:.0f} mÂ² |")
        if tower:
            lines.append("")
            lines.append(f"Assigned by matching: {tower.height_m:.1f} m ({tower.kind}, coverage "
                         f"{100 * tower.coverage:.0f} %, IoU {tower.iou:.2f}); largest overlapping value "
                         f"{tower.max_height_m:.1f} m.")
    (out_dir / f"{args.dataset}_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"buildings": len(buildings), "dataset_footprints": len(external),
               "match_kinds": dict(kinds), "osm_unmatched": len(result.osm_unmatched),
               "external_unmatched": len(result.external_unmatched),
               "duplicates": len(result.external_duplicates),
               "tower": None if tower is None else tower.__dict__}
    (out_dir / f"{args.dataset}_evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return 0


def osm_source_number(text):
    from bns.geospatial.heights import _number
    return _number(text)


if __name__ == "__main__":
    sys.exit(main())
