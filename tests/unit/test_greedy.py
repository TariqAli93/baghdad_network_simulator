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


# ---- SINR-based greedy selection (whole-network coverage, interference included) ----

from bns.optimization.greedy import greedy_sinr_site_selection  # noqa: E402


def coverage_table(values):
    return lambda selection: values[tuple(sorted(selection))]


def test_sinr_greedy_adds_the_best_network_and_stops_at_the_target():
    cov = coverage_table({(0,): 0.5, (1,): 0.6, (2,): 0.2, (0, 1): 0.7, (1, 2): 0.9, (0, 1, 2): 0.95})
    r = greedy_sinr_site_selection(cov, 3, target_fraction=0.85)
    assert r.selected == [1, 2] and r.coverage_after == [0.6, 0.9]
    assert r.target_reached and r.stopped_because == "target reached"


def test_sinr_greedy_is_not_a_union_of_masks_and_reports_degrading_additions():
    # site 2 alone covers 0.3 but adding it to site 0 lowers coverage through interference
    cov = coverage_table({(0,): 0.6, (1,): 0.1, (2,): 0.3, (0, 1): 0.65, (0, 2): 0.5, (0, 1, 2): 0.55})
    r = greedy_sinr_site_selection(cov, 3, target_fraction=0.95)
    assert r.selected == [0, 1]
    assert r.stopped_because == "no candidate raises coverage" and not r.target_reached
    assert {"step": 2, "candidate": 2, "change": pytest.approx(-0.1)} in r.degrading_additions
    assert r.degrading_additions[-1]["candidate"] == 2 and r.degrading_additions[-1]["step"] == 3


def test_sinr_greedy_ties_go_to_the_lowest_index_and_respect_the_site_limit():
    cov = coverage_table({(0,): 0.4, (1,): 0.4, (0, 1): 0.8})
    r = greedy_sinr_site_selection(cov, 2, target_fraction=1.0, max_sites=1)
    assert r.selected == [0] and r.stopped_because == "site limit reached"
