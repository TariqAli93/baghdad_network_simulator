"""Turn OpenStreetMap building footprints into a ray-tracing scene.

Pipeline: Overpass JSON -> local metric coordinates -> cleaned footprints with
a recorded height source -> extruded triangle meshes -> PLY + Mitsuba XML.

Mesh conventions (required by Sionna RT's diffraction, see docs/architecture.md):
  * walls and roof of a building share vertices, so their common edges are wedges;
  * there are no bottom faces: walls start below ground level, which avoids a
    false wedge along every footprint segment;
  * coordinates are metres, z up, origin at the centre of the study box.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import mapbox_earcut
import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from bns.geospatial.grid import footprint_mask
from bns.geospatial.heights import (ESTIMATED, OBSERVED, PLACEHOLDER, HeightPolicy,
                                    height_from_osm_tags)
from bns.geospatial.study_area import local_transformer  # noqa: F401  (used by Phase 0 scripts)

HEIGHT_FROM_TAG = "tag:height"
HEIGHT_FROM_LEVELS = "tag:building:levels"
HEIGHT_ASSUMED = "assumed"


@dataclass(frozen=True)
class SceneSettings:
    """Geometry assumptions. Every value here is recorded in scene_meta.json."""

    storey_height_m: float = 3.0       # used when only building:levels is tagged
    default_height_m: float = 9.0      # placeholder for untagged buildings (NOT approved)
    max_plausible_height_m: float = 250.0
    simplify_tolerance_m: float = 0.3
    min_area_m2: float = 4.0
    wall_sink_m: float = 0.5           # walls start this far below the ground plane
    ground_margin_m: float = 50.0
    material: str = "concrete"         # ITU-R P.2040 material for walls, roofs and ground
    wall_thickness_m: float = 0.2
    ground_thickness_m: float = 1.0


@dataclass
class Building:
    polygon: Polygon          # local metres
    height_m: float
    height_source: str
    osm_ids: tuple[int, ...]


# --- Reading OSM ------------------------------------------------------------------


_LABELS = {OBSERVED: HEIGHT_FROM_TAG, ESTIMATED: HEIGHT_FROM_LEVELS, PLACEHOLDER: HEIGHT_ASSUMED}


def resolve_height(tags: dict, settings: SceneSettings) -> tuple[float, str, str | None]:
    """Height, its source label, and any warning (Phase 0 form of heights.height_from_osm_tags)."""
    policy = HeightPolicy(settings.storey_height_m, settings.default_height_m,
                          settings.max_plausible_height_m)
    record = height_from_osm_tags(tags, policy, building_id="")
    return record.height_m, _LABELS[record.category], "; ".join(record.warnings) or None


def read_overpass_buildings(overpass_json: dict, transformer: Transformer,
                            settings: SceneSettings) -> tuple[list[Building], dict]:
    """Building ways from an Overpass `out tags geom` response, in local metres.

    This is the Phase 0 reader, kept so the Phase 0 experiments stay reproducible.
    It skips multipolygon relations. New code uses bns.geospatial.osm_source and
    bns.geospatial.pipeline instead.
    """
    buildings, warnings, skipped = [], [], Counter()
    for element in overpass_json.get("elements", []):
        tags = element.get("tags", {})
        if "building" not in tags:
            continue
        if element.get("type") != "way":
            skipped["non-way element (relation)"] += 1
            continue
        geometry = element.get("geometry", [])
        if len(geometry) < 4:
            skipped["fewer than 3 distinct nodes"] += 1
            continue
        xs, ys = transformer.transform([p["lon"] for p in geometry], [p["lat"] for p in geometry])
        polygon = Polygon(zip(xs, ys))
        height, source, warning = resolve_height(tags, settings)
        if warning:
            warnings.append({"osm_id": element["id"], "warning": warning})
        buildings.append(Building(polygon, height, source, (element["id"],)))
    return buildings, {"height_warnings": warnings, "skipped": dict(skipped)}


# --- Footprint cleaning -----------------------------------------------------------


def _polygons_of(geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if hasattr(geometry, "geoms"):
        return [g for part in geometry.geoms for g in _polygons_of(part)]
    return []


def _tidy(polygon: Polygon, settings: SceneSettings) -> list[Polygon]:
    """Simplify one footprint and remove holes too small or too thin to matter.

    Merging neighbouring footprints leaves hair-thin gaps where their outlines
    do not quite coincide. As holes they would become degenerate triangles and
    false diffraction wedges, so holes below the minimum area or narrower than
    about half a metre are filled.
    """
    polygon = polygon.simplify(settings.simplify_tolerance_m, preserve_topology=True)
    holes = [ring for ring in polygon.interiors
             if Polygon(ring).area >= settings.min_area_m2
             and Polygon(ring).area / ring.length >= 0.25]
    polygon = shapely.set_precision(Polygon(polygon.exterior, holes), 0.01)
    return [orient(p, sign=1.0) for p in _polygons_of(shapely.make_valid(polygon))
            if p.area >= settings.min_area_m2]


def clean_footprints(buildings: list[Building], settings: SceneSettings,
                     clip_box: Polygon | None = None) -> tuple[list[Building], dict]:
    """Repair, simplify and de-overlap footprints.

    * invalid rings are repaired, tiny pieces dropped;
    * where footprints overlap, the taller building keeps the shared area;
    * footprints of equal height that touch are merged into one solid, which
      removes the coincident party walls between them.
    """
    separated, stats = separate_footprints(buildings, settings, clip_box)
    merged, merge_stats = merge_solids(separated, settings)
    return merged, {**stats, **merge_stats}


def separate_footprints(buildings: list[Building], settings: SceneSettings,
                        clip_box: Polygon | None = None) -> tuple[list[Building], dict]:
    """Repair, clip and de-overlap footprints, keeping one piece per source building.

    The result still has one entry per original building (or per piece, if
    clipping or an overlap split it), so per-building information stays attached.
    """
    stats = Counter()
    repaired = []
    for b in buildings:
        geometry = shapely.make_valid(b.polygon)
        if clip_box is not None:
            geometry = geometry.intersection(clip_box)
        for polygon in _polygons_of(geometry):
            polygon = polygon.simplify(settings.simplify_tolerance_m, preserve_topology=True)
            if polygon.area < settings.min_area_m2:
                stats["dropped_small"] += 1
                continue
            repaired.append(Building(polygon, b.height_m, b.height_source, b.osm_ids))

    # Taller buildings claim overlapping ground first.
    repaired.sort(key=lambda b: -b.height_m)
    claimed, separated = None, []
    for b in repaired:
        geometry = b.polygon if claimed is None else b.polygon.difference(claimed)
        if geometry.area < b.polygon.area - 1e-6:
            stats["overlaps_resolved"] += 1
        for polygon in _polygons_of(geometry):
            if polygon.area >= settings.min_area_m2:
                separated.append(Building(polygon, b.height_m, b.height_source, b.osm_ids))
        claimed = b.polygon if claimed is None else claimed.union(b.polygon)
    return separated, dict(stats)


def merge_solids(separated: list[Building], settings: SceneSettings) -> tuple[list[Building], dict]:
    """Merge touching footprints of equal height and equal height source into solids."""
    stats = Counter()
    groups: dict[tuple[float, str], list[Building]] = {}
    for b in separated:
        groups.setdefault((round(b.height_m, 1), b.height_source), []).append(b)
    merged = []
    for (height, source), members in groups.items():
        union = unary_union([m.polygon for m in members])
        for part in _polygons_of(union):
            for polygon in _tidy(part, settings):
                ids = tuple(i for m in members if m.polygon.intersects(polygon) for i in m.osm_ids)
                merged.append(Building(polygon, height, source, ids))
    stats["footprints_before_merge"] = len(separated)
    stats["solids_after_merge"] = len(merged)

    # Different-height neighbours still share a wall; count them, they are a known artefact.
    if not merged:
        return merged, dict(stats)
    tree = shapely.STRtree([b.polygon for b in merged])
    contacts = 0
    for i, j in zip(*tree.query([b.polygon for b in merged], predicate="touches")):
        if i < j and merged[i].polygon.intersection(merged[j].polygon).length > 0.5:
            contacts += 1
    stats["different_height_contacts"] = contacts
    return merged, dict(stats)


# --- Meshing ----------------------------------------------------------------------


def _open_ring(coords) -> np.ndarray:
    ring = np.asarray(coords, dtype=np.float64)[:, :2]
    return ring[:-1] if np.allclose(ring[0], ring[-1]) else ring


def extrude(polygon: Polygon, height_m: float, sink_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Walls and roof of one building as an indexed triangle mesh (no bottom face).

    Each ring contributes one bottom and one top copy of its vertices; walls and
    roof index the same top vertices, so roof-wall edges and vertical corners
    are shared by exactly two triangles.
    """
    polygon = orient(polygon, sign=1.0)  # exterior counter-clockwise, holes clockwise
    rings = [_open_ring(polygon.exterior.coords)] + [_open_ring(r.coords) for r in polygon.interiors]
    flat = np.vstack(rings)
    n = len(flat)
    bottom = np.column_stack([flat, np.full(n, -sink_m)])
    top = np.column_stack([flat, np.full(n, height_m)])
    vertices = np.vstack([bottom, top])

    faces = []
    start = 0
    for ring in rings:
        m = len(ring)
        for i in range(m):
            a, b = start + i, start + (i + 1) % m
            faces.append((a, b, b + n))      # outward normal for a CCW exterior ring
            faces.append((a, b + n, a + n))
        start += m

    ring_ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    roof = mapbox_earcut.triangulate_float64(flat, ring_ends).reshape(-1, 3)
    for tri in roof:
        p, q, r = flat[tri]
        area2 = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        i, j, k = (int(v) + n for v in tri)
        faces.append((i, j, k) if area2 > 0 else (i, k, j))   # roof normal points up
    return vertices, np.asarray(faces, dtype=np.int32)


