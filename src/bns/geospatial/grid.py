"""Horizontal receiver grids and the outdoor mask. Pure geometry: no ray-tracing imports."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shapely


@dataclass(frozen=True)
class Grid:
    """Horizontal receiver grid. Arrays are indexed [y, x]."""

    center_xy: tuple[float, float]
    size_xy: tuple[float, float]
    cell_size_m: float
    height_m: float = 1.5

    @property
    def shape(self) -> tuple[int, int]:
        return (int(np.ceil(self.size_xy[1] / self.cell_size_m)),
                int(np.ceil(self.size_xy[0] / self.cell_size_m)))

    @property
    def x_centers(self) -> np.ndarray:
        n = self.shape[1]
        return self.center_xy[0] + (np.arange(n) - (n - 1) / 2.0) * self.cell_size_m

    @property
    def y_centers(self) -> np.ndarray:
        n = self.shape[0]
        return self.center_xy[1] + (np.arange(n) - (n - 1) / 2.0) * self.cell_size_m


def footprint_mask(x_centers, y_centers, cell_size_m: float, footprints) -> np.ndarray:
    """True for every square cell that touches any footprint; shape [y, x]."""
    xs, ys = np.meshgrid(np.asarray(x_centers, float), np.asarray(y_centers, float))
    half = cell_size_m / 2.0
    cells = shapely.box(xs.ravel() - half, ys.ravel() - half, xs.ravel() + half, ys.ravel() + half)
    touched = np.zeros(cells.shape, dtype=bool)
    footprints = list(footprints)
    if footprints:
        hit_cells, _ = shapely.STRtree(footprints).query(cells, predicate="intersects")
        touched[np.unique(hit_cells)] = True
    return touched.reshape(xs.shape)


def outdoor_mask(grid: Grid, footprints) -> np.ndarray:
    """True for every cell that touches no building footprint; shape [y, x].

    A cell that only partly overlaps a building is treated as indoor, so that
    outdoor statistics never include energy computed inside a building.
    """
    return ~footprint_mask(grid.x_centers, grid.y_centers, grid.cell_size_m, footprints)
