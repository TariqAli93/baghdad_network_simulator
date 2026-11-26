"""Summary statistics of maps: coverage, percentiles, distributions, RMSE.

A `mask` selects the receiver cells that count (outdoor cells). Cells without
signal are never dropped silently: they count as uncovered, and as zero-rate
users in percentiles.
"""

from __future__ import annotations

import numpy as np


def _select(values, mask) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if mask is None:
        return values.ravel()
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != values.shape:
        raise ValueError("mask and values must have the same shape.")
    return values[mask]


def coverage_fraction(values, threshold: float, mask=None) -> float:
    """Share of selected cells whose value is at or above the threshold.

    -inf and NaN (no signal) count as not covered.
    """
    selected = _select(values, mask)
    if selected.size == 0:
        raise ValueError("No cells selected: coverage is undefined.")
    with np.errstate(invalid="ignore"):
        return float(np.count_nonzero(selected >= threshold) / selected.size)


def percentile(values, q: float, mask=None) -> float:
    """q-th percentile over the selected cells (q = 5 for the 5th-percentile user rate)."""
    selected = _select(values, mask)
    if selected.size == 0:
        raise ValueError("No cells selected: percentile is undefined.")
    if np.any(np.isnan(selected)):
        raise ValueError("Missing values present; give cells without service a rate of 0.")
    return float(np.percentile(selected, q))


def empirical_cdf(values, mask=None) -> tuple[np.ndarray, np.ndarray]:
    """Sorted values and the cumulative share of cells at or below each of them."""
    selected = np.sort(_select(values, mask))
    if selected.size == 0:
        raise ValueError("No cells selected: the distribution is undefined.")
    return selected, np.arange(1, selected.size + 1) / selected.size


def rmse(a, b, return_count: bool = False):
    """Root-mean-square difference over the pairs where both values are finite.

    Used for path loss in dB (model against ray tracing). Pairs with a missing
    or infinite value (no path) are left out; ask for the count to report how
    many pairs the figure rests on.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Both series must have the same shape.")
    usable = np.isfinite(a) & np.isfinite(b)
    count = int(np.count_nonzero(usable))
    if count == 0:
        raise ValueError("No pair of finite values to compare.")
    value = float(np.sqrt(np.mean((a[usable] - b[usable]) ** 2)))
    return (value, count) if return_count else value
