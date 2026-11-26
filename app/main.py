"""Baghdad Network Simulator — research application.

    uv run streamlit run app/main.py

Pages read saved runs and the configuration; the Simulation page starts the same
experiment script as the command line, in its own process.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui  # noqa: E402

st.set_page_config(page_title="Baghdad Network Simulator", page_icon=":material/cell_tower:", layout="wide")
ui.inject_css()

VIEWS = Path(__file__).resolve().parent / "views"
pages = {
    "Project": [
        st.Page(VIEWS / "overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page(VIEWS / "study_area.py", title="Study area", icon=":material/map:"),
        st.Page(VIEWS / "radio.py", title="Radio scenarios", icon=":material/settings_input_antenna:"),
    ],
    "Simulation": [
        st.Page(VIEWS / "simulation.py", title="Run simulation", icon=":material/play_circle:"),
        st.Page(VIEWS / "coverage.py", title="Coverage analysis", icon=":material/layers:"),
        st.Page(VIEWS / "comparison.py", title="Comparison", icon=":material/compare_arrows:"),
        st.Page(VIEWS / "planning.py", title="Site planning", icon=":material/add_location_alt:"),
    ],
    "Evidence": [
        st.Page(VIEWS / "validation.py", title="Validation", icon=":material/verified:"),
        st.Page(VIEWS / "reports.py", title="Reports and exports", icon=":material/description:"),
        st.Page(VIEWS / "roadmap.py", title="6G roadmap", icon=":material/route:"),
    ],
}
nav = st.navigation(pages)
with st.sidebar:
    st.markdown("**Baghdad Network Simulator**")
    st.markdown('<div class="sidebar-note">4G · 5G · candidate 6G coverage by ray tracing (Sionna RT; CPU, optional GPU).<br>'
                "Research baseline approved by the supervisor; any valid parameter can be changed for a custom "
                "experiment or sensitivity analysis. Every result shows its configuration, dataset and validation "
                "status.</div>",
                unsafe_allow_html=True)
nav.run()
