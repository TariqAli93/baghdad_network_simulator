"""Baghdad Network Simulator — interactive RF simulation (Arabic / English).

    uv run streamlit run app/main.py            # Arabic by default; ?lang=en for English

Simulation first: the Simulation Workspace is the landing page (configure, place stations, simulate,
visualise, compare). Comparison, automatic site planning, the experiment history and the reports
follow; methodology, assumptions, validation, dataset provenance and the 6G roadmap are under
"Settings and Research Details". Simulations run in their own processes; pages read saved runs.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui  # noqa: E402

st.set_page_config(page_title=ui.t("common.app_name"), page_icon=":material/cell_tower:", layout="wide",
                   initial_sidebar_state="collapsed")
ui.inject_css()

VIEWS = Path(__file__).resolve().parent / "views"
t = ui.t
pages = {
    "": [
        st.Page(VIEWS / "workspace.py", title=t("nav.workspace"), icon=":material/cell_tower:", default=True),
        st.Page(VIEWS / "comparison.py", title=t("nav.scenario_comparison"), icon=":material/compare_arrows:"),
        st.Page(VIEWS / "planning.py", title=t("nav.site_planning"), icon=":material/add_location_alt:"),
        st.Page(VIEWS / "history.py", title=t("nav.history"), icon=":material/history:"),
        st.Page(VIEWS / "reports.py", title=t("nav.reports"), icon=":material/description:"),
        # opened from the Experiment History (a saved run's maps and statistics); not a menu entry
        st.Page(VIEWS / "coverage.py", title=t("nav.run_viewer"), icon=":material/layers:", visibility="hidden"),
    ],
    t("nav.research"): [
        st.Page(VIEWS / "research_status.py", title=t("nav.research_status"), icon=":material/fact_check:"),
        st.Page(VIEWS / "study_area.py", title=t("nav.study_area"), icon=":material/map:"),
        st.Page(VIEWS / "radio.py", title=t("nav.radio"), icon=":material/settings_input_antenna:"),
        st.Page(VIEWS / "validation.py", title=t("nav.validation"), icon=":material/verified:"),
        st.Page(VIEWS / "roadmap.py", title=t("nav.roadmap"), icon=":material/route:"),
    ],
}
nav = st.navigation(pages, position="top")
_, switch = st.columns([6, 1])
with switch:
    ui.language_switch()
nav.run()
