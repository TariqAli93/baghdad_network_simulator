import plotly.graph_objects as go
import streamlit as st
import ui
from ui import t

from bns import i18n
from bns.analysis import readiness
from bns.app import dashboard

tr = ui.tr()


@st.cache_data(show_spinner=False, ttl=20)
def facts(visited: tuple):
    return dashboard.build(ui.ROOT, set(visited))


@st.cache_data(show_spinner=False, ttl=60)
def indicators():
    return readiness.indicators(ui.ROOT)


d = facts(tuple(sorted(st.session_state.get("visited", set()))))

# ---------------------------------------------------------------- A. header
head, status = st.columns([4, 1])
with head:
    st.title(t("dashboard.title"))
    st.caption(t("dashboard.tagline"))
with status:
    if d.running is not None:
        chip = t("dashboard.status_running")
    elif d.latest is not None:
        chip = t("dashboard.status_idle_latest", date=tr.date(d.latest.manifest.get("created_utc", "")))
    else:
        chip = t("dashboard.status_none")
    st.markdown(f'<div style="margin-top:2.4rem"><span class="status-chip">{chip}</span></div>', unsafe_allow_html=True)


def duration(run) -> str:
    seconds = (run.manifest.get("timing") or {}).get("total_wall_seconds")
    if seconds is None:
        return "—"
    return t("dashboard.latest.seconds", value=seconds) if seconds < 120 else t("dashboard.latest.minutes",
                                                                                 value=seconds / 60)


def stations(run) -> str:
    n = len(run.sites)
    return t("common.candidates", count=n) if run.kind == "site_plan" else t("common.sites", count=n)


area_name = t(f"study_area.names.{d.area['name']}") if tr.has(f"study_area.names.{d.area['name']}") else d.area["name"]
size = d.area.get("receiver_area_m") or [0, 0]
size_text = f"{float(size[0]) / 1000:g} × {float(size[1]) / 1000:g} km"
ds = d.dataset

# ---------------------------------------------------------------- B. key metrics
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.card(t("dashboard.card.study_area"), area_name, t("dashboard.card.study_area_sub", size=ui.ltr(size_text)))
with c2:
    ui.card(t("dashboard.card.scenarios"), t("dashboard.card.scenarios_value"), t("dashboard.card.scenarios_sub"))
with c3:
    if not ds.get("available"):
        ui.card(t("dashboard.card.dataset"), t("dashboard.card.dataset_missing"), t("dashboard.card.dataset_missing_sub"))
    elif ds.get("synthetic_percent") is not None:
        ui.card(t("dashboard.card.dataset"), t("dashboard.card.dataset_synthetic", pct=ds["synthetic_percent"]),
                t("dashboard.card.dataset_synthetic_sub", buildings=ds["buildings"], documented=ds["documented"]))
    else:
        ui.card(t("dashboard.card.dataset"), t("dashboard.card.dataset_plain", documented=ds["documented"]),
                t("dashboard.card.dataset_plain_sub", buildings=ds["buildings"]))
with c4:
    if d.running is not None:
        progress = d.running.progress
        ui.card(t("dashboard.card.latest"), t("dashboard.card.latest_running"),
                t("simulation.history.traced", done=progress[0], total=progress[1]) if progress else
                t("simulation.history.preparing"))
    elif d.latest is not None:
        head_text, _ = i18n.classification_texts(tr, d.latest.classification)
        ui.card(t("dashboard.card.latest"), head_text,
                t("dashboard.card.latest_sub", stations=stations(d.latest), duration=duration(d.latest)))
    else:
        ui.card(t("dashboard.card.latest"), t("dashboard.card.latest_none"), t("dashboard.card.latest_none_sub"))

# ---------------------------------------------------------------- C. primary action
st.write("")
a1, a2, _ = st.columns([2, 2, 4])
if a1.button(t("dashboard.start"), type="primary"):
    st.switch_page("views/simulation.py")
if d.latest is not None and a2.button(t("dashboard.view_latest")):
    st.switch_page("views/coverage.py")

# ---------------------------------------------------------------- D. latest simulation
st.subheader(t("dashboard.latest.heading"))
if d.latest is None:
    st.info(t("dashboard.latest.empty"))
else:
    run = d.latest
    ui.result_banner(run.classification)
    run_area = run.manifest["area"]["name"]
    info = st.columns(4)
    info[0].markdown(f"**{t('dashboard.latest.area')}**  \n{area_name if run_area == d.area['name'] else run_area}")
    info[1].markdown(f"**{t('dashboard.latest.stations')}**  \n{stations(run)}")
    info[2].markdown(f"**{t('dashboard.latest.date')}**  \n{tr.date(run.manifest.get('created_utc', ''))}")
    info[3].markdown(f"**{t('dashboard.latest.duration')}**  \n{duration(run)}")

    def span(key, spec, unit, scale=1.0):
        r = dashboard.ranges(d.bands, key)
        if r is None:
            return "—"
        lo, hi = (v * scale for v in r)
        return f"{lo:{spec}}{unit}" if abs(hi - lo) < 1e-9 else f"{lo:{spec}} – {hi:{spec}}{unit}"

    m = st.columns(4)
    across = t("dashboard.latest.across")
    for col, label, value, tip in (
            (m[0], "coverage", span("coverage", ".1f", " %", 100), across),
            (m[1], "sinr", span("sinr_median_db", ".1f", " dB"), t("common.acronyms.sinr")),
            (m[2], "rate", span("rate_median_mbps", ".0f", " Mbit/s"), t("common.acronyms.shannon")),
            (m[3], "rate_p5", span("rate_p5_mbps", ".0f", " Mbit/s"), t("common.acronyms.shannon"))):
        with col:
            ui.card(t(f"dashboard.latest.{label}"), ui.ltr(value), across, tooltip=tip)
    if st.button(t("dashboard.latest.view_full")):
        st.switch_page("views/coverage.py")

