import json

import streamlit as st
import ui
import yaml

from bns.analysis import readiness
from bns.app import configuration

ui.page_header("Coverage and data rate of 4G, 5G and candidate 6G in Baghdad",
               "Ray-tracing study over a ~1 km² district and a 6G roadmap for Iraq (graduation project).")

scen = ui.scenarios()
cols = st.columns(len(scen))
for col, sc in zip(cols, scen, strict=True):
    with col:
        st.markdown(f'<div style="border-top:4px solid {ui.colour(sc["id"])};padding-top:.3rem">'
                    f'<b>{sc["label"]}</b><br><span style="font-size:1.5rem">{sc["frequency_hz"] / 1e9:g} GHz</span>'
                    f'<br>{sc["bandwidth_hz"] / 1e6:g} MHz · {sc["status"]}</div>', unsafe_allow_html=True)

st.subheader("Research readiness")
st.caption("Scientific and technical status, computed from the data, configuration and saved evidence. It informs; "
           "it never blocks a simulation. Each run's result is classified from its own configuration, dataset and "
           "validation status.")
indicators = readiness.indicators(ui.ROOT)
MARK = {readiness.READY: "✅ Ready", readiness.COMPLETED: "✅ Completed", readiness.INCOMPLETE: "🟠 Incomplete data",
        readiness.PENDING: "⏳ Validation pending", readiness.BASELINE: "🔷 Research baseline",
        readiness.CUSTOM: "🔶 Custom experiment", readiness.SYNTHETIC_COMPLETE: "🧩 Synthetic Data Complete"}
st.dataframe([{"item": i.title, "status": MARK.get(i.state, i.state), "details": i.detail} for i in indicators],
             hide_index=True, use_container_width=True)
obs = next(i for i in indicators if i.id == "observations").data
for grp in obs.get("groups") or []:
    if grp["required"]:
        pref = (f"; {' or '.join(grp['preferred'])} preferred" if grp.get("preferred") else "")
        st.progress(grp["observed"] / grp["required"],
                    text=f"{', '.join(grp['priorities'])} — {' or '.join(grp['accepted']).replace('_', ' ')}{pref}: "
                         f"{grp['observed']} of {grp['required']} buildings")
st.caption("Results are classified by configuration (Research Baseline, Custom Experiment, Sensitivity Analysis), "
           "dataset (complete, estimated or incomplete) and validation; only research-baseline runs on complete data after "
           "validation are Validated Research Results.")

st.subheader("Software status")
st.markdown("""
| Phase | Software | Scientific status |
|---|---|---|
| 0 Feasibility (CPU ray tracing) | done | engine checks E1–E5 passed; laptop acceptance: see above |
| 1 Literature and standards | done | references verified (`docs/references.md`) |
| 2–4 Geospatial pipeline, radio configuration | done | research baseline set; dataset incomplete (field observations) |
| 5–6 Single-site and multi-site coverage | done | preliminary simulations only |
| 7 Validation | done (TR 38.901, CPU/GPU, analytical); MATLAB package prepared | MATLAB not run; no field measurements |
| 8 Site planning | done (SINR greedy) | candidate pool needs the survey; preliminary simulations only |
| 9–10 Comparison, 6G roadmap | done | conclusions are the student's, from research results |
| Release | v1.0.0-rc.1: software release candidate | not a research result |
""")
st.caption("Software that works is not a scientific result: a result is a validated research finding only when it "
           "is a research-baseline run on complete data with validation completed.")

c1, c2, c3, c4 = st.columns(4)
runs = ui.run_list()
cache = list((ui.ROOT / "data" / "cache" / "pathgain").glob("*/*.json"))
c1.metric("Saved runs", len(runs))
c2.metric("Cached path-gain maps", len(cache))
profiles = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))["profiles"]
c3.metric("Usable profiles", sum(p.get("rays_per_site") is not None for p in profiles.values()))
areas = ui.study_areas()
c4.metric("Study areas", len(areas), help="Study district: "
          + (", ".join(k for k, v in areas.items() if v.get("approved")) or "none"))

st.subheader("Profiles and backends")
st.dataframe(configuration.backend_profile_rows(ui.ROOT), hide_index=True, use_container_width=True)
st.caption("The research baseline uses the standard profile on the CPU. Every profile and backend can run; others "
           "make the run a custom experiment (GPU limits: docs/validation.md §7).")

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
