"""The research baseline: a changed value makes runs custom experiments, never asks for approval."""

import shutil
from pathlib import Path

import pytest
import yaml

from bns.analysis import research_baseline as rb

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "configs").mkdir()
    for path in (ROOT / "configs").glob("*.yaml"):
        shutil.copy(path, tmp_path / "configs" / path.name)
    return tmp_path


def _edit(repo, name, change):
    path = repo / "configs" / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_the_repository_configuration_is_the_recorded_research_baseline():
    found = rb.check(ROOT)
    assert found and [i.name for i in found if i.state != "baseline"] == []
    names = {i.name for i in found}
    assert {"radio.tx_power_dbm", "rate_mappings", "site_rule", "height_policy", "profile.standard",
            "research_backend", "atmosphere_baseline", "area.tahrir_bab_al_sharqi_study", "B1_tolerance"} <= names


def test_changing_a_value_marks_only_that_item_modified(repo):
    _edit(repo, "radio_system.yaml", lambda d: d["parameters"]["tx_power_dbm"].update(value=43.0))
    assert {i.name: i.state for i in rb.modified(repo)} == {"radio.tx_power_dbm": "modified"}
    assert not hasattr(rb, "require_baseline")                     # a modified file is classified, never blocked


def test_wording_changes_do_not_modify_the_baseline(repo):
    _edit(repo, "radio_system.yaml", lambda d: d["parameters"]["tx_power_dbm"].update(justification="reworded"))
    assert rb.modified(repo) == []


def test_candidate_thresholds_and_rate_constants_belong_to_the_baseline(repo):
    _edit(repo, "site_rule.yaml", lambda d: d["candidate_thresholds"].update(min_spacing_m=80.0))
    _edit(repo, "radio_system.yaml", lambda d: d["rate_mappings"]["lte"].update(thr_max_bps_hz=4.8))
    assert {i.name for i in rb.modified(repo)} == {"site_rule", "rate_mappings"}


def test_recording_makes_the_current_configuration_the_baseline(repo):
    _edit(repo, "site_rule.yaml", lambda d: d["candidate_thresholds"].update(min_spacing_m=80.0))
    rb.record(repo, note="test refinement", recorded_on="2026-11-27")
    assert rb.modified(repo) == []
