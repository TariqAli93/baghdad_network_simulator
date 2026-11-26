"""Study areas, OSM parsing, height provenance, rooftop candidates, receiver grid, reports.

No network and no ray tracing: everything runs on small synthetic inputs.
"""

import hashlib
import json

import numpy as np
import pytest
from shapely.geometry import Point, box

from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline, quality, sites
from bns.geospatial.grid import Grid, outdoor_mask
from bns.geospatial.study_area import StudyArea, load_study_areas

AREA = StudyArea(name="test_area", role="development fixture", approved=False,
                 center_lat=33.328, center_lon=44.4085,
                 receiver_size_m=(400.0, 200.0), margin_m=100.0)
POLICY = ht.HeightPolicy(storey_height_m=3.0, placeholder_height_m=9.0, max_plausible_height_m=250.0)


# --- study area ---------------------------------------------------------------------


def test_repository_config_defines_the_fixture_and_marks_it_not_final(repo_root):
    areas = load_study_areas(repo_root / "configs" / "study_area.yaml")
    fixture = areas["tahrir_bab_al_sharqi"]
    assert fixture.role == "development fixture" and not fixture.approved
    assert not fixture.is_research_dataset


def test_provisional_area_uses_its_own_snapshot_and_leaves_the_fixture_alone(repo_root):
    areas = load_study_areas(repo_root / "configs" / "study_area.yaml")
    fixture, provisional = areas["tahrir_bab_al_sharqi"], areas["tahrir_bab_al_sharqi_v2"]
    assert fixture.snapshot == "tahrir_bab_al_sharqi"
    assert provisional.snapshot != fixture.snapshot
    assert provisional.role == "provisional study area" and not provisional.is_research_dataset
    assert (provisional.center_lat, provisional.center_lon, provisional.receiver_size_m,
            provisional.margin_m) == (fixture.center_lat, fixture.center_lon,
                                      fixture.receiver_size_m, fixture.margin_m)


def test_snapshot_defaults_to_the_area_name():
    assert AREA.snapshot == "test_area"


def test_fetch_refuses_to_overwrite_an_existing_snapshot(tmp_path):
    (tmp_path / "kept.json").write_text("{}")
    with pytest.raises(FileExistsError, match="kept"):
        osm_source.fetch_snapshot(tmp_path, "kept", (33.0, 44.0, 33.1, 44.1))


def test_extent_and_bounding_box_include_the_margin():
    assert AREA.half_extent_m == (300.0, 200.0)
    south, west, north, east = AREA.bbox_degrees(pad_m=0.0)
    t = AREA.transformer()
    x_w, y_s = t.transform(west, south)
    x_e, y_n = t.transform(east, north)
    assert x_w == pytest.approx(-300.0, abs=0.5) and x_e == pytest.approx(300.0, abs=0.5)
    assert y_s == pytest.approx(-200.0, abs=0.5) and y_n == pytest.approx(200.0, abs=0.5)


def test_receiver_grid_covers_the_receiver_area_only():
    grid = AREA.receiver_grid(cell_size_m=10.0, height_m=1.5)
    assert grid.shape == (20, 40)
    assert grid.x_centers[0] == pytest.approx(-195.0) and grid.y_centers[-1] == pytest.approx(95.0)


@pytest.mark.parametrize("change", [{"center_lat": 95.0}, {"receiver_size_m": (0.0, 100.0)},
                                    {"margin_m": -1.0}, {"role": "holiday"}])
def test_invalid_study_areas_are_rejected(change):
    values = dict(name="x", role="development fixture", approved=False, center_lat=33.3,
                  center_lon=44.4, receiver_size_m=(100.0, 100.0), margin_m=10.0)
    values.update(change)
    with pytest.raises(ValueError):
        StudyArea(**values)


