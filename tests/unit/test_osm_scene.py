import numpy as np
import pytest
from shapely.geometry import Polygon, box

from bns.geospatial import osm_scene as osm

SETTINGS = osm.SceneSettings()


def building(polygon, height=10.0, source=osm.HEIGHT_ASSUMED, osm_id=1):
    return osm.Building(polygon, height, source, (osm_id,))


# --- heights ---------------------------------------------------------------------


def test_height_tag_wins_and_is_recorded_as_observed():
    assert osm.resolve_height({"height": "24.5 m"}, SETTINGS) == (24.5, osm.HEIGHT_FROM_TAG, None)


def test_levels_are_converted_with_the_recorded_storey_height():
    height, source, warning = osm.resolve_height({"building:levels": "4"}, SETTINGS)
    assert (height, source, warning) == (4 * SETTINGS.storey_height_m, osm.HEIGHT_FROM_LEVELS, None)


def test_untagged_building_gets_the_placeholder_and_is_marked_assumed():
    height, source, _ = osm.resolve_height({"building": "yes"}, SETTINGS)
    assert (height, source) == (SETTINGS.default_height_m, osm.HEIGHT_ASSUMED)


def test_contradicting_tags_raise_a_warning():
    _, _, warning = osm.resolve_height({"height": "15", "building:levels": "38"}, SETTINGS)
    assert warning and "contradicts" in warning


@pytest.mark.parametrize("value", ["0", "-3", "9999", "tall"])
def test_implausible_height_is_not_used(value):
    height, source, _ = osm.resolve_height({"height": value}, SETTINGS)
    assert (height, source) == (SETTINGS.default_height_m, osm.HEIGHT_ASSUMED)


# --- coordinates -----------------------------------------------------------------


def test_local_projection_is_metric_and_centred():
    t = osm.local_transformer(33.328, 44.4085)
    assert np.allclose(t.transform(44.4085, 33.328), (0.0, 0.0), atol=1e-6)
    x, y = t.transform(44.4085, 33.329)         # 0.001 degree of latitude north
    assert x == pytest.approx(0.0, abs=1e-3)
    assert y == pytest.approx(110.9, abs=0.2)   # one millidegree of latitude at 33 N
    lon, lat = t.transform(500.0, -500.0, direction="INVERSE")
    assert np.allclose(t.transform(lon, lat), (500.0, -500.0), atol=1e-6)


# --- meshing ---------------------------------------------------------------------


def test_box_mesh_has_shared_edges_and_no_bottom():
    vertices, faces = osm.extrude(box(0, 0, 20, 10), 15.0, SETTINGS.wall_sink_m)
    report = osm.mesh_report(vertices, faces)
    assert len(vertices) == 8 and len(faces) == 10          # 8 wall + 2 roof triangles
    assert report["wedges"] == 8                              # 4 vertical corners + 4 roof edges
    assert report["rim_edges"] == 4                           # the open bottom
    assert report["non_manifold_edges"] == 0
    assert report["degenerate_triangles"] == 0
    assert report["roof_triangles_facing_down"] == 0
    assert vertices[:, 2].min() == -SETTINGS.wall_sink_m and vertices[:, 2].max() == 15.0


def test_wall_normals_point_outward():
    vertices, faces = osm.extrude(box(-5, -5, 5, 5), 10.0, 0.5)
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    centroids = tri.mean(axis=1)
    walls = np.abs(normals[:, 2]) < 1e-9
    outward = np.einsum("ij,ij->i", normals[walls, :2], centroids[walls, :2])
    assert np.all(outward > 0)


def test_courtyard_building_keeps_its_hole_and_stays_manifold():
    ring = Polygon(box(0, 0, 30, 30).exterior.coords, [box(10, 10, 20, 20).exterior.coords])
    vertices, faces = osm.extrude(ring, 12.0, 0.5)
    report = osm.mesh_report(vertices, faces)
    assert report["non_manifold_edges"] == 0 and report["degenerate_triangles"] == 0
    assert report["wedges"] == 16                             # 8 corners + 8 roof edges
    tri = vertices[faces]
    roof = np.abs(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])[:, 2]) > 1e-9
    roof_area = 0.5 * np.abs(np.cross(tri[roof, 1] - tri[roof, 0], tri[roof, 2] - tri[roof, 0])[:, 2]).sum()
    assert roof_area == pytest.approx(900.0 - 100.0)


