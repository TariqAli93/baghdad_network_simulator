"""Radio-system parameters: approval states, run modes, EIRP without double counting."""

import pytest
import yaml

from bns.analysis.radio_system import (RadioSystem, UndecidedParameter, UnapprovedParameter,
                                       DEVELOPMENT_LABEL)


def entry(value, status="candidate", **extra):
    base = {"value": value, "unit": "dB", "status": status, "sources": ["ITU-M2412"],
            "justification": "j", "validity": "v", "impact": "i"}
    return {**base, **extra}


def load(tmp_path, parameters):
    path = tmp_path / "radio.yaml"
    path.write_text(yaml.safe_dump({"parameters": parameters}), encoding="utf-8")
    return RadioSystem.load(path)


def test_repository_config_loads_and_approves_nothing_but_the_receiver_height(repo_root):
    system = RadioSystem.load(repo_root / "configs" / "radio_system.yaml")
    assert system.approved_parameters() == ["rx_height_m"]
    assert system.require("rx_height_m", mode="research") == 1.5


def test_development_mode_accepts_candidate_values_and_research_mode_rejects_them(tmp_path):
    system = load(tmp_path, {"noise_figure_db": entry(7.0)})
    assert system.require("noise_figure_db", mode="development") == 7.0
    with pytest.raises(UnapprovedParameter, match="noise_figure_db"):
        system.require("noise_figure_db", mode="research")


def test_approved_values_work_in_both_modes(tmp_path):
    system = load(tmp_path, {"noise_figure_db": entry(7.0, "approved", approved_by="supervisor, 2026-12-01")})
    assert system.require("noise_figure_db", mode="research") == 7.0


def test_undecided_parameters_stop_every_mode(tmp_path):
    system = load(tmp_path, {"noise_figure_db": {"value": None, "status": "undecided"}})
    with pytest.raises(UndecidedParameter):
        system.require("noise_figure_db", mode="development")
    with pytest.raises(UndecidedParameter):
        load(tmp_path, {}).require("coverage_target", mode="development")


def test_mode_must_be_named():
    with pytest.raises(ValueError):
        RadioSystem({}).require("noise_figure_db", mode="final")


def test_per_scenario_values(tmp_path):
    system = load(tmp_path, {"noise_figure_db": entry({"lte_1800": 7.0, "nr_28000": 10.0})})
    assert system.require("noise_figure_db", scenario="nr_28000", mode="development") == 10.0
    with pytest.raises(KeyError):
        system.require("noise_figure_db", scenario="c6g_8000", mode="development")
    with pytest.raises(ValueError, match="scenario"):
        system.require("noise_figure_db", mode="development")


@pytest.mark.parametrize("bad", [
    {"noise_figure_db": entry(None)},                                   # value missing
    {"noise_figure_db": {**entry(7.0), "sources": []}},                 # no source
    {"noise_figure_db": entry(7.0, "official")},                        # unknown state
    {"noise_figure_db": entry(7.0, "approved")},                        # approved by nobody
    {"noise_figure_db": {"value": 5.0, "status": "undecided"}},         # undecided with a value
    {"tx_power": entry(40.0)},                                          # unknown parameter
    {"tx_power_dbm": entry(40.0)},                                      # conducted or EIRP?
])
def test_inconsistent_entries_are_rejected_when_loading(tmp_path, bad):
    with pytest.raises(ValueError):
        load(tmp_path, bad)


def test_development_values_need_no_published_source_but_must_say_why(tmp_path):
    system = load(tmp_path, {"noise_figure_db": {"value": 7.0, "status": "development",
                                                 "unit": "dB", "justification": "software test"}})
    assert system.require("noise_figure_db", mode="development") == 7.0


ISO = {"tx_antenna_pattern": entry("iso")}
SECTOR = {"tx_antenna_pattern": entry("tr38901")}


def test_isotropic_trace_adds_conducted_power_plus_gain(tmp_path):
    system = load(tmp_path, {**ISO, "tx_power_dbm": entry(40.0, definition="conducted"),
                             "tx_antenna_gain_dbi": entry(8.0)})
    assert system.tx_power_for_path_gain_dbm("nr_3500", mode="development") == 48.0
    assert system.peak_eirp_dbm("nr_3500", mode="development") == 48.0


def test_eirp_is_used_as_given_and_a_gain_on_top_is_refused(tmp_path):
    system = load(tmp_path, {**ISO, "tx_power_dbm": entry(58.0, definition="eirp")})
    assert system.tx_power_for_path_gain_dbm("nr_3500", mode="development") == 58.0
    with pytest.raises(ValueError, match="double"):
        load(tmp_path, {**ISO, "tx_power_dbm": entry(58.0, definition="eirp"),
                        "tx_antenna_gain_dbi": entry(8.0)})


def test_traced_sector_pattern_already_contains_the_gain(tmp_path):
    system = load(tmp_path, {**SECTOR, "tx_power_dbm": entry(46.0, definition="conducted"),
                             "tx_antenna_gain_dbi": entry(0.0)})
    assert system.tx_power_for_path_gain_dbm("nr_3500", mode="development") == 46.0
    assert system.peak_eirp_dbm("nr_3500", mode="development") == 54.0      # 8 dBi element peak
    with pytest.raises(ValueError, match="double"):
        load(tmp_path, {**SECTOR, "tx_power_dbm": entry(46.0, definition="conducted"),
                        "tx_antenna_gain_dbi": entry(8.0)})
    with pytest.raises(ValueError, match="double"):
        load(tmp_path, {**SECTOR, "tx_power_dbm": entry(54.0, definition="eirp")})


def test_conducted_power_without_a_gain_is_undecided_not_zero(tmp_path):
    system = load(tmp_path, {**ISO, "tx_power_dbm": entry(40.0, definition="conducted")})
    with pytest.raises(UndecidedParameter, match="tx_antenna_gain_dbi"):
        system.tx_power_for_path_gain_dbm("nr_3500", mode="development")


def test_run_label_and_status_report(tmp_path):
    system = load(tmp_path, {"noise_figure_db": entry(7.0, "approved", approved_by="s"),
                             "coverage_target": entry(0.95)})
    assert system.label(["noise_figure_db"], mode="research") == "APPROVED RESEARCH CONFIGURATION"
    assert system.label(["noise_figure_db", "coverage_target"], mode="development") == DEVELOPMENT_LABEL
    assert system.label(["noise_figure_db"], mode="development") == DEVELOPMENT_LABEL
    report = system.status_report(["noise_figure_db", "coverage_target"])
    assert report["coverage_target"]["status"] == "candidate"
    assert report["noise_figure_db"]["sources"] == ["ITU-M2412"]
