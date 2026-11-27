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


SOURCE_KINDS = ("observation", "osm_height", "osm_levels", "dataset", "model", "placeholder")
DEFAULT_PRIORITY = SOURCE_KINDS

# Two sources "disagree" when they differ by more than max(6 m, a quarter of the chosen
# height): about two storeys for low buildings, and more than an error in the assumed
# storey height could explain for tall ones (a 55 m tower and an 80 m estimate disagree).
_CONFLICT_ABS_M = 6.0
_CONFLICT_REL = 0.25


def source_kind(source: str) -> str:
    """The kind of a HeightRecord.source, used for priorities."""
    if source.startswith("manual:"):
        return "observation"
    if source == "osm:height":
        return "osm_height"
    if source == "osm:building:levels":
        return "osm_levels"
    if source.startswith("dataset:"):
        return "dataset"
    if source.startswith("model:"):
        return "model"
    if source == "placeholder":
        return "placeholder"
    raise ValueError(f"Unknown height source {source!r}.")


@dataclass(frozen=True)
class HeightPolicy:
    """How heights are derived and chosen. Every value is a recorded assumption."""

    storey_height_m: float
    placeholder_height_m: float
    max_plausible_height_m: float
    priority: tuple[str, ...] = DEFAULT_PRIORITY    # which source wins when several exist

    def __post_init__(self):
        if sorted(self.priority) != sorted(SOURCE_KINDS) or self.priority[-1] != "placeholder":
            raise ValueError(f"priority must order all of {SOURCE_KINDS}, with placeholder last.")


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
    alternatives: tuple["HeightRecord", ...] = ()   # other valid sources, not chosen


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
    kind: str               # constant | uniform_levels | lognormal | synthetic_urban
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

    from_levels = None
    if levels is not None:
        method = f"{levels:g} levels x {policy.storey_height_m} m per storey (assumed storey height)"
        from_levels = HeightRecord(levels * policy.storey_height_m, ESTIMATED, "osm:building:levels",
                                   method, reference, original, warnings=tuple(warnings))
    if height is not None:
        return HeightRecord(height, OBSERVED, "osm:height", "value of the OSM height tag",
                            reference, original, warnings=tuple(warnings),
                            alternatives=(from_levels,) if from_levels else ())
    if from_levels is not None:
        return from_levels
    return HeightRecord(policy.placeholder_height_m, PLACEHOLDER, "placeholder",
                        f"no height information; default of {policy.placeholder_height_m} m assigned",
                        reference, original, warnings=tuple(warnings))


METHOD_CLASSES = {"measured": OBSERVED, "documented": OBSERVED, "visual_estimate": ESTIMATED,
                  "storey_count": ESTIMATED}


def _float_or_none(value):
    text = str(value if value is not None else "").strip()
    return None if text == "" else float(text)


def validate_observation(row: dict, *, storey_height_m: float | None, max_height_m: float | None):
    """(height_m, category, problems) of one observation row with a method_class.

    measured / documented heights are OBSERVED; a visual estimate or a storey count is
    ESTIMATED (storeys x the approved storey height when no height is given). Nothing is
    invented: a row with no value is skipped by the caller.
    """
    problems = []
    cls = str(row.get("method_class") or "").strip()
    if cls not in METHOD_CLASSES:
        return None, None, [f"method_class must be one of {sorted(METHOD_CLASSES)}, not {cls!r}"]
    try:
        height = _float_or_none(row.get("height_m"))
    except ValueError:
        return None, None, [f"height_m {row.get('height_m')!r} is not a number"]
    storeys = None
    if str(row.get("storeys") or "").strip():
        try:
            storeys = float(row["storeys"])
        except ValueError:
            storeys = -1.0
        if storeys <= 0 or storeys != int(storeys) or storeys > 200:
            problems.append(f"storeys {row['storeys']!r} must be a whole number between 1 and 200")
            storeys = None
    if height is None and cls == "storey_count" and storeys is not None:
        if storey_height_m is None:
            problems.append("a storey count needs the approved storey height")
        else:
            height = storeys * storey_height_m
    if height is None:
        problems.append(f"{cls} needs height_m" + (" or storeys" if cls == "storey_count" else ""))
    elif height <= 0 or (max_height_m is not None and height > max_height_m):
        problems.append(f"height {height:g} m is outside 0-{max_height_m or 'inf'} m")
    try:
        unc = _float_or_none(row.get("uncertainty_m"))
        if unc is not None and unc < 0:
            problems.append("uncertainty_m must not be negative")
    except ValueError:
        problems.append(f"uncertainty_m {row.get('uncertainty_m')!r} is not a number")
    return height, METHOD_CLASSES[cls], problems