# --- cleaning --------------------------------------------------------------------


def test_touching_footprints_of_equal_height_become_one_solid():
    cleaned, stats = osm.clean_footprints(
        [building(box(0, 0, 10, 10), osm_id=1), building(box(10, 0, 20, 10), osm_id=2)], SETTINGS)
    assert len(cleaned) == 1 and cleaned[0].polygon.area == pytest.approx(200.0)
    assert set(cleaned[0].osm_ids) == {1, 2}
    assert stats["different_height_contacts"] == 0


def test_different_heights_stay_separate_and_the_contact_is_counted():
    cleaned, stats = osm.clean_footprints(
        [building(box(0, 0, 10, 10), 10.0, osm_id=1), building(box(10, 0, 20, 10), 25.0, osm_id=2)],
        SETTINGS)
    assert len(cleaned) == 2 and stats["different_height_contacts"] == 1


def test_overlap_goes_to_the_taller_building():
    cleaned, stats = osm.clean_footprints(
        [building(box(0, 0, 10, 10), 10.0, osm_id=1), building(box(5, 0, 15, 10), 30.0, osm_id=2)],
        SETTINGS)
    by_height = {b.height_m: b.polygon.area for b in cleaned}
    assert by_height == {30.0: pytest.approx(100.0), 10.0: pytest.approx(50.0)}
    assert stats["overlaps_resolved"] == 1


def test_hair_thin_gap_between_merged_neighbours_is_filled():
    # two U-shaped halves that leave a 5 cm wide slot between them
    left = Polygon([(0, 0), (10, 0), (10, 2), (9.975, 2), (9.975, 8), (10, 8), (10, 10), (0, 10)])
    right = Polygon([(10, 0), (20, 0), (20, 10), (10, 10), (10, 8), (10.025, 8), (10.025, 2), (10, 2)])
    cleaned, _ = osm.clean_footprints([building(left, osm_id=1), building(right, osm_id=2)], SETTINGS)
    assert len(cleaned) == 1 and len(cleaned[0].polygon.interiors) == 0
    report = osm.mesh_report(*osm.extrude(cleaned[0].polygon, 10.0, 0.5))
    assert report["degenerate_triangles"] == 0 and report["non_manifold_edges"] == 0


def test_tiny_and_clipped_footprints_are_dropped():
    cleaned, _ = osm.clean_footprints(
        [building(box(0, 0, 1, 1)), building(box(100, 100, 120, 120), osm_id=2)],
        SETTINGS, clip_box=box(-50, -50, 50, 50))
    assert cleaned == []


# --- files and masks -------------------------------------------------------------


def test_scene_round_trip_and_ply_layout(tmp_path):
    b = [building(box(-10, -10, 10, 10), 12.0, osm.HEIGHT_FROM_TAG, 7)]
    meta = osm.write_scene(tmp_path, b, SETTINGS, (100.0, 100.0))
    assert meta["height_sources"] == {osm.HEIGHT_FROM_TAG: 1}
    assert meta["mesh"]["wedges"] == 8
    xml = (tmp_path / "scene.xml").read_text()
    assert 'value="concrete"' in xml and "meshes/buildings.ply" in xml and "meshes/ground.ply" in xml
    raw = (tmp_path / "meshes" / "buildings.ply").read_bytes()
    header, body = raw.split(b"end_header\n")
    assert b"element vertex 8" in header and b"element face 10" in header
    assert len(body) == 8 * 12 + 10 * 13                      # float32 xyz + (uchar, 3 int32)
    loaded = osm.load_footprints(tmp_path)
    assert loaded[0].height_m == 12.0 and loaded[0].polygon.equals(b[0].polygon)


def test_indoor_mask_marks_every_cell_touching_a_footprint():
    xs = np.arange(-25.0, 30.0, 10.0)     # cell centres -25 ... 25, 10 m cells
    ys = np.arange(-25.0, 30.0, 10.0)
    mask = osm.indoor_mask([building(box(-4, -4, 4, 4))], xs, ys, 10.0)
    assert mask.shape == (6, 6)
    assert mask.sum() == 4                 # the footprint straddles the four central cells
    assert mask[2:4, 2:4].all()
