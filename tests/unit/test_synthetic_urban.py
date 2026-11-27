"""Synthetic Urban Model: reproducible, plausible estimated heights for buildings without any height."""

from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from bns.geospatial import heights as ht

ROOT = Path(__file__).resolve().parents[2]
MODELS = ht.load_height_models(ROOT / "configs" / "height_models.yaml")


def building(bid, x, y, size, tags=None, height=None):
    if height is None:
        rec = ht.HeightRecord(9.0, ht.PLACEHOLDER, "placeholder", "no height information", f"test {bid}")
    else:
        rec = ht.HeightRecord(height, ht.OBSERVED, "osm:height", "value of the OSM height tag", f"test {bid}")
    return ht.Building(bid, box(x, y, x + size, y + size), tags or {"building": "yes"}, rec)


def town():
    out = [building(f"way/{i}", (i % 10) * 30.0, (i // 10) * 30.0, s)
           for i, s in enumerate([6, 9, 12, 15, 20, 25, 30, 40, 60, 8] * 4)]
    out += [building("way/house", 400, 0, 10, {"building": "house"}),
            building("way/tower", 420, 0, 30, {"building": "tower"}),
            building("way/apart", 460, 0, 20, {"building": "apartments"}),
            building("way/known", 30, 30, 20, height=55.0)]
    return out


def test_the_baseline_model_is_reproducible_and_order_independent():
    model = MODELS["synthetic_urban"]
    a = {b.building_id: b.height.height_m for b in ht.apply_height_model(town(), model, 42)}
    b = {b.building_id: b.height.height_m for b in ht.apply_height_model(list(reversed(town())), model, 42)}
    assert a == b
    c = {b.building_id: b.height.height_m for b in ht.apply_height_model(town(), model, 7)}
    assert a != c                                                   # the seed matters


def test_known_heights_are_never_overwritten_and_synthetic_ones_are_never_measurements():
    out = {b.building_id: b for b in ht.apply_height_model(town(), MODELS["synthetic_urban"], 42)}
    assert out["way/known"].height.height_m == 55.0 and out["way/known"].height.category == ht.OBSERVED
    for b in out.values():
        if b.building_id != "way/known":
            assert b.height.category == ht.PLACEHOLDER                # an assumption, not an observation
            assert b.height.source.startswith("model:synthetic_urban:")
            assert "synthetic" in b.height.method and "measured" not in b.height.method


def test_heights_follow_the_class_floor_ranges_in_whole_storeys():
    model = MODELS["synthetic_urban"]
    classes = model.params["classes"]
    for b in ht.apply_height_model(town(), model, 42):
        if b.building_id == "way/known":
            continue
        cls = b.height.source.split(":")[2]
        lo, hi = classes[cls]["floors"]
        floors = b.height.height_m / model.params["storey_height_m"]
        assert floors == int(floors) and lo <= floors <= hi, (b.building_id, cls, floors)


def test_classification_uses_tags_and_footprint_and_high_rise_needs_evidence():
    out = {b.building_id: b.height.source.split(":")[2]
           for b in ht.apply_height_model(town(), MODELS["synthetic_urban"], 42) if b.building_id != "way/known"}
    assert out["way/house"] == "small_residential"
    assert out["way/apart"] == "apartments"
    assert out["way/tower"] == "high_rise"                          # tagged evidence
    untagged = [c for bid, c in out.items() if bid.startswith("way/") and bid[4:].isdigit()]
    assert "high_rise" not in untagged                              # never from footprint size alone
    assert out["way/0"] == "small_residential"                     # 36 m2
    assert out["way/8"] in ("apartments", "large_commercial", "commercial")   # 3600 m2


def test_low_baseline_high_scenarios_are_ordered_per_building_on_the_same_geometry():
    t = town()
    low, base, high = ({b.building_id: b.height.height_m for b in ht.apply_height_model(t, MODELS[m], 42)}
                       for m in ("synthetic_urban_low", "synthetic_urban", "synthetic_urban_high"))
    assert all(low[k] <= base[k] <= high[k] for k in base)
    assert np.mean(list(low.values())) < np.mean(list(base.values())) < np.mean(list(high.values()))


def test_neighbourhood_smoothing_pulls_heights_towards_neighbours_within_the_class_range():
    model = MODELS["synthetic_urban"]
    tall = [building(f"way/n{i}", 10.0 * i, 0, 9, {"building": "apartments"}) for i in range(8)]
    target = building("way/t", 40, 15, 9, {"building": "residential"})
    tall = [ht.Building(b.building_id, b.polygon, b.tags,
                        ht.HeightRecord(24.0, ht.ESTIMATED, "osm:building:levels", "8 levels", "t")) for b in tall]
    smoothed = {b.building_id: b for b in ht.apply_height_model(tall + [target], model, 42)}["way/t"]
    alone = {b.building_id: b for b in ht.apply_height_model([target], model, 42)}["way/t"]
    assert smoothed.height.height_m >= alone.height.height_m
    assert smoothed.height.height_m <= 4 * model.params["storey_height_m"]   # stays a standard residential


@pytest.mark.parametrize("name", ["synthetic_urban", "synthetic_urban_low", "synthetic_urban_high"])
def test_the_three_scenarios_are_configured_with_the_same_classes(name):
    assert MODELS[name].kind == "synthetic_urban"
    assert MODELS[name].params["classes"] == MODELS["synthetic_urban"].params["classes"]
