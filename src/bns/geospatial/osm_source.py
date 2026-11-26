"""OpenStreetMap buildings: download once, store with a hash, parse into polygons.

A snapshot is the raw Overpass response saved next to a small metadata file
with its SHA-256. Every later run reads the snapshot, never the network, so
the building data behind a result can always be identified.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, polygonize, unary_union

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
LICENCE = "OpenStreetMap contributors, ODbL 1.0"


@dataclass(frozen=True)
class OsmBuilding:
    building_id: str        # "way/<id>" or "relation/<id>" (with "#n" for extra parts)
    polygon: Polygon        # local metres
    tags: dict


# --- snapshots ----------------------------------------------------------------------


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    # "out geom" (not "out tags geom") is required: only the full output carries the member
    # ways of multipolygon relations together with their coordinates.
    south, west, north, east = bbox
    return (f"[out:json][timeout:120][bbox:{south:.6f},{west:.6f},{north:.6f},{east:.6f}];"
            '(way["building"];relation["building"];);out geom;')


def fetch_snapshot(raw_dir: Path, name: str, bbox, area_info: dict | None = None,
                   replace: bool = False) -> dict:
    """Download the buildings of a bounding box and store them with their hash.

    An existing snapshot is never overwritten unless replace=True: snapshots are
    the record of the data behind earlier results.
    """
    if (Path(raw_dir) / f"{name}.json").exists() and not replace:
        raise FileExistsError(
            f"Snapshot '{name}' already exists in {raw_dir}. Use a new snapshot name "
            "(configs/study_area.yaml) or replace it explicitly.")
    query = overpass_query(bbox)
    body = urllib.parse.urlencode({"data": query}).encode()
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            request = urllib.request.Request(endpoint, data=body,
                                             headers={"User-Agent": "bns-dataset-builder/0.2"})
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read()
            json.loads(raw)                    # must be valid JSON before it is stored
            break
        except Exception as error:             # try the next mirror
            last_error = error
    else:
        raise RuntimeError(f"All Overpass endpoints failed: {last_error}")
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{name}.json").write_bytes(raw)
    meta = {"area": area_info or {"name": name},
            "bbox_south_west_north_east": list(bbox), "query": query, "endpoint": endpoint,
            "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(raw).hexdigest(), "licence": LICENCE}
    (raw_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_snapshot(raw_dir: Path, name: str) -> tuple[dict, dict]:
    """Read a stored snapshot and check it against its recorded hash."""
    data_path = Path(raw_dir) / f"{name}.json"
    meta_path = Path(raw_dir) / f"{name}.meta.json"
    if not data_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"No OpenStreetMap snapshot for '{name}' in {raw_dir}. "
            "Run scripts/build_dataset.py with --fetch to download one.")
    raw = data_path.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError(f"Snapshot {data_path.name} does not match its recorded SHA-256.")
    return json.loads(raw), meta


# --- parsing ------------------------------------------------------------------------


def _project(geometry: list[dict], transformer: Transformer) -> list[tuple[float, float]]:
    xs, ys = transformer.transform([p["lon"] for p in geometry], [p["lat"] for p in geometry])
    return list(zip(xs, ys))


def _polygons(geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [p for part in getattr(geometry, "geoms", []) for p in _polygons(part)]


def _rings_to_area(members: list[dict], roles: tuple[str, ...], transformer: Transformer):
    lines = [LineString(_project(m["geometry"], transformer)) for m in members
             if m.get("type") == "way" and m.get("role", "") in roles
             and len(m.get("geometry", [])) >= 2]
    if not lines:
        return None
    merged = linemerge(lines) if len(lines) > 1 else lines[0]
    polygons = list(polygonize(merged))
    return unary_union(polygons) if polygons else None


def parse_buildings(overpass_json: dict, transformer: Transformer) -> tuple[list[OsmBuilding], dict]:
    """Buildings mapped as closed ways or as multipolygon relations, in local metres.

    Anything that cannot be turned into a polygon is counted under "skipped"
    with the reason, never dropped silently.
    """
    buildings: list[OsmBuilding] = []
    skipped: Counter = Counter()
    relations = 0
    relations_missing_members = 0
    for element in overpass_json.get("elements", []):
        tags = element.get("tags", {})
        if "building" not in tags:
            continue
        kind, osm_id = element.get("type"), element.get("id")
        if kind == "way":
            points = _project(element.get("geometry", []), transformer)
            if len(points) < 4 or points[0] != points[-1]:
                skipped["way is not a closed ring"] += 1
                continue
            polygon = Polygon(points)
            if polygon.area <= 0:
                skipped["way with zero area"] += 1
                continue
            buildings.append(OsmBuilding(f"way/{osm_id}", polygon, tags))
        elif kind == "relation":
            members = element.get("members", [])
            if not any("geometry" in m for m in members):
                skipped["relation stored without member geometry"] += 1
                continue
            if any(m.get("type") == "way" and "geometry" not in m for m in members):
                relations_missing_members += 1
            outer = _rings_to_area(members, ("outer", ""), transformer)
            if outer is None:
                skipped["relation without a closed outer ring"] += 1
                continue
            inner = _rings_to_area(members, ("inner",), transformer)
            parts = _polygons(outer if inner is None else outer.difference(inner))
            if not parts:
                skipped["relation with zero area"] += 1
                continue
            relations += 1
            for index, polygon in enumerate(parts):
                suffix = "" if len(parts) == 1 else f"#{index + 1}"
                buildings.append(OsmBuilding(f"relation/{osm_id}{suffix}", polygon, tags))
        else:
            skipped[f"unsupported element type {kind}"] += 1
    report = {"buildings_read": len(buildings), "relations_read": relations,
              "relations_with_missing_members": relations_missing_members,
              "skipped": dict(skipped)}
    return buildings, report


def find_duplicates(buildings: list[OsmBuilding], min_overlap: float = 0.9) -> list[tuple[str, str]]:
    """Pairs of buildings whose footprints overlap by at least `min_overlap` of the smaller one.

    Such pairs are usually the same building mapped twice. They are reported,
    not removed: the footprint cleaner later gives overlapping ground to the
    taller of the two.
    """
    return overlapping_pairs([b.building_id for b in buildings], [b.polygon for b in buildings],
                             min_overlap)


def overlapping_pairs(ids: list[str], polygons, min_overlap: float) -> list[tuple[str, str]]:
    """Id pairs whose shapes overlap by at least `min_overlap` of the smaller area."""
    import shapely

    polygons = [shapely.make_valid(p) for p in polygons]
    if not polygons:
        return []
    tree = shapely.STRtree(polygons)
    pairs = []
    for i, j in zip(*tree.query(polygons, predicate="intersects"), strict=True):
        if i >= j:
            continue
        smaller = min(polygons[i].area, polygons[j].area)
        if smaller > 0 and polygons[i].intersection(polygons[j]).area >= min_overlap * smaller:
            pairs.append(tuple(sorted((ids[i], ids[j]))))
    return sorted(pairs)
