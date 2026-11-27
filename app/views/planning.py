import plotly.graph_objects as go
import streamlit as st
import ui
from ui import t

from bns.app import planning

ui.page_header("planning.title", "planning.caption")
st.caption(t("planning.heuristic"))
run = ui.pick_run("planning-run", kinds=("site_plan", "multi_site"))
if run is None:
    st.stop()
ui.result_banner(run.classification)
st.caption(t("planning.new_plan"))
scen = run.scenarios
names = {s["id"]: ui.scenario_name(s) for s in scen}


def category(c: str) -> str:
    return t(f"common.height_category.{c}") if ui.tr().has(f"common.height_category.{c}") else c


if run.kind == "site_plan":
    m = run.manifest
    rule = m["candidate_rule"]
    position = (rule.get("antenna_position") or "interior")
    st.markdown(t("planning.saved_plan", run=run.run_id, candidates=t("common.candidates", count=len(run.sites)),
                  height=f"{rule['min_height_m']:g}", spacing=f"{rule['min_spacing_m']:g}",
                  categories=", ".join(category(c) for c in rule["height_categories"]),
                  mast=f"{rule['mast_height_m']:g}", position=t(f"planning.positions.{position}")
                  if ui.tr().has(f"planning.positions.{position}") else position.replace("_", " "),
                  objective=m["objective"], overrides=m.get("overrides_for_sensitivity") or t("common.none"),
                  trace=f"{m['timing']['trace_wall_seconds']:.0f}", selection=f"{m['timing']['selection_seconds']:.1f}",
                  backend=run.backend))
    P = "planning.columns."
    st.dataframe([{t(P + "scenario"): names.get(sid, sid), t(P + "selected"): ", ".join(r["selected"]),
                   t(P + "coverage_after"): ", ".join(f"{100 * v:.1f}%" for v in r["coverage_after"]),
                   t(P + "stop"): ui.recorded(r["stopped_because"]), t(P + "why"): r["stop_explanation"],
                   t(P + "uncovered"): r["uncovered_outdoor_cells"],
                   t(P + "all_on"): ui.fmt(r["all_candidates_reference"]["coverage_fraction"], ".1%"),
                   t(P + "degrading"): len(r["degrading_additions"])}
                  for sid, r in run.summary["results"].items()], hide_index=True)
    st.caption(t("planning.english_reasons"))
    hist = run.path / "selection_history.csv"
    if hist.exists():
        with st.expander(t("planning.history")):
            st.download_button("selection_history.csv", hist.read_bytes(), file_name="selection_history.csv")
    sid0 = st.radio(t("planning.final_map"), [s["id"] for s in scen], horizontal=True, key="plan-map",
                    format_func=lambda i: names[i])
    layer = st.radio(t("common.layer"), ["covered", "uncovered", "sinr_db", "serving_site"], horizontal=True,
                     format_func=lambda k: t(f"planning.layers.{k}"))
    z = run.layer(sid0, layer)
    if z is None:
        st.warning(t("coverage.no_site"))
    else:
        if layer == "uncovered":
            z, layer = (~z.astype(bool)).astype(float), "covered"
        ui.chart(ui.map_figure(run.grid, z, run.outdoor, layer=layer, sites=run.sites_for(sid0),
                                      azimuths=run.site_azimuths_rad(), height=560))
    st.divider()
    st.subheader(t("planning.reevaluate"))
sid = st.radio(t("common.scenario"), [s["id"] for s in scen], horizontal=True, format_func=lambda i: names[i])


@st.cache_resource(show_spinner=False, max_entries=10)
def stacks(path: str, scenario: str):
    return planning.load_stacks(ui.ROOT, ui.run(path), scenario)


try:
    with st.spinner(t("common.reading_cache")):
        s = stacks(str(run.path), sid)
except planning.PlanningError as exc:
    ui.error_box(exc)
    st.stop()
if s.config_changed:
    st.warning(t("planning.config_changed", items=", ".join(s.config_changed)))

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
st.markdown(t("planning.saved_greedy", target=f"{saved['target']:.0%}", sites=ui.ltr(", ".join(map(str, saved["selected_sites"]))),
              coverage=f"{saved['coverage_after'][-1]:.1%}", reason=ui.recorded(saved["stopped_because"])),
            unsafe_allow_html=True)