def test_only_an_approved_study_district_counts_as_a_research_dataset():
    district = StudyArea(name="d", role="study district", approved=True, center_lat=33.3,
                         center_lon=44.4, receiver_size_m=(1000.0, 1000.0), margin_m=150.0)
    assert district.is_research_dataset
    pending = StudyArea(name="d", role="study district", approved=False, center_lat=33.3,
                        center_lon=44.4, receiver_size_m=(1000.0, 1000.0), margin_m=150.0)
    assert not pending.is_research_dataset


# --- receiver grid ------------------------------------------------------------------


def test_grid_cell_centres_are_symmetric_about_the_centre():
    grid = Grid((10.0, -20.0), (40.0, 20.0), 10.0)
    assert grid.shape == (2, 4)
    assert grid.x_centers.tolist() == [-5.0, 5.0, 15.0, 25.0]
    assert grid.y_centers.tolist() == [-25.0, -15.0]


def test_outdoor_mask_excludes_every_cell_touching_a_building():
    grid = Grid((0.0, 0.0), (60.0, 60.0), 10.0)
    mask = outdoor_mask(grid, [box(-4.0, -4.0, 4.0, 4.0)])
    assert mask.shape == (6, 6) and mask.sum() == 32
    assert not mask[2:4, 2:4].any()


# --- OSM parsing --------------------------------------------------------------------


def lonlat(area, points):
    t = area.transformer()
    return [dict(zip(("lon", "lat"), t.transform(x, y, direction="INVERSE"))) for x, y in points]


def way(area, osm_id, points, tags):
    ring = list(points) + [points[0]]
    return {"type": "way", "id": osm_id, "tags": tags, "geometry": lonlat(area, ring)}


SQUARE = [(0, 0), (20, 0), (20, 20), (0, 20)]


def shifted(points, dx, dy=0.0):
    return [(x + dx, y + dy) for x, y in points]


def test_building_ways_become_metric_polygons_with_their_tags():
    data = {"elements": [way(AREA, 7, SQUARE, {"building": "yes", "height": "12"}),
                         way(AREA, 8, SQUARE, {"highway": "service"})]}
    buildings, report = osm_source.parse_buildings(data, AREA.transformer())
    assert [b.building_id for b in buildings] == ["way/7"]
    assert buildings[0].polygon.area == pytest.approx(400.0, rel=1e-4)
    assert buildings[0].tags["height"] == "12"
    assert report["buildings_read"] == 1


def test_multipolygon_relation_with_split_outer_ring_and_a_courtyard():
    outer_a = lonlat(AREA, [(0, 0), (40, 0), (40, 40)])
    outer_b = lonlat(AREA, [(40, 40), (0, 40), (0, 0)])
    inner = lonlat(AREA, [(10, 10), (30, 10), (30, 30), (10, 30), (10, 10)])
    relation = {"type": "relation", "id": 5, "tags": {"building": "yes", "type": "multipolygon"},
                "members": [{"type": "way", "role": "outer", "geometry": outer_a},
                            {"type": "way", "role": "outer", "geometry": outer_b},
                            {"type": "way", "role": "inner", "geometry": inner}]}
    buildings, report = osm_source.parse_buildings({"elements": [relation]}, AREA.transformer())
    assert buildings[0].building_id == "relation/5"
    assert buildings[0].polygon.area == pytest.approx(1600.0 - 400.0, rel=1e-4)
    assert len(buildings[0].polygon.interiors) == 1
    assert report["relations_read"] == 1


def test_unusable_elements_are_counted_not_dropped_silently():
    open_way = {"type": "way", "id": 1, "tags": {"building": "yes"},
                "geometry": lonlat(AREA, [(0, 0), (5, 0)])}
    empty_relation = {"type": "relation", "id": 2, "tags": {"building": "yes"}, "members": []}
    buildings, report = osm_source.parse_buildings({"elements": [open_way, empty_relation]},
                                                   AREA.transformer())
    assert buildings == []
    assert sum(report["skipped"].values()) == 2


