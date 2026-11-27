import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import ui
from ui import t

from bns.app import evidence, results
from bns.app.results import cdf

ui.page_header("comparison.title", "comparison.caption")
ui.visit("comparison")
LAYOUT = dict(margin=dict(l=10, r=10, t=40, b=70), plot_bgcolor="#fcfcfb",
              legend=dict(orientation="h", y=-0.32, yanchor="top"))
C = "comparison.columns."


def r1(value, scale=1.0, digits=1):
    return None if value is None else round(scale * value, digits)


tab_bands, tab_runs, tab_sites, tab_model, tab_sens, tab_lim = st.tabs(
    [t(f"comparison.tabs.{k}") for k in ("bands", "runs", "sites", "model", "sensitivity", "limitations")])

with tab_bands:
    run = ui.pick_run("comparison-run")
    if run is not None:
        ui.result_banner(run.classification)
        scen, outdoor = run.scenarios, run.outdoor
        names = {sc["id"]: ui.scenario_name(sc) for sc in scen}
        table = evidence.band_table(run)
        # the scenario name carries the frequency and the bar chart below the received power
        st.dataframe([{t(C + "scenario"): names.get(r["scenario_id"], r["scenario"]),
                       "MHz": r["bandwidth_mhz"], t(C + "coverage"): r1(r["coverage"], 100),
                       t(C + "sinr"): r1(r["sinr_median_db"]),
                       t(C + "rate_p5"): r1(r["rate_p5_mbps"]), t(C + "rate_median"): r1(r["rate_median_mbps"], digits=0)}
                      for r in table], hide_index=True)
        if any(sc["id"].startswith("c6g") for sc in scen):
            st.caption(t("common.candidate_6g_note"))
        c1, c2, c3 = st.columns(3)
        for col, key, unit in ((c1, "coverage", "%"), (c2, "rx_power_median_dbm", "dBm"), (c3, "sinr_median_db", "dB")):
            ys = [None if r[key] is None else (100 * r[key] if key == "coverage" else r[key]) for r in table]
            fig = go.Figure(go.Bar(x=[f"{r['frequency_ghz']:g} GHz" for r in table], y=ys,
                                   marker_color=[ui.colour(r["scenario_id"]) for r in table],
                                   text=[None if y is None else f"{y:.1f}" for y in ys], textposition="outside"))
            fig.update_layout(height=300, title=t(f"comparison.charts.{key}"), yaxis_title=unit, **LAYOUT)
            ui.chart(container=col, fig=fig)

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
                fig.add_scatter(x=x, y=p, mode="lines", name=names[sc["id"]], line=dict(color=ui.colour(sc["id"]), width=2.4))
            fig.update_layout(height=360, title=title, xaxis_title=unit, yaxis_title=t("comparison.charts.cdf_y"), **LAYOUT)
            if log:
                fig.update_xaxes(type="log", range=[0, 4])
            return fig

        a, b = st.columns(2)
        ui.chart(container=a, fig=cdf_plot("sinr_db", t("comparison.charts.sinr_cdf"), "dB"))
        ui.chart(container=b, fig=cdf_plot("rate_bps", t("comparison.charts.rate_cdf"), "Mbit/s", 1e-6, log=True))
        st.caption(t("comparison.cdf_note"))

        if run.kind == "multi_site" and len(run.sites) > 1:
            st.subheader(t("comparison.network.title"))
            res = run.summary["results"]
            st.dataframe([{t(C + "scenario"): names[sc["id"]],
                           t("comparison.network.network"): round(100 * res[sc["id"]]["network"]["coverage_fraction"], 1),
                           **{t("comparison.network.alone", site=run.sites[i]["candidate_id"]): round(100 * a_["coverage_fraction"], 1)
                              for i, a_ in enumerate(res[sc["id"]]["sites_alone"]) if a_ is not None},
                           t("comparison.network.lowered"): ", ".join(
                               t("comparison.network.lowered_item", site=d["added_site"], change=f"{100 * d['change']:+.1f}")
                               for d in res[sc["id"]]["additions_that_lowered_coverage"]) or t("common.none")} for sc in scen],
                         hide_index=True)
            fig = go.Figure()
            for sc in scen:
                grown = [g["coverage_fraction"] for g in res[sc["id"]]["grown_in_given_order"]]
                fig.add_scatter(x=list(range(1, len(grown) + 1)), y=[100 * v for v in grown], mode="lines+markers",
                                name=names[sc["id"]], line=dict(color=ui.colour(sc["id"])))
            fig.update_layout(height=320, title=t("comparison.network.growth"),
                              xaxis=dict(title=t("comparison.network.sites_axis"), dtick=1),
                              yaxis_title=t(C + "coverage"), **LAYOUT)
            ui.chart(fig)

