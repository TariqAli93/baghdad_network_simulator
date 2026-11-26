"""GlobalBuildingAtlas (GBA.LoD1) heights against OpenStreetMap tags and 3D-GloBFP.

    uv run python scripts/evaluate_gba.py --area tahrir_bab_al_sharqi_v2

Needs the tile named in configs/height_datasets.yaml (gba) in data/cache/datasets/gba/
(its SHA-256 is checked). Writes the study-area extract data/raw/heights/gba/<area>.json
(+ .meta.json; never overwritten), outputs/datasets/<area>/gba_evaluation.md,
gba_evaluation.json and gba_buildings.csv. Nothing here changes a building height.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml
from scipy.stats import spearmanr

from bns.geospatial import gba
from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline
from bns.geospatial.study_area import load_study_areas

ROOT = Path(__file__).resolve().parents[1]
TOWER = "way/919688856"


def number(text) -> float | None:
    try:
        return float(str(text).replace("m", "").strip())
    except ValueError:
        return None


def stats(values, unit=" m", digits=1) -> str:
    v = np.asarray([x for x in values if x is not None], dtype=float)
    if v.size == 0:
        return "none"
    p5, p50, p95 = np.percentile(v, [5, 50, 95])
    f = f"{{:.{digits}f}}"
    return (f"n={v.size}, min {f.format(v.min())}, p5 {f.format(p5)}, median {f.format(p50)}, "
            f"p95 {f.format(p95)}, max {f.format(v.max())}{unit}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    args = parser.parse_args()

    spec = yaml.safe_load((ROOT / "configs" / "height_datasets.yaml").read_text(encoding="utf-8"))["datasets"]["gba"]
    tile = ROOT / "data" / "cache" / "datasets" / "gba" / spec["file"]
    if not tile.exists():
        print(f"Missing {tile}; download it from {spec['url']} (see configs/height_datasets.yaml).")
        return 1
    digest = sha256(tile)
    if digest != spec["sha256"]:
        print(f"Checksum mismatch for {tile}: {digest}")
        return 1

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")
    data, meta = osm_source.load_snapshot(ROOT / "data" / "raw" / "osm", area.snapshot)
    buildings, _, _ = pipeline.provenance_buildings(area, data, policy, meta["sha256"])
    records = gba.read_osm_records(tile)
    receiver = area.receiver_box()

    globfp = {}
    gpath = ROOT / "outputs" / "datasets" / area.name / "3d_globfp_buildings.csv"
    if gpath.exists():
        with gpath.open(encoding="utf-8") as f:
            globfp = {r["building_id"]: r for r in csv.DictReader(f)}

    rows, extract = [], {}
    for b in buildings:
        found = gba.lookup(records, b.building_id)
        heights = [h for _, h, _ in found if h is not None]
        tags = b.tags
        levels = number(tags.get("building:levels", ""))
        g = globfp.get(b.building_id, {})
        if found:
            extract[b.building_id] = [{"key": k, "height": h, "var": v} for k, h, v in found]
        rows.append({
            "building_id": b.building_id, "in_receiver_area": receiver.contains(b.polygon.representative_point()),
            "footprint_area_m2": round(b.polygon.area, 1), "resolved_height_m": b.height.height_m,
            "resolved_category": b.height.category, "resolved_source": b.height.source,
            "osm_height_tag": tags.get("height", ""), "osm_levels_tag": tags.get("building:levels", ""),
            "osm_levels_x_storey_m": "" if levels is None else round(levels * policy.storey_height_m, 1),
            "gba_keys": " ".join(k for k, *_ in found),
            "gba_height_m": "" if not heights else round(float(np.median(heights)), 2),
            "gba_var": "" if not found or found[0][2] is None else round(found[0][2], 3),
            "globfp_height_m": g.get("dataset_height_m", ""), "globfp_match": g.get("match_kind", ""),
        })

    out_dir = ROOT / "outputs" / "datasets" / area.name
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "gba_buildings.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    raw = ROOT / "data" / "raw" / "heights" / "gba" / f"{area.name}.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    if not raw.exists():                                     # extracts are never overwritten
        raw.write_text(json.dumps(extract, indent=1, sort_keys=True), encoding="utf-8")
        raw.with_suffix(".meta.json").write_text(json.dumps({
            "dataset": "gba", "source_file": spec["file"], "source_url": spec["url"],
            "source_sha256": digest, "revision": spec["revision"], "licence": spec["licence"],
            "osm_snapshot_sha256": meta["sha256"], "buildings": len(extract),
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "extract_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            "note": "GBA heights joined by OSM way id; GBA footprints were not used."}, indent=2), encoding="utf-8")

    def f(r, k):
        return None if r[k] == "" else float(r[k])

    inner = [r for r in rows if r["in_receiver_area"]]
    with_gba = [r for r in inner if r["gba_height_m"] != ""]
    area_all = sum(r["footprint_area_m2"] for r in inner)
    area_gba = sum(r["footprint_area_m2"] for r in with_gba)
    tagged = []
    for r in rows:
        ref = number(r["osm_height_tag"]) if r["osm_height_tag"] else None
        kind = "height tag"
        if ref is None and r["osm_levels_x_storey_m"] != "":
            ref, kind = float(r["osm_levels_x_storey_m"]), "storeys x 3 m"
        if ref is not None and r["gba_height_m"] != "":
            tagged.append((r, kind, ref, float(r["gba_height_m"])))
    both = [(float(r["gba_height_m"]), float(r["globfp_height_m"])) for r in inner
            if r["gba_height_m"] != "" and r["globfp_height_m"] != ""]
    gv = [(f(r, "gba_height_m"), f(r, "gba_var")) for r in with_gba if r["gba_var"] != ""]
    tower = next((r for r in rows if r["building_id"] == TOWER), None)
    placeholder_with_gba = [r for r in with_gba if r["resolved_category"] == ht.PLACEHOLDER]

    lines = [
        f"# GlobalBuildingAtlas heights against OpenStreetMap: {area.name}", "",
        f"Dataset: {spec['name']} ({spec['version']}), file `{spec['file']}`, revision {spec['revision'][:12]}, "
        f"SHA-256 {digest[:12]}... verified; licence {spec['licence']}. OSM snapshot {meta['sha256'][:12]} "
        f"({meta['fetched_utc']}). Generated by `scripts/evaluate_gba.py`; per-building table "
        "`gba_buildings.csv`.", "",
        "GBA heights were joined to OSM buildings **by way id** (GBA keys `osm<way id>IRQ`). The tile has no "
        "geometry; GBA footprints were not used. Relations cannot be joined (GBA keys carry no element type).", "",
        "## Coverage of the OSM buildings", "",
        f"- OSM buildings in the receiver area: {len(inner)}; with a GBA height: {len(with_gba)} "
        f"({100 * len(with_gba) / len(inner):.1f} % by count, {100 * area_gba / area_all:.1f} % by footprint area).",
        f"- Of the receiver-area buildings that today carry a placeholder height, {len(placeholder_with_gba)} have a "
        "GBA value.",
        f"- OSM-sourced records in the whole tile: {len(records)}; the tile also holds about 3.94 million "
        "Microsoft-footprint records for Iraq (`msIraq_<quadkey>_<n>IRQ`) whose footprints are only in the "
        "ODbL polygon part (GBA.ODbLPolygon), which was not downloaded.", "",
        "## Heights", "",
        f"- GBA, receiver area: {stats([f(r, 'gba_height_m') for r in with_gba])}.",
        f"- GBA below 3 m: {sum(f(r, 'gba_height_m') < 3 for r in with_gba)}; above 30 m: "
        f"{sum(f(r, 'gba_height_m') > 30 for r in with_gba)}.",
        f"- 3D-GloBFP for the same buildings: {stats([g for _, g in both])}; GBA {stats([a for a, _ in both])}.",
    ]
    if len(both) > 2:
        rho = spearmanr([a for a, _ in both], [b for _, b in both]).statistic
        diff = np.array([b - a for a, b in both])
        lines.append(f"- 3D-GloBFP minus GBA on {len(both)} buildings: median {np.median(diff):+.1f} m, "
                     f"mean {diff.mean():+.1f} m; Spearman correlation {rho:.2f}.")
    if len(gv) > 2:
        lines.append(f"- GBA `var` (undefined in the dataset card): {stats([v for _, v in gv], '', 2)}; "
                     f"Spearman with height {spearmanr([h for h, _ in gv], [v for _, v in gv]).statistic:.2f}.")
    lines += ["", "### Against OSM buildings with a height or storey tag (whole clip area)", "",
              "| OSM building | Reference | Reference height | GBA height | GBA - reference | 3D-GloBFP | In receiver area |",
              "|---|---|---|---|---|---|---|"]
    for r, kind, ref, est in sorted(tagged, key=lambda t: -t[2]):
        lines.append(f"| {r['building_id']} | {kind} | {ref:.1f} m | {est:.1f} m | {est - ref:+.1f} m | "
                     f"{r['globfp_height_m'] or '-'} | {'yes' if r['in_receiver_area'] else 'no'} |")
    summary = {"receiver_buildings": len(inner), "receiver_with_gba": len(with_gba),
               "receiver_area_share_with_gba": area_gba / area_all, "tagged_comparisons": len(tagged)}
    if tagged:
        d = np.array([est - ref for _, _, ref, est in tagged])
        ordinary = np.array([est - ref for _, _, ref, est in tagged if ref < 30])
        lines += ["", f"Over these {len(tagged)} buildings: mean difference {d.mean():+.1f} m, median "
                      f"{np.median(d):+.1f} m, RMSE {np.sqrt((d ** 2).mean()):.1f} m"
                      + (f"; below 30 m ({ordinary.size}): RMSE {np.sqrt((ordinary ** 2).mean()):.1f} m"
                         if ordinary.size else "")
                      + ". Tags are OSM contributions, not surveyed truth, and storeys x 3 m is itself an estimate."]
        summary.update({"tagged_mean_diff_m": float(d.mean()), "tagged_rmse_m": float(np.sqrt((d ** 2).mean()))})
    lines += ["", f"### The tagged tower ({TOWER}: height tag 55 m, 14 storeys)", ""]
    if tower is None or tower["gba_height_m"] == "":
        lines.append("No GBA record for the tower.")
    else:
        lines.append(f"GBA {tower['gba_height_m']} m (var {tower['gba_var']}), 3D-GloBFP "
                     f"{tower['globfp_height_m'] or '-'} m, OSM tag 55 m.")
        summary["tower_gba_m"] = float(tower["gba_height_m"])
    (out_dir / "gba_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "gba_evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