def test_relation_with_a_missing_outer_member_is_skipped_and_counted():
    # one of the two outer ways lies outside the download box and came without geometry
    outer_a = lonlat(AREA, [(0, 0), (40, 0), (40, 40)])
    relation = {"type": "relation", "id": 6, "tags": {"building": "yes"},
                "members": [{"type": "way", "role": "outer", "geometry": outer_a},
                            {"type": "way", "role": "outer", "ref": 99}]}
    buildings, report = osm_source.parse_buildings({"elements": [relation]}, AREA.transformer())
    assert buildings == []
    assert report["skipped"] == {"relation without a closed outer ring": 1}
    assert report["relations_with_missing_members"] == 1


def test_duplicate_footprints_are_found():
    data = {"elements": [way(AREA, 1, SQUARE, {"building": "yes"}),
                         way(AREA, 2, shifted(SQUARE, 0.2), {"building": "yes"}),
                         way(AREA, 3, shifted(SQUARE, 50), {"building": "yes"})]}
    buildings, _ = osm_source.parse_buildings(data, AREA.transformer())
    assert osm_source.find_duplicates(buildings, min_overlap=0.9) == [("way/1", "way/2")]


def test_relation_stored_without_member_geometry_is_reported_as_such():
    # The Phase 0 snapshot was fetched with "out tags geom", which omits relation members.
    bare = {"type": "relation", "id": 9, "tags": {"building": "yes"}, "bounds": {}}
    _, report = osm_source.parse_buildings({"elements": [bare]}, AREA.transformer())
    assert report["skipped"] == {"relation stored without member geometry": 1}


def test_query_asks_for_member_geometry_so_relations_can_be_read():
    query = osm_source.overpass_query((33.0, 44.0, 33.1, 44.1))
    assert query.endswith("out geom;") and "out tags geom" not in query
    assert 'relation["building"]' in query and "33.000000,44.000000,33.100000,44.100000" in query


def test_load_buildings_reads_back_what_build_dataset_wrote(tmp_path):
    data = {"elements": [way(AREA, 1, SQUARE, {"building": "yes", "height": "30"}),
                         way(AREA, 2, shifted(SQUARE, 60), {"building": "yes"})]}
    pipeline.build_dataset(AREA, data, tmp_path, POLICY, snapshot_sha256="s")
    loaded = {b.building_id: b for b in pipeline.load_buildings(tmp_path, AREA)}
    assert loaded["way/1"].height.height_m == 30.0 and loaded["way/1"].height.category == ht.OBSERVED
    assert loaded["way/1"].height.original == {"height": "30"}
    assert loaded["way/2"].height.category == ht.PLACEHOLDER
    assert loaded["way/1"].polygon.area == pytest.approx(400.0, rel=1e-3)


def test_height_policy_loads_from_the_repository_config(repo_root):
    policy = ht.load_height_policy(repo_root / "configs" / "study_area.yaml")
    assert policy.storey_height_m > 0 and policy.placeholder_height_m > 0


def test_snapshot_is_rejected_when_it_no_longer_matches_its_recorded_hash(tmp_path):
    raw = json.dumps({"elements": []}).encode()
    (tmp_path / "a.json").write_bytes(raw)
    (tmp_path / "a.meta.json").write_text(json.dumps({"sha256": hashlib.sha256(raw).hexdigest()}))
    data, meta = osm_source.load_snapshot(tmp_path, "a")
    assert data == {"elements": []} and len(meta["sha256"]) == 64
    (tmp_path / "a.json").write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="does not match"):
        osm_source.load_snapshot(tmp_path, "a")


def test_missing_snapshot_explains_how_to_get_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="--fetch"):
        osm_source.load_snapshot(tmp_path, "nowhere")


# --- height provenance --------------------------------------------------------------


def test_height_tag_is_recorded_as_observed_with_its_original_value():
    record = ht.height_from_osm_tags({"height": "24.5 m", "building:levels": "8"}, POLICY, "way/1")
    assert record.height_m == 24.5 and record.category == ht.OBSERVED
    assert record.source == "osm:height"
    assert record.original == {"height": "24.5 m", "building:levels": "8"}
    assert "way/1" in record.reference


