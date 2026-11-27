"""Both languages through the real application (headless AppTest; saved runs only, no ray tracing).

Opt-in with the other app tests (`uv run pytest -m app`).
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.app
PAGES = ["workspace", "comparison", "planning", "history", "reports", "coverage", "research_status", "study_area",
         "radio", "validation", "roadmap"]
ARABIC = re.compile(r"[؀-ۿ]")
KEY_MARKER = re.compile(r"\b(?:common|nav|dashboard|cls|limitations|readiness|study_area|config|simulation|coverage|"
                        r"comparison|planning|reports|radio|validation|roadmap|report|workspace|history|research_status)"
                        r"\.[a-z0-9_]+\.[a-z0-9_.]+\b")


def visible_text(at) -> str:
    texts = [str(e.value) for kind in ("markdown", "caption", "info", "warning", "error", "success", "title",
                                       "subheader") for e in getattr(at, kind)]
    labels = [str(getattr(w, "label", "")) for kind in ("button", "selectbox", "radio", "number_input", "text_input",
                                                        "multiselect", "toggle", "slider") for w in getattr(at, kind)]
    return " ".join(texts + labels)


@pytest.fixture(scope="module", params=["ar", "en"])
def app(request):
    if not (ROOT / "data" / "scenes" / "tahrir_bab_al_sharqi_study").exists():
        pytest.skip("study dataset not built (setup.ps1)")
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240)
    at.session_state["lang"] = request.param
    at.run()
    return request.param, at


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_in_the_language_without_untranslated_keys(app, page):
    lang, at = app
    at = at.switch_page(f"views/{page}.py").run()
    assert not at.exception, [e.message for e in at.exception]
    heading = str(at.title[0].value) if at.title else " ".join(b.label for b in at.button[:3])
    assert bool(ARABIC.search(heading)) == (lang == "ar"), heading
    assert KEY_MARKER.findall(visible_text(at)) == []
    if lang == "en" and page != "history":          # the history shows experiment names exactly as typed
        assert not ARABIC.search(visible_text(at)), "no Arabic on English pages"
    assert at.session_state["lang"] == lang                     # the choice survives page navigation


def test_right_to_left_styles_only_in_arabic(app):
    lang, at = app
    css = " ".join(str(m.value) for m in at.markdown if "<style>" in str(m.value))
    assert ("direction: rtl" in css) == (lang == "ar")
    assert "Noto Sans Arabic" in css                            # Arabic-capable font stack, no remote fonts
    assert "stPlotlyChart" in css or lang == "en"               # charts and tables are kept left-to-right


def test_language_switch_changes_the_interface_and_persists():
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240).run()
    assert "حفظ" in [b.label for b in at.button], "Arabic is the default language"
    switch = at.segmented_control(key="lang_switch")
    switch.set_value("en").run()
    assert at.session_state["lang"] == "en" and "Save" in [b.label for b in at.button]
    assert at.query_params.get("lang") in ("en", ["en"])        # the URL keeps the choice across reloads
    at.switch_page("views/coverage.py").run()
    assert str(at.title[0].value) == "Coverage Analysis"


def test_the_chosen_language_survives_an_application_restart(isolated_preferences):
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240).run()
    at.segmented_control(key="lang_switch").set_value("en").run()
    assert isolated_preferences.exists()
    restarted = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240).run()   # new session, no ?lang=
    assert restarted.session_state["lang"] == "en" and "Save" in [b.label for b in restarted.button]
    restarted.segmented_control(key="lang_switch").set_value("ar").run()
    again = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240).run()
    assert again.session_state["lang"] == "ar"


def test_language_from_the_query_parameter():
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=240)
    at.query_params["lang"] = "en"
    at.run()
    assert at.session_state["lang"] == "en" and "Save" in [b.label for b in at.button]


def test_the_workspace_offers_each_action_once(app):
    lang, at = app
    at = at.switch_page("views/workspace.py").run()
    from bns import i18n

    buttons = [b.label for b in at.button]
    assert i18n.translate(lang, "workspace.experiment.save") in buttons
    assert len(buttons) == len(set(buttons)), buttons                   # no duplicated actions
    text = visible_text(at)
    for removed in ("Phase", "commit", "approval record", "Prototype"):    # no development history or prototype labels
        assert removed not in text
