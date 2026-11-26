"""Building heights with provenance.

Every building carries a HeightRecord that says where its height came from:

    observed     reported for this building by a source (an OSM `height` tag,
                 a manual observation, a per-building dataset)
    estimated    derived for this building from other information about it
                 (number of storeys times an assumed storey height)
    placeholder  assigned without any information about this building
                 (a default value, or a draw from an assumed distribution)

A placeholder is never presented as an estimate, and an estimate never as an
observation. Original source values are kept in the record and are not
overwritten when a better source replaces the height.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import yaml
from shapely.geometry import Polygon

OBSERVED = "observed"
ESTIMATED = "estimated"
PLACEHOLDER = "placeholder"
CATEGORIES = (OBSERVED, ESTIMATED, PLACEHOLDER)

_HEIGHT_TAGS = ("height", "building:levels")
_NUMBER = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(m|meters|metres)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class HeightPolicy:
    """How OSM tags are turned into heights. Every value is a recorded assumption."""

    storey_height_m: float
    placeholder_height_m: float
    max_plausible_height_m: float


@dataclass(frozen=True)
class HeightRecord:
    height_m: float
    category: str                       # observed | estimated | placeholder
    source: str                         # e.g. "osm:height", "manual:<file>", "model:<name>"
    method: str                         # how the value was obtained, in words
    reference: str                      # where to find the original (object id, snapshot, file)
    original: dict = field(default_factory=dict)    # untouched source values (OSM tags)
    uncertainty_m: float | None = None  # only when the source states one
    warnings: tuple[str, ...] = ()
    superseded: "HeightRecord | None" = None        # the record this one replaced


@dataclass(frozen=True)
class Building:
    building_id: str
    polygon: Polygon        # local metres
    tags: dict
    height: HeightRecord


@dataclass(frozen=True)
class HeightModel:
    """An assumed height distribution for buildings without any height information."""

    name: str
    kind: str               # constant | uniform_levels | lognormal
    params: dict
    approved: bool          # approved by the supervisor for thesis results
    rationale: str = ""


def _number(text) -> float | None:
    match = _NUMBER.match(str(text)) if text is not None else None
    return float(match.group(1)) if match else None


def height_from_osm_tags(tags: dict, policy: HeightPolicy, building_id: str,
                         snapshot: str = "") -> HeightRecord:
    """Height record from the `height` and `building:levels` tags of one OSM building."""
    original = {key: tags[key] for key in _HEIGHT_TAGS if key in tags}
    reference = f"OpenStreetMap {building_id}" + (f", snapshot {snapshot[:12]}" if snapshot else "")
    warnings: list[str] = []
    height = _number(tags.get("height"))
    levels = _number(tags.get("building:levels"))
    if "height" in tags and (height is None or not 0.0 < height <= policy.max_plausible_height_m):
        warnings.append(f"implausible height={tags['height']!r} ignored")
        height = None
    if "building:levels" in tags and (
            levels is None
            or not 0.0 < levels * policy.storey_height_m <= policy.max_plausible_height_m):
        warnings.append(f"implausible building:levels={tags['building:levels']!r} ignored")
        levels = None
    if height is not None and levels is not None:
        from_levels = levels * policy.storey_height_m
        if abs(height - from_levels) > max(6.0, 0.5 * from_levels):
            warnings.append(f"height={height:g} m contradicts building:levels={levels:g}")

    if height is not None:
        return HeightRecord(height, OBSERVED, "osm:height", "value of the OSM height tag",
                            reference, original, warnings=tuple(warnings))
    if levels is not None:
        method = f"{levels:g} levels x {policy.storey_height_m} m per storey (assumed storey height)"
        return HeightRecord(levels * policy.storey_height_m, ESTIMATED, "osm:building:levels",
                            method, reference, original, warnings=tuple(warnings))
    return HeightRecord(policy.placeholder_height_m, PLACEHOLDER, "placeholder",
                        f"no height information; default of {policy.placeholder_height_m} m assigned",
                        reference, original, warnings=tuple(warnings))


def apply_manual_observations(buildings: list[Building], rows: list[dict],
                              source_name: str) -> tuple[list[Building], list[str]]:
    """Replace heights by observations made for specific buildings.

    Each row needs `building_id`, `height_m` and `method`; `observer`, `date`
    and `uncertainty_m` are optional. Returns the updated buildings and the
    ids in `rows` that match no building. The previous record and the original
    OSM values stay attached to the new record.
    """
    by_id = {row["building_id"]: row for row in rows}
    known = {b.building_id for b in buildings}
    updated = []
    for b in buildings:
        row = by_id.get(b.building_id)
        if row is None:
            updated.append(b)
            continue
        observer, date = row.get("observer", ""), row.get("date", "")
        method = row["method"] + (f" by {observer}" if observer else "")
        reference = f"{source_name}, {b.building_id}" + (f", {date}" if date else "")
        uncertainty = float(row["uncertainty_m"]) if row.get("uncertainty_m") not in (None, "") else None
        record = HeightRecord(float(row["height_m"]), OBSERVED, f"manual:{source_name}", method,
                              reference, b.height.original, uncertainty, superseded=b.height)
        updated.append(replace(b, height=record))
    return updated, [i for i in by_id if i not in known]


def _draw(model: HeightModel, rng: np.random.Generator) -> float:
    p = model.params
    if model.kind == "constant":
        return float(p["height_m"])
    if model.kind == "uniform_levels":
        levels = rng.integers(int(p["min_levels"]), int(p["max_levels"]) + 1)
        return float(levels * float(p["storey_height_m"]))
    if model.kind == "lognormal":
        value = float(p["median_m"]) * np.exp(float(p["sigma"]) * rng.standard_normal())
        return float(np.clip(value, float(p["min_m"]), float(p["max_m"])))
    raise ValueError(f"Unknown height model kind {model.kind!r}.")


def apply_height_model(buildings: list[Building], model: HeightModel, seed: int) -> list[Building]:
    """Give every placeholder building a height drawn from an assumed distribution.

    Observed and estimated heights are left alone. The result stays in the
    placeholder category: a draw from a distribution says nothing about the
    individual building. Each building's draw depends only on the seed and its
    id, so the outcome does not change with the order or number of buildings.
    """
    if model.kind not in ("constant", "uniform_levels", "lognormal"):
        raise ValueError(f"Unknown height model kind {model.kind!r}.")
    status = "approved" if model.approved else "not approved"
    updated = []
    for b in buildings:
        if b.height.category != PLACEHOLDER:
            updated.append(b)
            continue
        rng = np.random.default_rng([int(seed), zlib.crc32(b.building_id.encode())])
        method = (f"assigned from height model '{model.name}' ({model.kind}, {model.params}), "
                  f"seed {seed}; model {status} by the supervisor")
        record = HeightRecord(_draw(model, rng), PLACEHOLDER, f"model:{model.name}", method,
                              b.height.reference, b.height.original, superseded=b.height)
        updated.append(replace(b, height=record))
    return updated


def load_height_models(path: Path) -> dict[str, HeightModel]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {name: HeightModel(name, entry["kind"], dict(entry["params"]), bool(entry["approved"]),
                              entry.get("rationale", ""))
            for name, entry in data["height_models"].items()}


def load_height_policy(path: Path) -> HeightPolicy:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["height_policy"]
    return HeightPolicy(float(data["storey_height_m"]), float(data["placeholder_height_m"]),
                        float(data["max_plausible_height_m"]))