def test_levels_give_an_estimate_that_states_its_method():
    record = ht.height_from_osm_tags({"building:levels": "4"}, POLICY, "way/2")
    assert record.height_m == 12.0 and record.category == ht.ESTIMATED
    assert record.source == "osm:building:levels" and "3.0 m" in record.method


def test_missing_height_becomes_a_placeholder_never_an_estimate():
    record = ht.height_from_osm_tags({"building": "yes"}, POLICY, "way/3")
    assert record.category == ht.PLACEHOLDER and record.height_m == 9.0
    assert record.source == "placeholder" and record.original == {}


def test_implausible_and_contradicting_tags_are_flagged_and_kept_in_the_record():
    bad = ht.height_from_osm_tags({"height": "9999"}, POLICY, "way/4")
    assert bad.category == ht.PLACEHOLDER and bad.original == {"height": "9999"}
    assert any("implausible" in w for w in bad.warnings)
    clash = ht.height_from_osm_tags({"height": "15", "building:levels": "38"}, POLICY, "way/5")
    assert clash.height_m == 15.0 and any("contradicts" in w for w in clash.warnings)


def make_buildings():
    return [
        ht.Building("way/1", box(0, 0, 20, 20), {"building": "yes", "height": "30"},
                    ht.height_from_osm_tags({"height": "30"}, POLICY, "way/1")),
        ht.Building("way/2", box(100, 0, 120, 20), {"building": "yes", "building:levels": "5"},
                    ht.height_from_osm_tags({"building:levels": "5"}, POLICY, "way/2")),
        ht.Building("way/3", box(200, 0, 220, 20), {"building": "yes"},
                    ht.height_from_osm_tags({}, POLICY, "way/3")),
        ht.Building("way/4", box(300, 0, 340, 20), {"building": "yes"},
                    ht.height_from_osm_tags({}, POLICY, "way/4")),
    ]


def test_manual_observation_replaces_the_height_but_keeps_the_osm_original():
    buildings = make_buildings()
    rows = [{"building_id": "way/3", "height_m": "18.5", "method": "laser rangefinder",
             "observer": "student", "date": "2026-12-01", "uncertainty_m": "0.5"}]
    updated, unmatched = ht.apply_manual_observations(buildings, rows, "observations.csv")
    record = {b.building_id: b.height for b in updated}["way/3"]
    assert record.height_m == 18.5 and record.category == ht.OBSERVED
    assert record.source == "manual:observations.csv" and record.uncertainty_m == 0.5
    assert "laser rangefinder" in record.method and "2026-12-01" in record.reference
    assert record.superseded.category == ht.PLACEHOLDER      # the earlier record is retained
    assert unmatched == []
    assert buildings[2].height.category == ht.PLACEHOLDER    # input list is not modified


def test_manual_observation_for_an_unknown_building_is_reported():
    _, unmatched = ht.apply_manual_observations(
        make_buildings(), [{"building_id": "way/999", "height_m": "10", "method": "x"}], "f.csv")
    assert unmatched == ["way/999"]


def test_height_model_fills_placeholders_only_and_says_so():
    model = ht.HeightModel("flat12", "constant", {"height_m": 12.0}, approved=False)
    updated = ht.apply_height_model(make_buildings(), model, seed=1)
    by_id = {b.building_id: b.height for b in updated}
    assert by_id["way/1"].height_m == 30.0 and by_id["way/1"].category == ht.OBSERVED
    assert by_id["way/2"].category == ht.ESTIMATED
    assert by_id["way/3"].height_m == 12.0
    assert by_id["way/3"].category == ht.PLACEHOLDER          # still not a measurement
    assert by_id["way/3"].source == "model:flat12" and "not approved" in by_id["way/3"].method


