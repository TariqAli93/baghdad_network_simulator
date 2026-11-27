"""Carriers: the five scenario presets and custom frequency/bandwidth variants, with their validity rules."""

from pathlib import Path

import pytest

from bns.app import carriers as ca

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def scene(tmp_path):
    (tmp_path / "scene.xml").write_text(
        '<scene version="2.1.0"><bsdf type="itu-radio-material" id="m"><string name="type" value="concrete"/>'
        '</bsdf><bsdf type="itu-radio-material" id="g"><string name="type" value="concrete"/></bsdf></scene>',
        encoding="utf-8")
    return tmp_path


def test_the_five_presets_come_from_the_scenario_file_unchanged():
    presets = ca.presets(ROOT)
    assert [p["id"] for p in presets] == ["lte_1800", "nr_3500", "c6g_8000", "c6g_15000", "nr_28000"]
    assert all(p["preset"] == p["id"] and not p["custom"] and p["gas"] == ca.TABULATED for p in presets)
    assert [(p["frequency_hz"], p["bandwidth_hz"]) for p in presets] == [
        (1.8e9, 20e6), (3.5e9, 100e6), (8e9, 400e6), (15e9, 400e6), (28e9, 400e6)]


def test_the_material_range_is_read_from_the_installed_engine_for_the_scenes_materials(scene):
    assert ca.material_ranges_hz(scene) == [(1e9, 100e9), (110e9, 330e9)]    # ITU-R P.2040 concrete


def test_a_custom_carrier_keeps_its_preset_for_radio_values_and_rate_mapping(scene):
    nr = ca.preset(ROOT, "nr_3500")
    c = ca.customize(nr, frequency_hz=8e9, bandwidth_hz=100e6, scene_dir=scene)
    assert c["custom"] and c["preset"] == "nr_3500" and c["id"] == "nr_3500.f8000b100"
    assert c["gas"] == ca.TABULATED                             # 8 GHz is a tabulated carrier
    assert ca.radio_scenario(ROOT, c) == {**nr, "bandwidth_hz": 100e6}


def test_equal_values_give_back_the_preset(scene):
    nr = ca.preset(ROOT, "nr_3500")
    assert ca.customize(nr, frequency_hz=3.5e9, bandwidth_hz=100e6, scene_dir=scene) == nr


def test_an_untabulated_frequency_below_30_ghz_runs_without_gas_loss_and_says_so(scene):
    c = ca.customize(ca.preset(ROOT, "nr_3500"), frequency_hz=6e9, bandwidth_hz=100e6, scene_dir=scene)
    assert c["gas"] == ca.OMITTED and ca.gas_db_per_km(c) == 0.0
    assert ca.gas_db_per_km(ca.preset(ROOT, "nr_28000")) == pytest.approx(0.1018)


@pytest.mark.parametrize(("frequency", "bandwidth", "code"), [
    (0.7e9, 10e6, "frequency_range"),          # below the concrete model's 1 GHz
    (105e9, 400e6, "frequency_range"),         # between concrete's two ranges
    (400e9, 400e6, "frequency_range"),         # above 330 GHz
    (120e9, 400e6, "gas_unavailable"),         # concrete is defined, gas loss is not
    (60e9, 400e6, "gas_unavailable"),          # oxygen absorption: not tabulated, not negligible
    (3.5e9, 0.0, "bandwidth_range"),
    (1.8e9, 500e6, "bandwidth_range"),         # more than a quarter of the carrier
])
def test_unsupported_carriers_are_refused_with_a_reason(scene, frequency, bandwidth, code):
    with pytest.raises(ca.CarrierError) as err:
        ca.customize(ca.preset(ROOT, "nr_3500"), frequency_hz=frequency, bandwidth_hz=bandwidth, scene_dir=scene)
    assert err.value.code == code


def test_equal_bandwidth_sets_every_carrier_to_one_bandwidth(scene):
    same = ca.equal_bandwidth(ca.presets(ROOT), 100e6, scene)
    assert {c["bandwidth_hz"] for c in same} == {100e6}
    assert [c["frequency_hz"] for c in same] == [p["frequency_hz"] for p in ca.presets(ROOT)]
    assert [c["custom"] for c in same] == [True, False, True, True, True]


def test_deviations_name_the_custom_values_and_the_omitted_gas_loss(scene):
    c = ca.customize(ca.preset(ROOT, "nr_3500"), frequency_hz=6e9, bandwidth_hz=100e6, scene_dir=scene)
    text = " ".join(ca.deviations([ca.preset(ROOT, "lte_1800"), c]))
    assert "nr_3500" in text and "6 GHz" in text and "100 MHz" in text and "gas" in text
    assert ca.deviations(ca.presets(ROOT)) == []
