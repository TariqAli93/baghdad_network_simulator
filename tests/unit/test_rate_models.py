"""Per-band practical rate mappings (decision B3), checked against the 3GPP tables."""

from pathlib import Path

import numpy as np
import pytest
import yaml

from bns.analysis import link_budget as lb
from bns.analysis import rate_models as rm

ROOT = Path(__file__).resolve().parents[2]


def _db(values):
    return 10 ** (np.asarray(values, dtype=float) / 10)


def test_lte_mapping_reproduces_tr36942_table_a2_downlink_rows():
    # TR 36.942 V19.0.0 Table A.2 (DL, bit/s/Hz): alpha 0.6, SNIR_MIN -10 dB, Thr_MAX 4.4
    table = {-15: 0.0, -11: 0.0, -10: 0.08, -5: 0.24, 0: 0.60, 5: 1.23, 10: 2.08, 15: 3.02,
             20: 3.99, 21: 4.19, 22: 4.39, 23: 4.40, 25: 4.40}
    sinr_db = np.array(list(table))
    rate = lb.truncated_shannon_bps(1.0, _db(sinr_db), alpha=0.6, sinr_min_db=-10.0, thr_max_bps_hz=4.4)
    assert np.round(rate, 2) == pytest.approx(np.array(list(table.values())))


def test_lte_cap_is_continuous_and_reached_near_22_db():
    s_max_db = 10 * np.log10(2 ** (4.4 / 0.6) - 1)               # S^-1(Thr_MAX / alpha)
    assert s_max_db == pytest.approx(22.05, abs=0.01)
    below, above = lb.truncated_shannon_bps(1.0, _db([s_max_db - 1e-6, s_max_db + 1e-6]), alpha=0.6,
                                            sinr_min_db=-10.0, thr_max_bps_hz=4.4)
    assert below == pytest.approx(4.4, abs=1e-6) and above == pytest.approx(4.4)


def test_exactly_one_cap_must_be_given():
    with pytest.raises(ValueError):
        lb.truncated_shannon_bps(1.0, 1.0, alpha=0.6, sinr_min_db=-10.0)
    with pytest.raises(ValueError):
        lb.truncated_shannon_bps(1.0, 1.0, alpha=0.6, sinr_min_db=-10.0, sinr_max_db=30.0, thr_max_bps_hz=4.4)


def test_every_scenario_has_a_mapping_of_the_approved_technology():
    models = rm.load(ROOT / "configs" / "radio_system.yaml")
    scenarios = yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))["scenarios"]
    assert {s["id"] for s in scenarios} == set(models)
    assert models["lte_1800"].key == "lte" and models["lte_1800"].thr_max_bps_hz == 4.4
    assert models["lte_1800"].sinr_max_db is None
    for sid in ("nr_3500", "nr_28000"):
        assert models[sid].key == "nr" and models[sid].sinr_max_db == 30.0 and models[sid].caveat is None
    for sid in ("c6g_8000", "c6g_15000"):
        m = models[sid]
        assert m.key == "nr_based_candidate_6g"
        assert (m.alpha, m.sinr_min_db, m.sinr_max_db) == (0.6, -10.0, 30.0)   # NR constants, not copied
        assert m.caveat and "approximation" in m.label.lower()


def test_rate_model_rate_matches_the_link_budget_function():
    models = rm.load(ROOT / "configs" / "radio_system.yaml")
    sinr = _db([-20, -10, 10, 25, 35])
    lte = models["lte_1800"].rate_bps(20e6, sinr)
    assert lte == pytest.approx(lb.truncated_shannon_bps(20e6, sinr, alpha=0.6, sinr_min_db=-10, thr_max_bps_hz=4.4))
    nr = models["nr_3500"].rate_bps(100e6, sinr)
    assert nr == pytest.approx(lb.truncated_shannon_bps(100e6, sinr, alpha=0.6, sinr_min_db=-10, sinr_max_db=30))
    assert np.all(lte <= lb.shannon_capacity_bps(20e6, sinr))


def test_unknown_or_missing_mapping_is_refused(tmp_path):
    base = yaml.safe_load((ROOT / "configs" / "radio_system.yaml").read_text(encoding="utf-8"))
    base["scenario_rate_mapping"]["lte_1800"] = "nonexistent"
    path = tmp_path / "radio_system.yaml"
    path.write_text(yaml.safe_dump(base), encoding="utf-8")
    with pytest.raises(ValueError):
        rm.load(path)


def test_no_mapping_configured_gives_none(tmp_path):
    path = tmp_path / "radio_system.yaml"
    path.write_text("parameters: {}\n", encoding="utf-8")
    assert rm.load(path) == {}
