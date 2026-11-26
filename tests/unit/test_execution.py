"""Execution is independent of scientific classification: every technically valid experiment loads
and is classified; only technical problems stop it (the full loader, not only the interface)."""

from pathlib import Path

import pytest

from bns.analysis import classification as cl
from bns.simulation import experiment as ex

ROOT = Path(__file__).resolve().parents[2]
STUDY = ("tahrir_bab_al_sharqi_study", "osm+fp_3d_globfp")
V2 = ("tahrir_bab_al_sharqi_v2", "osm")


def need(area, variant):
    if not (ROOT / "data" / "scenes" / area / variant / "scene.xml").exists():
        pytest.skip(f"scene {area}/{variant} not built on this computer")


@pytest.mark.parametrize("area, variant", [STUDY, V2])
@pytest.mark.parametrize("profile", ["preview", "standard"])
@pytest.mark.parametrize("mode", ["development", "research"])
def test_baseline_values_load_on_both_datasets_with_every_profile_and_any_mode(area, variant, profile, mode):
    need(area, variant)
    exp = ex.load(ROOT, area, variant, profile, mode)                 # no refusal of any kind
    c = exp.classification
    assert c.result == cl.PRELIMINARY and c.dataset == cl.INCOMPLETE and c.validation == cl.PENDING
    if profile == "standard":
        assert c.configuration == cl.BASELINE and c.deviations == ()
    else:
        assert c.configuration == cl.CUSTOM and any("preview profile" in d for d in c.deviations)
    notes = ex.limitations(exp)
    assert any("validation pending" in n for n in notes)
    if area == V2[0]:
        assert any("not the study district" in n for n in notes)       # provisional area: never complete


def test_modified_values_run_as_a_custom_experiment_and_load_changes_as_a_sensitivity_analysis():
    need(*STUDY)
    custom = ex.load(ROOT, *STUDY, "standard", overrides={"tx_power_dbm": 43.0})
    assert custom.classification.configuration == cl.CUSTOM and custom.system.require(
        "tx_power_dbm", "lte_1800", mode="development") == 43.0
    sens = ex.load(ROOT, *STUDY, "standard", overrides={"interference_activity": 0.5})
    assert sens.classification.configuration == cl.SENSITIVITY
    assert sens.classification.result == cl.PRELIMINARY               # incomplete data: never more than preliminary


def test_sites_and_jobs_can_be_prepared_on_the_provisional_area():
    need(*V2)
    exp = ex.load(ROOT, *V2, "preview")
    placed = ex.place_sites(exp, [max(exp.receiver_buildings, key=lambda b: b.height.height_m).building_id])
    jobs = ex.jobs_for(exp, placed)
    assert len(jobs) == len(exp.scenarios) and all(len(js) == len(exp.antennas) for js in jobs.values())


def test_run_control_reports_execution_separately_from_classification(tmp_path):
    import json
    from datetime import datetime, timezone

    from bns.app import control

    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "request.json").write_text(json.dumps({"pid": 999999999, "started_utc":
                                                     datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    (folder / "log.txt").write_text("CLASS Preliminary Simulation · Research Baseline\nLIMITATION validation pending\n"
                                    "OUTPUT x\n", encoding="utf-8")
    s = control.state(folder)
    assert s.execution == "Completed" and s.limitations == ["validation pending"]
    (folder / "log.txt").write_text("CANCELLED\n", encoding="utf-8")
    assert control.state(folder).execution == "Cancelled"
    (folder / "log.txt").write_text("ERROR No dataset\n", encoding="utf-8")
    assert control.state(folder).execution == "Failed"
    argv = control.build_argv(tmp_path, {"area": "a", "variant": "v", "profile": "standard", "buildings": [], "sites": 1})
    assert "--mode" not in argv                                         # no mode to choose