def test_random_height_model_is_reproducible_and_independent_of_building_order():
    model = ht.HeightModel("levels", "uniform_levels",
                           {"min_levels": 1, "max_levels": 6, "storey_height_m": 3.0}, approved=False)
    first = {b.building_id: b.height.height_m for b in ht.apply_height_model(make_buildings(), model, seed=7)}
    again = {b.building_id: b.height.height_m
             for b in ht.apply_height_model(list(reversed(make_buildings())), model, seed=7)}
    other = {b.building_id: b.height.height_m for b in ht.apply_height_model(make_buildings(), model, seed=8)}
    assert first == again
    assert all(3.0 <= first[i] <= 18.0 and first[i] % 3.0 == 0 for i in ("way/3", "way/4"))
    many = [ht.Building(f"way/{i}", box(0, 0, 5, 5), {}, ht.height_from_osm_tags({}, POLICY, f"way/{i}"))
            for i in range(200)]
    a = [b.height.height_m for b in ht.apply_height_model(many, model, seed=7)]
    b = [b.height.height_m for b in ht.apply_height_model(many, model, seed=8)]
    assert a != b and len(set(a)) == 6 and other.keys() == first.keys()


def test_lognormal_height_model_respects_its_limits_and_median():
    model = ht.HeightModel("ln", "lognormal",
                           {"median_m": 10.0, "sigma": 0.5, "min_m": 3.0, "max_m": 60.0}, approved=False)
    many = [ht.Building(f"way/{i}", box(0, 0, 5, 5), {}, ht.height_from_osm_tags({}, POLICY, f"way/{i}"))
            for i in range(2000)]
    values = np.array([b.height.height_m for b in ht.apply_height_model(many, model, seed=3)])
    assert values.min() >= 3.0 and values.max() <= 60.0
    assert np.median(values) == pytest.approx(10.0, rel=0.1)


def test_unknown_height_model_kind_is_an_error():
    with pytest.raises(ValueError):
        ht.apply_height_model(make_buildings(), ht.HeightModel("x", "magic", {}, approved=False), seed=1)


def test_height_models_load_from_the_repository_config(repo_root):
    models = ht.load_height_models(repo_root / "configs" / "height_models.yaml")
    assert len(models) >= 3
    assert all(not m.approved for m in models.values())     # none is approved yet


# --- rooftop candidates -------------------------------------------------------------


def test_candidates_start_with_the_tallest_building_and_sit_inside_the_footprint():
    found = sites.rooftop_candidates(make_buildings(), mast_height_m=3.0, min_height_m=0.0,
                                     min_area_m2=0.0, min_spacing_m=0.0)
    assert [c.building_id for c in found][:2] == ["way/1", "way/2"]
    first = found[0]
    assert first.z == pytest.approx(33.0) and first.roof_height_m == 30.0
    assert make_buildings()[0].polygon.contains(Point(first.x, first.y))
    assert first.height_category == ht.OBSERVED


def test_candidate_filters_height_area_spacing_and_category():
    buildings = make_buildings()
    tall = sites.rooftop_candidates(buildings, mast_height_m=3.0, min_height_m=12.0,
                                    min_area_m2=0.0, min_spacing_m=0.0)
    assert [c.building_id for c in tall] == ["way/1", "way/2"]
    large = sites.rooftop_candidates(buildings, mast_height_m=3.0, min_height_m=0.0,
                                     min_area_m2=500.0, min_spacing_m=0.0)
    assert [c.building_id for c in large] == ["way/4"]
    spaced = sites.rooftop_candidates(buildings, mast_height_m=3.0, min_height_m=0.0,
                                      min_area_m2=0.0, min_spacing_m=150.0)
    # equal heights are ordered by roof area, so the larger way/4 is tried before way/3,
    # which then lies too close to it
    assert [c.building_id for c in spaced] == ["way/1", "way/4"]
    trusted = sites.rooftop_candidates(buildings, mast_height_m=3.0, min_height_m=0.0, min_area_m2=0.0,
                                       min_spacing_m=0.0, categories=(ht.OBSERVED, ht.ESTIMATED))
    assert [c.building_id for c in trusted] == ["way/1", "way/2"]
    capped = sites.rooftop_candidates(buildings, mast_height_m=3.0, min_height_m=0.0,
                                      min_area_m2=0.0, min_spacing_m=0.0, max_candidates=1)
    assert len(capped) == 1


