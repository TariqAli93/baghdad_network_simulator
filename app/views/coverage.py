import numpy as np
import plotly.graph_objects as go
import streamlit as st
import ui
from ui import t

from bns.app.results import cdf

ui.page_header("coverage.title", "coverage.caption")
ui.visit("coverage")
run = ui.pick_run("coverage-run")
if run is None:
    st.stop()
ui.result_banner(run.classification)
st.caption(t("coverage.run_line", backend=run.backend.upper(), profile=run.manifest["profile"]["name"],
             sites=t("coverage.site_plan_maps") if run.kind == "site_plan" else t("common.sites", count=len(run.sites))))

scen = run.scenarios
c1, c2, c3 = st.columns([2, 2, 1])
sid = c1.radio(t("common.scenario"), [s["id"] for s in scen], horizontal=True,
               format_func=lambda i: ui.scenario_name(next(s for s in scen if s["id"] == i)))
available = [k for k in ui.LAYERS if k in run.layers()]
if not available:
    st.warning(t("coverage.no_layers"))
    st.stop()
layer = c2.selectbox(t("common.layer"), available, format_func=ui.layer_title,
                     index=available.index("sinr_db") if "sinr_db" in available else 0)
show_buildings = c3.toggle(t("common.show_buildings"), value=True)

grid = run.grid
z = run.layer(sid, layer)
outdoor = run.outdoor
area = run.manifest["area"]
footprints = None
if show_buildings:
    try:
        _, blds = ui.buildings(area["name"], area.get("variant", "osm"))
        footprints = [b.polygon for b in blds]
    except Exception as exc:                    # dataset no longer present
        st.caption(t("coverage.buildings_unavailable"), help=str(exc))

left, right = st.columns([3, 1])
with left:
    ui.chart(ui.map_figure(grid, z, outdoor, layer=layer, sites=run.sites_for(sid), azimuths=run.sector_azimuths_rad,
                                  footprints=footprints))
with right:
    s = run.scenario_summary(sid)
    sc = next(x for x in scen if x["id"] == sid)
    st.markdown(f"#### {ui.scenario_name(sc)}")
    st.caption(f"{ui.ltr(f'{sc['bandwidth_hz'] / 1e6:g} MHz')} · {ui.scenario_status(sc)}", unsafe_allow_html=True)
    if sc["id"].startswith("c6g"):
        st.caption(t("common.candidate_6g_note"))
    if not s:
        st.warning(t("coverage.no_site"))
        st.stop()
    st.metric(t("coverage.metrics.coverage"), ui.fmt(s["coverage_fraction"], ".1%"),
              help=t("coverage.metrics.coverage_help", definition=s["coverage_definition"],
                     threshold=f"{s['coverage_threshold']:g}"))
    st.metric(t("coverage.metrics.sinr_median"), ui.fmt(s["sinr_db_median"], ".1f", " dB"), help=t("common.acronyms.sinr"))
    st.metric(t("coverage.metrics.sinr_p5"), ui.fmt(s["sinr_db_p5"], ".1f", " dB"))
    st.metric(t("coverage.metrics.rate_p5"), ui.fmt(s["rate_p5_bps"], ".1f", " Mbit/s", 1e-6),
              help=t("common.acronyms.shannon"))
    st.metric(t("coverage.metrics.rate_median"), ui.fmt(s["rate_median_bps"], ".0f", " Mbit/s", 1e-6))
    if s.get("rate_3gpp_p5_bps") is not None:
        st.metric(t("coverage.metrics.rate_3gpp_p5"), ui.fmt(s["rate_3gpp_p5_bps"], ".1f", " Mbit/s", 1e-6),
                  help=t("coverage.metrics.rate_3gpp_help"))
    st.metric(t("coverage.metrics.noise"), ui.fmt(s["noise_dbm"], ".1f", " dBm"))
    if "interference_limited_share" in s:
        st.metric(t("coverage.metrics.interference_limited"), ui.fmt(s["interference_limited_share"], ".0%"),
                  help=t("coverage.metrics.interference_limited_help"))
    st.caption(t("coverage.cells_note", cells=s["outdoor_cells"], unreached=f"{s['unreached_fraction']:.1%}"))

values = z[outdoor].astype(float)
if layer in ("rate_bps", "rate_3gpp_bps"):
    values = values / 1e6
if layer not in ("covered", "serving_site", "serving_sector"):
    x, p = cdf(values, floor=None)
    fig = go.Figure(go.Scatter(x=x, y=p, mode="lines", line=dict(color=ui.colour(sid), width=2.5)))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10),
                      title=t("coverage.cdf_title", layer=ui.layer_title(layer)),
                      xaxis_title=ui.LAYERS[layer][0], yaxis_title=t("coverage.cdf_y"), plot_bgcolor="#fcfcfb")
    ui.chart(fig)
    st.caption(t("coverage.cdf_note", cells=int((~np.isfinite(values)).sum())))

with st.expander(t("coverage.sites_selected") if run.kind == "site_plan" else t("coverage.sites")):
    st.dataframe(run.sites_for(sid), hide_index=True)
