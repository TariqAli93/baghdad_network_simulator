"""Rain and gas attenuation against the tabulated values of the ITU-R recommendations."""

import numpy as np
import pytest

from bns.geospatial.grid import Grid
from bns.propagation import atmosphere as atm

# ITU-R P.838-3, Table 5 (read from the Recommendation; see docs/references.md, ITU-P838)
P838_TABLE_5 = {
    #  GHz:   (kH,        alphaH, kV,        alphaV)
    1.5: (0.0000443, 1.0185, 0.0000574, 0.8957),
    2.0: (0.0000847, 1.0664, 0.0000998, 0.9490),
    3.5: (0.0001155, 1.4189, 0.0002346, 1.1387),
    8.0: (0.004115, 1.3905, 0.003450, 1.3797),
    15.0: (0.04481, 1.1233, 0.05008, 1.0440),
    28.0: (0.2051, 0.9679, 0.1964, 0.9277),
}


@pytest.mark.parametrize("f_ghz", sorted(P838_TABLE_5))
def test_rain_coefficients_reproduce_table_5_of_p838(f_ghz):
    k_h, a_h, k_v, a_v = P838_TABLE_5[f_ghz]
    got_kh, got_ah = atm.rain_coefficients(f_ghz * 1e9, "H")
    got_kv, got_av = atm.rain_coefficients(f_ghz * 1e9, "V")
    assert got_kh == pytest.approx(k_h, rel=2e-3)      # the table prints four significant digits
    assert got_kv == pytest.approx(k_v, rel=2e-3)
    assert got_ah == pytest.approx(a_h, abs=1e-4)
    assert got_av == pytest.approx(a_v, abs=1e-4)


def test_rain_specific_attenuation_is_k_times_rate_to_the_alpha():
    k, alpha = atm.rain_coefficients(28e9, "H")
    assert atm.rain_specific_attenuation_db_per_km(28e9, 25.0, "H") == pytest.approx(k * 25.0**alpha)
    assert atm.rain_specific_attenuation_db_per_km(28e9, 25.0, "H") == pytest.approx(4.62, abs=0.05)


def test_no_rain_means_no_rain_loss():
    assert atm.rain_specific_attenuation_db_per_km(28e9, 0.0, "V") == 0.0


def test_rain_loss_grows_with_rain_rate_and_with_frequency():
    rates = [atm.rain_specific_attenuation_db_per_km(15e9, r, "V") for r in (1.0, 10.0, 50.0)]
    assert rates == sorted(rates) and rates[0] > 0
    bands = [atm.rain_specific_attenuation_db_per_km(f, 25.0, "V") for f in (1.8e9, 3.5e9, 8e9, 15e9, 28e9)]
    assert bands == sorted(bands)


def test_rain_model_rejects_inputs_outside_its_range():
    with pytest.raises(ValueError):
        atm.rain_coefficients(0.5e9, "H")          # P.838-3 covers 1-1000 GHz
    with pytest.raises(ValueError):
        atm.rain_coefficients(28e9, "circular")
    with pytest.raises(ValueError):
        atm.rain_specific_attenuation_db_per_km(28e9, -1.0, "H")


def test_gas_attenuation_is_available_for_the_five_scenario_bands_and_small():
    values = [atm.gas_specific_attenuation_db_per_km(f) for f in (1.8e9, 3.5e9, 8e9, 15e9, 28e9)]
    assert values == sorted(values)
    assert 0.005 < values[0] < 0.01 and 0.08 < values[-1] < 0.12


def test_gas_attenuation_for_an_untabulated_frequency_is_refused_not_guessed():
    with pytest.raises(ValueError, match="not tabulated"):
        atm.gas_specific_attenuation_db_per_km(5.0e9)


def test_loss_over_a_path_is_specific_attenuation_times_length():
    assert atm.path_attenuation_db(0.1, 500.0) == pytest.approx(0.05)
    assert atm.path_attenuation_db(0.0, 1e6) == 0.0


def test_attenuation_map_uses_the_straight_line_distance_from_the_site():
    grid = Grid((0.0, 0.0), (2000.0, 1000.0), 1000.0, height_m=1.5)   # cells at x = -500, 500
    loss = atm.attenuation_map_db((-500.0, 0.0, 301.5), grid, specific_db_per_km=2.0)
    assert loss.shape == (1, 2)
    assert loss[0, 0] == pytest.approx(2.0 * 0.300)                    # straight down: 300 m
    assert loss[0, 1] == pytest.approx(2.0 * np.hypot(1000.0, 300.0) / 1000.0)


def test_repository_baseline_is_clear_sky_and_only_the_approved_rain_case_is_a_sensitivity_case(repo_root):
    baseline, cases = atm.load_conditions(repo_root / "configs" / "atmosphere.yaml")
    assert baseline == atm.Conditions(rain_rate_mm_h=0.0, include_gas=True)        # rain never in the baseline
    assert len(cases) >= 2
    # C2 (reported 2026-11-27): 18.6 mm/h approved as an optional sensitivity case only
    assert [c["conditions"].rain_rate_mm_h for c in cases if c["approved"]] == [18.6]
    assert all(case["conditions"].rain_rate_mm_h > 0 and case["source"] for case in cases)


def test_clear_sky_conditions_include_gas_but_no_rain():
    clear = atm.Conditions(rain_rate_mm_h=0.0, include_gas=True)
    assert clear.specific_attenuation_db_per_km(28e9, "V") == pytest.approx(
        atm.gas_specific_attenuation_db_per_km(28e9))
    rainy = atm.Conditions(rain_rate_mm_h=20.0, include_gas=True)
    assert rainy.specific_attenuation_db_per_km(28e9, "V") == pytest.approx(
        atm.gas_specific_attenuation_db_per_km(28e9)
        + atm.rain_specific_attenuation_db_per_km(28e9, 20.0, "V"))
