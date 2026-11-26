"""Network of sites with sectors: serving sector and site, interference, single vs multi-site."""

import numpy as np
import pytest

from bns.simulation.network import network, sites_alone
from bns.simulation.radio import RadioInputs

OUTDOOR = np.array([[True, True, True, False]])


def inputs(**changes):
    base = dict(tx_power_dbm=46.0, rx_gain_dbi=0.0, noise_figure_db=7.0, noise_temperature_k=290.0,
                bandwidth_hz=20e6, coverage_definition="snr_db", coverage_threshold=0.0,
                interference_activity=1.0)
    base.update(changes)
    return RadioInputs(**base)


# three sectors: site 0 has sectors 0 and 1, site 1 has sector 2
STACK = np.array([[[1e-10, 1e-13, 1e-12, 1e-10]],
                  [[1e-12, 1e-11, 1e-13, 1e-10]],
                  [[1e-13, 1e-12, 1e-10, 1e-10]]])
SECTOR_SITE = np.array([0, 0, 1])
LOSS = np.zeros_like(STACK)


def test_serving_sector_and_site_follow_the_strongest_sector():
    r = network(STACK, SECTOR_SITE, OUTDOOR, inputs(), LOSS)
    assert r.serving_sector.tolist() == [[0, 1, 2, -1]]       # indoor cells are not served
    assert r.serving_site.tolist() == [[0, 0, 1, -1]]


def test_interference_is_the_linear_sum_of_every_other_sector_including_co_located_ones():
    r = network(STACK, SECTOR_SITE, OUTDOOR, inputs(), LOSS)
    # cell 0: serving sector 0; interference from sector 1 (same site) and sector 2 (other site)
    expected_w = 10 ** ((46 - 120 - 30) / 10) + 10 ** ((46 - 130 - 30) / 10)
    assert r.interference_dbm[0, 0] == pytest.approx(10 * np.log10(expected_w) + 30, abs=1e-9)
    noise_w = 10 ** ((r.radio.noise_dbm - 30) / 10)
    signal_w = 10 ** ((46 - 100 - 30) / 10)
    assert r.radio.sinr_db[0, 0] == pytest.approx(10 * np.log10(signal_w / (expected_w + noise_w)))


def test_activity_factor_scales_interference_and_zero_activity_gives_snr():
    full = network(STACK, SECTOR_SITE, OUTDOOR, inputs(), LOSS)
    half = network(STACK, SECTOR_SITE, OUTDOOR, inputs(interference_activity=0.5), LOSS)
    assert half.interference_dbm[0, 0] == pytest.approx(full.interference_dbm[0, 0] - 10 * np.log10(2))
    idle = network(STACK, SECTOR_SITE, OUTDOOR, inputs(interference_activity=0.0), LOSS)
    snr = idle.radio.rx_power_dbm - idle.radio.noise_dbm
    assert idle.radio.sinr_db[0, :3] == pytest.approx(snr[0, :3])


def test_summary_reports_served_share_per_site_and_per_sector_over_outdoor_cells():
    r = network(STACK, SECTOR_SITE, OUTDOOR, inputs(), LOSS)
    assert r.summary["sites"] == 2 and r.summary["sectors"] == 3
    assert r.summary["served_share_per_site"] == pytest.approx([2 / 3, 1 / 3])
    assert r.summary["served_share_per_sector"] == pytest.approx([1 / 3, 1 / 3, 1 / 3])
    assert r.summary["interference_assumption"]["co_located_sectors_interfere"] is True


def test_sector_site_map_must_match_the_stack():
    with pytest.raises(ValueError):
        network(STACK, np.array([0, 1]), OUTDOOR, inputs(), LOSS)
    with pytest.raises(ValueError):
        network(STACK, np.array([0, 2, 2]), OUTDOOR, inputs(), LOSS)   # site 1 has no sector


def test_each_site_alone_ignores_the_other_sites():
    alone = sites_alone(STACK, SECTOR_SITE, OUTDOOR, inputs(), LOSS)
    assert len(alone) == 2
    only_site_1 = network(STACK[2:], np.array([0]), OUTDOOR, inputs(), LOSS[2:])
    assert alone[1].radio.sinr_db == pytest.approx(only_site_1.radio.sinr_db)


def test_adding_a_site_can_lower_coverage_when_its_interference_outweighs_its_service():
    # site 1 is weak everywhere but adds interference at the cell site 0 serves at the edge
    stack = np.array([[[1e-11, 1e-12, 1e-14, 1e-11]],
                      [[1e-13, 1e-12, 1e-15, 1e-11]]])
    loss = np.zeros_like(stack)
    one = network(stack[:1], np.array([0]), OUTDOOR, inputs(coverage_threshold=3.0), loss[:1])
    both = network(stack, np.array([0, 1]), OUTDOOR, inputs(coverage_threshold=3.0), loss)
    assert both.radio.summary["coverage_fraction"] < one.radio.summary["coverage_fraction"]


def test_equal_share_divides_each_sector_among_the_outdoor_cells_it_serves():
    from bns.simulation.network import equal_share_rate_bps

    rate = np.array([[100.0, 60.0, 30.0, 999.0]])
    serving = np.array([[0, 0, 1, 1]])                 # cell 3 is indoor
    shared = equal_share_rate_bps(rate, serving, OUTDOOR)
    assert shared.tolist() == [[50.0, 30.0, 30.0, 0.0]]
