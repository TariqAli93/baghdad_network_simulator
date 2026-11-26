import streamlit as st
import ui
import yaml

from bns.analysis.radio_system import RadioSystem
from bns.core.units import noise_power_dbm

ui.page_header("Radio scenarios", "The five scenarios and the proposed radio system (configs/*.yaml).")

scen = ui.scenarios()
system = RadioSystem.load(ui.ROOT / "configs" / "radio_system.yaml")
nf = system.require("noise_figure_db", mode="development")
temp = system.require("noise_temperature_k", mode="development")
st.dataframe([{"scenario": s["label"], "frequency [GHz]": s["frequency_hz"] / 1e9,
               "bandwidth [MHz]": s["bandwidth_hz"] / 1e6, "status": s["status"],
               "noise floor [dBm]": round(float(noise_power_dbm(s["bandwidth_hz"], nf, temp)), 1),
               "peak EIRP [dBm]": system.peak_eirp_dbm(s["id"], mode="development"),
               "basis": " ".join(s["basis"].split()), "sources": ", ".join(s["sources"])} for s in scen],
             hide_index=True, use_container_width=True)
st.caption("Only frequency and bandwidth differ between scenarios (controlled experiment, docs/methodology.md). "
           "6G bands are candidate research assumptions; 3.5 GHz for Iraq is assumed.")

st.subheader("Radio-system parameters")
raw = yaml.safe_load((ui.ROOT / "configs" / "radio_system.yaml").read_text(encoding="utf-8"))["parameters"]
counts = {}
for v in raw.values():
    counts[v["status"]] = counts.get(v["status"], 0) + 1
c = st.columns(4)
for col, state in zip(c, ("approved", "candidate", "development", "undecided"), strict=True):
    col.metric(state.capitalize(), counts.get(state, 0))
if counts.get("approved", 0) < len(raw):
    ui.development_banner()
    st.caption("Research runs refuse any parameter that is not approved by the supervisor.")
st.dataframe([{"parameter": k, "value": v.get("value"), "unit": v.get("unit", ""), "definition": v.get("definition", ""),
               "status": v["status"], "sources": ", ".join(v.get("sources", []) or []),
               "justification": " ".join(str(v.get("justification", "")).split())} for k, v in raw.items()],
             hide_index=True, use_container_width=True)
