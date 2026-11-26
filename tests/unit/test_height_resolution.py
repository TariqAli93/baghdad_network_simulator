"""Hybrid height resolution: priority between sources, conflicts, overrides, worklist."""

import pytest
from shapely.geometry import box

from bns.geospatial import heights as ht
from bns.geospatial.sites import Candidate

PRIORITY = ("observation", "osm_height", "osm_levels", "dataset", "model", "placeholder")
POLICY = ht.HeightPolicy(3.0, 9.0, 250.0, priority=PRIORITY)


def building(i, tags=None, size=20.0, x=0.0):
    tags = tags or {}
    return ht.Building(f"way/{i}", box(x, 0, x + size, size), tags,
                       ht.height_from_osm_tags(tags, POLICY, f"way/{i}"))


def dataset(height, i=1):
    return ht.HeightRecord(height, ht.ESTIMATED, "dataset:TestSet", "model estimate", f"rec/{i}")


def test_every_source_has_a_kind():
    assert ht.source_kind("manual:obs.csv") == "observation"
    assert ht.source_kind("osm:height") == "osm_height"
    assert ht.source_kind("osm:building:levels") == "osm_levels"
    assert ht.source_kind("dataset:3D-GloBFP v4") == "dataset"
    assert ht.source_kind("model:flat_9m") == "model"
    assert ht.source_kind("placeholder") == "placeholder"


def test_policy_rejects_an_incomplete_or_misordered_priority():
    with pytest.raises(ValueError):
        ht.HeightPolicy(3.0, 9.0, 250.0, priority=("osm_height", "placeholder"))
    with pytest.raises(ValueError):
        ht.HeightPolicy(3.0, 9.0, 250.0, priority=("placeholder",) + PRIORITY[:-1])


def test_height_tag_keeps_the_storey_estimate_as_an_alternative():
    record = building(1, {"height": "20", "building:levels": "6"}).height
    assert record.height_m == 20.0 and record.source == "osm:height"
    assert [a.source for a in record.alternatives] == ["osm:building:levels"]
    assert record.alternatives[0].height_m == 18.0


def test_dataset_fills_a_building_without_osm_height():
    [b] = ht.apply_candidates([building(1)], {"way/1": [dataset(14.0)]}, POLICY)
    assert b.height.height_m == 14.0 and b.height.category == ht.ESTIMATED
    assert b.height.source == "dataset:TestSet"


def test_priority_decides_between_storeys_and_a_dataset():
    tagged = building(1, {"building:levels": "4"})
    [levels_first] = ht.apply_candidates([tagged], {"way/1": [dataset(30.0)]}, POLICY)
    assert levels_first.height.source == "osm:building:levels"
    assert levels_first.height.alternatives[0].source == "dataset:TestSet"
    dataset_first = ht.HeightPolicy(3.0, 9.0, 250.0, priority=(
        "observation", "osm_height", "dataset", "osm_levels", "model", "placeholder"))
    [b] = ht.apply_candidates([tagged], {"way/1": [dataset(30.0)]}, dataset_first)
    assert b.height.source == "dataset:TestSet"


def test_disagreeing_sources_are_flagged_and_original_values_kept():
    [b] = ht.apply_candidates([building(1, {"height": "55"})], {"way/1": [dataset(80.0)]}, POLICY)
    assert b.height.height_m == 55.0
    assert b.height.original == {"height": "55"}
    assert ht.has_conflict(b.height)
    assert any("disagree" in w for w in b.height.warnings)


def test_small_differences_are_not_conflicts():
    [b] = ht.apply_candidates([building(1, {"height": "20"})], {"way/1": [dataset(23.0)]}, POLICY)
    assert not ht.has_conflict(b.height)


def test_observation_overrides_everything_and_keeps_all_earlier_values():
    [b] = ht.apply_candidates([building(1, {"height": "55"})], {"way/1": [dataset(80.0)]}, POLICY)
    rows = [{"building_id": "way/1", "height_m": "57", "method": "14 storeys counted, rangefinder"}]
    [observed], unmatched = ht.apply_manual_observations([b], rows, "obs.csv")
    assert observed.height.height_m == 57.0 and observed.height.category == ht.OBSERVED
    assert {a.source for a in observed.height.alternatives} == {"osm:height", "dataset:TestSet"}
    assert unmatched == []


def test_blank_rows_of_the_worklist_are_ignored():
    rows = [{"building_id": "way/1", "height_m": "", "method": ""}]
    [b], unmatched = ht.apply_manual_observations([building(1)], rows, "obs.csv")
    assert b.height.category == ht.PLACEHOLDER and unmatched == []


def test_worklist_names_tall_conflicting_site_and_blocking_buildings():
    tall = building(1, {"height": "40"})
    clash = ht.apply_candidates([building(2, {"height": "12"}, x=300)], {"way/2": [dataset(60.0)]},
                                POLICY)[0]
    near_site = building(3, {"building:levels": "5"}, x=60)        # 15 m, 50 m from the site
    far_low = building(4, x=900)
    site = Candidate("site-001", 10.0, 10.0, 43.0, "way/1", 40.0, 400.0, ht.OBSERVED)
    rows = ht.observation_worklist([tall, clash, near_site, far_low], [site], tall_m=30.0,
                                   near_site_m=100.0, blocking_share=0.3)
    reasons = {r["building_id"]: r["reasons"] for r in rows}
    assert "candidate rooftop" in reasons["way/1"] and "tall" in reasons["way/1"]
    assert "conflicting sources" in reasons["way/2"] and "tall" in reasons["way/2"]
    assert "may block a candidate site" in reasons["way/3"]
    assert "way/4" not in reasons
    assert all(r["height_m"] == "" for r in rows)                  # left for the observer
