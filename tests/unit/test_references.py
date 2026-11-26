"""The scenario file and the reference registry must stay consistent."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = (ROOT / "docs" / "references.md").read_text(encoding="utf-8")
SCENARIOS = yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))["scenarios"]

# A registry entry is a table row that starts with an ID in backticks.
REGISTRY_IDS = re.findall(r"^\| `([A-Z0-9][A-Z0-9-]+)` \|", REGISTRY, flags=re.MULTILINE)


def test_registry_ids_are_unique():
    assert len(REGISTRY_IDS) > 20
    duplicates = {i for i in REGISTRY_IDS if REGISTRY_IDS.count(i) > 1}
    assert not duplicates


def test_every_scenario_cites_registered_sources():
    for scenario in SCENARIOS:
        assert scenario["sources"], f"{scenario['id']} cites no source"
        missing = set(scenario["sources"]) - set(REGISTRY_IDS)
        assert not missing, f"{scenario['id']} cites unknown sources {missing}"


def test_the_five_baseline_scenarios_are_unchanged():
    table = {s["id"]: (float(s["frequency_hz"]), float(s["bandwidth_hz"])) for s in SCENARIOS}
    assert table == {
        "lte_1800": (1.8e9, 20e6),
        "nr_3500": (3.5e9, 100e6),
        "nr_28000": (28e9, 400e6),
        "c6g_8000": (8e9, 400e6),
        "c6g_15000": (15e9, 400e6),
    }


def test_six_g_scenarios_are_labelled_candidate_and_three_point_five_assumed():
    status = {s["id"]: s["status"] for s in SCENARIOS}
    assert status["c6g_8000"] == status["c6g_15000"] == "candidate"
    assert status["nr_3500"] == "assumed"
    for s in SCENARIOS:
        if s["status"] == "candidate":
            assert "Candidate" in s["label"]


def test_candidate_carriers_fit_inside_the_bands_under_study():
    # Resolution 256 (WRC-23), Region 1: 7.75-8.4 GHz and 14.8-15.35 GHz
    limits = {"c6g_8000": (7.75e9, 8.4e9), "c6g_15000": (14.8e9, 15.35e9)}
    for s in SCENARIOS:
        if s["id"] in limits:
            low = float(s["frequency_hz"]) - float(s["bandwidth_hz"]) / 2
            high = float(s["frequency_hz"]) + float(s["bandwidth_hz"]) / 2
            assert limits[s["id"]][0] <= low and high <= limits[s["id"]][1]
