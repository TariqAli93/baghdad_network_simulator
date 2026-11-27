"""The propagation scope a piece of validation evidence covers.

Validation (MATLAB cross-check, convergence on the final scene) checks the traced path gain. The
path gain depends on: the scene (geometry, heights, height model: its fingerprint), the receiver
grid (extent, cell size, receiver height), the ray count, the engine (variant, versions,
settings), the transmit antennas (pattern, polarisation, bearings, downtilt), the propagation
mechanisms and the seeds. Evidence applies to a run only when all of these are identical.

Radio-system quantities computed afterwards from the path gain (transmit power, noise figure,
coverage threshold and target, load, rate mappings, rain) do not change the path gain, so
evidence carries over across them without revalidation. Site positions are not part of the
scope: the evidence characterises the engine on this scene and settings, not one transmitter.
"""

from __future__ import annotations

import hashlib
import json

from bns.propagation.engine_settings import WEDGE_TABLE_SLOTS


def _r(v):
    return [round(float(x), 6) for x in v] if isinstance(v, (list, tuple)) else round(float(v), 6)


def scope(*, scene_fingerprint: str, grid: dict, rays_per_site: int, engine: dict, antennas: list[dict],
          mechanisms: dict, seeds) -> dict:
    return {"scene_fingerprint": scene_fingerprint,
            "grid": {k: _r(grid[k]) for k in ("center_xy", "size_xy", "cell_size_m", "height_m")},
            "rays_per_site": int(rays_per_site),
            "engine": {k: engine.get(k) for k in ("sionna-rt", "mitsuba", "drjit", "variant", "wedge_table_slots")},
            "antennas": [{"pattern": a["pattern"], "polarization": a["polarization"],
                          "orientation_rad": _r(a["orientation_rad"])} for a in antennas],
            "mechanisms": dict(sorted(mechanisms.items())), "seeds": [int(s) for s in seeds]}


def key(s: dict | None) -> str:
    if not s:
        return ""
    return hashlib.sha256(json.dumps(s, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def from_manifest(m: dict) -> dict | None:
    """The scope of a saved run, or None when its record lacks a propagation input."""
    try:
        versions, backend = m["versions"], m["backend"]
        engine = {"sionna-rt": versions["sionna-rt"], "mitsuba": versions["mitsuba"], "drjit": versions["drjit"],
                  "variant": backend["variant"], "wedge_table_slots": WEDGE_TABLE_SLOTS}
        return scope(scene_fingerprint=m["area"]["scene_fingerprint"], grid=m["grid"],
                     rays_per_site=m["profile"]["rays_per_site"], engine=engine,
                     antennas=m["sectors_per_site"], mechanisms=m["mechanisms"], seeds=m["seeds"])
    except (KeyError, TypeError):
        return None
