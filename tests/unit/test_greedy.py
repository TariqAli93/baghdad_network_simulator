"""Greedy site selection on hand-built coverage tables."""

import numpy as np
import pytest

from bns.optimization.greedy import greedy_site_selection


def table(*rows):
    return np.array(rows, dtype=bool)


def test_picks_the_site_with_the_largest_gain_first_then_the_best_addition():
    covered = table(
        [1, 1, 1, 1, 0, 0, 0, 0, 0, 0],   # site 0: 4 cells
        [0, 0, 0, 1, 1, 0, 0, 0, 0, 0],   # site 1: 2 cells, 1 new after site 0
        [0, 0, 0, 0, 1, 1, 1, 1, 1, 1],   # site 2: 6 cells
    )
    result = greedy_site_selection(covered, target_fraction=1.0)
    assert result.selected == [2, 0]
    assert result.coverage_after == pytest.approx([0.6, 1.0])
    assert result.gain == pytest.approx([0.6, 0.4])
    assert result.target_reached


def test_stops_as_soon_as_the_target_is_met():
    covered = table([1, 1, 1, 1, 1, 1, 1, 1, 1, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    result = greedy_site_selection(covered, target_fraction=0.9)
    assert result.selected == [0] and result.target_reached


def test_unreachable_target_is_reported_and_useless_sites_are_not_added():
    covered = table([1, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0])
    result = greedy_site_selection(covered, target_fraction=0.95)
    assert result.selected == [0]
    assert not result.target_reached
    assert result.coverage_after == pytest.approx([0.5])
    assert result.uncovered_cells.tolist() == [2, 3]


def test_ties_go_to_the_lowest_site_index_so_results_are_reproducible():
    covered = table([1, 1, 0, 0], [0, 0, 1, 1])
    assert greedy_site_selection(covered, target_fraction=0.5).selected == [0]


def test_a_site_budget_limits_the_selection():
    covered = np.eye(5, dtype=bool)
    result = greedy_site_selection(covered, target_fraction=1.0, max_sites=2)
    assert len(result.selected) == 2 and not result.target_reached
    assert result.coverage_after[-1] == pytest.approx(0.4)


def test_zero_target_needs_no_site():
    result = greedy_site_selection(table([1, 0]), target_fraction=0.0)
    assert result.selected == [] and result.target_reached


def test_inputs_are_checked():
    with pytest.raises(ValueError):
        greedy_site_selection(table([1, 0]), target_fraction=1.2)
    with pytest.raises(ValueError):
        greedy_site_selection(np.zeros((2, 0), dtype=bool), target_fraction=0.5)
    with pytest.raises(ValueError):
        greedy_site_selection(np.ones((2, 3)), target_fraction=0.5)   # not boolean
