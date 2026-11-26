import numpy as np
import plotly.graph_objects as go
import streamlit as st
import ui

from bns.app.results import cdf

ui.page_header("Coverage analysis", "Maps of a saved run. Indoor cells (building footprints) are shown grey "
               "and never count; unreached outdoor cells count as uncovered.")
run = ui.pick_run("coverage-run")
if run is None:
    st.stop()
ui.development_banner(run.label)
st.caption(f"Backend: {run.backend.upper()} · profile {run.manifest['profile']['name']} · "
           + ("site plan: maps show the final selection of each scenario" if run.kind == "site_plan" else
              f"{len(run.sites)} site(s)"))

scen = run.scenarios
c1, c2, c3 = st.columns([2, 2, 1])
sid = c1.radio("Scenario", [s["id"] for s in scen], horizontal=True,
               format_func=lambda i: next(ui.band_name(s['label'], s['frequency_hz'] / 1e9) for s in scen if s["id"] == i))
available = [k for k in ui.LAYERS if k in run.layers()]
if not available:
    st.warning("This run has no map layers for display.")
    st.stop()
layer = c2.selectbox("Layer", available, format_func=lambda k: ui.LAYERS[k][0],
                     index=available.index("sinr_db") if "sinr_db" in available else 0)
show_buildings = c3.toggle("Buildings", value=True)

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
        st.caption(f"Buildings unavailable: {exc}")

left, right = st.columns([3, 1])
with left:
    st.plotly_chart(ui.map_figure(grid, z, outdoor, layer=layer, sites=run.sites_for(sid), azimuths=run.sector_azimuths_rad,
                                  footprints=footprints), use_container_width=True)
with right:
    s = run.scenario_summary(sid)
    sc = next(x for x in scen if x["id"] == sid)
    st.markdown(f"#### {sc['label']}")
    st.caption(f"{sc['frequency_hz'] / 1e9:g} GHz · {sc['bandwidth_hz'] / 1e6:g} MHz · {sc['status']}")
    if not s:
        st.warning("No site was selected for this scenario.")
        st.stop()
    st.metric("Coverage", ui.fmt(s["coverage_fraction"], ".1%"),
              help=f"Outdoor cells with {s['coverage_definition']} ≥ {s['coverage_threshold']:g}")
    st.metric("Median SINR", ui.fmt(s["sinr_db_median"], ".1f", " dB"))
    st.metric("5th-percentile SINR", ui.fmt(s["sinr_db_p5"], ".1f", " dB"))
    st.metric("5th-percentile rate", ui.fmt(s["rate_p5_bps"], ".1f", " Mbit/s", 1e-6))
    st.metric("Median rate", ui.fmt(s["rate_median_bps"], ".0f", " Mbit/s", 1e-6))
    st.metric("Noise power", ui.fmt(s["noise_dbm"], ".1f", " dBm"))
    if "interference_limited_share" in s:
        st.metric("Interference-limited cells", ui.fmt(s["interference_limited_share"], ".0%"),
                  help="Served outdoor cells where interference exceeds noise.")
    st.caption(f"{s['outdoor_cells']} outdoor cells · unreached {s['unreached_fraction']:.1%}. "
               "Rates are Shannon upper bounds, not user throughput.")

values = z[outdoor].astype(float)
if layer == "rate_bps":
    values = values / 1e6
if layer not in ("covered", "serving_site", "serving_sector"):
    x, p = cdf(values, floor=None)
    fig = go.Figure(go.Scatter(x=x, y=p, mode="lines", line=dict(color=ui.colour(sid), width=2.5)))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10), title=f"CDF of outdoor cells: {ui.LAYERS[layer][0]}",
                      xaxis_title=ui.LAYERS[layer][1], yaxis_title="share at or below", plot_bgcolor="#fcfcfb")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Cells without any path ({int((~np.isfinite(values)).sum())}) are left out of this curve.")

with st.expander("Sites" + (" (selected for this scenario)" if run.kind == "site_plan" else "")):
    st.dataframe(run.sites_for(sid), hide_index=True, use_container_width=True)
