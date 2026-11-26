"""From cached path gain to received power, SNR/SINR, coverage and rate (hand-checked numbers)."""

import numpy as np
import pytest

from bns.simulation.radio import RadioInputs, multi_site, single_site

OUTDOOR = np.array([[True, True, True, False]])


def inputs(**changes):
    base = dict(eirp_dbm=46.0, rx_gain_dbi=0.0, noise_figure_db=7.0, noise_temperature_k=290.0,
                bandwidth_hz=20e6, coverage_definition="rx_power_dbm", coverage_threshold=-100.0,
                interference_activity=1.0)
    base.update(changes)
    return RadioInputs(**base)


def test_received_power_snr_and_rate_against_a_hand_calculation():
    gain = np.array([[1e-10, 1e-15, 0.0, 1e-10]])
    result = single_site(gain, OUTDOOR, inputs(), extra_loss_db=np.zeros((1, 4)))
    # -54 dBm; noise = -173.98 + 73.01 + 7 = -93.97 dBm
    assert result.rx_power_dbm[0, 0] == pytest.approx(-54.0)
    assert result.noise_dbm == pytest.approx(-93.97, abs=0.01)
    assert result.sinr_db[0, 0] == pytest.approx(39.97, abs=0.01)
    assert result.rate_bps[0, 0] == pytest.approx(20e6 * np.log2(1 + 10 ** 3.997), rel=1e-3)
    assert result.rx_power_dbm[0, 2] == -np.inf and result.rate_bps[0, 2] == 0.0


def test_coverage_counts_outdoor_cells_only_and_unreached_cells_as_uncovered():
    gain = np.array([[1e-10, 1e-15, 0.0, 1e-10]])
    result = single_site(gain, OUTDOOR, inputs(), extra_loss_db=np.zeros((1, 4)))
    assert result.covered.tolist() == [[True, False, False, False]]
    assert result.summary["coverage_fraction"] == pytest.approx(1 / 3)
    assert result.summary["outdoor_cells"] == 3
    # the unreached outdoor cell enters the percentile with a rate of 0
    expected = np.percentile([result.rate_bps[0, 0], result.rate_bps[0, 1], 0.0], 5)
    assert result.summary["rate_p5_bps"] == pytest.approx(expected)
    assert result.summary["unreached_fraction"] == pytest.approx(1 / 3)


def test_snr_threshold_makes_coverage_depend_on_bandwidth():
    gain = np.array([[10 ** -13.4, 10 ** -13.4, 10 ** -13.4, 0.0]])   # -88 dBm received
    narrow = single_site(gain, OUTDOOR, inputs(coverage_definition="snr_db", coverage_threshold=0.0),
                         np.zeros((1, 4)))
    wide = single_site(gain, OUTDOOR, inputs(coverage_definition="snr_db", coverage_threshold=0.0,
                                             bandwidth_hz=400e6), np.zeros((1, 4)))
    assert narrow.summary["coverage_fraction"] == pytest.approx(1.0)   # SNR +6 dB at 20 MHz
    assert wide.summary["coverage_fraction"] == pytest.approx(0.0)     # SNR -7 dB at 400 MHz
    assert wide.noise_dbm - narrow.noise_dbm == pytest.approx(13.01, abs=0.01)


def test_extra_losses_lower_received_power_cell_by_cell():
    gain = np.full((1, 4), 1e-10)
    loss = np.array([[0.0, 1.0, 3.0, 0.0]])
    result = single_site(gain, OUTDOOR, inputs(), extra_loss_db=loss)
    assert result.rx_power_dbm[0, :3].tolist() == pytest.approx([-54.0, -55.0, -57.0])


def test_invalid_path_gain_is_rejected_not_hidden():
    with pytest.raises(ValueError):
        single_site(np.array([[np.nan, 1e-9, 1e-9, 1e-9]]), OUTDOOR, inputs(), np.zeros((1, 4)))
    with pytest.raises(ValueError):
        single_site(np.array([[-1e-9, 1e-9, 1e-9, 1e-9]]), OUTDOOR, inputs(), np.zeros((1, 4)))
    with pytest.raises(ValueError):
        single_site(np.array([[2.0, 1e-9, 1e-9, 1e-9]]), OUTDOOR, inputs(), np.zeros((1, 4)))


def test_very_small_path_gains_stay_finite():
    result = single_site(np.full((1, 4), 1e-30), OUTDOOR, inputs(), np.zeros((1, 4)))
    assert np.all(np.isfinite(result.rx_power_dbm)) and np.all(result.rate_bps >= 0)


def test_two_sites_give_sinr_with_linear_interference_and_a_serving_map():
    stack = np.array([[[1e-10, 1e-12, 1e-11, 0.0]], [[1e-12, 1e-10, 1e-11, 0.0]]])
    loss = np.zeros((2, 1, 4))
    result = multi_site(stack, OUTDOOR, inputs(), extra_loss_db=loss)
    assert result.serving.tolist() == [[0, 1, 0, -1]]
    s, i = 10 ** ((46 - 100 - 30) / 10), 10 ** ((46 - 120 - 30) / 10)
    n = 10 ** ((-93.97 - 30) / 10)
    assert result.sinr_db[0, 0] == pytest.approx(10 * np.log10(s / (i + n)), abs=0.01)
    assert result.sinr_db[0, 2] == pytest.approx(10 * np.log10(1 / (1 + n / 10 ** ((46 - 110 - 30) / 10))),
                                                 abs=0.01)
    alone = single_site(stack[0], OUTDOOR, inputs(), loss[0])
    assert result.sinr_db[0, 0] < alone.sinr_db[0, 0]                 # interference lowers SINR


def test_no_load_means_no_interference():
    stack = np.array([[[1e-10, 1e-12, 1e-11, 0.0]], [[1e-12, 1e-10, 1e-11, 0.0]]])
    idle = multi_site(stack, OUTDOOR, inputs(interference_activity=0.0), np.zeros((2, 1, 4)))
    alone = single_site(stack[0], OUTDOOR, inputs(), np.zeros((1, 4)))
    assert idle.sinr_db[0, 0] == pytest.approx(alone.sinr_db[0, 0])
