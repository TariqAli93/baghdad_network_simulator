"""GlobalBuildingAtlas (GBA.LoD1) heights for OpenStreetMap buildings.

A GBA.LoD1 tile is one JSON object mapping a building key to {"height", "var"}.
Keys name the footprint source: "osm<way id><ISO3>" for OpenStreetMap ways,
"osm<id>_<part><ISO3>" for parts, "ms<Country>_<quadkey>_<n><ISO3>" for Microsoft
footprints, "ours..." for footprints derived by the GBA authors. The tile holds
no geometry: footprints are in GBA.Polygon (Microsoft and OSM in the ODbL part).
So without a polygon file only OSM buildings can be given a GBA height, by id.

"var" is passed through unchanged; the dataset card does not define it.
"""

from __future__ import annotations

import re
from pathlib import Path

_RECORD = re.compile(r'"(osm\d+(?:_\d+)?[A-Z]{3})": \{"height": ([-+0-9.eE]+|null), "var": ([-+0-9.eE]+|null)\}')


def osm_number(building_id: str) -> tuple[str, str] | None:
    """('way'|'relation', id) of an OSM building id such as 'way/123' or 'way/123#p2'."""
    m = re.fullmatch(r"(way|relation)/(\d+)(?:#p\d+)?", building_id)
    return (m.group(1), m.group(2)) if m else None


def read_osm_records(path: Path) -> dict[str, tuple[float | None, float | None]]:
    """Every OSM-sourced record of a tile: key -> (height m, var)."""
    text = Path(path).read_text(encoding="utf-8")
    out = {}
    for key, h, v in _RECORD.findall(text):
        out[key] = (None if h == "null" else float(h), None if v == "null" else float(v))
    return out


def lookup(records: dict, building_id: str, country: str = "IRQ") -> list[tuple[str, float | None, float | None]]:
    """GBA records of one OSM building: the way itself, or the numbered parts of that id.

    GBA keys carry the bare OSM number without the element type, so a relation and a
    way with the same number cannot be told apart; relations are therefore not looked up.
    """
    parsed = osm_number(building_id)
    if parsed is None or parsed[0] != "way":
        return []
    number = parsed[1]
    exact = f"osm{number}{country}"
    if exact in records:
        return [(exact, *records[exact])]
    prefix = f"osm{number}_"
    return sorted((k, *records[k]) for k in records if k.startswith(prefix) and k.endswith(country))


def load_extract_records(path: Path) -> dict[str, tuple[float | None, float | None]]:
    """GBA key -> (height, var) from a study-area extract written by scripts/evaluate_gba.py."""
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {r["key"]: (r["height"], r["var"]) for rows in data.values() for r in rows}


def height_records(buildings, records: dict, dataset: str, reference: str) -> dict:
    """building id -> [HeightRecord] (estimated) for the buildings GBA has a height for."""
    import numpy as np

    from bns.geospatial import heights as ht

    out = {}
    for b in buildings:
        found = [(k, h, v) for k, h, v in lookup(records, b.building_id) if h is not None]
        if not found:
            continue
        value = float(np.median([h for _, h, _ in found]))
        out[b.building_id] = [ht.HeightRecord(
            round(value, 2), ht.ESTIMATED, f"dataset:{dataset}",
            f"{dataset} model height joined by OSM way id"
            + (f"; median of {len(found)} parts" if len(found) > 1 else ""),
            f"{reference}; {', '.join(k for k, _, _ in found)}",
            {"dataset_height_m": value, "dataset_var": [v for _, _, v in found]})]
    return out
