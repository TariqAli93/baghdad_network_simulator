"""Radio-system parameters must be explicit about whether anyone has approved them."""

import pytest
import yaml

from bns.analysis.radio_system import RadioSystem, UndecidedParameter


def write(tmp_path, parameters):
    path = tmp_path / "radio.yaml"
    path.write_text(yaml.safe_dump({"parameters": parameters}), encoding="utf-8")
    return path


def test_repository_config_has_no_decided_power_gain_noise_or_threshold(repo_root):
    system = RadioSystem.load(repo_root / "configs" / "radio_system.yaml")
    for name in ("tx_power_dbm", "tx_antenna_gain_dbi", "rx_antenna_gain_dbi", "noise_figure_db",
                 "coverage_threshold_dbm", "coverage_target", "interference_activity",
                 "antenna_height_above_roof_m"):
        with pytest.raises(UndecidedParameter, match=name):
            system.require(name)
    assert system.approved_parameters() == []


def test_approved_value_is_returned(tmp_path):
    system = RadioSystem.load(write(tmp_path, {
        "noise_figure_db": {"value": 7.0, "status": "approved", "source": "supervisor, 2026-12-01"}}))
    assert system.require("noise_figure_db") == 7.0
    assert system.approved_parameters() == ["noise_figure_db"]


def test_provisional_value_is_usable_but_is_listed_so_reports_can_flag_it(tmp_path):
    system = RadioSystem.load(write(tmp_path, {
        "tx_power_dbm": {"value": 40.0, "status": "provisional", "source": "example from study X"}}))
    assert system.require("tx_power_dbm") == 40.0
    assert system.provisional_parameters() == ["tx_power_dbm"]
    assert system.approved_parameters() == []


def test_per_scenario_values_are_supported(tmp_path):
    system = RadioSystem.load(write(tmp_path, {
        "tx_antenna_gain_dbi": {"value": {"lte_1800": 15.0, "nr_28000": 27.0},
                                "status": "provisional", "source": "example"}}))
    assert system.require("tx_antenna_gain_dbi", scenario="nr_28000") == 27.0
    with pytest.raises(KeyError):
        system.require("tx_antenna_gain_dbi", scenario="c6g_8000")
    with pytest.raises(ValueError, match="scenario"):
        system.require("tx_antenna_gain_dbi")


@pytest.mark.parametrize("entry", [
    {"value": None, "status": "approved", "source": "x"},       # approved but empty
    {"value": 5.0, "status": "undecided", "source": ""},         # undecided but has a value
    {"value": 5.0, "status": "approved", "source": ""},          # no source
    {"value": 5.0, "status": "official", "source": "x"},         # unknown status
])
def test_inconsistent_entries_are_rejected_when_loading(tmp_path, entry):
    with pytest.raises(ValueError):
        RadioSystem.load(write(tmp_path, {"noise_figure_db": entry}))


def test_unknown_parameter_name_is_an_error(tmp_path):
    system = RadioSystem.load(write(tmp_path, {}))
    with pytest.raises(KeyError):
        system.require("tx_power")
