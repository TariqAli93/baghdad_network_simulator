"""Build a ray-tracing dataset for a study area.

    OSM snapshot -> buildings with height provenance -> repaired footprints
    -> 3D scene for Sionna RT + per-building table + quality report

The same function serves the development fixture and, later, the study
district; nothing in it is specific to one place.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from bns.geospatial import heights as ht
from bns.geospatial import osm_scene, osm_source, quality
from bns.geospatial.study_area import StudyArea


def provenance_buildings(area: StudyArea, overpass_json: dict, policy: ht.HeightPolicy,
                         snapshot_sha256: str, *, height_model: ht.HeightModel | None = None,
                         seed: int | None = None, manual_rows: list[dict] | None = None,
                         manual_name: str = "manual", scene_settings=None
                         ) -> tuple[list[ht.Building], dict, dict]:
    """Parse, attach height records, then repair, clip and de-overlap the footprints.

    Returns the per-building table (one entry per building piece), the parse
    report and the cleaning report.
    """
    settings = scene_settings or osm_scene.SceneSettings()
    raw, parse_report = osm_source.parse_buildings(overpass_json, area.transformer())
    buildings = [ht.Building(b.building_id, b.polygon, b.tags,
                             ht.height_from_osm_tags(b.tags, policy, b.building_id, snapshot_sha256))
                 for b in raw]
    clean_report: dict = {}
    if manual_rows:
        buildings, unmatched = ht.apply_manual_observations(buildings, manual_rows, manual_name)
        clean_report["manual_observations_without_building"] = unmatched
    if height_model is not None:
        if seed is None:
            raise ValueError("A height model needs an explicit seed.")
        buildings = ht.apply_height_model(buildings, height_model, seed)

    # The footprint cleaner works on plain (polygon, height) items; the building id
    # travels through it so each cleaned piece finds its record again.
    by_id = {b.building_id: b for b in buildings}
    plain = [osm_scene.Building(b.polygon, b.height.height_m, b.height.category, (b.building_id,))
             for b in buildings]
    pieces, separate_report = osm_scene.separate_footprints(plain, settings, area.clip_box())
    cleaned = [replace(by_id[p.osm_ids[0]], polygon=p.polygon) for p in pieces]
    clean_report.update(separate_report)
    clean_report["buildings_outside_area_or_too_small"] = len(by_id) - len({b.building_id for b in cleaned})
    return cleaned, parse_report, clean_report


def _geojson(area: StudyArea, buildings: list[ht.Building]) -> dict:
    inverse = area.transformer()

    def ring(coords) -> list[list[float]]:
        xs, ys = np.asarray(coords)[:, 0], np.asarray(coords)[:, 1]
        lon, lat = inverse.transform(xs, ys, direction="INVERSE")
        return [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]

    features = []
    for b in buildings:
        h = b.height
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [ring(b.polygon.exterior.coords)]
                         + [ring(r.coords) for r in b.polygon.interiors]},
            "properties": {
                "building_id": b.building_id,
                "height_m": h.height_m,
                "height_category": h.category,
                "height_source": h.source,
                "height_method": h.method,
                "height_uncertainty_m": h.uncertainty_m,
                "height_reference": h.reference,
                "original_height_tag": h.original.get("height"),
                "original_levels_tag": h.original.get("building:levels"),
                "height_warnings": list(h.warnings),
                "footprint_area_m2": round(float(b.polygon.area), 2),
            },
        })
    return {"type": "FeatureCollection",
            "licence": osm_source.LICENCE + " (footprints and tags)",
            "features": features}


def build_dataset(area: StudyArea, overpass_json: dict, out_dir: Path, policy: ht.HeightPolicy,
                  snapshot_sha256: str, *, height_model: ht.HeightModel | None = None,
                  seed: int | None = None, manual_rows: list[dict] | None = None,
                  manual_name: str = "manual", scene_settings=None,
                  height_method_approved: bool = False) -> dict:
    """Write scene, building table and quality report into out_dir; return the report."""
    settings = scene_settings or osm_scene.SceneSettings()
    out_dir = Path(out_dir)
    buildings, parse_report, clean_report = provenance_buildings(
        area, overpass_json, policy, snapshot_sha256, height_model=height_model, seed=seed,
        manual_rows=manual_rows, manual_name=manual_name, scene_settings=settings)

    plain = [osm_scene.Building(b.polygon, b.height.height_m, b.height.category, (b.building_id,))
             for b in buildings]
    solids, merge_report = osm_scene.merge_solids(plain, settings)
    clean_report.update(merge_report)
    model_info = None if height_model is None else {
        "name": height_model.name, "kind": height_model.kind,
        "approved": height_model.approved, "seed": seed}
    scene_meta = osm_scene.write_scene(
        out_dir, solids, settings, area.half_extent_m,
        extra_meta={"area": area.name, "osm_snapshot_sha256": snapshot_sha256,
                    "height_model": model_info})

    (out_dir / "buildings.geojson").write_text(
        json.dumps(_geojson(area, buildings)), encoding="utf-8")
    report = quality.quality_report(buildings, area, parse_report, clean_report,
                                    scene_meta.get("mesh", {}), height_model=model_info,
                                    height_method_approved=height_method_approved)
    report["osm_snapshot_sha256"] = snapshot_sha256
    (out_dir / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "quality_report.md").write_text(quality.render_markdown(report), encoding="utf-8")
    return report


def load_buildings(dataset_dir: Path, area: StudyArea) -> list[ht.Building]:
    """Read the per-building table of a built dataset back, in local metres."""
    from shapely.geometry import Polygon

    forward = area.transformer()
    data = json.loads((Path(dataset_dir) / "buildings.geojson").read_text(encoding="utf-8"))
    buildings = []
    for feature in data["features"]:
        rings = []
        for ring in feature["geometry"]["coordinates"]:
            lon, lat = np.asarray(ring)[:, 0], np.asarray(ring)[:, 1]
            xs, ys = forward.transform(lon, lat)
            rings.append(list(zip(xs, ys)))
        p = feature["properties"]
        original = {k: v for k, v in (("height", p["original_height_tag"]),
                                      ("building:levels", p["original_levels_tag"])) if v is not None}
        record = ht.HeightRecord(p["height_m"], p["height_category"], p["height_source"],
                                 p["height_method"], p["height_reference"], original,
                                 p["height_uncertainty_m"], tuple(p["height_warnings"]))
        buildings.append(ht.Building(p["building_id"], Polygon(rings[0], rings[1:]), {}, record))
    return buildings
