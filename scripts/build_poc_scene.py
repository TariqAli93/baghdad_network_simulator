"""Download the proof-of-concept study box once and build its ray-tracing scenes.

    uv run python scripts/build_poc_scene.py            (reuses the saved OSM snapshot)
    uv run python scripts/build_poc_scene.py --refetch  (downloads a new snapshot)

The raw OpenStreetMap response is stored under data/raw/osm/ with its SHA-256,
so every later run uses exactly the same building data.

Two scenes are written to data/scenes/:
    poc_full   all buildings of the 1.3 km box (1 km receiver area + 150 m margin)
    poc_crop   only the buildings within 350 m of the box centre
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import box

from bns.geospatial import osm_scene as osm
from bns.runtime import PROJECT_ROOT

# Provisional proof-of-concept area: Tahrir Square / Bab Al-Sharqi, Baghdad.
# The study district itself is chosen in Phase 2 with the supervisor.
AREA = {"name": "tahrir_bab_al_sharqi", "lat": 33.3280, "lon": 44.4085}
FULL_HALF_M = 650.0
CROP_HALF_M = 350.0

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "osm"
SCENES = PROJECT_ROOT / "data" / "scenes"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def bbox_degrees(lat: float, lon: float, half_m: float) -> tuple[float, float, float, float]:
    """South, west, north, east of a square box, slightly padded."""
    inverse = osm.local_transformer(lat, lon)
    west, south = inverse.transform(-half_m - 20, -half_m - 20, direction="INVERSE")
    east, north = inverse.transform(half_m + 20, half_m + 20, direction="INVERSE")
    return south, west, north, east


def fetch(snapshot: Path) -> None:
    south, west, north, east = bbox_degrees(AREA["lat"], AREA["lon"], FULL_HALF_M)
    query = (f"[out:json][timeout:120][bbox:{south:.6f},{west:.6f},{north:.6f},{east:.6f}];"
             '(way["building"];relation["building"];);out tags geom;')
    body = urllib.parse.urlencode({"data": query}).encode()
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            request = urllib.request.Request(endpoint, data=body,
                                             headers={"User-Agent": "bns-poc-scene/0.1"})
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read()
            json.loads(raw)   # must be valid JSON before it is saved
            break
        except Exception as error:   # try the next mirror
            last_error = error
    else:
        raise RuntimeError(f"All Overpass endpoints failed: {last_error}")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(raw)
    meta = {"area": AREA, "bbox_south_west_north_east": [south, west, north, east],
            "query": query, "endpoint": endpoint,
            "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "licence": "OpenStreetMap contributors, ODbL 1.0"}
    snapshot.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refetch", action="store_true")
    args = parser.parse_args()

    snapshot = RAW_DIR / f"{AREA['name']}.json"
    if args.refetch or not snapshot.exists():
        fetch(snapshot)
    raw = snapshot.read_bytes()
    source = json.loads(snapshot.with_suffix(".meta.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != source["sha256"]:
        raise RuntimeError("OSM snapshot does not match its recorded SHA-256.")

    settings = osm.SceneSettings()
    transformer = osm.local_transformer(AREA["lat"], AREA["lon"])
    buildings, read_report = osm.read_overpass_buildings(json.loads(raw), transformer, settings)
    print(f"OSM snapshot {snapshot.name}: {len(buildings)} building ways, "
          f"{len(read_report['height_warnings'])} height warnings, skipped {read_report['skipped']}")

    for name, half in (("poc_full", FULL_HALF_M), ("poc_crop", CROP_HALF_M)):
        clip = box(-half, -half, half, half)
        cleaned, clean_report = osm.clean_footprints(buildings, settings, clip_box=clip)
        meta = osm.write_scene(
            SCENES / name, cleaned, settings, (half, half),
            extra_meta={"area": AREA, "osm_snapshot_sha256": digest,
                        "osm_fetched_utc": source["fetched_utc"],
                        "read_report": read_report, "clean_report": clean_report})
        mesh = meta["mesh"]
        print(f"{name}: {meta['buildings']} solids, heights {meta['height_sources']}, "
              f"range {meta['height_min_max_m']} m, {mesh['triangles']} triangles, "
              f"{mesh['wedges']} wedges, {mesh['non_manifold_edges']} non-manifold edges, "
              f"{clean_report.get('different_height_contacts', 0)} different-height contacts")
        if mesh["non_manifold_edges"] or mesh["degenerate_triangles"] or mesh["roof_triangles_facing_down"]:
            print(f"  WARNING: mesh quality problems in {name}: {mesh}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
