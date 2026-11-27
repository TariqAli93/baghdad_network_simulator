"""The simulation workspace prototype runs headless and shows results that belong to its stations.

Opt-in (`uv run pytest -m app`): needs the study district's Synthetic Urban Model dataset, the saved
research-baseline demonstration run and its traces in the path-gain cache. Map interactions (place,
move, select) go through the map component, which AppTest cannot drive; they were checked in a
browser (docs/simulation-workspace.md).
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.app
DEMO = "multi_site-tahrir_bab_al_sharqi_study-synthetic_urban-seed42+fp_3d_globfp-standard-1sites-20261127T121824Z"


def workspace(lang="en"):
    if not (ROOT / "outputs" / "runs" / "development" / DEMO / "network.npz").exists():
        pytest.skip("demonstration run not on this computer")
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240)     # the landing page
    at.session_state["lang"] = lang
    return at.run()


def state(at) -> str:
    return next(m.value for m in at.markdown if 'class="ws-state' in m.value)


def metric(at, label: str) -> str:
    table = next(m.value for m in at.markdown if 'class="ws-m' in m.value)
    row = re.search(re.escape(label) + r'</td><td class="v"><span[^>]*>([^<]+)<', table)
    return row.group(1)


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_the_workspace_opens_on_the_demonstration_run_with_current_results(lang):
    at = workspace(lang)
    assert not at.exception, [e.message for e in at.exception]
    assert [s.station_id for s in at.session_state["w_stations"]] == ["S1"]
    assert "current" in state(at)


def test_shown_values_are_the_saved_runs_values():
    import json

    at = workspace()
    summary = json.loads((ROOT / "outputs" / "runs" / "development" / DEMO / "summary.json").read_text(encoding="utf-8"))
    saved = summary["results"]["nr_3500"]["network"]
    assert metric(at, "Median SINR") == f"{saved['sinr_db_median']:.1f} dB"
    assert metric(at, "Coverage") == f"{saved['coverage_fraction']:.1%}"


def demonstration_traces_cached() -> bool:
    """Whether this computer's path-gain cache holds the demonstration run's traces. A fresh installation
    has none: it shows the saved results, and any change re-traces (no instant radio recomputation)."""
    import json

    from bns.simulation.cache import PathGainCache

    runs = sorted(ROOT.glob("outputs/runs/development/*-standard-1sites-ws-20261127T162816Z/manifest.json"))
    if not runs:
        return False
    keys = [j["key"] for j in json.loads(runs[0].read_text(encoding="utf-8"))["jobs"]]
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    return bool(keys) and all(cache.has(k) for k in keys)


def test_a_radio_change_recomputes_at_once_and_a_propagation_change_makes_the_results_stale():
    if not demonstration_traces_cached():
        pytest.skip("needs the demonstration run's traces in the path-gain cache (a fresh installation has none)")
    at = workspace()
    at.session_state["w_r_load"] = 0.5                  # network load: radio only
    at.run()
    assert "current" in state(at)
    assert "Sensitivity Analysis" in next(m.value for m in at.markdown if 'class="ws-class' in m.value)
    at.session_state["w_rx"] = 2.0                      # receiver height: part of every job key
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert "ws-state stale" in state(at)
    assert "Run simulation (15 traces)" in [b.label for b in at.button]     # 1 station x 3 sectors x 5 carriers


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_a_station_with_its_own_carriers_is_shown_per_carrier(lang):
    """S1 transmitting only on 4G: the 3.5 GHz band says nobody transmits on it, the station's carrier table
    and the 'carriers' deviation are shown, and the experiment becomes a custom experiment."""
    from dataclasses import replace

    from bns.app import workspace as ws

    at = workspace(lang)
    s1 = at.session_state["w_stations"][0]
    at.session_state["w_stations"] = [replace(s1, carriers=(ws.StationCarrier.of(s1, "lte_1800"),))]
    at.session_state["w_sel"] = {"kind": "station", "id": s1.station_id}
    at.session_state["w_band"] = "nr_3500"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert "empty" in state(at)
    texts = " ".join(str(m.value) for m in at.markdown)
    marker = "Carriers of this station" if lang == "en" else "حوامل هذه المحطة"
    assert marker in texts
    cls_line = next(m.value for m in at.markdown if 'class="ws-class' in m.value)
    assert ("Custom Experiment" if lang == "en" else "تجربة مخصصة") in cls_line
    assert any(b.label.startswith("Run simulation" if lang == "en" else "تشغيل المحاكاة") for b in at.button)
