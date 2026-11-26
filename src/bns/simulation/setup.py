"""Turn a site, a profile and the radio configuration into propagation jobs.

Shared by every experiment script so that all of them describe a run the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from bns.analysis.radio_system import RadioSystem
from bns.geospatial.grid import Grid
from bns.propagation.engine_settings import engine_fingerprint
from bns.simulation.cache import scene_fingerprint
from bns.simulation.jobs import Antenna, Mechanisms, PropagationJob


@dataclass(frozen=True)
class Profile:
    name: str
    cell_size_m: float
    rays_per_site: int


@dataclass(frozen=True)
class SimulationConfig:
    profiles: dict
    mechanisms: Mechanisms
    seeds: tuple[int, ...]
    polarization: str

    @classmethod
    def load(cls, path: Path) -> "SimulationConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        profiles = {}
        for name, p in data["profiles"].items():
            if p.get("rays_per_site") is None:
                continue                    # not yet determined
            profiles[name] = Profile(name, float(p["cell_size_m"]), int(float(p["rays_per_site"])))
        return cls(profiles, Mechanisms(**data["mechanisms"]), tuple(data["seeds"]),
                   data["polarization"])

    def profile(self, name: str) -> Profile:
        if name not in self.profiles:
            raise KeyError(f"Profile '{name}' is not defined or not yet determined.")
        return self.profiles[name]


def sector_antennas(system: RadioSystem, *, mode: str, polarization: str) -> list[Antenna]:
    """One traced antenna per sector, evenly spaced in azimuth, all with the same downtilt."""
    pattern = system.require("tx_antenna_pattern", mode=mode)
    if pattern == "iso":
        return [Antenna("iso", polarization, (0.0, 0.0, 0.0))]
    sectors = int(system.require("sectors_per_site", mode=mode))
    tilt = np.radians(system.require("mechanical_downtilt_deg", mode=mode))
    return [Antenna(pattern, polarization, (float(2 * np.pi * k / sectors), float(tilt), 0.0))
            for k in range(sectors)]


def site_jobs(scene_dir: Path | None, frequency_hz: float, position_m, antennas: list[Antenna],
              grid: Grid, config: SimulationConfig, rays_per_site: int) -> list[PropagationJob]:
    """One propagation job per antenna (sector) of one site at one frequency."""
    fingerprint = scene_fingerprint(scene_dir)
    engine = engine_fingerprint()
    return [PropagationJob(fingerprint, None if scene_dir is None else str(scene_dir),
                           float(frequency_hz), tuple(float(v) for v in position_m), antenna, grid,
                           config.mechanisms, int(rays_per_site), config.seeds, engine)
            for antenna in antennas]
