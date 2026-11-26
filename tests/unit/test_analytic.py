import numpy as np
import pytest

from bns.core.units import free_space_path_gain, linear_to_db
from bns.validation import analytic as a


def test_concrete_permittivity_matches_itu_table():
    eta = a.itu_concrete_permittivity(1.0e9)
    assert eta.real == pytest.approx(5.24)
    # sigma = 0.0462 S/m at 1 GHz -> imaginary part = sigma / (eps0 * omega)
    assert -eta.imag == pytest.approx(0.0462 / (a.EPSILON_0 * 2 * np.pi * 1e9), rel=1e-12)
    assert -eta.imag == pytest.approx(0.8305, abs=1e-3)


def test_concrete_rejects_frequencies_outside_itu_range():
    with pytest.raises(ValueError):
        a.itu_concrete_permittivity(0.7e9)


def test_normal_incidence_is_polarization_independent_in_magnitude():
    eta = a.itu_concrete_permittivity(3.5e9)
    te = a.fresnel_half_space(0.0, eta, "TE")
    tm = a.fresnel_half_space(0.0, eta, "TM")
    assert abs(te) == pytest.approx(abs(tm))
    # lossless estimate (sqrt(eps)-1)/(sqrt(eps)+1) = 0.392 for eps_r = 5.24
    assert abs(te) == pytest.approx(0.392, abs=0.01)


def test_grazing_incidence_reflects_everything():
    eta = a.itu_concrete_permittivity(3.5e9)
    for pol in ("TE", "TM"):
        assert abs(a.fresnel_half_space(np.radians(89.999), eta, pol)) == pytest.approx(1.0, abs=1e-3)


def test_brewster_minimum_exists_for_tm_only():
    eta = a.itu_concrete_permittivity(3.5e9)
    theta = np.radians(np.linspace(0.0, 89.0, 891))
    tm = np.abs(a.fresnel_half_space(theta, eta, "TM"))
    te = np.abs(a.fresnel_half_space(theta, eta, "TE"))
    brewster = np.degrees(theta[np.argmin(tm)])
    assert brewster == pytest.approx(np.degrees(np.arctan(np.sqrt(5.24))), abs=0.5)
    assert tm.min() < 0.05
    assert np.all(np.diff(te) > 0)  # TE rises monotonically, no dip


def test_thick_lossy_slab_tends_to_half_space():
    f = 28e9
    eta = a.itu_concrete_permittivity(f)
    theta = np.radians(np.linspace(0.0, 85.0, 50))
    for pol in ("TE", "TM"):
        slab = a.fresnel_slab(theta, eta, 2.0, f, pol)
        half = a.fresnel_half_space(theta, eta, pol)
        assert np.allclose(np.abs(slab), np.abs(half), atol=1e-6)


def test_two_ray_reduces_to_friis_without_reflection_far_field():
    # With the receiver on the ground plane both rays have equal length.
    f, h_t = 3.5e9, 20.0
    eta = a.itu_concrete_permittivity(f)
    rho = np.array([50.0, 200.0])
    g = a.two_ray_noncoherent_gain(rho, h_t, 0.0, f, eta, 2.0, "TE")
    d = np.hypot(rho, h_t)
    r = np.abs(a.fresnel_slab(np.arctan2(rho, h_t), eta, 2.0, f, "TE"))
    assert np.allclose(g, free_space_path_gain(d, f) * (1 + r**2))


def test_cell_average_equals_centre_value_far_from_tx():
    f = 3.5e9
    x = np.array([500.0])
    y = np.array([0.0])
    avg = a.cell_averaged_friis((0, 0, 10.0), x, y, 1.5, 10.0, f)
    centre = free_space_path_gain(np.sqrt(500.0**2 + 8.5**2), f)
    assert avg[0, 0] == pytest.approx(centre, rel=1e-3)


def test_cell_average_differs_from_centre_value_near_tx_and_has_converged():
    f = 3.5e9
    args = ((0, 0, 10.0), np.array([5.0]), np.array([5.0]), 1.5, 10.0, f)
    avg = a.cell_averaged_friis(*args)[0, 0]
    fine = a.cell_averaged_friis(*args, n_sub=64)[0, 0]
    centre = free_space_path_gain(np.sqrt(50.0 + 8.5**2), f)
    assert 0.05 < abs(linear_to_db(avg / centre)) < 1.0   # averaging matters under the mast
    assert abs(linear_to_db(avg / fine)) < 0.01           # 8x8 sub-samples are enough


def test_knife_edge_is_minus_6_db_on_the_shadow_boundary():
    assert linear_to_db(a.knife_edge_gain(0.0)) == pytest.approx(-6.0206, abs=1e-3)
    assert a.knife_edge_loss_db_p526(0.0) == pytest.approx(6.03, abs=0.05)


def test_knife_edge_exact_and_p526_agree_in_shadow():
    nu = np.linspace(0.0, 10.0, 60)
    exact = -linear_to_db(a.knife_edge_gain(nu))
    approx = a.knife_edge_loss_db_p526(nu)
    assert np.max(np.abs(exact - approx)) < 0.6


def test_knife_edge_tends_to_free_space_far_into_the_lit_region():
    assert a.knife_edge_gain(-8.0) == pytest.approx(1.0, abs=0.05)


def test_deep_shadow_loss_scales_10_db_per_frequency_decade():
    # same geometry, nu ~ sqrt(f): excess loss grows by 10*log10(f2/f1)
    nu_low = 6.0
    nu_high = nu_low * np.sqrt(10.0)
    diff = a.knife_edge_loss_db_p526(nu_high) - a.knife_edge_loss_db_p526(nu_low)
    assert diff == pytest.approx(10.0, abs=0.1)


def test_edge_path_lengths_in_the_perpendicular_plane():
    diffracted, direct = a.edge_path_lengths((-60.0, 0.0, 30.0), (40.0, 0.0, 1.5), 5.0, 20.0)
    assert direct == pytest.approx(np.hypot(100.0, 28.5))
    assert diffracted == pytest.approx(np.hypot(65.0, 10.0) + np.hypot(35.0, 18.5))
    assert diffracted > direct


def test_fresnel_nu_sign_and_scaling():
    nu_shadow = a.fresnel_nu(101.0, 100.0, 3.5e9)
    nu_lit = a.fresnel_nu(101.0, 100.0, 3.5e9, in_shadow=False)
    assert nu_shadow > 0 and nu_lit == pytest.approx(-nu_shadow)
    assert a.fresnel_nu(101.0, 100.0, 14e9) == pytest.approx(2.0 * nu_shadow)
