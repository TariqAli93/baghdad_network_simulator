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
    at = AppTest.from_file(str(ROOT / "app" / "workspace.py"), default_timeout=240)
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


def test_a_radio_change_recomputes_at_once_and_a_propagation_change_makes_the_results_stale():
    at = workspace()
    at.session_state["w_r_load"] = 0.5                  # network load: radio only
    at.run()
    assert "current" in state(at)
    assert "Sensitivity Analysis" in next(m.value for m in at.markdown if 'class="ws-class' in m.value)
    at.session_state["w_rx"] = 2.0                      # receiver height: part of every job key
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert "ws-state stale" in state(at)
    assert any(b.label.startswith("Trace this band") for b in at.button)
