"""Research status: the study district's dataset, the configuration and the validation evidence, and what
still limits research use. Formerly the dashboard's status section; the simulation itself is in the
Simulation Workspace."""

import streamlit as st
import ui
from ui import t

from bns.analysis import readiness
from bns.app import dashboard

ui.page_header("research_status.title", "research_status.caption")
tr = ui.tr()


@st.cache_data(show_spinner=False, ttl=60)
def indicators():
    return readiness.indicators(ui.ROOT)


area, ds = dashboard.study_summary(ui.ROOT)
name = t(f"study_area.names.{area['name']}") if tr.has(f"study_area.names.{area['name']}") else area["name"]
size = area.get("receiver_area_m") or [0, 0]
st.markdown(t("research_status.area", name=name, size=ui.ltr(f"{float(size[0]) / 1000:g} × {float(size[1]) / 1000:g} km"),
              variant=ui.variant_name(area["variant"])), unsafe_allow_html=True)

ind = {i.id: i for i in indicators()}
s1, s2 = st.columns(2)
with s1:
    st.markdown(f"**{t('dashboard.status.dataset')}**")
    if not ds.get("available"):
        st.markdown(t("dashboard.status.dataset_missing"))
    elif ds.get("synthetic_percent") is not None:
        st.markdown(t("dashboard.status.dataset_synthetic", pct=ds["synthetic_percent"], documented=ds["documented"]))
    else:
        st.markdown(t("dashboard.status.dataset_plain", documented=ds["documented"], buildings=ds["buildings"]))
    st.markdown(f"**{t('dashboard.status.configuration')}**")
    st.markdown(t("dashboard.status.configuration_baseline" if ind["configuration"].state == readiness.BASELINE
                  else "dashboard.status.configuration_custom"))
with s2:
    st.markdown(f"**{t('dashboard.status.validation')}**")
    done = ind["convergence"].state == readiness.COMPLETED and ind["matlab"].state == readiness.COMPLETED
    st.markdown(t("dashboard.status.validation_done" if done else "dashboard.status.validation_text"))
    st.markdown(f"**{t('research_status.classification')}**")
    st.markdown(t("research_status.classification_text"))

st.subheader(t("research_status.indicators"))
dc = "dashboard.status.detail_columns."
st.dataframe([{t(dc + "item"): t(f"readiness.title.{i.id}"), t(dc + "state"): t(f"readiness.state.{i.state}"),
               t(dc + "details"): i.detail} for i in indicators()], hide_index=True, width="stretch")

st.subheader(t("research_status.limitations"))
for key in ("heights", "validated", "shannon", "greedy", "validation_scope", "candidate_6g", "runs_compared"):
    st.markdown(f"- {t('limitations.general.' + key)}")