with tab_runs:
    paths = ui.run_list()
    requested = [p for p in st.session_state.pop("cmp-runs", []) if p in paths]      # from the Experiment History
    if requested:
        st.session_state["cmp_runs"] = requested
    chosen = ui.multiselect(st, t("comparison.runs.select"), paths, "cmp_runs",
                            default=paths[:2] if len(paths) > 1 else paths,
                            format_func=lambda p: ui.run_title(ui.run(p)))
    if len(chosen) >= 2:
        runs = [ui.run(p) for p in chosen]
        ref = runs[0]
        for other in runs[1:]:
            diff = results.differences(ref, other)
            if diff:
                st.warning(t("comparison.runs.differ", other=other.run_id, ref=ref.run_id, items=", ".join(diff)))
            else:
                st.success(t("comparison.runs.same", other=other.run_id, ref=ref.run_id))
        metric = ui.select(st, t("dashboard.comparison.metric"), ["coverage", "sinr_median_db", "rate_p5_mbps",
                                                                   "rate_median_mbps"], "cmp_metric",
                           format_func=lambda k: t(f"comparison.runs.metrics.{k}"))
        fig = go.Figure()
        for r in runs:
            rows = evidence.band_table(r)
            fig.add_scatter(x=[x["frequency_ghz"] for x in rows],
                            y=[None if x[metric] is None else (100 * x[metric] if metric == "coverage" else x[metric])
                               for x in rows], mode="lines+markers", name=ui.run_title(r)[:70])
        fig.update_layout(height=380, xaxis=dict(title=t("comparison.frequency_axis"), type="log"),
                          yaxis_title=t(f"comparison.runs.metrics.{metric}"), **LAYOUT)
        ui.chart(fig)

        # two runs side by side: a carrier of each (e.g. 5G 3.5 GHz and candidate 6G 8 GHz), one layer, one scale
        st.subheader(t("comparison.runs.maps_title"))
        a_run, b_run = runs[0], runs[1]

        def where(run):
            return sorted((round(s["x"], 1), round(s["y"], 1), round(s["z"], 1)) for s in run.sites_for(run.scenarios[0]["id"]))

        st.markdown(t("comparison.runs.sites_same" if where(a_run) == where(b_run) else "comparison.runs.sites_differ"))

        def carrier_label(sc):
            custom = f" → {sc['frequency_hz'] / 1e9:g} GHz / {sc['bandwidth_hz'] / 1e6:g} MHz" if sc.get("custom") else ""
            return ui.scenario_name({"id": sc.get("preset", sc["id"]), "label": sc["label"],
                                     "frequency_hz": sc.get("preset_frequency_hz", sc["frequency_hz"])}) + custom

        m1, m2, m3 = st.columns(3)
        sa = ui.select(m1, t("comparison.runs.band_a"), a_run.scenarios, "cmp-a", format_func=carrier_label)
        sb = ui.select(m2, t("comparison.runs.band_b"), b_run.scenarios, "cmp-b", format_func=carrier_label)
        shared = [k for k in ("sinr_db", "rx_power_dbm", "rate_bps", "interference_dbm", "path_gain_db")
                  if k in a_run.layers() and k in b_run.layers()]
        lay = ui.select(m3, t("common.layer"), shared, "cmp-layer", format_func=ui.layer_title)
        if a_run.manifest["grid"] != b_run.manifest["grid"]:
            st.warning(t("comparison.runs.grid_differs"))
        elif lay:
            from plotly.subplots import make_subplots

            unit, rng, _ = ui.LAYERS[lay]
            scale = 1e-6 if lay == "rate_bps" else 1.0
            za, zb = (np.where(r.outdoor, r.layer(sc["id"], lay) * scale, np.nan) for r, sc in ((a_run, sa), (b_run, sb)))
            if lay == "rate_bps":
                finite = np.concatenate([z[np.isfinite(z) & (z > 0)] for z in (za, zb)])
                rng, unit = (0.0, float(np.percentile(finite, 99)) if finite.size else 1.0), "Mbit/s"
            grid = a_run.grid
            # not shared_yaxes: a shared y axis ignores the second map's scaleanchor and stretches it
            fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.04,
                                subplot_titles=[carrier_label(sa), carrier_label(sb)])
            for k, z in enumerate((za, zb), start=1):
                fig.add_heatmap(x=grid.x_centers, y=grid.y_centers, z=np.where(np.isfinite(z), z, np.nan),
                                colorscale=ui.SEQ, zmin=rng[0], zmax=rng[1], showscale=k == 2, colorbar=dict(title=unit),
                                row=1, col=k, hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z:.1f} " + unit
                                + "<extra></extra>")
                fig.update_yaxes(scaleanchor=f"x{k if k > 1 else ''}", scaleratio=1, showticklabels=k == 1, row=1, col=k)
            half = grid.cell_size_m / 2                 # the same extent in both maps
            fig.update_xaxes(range=[grid.x_centers[0] - half, grid.x_centers[-1] + half], constrain="domain")
            fig.update_yaxes(range=[grid.y_centers[0] - half, grid.y_centers[-1] + half], constrain="domain")
            fig.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="#e9e8e3")
            fig.update_annotations(font_size=12)
            ui.chart(fig)
            rows = [{t(C + "scenario"): carrier_label(sc), "GHz": sc["frequency_hz"] / 1e9, "MHz": sc["bandwidth_hz"] / 1e6,
                     t(C + "coverage"): r1(run.scenario_summary(sc["id"]).get("coverage_fraction"), 100),
                     t(C + "sinr"): r1(run.scenario_summary(sc["id"]).get("sinr_db_median")),
                     t(C + "rate_p5"): r1((run.scenario_summary(sc["id"]).get("rate_p5_bps") or 0) / 1e6),
                     t(C + "rate_median"): r1((run.scenario_summary(sc["id"]).get("rate_median_bps") or 0) / 1e6, digits=0)}
                    for run, sc in ((a_run, sa), (b_run, sb))]
            st.dataframe(rows, hide_index=True, width="stretch")
            st.caption(t("common.candidate_6g_note") + " " + t("comparison.cdf_note"))
    else:
        st.info(t("comparison.runs.need_two"))

