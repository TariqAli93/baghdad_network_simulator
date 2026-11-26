import plotly.graph_objects as go
import streamlit as st
import ui

from bns.app import planning

ui.page_header("Site planning", "SINR-based greedy selection over the sites of a saved multi-site run. Every "
               "evaluation includes the interference of all selected sectors; path gain is read from the cache, "
               "nothing is traced.")
st.caption("The greedy result is a heuristic over these candidates only, not a proven minimum. Adding a site can "
           "lower coverage; such additions are listed.")
run = ui.pick_run("planning-run", kinds=("site_plan", "multi_site"))
if run is None:
    st.stop()
ui.development_banner(run.label)
st.caption("Create a new plan with `uv run python scripts/plan_sites.py --area NAME --mode development "
           "[--backend gpu] [--threshold DB --load X]` (traces only what is not cached).")
scen = run.scenarios

if run.kind == "site_plan":
    m = run.manifest
    rule = m["candidate_rule"]
    st.markdown(f"**Saved plan** `{run.run_id}` — {len(run.sites)} candidates (roof ≥ {rule['min_height_m']:g} m, "
                f"≥ {rule['min_spacing_m']:g} m apart, heights {', '.join(rule['height_categories'])}; mast "
                f"{rule['mast_height_m']:g} m, antennas at the {(rule.get('antenna_position') or 'interior').replace('_', ' ')} of the roof); objective: {m['objective']}. Overrides: "
                f"{m.get('overrides_for_sensitivity') or 'none'}. Traces {m['timing']['trace_wall_seconds']:.0f} s, "
                f"selection {m['timing']['selection_seconds']:.1f} s ({run.backend}).")
    st.dataframe([{"scenario": next(s['label'] for s in scen if s['id'] == sid), "selected (in order)": ", ".join(r["selected"]),
                   "coverage after each": ", ".join(f"{100 * v:.1f}%" for v in r["coverage_after"]),
                   "stop": r["stopped_because"], "why": r["stop_explanation"],
                   "uncovered cells": r["uncovered_outdoor_cells"],
                   "all candidates on": ui.fmt(r["all_candidates_reference"]["coverage_fraction"], ".1%"),
                   "degrading additions seen": len(r["degrading_additions"])}
                  for sid, r in run.summary["results"].items()], hide_index=True, use_container_width=True)
    hist = run.path / "selection_history.csv"
    if hist.exists():
        with st.expander("Selection history (every candidate evaluated at every step)"):
            st.download_button("selection_history.csv", hist.read_bytes(), file_name="selection_history.csv")
    sid0 = st.radio("Final map for", [s["id"] for s in scen], horizontal=True, key="plan-map",
                    format_func=lambda i: next(s["label"] for s in scen if s["id"] == i))
    layer = st.radio("Layer", ["covered", "uncovered", "sinr_db", "serving_site"], horizontal=True,
                     format_func=lambda k: {"covered": "coverage", "uncovered": "uncovered areas", "sinr_db": "SINR",
                                            "serving_site": "serving site"}[k])
    z = run.layer(sid0, layer)
    if z is None:
        st.warning("No site selected for this scenario.")
    else:
        if layer == "uncovered":
            z, layer = (~z.astype(bool)).astype(float), "covered"
        st.plotly_chart(ui.map_figure(run.grid, z, run.outdoor, layer=layer, sites=run.sites_for(sid0),
                                      azimuths=run.sector_azimuths_rad, height=560), use_container_width=True)
    st.divider()
    st.subheader("Re-evaluate from the cache")
sid = st.radio("Scenario", [s["id"] for s in scen], horizontal=True,
               format_func=lambda i: next(s["label"] for s in scen if s["id"] == i))


@st.cache_resource(show_spinner="Reading cached path gain...", max_entries=10)
def stacks(path: str, scenario: str):
    return planning.load_stacks(ui.ROOT, ui.run(path), scenario)


try:
    s = stacks(str(run.path), sid)
except planning.PlanningError as exc:
    st.error(str(exc))
    st.stop()
if s.config_changed:
    st.warning("These radio parameters changed since the run; results below use the current files: "
               + ", ".join(s.config_changed))