def apply_manual_observations(buildings: list[Building], rows: list[dict], source_name: str, *,
                              storey_height_m: float | None = None,
                              max_height_m: float | None = None) -> tuple[list[Building], list[str]]:
    """Replace heights by observations made for specific buildings.

    Fieldwork rows carry `method_class` (measured | documented | visual_estimate |
    storey_count), `height_m` and/or `storeys`, `method`, `source`, `date`, `observer`,
    `uncertainty_m`, `notes`; invalid rows stop the import with every problem listed.
    Rows without `method_class` (older files) need `height_m` and `method` and are
    recorded as observed, as before. Returns the updated buildings and the ids that match
    no building. The previous record and the original values stay attached.
    """
    problems, parsed = [], {}
    for row in rows:
        has_value = any(str(row.get(k) or "").strip() for k in ("height_m", "storeys"))
        if not has_value:
            continue                                            # unfilled worklist row
        if "method_class" in row and str(row.get("method_class") or "").strip():
            height, category, issues = validate_observation(row, storey_height_m=storey_height_m,
                                                            max_height_m=max_height_m)
            problems += [f"{row.get('building_id')}: {i}" for i in issues]
        else:
            try:
                height, category = float(row["height_m"]), OBSERVED
            except (KeyError, ValueError):
                problems.append(f"{row.get('building_id')}: height_m {row.get('height_m')!r} is not a number")
                continue
            if "method_class" in row:                         # template column present but empty
                problems.append(f"{row.get('building_id')}: method_class is required")
        parsed[row["building_id"]] = (row, height, category)
    if problems:
        raise ValueError("Invalid observations:\n  " + "\n  ".join(problems))
    known = {b.building_id for b in buildings}
    updated = []
    for b in buildings:
        item = parsed.get(b.building_id)
        if item is None:
            updated.append(b)
            continue
        row, height, category = item
        cls = str(row.get("method_class") or "").strip()
        observer, date = row.get("observer", ""), row.get("date", "")
        method = (f"{cls}: " if cls else "") + str(row.get("method") or "") + (f" by {observer}" if observer else "")
        if cls == "storey_count" and not str(row.get("height_m") or "").strip():
            method += f" ({int(float(row['storeys']))} storeys x {storey_height_m:g} m)"
        reference = (f"{source_name}, {b.building_id}" + (f", {date}" if date else "")
                     + (f", source: {row['source']}" if str(row.get("source") or "").strip() else "")
                     + (f", notes: {row['notes']}" if str(row.get("notes") or "").strip() else ""))
        uncertainty = _float_or_none(row.get("uncertainty_m"))
        original = dict(b.height.original)
        if str(row.get("storeys") or "").strip():
            original["observed_storeys"] = int(float(row["storeys"]))
        earlier = _informative((b.height,) + b.height.alternatives)
        record = HeightRecord(float(height), category, f"manual:{source_name}", method.strip(),
                              reference, original, uncertainty, superseded=b.height, alternatives=earlier)
        updated.append(replace(b, height=_with_conflicts(record)))
    return updated, [i for i in parsed if i not in known]


def _informative(records) -> tuple[HeightRecord, ...]:
    """Records that carry information about the building itself (not models, not defaults)."""
    seen, kept = set(), []
    for r in records:
        if source_kind(r.source) in ("model", "placeholder") or (r.source, r.height_m) in seen:
            continue
        seen.add((r.source, r.height_m))
        kept.append(replace(r, alternatives=()))
    return tuple(kept)


