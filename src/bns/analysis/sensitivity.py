"""What a set of path-gain maps says about coverage, for comparing scene variants.

Works on path gain only. Coverage is expressed through a maximum allowed path
loss, which stands for "transmit power plus antenna gains minus the required
received power". That combination is a radio-system decision, so the caller
supplies one or more thresholds; none is built in.
"""

from __future__ import annotations

import numpy as np

from bns.core.units import linear_to_db
from bns.optimization.greedy import greedy_site_selection


def summarise_variant(gain_los, gain_reflected, gain_full, outdoor, *, thresholds_db,
                      coverage_target: float) -> dict:
    """Summary of one variant from three stacks of maps, each shaped [site, y, x].

    gain_los        line of sight only
    gain_reflected  line of sight + reflections
    gain_full       line of sight + reflections + diffraction
    outdoor         boolean [y, x]; only these cells count
    """
    los, reflected, full = (np.asarray(a, dtype=float) for a in (gain_los, gain_reflected, gain_full))
    outdoor = np.asarray(outdoor, dtype=bool)
    if not (los.shape == reflected.shape == full.shape) or full.shape[1:] != outdoor.shape:
        raise ValueError("The three stacks must share one shape [site, y, x] matching the mask.")
    los, reflected, full = los[:, outdoor], reflected[:, outdoor], full[:, outdoor]   # [site, cell]
    n_cells = full.shape[1]

    best_los, best_reflected, best_full = los.max(axis=0), reflected.max(axis=0), full.max(axis=0)
    reached = best_full > 0
    loss_db = -linear_to_db(best_full[reached])
    p5, p50, p95 = np.percentile(loss_db, [5, 50, 95]) if reached.any() else (np.nan,) * 3

    site_loss_db = -linear_to_db(full)                 # inf where a site does not reach a cell
    coverage = []
    for threshold in thresholds_db:
        covered = site_loss_db <= threshold
        greedy = greedy_site_selection(covered, coverage_target)
        coverage.append({
            "max_path_loss_db": float(threshold),
            "coverage_all_sites": float(covered.any(axis=0).mean()),
            "coverage_target": coverage_target,
            "target_reached": greedy.target_reached,
            "greedy_sites": greedy.selected,
            "greedy_coverage_after": greedy.coverage_after,
        })

    return {
        "sites": int(full.shape[0]),
        "outdoor_cells": int(n_cells),
        "los_fraction_per_site": (los > 0).mean(axis=1).tolist(),
        "los_fraction_any_site": float((best_los > 0).mean()),
        "shadow_fraction_per_site": (full <= 0).mean(axis=1).tolist(),
        "shadow_fraction_all_sites": float((~reached).mean()),
        "reflection_only_fraction": float(((best_reflected > 0) & (best_los <= 0)).mean()),
        "diffraction_only_fraction": float((reached & (best_reflected <= 0)).mean()),
        "best_path_loss_db": {"p5": float(p5), "median": float(p50), "p95": float(p95),
                              "reached_cells": int(reached.sum())},
        "coverage": coverage,
    }
