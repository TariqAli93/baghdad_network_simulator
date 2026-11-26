import json

import plotly.graph_objects as go
import streamlit as st
import ui

from bns.analysis import readiness
from bns.app import configuration

ui.page_header("Study area", "Buildings, height provenance and data quality of each dataset variant.")

areas = ui.study_areas()
c1, c2 = st.columns([2, 2])
approved_areas = [k for k, v in areas.items() if v.get("approved")]
area_name = c1.selectbox("Area", list(areas), index=list(areas).index(approved_areas[0]) if approved_areas else 0)
info = areas[area_name]
variants = ui.variants(area_name)
if not variants:
    st.warning(f"No dataset built for {area_name}. Run `scripts/build_dataset.py --area {area_name}`.")
    st.stop()
variant = c2.selectbox("Dataset variant", variants, index=variants.index("osm") if "osm" in variants else 0,
                       help="osm: OpenStreetMap heights only (placeholder 9 m elsewhere); osm+<dataset>: "
                            "external heights as candidates under the height policy.")
st.markdown(f"**Role:** {info['role']} · **approved:** {info.get('approved', False)}")
if info["role"] != "study district":
    st.warning("Not the study district: use for development and testing only, never to report Baghdad results.")
else:
    gates = {g.id: g for g in readiness.gates(ui.ROOT)}
    with st.expander("Approved study-area and building-data methodology", expanded=True):
        rows = configuration.study_area_rows(ui.ROOT, area_name)
        st.dataframe(rows, hide_index=True, use_container_width=True, height=36 * len(rows) + 40)
    obs = gates["observations"]
    st.markdown(f"**Mandatory observations:** {obs.detail}")
    data = obs.data
    if data.get("by_priority"):
        cols = st.columns(len(data["by_priority"]) + 1)
        for col, (p, v) in zip(cols, data["by_priority"].items()):
            col.metric("Candidate survey (S)" if p == "S" else f"{p} observed", f"{v['observed']} / {v['required']}")
            col.progress(v["observed"] / v["required"] if v["required"] else 0.0)
        cols[-1].metric("Covered by sensitivity", ", ".join(f"{k}: {n}" for k, n in data["covered_by_sensitivity"].items())
                        or "—")
    st.caption("Worklist, map and template: outputs/datasets/<area>/fieldwork/ (scripts/fieldwork_package.py). "
               "Import observations with scripts/build_dataset.py --observations FILE; the required list comes from "
               "configs/study_area.yaml, never from the submitted file.")
    with st.expander("Site rule and candidate rooftops (decision A4)"):
        rows = configuration.site_rule_rows(ui.ROOT)
        st.dataframe(rows, hide_index=True, use_container_width=True, height=36 * len(rows) + 40)
        st.caption(gates["candidate_criteria"].title + ": " + gates["candidate_criteria"].detail)

quality = json.loads((ui.ROOT / "data" / "scenes" / area_name / variant / "quality_report.json").read_text(encoding="utf-8"))
cats = quality["height_categories"]["by_count"]
pct = quality["height_categories"]["by_count_percent"]
m = st.columns(4)
m[0].metric("Buildings", quality["buildings"])
m[1].metric("Observed heights", f"{cats['observed']} ({pct['observed']:.1f} %)")
m[2].metric("Estimated heights", f"{cats['estimated']} ({pct['estimated']:.1f} %)")
m[3].metric("Placeholder heights", f"{cats['placeholder']} ({pct['placeholder']:.1f} %)")
if not quality["fit_for_research"]:
    st.error("Not fit for research: " + "; ".join(quality["not_fit_reasons"]))

area, buildings = ui.buildings(area_name, variant)
colour_by = st.radio("Colour buildings by", ["height provenance", "height"], horizontal=True)
fig = go.Figure()
if colour_by == "height provenance":
    for cat, col in ui.CATEGORY_COLOURS.items():
        polys = [b.polygon for b in buildings if b.height.category == cat]
        if polys:
            xs, ys = ui.outline_xy(polys)
            fig.add_scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=col, line=dict(color="#555", width=0.4),
                            name=f"{cat} ({len(polys)})", hoverinfo="skip")
else:
    bands = [(0, 6, "#e3ecf7"), (6, 10, "#9ec5f4"), (10, 15, "#3987e5"), (15, 30, "#184f95"), (30, 999, "#0b1f3a")]
    for lo, hi, col in bands:
        polys = [b.polygon for b in buildings if lo <= b.height.height_m < hi]
        if polys:
            xs, ys = ui.outline_xy(polys)
            fig.add_scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=col, line=dict(color="#555", width=0.4),
                            name=f"{lo}-{hi if hi < 999 else '+'} m ({len(polys)})", hoverinfo="skip")
rx = area.receiver_box()
bx, by = rx.exterior.xy
fig.add_scatter(x=list(bx), y=list(by), mode="lines", line=dict(color="#c0504d", dash="dash", width=1.5),
                name="receiver area")
tall = sorted(buildings, key=lambda b: -b.height.height_m)[:40]
fig.add_scatter(x=[b.polygon.representative_point().x for b in tall], y=[b.polygon.representative_point().y for b in tall],
                mode="markers", marker=dict(size=5, color="rgba(0,0,0,0)"), showlegend=False,
                hovertext=[f"{b.building_id}<br>{b.height.height_m:g} m, {b.height.category}<br>{b.height.source}"
                           for b in tall], hoverinfo="text")
fig.update_layout(height=680, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="#fcfcfb",
                  yaxis=dict(scaleanchor="x", title="y north [m]"), xaxis=dict(title="x east [m]"),
                  legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Tallest buildings and their height provenance")
st.dataframe([{"building": b.building_id, "height [m]": b.height.height_m, "category": b.height.category,
               "source": b.height.source, "method": b.height.method,
               "alternatives": "; ".join(f"{a.source} {a.height_m:g} m" for a in b.height.alternatives)}
              for b in tall[:25]], hide_index=True, use_container_width=True)

st.subheader("External height datasets (evaluated, not approved)")
for name, title in (("gba", "GlobalBuildingAtlas"), ("3d_globfp", "3D-GloBFP")):
    path = ui.ROOT / "outputs" / "datasets" / area_name / f"{name}_evaluation.md"
    with st.expander(title, expanded=False):
        st.markdown(path.read_text(encoding="utf-8") if path.exists()
                    else f"No evaluation for this area (`scripts/evaluate_{'gba' if name == 'gba' else 'height_dataset'}.py`).")
