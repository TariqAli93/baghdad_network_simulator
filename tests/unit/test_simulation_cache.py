"""Propagation jobs, cache keys and the path-gain cache."""

import dataclasses
import json

import numpy as np
import pytest

from bns.geospatial.grid import Grid
from bns.simulation.cache import PathGainCache, scene_fingerprint
from bns.simulation.jobs import Antenna, Mechanisms, PropagationJob

ENGINE = {"sionna-rt": "2.2.0", "mitsuba": "3.9.1", "drjit": "1.5.0",
          "variant": "llvm_ad_mono_polarized", "wedge_table_slots": 1048576}


def job(**changes):
    base = PropagationJob(
        scene_fingerprint="scene-abc", scene_dir=None, frequency_hz=3.5e9,
        tx_position_m=(10.0, -5.0, 33.0), antenna=Antenna("iso", "V", (0.0, 0.0, 0.0)),
        grid=Grid((0.0, 0.0), (100.0, 100.0), 10.0, 1.5),
        mechanisms=Mechanisms(max_depth=2, los=True, specular_reflection=True, diffraction=True,
                              refraction=False, diffuse_reflection=False, edge_diffraction=False),
        rays_per_site=10**8, seeds=(1,), engine=ENGINE)
    return dataclasses.replace(base, **changes)


@pytest.mark.parametrize("change", [
    {"scene_fingerprint": "scene-xyz"},
    {"frequency_hz": 28e9},
    {"tx_position_m": (10.0, -5.0, 36.0)},
    {"antenna": Antenna("tr38901", "V", (0.0, 0.0, 0.0))},
    {"antenna": Antenna("iso", "H", (0.0, 0.0, 0.0))},
    {"grid": Grid((0.0, 0.0), (100.0, 100.0), 5.0, 1.5)},
    {"grid": Grid((0.0, 0.0), (100.0, 100.0), 10.0, 2.0)},
    {"mechanisms": Mechanisms(3, True, True, True, False, False, False)},
    {"mechanisms": Mechanisms(2, True, True, False, False, False, False)},
    {"rays_per_site": 10**9},
    {"seeds": (2,)},
    {"engine": {**ENGINE, "sionna-rt": "2.3.0"}},
    {"engine": {**ENGINE, "wedge_table_slots": 10000}},
])
def test_every_propagation_dependency_changes_the_key(change):
    assert job(**change).key() != job().key()


def test_the_key_is_stable_and_ignores_the_scene_folder_location():
    assert job().key() == job().key()
    assert job(scene_dir="D:/elsewhere").key() == job().key()


def test_tiny_float_noise_in_the_position_does_not_split_the_cache():
    assert job(tx_position_m=(10.0 + 1e-9, -5.0, 33.0)).key() == job().key()


def test_radio_system_parameters_are_not_part_of_a_propagation_job():
    names = {f.name for f in dataclasses.fields(PropagationJob)}
    assert not names & {"tx_power_dbm", "noise_figure_db", "bandwidth_hz", "coverage_threshold_dbm"}


def test_scene_fingerprint_follows_geometry_heights_and_materials(tmp_path):
    (tmp_path / "meshes").mkdir()
    (tmp_path / "scene.xml").write_text('<scene><string name="type" value="concrete"/></scene>')
    (tmp_path / "meshes" / "buildings.ply").write_bytes(b"ply-heights-9m")
    first = scene_fingerprint(tmp_path)
    (tmp_path / "quality_report.md").write_text("reports do not matter")
    assert scene_fingerprint(tmp_path) == first
    (tmp_path / "meshes" / "buildings.ply").write_bytes(b"ply-heights-12m")
    second = scene_fingerprint(tmp_path)
    assert second != first
    (tmp_path / "scene.xml").write_text('<scene><string name="type" value="brick"/></scene>')
    assert scene_fingerprint(tmp_path) != second
    assert scene_fingerprint(None) == "empty-scene"


def staged(tmp_path, key, values):
    folder = tmp_path / "staging"
    folder.mkdir(exist_ok=True)
    PathGainCache.write_entry(folder, key, np.asarray(values), {"note": "test"})
    return folder


def test_published_entries_are_read_back_with_their_manifest(tmp_path):
    cache = PathGainCache(tmp_path / "cache")
    assert cache.get("k1") is None
    cache.publish(staged(tmp_path, "k1", [[1e-9, 0.0]]), ["k1"])
    gain, manifest = cache.get("k1")
    assert gain.tolist() == [[1e-9, 0.0]] and manifest["note"] == "test"


def test_an_entry_without_manifest_or_with_a_wrong_checksum_is_a_miss(tmp_path):
    cache = PathGainCache(tmp_path / "cache")
    cache.publish(staged(tmp_path, "k2", [1.0]), ["k2"])
    data, meta = cache.paths("k2")
    meta.unlink()
    assert cache.get("k2") is None
    cache.publish(staged(tmp_path, "k3", [1.0]), ["k3"])
    data, meta = cache.paths("k3")
    data.write_bytes(data.read_bytes() + b"x")
    assert cache.get("k3") is None


def test_publishing_a_key_that_was_not_staged_is_an_error(tmp_path):
    cache = PathGainCache(tmp_path / "cache")
    with pytest.raises(FileNotFoundError):
        cache.publish(staged(tmp_path, "k4", [1.0]), ["missing"])
    assert cache.get("k4") is None                 # nothing published by a failed call


def test_job_round_trips_through_json():
    original = job(scene_dir="D:/scenes/x")
    assert PropagationJob.from_dict(json.loads(json.dumps(original.to_dict()))) == original
