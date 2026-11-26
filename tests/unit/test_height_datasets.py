"""External building-height datasets: extraction, footprint matching, height assignment."""

import json
import zipfile

import pytest
import shapefile
from shapely.geometry import box

from bns.geospatial import heights as ht
from bns.geospatial import height_datasets as hd
from bns.geospatial.study_area import StudyArea

AREA = StudyArea(name="t", role="development fixture", approved=False, center_lat=33.328,
                 center_lon=44.4085, receiver_size_m=(400.0, 400.0), margin_m=50.0)
POLICY = ht.HeightPolicy(3.0, 9.0, 250.0)


def lonlat_ring(points):
    t = AREA.transformer()
    return [list(t.transform(x, y, direction="INVERSE")) for x, y in points]


def write_tile(tmp_path, parts):
    """A tiny 3D-GloBFP-like shapefile zip: one Height field, WGS84 polygons."""
    stem = tmp_path / "tile"
    with shapefile.Writer(str(stem), shapeType=shapefile.POLYGON) as w:
        w.field("Height", "N", 24, 15)
        for ring, height in parts:
            w.poly([ring])
            w.record(height)
    (tmp_path / "tile.prj").write_text('GEOGCS["GCS_WGS_1984"]')
    archive = tmp_path / "tile.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for ext in ("shp", "shx", "dbf", "prj"):
            z.write(tmp_path / f"tile.{ext}", f"tile.{ext}")
    return archive


def square(x, y, size):
    return [(x, y), (x, y + size), (x + size, y + size), (x + size, y), (x, y)]   # clockwise


def test_extract_keeps_only_footprints_inside_the_box_with_their_height(tmp_path):
    inside = lonlat_ring(square(0, 0, 20))
    far = lonlat_ring(square(5000, 5000, 20))
    archive = write_tile(tmp_path, [(inside, 12.5), (far, 30.0)])
    features = hd.extract_tile(archive, AREA.bbox_degrees())
    assert len(features) == 1
    assert features[0]["properties"]["height_m"] == pytest.approx(12.5)
    assert features[0]["properties"]["record"] == 0


def test_extract_round_trips_through_the_stored_geojson(tmp_path):
    archive = write_tile(tmp_path, [(lonlat_ring(square(0, 0, 20)), 7.0)])
    out = tmp_path / "extract.geojson"
    hd.write_extract(hd.extract_tile(archive, AREA.bbox_degrees()), out, {"dataset": "test"})
    loaded = hd.load_extract(out, AREA)
    assert len(loaded) == 1 and loaded[0].height_m == 7.0
    assert loaded[0].polygon.area == pytest.approx(400.0, rel=1e-3)
    assert json.loads(out.read_text())["metadata"]["dataset"] == "test"


def ext(i, polygon, height):
    return hd.ExternalFootprint(f"ext/{i}", polygon, height)


def osm(i, polygon, tags=None):
    return ht.Building(f"way/{i}", polygon, tags or {},
                       ht.height_from_osm_tags(tags or {}, POLICY, f"way/{i}"))


def test_matching_classifies_one_to_one_split_and_missing_buildings():
    buildings = [osm(1, box(0, 0, 20, 20)),         # same footprint in both
                 osm(2, box(100, 0, 140, 20)),      # mapped as two halves in the dataset
                 osm(3, box(200, 0, 220, 20))]      # absent from the dataset
    external = [ext(1, box(0.5, 0, 20, 20), 10.0),
                ext(2, box(100, 0, 120, 20), 6.0), ext(3, box(120, 0, 140, 20), 12.0),
                ext(4, box(300, 0, 320, 20), 9.0)]  # absent from OSM
    result = hd.match_footprints(buildings, external, min_coverage=0.5)
    by_id = {m.building_id: m for m in result.matches}
    assert by_id["way/1"].kind == "one-to-one" and by_id["way/1"].height_m == 10.0
    assert by_id["way/1"].iou == pytest.approx(0.975)
    assert by_id["way/2"].kind == "split" and by_id["way/2"].height_m == pytest.approx(9.0)
    assert by_id["way/2"].max_height_m == 12.0 and by_id["way/2"].coverage == pytest.approx(1.0)
    assert result.osm_unmatched == ["way/3"]
    assert result.external_unmatched == ["ext/4"]


def test_a_dataset_footprint_spanning_several_osm_buildings_is_flagged():
    buildings = [osm(1, box(0, 0, 20, 20)), osm(2, box(20, 0, 40, 20))]
    result = hd.match_footprints(buildings, [ext(1, box(0, 0, 40, 20), 15.0)], min_coverage=0.5)
    kinds = {m.building_id: m.kind for m in result.matches}
    assert kinds == {"way/1": "merged", "way/2": "merged"}


def test_weak_overlap_is_not_a_match():
    result = hd.match_footprints([osm(1, box(0, 0, 20, 20))], [ext(1, box(15, 0, 35, 20), 8.0)],
                                 min_coverage=0.5)
    assert result.matches == [] and result.osm_unmatched == ["way/1"]


def test_overlapping_dataset_footprints_are_reported_as_duplicates():
    external = [ext(1, box(0, 0, 20, 20), 5.0), ext(2, box(0.5, 0, 20, 20), 6.0)]
    result = hd.match_footprints([osm(1, box(0, 0, 20, 20))], external, min_coverage=0.5)
    assert result.external_duplicates == [("ext/1", "ext/2")]


def test_matched_height_becomes_an_estimate_with_its_provenance():
    result = hd.match_footprints([osm(1, box(0, 0, 20, 20))], [ext(7, box(0, 0, 20, 20), 11.0)],
                                 min_coverage=0.5)
    record = hd.height_record(result.matches[0], dataset="3D-GloBFP v4", reference="tile 1590")
    assert record.category == ht.ESTIMATED and record.height_m == 11.0
    assert record.source == "dataset:3D-GloBFP v4"
    assert "one-to-one" in record.method and "ext/7" in record.reference