# ---------------------------------------------------------------- E. network comparison
st.subheader(t("dashboard.comparison.heading"))
if not d.bands:
    st.info(t("dashboard.comparison.empty"))
else:
    st.caption(t("dashboard.comparison.subtitle"))
    names = {sc["id"]: ui.scenario_name(sc) for sc in d.scenarios}
    cols = "dashboard.comparison.columns."

    def r1(v, scale=1.0, digits=1):
        return None if v is None else round(v * scale, digits)

    st.dataframe([{t(cols + "scenario"): names.get(b["scenario_id"], b["scenario"]),
                   t(cols + "bandwidth"): b["bandwidth_mhz"],
                   t(cols + "coverage"): r1(b["coverage"], 100),
                   t(cols + "rx_power"): r1(b["rx_power_median_dbm"]),
                   t(cols + "sinr"): r1(b["sinr_median_db"]),
                   t(cols + "rate"): r1(b["rate_median_mbps"], digits=0),
                   t(cols + "rate_p5"): r1(b["rate_p5_mbps"], digits=0),
                   t(cols + "status"): t(f"common.scenario_status.{b['status']}")} for b in d.bands],
                 hide_index=True)
    metrics = ["coverage", "rx_power_median_dbm", "sinr_median_db", "rate_median_mbps"]
    metric = st.segmented_control(t("dashboard.comparison.metric"), metrics, default="coverage",
                                  format_func=lambda k: t(f"dashboard.comparison.metrics.{k}"), key="dash-metric") \
        or "coverage"
    ys = [None if b[metric] is None else (100 * b[metric] if metric == "coverage" else b[metric]) for b in d.bands]
    fig = go.Figure(go.Bar(x=[names.get(b["scenario_id"], b["scenario"]) for b in d.bands], y=ys,
                           marker_color=[ui.colour(b["scenario_id"]) for b in d.bands],
                           text=[None if y is None else f"{y:.1f}" for y in ys], textposition="outside"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      yaxis_title=t(f"dashboard.comparison.metrics.{metric}"))
    ui.chart(fig)
    st.caption(t("common.candidate_6g_note") + " " + t("common.units_note"))

# ---------------------------------------------------------------- F. scientific status
st.subheader(t("dashboard.status.heading"))
st.caption(t("dashboard.status.note"))
ind = {i.id: i for i in indicators()}
s1, s2 = st.columns(2)
with s1:
    st.markdown(f"**{t('dashboard.status.dataset')}**")
    if not ds.get("available"):
        st.markdown(t("dashboard.status.dataset_missing"))
    elif ds.get("synthetic_percent") is not None:
        st.markdown(t("dashboard.status.dataset_synthetic", pct=ds["synthetic_percent"], documented=ds["documented"]))
    else:
        st.markdown(t("dashboard.status.dataset_plain", documented=ds["documented"], buildings=ds["buildings"]))
    st.markdown(f"**{t('dashboard.status.configuration')}**")
    st.markdown(t("dashboard.status.configuration_baseline" if ind["configuration"].state == readiness.BASELINE
                  else "dashboard.status.configuration_custom"))
with s2:
    st.markdown(f"**{t('dashboard.status.validation')}**")
    done = ind["convergence"].state == readiness.COMPLETED and ind["matlab"].state == readiness.COMPLETED
    st.markdown(t("dashboard.status.validation_done" if done else "dashboard.status.validation_text"))
    st.markdown(f"**{t('dashboard.status.limitations')}**")
    for key in ("heights", "shannon", "candidate_6g"):
        st.markdown(f"- {t(f'limitations.general.{key}')}")
with st.expander(t("dashboard.status.details")):
    dc = "dashboard.status.detail_columns."
    st.dataframe([{t(dc + "item"): t(f"readiness.title.{i.id}"), t(dc + "state"): t(f"readiness.state.{i.state}"),
                   t(dc + "details"): i.detail} for i in indicators()], hide_index=True)

# ---------------------------------------------------------------- G. next step
st.subheader(t("dashboard.next.heading"))
step = d.next_step
target = {"progress": "views/simulation.py", "first_run": "views/simulation.py", "explore_coverage": "views/coverage.py",
          "compare": "views/comparison.py", "review_limitations": "views/validation.py", "report": "views/reports.py",
          "new_experiment": "views/simulation.py"}[step]
n1, n2 = st.columns([3, 1])
n1.markdown(t(f"dashboard.next.{step}"))
if n2.button(t(f"dashboard.next.button.{step}"), use_container_width=True, key="next-step"):
    st.switch_page(target)