# --- quality report -----------------------------------------------------------------


def test_quality_report_gives_shares_by_count_and_by_footprint_area():
    report = quality.quality_report(make_buildings(), AREA, parse_report={"skipped": {}},
                                    clean_report={}, mesh_report={})
    by_count = report["height_categories"]["by_count_percent"]
    assert by_count == {ht.OBSERVED: 25.0, ht.ESTIMATED: 25.0, ht.PLACEHOLDER: 50.0}
    by_area = report["height_categories"]["by_area_percent"]
    assert by_area[ht.PLACEHOLDER] == pytest.approx(60.0)     # 400 + 800 of 2000 m2
    assert sum(by_area.values()) == pytest.approx(100.0)
    assert report["buildings"] == 4 and report["missing_height_buildings"] == 2
    assert report["height_sources"]["by_count"]["osm:height"] == 1


def test_quality_report_says_why_a_dataset_is_not_fit_for_research():
    report = quality.quality_report(make_buildings(), AREA, {"skipped": {}}, {}, {})
    assert report["fit_for_research"] is False
    reasons = " ".join(report["not_fit_reasons"])
    assert "development fixture" in reasons and "placeholder" in reasons
    text = quality.render_markdown(report)
    assert "50.0 %" in text and "NOT fit for research" in text


# --- end-to-end build ---------------------------------------------------------------


def test_build_dataset_writes_scene_buildings_and_report_with_provenance(tmp_path):
    data = {"elements": [
        way(AREA, 1, SQUARE, {"building": "yes", "height": "30"}),
        way(AREA, 2, shifted(SQUARE, 60), {"building": "yes", "building:levels": "5"}),
        way(AREA, 3, shifted(SQUARE, -80), {"building": "yes"}),
    ]}
    report = pipeline.build_dataset(AREA, data, tmp_path, POLICY, snapshot_sha256="abc123")
    for name in ("scene.xml", "meshes/buildings.ply", "meshes/ground.ply", "footprints.json",
                 "buildings.geojson", "quality_report.json", "quality_report.md"):
        assert (tmp_path / name).exists(), name

    features = json.loads((tmp_path / "buildings.geojson").read_text())["features"]
    props = {f["properties"]["building_id"]: f["properties"] for f in features}
    assert props["way/1"]["height_category"] == ht.OBSERVED and props["way/1"]["height_m"] == 30.0
    assert props["way/1"]["original_height_tag"] == "30"
    assert props["way/2"]["height_method"].startswith("5 levels")
    assert props["way/3"]["height_category"] == ht.PLACEHOLDER
    assert "abc123" in props["way/3"]["height_reference"]
    lon, lat = features[0]["geometry"]["coordinates"][0][0]
    assert 44.40 < lon < 44.42 and 33.32 < lat < 33.34          # stored in WGS84

    assert report["buildings"] == 3
    assert report["height_categories"]["by_count_percent"][ht.PLACEHOLDER] == pytest.approx(100 / 3)
    assert report["mesh"]["non_manifold_edges"] == 0


def test_a_building_split_by_cleaning_gets_unique_piece_ids():
    # a tall building cuts a low one in two: the low one becomes two pieces
    data = {"elements": [way(AREA, 1, [(0, 0), (60, 0), (60, 10), (0, 10)], {"building": "yes"}),
                         way(AREA, 2, [(25, -5), (35, -5), (35, 15), (25, 15)],
                             {"building": "yes", "height": "30"})]}
    buildings, _, _ = pipeline.provenance_buildings(AREA, data, POLICY, "s")
    ids = [b.building_id for b in buildings]
    assert len(ids) == len(set(ids)) == 3
    assert sorted(ids) == ["way/1#p1", "way/1#p2", "way/2"]


