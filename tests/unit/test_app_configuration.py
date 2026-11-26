"""Display rows of the approved configuration come from the files, with their effective approval."""

import shutil
from pathlib import Path

import yaml

from bns.app import configuration as cfg
from bns.simulation.experiment import load_scenarios

ROOT = Path(__file__).resolve().parents[2]


def test_rows_read_the_configuration_values():
    radio = {r["parameter"]: r for r in cfg.radio_rows(ROOT)}
    assert radio["tx_power_dbm"]["value"] == 46.0 and radio["tx_power_dbm"]["approval"] == "approved"
    site = {r["item"]: r for r in cfg.site_rule_rows(ROOT)}
    assert site["Mast height above the roof"]["value"] == "3.0 m"
    assert "0, 120, 240" in site["Sectors and azimuths"]["value"]
    assert site["Minimum roof height"]["value"].startswith("PENDING")
    rates = {r["scenario"]: r for r in cfg.rate_rows(ROOT, load_scenarios(ROOT))}
    assert rates["4G LTE"]["cap"] == "4.4 bit/s/Hz"
    assert rates["5G NR mid-band"]["cap"] == "30 dB"
    assert rates["Candidate 6G 15 GHz"]["label"] == "research approximation"
    area = {r["item"]: r for r in cfg.study_area_rows(ROOT, "tahrir_bab_al_sharqi_study")}
    assert area["Centre"]["value"] == "33.328 N, 44.4085 E"
    assert area["Required observations"]["value"].startswith("P0, P1, P2, S")
    profiles = {r["item"]: r for r in cfg.backend_profile_rows(ROOT)}
    assert profiles["profile research"]["value"].endswith("disabled")
    assert profiles["backend gpu"]["value"] == "development only"


def test_a_changed_approved_value_is_shown_as_void(tmp_path):
    (tmp_path / "configs").mkdir()
    for p in (ROOT / "configs").glob("*.yaml"):
        shutil.copy(p, tmp_path / "configs" / p.name)
    path = tmp_path / "configs" / "radio_system.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["parameters"]["coverage_threshold"]["value"] = 0.0
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    radio = {r["parameter"]: r for r in cfg.radio_rows(tmp_path)}
    assert radio["coverage_threshold"]["approval"].startswith("approval void")
    assert radio["noise_figure_db"]["approval"] == "approved"