with tab_sites:
    plans = evidence.site_plans(ui.ROOT)
    if not plans:
        st.info(t("comparison.plans.none"))
    else:
        cases = sorted({(p["threshold_db"], p["load"], p["run"]) for p in plans})
        fig = go.Figure()
        for thr, load, rid in cases:
            sel = [p for p in plans if p["run"] == rid]
            fig.add_scatter(x=[p["frequency_ghz"] for p in sel], y=[p["sites"] for p in sel], mode="lines+markers",
                            name=t("comparison.plans.case", threshold=f"{thr:g}", load=f"{load:g}")
                            + (f" ({t('cls.sensitivity')})" if sel[0]["overrides"] else ""),
                            hovertext=[f"{ui.recorded(p['stopped_because'])}, {100 * (p['coverage'] or 0):.1f} %"
                                       for p in sel])
        fig.update_layout(height=380, title=t("comparison.plans.chart"),
                          xaxis=dict(title=t("comparison.frequency_axis"), type="log"),
                          yaxis=dict(title=t("comparison.network.sites_axis"), dtick=1), **LAYOUT)
        ui.chart(fig)
        P = "comparison.plans.columns."
        by_freq = {round(s["frequency_hz"] / 1e9, 3): ui.scenario_name(s) for s in ui.scenarios()}
        st.dataframe([{t(P + "band"): by_freq.get(round(p["frequency_ghz"], 3),
                                                  ui.band_name(p["scenario"], p["frequency_ghz"])),
                       t(P + "threshold"): p["threshold_db"], t(P + "load"): p["load"], t(P + "sites"): p["sites"],
                       t(P + "density"): round(p["site_density_per_km2"], 2), t(P + "coverage"): ui.fmt(p["coverage"], ".1%"),
                       t(P + "target"): ui.fmt(p["target"], ".0%"), t(P + "stop"): ui.recorded(p["stopped_because"]),
                       t(P + "candidates"): p["candidates"], t(P + "profile"): p["profile"], t(P + "backend"): p["backend"]}
                      for p in plans], hide_index=True)
        st.caption(t("comparison.plans.note"))

