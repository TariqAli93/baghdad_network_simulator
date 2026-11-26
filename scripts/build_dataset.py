"""Build the ray-tracing dataset of a study area from its OpenStreetMap snapshot.

    uv run python scripts/build_dataset.py --area tahrir_bab_al_sharqi
    uv run python scripts/build_dataset.py --area NAME --fetch
    uv run python scripts/build_dataset.py --area NAME --height-model low_rise_2_to_4 --seed 1
    uv run python scripts/build_dataset.py --area NAME --observations data/raw/heights/NAME.csv

Areas are defined in configs/study_area.yaml, height models in configs/height_models.yaml.
Without --fetch the stored snapshot in data/raw/osm/ is used, so results stay reproducible.

Writes
    data/scenes/<area>/<variant>/        scene.xml, meshes, buildings.geojson (git-ignored)
    outputs/datasets/<area>/<variant>/   quality_report.md and .json (kept)
where <variant> is "osm" or "<height model>-seed<N>".
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline
from bns.geospatial.study_area import load_study_areas

ROOT = Path(__file__).resolve().parents[1]
RAW_OSM = ROOT / "data" / "raw" / "osm"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--fetch", action="store_true",
                        help="download a new OpenStreetMap snapshot (replaces the stored one)")
    parser.add_argument("--height-model", help="name in configs/height_models.yaml")
    parser.add_argument("--seed", type=int, help="random seed, required with --height-model")
    parser.add_argument("--observations", type=Path,
                        help="CSV of observed heights: building_id,height_m,method[,observer,date,uncertainty_m]")
    args = parser.parse_args()

    areas = load_study_areas(ROOT / "configs" / "study_area.yaml")
    if args.area not in areas:
        print(f"Unknown area '{args.area}'. Defined: {', '.join(areas)}")
        return 1
    area = areas[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")

    if args.fetch:
        meta = osm_source.fetch_snapshot(
            RAW_OSM, area.name, area.bbox_degrees(),
            {"name": area.name, "lat": area.center_lat, "lon": area.center_lon})
        print(f"Fetched snapshot {area.name}.json ({meta['sha256'][:12]}, {meta['fetched_utc']})")
    data, meta = osm_source.load_snapshot(RAW_OSM, area.name)

    model, variant = None, "osm"
    if args.height_model:
        models = ht.load_height_models(ROOT / "configs" / "height_models.yaml")
        if args.height_model not in models:
            print(f"Unknown height model '{args.height_model}'. Defined: {', '.join(models)}")
            return 1
        if args.seed is None:
            print("--height-model needs --seed.")
            return 1
        model, variant = models[args.height_model], f"{args.height_model}-seed{args.seed}"
    rows = None
    if args.observations:
        with open(args.observations, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

    scene_dir = ROOT / "data" / "scenes" / area.name / variant
    report = pipeline.build_dataset(
        area, data, scene_dir, policy, meta["sha256"], height_model=model, seed=args.seed,
        manual_rows=rows, manual_name=args.observations.name if args.observations else "manual")

    report_dir = ROOT / "outputs" / "datasets" / area.name / variant
    report_dir.mkdir(parents=True, exist_ok=True)
    for name in ("quality_report.md", "quality_report.json"):
        shutil.copyfile(scene_dir / name, report_dir / name)

    cats = report["height_categories"]["by_count_percent"]
    print(f"{area.name} [{variant}]: {report['buildings']} buildings; heights observed "
          f"{cats['observed']:.1f} %, estimated {cats['estimated']:.1f} %, "
          f"placeholder {cats['placeholder']:.1f} %")
    print(f"mesh: {report['mesh'].get('triangles')} triangles, {report['mesh'].get('wedges')} wedges, "
          f"{report['mesh'].get('non_manifold_edges')} non-manifold edges")
    verdict = "fit for research" if report["fit_for_research"] else "NOT fit for research"
    print(f"{verdict}: {'; '.join(report['not_fit_reasons'])}")
    print(f"scene: {scene_dir}")
    print(f"report: {report_dir / 'quality_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
