import numpy as np
import pytest

from bns.core import units as u


def test_db_linear_round_trip():
    values = np.array([-120.0, -3.0, 0.0, 10.0, 43.0])
    assert np.allclose(u.linear_to_db(u.db_to_linear(values)), values)


def test_known_db_values():
    assert u.db_to_linear(10.0) == pytest.approx(10.0)
    assert u.db_to_linear(3.0) == pytest.approx(1.995262, rel=1e-6)
    assert u.linear_to_db(0.5) == pytest.approx(-3.0103, abs=1e-4)


def test_zero_power_is_minus_infinity_not_an_error():
    assert u.linear_to_db(0.0) == -np.inf


def test_dbm_watt():
    assert u.dbm_to_watt(30.0) == pytest.approx(1.0)
    assert u.dbm_to_watt(0.0) == pytest.approx(1e-3)
    assert u.watt_to_dbm(20.0) == pytest.approx(43.0103, abs=1e-4)
    assert u.watt_to_dbm(u.dbm_to_watt(-97.5)) == pytest.approx(-97.5)


def test_wavelength():
    assert u.wavelength(3.0e9) == pytest.approx(0.0999308, rel=1e-6)


def test_free_space_path_loss_reference_value():
    # 20*log10(d_km) + 20*log10(f_MHz) + 32.44 with d = 1 km, f = 1800 MHz
    assert u.free_space_path_loss_db(1000.0, 1.8e9) == pytest.approx(97.55, abs=0.01)


def test_free_space_loss_grows_6_db_per_distance_doubling():
    near = u.free_space_path_loss_db(100.0, 3.5e9)
    far = u.free_space_path_loss_db(200.0, 3.5e9)
    assert far - near == pytest.approx(6.0206, abs=1e-3)


def test_free_space_loss_grows_20_db_per_frequency_decade():
    low = u.free_space_path_loss_db(100.0, 2.8e9)
    high = u.free_space_path_loss_db(100.0, 28.0e9)
    assert high - low == pytest.approx(20.0, abs=1e-9)


def test_thermal_noise_density():
    # kT at 290 K is -173.98 dBm/Hz
    assert u.noise_power_dbm(1.0) == pytest.approx(-173.98, abs=0.01)


def test_noise_scales_with_bandwidth_and_noise_figure():
    n20 = u.noise_power_dbm(20e6)
    n400 = u.noise_power_dbm(400e6)
    assert n20 == pytest.approx(-100.97, abs=0.01)
    assert n400 - n20 == pytest.approx(10 * np.log10(20.0), abs=1e-9)
    assert u.noise_power_dbm(20e6, noise_figure_db=7.0) - n20 == pytest.approx(7.0)