with tab_model:
    v = evidence.validation_summary(ui.ROOT)
    if v is None:
        st.info(t("comparison.model.none"))
    else:
        st.caption(t("comparison.model.caption", folder=v["folder"].name))
        names = {s["id"]: ui.scenario_name(s) for s in ui.scenarios()}
        fig = go.Figure()
        for model, dash in (("UMa", "solid"), ("UMi", "dash")):
            for cls, symbol in (("LOS", "circle"), ("NLOS", "square")):
                sel = [r for r in v["rows"] if r["model"] == model and r["class"] == cls]
                fig.add_scatter(x=[names[r["scenario_id"]] for r in sel], y=[r["rmse_db"] for r in sel],
                                mode="lines+markers", name=f"{model} {cls}", line=dict(dash=dash),
                                marker=dict(symbol=symbol))
        fig.update_layout(height=360, title=t("comparison.model.chart"), yaxis_title="dB", **LAYOUT)
        ui.chart(fig)
        st.dataframe([{**r, "scenario": names[r["scenario_id"]], "mean_error_db": round(r["mean_error_db"], 1),
                       "std_db": round(r["std_db"], 1), "rmse_db": round(r["rmse_db"], 1)} for r in v["rows"]],
                     hide_index=True)

with tab_sens:
    candidates = [ui.run(p) for p in ui.run_list() if (ui.run(p).path / "sensitivity.json").exists() and not ui.run(p).invalid]
    if not candidates:
        st.info(t("comparison.sens.none"))
    else:
        srun = candidates[0]
        data = json.loads((srun.path / "sensitivity.json").read_text(encoding="utf-8"))
        ui.result_banner(ui.label_classification(data["label"]))
        st.caption(t("comparison.sens.caption", run=srun.run_id, threshold=data["sourced"]["threshold"],
                     load=data["sourced"]["load"]))
        load = st.radio(t("comparison.sens.load"), data["loads"], horizontal=True)
        names = {s["id"]: ui.scenario_name(s) for s in srun.scenarios}
        fig = go.Figure()
        for sc in srun.scenarios:
            cs = [c for c in data["results"][sc["id"]] if c["load"] == load]
            fig.add_scatter(x=[c["threshold_db"] for c in cs], y=[100 * c["all_sites"]["coverage"] for c in cs],
                            mode="lines+markers", name=t("comparison.sens.all_sites", band=names[sc["id"]]),
                            line=dict(color=ui.colour(sc["id"])))
            fig.add_scatter(x=[c["threshold_db"] for c in cs], y=[100 * c["site_1_alone"]["coverage"] for c in cs],
                            mode="lines", name=t("comparison.sens.site_1", band=names[sc["id"]]),
                            line=dict(color=ui.colour(sc["id"]), dash="dot"), showlegend=False)
        fig.add_vline(x=-10, line_dash="dash", line_color="#888", annotation_text=t("comparison.sens.candidate_line"))
        fig.update_layout(height=380, title=t("comparison.sens.chart"), xaxis_title=t("comparison.sens.threshold_axis"),
                          yaxis_title=t(C + "coverage"), **LAYOUT)
        ui.chart(fig)
        with st.expander(t("comparison.sens.table")):
            ui.markdown_file(srun.path / "sensitivity.md")

with tab_lim:
    for key in ("heights", "validated", "shannon", "greedy", "validation_scope", "candidate_6g", "runs_compared"):
        st.markdown(f"- {t('limitations.general.' + key)}")
