"""Scientific classification of results: configuration, dataset and validation are separate states,
and none of them decides whether a run may execute."""

import json
import shutil
from pathlib import Path

import pytest

from bns.analysis import classification as cl

ROOT = Path(__file__).resolve().parents[2]


def test_configuration_class_follows_the_overrides_and_deviations():
    assert cl.configuration_class({}) == cl.BASELINE
    assert cl.configuration_class({"interference_activity": 0.5}) == cl.SENSITIVITY
    assert cl.configuration_class({"rain_rate_mm_h": 18.6, "coverage_threshold": 0.0}) == cl.SENSITIVITY
    assert cl.configuration_class({"tx_power_dbm": 43.0}) == cl.CUSTOM
    assert cl.configuration_class({}, ["GPU backend"]) == cl.CUSTOM          # baseline values, other backend
    assert cl.configuration_class({"interference_activity": 0.5}, ["preview profile"]) == cl.CUSTOM


def test_dataset_quality_has_three_levels_and_a_provisional_area_is_never_complete():
    assert cl.dataset_class({"fit_for_research": True}, study_district=True) == cl.COMPLETE
    assert cl.dataset_class({"fit_for_research": True}, study_district=False) == cl.INCOMPLETE
    assert cl.dataset_class({"fit_for_research": False, "height_model": {"name": "mixed"}}, study_district=True) \
        == cl.ESTIMATED
    assert cl.dataset_class({"fit_for_research": False, "height_model": None}, study_district=True) == cl.INCOMPLETE


@pytest.mark.parametrize("config, dataset, validation, result", [
    (cl.BASELINE, cl.COMPLETE, cl.VALIDATED, cl.VALIDATED_RESULTS),
    (cl.BASELINE, cl.COMPLETE, cl.PENDING, "Research Baseline · Validation Pending"),
    (cl.BASELINE, cl.ESTIMATED, cl.VALIDATED, cl.PRELIMINARY),
    (cl.BASELINE, cl.INCOMPLETE, cl.PENDING, cl.PRELIMINARY),
    (cl.CUSTOM, cl.COMPLETE, cl.VALIDATED, cl.CUSTOM),
    (cl.SENSITIVITY, cl.COMPLETE, cl.PENDING, cl.SENSITIVITY),
    (cl.SENSITIVITY, cl.INCOMPLETE, cl.PENDING, cl.PRELIMINARY),
    (cl.NOT_RECORDED, cl.COMPLETE, cl.VALIDATED, cl.PRELIMINARY),
])
def test_only_validated_baseline_runs_on_complete_data_are_validated_research_results(config, dataset, validation,
                                                                                    result):
    c = cl.Classification(config, dataset, validation)
    assert c.result == result
    assert c.validated == (config == cl.BASELINE and dataset == cl.COMPLETE and validation == cl.VALIDATED)


def test_the_label_names_all_three_states_and_never_mentions_approval():
    c = cl.Classification(cl.CUSTOM, cl.INCOMPLETE, cl.PENDING, ("tx_power_dbm = 43.0",))
    assert c.label == "Preliminary Simulation · Custom Experiment · Incomplete data · Validation Pending"
    assert "tx_power_dbm = 43.0" in c.details
    for config in (cl.BASELINE, cl.CUSTOM, cl.SENSITIVITY, cl.NOT_RECORDED):
        for data in (cl.COMPLETE, cl.ESTIMATED, cl.INCOMPLETE):
            for val in (cl.VALIDATED, cl.PENDING):
                text = cl.Classification(config, data, val).label.lower()
                assert "approv" not in text and "development" not in text


def test_classification_round_trips_through_the_manifest():
    c = cl.Classification(cl.SENSITIVITY, cl.ESTIMATED, cl.PENDING, ("interference_activity = 0.5",))
    assert cl.from_manifest({"classification": json.loads(json.dumps(c.as_dict()))}) == c


def test_historical_runs_are_preliminary_with_their_configuration_not_recorded():
    old = {"label": "DEVELOPMENT — NOT APPROVED FOR RESEARCH", "mode": "development",
           "area": {"fit_for_research": False}}
    c = cl.from_manifest(old)
    assert (c.configuration, c.dataset, c.validation, c.result) == (cl.NOT_RECORDED, cl.INCOMPLETE, cl.PENDING,
                                                                    cl.PRELIMINARY)
    assert "NOT APPROVED" not in c.label


def test_the_repository_validation_state_is_pending():
    assert cl.validation_class(ROOT) == cl.PENDING                # no final-scene convergence, no MATLAB run


def test_a_matlab_comparison_counts_only_if_it_meets_the_b1_criterion(tmp_path):
    from bns.analysis import readiness

    (tmp_path / "configs").mkdir()
    for p in (ROOT / "configs").glob("*.yaml"):
        shutil.copy(p, tmp_path / "configs" / p.name)
    case = tmp_path / "validation" / "matlab" / "case1"
    case.mkdir(parents=True)
    (case / "comparison.json").write_text(json.dumps({"nr_3500_LOS": {"n": 50, "reached": 50, "median_db": 3.1},
                                                      "nr_3500_NLOS": {"n": 20, "reached": 20, "median_db": 9.0}}))
    matlab = {i.id: i for i in readiness.indicators(tmp_path)}["matlab"]
    assert matlab.state == readiness.PENDING and "2.0 dB" in matlab.detail
    (case / "comparison.json").write_text(json.dumps({"nr_3500_LOS": {"n": 50, "reached": 50, "median_db": -1.2},
                                                      "nr_3500_NLOS": {"n": 20, "reached": 20, "median_db": 9.0}}))
    assert {i.id: i for i in readiness.indicators(tmp_path)}["matlab"].state == readiness.COMPLETED