r = run.summary["results"][sid]
overrides = run.manifest.get("overrides_for_sensitivity") or {}
params = run.manifest["radio_parameters"]
if run.kind == "site_plan":
    saved = {"target": r["target"], "selected_sites": r["selected"], "coverage_after": r["coverage_after"] or [0.0],
             "stopped_because": r["stopped_because"]}
    ids = [x["candidate_id"] for x in run.sites]
    default_sel = [ids.index(c) for c in r["selected"]]
else:
    saved = r["greedy_sinr"]
    default_sel = list(range(len(run.sites)))
st.markdown(f"**Saved greedy result** (target {saved['target']:.0%}): sites {saved['selected_sites']} → "
            f"{saved['coverage_after'][-1]:.1%}; stopped because *{saved['stopped_because']}*.")

st.subheader("Try a selection")
st.caption("Sliders change assumptions for a sensitivity check only; the research baseline is unchanged.")
labels = [f"{x['candidate_id']} · {x['building_id']} · roof {x['roof_height_m']:g} m ({x['height_category']})"
          for x in run.sites]
chosen = st.multiselect("Sites transmitting", list(range(len(labels))), default=default_sel,
                        format_func=lambda i: labels[i])
c1, c2, c3 = st.columns(3)
activity = c1.slider("Interference activity (load of non-serving sectors)", 0.0, 1.0,
                     float(overrides.get("interference_activity", params.get("interference_activity", {}).get("value", 1.0))),
                     0.05, help="1.0 = every other sector always transmits (candidate value, ITU-R M.2412 full buffer).")
threshold = c2.slider("Coverage threshold, SINR [dB]", -15.0, 10.0,
                      float(overrides.get("coverage_threshold", params.get("coverage_threshold", {}).get("value", -10.0))),
                      0.5, help="Candidate −10 dB (lowest SINR with a non-zero rate in the 3GPP mapping).")
target = c3.slider("Coverage target", 0.5, 1.0, float(saved["target"]), 0.01)
if chosen:
    net = planning.evaluate(s, tuple(chosen), interference_activity=activity, coverage_threshold=threshold)
    m = st.columns(4)
    m[0].metric("Coverage", f"{net.radio.summary['coverage_fraction']:.1%}")
    m[1].metric("Median SINR", ui.fmt(net.radio.summary["sinr_db_median"], ".1f", " dB"))
    m[2].metric("5th-pct rate", ui.fmt(net.radio.summary["rate_p5_bps"], ".1f", " Mbit/s", 1e-6))
    m[3].metric("Interference-limited cells", f"{net.summary['interference_limited_share']:.0%}")
    sites = [run.sites[i] for i in sorted(chosen)]
    st.plotly_chart(ui.map_figure(run.grid, net.radio.sinr_db, run.outdoor, layer="sinr_db", sites=sites,
                                  azimuths=run.sector_azimuths_rad, height=520), use_container_width=True)

st.subheader("Greedy selection with these settings")
g = planning.greedy(s, target, interference_activity=activity, coverage_threshold=threshold)
st.markdown(f"Selected {[run.sites[i]['candidate_id'] for i in g.selected]} → "
            f"{g.coverage_after[-1]:.1%}; target {'reached' if g.target_reached else 'not reached'} "
            f"(*{g.stopped_because}*).")
fig = go.Figure(go.Scatter(x=list(range(1, len(g.coverage_after) + 1)), y=[100 * v for v in g.coverage_after],
                           mode="lines+markers", line=dict(color=ui.colour(sid), width=2.5)))
fig.add_hline(y=100 * target, line_dash="dash", line_color="#888", annotation_text="target")
fig.update_layout(height=280, margin=dict(l=10, r=10, t=20, b=10), xaxis=dict(title="sites selected", dtick=1),
                  yaxis_title="coverage [%]", plot_bgcolor="#fcfcfb")
st.plotly_chart(fig, use_container_width=True)
st.dataframe([{"step": e["step"], "coverage before": f"{e['before']:.1%}",
               **{run.sites[c]["candidate_id"]: f"{v:.1%}" for c, v in e["coverage_with"].items()}}
              for e in g.evaluations], hide_index=True, use_container_width=True)
if g.degrading_additions:
    st.warning("Additions that would have lowered coverage: " + "; ".join(
        f"step {d['step']}: {run.sites[d['candidate']]['candidate_id']} ({100 * d['change']:+.1f} pt)"
        for d in g.degrading_additions))
