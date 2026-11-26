"""Greedy base-station site selection.

At each step the candidate that newly covers the most cells is added, until the
coverage target is met or no candidate adds anything. The result is the site
count *found by the greedy algorithm*. It is not a proven minimum.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GreedyResult:
    selected: list[int]             # candidate indices in the order they were chosen
    coverage_after: list[float]     # covered share after each choice
    gain: list[float]               # share newly covered by each choice
    target_reached: bool
    uncovered_cells: np.ndarray     # indices of cells still uncovered at the end


def greedy_site_selection(covered, target_fraction: float,
                          max_sites: int | None = None) -> GreedyResult:
    """Select sites from a boolean table covered[site, cell].

    Ties are broken by the lowest candidate index, so the same input always
    gives the same answer. Candidates that would add no coverage are never
    selected; an unreachable target is reported through `target_reached`.
    """
    covered = np.asarray(covered)
    if covered.dtype != bool or covered.ndim != 2:
        raise ValueError("covered must be a boolean array of shape [sites, cells].")
    n_sites, n_cells = covered.shape
    if n_cells == 0:
        raise ValueError("There are no cells to cover.")
    if not 0.0 <= target_fraction <= 1.0:
        raise ValueError("target_fraction must be between 0 and 1.")

    is_covered = np.zeros(n_cells, dtype=bool)
    selected, coverage_after, gain = [], [], []
    limit = n_sites if max_sites is None else min(max_sites, n_sites)
    while is_covered.mean() < target_fraction and len(selected) < limit:
        new_cells = (covered & ~is_covered).sum(axis=1)
        best = int(np.argmax(new_cells))        # argmax returns the lowest index on ties
        if new_cells[best] == 0:
            break
        is_covered |= covered[best]
        selected.append(best)
        gain.append(float(new_cells[best] / n_cells))
        coverage_after.append(float(is_covered.mean()))
    return GreedyResult(selected, coverage_after, gain,
                        bool(is_covered.mean() >= target_fraction),
                        np.flatnonzero(~is_covered))
