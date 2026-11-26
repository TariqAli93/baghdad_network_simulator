"""Path-gain maps from Sionna RT on the CPU.

The ray tracer returns *path gain* only. It depends on the scene, the site,
the antenna, the frequency, the propagation settings and the grid, but not on
transmit power or bandwidth, so one map per (site, band) can be cached and
reused for every received-power, SINR and site-selection calculation.

`bns.runtime.init()` must have been called before this module is imported.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

import mitsuba as mi
from sionna.rt import PlanarArray, RadioMapSolver, Transmitter, load_scene

from bns.geospatial.grid import Grid  # noqa: F401  (re-exported for callers of this module)
from bns.propagation.engine_settings import VARIANTS as _VARIANTS

if mi.variant() not in _VARIANTS.values():
    raise ImportError("Call bns.runtime.init() before importing bns.propagation.sionna_engine.")

_TX_NAME = "site"
_solver = None

# The wedge-table workaround (see bns.propagation.engine_settings): Sionna's default of
# 10,000 slots silently drops diffracting wedges of a city scene.
from bns.propagation.engine_settings import (SIONNA_DEFAULT_WEDGE_SLOTS,  # noqa: E402,F401
                                             WEDGE_TABLE_SLOTS)


def set_wedge_table_slots(slots: int) -> None:
    """Size of the solver's wedge table (only experiments should change this)."""
    RadioMapSolver._WEDGE_INTERSECTIONS_SIZE = int(slots)


set_wedge_table_slots(WEDGE_TABLE_SLOTS)


@dataclass(frozen=True)
class Propagation:
    """Which propagation mechanisms are traced.

    max_depth counts interactions per path (0 = line of sight only). Refraction
    is off by default: buildings are opaque, as in the project methodology.
    Diffraction in a radio map is first-order and direct (site -> one wedge ->
    receiver); it is never combined with a reflection.
    """

    max_depth: int = 2
    los: bool = True
    specular_reflection: bool = True
    diffraction: bool = False
    refraction: bool = False
    diffuse_reflection: bool = False
    edge_diffraction: bool = False
    diffraction_lit_region: bool = True


@dataclass
class PathGainMap:
    mean: np.ndarray                    # linear path gain, [ny, nx]
    std_error: np.ndarray | None        # standard error of the mean across seeds
    grid: Grid
    seeds: list[int]
    samples_per_seed: int
    seconds_per_seed: list[float] = field(default_factory=list)
    per_seed: np.ndarray | None = None  # [n_seeds, ny, nx] when requested

    def summary(self) -> dict:
        return {"grid": asdict(self.grid), "seeds": self.seeds,
                "samples_per_seed": self.samples_per_seed,
                "seconds_per_seed": [round(s, 4) for s in self.seconds_per_seed]}


def open_scene(scene_xml: Path | None, frequency_hz: float, polarization: str = "V",
               pattern: str = "iso"):
    """Load a scene (or an empty one) with a single-element transmit antenna."""
    if scene_xml is None:
        scene = load_scene()
    else:
        scene = load_scene(str(scene_xml), merge_shapes=True, remove_duplicate_vertices=True)
    scene.frequency = frequency_hz
    scene.tx_array = PlanarArray(num_rows=1, num_cols=1, pattern=pattern, polarization=polarization)
    return scene


def path_gain_map(scene, tx_position, grid: Grid, propagation: Propagation,
                  samples_per_seed: int, seeds, keep_per_seed: bool = False,
                  orientation_rad=(0.0, 0.0, 0.0)) -> PathGainMap:
    """Trace one site and return the mean path gain over the given seeds.

    Rays leave the site on a deterministic Fibonacci lattice, so line-of-sight
    and specular results do not depend on the seed: their accuracy is set by
    `samples_per_seed` alone and averaging seeds does not improve them. The
    seed only drives the random parts of the solver (which wedge a diffracted
    ray uses, diffuse scattering). `std_error` therefore measures the noise of
    those random parts only.
    """
    global _solver
    if _solver is None:
        _solver = RadioMapSolver()
    if _TX_NAME in scene.transmitters:
        scene.remove(_TX_NAME)
    scene.add(Transmitter(_TX_NAME, position=[float(v) for v in tx_position], power_dbm=0.0,
                          orientation=[float(v) for v in orientation_rad]))

    seeds = [int(s) for s in seeds]
    total = np.zeros(grid.shape)
    total_sq = np.zeros(grid.shape)
    kept, seconds = [], []
    for seed in seeds:
        start = time.perf_counter()
        radio_map = _solver(
            scene,
            center=mi.Point3f(grid.center_xy[0], grid.center_xy[1], grid.height_m),
            orientation=mi.Point3f(0.0, 0.0, 0.0),
            size=mi.Point2f(grid.size_xy[0], grid.size_xy[1]),
            cell_size=mi.Point2f(grid.cell_size_m, grid.cell_size_m),
            samples_per_tx=int(samples_per_seed),
            max_depth=propagation.max_depth,
            los=propagation.los,
            specular_reflection=propagation.specular_reflection,
            diffuse_reflection=propagation.diffuse_reflection,
            refraction=propagation.refraction,
            diffraction=propagation.diffraction,
            edge_diffraction=propagation.edge_diffraction,
            diffraction_lit_region=propagation.diffraction_lit_region,
            seed=seed,
        )
        # Dr.Jit evaluates lazily: converting to NumPy is what runs the tracer.
        gain = np.asarray(radio_map.path_gain.numpy(), dtype=np.float64)[0]
        seconds.append(time.perf_counter() - start)
        if gain.shape != grid.shape:
            raise RuntimeError(f"Engine grid {gain.shape} differs from requested {grid.shape}.")
        total += gain
        total_sq += gain**2
        if keep_per_seed:
            kept.append(gain)

    k = len(seeds)
    mean = total / k
    std_error = None
    if k > 1:
        variance = np.maximum(total_sq / k - mean**2, 0.0) * k / (k - 1)
        std_error = np.sqrt(variance / k)
    return PathGainMap(mean, std_error, grid, seeds, int(samples_per_seed), seconds,
                       np.stack(kept) if keep_per_seed else None)
