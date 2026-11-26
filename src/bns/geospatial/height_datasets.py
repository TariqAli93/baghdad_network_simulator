"""External building-height datasets: extract a study area, match it to OpenStreetMap.

The dataset's own footprints rarely coincide with OpenStreetMap's: one OSM
building may appear as one, several or part of one dataset footprint. Each OSM
building is therefore matched by area overlap, and the kind of match is kept
so that the height it receives can be judged:

    one-to-one  one dataset footprint covers the building
    split       several dataset footprints together cover the building;
                the area-weighted mean of their heights is used
    merged      a dataset footprint also covers a neighbouring OSM building
                (the dataset treats them as one block)

A dataset height is a model estimate, never a measurement (category "estimated").
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon, shape

from bns.geospatial import heights as ht
from bns.geospatial.osm_source import overlapping_pairs
from bns.geospatial.study_area import StudyArea

# An overlap is "significant" for a building when it is at least this share of the
# building's area, or at least half of the dataset footprint's own area.
_SIGNIFICANT_SHARE_OF_BUILDING = 0.1
_SIGNIFICANT_SHARE_OF_FOOTPRINT = 0.5
# A dataset footprint "merges" two OSM buildings when it covers at least this share of each.
_MERGE_SHARE = 0.25


@dataclass(frozen=True)
class ExternalFootprint:
    footprint_id: str
    polygon: Polygon | MultiPolygon        # local metres
    height_m: float


@dataclass(frozen=True)
class Match:
    building_id: str
    kind: str                       # one-to-one | split | merged
    footprint_ids: tuple[str, ...]
    height_m: float                 # area-weighted mean of the matched footprints
    max_height_m: float
    coverage: float                 # share of the building covered by matched footprints
    iou: float                      # intersection over union with the matched footprints


@dataclass(frozen=True)
class MatchResult:
    matches: list[Match]
    osm_unmatched: list[str]
    external_unmatched: list[str]
    external_duplicates: list[tuple[str, str]]


# --- extraction ---------------------------------------------------------------------


def _rings_to_geometry(points, parts) -> dict | None:
    """Shapefile rings (outer clockwise, holes counter-clockwise) -> GeoJSON geometry."""
    bounds = list(parts) + [len(points)]
    outers, holes = [], []
    for start, end in zip(bounds[:-1], bounds[1:], strict=True):
        ring = [(float(x), float(y)) for x, y in points[start:end]]
        if len(ring) < 4:
            continue
        signed = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:], strict=True))
        (holes if signed > 0 else outers).append(ring)
    if not outers:
        return None
    polygons = [[outer] for outer in outers]
    for hole in holes:
        probe = shapely.Point(hole[0])
        for rings in polygons:
            if Polygon(rings[0]).covers(probe):
                rings.append(hole)
                break
    def rounded(ring):
        return [[round(x, 7), round(y, 7)] for x, y in ring]
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": [rounded(r) for r in polygons[0]]}
    return {"type": "MultiPolygon", "coordinates": [[rounded(r) for r in p] for p in polygons]}


def extract_tile(archive: Path, bbox_deg: tuple[float, float, float, float],
                 height_field: str = "Height") -> list[dict]:
    """Features of a zipped WGS84 polygon shapefile whose bounding box meets the area.

    bbox_deg is (south, west, north, east). Each feature keeps the record number
    in the original file and the height exactly as stored.
    """
    import tempfile
    import zipfile

    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory(dir=Path(archive).parent) as tmp:
        # pyshp's own zip support breaks on member names with dots (e.g. "1590_43.75_..."),
        # so the members are unpacked to a temporary folder first.
        shp = [n for n in z.namelist() if n.lower().endswith(".shp")]
        if len(shp) != 1:
            raise ValueError(f"{archive} must contain exactly one .shp file.")
        stem = shp[0][:-4]
        for ext in (".shp", ".shx", ".dbf"):
            z.extract(stem + ext, tmp)
        return _read_shapefile(Path(tmp) / f"{stem}.shp", bbox_deg, height_field)


def _read_shapefile(path: Path, bbox_deg, height_field: str) -> list[dict]:
    import shapefile

    south, west, north, east = bbox_deg
    features = []
    with open(path, "rb") as shp, open(path.with_suffix(".shx"), "rb") as shx, \
            open(path.with_suffix(".dbf"), "rb") as dbf, \
            shapefile.Reader(shp=shp, shx=shx, dbf=dbf) as reader:
        names = [f[0] for f in reader.fields[1:]]
        column = names.index(height_field)
        for index, item in enumerate(reader.iterShapeRecords(bbox=[west, south, east, north])):
            geometry = _rings_to_geometry(item.shape.points, item.shape.parts)
            if geometry is None:
                continue
            record = getattr(item.record, "oid", index)
            features.append({"type": "Feature", "geometry": geometry,
                             "properties": {"record": int(record),
                                            "height_m": float(item.record[column])}})
    return features


def write_extract(features: list[dict], path: Path, metadata: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "metadata": metadata,
                                "features": features}), encoding="utf-8")


def load_extract(path: Path, area: StudyArea) -> list[ExternalFootprint]:
    """Read a stored extract into local metres."""
    forward = area.transformer()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    footprints = []
    for feature in data["features"]:
        geometry = shape(feature["geometry"])
        local = shapely.transform(geometry, lambda xy: np.column_stack(forward.transform(xy[:, 0], xy[:, 1])))
        footprints.append(ExternalFootprint(f"rec/{feature['properties']['record']}",
                                            shapely.make_valid(local),
                                            float(feature["properties"]["height_m"])))
    return footprints


# --- matching -----------------------------------------------------------------------


def match_footprints(buildings: list[ht.Building], external: list[ExternalFootprint],
                     min_coverage: float) -> MatchResult:
    """Match each OSM building to the dataset footprints that cover it.

    A building is matched when significant dataset footprints cover at least
    `min_coverage` of its area.
    """
    ext_polys = [shapely.make_valid(e.polygon) for e in external]
    tree = shapely.STRtree(ext_polys) if ext_polys else None
    overlaps: dict[int, list[tuple[int, float]]] = {}       # building -> [(ext index, area)]
    owners: dict[int, list[tuple[int, float]]] = {}         # ext -> [(building index, share)]
    polys = [shapely.make_valid(b.polygon) for b in buildings]
    for bi, poly in enumerate(polys):
        if tree is None:
            break
        for ei in tree.query(poly, predicate="intersects"):
            area = poly.intersection(ext_polys[ei]).area
            if area <= 0:
                continue
            significant = (area >= _SIGNIFICANT_SHARE_OF_BUILDING * poly.area
                           or area >= _SIGNIFICANT_SHARE_OF_FOOTPRINT * ext_polys[ei].area)
            if significant:
                overlaps.setdefault(bi, []).append((int(ei), area))
                owners.setdefault(int(ei), []).append((bi, area / poly.area))

    matches, unmatched, used = [], [], set()
    for bi, building in enumerate(buildings):
        parts = overlaps.get(bi, [])
        coverage = min(1.0, sum(a for _, a in parts) / polys[bi].area) if parts else 0.0
        if coverage < min_coverage:
            unmatched.append(building.building_id)
            continue
        merged = any(sum(1 for _, share in owners[ei] if share >= _MERGE_SHARE) > 1 for ei, _ in parts)
        kind = "merged" if merged else ("one-to-one" if len(parts) == 1 else "split")
        weights = np.array([a for _, a in parts])
        heights = np.array([external[ei].height_m for ei, _ in parts])
        union = shapely.union_all([ext_polys[ei] for ei, _ in parts])
        iou = polys[bi].intersection(union).area / polys[bi].union(union).area
        matches.append(Match(building.building_id, kind,
                             tuple(external[ei].footprint_id for ei, _ in parts),
                             float(np.average(heights, weights=weights)), float(heights.max()),
                             float(coverage), float(iou)))
        used.update(ei for ei, _ in parts)

    return MatchResult(
        matches, unmatched,
        [e.footprint_id for ei, e in enumerate(external) if ei not in used],
        overlapping_pairs([e.footprint_id for e in external], ext_polys, 0.9))


def height_record(match: Match, dataset: str, reference: str) -> ht.HeightRecord:
    """The dataset height of a matched building, as an estimate with its provenance."""
    method = (f"{dataset} model height; {match.kind} footprint match covering "
              f"{100 * match.coverage:.0f} % of the OSM footprint (IoU {match.iou:.2f}); "
              f"area-weighted mean of {len(match.footprint_ids)} footprint(s)")
    return ht.HeightRecord(match.height_m, ht.ESTIMATED, f"dataset:{dataset}", method,
                           f"{reference}; {', '.join(match.footprint_ids)}",
                           {"dataset_height_m": match.height_m,
                            "dataset_max_height_m": match.max_height_m})


# --- missing footprints (decision A2) -------------------------------------------------


def missing_footprints(buildings: list[ht.Building], external: list[ExternalFootprint], clip_box,
                       min_area_m2: float) -> list[ExternalFootprint]:
    """External footprints that touch no OSM building at all, inside the clip box.

    Only footprints with no overlap are taken: a partial overlap is a geometry mismatch or a
    merged block, not a missing building (docs/building-height-data.md, section 9).
    """
    tree = shapely.STRtree([b.polygon for b in buildings])
    out = []
    for e in external:
        if e.polygon.area < min_area_m2 or not clip_box.contains(e.polygon.representative_point()):
            continue
        if len(tree.query(e.polygon, predicate="intersects")) == 0:
            out.append(e)
    return out


def footprint_buildings(missing: list[ExternalFootprint], dataset: str, reference: str,
                        policy: ht.HeightPolicy) -> list[ht.Building]:
    """Buildings for missing footprints: footprint provenance kept, height an explicit placeholder.

    The dataset's own height is NOT used (A2: rejected as a height source); it is kept only
    as an untouched original value for reference.
    """
    out = []
    for e in missing:
        record = ht.HeightRecord(policy.placeholder_height_m, ht.PLACEHOLDER, "placeholder",
                                 f"no height information; footprint added from {dataset} (missing in OSM)",
                                 f"{reference}; {e.footprint_id}", {"dataset_height_m_not_used": e.height_m})
        out.append(ht.Building(f"{dataset}/{e.footprint_id}", e.polygon,
                               {"footprint_source": f"dataset:{dataset}", "footprint_reference": reference},
                               record))
    return out
