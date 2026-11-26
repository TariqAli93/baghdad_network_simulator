import json

import streamlit as st
import ui
import yaml

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

st.subheader("Where the project stands")
st.markdown("""
| Phase | Software | Scientific status |
|---|---|---|
| 0 Feasibility (CPU ray tracing) | done | engine checks E1–E5 passed; **laptop gate open** (not yet run on the 16 GB laptop) |
| 1 Literature and standards | done | references verified (`docs/references.md`) |
| 2 Geospatial pipeline | done | district, building data and height method **not approved** |
| 3–4 Radio configuration, production pipeline | done | radio parameters are **proposals** awaiting approval |
| 5 Single-site coverage | done | blocked by the approvals above; development results only |
| 6 Multi-site network | done (first version) | development results only |
| 7+ Validation against 3GPP/MATLAB, site density, roadmap | not started | — |
""")
st.caption("Software that works is not a scientific result: no phase is scientifically complete until the "
           "supervisor approves the district, building heights, radio parameters and site rule "
           "(`docs/supervisor-decisions.md`).")

c1, c2, c3, c4 = st.columns(4)
runs = ui.run_list()
cache = list((ui.ROOT / "data" / "cache" / "pathgain").glob("*/*.json"))
c1.metric("Saved runs", len(runs))
c2.metric("Cached path-gain maps", len(cache))
profiles = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))["profiles"]
c3.metric("Usable profiles", sum(p.get("rays_per_site") is not None for p in profiles.values()))
areas = ui.study_areas()
c4.metric("Study areas", len(areas), help="None is the approved study district yet.")

st.subheader("Profiles")
st.dataframe([{"profile": k, "cell size [m]": v["cell_size_m"],
               "rays per sector": "—" if v.get("rays_per_site") is None else f"{float(v['rays_per_site']):.0e}",
               "status": v.get("status", ""), "basis": " ".join(str(v.get("basis", "")).split())}
              for k, v in profiles.items()], hide_index=True, use_container_width=True)

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
