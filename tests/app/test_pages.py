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
PAGES = ["workspace", "comparison", "planning", "history", "reports", "coverage", "research_status", "study_area",
         "radio", "validation", "roadmap"]


@pytest.fixture(scope="module")
def app():
    if not (ROOT / "data" / "scenes" / "tahrir_bab_al_sharqi_v2" / "osm" / "scene.xml").exists():
        pytest.skip("development dataset not built (setup.ps1)")
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
    at.session_state["lang"] = "en"                 # labels below are the English interface (Arabic: test_i18n_pages)
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception_and_shows_its_title(app, page):
    at = app.switch_page(f"views/{page}.py").run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title or page == "workspace", "every page but the workspace starts with a title"


def test_the_workspace_is_the_landing_page_with_the_simulation_actions(app):
    at = app.switch_page("views/workspace.py").run()     # the default page
    assert not at.exception, [e.message for e in at.exception]
    labels = [b.label for b in at.button]
    assert "Save" in labels and any(label.startswith("Run simulation") for label in labels)
    assert next(s for s in at.selectbox if s.label == "Area").value == "tahrir_bab_al_sharqi_study"
    assert next(s for s in at.selectbox if s.label == "Dataset").value == "synthetic_urban-seed42+fp_3d_globfp"
    text = " ".join(str(m.value) for m in at.markdown)
    assert "Validation" in text and "Scientific limitations" in text      # the classification popover's contents


def test_a_changed_radio_value_makes_a_custom_experiment_and_reset_restores_the_baseline(app):
    at = app.switch_page("views/workspace.py").run()
    nf = next(n for n in at.number_input if n.label.startswith("Noise figure"))
    assert nf.value == 9.0                                       # the research-baseline value
    nf.set_value(7.0).run()
    assert any("Custom Experiment" in str(m.value) for m in at.markdown if 'class="ws-class' in str(m.value))
    next(b for b in at.button if b.label == "Reset to the research baseline").click().run()
    assert next(n for n in at.number_input if n.label.startswith("Noise figure")).value == 9.0
    assert not any("Custom Experiment" in str(m.value) for m in at.markdown if 'class="ws-class' in str(m.value))


def test_reports_offer_csv_json_zip_and_html_exports(app):
    at = app.switch_page("views/reports.py").run()
    labels = [b.label for b in at.get("download_button")]
    assert "manifest.json" in labels and "summary.json" in labels
    assert any(label.startswith("Whole run folder") for label in labels)
    assert any(label.startswith("Report (HTML") for label in labels)


def test_out_of_range_values_cannot_be_entered(app):
    at = app.switch_page("views/workspace.py").run()
    load = next(s for s in at.slider if s.label.startswith("Network load"))
    assert (load.min, load.max) == (0.0, 1.0)                  # the widget enforces the valid range


@pytest.mark.parametrize("page", PAGES)
def test_no_page_shows_the_old_approval_label(app, page):
    at = app.switch_page(f"views/{page}.py").run()
    texts = [e.value for kind in ("markdown", "caption", "info", "warning", "error", "success", "title")
             for e in getattr(at, kind)]
    joined = " ".join(str(t) for t in texts)
    assert "NOT APPROVED" not in joined and "DEVELOPMENT —" not in joined
