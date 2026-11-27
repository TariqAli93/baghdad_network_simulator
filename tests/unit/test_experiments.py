"""Experiments: editable configurations, kept apart from the immutable runs made from them."""

import json

import pytest

from bns.app import experiments as xp


def config(**changes):
    base = dict(name="5G baseline", area="tahrir_bab_al_sharqi_study", variant="synthetic_urban-seed42+fp_3d_globfp",
                profile="standard", cell_size_m=10.0, rays_per_site=int(1e9), backend="cpu", rx_height_m=1.5,
                radio={"coverage_threshold": -10.0, "interference_activity": 1.0, "noise_figure_db": 9.0,
                       "rain_rate_mm_h": 0.0},
                carriers=[{"id": "nr_3500", "preset": "nr_3500", "frequency_hz": 3.5e9, "bandwidth_hz": 1e8}],
                stations=[{"station_id": "S1", "x": 1.0, "y": 2.0, "antenna_height_m": 58.0, "mount": "rooftop"}],
                template={"tx_power_dbm": 46.0})
    base.update(changes)
    return xp.Experiment.new(**base)


def test_save_and_open_round_trip_everything_the_configuration_holds(tmp_path):
    saved = xp.save(tmp_path, config())
    again = xp.load(tmp_path, saved.experiment_id)
    assert again == saved
    assert again.modified_utc >= again.created_utc


def test_save_as_and_duplicate_make_new_experiments_and_leave_the_original(tmp_path):
    a = xp.save(tmp_path, config())
    b = xp.save_as(tmp_path, a, "6G at the same sites")
    c = xp.duplicate(tmp_path, a.experiment_id, "copy")
    assert len({a.experiment_id, b.experiment_id, c.experiment_id}) == 3
    assert b.stations == a.stations and b.origin == {"saved_as_from": a.experiment_id}
    assert c.origin == {"duplicated_from": a.experiment_id}
    assert xp.load(tmp_path, a.experiment_id).name == "5G baseline"


def test_rename_changes_only_the_name(tmp_path):
    a = xp.save(tmp_path, config())
    xp.rename(tmp_path, a.experiment_id, "renamed")
    b = xp.load(tmp_path, a.experiment_id)
    assert b.name == "renamed" and b.stations == a.stations


def test_delete_moves_the_configuration_aside_and_keeps_runs(tmp_path):
    a = xp.save(tmp_path, config())
    run = tmp_path / "outputs" / "runs" / "development" / "multi_site-x"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"experiment": {"id": a.experiment_id}}), encoding="utf-8")
    xp.delete(tmp_path, a.experiment_id)
    assert [e.experiment_id for e in xp.list_all(tmp_path)] == []
    assert (run / "manifest.json").exists()                       # completed runs are history
    assert any(xp.folder(tmp_path).joinpath(".deleted").iterdir())   # recoverable


def test_runs_of_an_experiment_come_from_the_runs_themselves(tmp_path):
    a = xp.save(tmp_path, config())
    for name, owner in (("multi_site-1", a.experiment_id), ("multi_site-2", "other"), ("multi_site-3", a.experiment_id)):
        run = tmp_path / "outputs" / "runs" / "development" / name
        run.mkdir(parents=True)
        (run / "manifest.json").write_text(json.dumps({"experiment": {"id": owner},
                                                       "created_utc": name[-1]}), encoding="utf-8")
    assert xp.runs_of(tmp_path, a.experiment_id) == ["multi_site-3", "multi_site-1"]


def test_unreadable_files_are_skipped_not_fatal(tmp_path):
    xp.save(tmp_path, config())
    (xp.folder(tmp_path) / "broken.json").write_text("{not json", encoding="utf-8")
    assert len(xp.list_all(tmp_path)) == 1


def test_names_need_a_character_and_ids_are_safe_file_names(tmp_path):
    with pytest.raises(ValueError):
        xp.save(tmp_path, config(name="  "))
    arabic = xp.save(tmp_path, config(name="تجربة الجيل السادس"))
    assert arabic.experiment_id.isascii() and "/" not in arabic.experiment_id
    assert xp.load(tmp_path, arabic.experiment_id).name == "تجربة الجيل السادس"
