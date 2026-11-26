"""Received power, SINR and Shannon rate: analytical cases with hand-computed answers."""

import numpy as np
import pytest

from bns.analysis import link_budget as lb
from bns.core.units import dbm_to_watt, noise_power_dbm


# --- received power -----------------------------------------------------------------


def test_received_power_is_transmit_power_plus_path_gain_in_db():
    assert lb.received_power_dbm(43.0, 1e-10) == pytest.approx(-57.0)


def test_antenna_gains_add_and_extra_losses_subtract():
    value = lb.received_power_dbm(43.0, 1e-10, tx_gain_dbi=15.0, rx_gain_dbi=2.0, extra_loss_db=4.0)
    assert value == pytest.approx(-44.0)


def test_no_path_gives_minus_infinity_not_an_error():
    out = lb.received_power_dbm(43.0, np.array([1e-9, 0.0]))
    assert out[0] == pytest.approx(-47.0) and out[1] == -np.inf


def test_received_power_keeps_the_map_shape_and_allows_per_cell_losses():
    gain = np.full((2, 3, 4), 1e-9)
    loss = np.linspace(0.0, 1.1, 12).reshape(3, 4)
    out = lb.received_power_dbm(30.0, gain, extra_loss_db=loss)
    assert out.shape == (2, 3, 4)
    assert out[1, 2, 3] == pytest.approx(30.0 - 90.0 - 1.1)


def test_doubling_distance_in_free_space_costs_6_db_of_received_power():
    from bns.core.units import free_space_path_gain
    near = lb.received_power_dbm(40.0, free_space_path_gain(100.0, 3.5e9))
    far = lb.received_power_dbm(40.0, free_space_path_gain(200.0, 3.5e9))
    assert near - far == pytest.approx(6.0206, abs=1e-3)


# --- SINR ---------------------------------------------------------------------------


def test_single_site_sinr_is_signal_over_noise():
    result = lb.sinr(np.array([[8.0]]), noise_w=2.0, interference_activity=1.0)
    assert result.sinr[0] == pytest.approx(4.0) and result.serving[0] == 0


def test_interference_is_summed_in_linear_units():
    # strongest 4 W, two interferers of 1 W, noise 2 W -> 4 / (1 + 1 + 2) = 1
    received = np.array([[1.0], [4.0], [1.0]])
    result = lb.sinr(received, noise_w=2.0, interference_activity=1.0)
    assert result.sinr[0] == pytest.approx(1.0)
    assert result.serving[0] == 1
    assert result.signal_w[0] == 4.0 and result.interference_w[0] == pytest.approx(2.0)


def test_two_equal_sites_without_noise_give_zero_db():
    result = lb.sinr(np.array([[3.0], [3.0]]), noise_w=0.0, interference_activity=1.0)
    assert result.sinr[0] == pytest.approx(1.0)


def test_adding_an_interferer_lowers_sinr_when_everything_else_is_fixed():
    alone = lb.sinr(np.array([[5.0]]), noise_w=1.0, interference_activity=1.0).sinr[0]
    shared = lb.sinr(np.array([[5.0], [0.5]]), noise_w=1.0, interference_activity=1.0).sinr[0]
    assert shared < alone


def test_interference_activity_scales_only_the_interference():
    received = np.array([[4.0], [2.0]])
    half = lb.sinr(received, noise_w=2.0, interference_activity=0.5)
    assert half.sinr[0] == pytest.approx(4.0 / (0.5 * 2.0 + 2.0))
    idle = lb.sinr(received, noise_w=2.0, interference_activity=0.0)
    assert idle.sinr[0] == pytest.approx(2.0)


def test_cell_without_any_signal_has_zero_sinr_and_no_server():
    result = lb.sinr(np.array([[0.0, 2.0], [0.0, 1.0]]), noise_w=1.0, interference_activity=1.0)
    assert result.sinr[0] == 0.0 and result.serving[0] == -1
    assert result.sinr[1] == pytest.approx(1.0) and result.serving[1] == 0


def test_sinr_works_on_maps_and_rejects_bad_inputs():
    received = np.ones((3, 4, 5))
    result = lb.sinr(received, noise_w=1.0, interference_activity=1.0)
    assert result.sinr.shape == (4, 5) and result.serving.shape == (4, 5)
    assert np.allclose(result.sinr, 1.0 / 3.0)
    with pytest.raises(ValueError):
        lb.sinr(received, noise_w=-1.0, interference_activity=1.0)
    with pytest.raises(ValueError):
        lb.sinr(received, noise_w=1.0, interference_activity=1.5)
    with pytest.raises(ValueError):
        lb.sinr(np.array([[-1.0]]), noise_w=1.0, interference_activity=1.0)


def test_sinr_from_dbm_inputs_matches_a_hand_calculation():
    # -70 dBm signal, -80 dBm interferer, 20 MHz with 7 dB noise figure (-93.97 dBm)
    received = dbm_to_watt(np.array([[-70.0], [-80.0]]))
    noise = dbm_to_watt(noise_power_dbm(20e6, noise_figure_db=7.0))
    result = lb.sinr(received, noise_w=noise, interference_activity=1.0)
    expected = 1e-10 / (1e-11 + 10 ** ((-93.97 - 30) / 10))
    assert result.sinr[0] == pytest.approx(expected, rel=1e-3)


# --- Shannon capacity ---------------------------------------------------------------


def test_shannon_at_zero_db_gives_one_bit_per_hertz():
    assert lb.shannon_capacity_bps(20e6, 1.0) == pytest.approx(20e6)


def test_shannon_known_points():
    assert lb.shannon_capacity_bps(100e6, 15.0) == pytest.approx(400e6)
    assert lb.shannon_capacity_bps(100e6, 0.0) == 0.0


def test_shannon_scales_linearly_with_bandwidth_at_fixed_sinr():
    narrow = lb.shannon_capacity_bps(20e6, 7.0)
    wide = lb.shannon_capacity_bps(400e6, 7.0)
    assert wide / narrow == pytest.approx(20.0)


def test_wider_bandwidth_with_the_same_received_power_does_not_scale_rate_linearly():
    # same signal power, noise grows with bandwidth: the rate gain is below the bandwidth ratio
    signal = dbm_to_watt(-90.0)
    rates = []
    for bandwidth in (20e6, 400e6):
        noise = dbm_to_watt(noise_power_dbm(bandwidth))
        rates.append(lb.shannon_capacity_bps(bandwidth, signal / noise))
    assert 1.0 < rates[1] / rates[0] < 20.0


def test_shannon_rejects_negative_sinr():
    with pytest.raises(ValueError):
        lb.shannon_capacity_bps(20e6, -0.1)
