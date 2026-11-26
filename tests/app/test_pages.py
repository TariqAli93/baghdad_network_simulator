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


def test_research_mode_is_refused_with_its_reason(app):
    at = app.switch_page("views/simulation.py").run()
    mode = next(s for s in at.selectbox if s.label == "Mode")
    mode.set_value("research")
    next(b for b in at.button if b.label == "Check sites and workload").click()
    at.run()
    assert any("cannot start" in e.value and "Research mode" in e.value for e in at.error)


def test_reports_offer_csv_json_zip_and_html_exports(app):
    at = app.switch_page("views/reports.py").run()
    labels = [b.label for b in at.get("download_button")]
    assert "manifest.json" in labels and "summary.json" in labels
    assert any(label.startswith("Whole run folder") for label in labels)
    assert any(label.startswith("Report (HTML") for label in labels)
