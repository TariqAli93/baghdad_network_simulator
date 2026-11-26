"""Readiness gates: tracked separately, computed from the files, never marked passed without evidence."""

import csv
import json
import shutil
from pathlib import Path

import pytest
import yaml

from bns.analysis import readiness as rd

ROOT = Path(__file__).resolve().parents[2]
AREA = "tahrir_bab_al_sharqi_study"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "configs").mkdir()
    for path in (ROOT / "configs").glob("*.yaml"):
        shutil.copy(path, tmp_path / "configs" / path.name)
    work = tmp_path / "outputs" / "datasets" / AREA / "fieldwork"
    work.mkdir(parents=True)
    rows = [{"building_id": f"way/{i}", "priority": p} for i, p in
            enumerate(["P0", "P1", "P2", "P2", "S", "S", "P3", "P3", "P3"])]
    with open(work / "observation_priorities.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["building_id", "priority"])
        w.writeheader()
        w.writerows(rows)
    return tmp_path


def _dataset(repo, variant, *, fit, missing, priorities=("P0", "P1", "P2", "S"), rules="current"):
    if rules == "current":
        rules = yaml.safe_load((repo / "configs" / "study_area.yaml").read_text(encoding="utf-8"))[
            "areas"][AREA]["observations"].get("method_requirements")
    folder = repo / "outputs" / "datasets" / AREA / variant
    folder.mkdir(parents=True)
    listed = 6
    (folder / "quality_report.json").write_text(json.dumps(
        {"fit_for_research": fit, "not_fit_reasons": [] if fit else ["observation worklist incomplete"]}), encoding="utf-8")
    (folder / "dataset_manifest.json").write_text(json.dumps(
        {"created_utc": "2026-11-27T00:00:00+00:00",
         "inputs": {"required_observations": {"required_priorities": list(priorities), "count": listed,
                                              "method_requirements": rules}},
         "observation_worklist": {"listed": listed, "observed": listed - len(missing), "unmatched": 0,
                                  "missing": missing}}), encoding="utf-8")


def _gates(repo):
    return {g.id: g for g in rd.gates(repo)}


def test_gates_are_the_eight_tracked_items_in_order(repo):
    assert [g.id for g in rd.gates(repo)] == ["methodology", "dataset", "observations", "candidate_criteria",
                                              "convergence", "matlab", "laptop", "delivery"]


def test_nothing_is_marked_met_without_evidence(repo):
    g = _gates(repo)
    assert g["methodology"].state == "reported"               # reported approval, no written reference
    for gid in ("dataset", "observations", "candidate_criteria"):
        assert g[gid].state == "not met"
    for gid in ("convergence", "matlab", "laptop"):
        assert g[gid].state == "not executed"
    assert g["delivery"].state == "not met"
    with pytest.raises(rd.NotReady):
        rd.require_research_ready(repo)


def test_observation_progress_counts_the_required_priorities_and_the_candidate_survey(repo):
    _dataset(repo, "osm+fp", fit=False, missing=["way/1", "way/2", "way/3", "way/5"])
    g = _gates(repo)["observations"]
    assert g.state == "not met"
    assert g.data["required"] == 6 and g.data["observed"] == 2
    assert g.data["by_priority"]["P0"] == {"required": 1, "observed": 1}
    assert g.data["by_priority"]["S"] == {"required": 2, "observed": 1}
    assert g.data["covered_by_sensitivity"] == {"P3": 3}


def test_a_dataset_built_for_an_older_requirement_does_not_count(repo):
    _dataset(repo, "old", fit=True, missing=[], priorities=("P0", "P1", "P2", "P3"))
    g = _gates(repo)
    assert g["observations"].state == "not met" and "rebuild" in g["observations"].detail
    assert g["dataset"].state == "not met"


def test_a_fit_dataset_with_complete_observations_meets_both_gates(repo):
    _dataset(repo, "osm+fp+observations-1234abcd", fit=True, missing=[])
    g = _gates(repo)
    assert g["dataset"].state == "met" and g["observations"].state == "met"


def test_research_is_locked_until_the_candidate_thresholds_and_convergence_exist(repo):
    _dataset(repo, "osm+fp+observations-1234abcd", fit=True, missing=[])
    with pytest.raises(rd.NotReady, match="candidate"):
        rd.require_research_ready(repo)
    rule = yaml.safe_load((repo / "configs" / "site_rule.yaml").read_text(encoding="utf-8"))
    rule["candidate_thresholds"] = {"min_roof_height_m": 12.0, "min_roof_area_m2": 100.0, "min_spacing_m": 150.0,
                                    "status": "approved"}
    (repo / "configs" / "site_rule.yaml").write_text(yaml.safe_dump(rule), encoding="utf-8")
    g = _gates(repo)
    assert g["candidate_criteria"].state == "met"
    assert g["methodology"].state == "not met"                # new approved value not confirmed in the lock
    with pytest.raises(rd.NotReady, match="convergence"):
        rd.require_research_ready(repo)


def test_a_changed_approved_value_breaks_the_methodology_gate(repo):
    path = repo / "configs" / "radio_system.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["parameters"]["noise_figure_db"]["value"] = 7.0
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    g = _gates(repo)["methodology"]
    assert g.state == "not met" and "noise_figure_db" in g.detail


def test_the_repository_state_is_locked_for_research():
    gates = {g.id: g for g in rd.gates(ROOT)}
    assert gates["methodology"].state == "reported"
    assert gates["candidate_criteria"].state == "not met"
    assert gates["convergence"].state == "not executed"
    with pytest.raises(rd.NotReady):
        rd.require_research_ready(ROOT)


def test_observation_progress_is_split_into_measured_heights_and_the_storey_survey(repo):
    _dataset(repo, "osm+fp", fit=False, missing=["way/1", "way/2", "way/3", "way/5"])
    groups = {tuple(g["priorities"]): g for g in _gates(repo)["observations"].data["groups"]}
    assert set(groups) == {("P0", "P1", "P2"), ("S",)}
    assert (groups[("P0", "P1", "P2")]["observed"], groups[("P0", "P1", "P2")]["required"]) == (1, 4)
    assert groups[("P0", "P1", "P2")]["accepted"] == ["measured", "documented"]
    assert (groups[("S",)]["observed"], groups[("S",)]["required"]) == (1, 2)
    assert "storey_count" in groups[("S",)]["accepted"]


def test_a_dataset_judged_under_looser_method_rules_does_not_count(repo):
    _dataset(repo, "old-rules", fit=True, missing=[], rules=None)        # built before method_requirements
    g = _gates(repo)
    assert g["dataset"].state == "not met" and g["observations"].state == "not met"
