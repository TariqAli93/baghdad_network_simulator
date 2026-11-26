"""Coverage, percentiles, CDF and RMSE on small arrays with known answers."""

import numpy as np
import pytest

from bns.analysis import metrics as m


# --- coverage -----------------------------------------------------------------------


def test_coverage_counts_cells_at_or_above_the_threshold():
    power = np.array([-80.0, -100.0, -120.0, -np.inf])
    assert m.coverage_fraction(power, -100.0) == pytest.approx(0.5)


def test_coverage_uses_only_the_cells_selected_by_the_mask():
    power = np.array([[-80.0, -130.0], [-90.0, -130.0]])
    outdoor = np.array([[True, False], [True, True]])
    assert m.coverage_fraction(power, -100.0, outdoor) == pytest.approx(2.0 / 3.0)


def test_cells_without_a_value_count_as_not_covered():
    assert m.coverage_fraction(np.array([np.nan, -50.0]), -100.0) == pytest.approx(0.5)


def test_coverage_of_nothing_is_an_error():
    with pytest.raises(ValueError):
        m.coverage_fraction(np.array([-80.0]), -100.0, np.array([False]))


# --- percentiles --------------------------------------------------------------------


def test_fifth_percentile_of_a_uniform_ramp():
    rates = np.arange(0.0, 101.0)          # 0..100
    assert m.percentile(rates, 5.0) == pytest.approx(5.0)


def test_users_without_service_pull_the_fifth_percentile_to_zero():
    rates = np.concatenate([np.zeros(10), np.full(90, 50.0)])
    assert m.percentile(rates, 5.0) == 0.0


def test_percentile_respects_the_mask():
    rates = np.array([1.0, 2.0, 3.0, 1000.0])
    assert m.percentile(rates, 50.0, np.array([True, True, True, False])) == pytest.approx(2.0)


def test_percentile_rejects_missing_values_instead_of_hiding_them():
    with pytest.raises(ValueError):
        m.percentile(np.array([1.0, np.nan]), 5.0)


# --- CDF ----------------------------------------------------------------------------


def test_cdf_is_sorted_and_ends_at_one():
    x, p = m.empirical_cdf(np.array([3.0, 1.0, 2.0, 2.0]))
    assert x.tolist() == [1.0, 2.0, 2.0, 3.0]
    assert p.tolist() == [0.25, 0.5, 0.75, 1.0]


def test_cdf_value_at_a_point_equals_the_share_at_or_below_it():
    values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    x, p = m.empirical_cdf(values)
    assert p[np.searchsorted(x, 30.0, side="right") - 1] == pytest.approx(0.6)


def test_cdf_keeps_no_signal_cells_at_the_bottom():
    x, p = m.empirical_cdf(np.array([-np.inf, -90.0, -80.0]), mask=None)
    assert x[0] == -np.inf and p[0] == pytest.approx(1.0 / 3.0)


# --- RMSE ---------------------------------------------------------------------------


def test_rmse_of_identical_series_is_zero():
    a = np.array([100.0, 110.0, 120.0])
    assert m.rmse(a, a) == 0.0


def test_rmse_hand_calculation():
    assert m.rmse(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 5.0])) == pytest.approx(np.sqrt(4.0 / 3.0))


def test_constant_offset_gives_that_offset():
    a = np.linspace(90.0, 140.0, 11)
    assert m.rmse(a, a + 3.0) == pytest.approx(3.0)


def test_rmse_reports_how_many_pairs_were_usable():
    value, used = m.rmse(np.array([1.0, np.inf, 3.0]), np.array([2.0, 5.0, np.nan]), return_count=True)
    assert value == pytest.approx(1.0) and used == 1


def test_rmse_errors_on_shape_mismatch_or_no_usable_pair():
    with pytest.raises(ValueError):
        m.rmse(np.array([1.0, 2.0]), np.array([1.0]))
    with pytest.raises(ValueError):
        m.rmse(np.array([np.inf]), np.array([1.0]))
