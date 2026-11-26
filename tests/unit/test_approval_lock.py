"""An approved value that changes loses its approval until it is reconfirmed (approval lock)."""

import shutil
from pathlib import Path

import pytest
import yaml

from bns.analysis import approval_lock as al

ROOT = Path(__file__).resolve().parents[2]
FILES = ("radio_system.yaml", "site_rule.yaml", "study_area.yaml", "simulation.yaml", "approvals.yaml",
         "approval_lock.yaml", "scenarios.yaml")


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "configs").mkdir()
    for name in FILES:
        shutil.copy(ROOT / "configs" / name, tmp_path / "configs" / name)
    return tmp_path


def test_the_repository_configuration_matches_its_recorded_approvals():
    report = al.check(ROOT)
    assert report, "no approved item found"
    assert [i.name for i in report if i.state != "locked"] == []


def test_every_approved_radio_parameter_and_the_rate_mappings_are_locked():
    names = {i.name for i in al.check(ROOT)}
    radio = yaml.safe_load((ROOT / "configs" / "radio_system.yaml").read_text(encoding="utf-8"))["parameters"]
    assert {f"radio.{n}" for n, e in radio.items() if e["status"] == "approved"} <= names
    assert {"rate_mappings", "site_rule", "height_policy", "profile.standard", "research_backend",
            "area.tahrir_bab_al_sharqi_study", "B1_tolerance"} <= names


def _edit(repo, name, change):
    path = repo / "configs" / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_changing_an_approved_value_marks_it_changed(repo):
    _edit(repo, "radio_system.yaml", lambda d: d["parameters"]["tx_power_dbm"].update(value=43.0))
    changed = {i.name: i.state for i in al.check(repo) if i.state != "locked"}
    assert changed == {"radio.tx_power_dbm": "changed"}
    with pytest.raises(al.ApprovalChanged, match="tx_power_dbm"):
        al.require_unchanged(repo)


def test_editing_comments_or_justifications_does_not_change_an_approval(repo):
    _edit(repo, "radio_system.yaml", lambda d: d["parameters"]["tx_power_dbm"].update(justification="reworded"))
    assert all(i.state == "locked" for i in al.check(repo))


def test_changing_a_rate_constant_or_the_site_rule_is_detected(repo):
    _edit(repo, "radio_system.yaml", lambda d: d["rate_mappings"]["lte"].update(thr_max_bps_hz=4.8))
    _edit(repo, "site_rule.yaml", lambda d: d.update(edge_inset_m=2.0))
    states = {i.name: i.state for i in al.check(repo)}
    assert states["rate_mappings"] == "changed" and states["site_rule"] == "changed"


def test_a_newly_approved_value_without_a_lock_entry_is_not_confirmed(repo):
    _edit(repo, "simulation.yaml", lambda d: d["profiles"]["preview"].update(status="approved", approved_by="x"))
    assert {i.name: i.state for i in al.check(repo)}["profile.preview"] == "not recorded"


def test_recording_reconfirms_the_current_values(repo):
    _edit(repo, "radio_system.yaml", lambda d: d["parameters"]["tx_power_dbm"].update(value=43.0))
    al.record(repo, confirmed_by="test", confirmed_on="2026-11-27")
    assert all(i.state == "locked" for i in al.check(repo))
