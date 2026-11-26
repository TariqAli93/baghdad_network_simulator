"""Reading GlobalBuildingAtlas LoD1 records and joining them to OSM buildings by id."""

from bns.geospatial import gba

TILE = ('{"osm111IRQ": {"height": 12.5, "var": 3.25}, "osm222_1IRQ": {"height": 4.0, "var": 0.5}, '
        '"osm222_2IRQ": {"height": 6.0, "var": null}, "msIraq_122113311_7IRQ": {"height": 9.0, "var": 1.0}, '
        '"osm333SYR": {"height": 30.0, "var": 2.0}}')


def test_only_osm_records_are_read_with_their_values(tmp_path):
    path = tmp_path / "tile.json"
    path.write_text(TILE, encoding="utf-8")
    records = gba.read_osm_records(path)
    assert set(records) == {"osm111IRQ", "osm222_1IRQ", "osm222_2IRQ", "osm333SYR"}
    assert records["osm111IRQ"] == (12.5, 3.25) and records["osm222_2IRQ"] == (6.0, None)


def test_lookup_joins_ways_and_their_parts_but_not_relations_or_other_countries(tmp_path):
    path = tmp_path / "tile.json"
    path.write_text(TILE, encoding="utf-8")
    records = gba.read_osm_records(path)
    assert gba.lookup(records, "way/111") == [("osm111IRQ", 12.5, 3.25)]
    assert gba.lookup(records, "way/111#p2") == [("osm111IRQ", 12.5, 3.25)]     # repaired piece
    assert [k for k, *_ in gba.lookup(records, "way/222")] == ["osm222_1IRQ", "osm222_2IRQ"]
    assert gba.lookup(records, "relation/111") == []                            # ambiguous number
    assert gba.lookup(records, "way/333") == []                                 # Syrian record
    assert gba.osm_number("node/5") is None


def test_height_records_are_estimates_with_their_provenance(tmp_path):
    from shapely.geometry import box

    from bns.geospatial import heights as ht

    records = {"osm111IRQ": (12.5, 3.25), "osm222_1IRQ": (4.0, 0.5), "osm222_2IRQ": (6.0, None)}
    rec = ht.HeightRecord(9.0, ht.PLACEHOLDER, "placeholder", "default", "x")
    buildings = [ht.Building(i, box(0, 0, 1, 1), {}, rec) for i in ("way/111", "way/222", "way/999")]
    out = gba.height_records(buildings, records, "GlobalBuildingAtlas", "GBA tile")
    assert set(out) == {"way/111", "way/222"}
    [r] = out["way/222"]
    assert r.height_m == 5.0 and r.category == ht.ESTIMATED and r.source == "dataset:GlobalBuildingAtlas"
    assert "osm222_1IRQ" in r.reference and r.original["dataset_var"] == [0.5, None]
