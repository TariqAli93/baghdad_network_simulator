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
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
import sys
from pathlib import Path

import yaml

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
    parser.add_argument("--height-dataset", action="append", default=[],
                        help="name in configs/height_datasets.yaml whose extract for this area "
                             "(scripts/import_height_dataset.py) adds height candidates")
    parser.add_argument("--add-footprints", action="append", default=[],
                        help="name in configs/height_datasets.yaml whose footprints that overlap no OSM "
                             "building are added (decision A2); their heights are NOT used")
    args = parser.parse_args()

    areas = load_study_areas(ROOT / "configs" / "study_area.yaml")
    if args.area not in areas:
        print(f"Unknown area '{args.area}'. Defined: {', '.join(areas)}")
        return 1
    area = areas[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")

    if args.fetch:
        meta = osm_source.fetch_snapshot(
            RAW_OSM, area.snapshot, area.bbox_degrees(),
            {"name": area.name, "lat": area.center_lat, "lon": area.center_lon})
        print(f"Fetched snapshot {area.snapshot}.json ({meta['sha256'][:12]}, {meta['fetched_utc']})")
    data, meta = osm_source.load_snapshot(RAW_OSM, area.snapshot)

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
            rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
        # every observation file gives its own, immutable dataset version
        obs_sha = hashlib.sha256(Path(args.observations).read_bytes()).hexdigest()
        variant += f"+observations-{obs_sha[:8]}"
    datasets = []
    if args.height_dataset:
        specs = yaml.safe_load((ROOT / "configs" / "height_datasets.yaml").read_text(
            encoding="utf-8"))["datasets"]
        for key in args.height_dataset:
            folder = ROOT / "data" / "raw" / "heights" / key
            extract = next((p for p in (folder / f"{area.name}.geojson", folder / f"{area.name}.json")
                            if p.exists()), None)
            if extract is None:
                print(f"No {key} extract for {area.name}: run scripts/import_height_dataset.py "
                      "(footprint datasets) or scripts/evaluate_gba.py (GBA) first.")
                return 1
            spec = specs[key]
            where = f"DOI {spec['doi']}" if "doi" in spec else f"revision {spec['revision'][:12]}"
            datasets.append((f"{spec['name']} {spec['version'].split()[0]}", extract,
                             f"{spec['name']} {spec.get('tile') or spec.get('file', '')}, {where}"))
            variant += f"+{key}"

    footprints = []
    if args.add_footprints:
        specs = yaml.safe_load((ROOT / "configs" / "height_datasets.yaml").read_text(encoding="utf-8"))["datasets"]
        for key in args.add_footprints:
            # an area that reuses another area's snapshot (same extent) reuses its extract
            extract = next((p for p in (ROOT / "data" / "raw" / "heights" / key / f"{n}.geojson"
                                        for n in (area.name, area.snapshot)) if p.exists()), None)
            if extract is None:
                print(f"No {key} footprint extract for {area.name}: run scripts/import_height_dataset.py first.")
                return 1
            spec = specs[key]
            footprints.append((key, extract, f"{spec['name']} {spec.get('tile', '')}, {spec.get('licence', '')}"))
            variant += f"+fp_{key}"
    area_config = yaml.safe_load((ROOT / "configs" / "study_area.yaml").read_text(encoding="utf-8"))
    method_approved = bool(area_config["height_policy"].get("approved_by"))
    # the mandatory observations of the approved method (A2): the configured worklist, filtered
    # by the required priorities; the submitted file never defines what is mandatory
    required, accepted = None, None
    requirement = (area_config["areas"][area.name].get("observations") or {})
    if requirement:
        worklist_path = ROOT / requirement["worklist"]
        if not worklist_path.exists():
            print(f"The required worklist {worklist_path} is missing: run scripts/fieldwork_package.py first.")
            return 1
        with open(worklist_path, newline="", encoding="utf-8") as handle:
            listed = list(csv.DictReader(line for line in handle if not line.startswith("#")))
        # which method classes satisfy each required building (P0-P2 measured or documented,
        # the candidate survey S a storey count): configs/study_area.yaml, method_requirements
        accepted = pipeline.accepted_methods(listed, requirement)
        required = list(accepted)

    scene_dir = ROOT / "data" / "scenes" / area.name / variant
    report = pipeline.build_dataset(
        area, data, scene_dir, policy, meta["sha256"], height_model=model, seed=args.seed,
        manual_rows=rows, manual_name=args.observations.name if args.observations else "manual",
        height_datasets=datasets, extra_footprints=footprints, height_method_approved=method_approved,
        required_observations=required, accepted_observations=accepted)

    report_dir = ROOT / "outputs" / "datasets" / area.name / variant
    report_dir.mkdir(parents=True, exist_ok=True)
    for name in ("quality_report.md", "quality_report.json"):
        shutil.copyfile(scene_dir / name, report_dir / name)

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    from bns.simulation.cache import scene_fingerprint
    manifest = {
        "dataset": f"{area.name}/{variant}", "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "software_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                          cwd=ROOT).stdout.strip() or "unknown",
        "inputs": {"osm_snapshot": area.snapshot, "osm_snapshot_sha256": meta["sha256"],
                   "observations": None if not args.observations else {
                       "file": str(args.observations), "sha256": sha(args.observations)},
                   "required_observations": None if required is None else {
                       "worklist": requirement["worklist"], "sha256": sha(ROOT / requirement["worklist"]),
                       "required_priorities": requirement["required_priorities"],
                       "method_requirements": requirement.get("method_requirements"), "count": len(required)},
                   "footprint_datasets": [{"name": k, "extract": str(p.relative_to(ROOT)), "sha256": sha(p)}
                                          for k, p, _ in footprints],
                   "height_datasets": [{"name": k, "extract": str(Path(p).relative_to(ROOT)), "sha256": sha(p)}
                                       for k, p, _ in datasets]},
        "outputs": {"scene_fingerprint": scene_fingerprint(scene_dir),
                    "buildings_geojson_sha256": sha(scene_dir / "buildings.geojson"),
                    "quality_report_sha256": sha(scene_dir / "quality_report.json")},
        "height_categories": report["height_categories"]["by_count"],
        "observation_worklist": report.get("observation_worklist"),
        "fit_for_research": report["fit_for_research"], "not_fit_reasons": report["not_fit_reasons"],
        "fitness_notes": report.get("fitness_notes", [])}
    (report_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

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
