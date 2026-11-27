"""Custom experiments: valid parameter changes run freely, are classified and recorded; the
approved configuration stays the research baseline and can always be restored."""

from pathlib import Path

import numpy as np
import pytest

from bns.simulation import experiment as ex

ROOT = Path(__file__).resolve().parents[2]


def test_the_baseline_holds_the_approved_values():
    b = ex.baseline_values(ROOT, "standard")
    assert b["tx_power_dbm"] == 46.0 and b["coverage_threshold"] == -10.0 and b["interference_activity"] == 1.0
    assert b["antenna_height_above_roof_m"] == 3.0 and b["mechanical_downtilt_deg"] == 10.0
    assert (b["cell_size_m"], b["rays_per_site"]) == (10.0, 10**9)
    assert b["rain_rate_mm_h"] == 0.0
    assert (b["min_roof_height_m"], b["min_roof_area_m2"], b["min_spacing_m"]) == (12.0, 100.0, 125.0)  # refined


def test_only_values_that_differ_from_the_baseline_are_overrides():
    b = ex.baseline_values(ROOT, "standard")
    edited = {**b, "tx_power_dbm": 43.0, "interference_activity": 0.5}
    assert ex.differences(edited, b) == {"tx_power_dbm": 43.0, "interference_activity": 0.5}
    assert ex.differences(dict(b), b) == {}                      # reset to baseline = no override
    assert ex.run_class({}) == "research baseline"
    assert ex.run_class({"tx_power_dbm": 43.0}) == "custom experiment"


@pytest.mark.parametrize("bad", [{"tx_power_dbm": 90.0}, {"interference_activity": 1.5}, {"sectors_per_site": 2.5},
                                 {"rays_per_site": 10}, {"unknown_parameter": 1.0}, {"coverage_target": 0.0},
                                 {"cell_size_m": float("nan")}])
def test_invalid_overrides_are_refused(bad):
    with pytest.raises(ex.ExperimentError):
        ex.validate_overrides(bad)


def test_a_custom_radio_system_keeps_the_double_counting_safeguard():
    from bns.analysis.radio_system import RadioSystem

    system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
    custom = ex.custom_radio_system(system, {"tx_power_dbm": 40.0, "mechanical_downtilt_deg": 6.0})
    assert custom.require("tx_power_dbm", "lte_1800", mode="development") == 40.0
    assert custom.status("tx_power_dbm") == "development"                  # never presented as approved
    assert custom.status("noise_figure_db") == "approved"
    from bns.analysis.radio_system import UnapprovedParameter
    with pytest.raises(UnapprovedParameter):
        custom.require("tx_power_dbm", "lte_1800", mode="research")


def test_invalid_values_still_stop_a_run_before_anything_is_loaded():
    with pytest.raises(ex.ExperimentError, match="valid range"):
        ex.load(ROOT, "tahrir_bab_al_sharqi_study", "osm+fp_3d_globfp", "standard", overrides={"tx_power_dbm": 90.0})
    with pytest.raises(ex.ExperimentError, match="Unknown study area"):
        ex.load(ROOT, "nowhere", "osm", "standard")
    with pytest.raises(ex.ExperimentError, match="No dataset"):
        ex.load(ROOT, "tahrir_bab_al_sharqi_study", "missing-variant", "standard")
    with pytest.raises(ex.ExperimentError):
        ex.load(ROOT, "tahrir_bab_al_sharqi_study", "osm+fp_3d_globfp", "research")   # 5 m profile not converged


def test_sectors_face_compass_bearings_0_120_240():
    from bns.analysis.radio_system import RadioSystem
    from bns.simulation.setup import scene_azimuth_to_bearing_deg, sector_antennas

    system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
    antennas = sector_antennas(system, mode="development", polarization="V")
    assert [scene_azimuth_to_bearing_deg(a.orientation_rad[0]) for a in antennas] == pytest.approx([0.0, 120.0, 240.0])
    # the first sector points north (+y) in the scene frame
    yaw = antennas[0].orientation_rad[0]
    assert (np.cos(yaw), np.sin(yaw)) == pytest.approx((0.0, 1.0), abs=1e-12)
