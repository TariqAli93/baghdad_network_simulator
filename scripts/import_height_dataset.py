"""Extract a study area from a cached building-height dataset and store it with a manifest.

    uv run python scripts/import_height_dataset.py --dataset 3d_globfp --area tahrir_bab_al_sharqi_v2

The original file must be in data/cache/datasets/<dataset>/ (download it from the URL in
configs/height_datasets.yaml; its MD5 and SHA-256 are checked before use). The extract and
a manifest are written to data/raw/heights/<dataset>/<area>.geojson and .manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from bns.geospatial import height_datasets as hd
from bns.geospatial.study_area import load_study_areas

ROOT = Path(__file__).resolve().parents[1]


def file_hashes(path: Path) -> tuple[str, str]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            md5.update(block)
            sha.update(block)
    return md5.hexdigest(), sha.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--area", required=True)
    args = parser.parse_args()

    spec = yaml.safe_load((ROOT / "configs" / "height_datasets.yaml").read_text(encoding="utf-8"))
    spec = spec["datasets"][args.dataset]
    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    archive = ROOT / "data" / "cache" / "datasets" / args.dataset / spec["file"]
    if not archive.exists():
        print(f"Missing {archive}. Download {spec['url']} ({spec['size_bytes']:,} bytes) there first.")
        return 1
    md5, sha = file_hashes(archive)
    if (md5, sha) != (spec["md5"], spec["sha256"]):
        print(f"Checksum mismatch for {archive.name}: md5 {md5}, sha256 {sha}.")
        return 1

    bbox = area.bbox_degrees()
    features = hd.extract_tile(archive, bbox, spec["height_field"])
    out = ROOT / "data" / "raw" / "heights" / args.dataset / f"{area.name}.geojson"
    metadata = {
        "dataset": spec["name"], "version": spec["version"], "doi": spec["doi"],
        "licence": spec["licence"], "citation": " ".join(spec["citation"].split()),
        "source_file": spec["file"], "source_md5": md5, "source_sha256": sha,
        "bbox_south_west_north_east": list(bbox), "area": area.name,
        "features": len(features),
        "extracted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Extract of a model-estimated dataset; heights are estimates, not measurements.",
    }
    hd.write_extract(features, out, metadata)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {**metadata, "extract_file": out.name, "extract_sha256": digest}
    out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"{len(features)} footprints from {spec['name']} -> {out} (sha256 {digest[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
