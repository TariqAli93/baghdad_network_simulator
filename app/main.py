"""Baghdad Network Simulator — research application (Arabic / English).

    uv run streamlit run app/main.py            # Arabic by default; ?lang=en for English

Pages read saved runs and the configuration; the Run Simulation page starts the same
experiment script as the command line, in its own process.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui  # noqa: E402

st.set_page_config(page_title=ui.t("common.app_name"), page_icon=":material/cell_tower:", layout="wide")
ui.inject_css()

VIEWS = Path(__file__).resolve().parent / "views"
t = ui.t
# the workflow first; scientific background pages grouped under "Research Details"
pages = {
    "": [
        st.Page(VIEWS / "overview.py", title=t("nav.dashboard"), icon=":material/dashboard:", default=True),
        st.Page(VIEWS / "study_area.py", title=t("nav.study_area"), icon=":material/map:"),
        st.Page(VIEWS / "simulation.py", title=t("nav.run_simulation"), icon=":material/play_circle:"),
        st.Page(VIEWS / "coverage.py", title=t("nav.coverage"), icon=":material/layers:"),
        st.Page(VIEWS / "comparison.py", title=t("nav.comparison"), icon=":material/compare_arrows:"),
        st.Page(VIEWS / "planning.py", title=t("nav.planning"), icon=":material/add_location_alt:"),
        st.Page(VIEWS / "reports.py", title=t("nav.reports"), icon=":material/description:"),
    ],
    t("nav.advanced"): [
        st.Page(VIEWS / "radio.py", title=t("nav.radio"), icon=":material/settings_input_antenna:"),
        st.Page(VIEWS / "validation.py", title=t("nav.validation"), icon=":material/verified:"),
        st.Page(VIEWS / "roadmap.py", title=t("nav.roadmap"), icon=":material/route:"),
    ],
}
nav = st.navigation(pages)
with st.sidebar:
    st.markdown(f"**{t('common.app_name')}**")
    st.markdown(f'<div class="sidebar-note">{t("nav.sidebar_note")}</div>', unsafe_allow_html=True)
_, switch = st.columns([5, 1])
with switch:
    ui.language_switch()
nav.run()