def test_build_dataset_with_an_external_dataset_records_every_source(tmp_path):
    from bns.geospatial import height_datasets as hd

    data = {"elements": [way(AREA, 1, SQUARE, {"building": "yes", "height": "30"}),
                         way(AREA, 2, shifted(SQUARE, 60), {"building": "yes"})]}
    ring = lambda pts: [[lon, lat] for lon, lat in ((p["lon"], p["lat"]) for p in lonlat(AREA, pts))]
    features = [{"type": "Feature", "properties": {"record": 11, "height_m": 70.0},
                 "geometry": {"type": "Polygon", "coordinates": [ring(SQUARE + [SQUARE[0]])]}},
                {"type": "Feature", "properties": {"record": 12, "height_m": 14.0},
                 "geometry": {"type": "Polygon",
                              "coordinates": [ring(shifted(SQUARE, 60) + [shifted(SQUARE, 60)[0]])]}}]
    extract = tmp_path / "extract.geojson"
    hd.write_extract(features, extract, {"dataset": "TestSet"})
    report = pipeline.build_dataset(AREA, data, tmp_path / "out", POLICY, snapshot_sha256="s",
                                    height_datasets=[("TestSet", extract, "test tile")])
    props = {f["properties"]["building_id"]: f["properties"]
             for f in json.loads((tmp_path / "out" / "buildings.geojson").read_text())["features"]}
    assert props["way/1"]["height_m"] == 30.0 and props["way/1"]["height_conflict"] is True
    assert props["way/1"]["height_alternatives"][0]["source"] == "dataset:TestSet"
    assert props["way/2"]["height_m"] == 14.0 and props["way/2"]["height_category"] == ht.ESTIMATED
    assert report["conflicting_buildings"] == 1
    assert report["height_sources"]["by_count"]["dataset:TestSet"] == 1
    reloaded = {b.building_id: b for b in pipeline.load_buildings(tmp_path / "out", AREA)}
    assert reloaded["way/1"].height.alternatives[0].height_m == 70.0
    assert reloaded["way/1"].tags == {"height": "30"}


def test_build_dataset_with_a_height_model_labels_the_variant(tmp_path):
    data = {"elements": [way(AREA, 3, SQUARE, {"building": "yes"})]}
    model = ht.HeightModel("flat15", "constant", {"height_m": 15.0}, approved=False)
    report = pipeline.build_dataset(AREA, data, tmp_path, POLICY, snapshot_sha256="x",
                                    height_model=model, seed=4)
    assert report["height_model"] == {"name": "flat15", "kind": "constant", "approved": False, "seed": 4}
    props = json.loads((tmp_path / "buildings.geojson").read_text())["features"][0]["properties"]
    assert props["height_m"] == 15.0 and props["height_source"] == "model:flat15"
    assert props["height_category"] == ht.PLACEHOLDER


def test_sector_antennas_stand_at_the_roof_edge_they_face():
    import numpy as np
    from shapely.geometry import Polygon

    from bns.geospatial.sites import edge_positions

    roof = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
    east, north, west = edge_positions(roof, 5.0, 5.0, [0.0, np.pi / 2, np.pi], inset_m=1.0)
    assert east == pytest.approx((19.0, 5.0)) and north == pytest.approx((5.0, 9.0))
    assert west == pytest.approx((1.0, 5.0))
    courtyard = Polygon([(0, 0), (30, 0), (30, 30), (0, 30)], [[(10, 10), (20, 10), (20, 20), (10, 20)]])
    [p] = edge_positions(courtyard, 5.0, 15.0, [0.0], inset_m=1.0)
    assert p == pytest.approx((9.0, 15.0))                        # stops at the courtyard wall
    with pytest.raises(ValueError):
        edge_positions(roof, 50.0, 5.0, [0.0], inset_m=1.0)


