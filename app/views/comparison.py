import json

import plotly.graph_objects as go
import streamlit as st
import ui

from bns.app import evidence, results
from bns.app.results import cdf
from bns.reporting.report import LIMITATIONS

ui.page_header("Comparison", "The five scenarios on the same grid, sites and radio system — only frequency and "
               "bandwidth differ — plus comparisons across runs, site counts, the 3GPP check and sensitivity.")
LAYOUT = dict(margin=dict(l=10, r=10, t=40, b=70), plot_bgcolor="#fcfcfb",
              legend=dict(orientation="h", y=-0.32, yanchor="top"))

tab_bands, tab_runs, tab_sites, tab_model, tab_sens, tab_lim = st.tabs(
    ["Scenarios in one run", "Across runs", "Site counts", "3GPP model check", "Sensitivity", "Limitations"])

with tab_bands:
    run = ui.pick_run("comparison-run")
    if run is not None:
        ui.development_banner(run.label)
        scen, outdoor = run.scenarios, run.outdoor
        table = evidence.band_table(run)
        st.dataframe([{"scenario": r["scenario"], "GHz": r["frequency_ghz"], "MHz": r["bandwidth_mhz"],
                       "coverage [%]": None if r["coverage"] is None else round(100 * r["coverage"], 1),
                       "median received power [dBm]": None if r["rx_power_median_dbm"] is None else round(r["rx_power_median_dbm"], 1),
                       "median SINR [dB]": None if r["sinr_median_db"] is None else round(r["sinr_median_db"], 1),
                       "5th-pct rate [Mbit/s]": None if r["rate_p5_mbps"] is None else round(r["rate_p5_mbps"], 1),
                       "median rate [Mbit/s]": None if r["rate_median_mbps"] is None else round(r["rate_median_mbps"])}
                      for r in table], hide_index=True, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        for col, key, title, unit in ((c1, "coverage", "Coverage vs frequency", "%"),
                                      (c2, "rx_power_median_dbm", "Median received power", "dBm"),
                                      (c3, "sinr_median_db", "Median SINR", "dB")):
            ys = [None if r[key] is None else (100 * r[key] if key == "coverage" else r[key]) for r in table]
            fig = go.Figure(go.Bar(x=[f"{r['frequency_ghz']:g} GHz" for r in table], y=ys,
                                   marker_color=[ui.colour(r["scenario_id"]) for r in table],
                                   text=[None if y is None else f"{y:.1f}" for y in ys], textposition="outside"))
            fig.update_layout(height=300, title=title, yaxis_title=unit, **LAYOUT)
            col.plotly_chart(fig, use_container_width=True)

        def cdf_plot(name, title, unit, scale=1.0, log=False):
            fig = go.Figure()
            for sc in scen:
                layer = run.layer(sc["id"], name)
                if layer is None:
                    continue
                x, p = cdf(layer[outdoor] * scale, floor=-40 if name == "sinr_db" else None)
                if log:
                    keep = x > 0
                    x, p = x[keep], p[keep]
                fig.add_scatter(x=x, y=p, mode="lines", name=sc["label"], line=dict(color=ui.colour(sc["id"]), width=2.4))
            fig.update_layout(height=360, title=title, xaxis_title=unit, yaxis_title="share of outdoor cells at or below",
                              **LAYOUT)
            if log:
                fig.update_xaxes(type="log", range=[0, 4])
            return fig

        a, b = st.columns(2)
        a.plotly_chart(cdf_plot("sinr_db", "SINR CDF", "dB"), use_container_width=True)
        b.plotly_chart(cdf_plot("rate_bps", "Shannon rate CDF (upper bound)", "Mbit/s", 1e-6, log=True),
                       use_container_width=True)
        st.caption("Unreached outdoor cells enter the SINR curve at −40 dB and the rate percentiles with 0. Shannon "
                   "rate = one user with the whole carrier: a theoretical link bound, not capacity or throughput.")

        if run.kind == "multi_site" and len(run.sites) > 1:
            st.subheader("Single site vs network")
            res = run.summary["results"]
            st.dataframe([{"scenario": sc["label"], "network [%]": round(100 * res[sc["id"]]["network"]["coverage_fraction"], 1),
                           **{f"{run.sites[i]['candidate_id']} alone [%]": round(100 * a_["coverage_fraction"], 1)
                              for i, a_ in enumerate(res[sc["id"]]["sites_alone"])},
                           "additions that lowered coverage": ", ".join(
                               f"site {d['added_site']} ({100 * d['change']:+.1f} pt)"
                               for d in res[sc["id"]]["additions_that_lowered_coverage"]) or "none"} for sc in scen],
                         hide_index=True, use_container_width=True)
            fig = go.Figure()
            for sc in scen:
                grown = [g["coverage_fraction"] for g in res[sc["id"]]["grown_in_given_order"]]
                fig.add_scatter(x=list(range(1, len(grown) + 1)), y=[100 * v for v in grown], mode="lines+markers",
                                name=sc["label"], line=dict(color=ui.colour(sc["id"])))
            fig.update_layout(height=320, title="Coverage vs number of sites (given order)", xaxis=dict(title="sites", dtick=1),
                              yaxis_title="coverage [%]", **LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

with tab_runs:
    paths = ui.run_list()
    chosen = st.multiselect("Runs to compare", paths, default=paths[:2] if len(paths) > 1 else paths,
                            format_func=lambda p: ui.run_title(ui.run(p)))
    if len(chosen) >= 2:
        runs = [ui.run(p) for p in chosen]
        ref = runs[0]
        for other in runs[1:]:
            diff = results.differences(ref, other)
            if diff:
                st.warning(f"`{other.run_id}` differs from `{ref.run_id}` in: **{', '.join(diff)}**. These are not the "
                           "same experiment; read differences as the combined effect of all of them.")
            else:
                st.success(f"`{other.run_id}` and `{ref.run_id}` share area, grid, profile, mechanisms, antennas, radio "
                           "parameters, load and backend.")
        metric = st.selectbox("Metric", ["coverage", "sinr_median_db", "rate_p5_mbps", "rate_median_mbps"],
                              format_func=lambda k: {"coverage": "coverage [%]", "sinr_median_db": "median SINR [dB]",
                                                     "rate_p5_mbps": "5th-pct Shannon rate [Mbit/s]",
                                                     "rate_median_mbps": "median Shannon rate [Mbit/s]"}[k])
        fig = go.Figure()
        for r in runs:
            t = evidence.band_table(r)
            fig.add_scatter(x=[x["frequency_ghz"] for x in t],
                            y=[None if x[metric] is None else (100 * x[metric] if metric == "coverage" else x[metric]) for x in t],
                            mode="lines+markers", name=ui.run_title(r)[:70])
        fig.update_layout(height=380, xaxis=dict(title="frequency [GHz]", type="log"), **LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select at least two runs.")

with tab_sites:
    plans = evidence.site_plans(ui.ROOT)
    if not plans:
        st.info("No saved site plan (scripts/plan_sites.py or the Site planning page).")
    else:
        cases = sorted({(p["threshold_db"], p["load"], p["run"]) for p in plans})
        fig = go.Figure()
        for thr, load, rid in cases:
            sel = [p for p in plans if p["run"] == rid]
            fig.add_scatter(x=[p["frequency_ghz"] for p in sel], y=[p["sites"] for p in sel], mode="lines+markers",
                            name=f"threshold {thr:g} dB, load {load:g}" + (" (sensitivity)" if sel[0]["overrides"] else ""),
                            hovertext=[f"{p['stopped_because']}, coverage {100 * (p['coverage'] or 0):.1f} %" for p in sel])
        fig.update_layout(height=380, title="Sites selected by the SINR greedy vs frequency",
                          xaxis=dict(title="frequency [GHz]", type="log"), yaxis=dict(title="sites", dtick=1), **LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe([{"band": ui.band_name(p['scenario'], p['frequency_ghz']), "threshold [dB]": p["threshold_db"],
                       "load": p["load"], "sites": p["sites"], "sites per km²": round(p["site_density_per_km2"], 2),
                       "coverage": ui.fmt(p["coverage"], ".1%"), "target": ui.fmt(p["target"], ".0%"),
                       "stop": p["stopped_because"], "candidates": p["candidates"], "profile": p["profile"],
                       "backend": p["backend"]} for p in plans], hide_index=True, use_container_width=True)
        st.caption("Greedy over the saved candidates (heuristic, not a minimum). 'no candidate raises coverage' is a "
                   "local stall, not proof that the target is unreachable. Density = sites / 1 km² receiver area.")

with tab_model:
    v = evidence.validation_summary(ui.ROOT)
    if v is None:
        st.info("No TR 38.901 comparison saved yet (scripts/validate_tr38901.py).")
    else:
        st.caption(f"`{v['folder'].name}` — model-to-model comparison (category 2), not a validation against measurements.")
        names = {s["id"]: ui.band_name(s['label'], s['frequency_hz'] / 1e9) for s in ui.scenarios()}
        fig = go.Figure()
        for model, dash in (("UMa", "solid"), ("UMi", "dash")):
            for cls, symbol in (("LOS", "circle"), ("NLOS", "square")):
                sel = [r for r in v["rows"] if r["model"] == model and r["class"] == cls]
                fig.add_scatter(x=[names[r["scenario_id"]] for r in sel], y=[r["rmse_db"] for r in sel],
                                mode="lines+markers", name=f"{model} {cls}", line=dict(dash=dash),
                                marker=dict(symbol=symbol))
        fig.update_layout(height=360, title="RMSE of traced vs TR 38.901 path loss", yaxis_title="dB", **LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe([{**r, "scenario": names[r["scenario_id"]], "mean_error_db": round(r["mean_error_db"], 1),
                       "std_db": round(r["std_db"], 1), "rmse_db": round(r["rmse_db"], 1)} for r in v["rows"]],
                     hide_index=True, use_container_width=True)

with tab_sens:
    candidates = [ui.run(p) for p in ui.run_list() if (ui.run(p).path / "sensitivity.json").exists()]
    if not candidates:
        st.info("No sensitivity analysis saved (scripts/run_sensitivity.py RUN_DIR).")
    else:
        srun = candidates[0]
        data = json.loads((srun.path / "sensitivity.json").read_text(encoding="utf-8"))
        ui.development_banner(data["label"])
        st.caption(f"From `{srun.run_id}`. Sourced candidate values: threshold {data['sourced']['threshold']} dB, "
                   f"load {data['sourced']['load']}; all other points are provisional sweep values.")
        load = st.radio("Load (interference activity)", data["loads"], horizontal=True)
        fig = go.Figure()
        for sc in srun.scenarios:
            cs = [c for c in data["results"][sc["id"]] if c["load"] == load]
            fig.add_scatter(x=[c["threshold_db"] for c in cs], y=[100 * c["all_sites"]["coverage"] for c in cs],
                            mode="lines+markers", name=f"{sc['label']} all sites", line=dict(color=ui.colour(sc["id"])))
            fig.add_scatter(x=[c["threshold_db"] for c in cs], y=[100 * c["site_1_alone"]["coverage"] for c in cs],
                            mode="lines", name=f"{sc['label']} site 1", line=dict(color=ui.colour(sc["id"]), dash="dot"),
                            showlegend=False)
        fig.add_vline(x=-10, line_dash="dash", line_color="#888", annotation_text="candidate −10 dB")
        fig.update_layout(height=380, title="Coverage vs SINR threshold (solid: all sites; dotted: site 1 alone)",
                          xaxis_title="threshold [dB]", yaxis_title="coverage [%]", **LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("Full table"):
            ui.markdown_file(srun.path / "sensitivity.md")

with tab_lim:
    for line in LIMITATIONS:
        st.markdown(f"- {line}")
    st.markdown("- Runs are compared as one experiment only when area, grid, profile, mechanisms, antennas, radio "
                "parameters, load and backend match; otherwise a warning names the differences.")
