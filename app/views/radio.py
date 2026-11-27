import streamlit as st
import ui
from ui import t

from bns.analysis.radio_system import RadioSystem
from bns.app import configuration
from bns.core.units import noise_power_dbm

ui.page_header("radio.title", "radio.caption")

scen = ui.scenarios()
system = RadioSystem.load(ui.ROOT / "configs" / "radio_system.yaml")
nf = system.require("noise_figure_db", mode="development")
temp = system.require("noise_temperature_k", mode="development")
C = "radio.columns."
st.dataframe([{t(C + "scenario"): ui.scenario_name(s), t(C + "frequency"): s["frequency_hz"] / 1e9,
               t(C + "bandwidth"): s["bandwidth_hz"] / 1e6, t(C + "status"): ui.scenario_status(s),
               t(C + "noise"): round(float(noise_power_dbm(s["bandwidth_hz"], nf, temp)), 1),
               t(C + "eirp"): system.peak_eirp_dbm(s["id"], mode="development"),
               t(C + "basis"): " ".join(s["basis"].split()), t(C + "sources"): ", ".join(s["sources"])} for s in scen],
             hide_index=True, use_container_width=True)
st.caption(t("radio.scenarios_note"))

st.subheader(t("radio.parameters"))
st.dataframe(ui.localized_rows(configuration.radio_rows(ui.ROOT)), hide_index=True, use_container_width=True)
st.caption(t("radio.parameters_note"))

st.subheader(t("radio.rates"))
st.dataframe(ui.localized_rows(configuration.rate_rows(ui.ROOT, scen), value_columns=("label", "scenario")),
             hide_index=True, use_container_width=True)
st.caption(t("radio.rates_note"))
if ui.lang() != "en":
    st.caption(t("radio.english_fields"))
