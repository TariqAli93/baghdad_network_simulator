"""Candidate base-station positions on rooftops."""

from __future__ import annotations

from dataclasses import dataclass

from bns.geospatial.heights import Building


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    x: float
    y: float
    z: float                    # antenna height above ground = roof height + mast
    building_id: str
    roof_height_m: float
    footprint_area_m2: float
    height_category: str        # how trustworthy the roof height is


def is_structure_not_building(tags: dict) -> bool:
    """Monuments, memorials and artworks mapped as buildings: obstacles, but never transmitter sites."""
    return bool(tags.get("historic") or tags.get("memorial") or tags.get("tourism") == "artwork"
                or tags.get("man_made") in ("monument", "obelisk"))


def candidate_categories(rule_categories, height_model: dict | None) -> tuple[str, ...]:
    """Height categories eligible for candidate roofs. On a Synthetic Urban Model dataset the
    synthetic heights (category placeholder, source model:...) are eligible too: the experiment is
    a simulation on estimated building heights and every candidate keeps its height category."""
    cats = tuple(rule_categories or ("observed", "estimated"))
    if (height_model or {}).get("kind") == "synthetic_urban" and "placeholder" not in cats:
        cats += ("placeholder",)
    return cats


def rooftop_candidates(buildings: list[Building], *, mast_height_m: float, min_height_m: float,
                       min_area_m2: float, min_spacing_m: float,
                       max_candidates: int | None = None,
                       categories: tuple[str, ...] | None = None) -> list[Candidate]:
    """One candidate per eligible building, tallest first.

    A building is eligible if it is at least `min_height_m` high and
    `min_area_m2` large, and, when `categories` is given, if its height belongs
    to one of those provenance categories. Candidates closer than
    `min_spacing_m` to an already accepted (taller) one are skipped. Among
    equal heights the larger roof comes first, then the building id, so the
    result is reproducible. The antenna stands on a point inside the footprint.
    Every argument is explicit: there is no default mast height.
    """
    eligible = [b for b in buildings
                if not is_structure_not_building(b.tags or {})
                and b.height.height_m >= min_height_m and b.polygon.area >= min_area_m2
                and (categories is None or b.height.category in categories)]
    eligible.sort(key=lambda b: (-b.height.height_m, -b.polygon.area, b.building_id))

    accepted: list[Candidate] = []
    for b in eligible:
        spot = b.polygon.representative_point()
        if any((spot.x - c.x) ** 2 + (spot.y - c.y) ** 2 < min_spacing_m**2 for c in accepted):
            continue
        accepted.append(Candidate(f"site-{len(accepted) + 1:03d}", float(spot.x), float(spot.y),
                                  b.height.height_m + mast_height_m, b.building_id,
                                  b.height.height_m, float(b.polygon.area), b.height.category))
        if max_candidates is not None and len(accepted) >= max_candidates:
            break
    return accepted


def edge_positions(polygon, x: float, y: float, azimuths_rad: list[float], inset_m: float) -> list[tuple[float, float]]:
    """Antenna positions at the roof edge facing each sector (decision A4).

    For each azimuth, the point where the ray from (x, y) leaves the footprint, moved
    `inset_m` back inside. (x, y) must lie inside the footprint (a candidate's roof point).
    """
    import numpy as np
    from shapely.geometry import LineString, Point

    if not polygon.covers(Point(x, y)):
        raise ValueError("The roof point must lie inside the footprint.")
    reach = 2.0 * max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1]) + 1.0
    out = []
    for az in azimuths_rad:
        ray = LineString([(x, y), (x + reach * np.cos(az), y + reach * np.sin(az))])
        hit = ray.intersection(polygon.boundary)
        points = [hit] if hit.geom_type == "Point" else [g for g in getattr(hit, "geoms", []) if g.geom_type == "Point"]
        if not points:
            raise ValueError("The ray does not leave the footprint.")
        r = min(np.hypot(p.x - x, p.y - y) for p in points)        # first crossing of the outline
        d = max(r - inset_m, 0.0)
        out.append((float(x + d * np.cos(az)), float(y + d * np.sin(az))))
    return out


def shadowing_buildings(buildings: list[Building], antennas_xyz: list[tuple[float, float, float]],
                        receivers_xy: list[tuple[float, float]], receiver_height_m: float) -> dict[str, int]:
    """Which building first blocks the straight line from each antenna to each receiver point.

    Each building blocks with its CURRENT height (observed, estimated or placeholder), so
    the result says which buildings decide the shadows if those heights are right; it is
    the basis for prioritising observations, not a propagation result. Returns building
    id -> number of (antenna, receiver) lines it blocks first.
    """
    import numpy as np
    from shapely.geometry import LineString
    from shapely.strtree import STRtree

    polys = [b.polygon for b in buildings]
    tree = STRtree(polys)
    counts: dict[str, int] = {}
    for ax, ay, az in antennas_xyz:
        for rx, ry in receivers_xy:
            length = float(np.hypot(rx - ax, ry - ay))
            if length < 1e-6:
                continue
            seg = LineString([(ax, ay), (rx, ry)])
            first = None
            for i in tree.query(seg, predicate="intersects"):
                part = polys[i].intersection(seg)
                pieces = getattr(part, "geoms", [part])
                for piece in pieces:
                    if piece.is_empty:
                        continue
                    coords = np.asarray(piece.coords) if hasattr(piece, "coords") else np.empty((0, 2))
                    if coords.size == 0:
                        continue
                    d = float(np.min(np.hypot(coords[:, 0] - ax, coords[:, 1] - ay)))
                    z = az + (receiver_height_m - az) * d / length     # line height where it enters
                    if z < buildings[i].height.height_m and (first is None or d < first[0]):
                        first = (d, buildings[i].building_id)
            if first is not None:
                counts[first[1]] = counts.get(first[1], 0) + 1
    return counts
