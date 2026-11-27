"""Validation evidence applies only to runs inside its documented propagation scope."""

import json
import shutil
from pathlib import Path

import yaml

from bns.analysis import classification as cl
from bns.analysis import validation_scope as vs

ROOT = Path(__file__).resolve().parents[2]
ANT = [{"pattern": "tr38901", "polarization": "V", "orientation_rad": [1.5708, 0.1745, 0.0]}]
MECH = {"max_depth": 2, "los": True, "specular_reflection": True, "diffraction": True, "refraction": False,
        "diffuse_reflection": False, "edge_diffraction": False}
ENGINE = {"sionna-rt": "2.2.0", "mitsuba": "3.9.1", "drjit": "1.5.0", "variant": "llvm_ad_mono_polarized",
          "wedge_table_slots": 1048576}
GRID = {"center_xy": [0.0, 0.0], "size_xy": [1000.0, 1000.0], "cell_size_m": 25.0, "height_m": 1.5}


def scope(**change):
    args = {"scene_fingerprint": "scene-a", "grid": GRID, "rays_per_site": 10**8, "engine": ENGINE,
            "antennas": ANT, "mechanisms": MECH, "seeds": [1]} | change
    return vs.scope(**args)


def manifest(s_fp="scene-a", cell=25.0, rays=10**8, variant="llvm_ad_mono_polarized", tilt=0.1745):
    return {"area": {"scene_fingerprint": s_fp}, "grid": {**GRID, "cell_size_m": cell},
            "profile": {"name": "preview", "cell_size_m": cell, "rays_per_site": rays},
            "backend": {"name": "cpu" if "llvm" in variant else "gpu", "variant": variant},
            "versions": {"sionna-rt": "2.2.0", "mitsuba": "3.9.1", "drjit": "1.5.0"},
            "sectors_per_site": [{**ANT[0], "orientation_rad": [1.5708, tilt, 0.0]}],
            "mechanisms": MECH, "seeds": [1]}


def test_every_propagation_input_is_part_of_the_scope():
    base = vs.key(scope())
    assert vs.key(scope()) == base
    for change in ({"scene_fingerprint": "scene-b"}, {"grid": {**GRID, "cell_size_m": 10.0}},
                   {"grid": {**GRID, "height_m": 2.0}}, {"rays_per_site": 10**9},
                   {"engine": {**ENGINE, "variant": "cuda_ad_mono_polarized"}},
                   {"engine": {**ENGINE, "sionna-rt": "2.3.0"}},
                   {"antennas": [{**ANT[0], "orientation_rad": [0.0, 0.1745, 0.0]}]},
                   {"mechanisms": {**MECH, "max_depth": 3}}, {"seeds": [2]}):
        assert vs.key(scope(**change)) != base, change


def test_a_scope_is_read_back_from_a_run_manifest():
    assert vs.key(vs.from_manifest(manifest())) == vs.key(scope())
    assert vs.from_manifest({"area": {}}) is None                     # incomplete record: no scope, no evidence


def _repo(tmp_path):
    (tmp_path / "configs").mkdir(parents=True)
    for p in (ROOT / "configs").glob("*.yaml"):
        shutil.copy(p, tmp_path / "configs" / p.name)
    return tmp_path


def _evidence(repo, run_manifest, median_db):
    run = repo / "outputs" / "runs" / "development" / "source"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps(run_manifest), encoding="utf-8")
    case = repo / "validation" / "matlab" / "case1"
    case.mkdir(parents=True)
    (case / "case.json").write_text(json.dumps({"source_run": "outputs/runs/development/source"}), encoding="utf-8")
    (case / "comparison.json").write_text(json.dumps({"nr_3500_LOS": {"n": 9, "reached": 9, "median_db": median_db}}),
                                          encoding="utf-8")


def _accept_convergence(repo, profile, s_fp, backend="cpu"):
    path = repo / "configs" / "simulation.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["profiles"][profile]["final_scene_convergence"] = {"status": "accepted", "scene_fingerprint": s_fp,
                                                            "backend": backend}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_evidence_validates_only_runs_inside_its_scope(tmp_path):
    repo = _repo(tmp_path)
    _evidence(repo, manifest(), median_db=1.1)
    _accept_convergence(repo, "preview", "scene-a")
    inside = vs.from_manifest(manifest())
    assert cl.validation_class(repo, inside, profile="preview") == cl.VALIDATED
    # other scene, other ray count, other backend, other antenna: evidence does not apply
    for other in (manifest(s_fp="scene-b"), manifest(rays=10**9), manifest(variant="cuda_ad_mono_polarized"),
                  manifest(tilt=0.0)):
        assert cl.validation_class(repo, vs.from_manifest(other), profile="preview") == cl.PENDING
    assert cl.validation_class(repo, None, profile="preview") == cl.PENDING


def test_both_kinds_of_evidence_are_needed_and_the_matlab_criterion_must_hold(tmp_path):
    repo = _repo(tmp_path)
    _evidence(repo, manifest(), median_db=3.5)                         # beyond the 2.0 dB B1 tolerance
    _accept_convergence(repo, "preview", "scene-a")
    assert cl.validation_class(repo, vs.from_manifest(manifest()), profile="preview") == cl.PENDING
    repo2 = _repo(tmp_path / "second")
    _evidence(repo2, manifest(), median_db=1.0)                        # MATLAB passes, convergence not accepted
    assert cl.validation_class(repo2, vs.from_manifest(manifest()), profile="preview") == cl.PENDING


def test_radio_system_changes_keep_the_propagation_evidence():
    from bns.simulation import experiment as ex

    if not (ROOT / "data" / "scenes" / "tahrir_bab_al_sharqi_v2" / "osm" / "scene.xml").exists():
        import pytest
        pytest.skip("scene not built on this computer")
    a = ex.load(ROOT, "tahrir_bab_al_sharqi_v2", "osm", "preview")
    b = ex.load(ROOT, "tahrir_bab_al_sharqi_v2", "osm", "preview",
                overrides={"tx_power_dbm": 40.0, "noise_figure_db": 7.0, "interference_activity": 0.5})
    c = ex.load(ROOT, "tahrir_bab_al_sharqi_v2", "osm", "preview", overrides={"mechanical_downtilt_deg": 6.0})
    assert a.classification.validation_scope == b.classification.validation_scope        # radio only: same scope
    assert a.classification.validation_scope != c.classification.validation_scope        # antenna: new scope
