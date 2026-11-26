"""Non-UI support of the application: finding saved runs and following a started run."""

import json
from datetime import datetime, timezone

import numpy as np

from bns.app import control, results


def fake_run(root, name, created, kind="multi_site"):
    folder = root / "outputs" / "runs" / "development" / name
    folder.mkdir(parents=True)
    manifest = {"run_id": name, "kind": kind, "mode": "development", "created_utc": created,
                "label": "DEVELOPMENT — NOT APPROVED FOR RESEARCH",
                "grid": {"center_xy": [0, 0], "size_xy": [20, 10], "cell_size_m": 10, "height_m": 1.5},
                "scenarios": [{"id": "lte_1800"}],
                "sites": [{"candidate_id": "site-001", "x": 0, "y": 0, "z": 30}],
                "sectors_per_site": [{"pattern": "tr38901", "orientation_rad": [0.0, 0.17, 0.0]}]}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps({"results": {"lte_1800": {"network": {"coverage_fraction": 0.5}}}}),
                                         encoding="utf-8")
    np.savez(folder / results.ARRAYS[kind], outdoor=np.array([[True, False]]),
             lte_1800_sinr_db=np.array([[3.0, -np.inf]]), lte_1800_alone0_sinr_db=np.array([[4.0, -np.inf]]))
    return folder


def test_runs_are_listed_newest_first_and_incomplete_folders_are_skipped(tmp_path):
    fake_run(tmp_path, "old", "2026-11-01T00:00:00+00:00")
    fake_run(tmp_path, "new", "2026-11-02T00:00:00+00:00")
    (tmp_path / "outputs" / "runs" / "development" / "half").mkdir()
    runs = results.list_runs(tmp_path)
    assert [r.run_id for r in runs] == ["new", "old"]
    r = runs[0]
    assert r.is_development and r.grid.shape == (1, 2)
    assert r.layers() == ["sinr_db"]                       # per-site layers are not offered as map layers
    assert r.site_alone_sinr("lte_1800", 0)[0, 0] == 4.0
    assert r.scenario_summary("lte_1800")["coverage_fraction"] == 0.5
    assert r.sector_azimuths_rad == [0.0]


def test_cdf_drops_or_floors_cells_without_a_value():
    x, p = results.cdf(np.array([2.0, -np.inf, 1.0]))
    assert x.tolist() == [1.0, 2.0] and p.tolist() == [0.5, 1.0]
    x, _ = results.cdf(np.array([2.0, -np.inf]), floor=-40)
    assert x.tolist() == [-40.0, 2.0]


def test_argv_uses_either_the_named_buildings_or_the_site_rule(tmp_path):
    base = {"area": "a", "variant": "osm", "profile": "preview", "mode": "development"}
    by_rule = control.build_argv(tmp_path, {**base, "buildings": [], "sites": 3, "min_height_m": 10,
                                            "min_spacing_m": 100})
    assert by_rule[-6:] == ["--sites", "3", "--min-height", "10.0", "--min-spacing", "100.0"]
    named = control.build_argv(tmp_path, {**base, "buildings": ["way/1", "way/2"]})
    assert named[-3:] == ["--buildings", "way/1", "way/2"] and "--sites" not in named


def test_state_is_read_from_the_log_of_a_finished_run(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "request.json").write_text(json.dumps({"pid": 999999999, "started_utc":
                                                     datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    (folder / "log.txt").write_text('WORKLOAD {"jobs": 6, "cached": 2, "to_trace": 4, "estimate": null}\n'
                                    "PROGRESS 2/4 8.1 s\nPROGRESS 4/4 7.9 s\nOUTPUT D:/x/run-1\n", encoding="utf-8")
    s = control.state(folder)
    assert not s.running and s.returncode == 0
    assert s.progress == (4, 4) and s.workload["cached"] == 2 and s.output.name == "run-1"
    (folder / "log.txt").write_text("PROGRESS 1/4 8 s\nCANCELLED finished traces stay cached\n", encoding="utf-8")
    assert control.state(folder).cancelled and control.state(folder).returncode == 2
    control.cancel(folder)
    assert (folder / "cancel").exists()



def test_runs_that_differ_in_profile_or_load_override_are_flagged_as_not_comparable(tmp_path):
    a = results.load_run(fake_run(tmp_path, "a", "2026-11-01T00:00:00+00:00"))
    b = results.load_run(fake_run(tmp_path, "b", "2026-11-02T00:00:00+00:00"))
    for r in (a, b):
        r.manifest.update(area={"name": "x", "variant": "osm"}, profile={"name": "preview", "cell_size_m": 25,
                                                                        "rays_per_site": 1e8})
    assert results.differences(a, b) == []
    b.manifest["profile"] = {"name": "standard", "cell_size_m": 10, "rays_per_site": 1e9}
    b.manifest["overrides_for_sensitivity"] = {"interference_activity": 0.5}
    assert results.differences(a, b) == ["profile", "sensitivity overrides"]
