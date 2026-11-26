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
                if b.height.height_m >= min_height_m and b.polygon.area >= min_area_m2
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
