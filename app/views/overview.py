import json

import streamlit as st
import ui
import yaml

from bns.analysis import readiness
from bns.app import configuration

ui.page_header("Coverage and data rate of 4G, 5G and candidate 6G in Baghdad",
               "Ray-tracing study over a ~1 km² district and a 6G roadmap for Iraq (graduation project).")
ui.development_banner()

scen = ui.scenarios()
cols = st.columns(len(scen))
for col, sc in zip(cols, scen, strict=True):
    with col:
        st.markdown(f'<div style="border-top:4px solid {ui.colour(sc["id"])};padding-top:.3rem">'
                    f'<b>{sc["label"]}</b><br><span style="font-size:1.5rem">{sc["frequency_hz"] / 1e9:g} GHz</span>'
                    f'<br>{sc["bandwidth_hz"] / 1e6:g} MHz · {sc["status"]}</div>', unsafe_allow_html=True)

st.subheader("Research readiness")
st.caption("Computed from the configuration files and saved evidence (bns.analysis.readiness). Research runs stay "
           "locked until the five pre-experiment gates pass; nothing is marked met without its evidence.")
gates = readiness.gates(ui.ROOT)
MARK = {"met": "✅ met", "reported": "🟡 reported", "not met": "⛔ not met", "not executed": "⏸ not executed",
        "executed, awaiting review": "🟡 executed, awaiting review"}
st.dataframe([{"gate": g.title, "state": MARK.get(g.state, g.state), "needed before": g.needed_before,
               "evidence / what is missing": g.detail} for g in gates], hide_index=True, use_container_width=True)
locked = [g for g in gates if g.id in readiness.PRE_EXPERIMENT and g.state not in readiness.PASSING]
if locked:
    st.error(f"Research mode is locked: {len(locked)} of {len(readiness.PRE_EXPERIMENT)} pre-experiment conditions "
             "are not met (" + ", ".join(g.title for g in locked) + ").")
obs = next(g for g in gates if g.id == "observations").data
for grp in obs.get("groups") or []:
    if grp["required"]:
        st.progress(grp["observed"] / grp["required"],
                    text=f"{', '.join(grp['priorities'])} — {' or '.join(grp['accepted']).replace('_', ' ')}: "
                         f"{grp['observed']} of {grp['required']} buildings ({obs.get('stage') or 'current'} stage)")

with st.expander("Supervisor decisions and open conditions (configs/approvals.yaml)"):
    st.caption(configuration.approval_source(ui.ROOT) + " An approved value that changes loses its approval "
               "until reconfirmed (configs/approval_lock.yaml).")
    st.dataframe(configuration.decisions(ui.ROOT), hide_index=True, use_container_width=True)
    st.markdown("**Not specified by the supervisor** (left empty; the step that needs them refuses):")
    for u in configuration.unspecified(ui.ROOT):
        st.markdown(f"- {u['item']} — needed for {u['needed_for']}")

st.subheader("Software status")
st.markdown("""
| Phase | Software | Scientific status |
|---|---|---|
| 0 Feasibility (CPU ray tracing) | done | engine checks E1–E5 passed; laptop acceptance: see the gates above |
| 1 Literature and standards | done | references verified (`docs/references.md`) |
| 2–4 Geospatial pipeline, radio configuration | done | methodology approved as reported; dataset not yet fit (observations) |
| 5–6 Single-site and multi-site coverage | done | development results only |
| 7 Validation | done (TR 38.901, CPU/GPU, analytical); MATLAB package prepared | MATLAB not executed; no field measurements |
| 8 Site planning | done (SINR greedy) | candidate thresholds pending; development results only |
| 9–10 Comparison, 6G roadmap | done | conclusions are the student's, from research results |
| Release | v1.0.0-rc.1: software release candidate | not a research result |
""")
st.caption("Software that works is not a scientific result: no phase is scientifically complete until research runs "
           "on a dataset fit for research pass the gates above.")

c1, c2, c3, c4 = st.columns(4)
runs = ui.run_list()
cache = list((ui.ROOT / "data" / "cache" / "pathgain").glob("*/*.json"))
c1.metric("Saved runs", len(runs))
c2.metric("Cached path-gain maps", len(cache))
profiles = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))["profiles"]
c3.metric("Usable profiles", sum(p.get("rays_per_site") is not None for p in profiles.values()))
areas = ui.study_areas()
c4.metric("Study areas", len(areas), help="Approved study district: "
          + (", ".join(k for k, v in areas.items() if v.get("approved")) or "none"))

st.subheader("Profiles and backends")
st.dataframe(configuration.backend_profile_rows(ui.ROOT), hide_index=True, use_container_width=True)
st.caption("Research runs: approved profile and the production backend (CPU) only; GPU and auto are for "
           "development. The standard profile's acceptance must be re-measured on the final scene.")

if runs:
    latest = ui.run(runs[0])
    st.subheader("Latest run")
    st.write(ui.run_title(latest))
    st.dataframe([{"scenario": sc["label"], "coverage": ui.fmt(latest.scenario_summary(sc["id"])["coverage_fraction"],
                                                                ".1%"),
                   "median SINR": ui.fmt(latest.scenario_summary(sc["id"])["sinr_db_median"], ".1f", " dB"),
                   "5th-pct rate": ui.fmt(latest.scenario_summary(sc["id"])["rate_p5_bps"], ".1f", " Mbit/s", 1e-6)}
                  for sc in latest.scenarios], hide_index=True, use_container_width=True)
    with st.expander("Run manifest (excerpt)"):
        st.code(json.dumps({k: latest.manifest[k] for k in ("label", "run_id", "profile", "timing")
                            if k in latest.manifest}, indent=2), language="json")
