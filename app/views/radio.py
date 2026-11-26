import streamlit as st
import ui

from bns.analysis.radio_system import RadioSystem
from bns.app import configuration
from bns.core.units import noise_power_dbm

ui.page_header("Radio scenarios", "The five scenarios, the approved radio system and the rate models "
               "(read from configs/*.yaml; read-only here).")

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
rows = configuration.radio_rows(ui.ROOT)
counts = {}
for r in rows:
    key = "approved" if r["approval"] == "approved" else ("void" if r["approval"].startswith("approval void") else r["approval"])
    counts[key] = counts.get(key, 0) + 1
c = st.columns(4)
for col, state in zip(c, ("approved", "void", "candidate", "development"), strict=True):
    col.metric({"void": "Approval void (changed)"}.get(state, state.capitalize()), counts.get(state, 0))
if counts.get("approved", 0) < len(rows):
    ui.development_banner()
    st.caption("Research runs refuse any parameter that is not approved, or that changed since its approval.")
st.dataframe(rows, hide_index=True, use_container_width=True)
st.caption("Approved values are read-only: they change only through the approval workflow (edit the configuration "
           "file, obtain the supervisor's reconfirmation, then scripts/approval_lock.py --record). The traced TR 38.901 "
           "pattern already contains the 8 dBi peak gain, so the added antenna gain is 0 (no double counting).")

st.subheader("Data-rate models (decision B3)")
st.dataframe(configuration.rate_rows(ui.ROOT, scen), hide_index=True, use_container_width=True)
st.caption("The Shannon bound is reported for every band; the practical mapping is reported beside it, never "
           "instead. Candidate 6G uses the NR values as a research approximation: no 6G link-level mapping exists. "
           "Verification against TR 36.942 and TR 38.921: docs/rate-mapping-verification.md.")
