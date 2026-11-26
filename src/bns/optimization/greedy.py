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


@dataclass(frozen=True)
class SinrGreedyResult:
    selected: list[int]             # candidate indices in the order they were chosen
    coverage_after: list[float]     # SINR coverage of the whole selection after each choice
    evaluations: list[dict]         # per step: coverage the selection would have with each candidate
    degrading_additions: list[dict]  # evaluated additions that would have LOWERED coverage
    target_reached: bool
    stopped_because: str


def greedy_sinr_site_selection(coverage_of, n_candidates: int, target_fraction: float,
                               max_sites: int | None = None) -> SinrGreedyResult:
    """Greedy selection on the coverage of the WHOLE network, interference included.

    coverage_of(selection) must return the covered share of outdoor cells when
    exactly the sites in `selection` (a tuple of candidate indices) transmit, with
    every selected sector interfering (bns.simulation.network). Unlike
    greedy_site_selection this is not a union of coverage masks: a candidate that
    adds more interference than service lowers coverage, and such additions are
    reported in `degrading_additions`. At each step the candidate giving the highest
    network coverage is added; ties go to the lowest index. The search stops when
    the target is met, the site limit is reached, or no candidate raises coverage.
    The result is what the greedy heuristic found, not a proven minimum.
    """
    if n_candidates <= 0:
        raise ValueError("There are no candidates.")
    if not 0.0 <= target_fraction <= 1.0:
        raise ValueError("target_fraction must be between 0 and 1.")
    limit = n_candidates if max_sites is None else min(max_sites, n_candidates)
    selected: list[int] = []
    coverage_after: list[float] = []
    evaluations: list[dict] = []
    degrading: list[dict] = []
    current = 0.0
    stopped = "candidates exhausted"
    while True:
        if selected and current >= target_fraction:
            stopped = "target reached"
            break
        if len(selected) >= limit:
            stopped = "site limit reached" if len(selected) < n_candidates else "candidates exhausted"
            break
        trial = {c: float(coverage_of(tuple(selected + [c])))
                 for c in range(n_candidates) if c not in selected}
        evaluations.append({"step": len(selected) + 1, "before": current, "coverage_with": trial})
        if selected:
            degrading += [{"step": len(selected) + 1, "candidate": c, "change": v - current}
                          for c, v in trial.items() if v < current]
        best = min(trial, key=lambda c: (-trial[c], c))
        if selected and trial[best] <= current:
            stopped = "no candidate raises coverage"
            break
        selected.append(best)
        current = trial[best]
        coverage_after.append(current)
    return SinrGreedyResult(selected, coverage_after, evaluations, degrading,
                            bool(selected) and current >= target_fraction, stopped)
