import json

import plotly.graph_objects as go
import streamlit as st
import ui
from ui import t

from bns.analysis import readiness
from bns.app import configuration

ui.page_header("study_area.title", "study_area.caption")
tr = ui.tr()

areas = ui.study_areas()
c1, c2 = st.columns([2, 2])
study = [k for k, v in areas.items() if v.get("approved")]


def area_label(a: str) -> str:
    key = f"study_area.names.{a}"
    return t(key) if tr.has(key) else a


area_name = c1.selectbox(t("study_area.area"), list(areas), index=list(areas).index(study[0]) if study else 0,
                         format_func=area_label)
info = areas[area_name]
variants = ui.variants(area_name)
if not variants:
    st.warning(t("study_area.no_dataset", area=area_name))
    st.stop()
variant = c2.selectbox(t("study_area.variant"), variants, index=ui.default_variant(area_name, variants),
                       format_func=ui.variant_name, help=t("study_area.variant_help"))
if info["role"] != "study district":
    st.warning(t("study_area.not_study"))

quality = json.loads((ui.ROOT / "data" / "scenes" / area_name / variant / "quality_report.json").read_text(encoding="utf-8"))
cats = quality["height_categories"]["by_count"]
model = quality.get("height_model") or {}
synthetic = (model.get("synthetic") or {}).get("synthetic_buildings", 0) if model else 0
documented = cats.get("observed", 0) + cats.get("estimated", 0)
total = quality["buildings"]
m = st.columns(4)
m[0].metric(t("study_area.metrics.buildings"), total)
m[1].metric(t("study_area.metrics.documented"), f"{documented} ({100 * documented / total:.1f} %)")
m[2].metric(t("study_area.metrics.synthetic"), f"{synthetic} ({100 * synthetic / total:.1f} %)")
plain = cats.get("placeholder", 0) - synthetic
m[3].metric(t("study_area.metrics.placeholder"), f"{plain} ({100 * plain / total:.1f} %)")
if synthetic:
    st.info(t("study_area.synthetic_note", seed=model.get("seed")))

area, buildings = ui.buildings(area_name, variant)
colour_by = st.radio(t("study_area.map_colour"), ["provenance", "height"], horizontal=True,
                     format_func=lambda k: t(f"study_area.colour_{k}"))
fig = go.Figure()
if colour_by == "provenance":
    for cat, col in ui.CATEGORY_COLOURS.items():
        polys = [b.polygon for b in buildings if ui.height_display_category(b) == cat]
        if polys:
            xs, ys = ui.outline_xy(polys)
            fig.add_scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=col, line=dict(color="#555", width=0.4),
                            name=f"{t(f'common.height_category.{cat}')} ({len(polys)})", hoverinfo="skip")
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
                name=t("study_area.receiver_area"))
tall = sorted(buildings, key=lambda b: -b.height.height_m)[:40]
fig.add_scatter(x=[b.polygon.representative_point().x for b in tall], y=[b.polygon.representative_point().y for b in tall],
                mode="markers", marker=dict(size=5, color="rgba(0,0,0,0)"), showlegend=False,
                hovertext=[f"{b.building_id}<br>{b.height.height_m:g} m, "
                           f"{t('common.height_category.' + ui.height_display_category(b))}<br>{b.height.source}"
                           for b in tall], hoverinfo="text")
fig.update_layout(height=640, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="#fcfcfb",
                  yaxis=dict(scaleanchor="x", title=t("study_area.y_axis")), xaxis=dict(title=t("study_area.x_axis")),
                  legend=dict(orientation="h", y=1.02))
ui.chart(fig)

if info["role"] == "study district":
    gates = {g.id: g for g in readiness.indicators(ui.ROOT)}
    with st.expander(t("study_area.observations")):
        data = gates["observations"].data
        for grp in data.get("groups") or []:
            accepted = ", ".join(grp["accepted"]).replace("_", " ")
            st.progress(grp["observed"] / grp["required"] if grp["required"] else 0.0,
                        text=t("study_area.group_progress", groups=", ".join(grp["priorities"]), observed=grp["observed"],
                               required=grp["required"], accepted=accepted))
        st.caption(t("study_area.observations_note"))
    with st.expander(t("study_area.methodology")):
        rows = ui.localized_rows(configuration.study_area_rows(ui.ROOT, area_name))
        st.dataframe(rows, hide_index=True, use_container_width=True, height=36 * len(rows) + 40)
    with st.expander(t("study_area.site_rule")):
        rows = ui.localized_rows(configuration.site_rule_rows(ui.ROOT))
        st.dataframe(rows, hide_index=True, use_container_width=True, height=36 * len(rows) + 40)
        cand = gates["candidates"]
        st.caption(f"{t('readiness.title.candidates')}: {t('readiness.state.' + cand.state)} — {cand.detail}")

with st.expander(t("study_area.tallest")):
    cols = "study_area.columns."
    st.dataframe([{t(cols + "building"): b.building_id, t(cols + "height"): b.height.height_m,
                   t(cols + "category"): t("common.height_category." + ui.height_display_category(b)),
                   t(cols + "source"): b.height.source, t(cols + "method"): b.height.method,
                   t(cols + "alternatives"): "; ".join(f"{a.source} {a.height_m:g} m" for a in b.height.alternatives)}
                  for b in tall[:25]], hide_index=True)

with st.expander(t("study_area.external")):
    for name, title in (("gba", "GlobalBuildingAtlas"), ("3d_globfp", "3D-GloBFP")):
        path = ui.ROOT / "outputs" / "datasets" / area_name / f"{name}_evaluation.md"
        st.markdown(f"**{title}**")
        if path.exists():
            ui.markdown_file(path)
        else:
            st.caption(t("study_area.no_evaluation"))
