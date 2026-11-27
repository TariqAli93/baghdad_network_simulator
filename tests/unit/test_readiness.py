"""Readiness indicators: scientific status computed from the files, never marked done without evidence."""

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


def _rules(repo):
    return yaml.safe_load((repo / "configs" / "study_area.yaml").read_text(encoding="utf-8"))[
        "areas"][AREA]["observations"].get("method_requirements")


def _dataset(repo, variant, *, fit, missing, priorities=("P0", "P1", "P2", "S"), rules="current"):
    rules = _rules(repo) if rules == "current" else rules
    folder = repo / "outputs" / "datasets" / AREA / variant
    folder.mkdir(parents=True)
    listed = 6
    (folder / "quality_report.json").write_text(json.dumps(
        {"fit_for_research": fit, "not_fit_reasons": [] if fit else ["observation worklist incomplete"],
         "height_categories": {"by_count_percent": {"observed": 1.0, "estimated": 1.0, "placeholder": 98.0}}}),
        encoding="utf-8")
    (folder / "dataset_manifest.json").write_text(json.dumps(
        {"created_utc": "2026-11-27T00:00:00+00:00",
         "inputs": {"required_observations": {"required_priorities": list(priorities), "count": listed,
                                              "method_requirements": rules}},
         "observation_worklist": {"listed": listed, "observed": listed - len(missing), "unmatched": 0,
                                  "missing": missing}}), encoding="utf-8")


def _ind(repo):
    return {i.id: i for i in rd.indicators(repo)}


def test_indicators_are_scientific_and_in_order(repo):
    assert [i.id for i in rd.indicators(repo)] == ["dataset", "heights", "observations", "synthetic", "candidates",
                                                    "configuration", "convergence", "validation", "matlab", "laptop"]
    states = {i.state for i in rd.indicators(repo)}
    assert states <= {rd.READY, rd.COMPLETED, rd.INCOMPLETE, rd.PENDING, rd.BASELINE, rd.CUSTOM,
                      rd.SYNTHETIC_COMPLETE}


def test_nothing_is_completed_without_evidence(repo):
    g = _ind(repo)
    assert g["configuration"].state == rd.BASELINE
    for i in ("dataset", "heights", "observations", "synthetic", "candidates"):
        assert g[i].state == rd.INCOMPLETE
    for i in ("convergence", "validation", "matlab", "laptop"):
        assert g[i].state == rd.PENDING
    assert not hasattr(rd, "require_research_ready")                # information only, never a gate


def test_observation_progress_has_separate_groups_with_the_p2_fallback(repo):
    _dataset(repo, "osm+fp", fit=False, missing=["way/1", "way/2", "way/3", "way/5"])
    groups = {tuple(g["priorities"]): g for g in _ind(repo)["observations"].data["groups"]}
    assert set(groups) == {("P0", "P1"), ("P2",), ("S",)}
    assert groups[("P0", "P1")]["accepted"] == ["measured", "documented"]
    assert "storey_count" in groups[("P2",)]["accepted"] and groups[("P2",)]["preferred"] == ["measured", "documented"]
    assert (groups[("P0", "P1")]["observed"], groups[("P0", "P1")]["required"]) == (1, 2)
    assert (groups[("P2",)]["observed"], groups[("P2",)]["required"]) == (0, 2)
    assert (groups[("S",)]["observed"], groups[("S",)]["required"]) == (1, 2)
    assert _ind(repo)["observations"].data["covered_by_sensitivity"] == {"P3": 3}


def test_a_dataset_built_for_other_requirements_does_not_count(repo):
    _dataset(repo, "old", fit=True, missing=[], priorities=("P0", "P1", "P2", "P3"))
    _dataset(repo, "old-rules", fit=True, missing=[], rules=None)
    g = _ind(repo)
    assert g["dataset"].state == rd.INCOMPLETE and "rebuild" in g["dataset"].detail
    assert g["observations"].state == rd.INCOMPLETE


def test_a_fit_dataset_completes_heights_and_observations(repo):
    _dataset(repo, "osm+fp+observations-1234abcd", fit=True, missing=[])
    g = _ind(repo)
    assert (g["dataset"].state, g["heights"].state, g["observations"].state) == (rd.READY, rd.READY, rd.COMPLETED)
    assert g["convergence"].state == rd.PENDING                     # still to be measured on the final scene


def test_a_changed_configuration_is_a_custom_experiment_not_an_approval_problem(repo):
    path = repo / "configs" / "radio_system.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["parameters"]["noise_figure_db"]["value"] = 7.0
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    g = _ind(repo)["configuration"]
    assert g.state == rd.CUSTOM and "noise_figure_db" in g.detail
    assert "approv" not in g.detail.lower()


def test_the_repository_state():
    g = {i.id: i for i in rd.indicators(ROOT)}
    assert g["configuration"].state == rd.BASELINE
    assert g["validation"].state == rd.COMPLETED                     # TR 38.901 comparison saved
    assert g["convergence"].state == rd.PENDING
    assert g["observations"].state == rd.INCOMPLETE