def merge_meshes(parts: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    vertices, faces, offset = [], [], 0
    for v, f in parts:
        vertices.append(v)
        faces.append(f + offset)
        offset += len(v)
    if not vertices:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int32)
    return np.vstack(vertices), np.vstack(faces)


def ground_quad(half_x: float, half_y: float) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.array([[-half_x, -half_y, 0.0], [half_x, -half_y, 0.0],
                         [half_x, half_y, 0.0], [-half_x, half_y, 0.0]])
    return vertices, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)


def mesh_report(vertices: np.ndarray, faces: np.ndarray, flat_tolerance_deg: float = 1.0) -> dict:
    """Topology facts the diffraction solver depends on.

    A wedge is an edge shared by exactly two non-coplanar triangles; a rim edge
    belongs to one triangle (the open bottom of the walls); anything shared by
    more than two triangles is a meshing error.
    """
    v = vertices[faces]
    normals = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    degenerate = int(np.sum(lengths < 1e-9))
    normals = normals / np.where(lengths[:, None] < 1e-12, 1.0, lengths[:, None])

    edges = np.sort(np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    face_of_edge = np.tile(np.arange(len(faces)), 3)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges, face_of_edge = edges[order], face_of_edge[order]
    _, first, counts = np.unique(edges, axis=0, return_index=True, return_counts=True)

    paired = first[counts == 2]
    cos_angle = np.einsum("ij,ij->i", normals[face_of_edge[paired]], normals[face_of_edge[paired + 1]])
    wedges = int(np.sum(cos_angle < math.cos(math.radians(flat_tolerance_deg))))
    return {
        "vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "degenerate_triangles": degenerate,
        "rim_edges": int(np.sum(counts == 1)),
        "wedges": wedges,
        "flat_shared_edges": int(len(paired) - wedges),
        "non_manifold_edges": int(np.sum(counts > 2)),
        "roof_triangles_facing_down": int(np.sum((np.abs(normals[:, 2]) > 0.5) & (normals[:, 2] < 0))),
    }


# --- Writing ----------------------------------------------------------------------


def write_ply(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Binary little-endian PLY, float32 positions, no normals (flat shading)."""
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(vertices)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\n"
        "property list uchar int vertex_indices\nend_header\n"
    )
    face_records = np.empty(len(faces), dtype=[("n", "u1"), ("idx", "<i4", 3)])
    face_records["n"] = 3
    face_records["idx"] = faces
    with open(path, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(np.asarray(vertices, dtype="<f4").tobytes())
        handle.write(face_records.tobytes())


def scene_xml(settings: SceneSettings, with_buildings: bool, with_ground: bool) -> str:
    def material(name: str, thickness: float) -> str:
        return (f'  <bsdf type="itu-radio-material" id="{name}">\n'
                f'    <string name="type" value="{settings.material}"/>\n'
                f'    <float name="thickness" value="{thickness}"/>\n'
                "  </bsdf>\n")

    def shape(name: str, material_id: str) -> str:
        return (f'  <shape type="ply" id="mesh-{name}">\n'
                f'    <string name="filename" value="meshes/{name}.ply"/>\n'
                '    <boolean name="face_normals" value="true"/>\n'
                f'    <ref id="{material_id}" name="bsdf"/>\n'
                "  </shape>\n")

    # Sionna strips the "mesh-" prefix from shape ids and requires object and
    # material names to be unique together, hence the "-material" suffix.
    xml = '<scene version="2.1.0">\n'
    if with_buildings:
        xml += material("buildings-material", settings.wall_thickness_m)
        xml += shape("buildings", "buildings-material")
    if with_ground:
        xml += material("ground-material", settings.ground_thickness_m)
        xml += shape("ground", "ground-material")
    return xml + "</scene>\n"


def write_scene(out_dir: Path, buildings: list[Building], settings: SceneSettings,
                half_extent_m: tuple[float, float], with_ground: bool = True,
                extra_meta: dict | None = None) -> dict:
    """Write meshes, scene.xml, footprints and scene_meta.json; return the metadata."""
    out_dir = Path(out_dir)
    (out_dir / "meshes").mkdir(parents=True, exist_ok=True)
    vertices, faces = merge_meshes(
        [extrude(b.polygon, b.height_m, settings.wall_sink_m) for b in buildings])
    report = mesh_report(vertices, faces) if len(faces) else {}
    if buildings:
        write_ply(out_dir / "meshes" / "buildings.ply", vertices, faces)
    if with_ground:
        gx = half_extent_m[0] + settings.ground_margin_m
        gy = half_extent_m[1] + settings.ground_margin_m
        write_ply(out_dir / "meshes" / "ground.ply", *ground_quad(gx, gy))
    (out_dir / "scene.xml").write_text(
        scene_xml(settings, bool(buildings), with_ground), encoding="utf-8")

    footprints = [{
        "height_m": b.height_m,
        "height_source": b.height_source,
        "osm_ids": list(b.osm_ids),
        "exterior": np.round(np.asarray(b.polygon.exterior.coords), 3).tolist(),
        "interiors": [np.round(np.asarray(r.coords), 3).tolist() for r in b.polygon.interiors],
    } for b in buildings]
    (out_dir / "footprints.json").write_text(json.dumps(footprints), encoding="utf-8")

    sources = Counter(b.height_source for b in buildings)
    heights = [b.height_m for b in buildings]
    meta = {
        "settings": settings.__dict__,
        "half_extent_m": list(half_extent_m),
        "buildings": len(buildings),
        "height_sources": dict(sources),
        "height_min_max_m": [min(heights), max(heights)] if heights else None,
        "footprint_area_m2": float(sum(b.polygon.area for b in buildings)),
        "mesh": report,
        **(extra_meta or {}),
    }
    (out_dir / "scene_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_footprints(scene_dir: Path) -> list[Building]:
    data = json.loads((Path(scene_dir) / "footprints.json").read_text(encoding="utf-8"))
    return [Building(Polygon(f["exterior"], f["interiors"]), f["height_m"],
                     f["height_source"], tuple(f["osm_ids"])) for f in data]


def rooftop_site(buildings: list[Building], mast_height_m: float,
                 within_m: float) -> tuple[tuple[float, float, float], Building]:
    """Antenna position on the tallest building within `within_m` of the origin."""
    origin = shapely.Point(0.0, 0.0)
    near = [b for b in buildings if b.polygon.representative_point().distance(origin) < within_m]
    if not near:
        raise ValueError(f"No building within {within_m} m of the centre.")
    host = max(near, key=lambda b: b.height_m)
    spot = host.polygon.representative_point()
    return (float(spot.x), float(spot.y), host.height_m + mast_height_m), host


# --- Receiver grid helpers --------------------------------------------------------


def indoor_mask(buildings: list[Building], x_centers, y_centers, cell_size_m: float) -> np.ndarray:
    """True for every grid cell that touches a building footprint.

    Shape [len(y_centers), len(x_centers)], matching the radio-map arrays.
    """
    return footprint_mask(x_centers, y_centers, cell_size_m, [b.polygon for b in buildings])