st.subheader(t("planning.try"))
st.caption(t("planning.try_note"))
labels = [t("planning.site_label", site=x["candidate_id"], building=x["building_id"], roof=f"{x['roof_height_m']:g}",
            category=category(x["height_category"])) for x in run.sites]
chosen = st.multiselect(t("planning.transmitting"), list(range(len(labels))), default=default_sel,
                        format_func=lambda i: labels[i])
c1, c2, c3 = st.columns(3)
activity = c1.slider(t("planning.activity"), 0.0, 1.0,
                     float(overrides.get("interference_activity", params.get("interference_activity", {}).get("value", 1.0))),
                     0.05, help=t("planning.activity_help"))
threshold = c2.slider(t("simulation.params.coverage_threshold"), -15.0, 10.0,
                      float(overrides.get("coverage_threshold", params.get("coverage_threshold", {}).get("value", -10.0))),
                      0.5, help=t("planning.threshold_help"))
target = c3.slider(t("planning.target"), 0.5, 1.0, float(saved["target"]), 0.01)
if chosen:
    net = planning.evaluate(s, tuple(chosen), interference_activity=activity, coverage_threshold=threshold)
    m = st.columns(4)
    m[0].metric(t("coverage.metrics.coverage"), f"{net.radio.summary['coverage_fraction']:.1%}")
    m[1].metric(t("coverage.metrics.sinr_median"), ui.fmt(net.radio.summary["sinr_db_median"], ".1f", " dB"))
    m[2].metric(t("coverage.metrics.rate_p5"), ui.fmt(net.radio.summary["rate_p5_bps"], ".1f", " Mbit/s", 1e-6))
    m[3].metric(t("coverage.metrics.interference_limited"), f"{net.summary['interference_limited_share']:.0%}")
    sites = [run.sites[i] for i in sorted(chosen)]
    ui.chart(ui.map_figure(run.grid, net.radio.sinr_db, run.outdoor, layer="sinr_db", sites=sites,
                                  azimuths=run.site_azimuths_rad(), height=520))

st.subheader(t("planning.greedy"))
g = planning.greedy(s, target, interference_activity=activity, coverage_threshold=threshold)
st.markdown(t("planning.greedy_result", sites=ui.ltr(", ".join(run.sites[i]["candidate_id"] for i in g.selected)),
              coverage=f"{g.coverage_after[-1]:.1%}",
              reached=t("planning.reached") if g.target_reached else t("planning.not_reached"),
              # the stop reason only when it adds something ("target reached; target reached" otherwise)
              reason="" if g.stopped_because == "target reached" else f" (*{ui.recorded(g.stopped_because)}*)"),
            unsafe_allow_html=True)
fig = go.Figure(go.Scatter(x=list(range(1, len(g.coverage_after) + 1)), y=[100 * v for v in g.coverage_after],
                           mode="lines+markers", line=dict(color=ui.colour(sid), width=2.5)))
fig.add_hline(y=100 * target, line_dash="dash", line_color="#888", annotation_text=t("planning.target"))
fig.update_layout(height=280, margin=dict(l=10, r=10, t=20, b=10),
                  xaxis=dict(title=t("planning.sites_selected"), dtick=1),
                  yaxis_title=t("comparison.columns.coverage"), plot_bgcolor="#fcfcfb")
ui.chart(fig)
st.dataframe([{t("planning.step"): e["step"], t("planning.coverage_before"): f"{e['before']:.1%}",
               **{run.sites[c]["candidate_id"]: f"{v:.1%}" for c, v in e["coverage_with"].items()}}
              for e in g.evaluations], hide_index=True)
if g.degrading_additions:
    st.warning(t("planning.degrading", items="; ".join(
        t("planning.degrading_item", step=d["step"], site=run.sites[d["candidate"]]["candidate_id"],
          change=f"{100 * d['change']:+.1f}") for d in g.degrading_additions)))
