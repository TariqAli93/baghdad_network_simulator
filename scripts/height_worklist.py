"""List the buildings whose height should be observed, as a CSV to fill in.

    uv run python scripts/height_worklist.py --area tahrir_bab_al_sharqi_v2 ^
        --mast-height-m 3 --min-site-height-m 10 --site-spacing-m 150 --max-sites 20 ^
        --tall-m 20 --near-site-m 150 --blocking-share 0.5 [--height-dataset 3d_globfp]

A building is listed when it is tall by any source, hosts a candidate site, has
conflicting height sources, or stands near a candidate site and is at least the given
share of that site's antenna height. Fill in height_m, method, observer, date and
(optionally) uncertainty_m, then build with --observations <file>. Rows left blank are
ignored. Candidate sites are those scripts/build_dataset.py would propose with the same
arguments; all arguments are provisional (decision D4).

Writes outputs/datasets/<area>/height_worklist.csv.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline, sites
from bns.geospatial.study_area import load_study_areas

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    for name in ("--mast-height-m", "--min-site-height-m", "--site-spacing-m", "--tall-m",
                 "--near-site-m", "--blocking-share"):
        parser.add_argument(name, type=float, required=True)
    parser.add_argument("--max-sites", type=int, required=True)
    parser.add_argument("--height-dataset", action="append", default=[])
    parser.add_argument("--observations", type=Path,
                        help="observations made so far (stage 1), so new candidate roofs are found")
    parser.add_argument("--add-footprints", action="append", default=[],
                        help="also list footprints added from this dataset (as scripts/build_dataset.py does)")
    args = parser.parse_args()

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")
    data, meta = osm_source.load_snapshot(ROOT / "data" / "raw" / "osm", area.snapshot)
    specs = yaml.safe_load((ROOT / "configs" / "height_datasets.yaml").read_text(encoding="utf-8"))
    datasets = [(specs["datasets"][k]["name"], ROOT / "data" / "raw" / "heights" / k / f"{area.name}.geojson",
                 specs["datasets"][k]["doi"]) for k in args.height_dataset]
    raw = ROOT / "data" / "raw" / "heights"
    footprints = [(k, next(p for p in (raw / k / f"{area.name}.geojson", raw / k / f"{area.snapshot}.geojson")
                          if p.exists()), specs["datasets"][k]["name"]) for k in args.add_footprints]
    rows = None
    if args.observations:
        with open(args.observations, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    buildings, _, _ = pipeline.provenance_buildings(area, data, policy, meta["sha256"],
                                                    height_datasets=datasets, extra_footprints=footprints,
                                                    manual_rows=rows, manual_name=Path(args.observations).name
                                                    if args.observations else "manual")
    inside = [b for b in buildings if area.receiver_box().contains(b.polygon.representative_point())]
    candidates = sites.rooftop_candidates(
        inside, mast_height_m=args.mast_height_m, min_height_m=args.min_site_height_m,
        min_area_m2=0.0, min_spacing_m=args.site_spacing_m, max_candidates=args.max_sites,
        categories=(ht.OBSERVED, ht.ESTIMATED))
    rows = ht.observation_worklist(buildings, candidates, tall_m=args.tall_m,
                                   near_site_m=args.near_site_m, blocking_share=args.blocking_share)
    inverse = area.transformer()
    for row in rows:
        lon, lat = inverse.transform(row["x_m"], row["y_m"], direction="INVERSE")
        row["lat"], row["lon"] = round(lat, 6), round(lon, 6)
        kind = row["building_id"].split("/")[0]
        row["osm_url"] = (f"https://www.openstreetmap.org/{row['building_id'].split('#')[0]}"
                          if kind in ("way", "relation") else "")
        row["building_id"] = row["building_id"].split("#p")[0]    # observations apply to the whole building
    out = ROOT / "outputs" / "datasets" / area.name / "height_worklist.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["building_id"])
        writer.writeheader()
        writer.writerows(rows)
    counts = {}
    for row in rows:
        for reason in row["reasons"].split("; "):
            counts[reason] = counts.get(reason, 0) + 1
    print(f"{len(rows)} buildings to observe ({counts}); {len(candidates)} candidate sites -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