def _disagrees(a: float, b: float) -> bool:
    return abs(a - b) > max(_CONFLICT_ABS_M, _CONFLICT_REL * a)


def _with_conflicts(record: HeightRecord) -> HeightRecord:
    notes = [f"sources disagree: {record.source} {record.height_m:g} m vs {alt.source} "
             f"{alt.height_m:g} m" for alt in record.alternatives
             if _disagrees(record.height_m, alt.height_m)]
    kept = [w for w in record.warnings if not w.startswith("sources disagree")]
    return replace(record, warnings=tuple(kept + notes))


def has_conflict(record: HeightRecord) -> bool:
    return any(w.startswith("sources disagree") for w in record.warnings)


def resolve(candidates: list[HeightRecord], policy: HeightPolicy) -> HeightRecord:
    """Pick the candidate whose source kind ranks first in the policy's priority.

    The others that describe the building itself are kept as alternatives, and
    a warning is added for every alternative that disagrees with the choice.
    """
    rank = {kind: i for i, kind in enumerate(policy.priority)}
    ordered = sorted(candidates, key=lambda r: rank[source_kind(r.source)])
    chosen = ordered[0]
    alternatives = _informative([r for r in ordered[1:] if r is not chosen])
    return _with_conflicts(replace(chosen, alternatives=alternatives))


def apply_candidates(buildings: list[Building], extra: dict[str, list[HeightRecord]],
                     policy: HeightPolicy) -> list[Building]:
    """Add height candidates (for example from a dataset) and re-resolve each building."""
    updated = []
    for b in buildings:
        more = extra.get(b.building_id, [])
        if not more:
            updated.append(b)
            continue
        base = replace(b.height, alternatives=())
        candidates = [base, *b.height.alternatives, *more]
        updated.append(replace(b, height=resolve(candidates, policy)))
    return updated


def observation_worklist(buildings: list[Building], candidates, *, tall_m: float,
                         near_site_m: float, blocking_share: float) -> list[dict]:
    """Buildings whose height should be observed, with the reasons.

    tall               any source gives at least tall_m
    candidate rooftop  a candidate site stands on it
    conflicting sources
    may block a candidate site
                       within near_site_m of a site and at least blocking_share of the
                       site's antenna height (by any source)
    The height columns are left empty for the observer to fill; the filled file is
    read back with apply_manual_observations.
    """
    hosts = {c.building_id for c in candidates}
    rows = []
    for b in buildings:
        heights = [b.height.height_m] + [a.height_m for a in b.height.alternatives]
        highest = max(heights)
        spot = b.polygon.representative_point()
        reasons = []
        if b.building_id in hosts:
            reasons.append("candidate rooftop")
        if highest >= tall_m:
            reasons.append("tall")
        if has_conflict(b.height):
            reasons.append("conflicting sources")
        if b.building_id not in hosts and any(
                (spot.x - c.x) ** 2 + (spot.y - c.y) ** 2 <= near_site_m**2
                and highest >= blocking_share * c.z for c in candidates):
            reasons.append("may block a candidate site")
        if reasons:
            rows.append({
                "building_id": b.building_id, "reasons": "; ".join(reasons),
                "current_height_m": round(b.height.height_m, 1), "current_source": b.height.source,
                "other_sources": "; ".join(f"{a.source} {a.height_m:g} m" for a in b.height.alternatives),
                "x_m": round(spot.x, 1), "y_m": round(spot.y, 1),
                "height_m": "", "method": "", "observer": "", "date": "", "uncertainty_m": "",
            })
    return rows


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


def synthetic_class(b: Building, params: dict) -> str:
    """Building class of the Synthetic Urban Model: from the OSM building tag when it names the use,
    otherwise from the footprint area; high-rise only with tagged evidence."""
    tag = str(b.tags.get("building", "")).strip().lower()
    area = float(b.polygon.area)
    for cls, tags in (params.get("tag_classes") or {}).items():
        if tag in tags:
            if cls == "commercial" and area >= float(params["large_commercial_min_area_m2"]):
                return "large_commercial"
            return cls
    for upper, cls in params["area_classes"]:
        if area < float(upper):
            return cls
    return params["area_classes"][-1][1]


