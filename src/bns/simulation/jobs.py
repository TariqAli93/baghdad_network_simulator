"""A propagation job: everything the ray tracer's result depends on, and nothing else.

Radio-system parameters (transmit power, gains, noise, bandwidth, thresholds) are
deliberately absent: they are applied afterwards to the cached path gain, so
changing them never triggers new ray tracing. Anything that changes the path
gain must be a field here, because the cache key is computed from these fields.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from bns.geospatial.grid import Grid


@dataclass(frozen=True)
class Antenna:
    """Transmit antenna as seen by the ray tracer (pattern and orientation shape the path gain)."""

    pattern: str                    # "iso" (isotropic); Sionna also offers "dipole", "tr38901"
    polarization: str               # "V" or "H"
    orientation_rad: tuple[float, float, float]


@dataclass(frozen=True)
class Mechanisms:
    max_depth: int                  # interactions per path; 0 = line of sight only
    los: bool
    specular_reflection: bool
    diffraction: bool
    refraction: bool
    diffuse_reflection: bool
    edge_diffraction: bool


@dataclass(frozen=True)
class PropagationJob:
    scene_fingerprint: str          # hash of scene.xml and meshes (geometry, heights, materials)
    scene_dir: str | None           # where the scene is now; not part of the key
    frequency_hz: float
    tx_position_m: tuple[float, float, float]
    antenna: Antenna
    grid: Grid
    mechanisms: Mechanisms
    rays_per_site: int
    seeds: tuple[int, ...]
    engine: dict = field(default_factory=dict)    # versions and settings that affect results

    def key_fields(self) -> dict:
        return {
            "scene": self.scene_fingerprint,
            "frequency_hz": float(self.frequency_hz),
            "tx_position_m": [round(float(v), 4) for v in self.tx_position_m],
            "antenna": asdict(self.antenna),
            "grid": {"center_xy": [round(float(v), 4) for v in self.grid.center_xy],
                     "size_xy": [float(v) for v in self.grid.size_xy],
                     "cell_size_m": float(self.grid.cell_size_m),
                     "height_m": float(self.grid.height_m)},
            "mechanisms": asdict(self.mechanisms),
            "rays_per_site": int(self.rays_per_site),
            "seeds": [int(s) for s in self.seeds],
            "engine": dict(sorted(self.engine.items())),
        }

    def key(self) -> str:
        canonical = json.dumps(self.key_fields(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {"scene_dir": self.scene_dir, **self.key_fields(),
                "scene_fingerprint": self.scene_fingerprint}

    @classmethod
    def from_dict(cls, d: dict) -> "PropagationJob":
        g = d["grid"]
        return cls(
            scene_fingerprint=d["scene_fingerprint"], scene_dir=d["scene_dir"],
            frequency_hz=float(d["frequency_hz"]), tx_position_m=tuple(d["tx_position_m"]),
            antenna=Antenna(d["antenna"]["pattern"], d["antenna"]["polarization"],
                            tuple(d["antenna"]["orientation_rad"])),
            grid=Grid(tuple(g["center_xy"]), tuple(g["size_xy"]), g["cell_size_m"], g["height_m"]),
            mechanisms=Mechanisms(**d["mechanisms"]), rays_per_site=int(d["rays_per_site"]),
            seeds=tuple(d["seeds"]), engine=dict(d["engine"]))
