"""TR 38.901 UMa/UMi path loss and LOS probability against hand calculations and identities."""

import numpy as np
import pytest

from bns.validation import tr38901 as m


def test_breakpoints_match_the_table_in_the_reference_notes():
    # docs/references.md §5.1, user at 1.5 m
    assert m.breakpoint_m(25.0, 1.5, 3.5e9) == pytest.approx(560.0)
    assert m.breakpoint_m(10.0, 1.5, 1.8e9) == pytest.approx(108.0)
    assert m.breakpoint_m(10.0, 1.5, 28e9) == pytest.approx(1680.0)


def test_uma_los_hand_value_and_continuity_at_the_breakpoint():
    d3 = np.sqrt(100.0**2 + 23.5**2)
    assert m.pathloss_los("UMa", 100.0, 3.5e9, 25.0, 1.5) == pytest.approx(28 + 22 * np.log10(d3) + 20 * np.log10(3.5))
    for scenario, h in (("UMa", 25.0), ("UMi", 10.0)):
        bp = m.breakpoint_m(h, 1.5, 1.8e9)
        below, above = m.pathloss_los(scenario, [bp * (1 - 1e-9), bp * (1 + 1e-9)], 1.8e9, h, 1.5)
        assert below == pytest.approx(above, abs=1e-3)


def test_nlos_is_never_below_los_and_frequency_enters_as_20_log_f_for_uma():
    d = np.linspace(10, 1000, 50)
    for scenario, h in (("UMa", 25.0), ("UMi", 10.0)):
        assert np.all(m.pathloss_nlos(scenario, d, 8e9, h, 1.5) >= m.pathloss_los(scenario, d, 8e9, h, 1.5))
    d = np.array([50.0, 200.0])                      # below the UMa breakpoint at both frequencies
    diff = m.pathloss_los("UMa", d, 28e9, 25.0, 1.5) - m.pathloss_los("UMa", d, 3.5e9, 25.0, 1.5)
    assert diff == pytest.approx(20 * np.log10(8.0))


def test_umi_nlos_hand_value():
    d3 = np.sqrt(300.0**2 + 8.5**2)
    expected = max(32.4 + 21 * np.log10(d3) + 20 * np.log10(3.5), 35.3 * np.log10(d3) + 22.4 + 21.3 * np.log10(3.5))
    assert m.pathloss_nlos("UMi", 300.0, 3.5e9, 10.0, 1.5) == pytest.approx(expected)


def test_los_probability_is_one_near_the_site_and_decreases():
    p = m.los_probability("UMi", [5.0, 18.0, 50.0, 200.0])
    assert p[0] == 1.0 and p[1] == 1.0 and p[1] > p[2] > p[3]
    assert m.los_probability("UMa", 100.0) == pytest.approx(0.18 + np.exp(-100 / 63) * 0.82)


def test_applicability_refuses_heights_and_distances_outside_the_model():
    mask, reasons = m.applicable("UMa", [5.0, 50.0, 6000.0], 3.5e9, 25.0, 1.5)
    assert mask.tolist() == [False, True, False] and reasons == []
    mask, reasons = m.applicable("UMa", [50.0], 3.5e9, 58.0, 1.5)
    assert not mask.any() and "assumes 25 m" in reasons[0]