def _triangular_inverse(u: float, mode: float) -> float:
    """Inverse CDF of the triangular distribution on [0, 1] with the given mode."""
    if mode <= 0.0:
        return 1.0 - np.sqrt(1.0 - u)
    if mode >= 1.0:
        return float(np.sqrt(u))
    return float(np.sqrt(u * mode)) if u < mode else 1.0 - float(np.sqrt((1.0 - u) * (1.0 - mode)))


def _synthetic_urban(buildings: list[Building], model: HeightModel, seed: int) -> list[Building]:
    """Synthetic Urban Model (algorithm synthetic-urban-1, configs/height_models.yaml).

    Only placeholder buildings change. Each draws one uniform number from (seed, building id) - the
    same in every scenario, so scenarios are ordered per building - maps it to whole floors through a
    triangular distribution over its class range, and moves towards the median floors of neighbours
    within the radius (known heights and other first draws), staying inside its class range.
    """
    p = model.params
    storey = float(p["storey_height_m"])
    mode = float(p["mode_position"])
    radius, weight = float(p["neighbour_radius_m"]), float(p["neighbour_weight"])
    classes = {b.building_id: synthetic_class(b, p) for b in buildings if b.height.category == PLACEHOLDER}
    first = {}
    for b in buildings:
        if b.building_id not in classes:
            continue
        lo, hi = (int(v) for v in p["classes"][classes[b.building_id]]["floors"])
        u = np.random.default_rng([int(seed), zlib.crc32(b.building_id.encode())]).random()
        first[b.building_id] = lo + min(int(_triangular_inverse(u, mode) * (hi - lo + 1)), hi - lo)
    # floors of every building for the neighbourhood: known heights and first draws
    centre = {b.building_id: b.polygon.centroid for b in buildings}
    floors = {b.building_id: first.get(b.building_id, b.height.height_m / storey) for b in buildings}
    cells: dict[tuple[int, int], list[str]] = {}
    for bid, c in centre.items():
        cells.setdefault((int(c.x // radius), int(c.y // radius)), []).append(bid)
    status = "synthetic estimate, not a measurement"
    out = []
    for b in buildings:
        if b.building_id not in classes:
            out.append(b)
            continue
        cls = classes[b.building_id]
        lo, hi = (int(v) for v in p["classes"][cls]["floors"])
        c = centre[b.building_id]
        cx, cy = int(c.x // radius), int(c.y // radius)
        near = [floors[o] for dx in (-1, 0, 1) for dy in (-1, 0, 1) for o in cells.get((cx + dx, cy + dy), [])
                if o != b.building_id and centre[o].distance(c) <= radius]
        f = first[b.building_id]
        if near:
            f = int(round((1.0 - weight) * f + weight * float(np.median(near))))
        f = int(min(max(f, lo), hi))
        method = (f"Synthetic Urban Model {p.get('version', '')} '{model.name}' ({p.get('scenario', '')} scenario), "
                  f"class {cls}, {f} floors x {storey:g} m, seed {seed}; {status}")
        record = HeightRecord(f * storey, PLACEHOLDER, f"model:{model.name}:{cls}", method,
                              b.height.reference, b.height.original, superseded=b.height)
        out.append(replace(b, height=record))
    return out


def apply_height_model(buildings: list[Building], model: HeightModel, seed: int) -> list[Building]:
    """Give every placeholder building a height drawn from an assumed distribution.

    Observed and estimated heights are left alone. The result stays in the
    placeholder category: a draw from a distribution says nothing about the
    individual building. Each building's draw depends only on the seed and its
    id, so the outcome does not change with the order or number of buildings.
    """
    if model.kind == "synthetic_urban":
        return _synthetic_urban(buildings, model, seed)
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
                        float(data["max_plausible_height_m"]),
                        tuple(data.get("priority", DEFAULT_PRIORITY)))
