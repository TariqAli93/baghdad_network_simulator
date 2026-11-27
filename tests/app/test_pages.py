"""Every application page runs headless without an exception, on the saved development data.

Opt-in (`uv run pytest -m app`): needs the built development dataset and saved runs, which a
fresh clone does not have until setup.ps1 has run. Uses Streamlit's AppTest: no browser, no
ray tracing.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.app
PAGES = ["overview", "study_area", "radio", "simulation", "coverage", "comparison", "planning", "validation",
         "reports", "roadmap"]


@pytest.fixture(scope="module")
def app():
    if not (ROOT / "data" / "scenes" / "tahrir_bab_al_sharqi_v2" / "osm" / "scene.xml").exists():
        pytest.skip("development dataset not built (setup.ps1)")
    return AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception_and_shows_its_title(app, page):
    at = app.switch_page(f"views/{page}.py").run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title, "every page starts with a title"


@pytest.mark.parametrize("area", ["tahrir_bab_al_sharqi_study", "tahrir_bab_al_sharqi_v2"])
def test_both_datasets_are_ready_to_run_with_their_limitations_shown(app, area):
    if not (ROOT / "data" / "scenes" / area).exists():
        pytest.skip(f"no scene of {area} on this computer")
    at = app.switch_page("views/simulation.py").run()
    assert not any(s.label == "Run type" for s in at.selectbox)          # no mode to choose
    assert next(s for s in at.selectbox if s.label == "Area").value == "tahrir_bab_al_sharqi_study"   # default
    next(s for s in at.selectbox if s.label == "Area").set_value(area)
    at.run()
    expected = {"tahrir_bab_al_sharqi_study": "osm+fp_3d_globfp", "tahrir_bab_al_sharqi_v2": "osm"}[area]
    assert next(s for s in at.selectbox if s.label == "Dataset variant").value == expected  # configured primary
    next(b for b in at.button if b.label == "Check sites and workload").click()
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert not any("cannot start" in e.value for e in at.error)
    assert any("Execution:** Ready" in m.value for m in at.markdown)
    assert any(b.label == "Start run" for b in at.button)
    warnings = " ".join(w.value for w in at.warning)
    assert "Scientific limitations" in warnings and "validation pending" in warnings
    if area.endswith("_v2"):
        assert "not the study district" in warnings


def test_reports_offer_csv_json_zip_and_html_exports(app):
    at = app.switch_page("views/reports.py").run()
    labels = [b.label for b in at.get("download_button")]
    assert "manifest.json" in labels and "summary.json" in labels
    assert any(label.startswith("Whole run folder") for label in labels)
    assert any(label.startswith("Report (HTML") for label in labels)


def test_a_changed_parameter_makes_a_custom_experiment_and_reset_restores_the_baseline(app):
    at = app.switch_page("views/simulation.py").run()
    assert any("Research Baseline" in s.value for s in at.success)
    power = next(n for n in at.number_input if n.label.startswith("Transmit power"))
    assert power.value == 46.0                                    # the research-baseline value
    power.set_value(43.0)
    next(b for b in at.button if b.label == "Check sites and workload").click()
    at.run()
    assert any("Custom Experiment" in i.value and "tx_power_dbm 43" in i.value for i in at.info)
    assert not at.exception, [e.message for e in at.exception]
    next(b for b in at.button if b.label == "Reset to research baseline").click()
    at.run()
    assert next(n for n in at.number_input if n.label.startswith("Transmit power")).value == 46.0
    assert any("Research Baseline" in s.value for s in at.success)


def test_out_of_range_values_cannot_be_entered(app):
    at = app.switch_page("views/simulation.py").run()
    load = next(n for n in at.number_input if n.label.startswith("Network load"))
    assert (load.proto.min, load.proto.max) == (0.0, 1.0)          # the widget enforces the valid range


@pytest.mark.parametrize("page", PAGES)
def test_no_page_shows_the_old_approval_label(app, page):
    at = app.switch_page(f"views/{page}.py").run()
    texts = [e.value for kind in ("markdown", "caption", "info", "warning", "error", "success", "title")
             for e in getattr(at, kind)]
    joined = " ".join(str(t) for t in texts)
    assert "NOT APPROVED" not in joined and "DEVELOPMENT —" not in joined
