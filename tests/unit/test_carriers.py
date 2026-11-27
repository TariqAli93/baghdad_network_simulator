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


def test_an_untabulated_frequency_gets_its_p676_gas_loss_recorded_with_the_model(scene):
    from bns.propagation import atmosphere as atm

    c = ca.customize(ca.preset(ROOT, "nr_3500"), frequency_hz=6e9, bandwidth_hz=100e6, scene_dir=scene)
    assert c["gas"] == ca.P676
    assert ca.gas_db_per_km(c) == pytest.approx(atm.gas_specific_attenuation_p676_db_per_km(6e9), abs=1e-6)
    assert c["gas_model"]["recommendation"].startswith("ITU-R P.676-") and "ITU-Rpy" in c["gas_model"]["implementation"]
    assert ca.gas_db_per_km(ca.preset(ROOT, "nr_28000")) == pytest.approx(0.1018)      # presets: the table


def test_a_run_that_recorded_omitted_gas_loss_is_read_as_recorded():
    assert ca.gas_db_per_km({"gas": ca.OMITTED, "frequency_hz": 6e9}) == 0.0


def test_oxygen_absorption_near_60_ghz_is_now_computed_not_refused(scene):
    c = ca.customize(ca.preset(ROOT, "nr_28000"), frequency_hz=60e9, bandwidth_hz=400e6, scene_dir=scene)
    assert 10.0 < ca.gas_db_per_km(c) < 20.0          # about 15 dB/km in the reference atmosphere


@pytest.mark.parametrize(("frequency", "bandwidth", "code"), [
    (0.7e9, 10e6, "frequency_range"),          # below the concrete model's and P.676's 1 GHz
    (105e9, 400e6, "frequency_range"),         # between concrete's two ranges
    (120e9, 400e6, "frequency_range"),         # concrete and P.676 are defined; the TR 38.901 element is not
    (400e9, 400e6, "frequency_range"),         # above 330 GHz
    (3.5e9, 0.0, "bandwidth_range"),
    (1.8e9, 500e6, "bandwidth_range"),         # more than a quarter of the carrier
])
def test_unsupported_carriers_are_refused_with_a_reason(scene, frequency, bandwidth, code):
    with pytest.raises(ca.CarrierError) as err:
        ca.customize(ca.preset(ROOT, "nr_3500"), frequency_hz=frequency, bandwidth_hz=bandwidth, scene_dir=scene)
    assert err.value.code == code


def test_the_supported_range_is_the_intersection_of_materials_gas_model_and_antenna(scene):
    assert ca.supported_ranges_hz(scene, ("tr38901",)) == [(1e9, 100e9)]
    assert ca.supported_ranges_hz(scene, ("iso",)) == [(1e9, 100e9), (110e9, 330e9)]
    c = ca.customize(ca.preset(ROOT, "nr_28000"), frequency_hz=120e9, bandwidth_hz=400e6, scene_dir=scene,
                     patterns=("iso",))
    assert c["gas"] == ca.P676


def test_equal_bandwidth_sets_every_carrier_to_one_bandwidth(scene):
    same = ca.equal_bandwidth(ca.presets(ROOT), 100e6, scene)
    assert {c["bandwidth_hz"] for c in same} == {100e6}
    assert [c["frequency_hz"] for c in same] == [p["frequency_hz"] for p in ca.presets(ROOT)]
    assert [c["custom"] for c in same] == [True, False, True, True, True]


def test_deviations_name_the_custom_values_and_the_gas_model(scene):
    c = ca.customize(ca.preset(ROOT, "nr_3500"), frequency_hz=6e9, bandwidth_hz=100e6, scene_dir=scene)
    text = " ".join(ca.deviations([ca.preset(ROOT, "lte_1800"), c]))
    assert "nr_3500" in text and "6 GHz" in text and "100 MHz" in text and "P.676" in text and "ITU-Rpy" in text
    assert ca.deviations(ca.presets(ROOT)) == []