def test_placeholders_block_research_until_the_approved_worklist_is_complete():
    from shapely.geometry import box

    from bns.geospatial.quality import quality_report

    district = StudyArea(name="d", role="study district", approved=True, center_lat=33.3, center_lon=44.4,
                         receiver_size_m=(100.0, 100.0), margin_m=10.0)
    observed = ht.HeightRecord(20.0, ht.OBSERVED, "manual:obs.csv", "laser", "x")
    placeholder = ht.HeightRecord(9.0, ht.PLACEHOLDER, "placeholder", "none", "x")
    blds = [ht.Building("way/1", box(0, 0, 10, 10), {}, observed), ht.Building("way/2", box(20, 0, 30, 10), {}, placeholder)]

    def fit(**kw):
        r = quality_report(blds, district, {}, {}, {}, **kw)
        return r["fit_for_research"], r["not_fit_reasons"]

    assert fit(height_method_approved=True) == (False, ["50.0 % of buildings have placeholder heights"])
    ok, reasons = fit(height_method_approved=True, worklist={"listed": 2, "observed": 1, "unmatched": 0})
    assert not ok and "1 of 2 buildings observed" in reasons[1]
    assert fit(height_method_approved=True, worklist={"listed": 1, "observed": 1, "unmatched": 0}) == (True, [])
    assert not fit(height_method_approved=False, worklist={"listed": 1, "observed": 1, "unmatched": 0})[0]
    assert not fit(height_method_approved=True, worklist={"listed": 1, "observed": 1, "unmatched": 1})[0]


def test_completeness_is_judged_against_the_required_list_not_the_submitted_file():
    from bns.geospatial.pipeline import observation_status

    required = ["way/1", "way/2", "way/3"]
    rows = [{"building_id": "way/1", "method_class": "measured", "height_m": "20"},
            {"building_id": "way/2", "method_class": "storey_count", "storeys": "4"},
            {"building_id": "way/9", "method_class": "measured", "height_m": "10"}]     # not required
    status = observation_status(required, rows, unmatched=[])
    assert status == {"listed": 3, "observed": 2, "unmatched": 0, "missing": ["way/3"]}
    legacy = [{"building_id": i, "height_m": "10", "method": "x"} for i in required]   # no method class
    assert observation_status(required, legacy, unmatched=[])["observed"] == 0
    assert observation_status(required, None, unmatched=[])["observed"] == 0


def test_shadowing_counts_only_buildings_tall_enough_to_cut_the_line_first():
    from shapely.geometry import box

    from bns.geospatial.sites import shadowing_buildings

    low = ht.HeightRecord(3.0, ht.PLACEHOLDER, "placeholder", "none", "x")
    high = ht.HeightRecord(25.0, ht.OBSERVED, "osm:height", "tag", "x")
    blds = [ht.Building("low_near", box(10, -5, 15, 5), {}, low),       # under the line: no shadow
            ht.Building("high_mid", box(40, -5, 45, 5), {}, high),      # cuts the line first
            ht.Building("high_far", box(70, -5, 75, 5), {}, high)]      # behind high_mid
    hits = shadowing_buildings(blds, [(0.0, 0.0, 20.0)], [(100.0, 0.0)], receiver_height_m=1.5)
    assert hits == {"high_mid": 1}


def test_monuments_memorials_and_artworks_are_never_transmitter_candidates():
    from shapely.geometry import box

    from bns.geospatial.sites import rooftop_candidates

    rec = ht.HeightRecord(15.0, ht.OBSERVED, "osm:height", "tag", "x")
    blds = [ht.Building("way/1", box(0, 0, 50, 2), {"building": "yes", "historic": "monument"}, rec),
            ht.Building("way/2", box(100, 0, 104, 4), {"building": "yes", "memorial": "yes"}, rec),
            ht.Building("way/3", box(200, 0, 204, 4), {"building": "yes", "tourism": "artwork"}, rec),
            ht.Building("way/4", box(300, 0, 330, 30), {"building": "commercial"}, rec)]
    got = rooftop_candidates(blds, mast_height_m=3.0, min_height_m=0.0, min_area_m2=0.0, min_spacing_m=0.0)
    assert [c.building_id for c in got] == ["way/4"]
