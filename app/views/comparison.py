import plotly.graph_objects as go
import streamlit as st
import ui

from bns.app.results import cdf

ui.page_header("Comparison", "The five scenarios on the same grid, sites and radio system: only frequency and "
               "bandwidth differ.")
run = ui.pick_run("comparison-run")
if run is None:
    st.stop()
ui.development_banner(run.label)
scen = run.scenarios
outdoor = run.outdoor

rows = []
for sc in scen:
    s = run.scenario_summary(sc["id"])
    rows.append({"scenario": sc["label"], "GHz": sc["frequency_hz"] / 1e9, "MHz": sc["bandwidth_hz"] / 1e6,
                 "coverage": round(100 * s["coverage_fraction"], 1),
                 "median SINR [dB]": None if s["sinr_db_median"] is None else round(s["sinr_db_median"], 1),
                 "5th-pct SINR [dB]": round(s["sinr_db_p5"], 1) if s["sinr_db_p5"] > -1e8 else None,
                 "5th-pct rate [Mbit/s]": round(s["rate_p5_bps"] / 1e6, 1),
                 "median rate [Mbit/s]": round(s["rate_median_bps"] / 1e6, 0),
                 "noise [dBm]": round(s["noise_dbm"], 1)})
st.dataframe(rows, hide_index=True, use_container_width=True,
             column_config={"coverage": st.column_config.ProgressColumn("coverage [%]", min_value=0, max_value=100,
                                                                        format="%.1f")})


def cdf_plot(name: str, title: str, unit: str, scale: float = 1.0, log: bool = False) -> go.Figure:
    fig = go.Figure()
    for sc in scen:
        v = run.layer(sc["id"], name)[outdoor] * scale
        x, p = cdf(v, floor=-40 if name == "sinr_db" else None)
        if log:
            keep = x > 0
            x, p = x[keep], p[keep]
        fig.add_scatter(x=x, y=p, mode="lines", name=sc["label"], line=dict(color=ui.colour(sc["id"]), width=2.4))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10), title=title, xaxis_title=unit,
                      yaxis_title="share of outdoor cells at or below", plot_bgcolor="#fcfcfb",
                      legend=dict(orientation="h", y=-0.25))
    if log:
        fig.update_xaxes(type="log", range=[0, 4])
    return fig


c1, c2 = st.columns(2)
c1.plotly_chart(cdf_plot("sinr_db", "SINR", "dB"), use_container_width=True)
c2.plotly_chart(cdf_plot("rate_bps", "Shannon rate (upper bound)", "Mbit/s", 1e-6, log=True), use_container_width=True)
st.caption("Unreached outdoor cells enter the SINR curve at −40 dB and the rate percentiles with 0.")

fig = go.Figure()
for metric, label in (("rate_p5_bps", "5th percentile"), ("rate_median_bps", "median")):
    fig.add_bar(x=[sc["label"] for sc in scen], y=[run.scenario_summary(sc["id"])[metric] / 1e6 for sc in scen],
                name=label, marker_color=[ui.colour(sc["id"]) for sc in scen],
                marker_pattern_shape="" if metric == "rate_median_bps" else "/", opacity=1 if metric == "rate_median_bps" else 0.65)
fig.update_layout(barmode="group", height=320, margin=dict(l=10, r=10, t=40, b=10), title="Shannon rate [Mbit/s]",
                  plot_bgcolor="#fcfcfb", yaxis_type="log")
st.plotly_chart(fig, use_container_width=True)

if run.kind == "multi_site" and len(run.sites) > 1:
    st.subheader("Single site vs network")
    res = run.summary["results"]
    table = []
    for sc in scen:
        r = res[sc["id"]]
        row = {"scenario": sc["label"], "network": round(100 * r["network"]["coverage_fraction"], 1)}
        for i, a in enumerate(r["sites_alone"]):
            row[f"{run.sites[i]['candidate_id']} alone"] = round(100 * a["coverage_fraction"], 1)
        row["additions that lowered coverage"] = ", ".join(
            f"site {d['added_site']} ({100 * d['change']:+.1f} pt)" for d in r["additions_that_lowered_coverage"]) or "none"
        table.append(row)
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption("Coverage in % of outdoor cells. Every site keeps its own three sectors; in the network every sector "
               "interferes with every other (reuse 1, full load).")
    fig = go.Figure()
    for sc in scen:
        grown = [g["coverage_fraction"] for g in res[sc["id"]]["grown_in_given_order"]]
        fig.add_scatter(x=list(range(1, len(grown) + 1)), y=[100 * v for v in grown], mode="lines+markers",
                        name=sc["label"], line=dict(color=ui.colour(sc["id"])))
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=40, b=10), title="Coverage as sites are added in the given order",
                      xaxis=dict(title="sites", dtick=1), yaxis_title="coverage [%]", plot_bgcolor="#fcfcfb")
    st.plotly_chart(fig, use_container_width=True)

    sid = st.selectbox("SINR distribution, network vs each site alone", [s["id"] for s in scen],
                       format_func=lambda i: next(s["label"] for s in scen if s["id"] == i))
    fig = go.Figure()
    x, p = cdf(run.layer(sid, "sinr_db")[outdoor], floor=-40)
    fig.add_scatter(x=x, y=p, name="network", line=dict(color=ui.colour(sid), width=3))
    for i, s in enumerate(run.sites):
        alone = run.site_alone_sinr(sid, i)
        if alone is not None:
            x, p = cdf(alone[outdoor], floor=-40)
            fig.add_scatter(x=x, y=p, name=f"{s['candidate_id']} alone", line=dict(color=ui.SITE_COLOURS[i], dash="dot"))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="SINR [dB]",
                      yaxis_title="share at or below", plot_bgcolor="#fcfcfb")
    st.plotly_chart(fig, use_container_width=True)

