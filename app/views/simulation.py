import json

import streamlit as st
import ui
import yaml
from ui import t

from bns.analysis import classification
from bns.app import control
from bns.simulation import experiment as ex
from bns.simulation.cache import PathGainCache

ui.page_header("simulation.title", "simulation.caption")
tr = ui.tr()

areas = ui.study_areas()
profiles = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))["profiles"]
usable = [k for k, v in profiles.items() if v.get("rays_per_site") is not None]
# parameter -> (step, number format) by group; labels are simulation.params.<parameter>,
# ranges come from bns.simulation.experiment.OVERRIDES
PARAMS = {
    "radio": {"tx_power_dbm": (1.0, "%.1f"), "mechanical_downtilt_deg": (1.0, "%.1f"), "sectors_per_site": (1, "%d"),
              "antenna_height_above_roof_m": (0.5, "%.1f"), "rx_height_m": (0.5, "%.1f"),
              "noise_figure_db": (0.5, "%.1f")},
    "coverage": {"coverage_threshold": (1.0, "%.1f"), "coverage_target": (0.01, "%.2f"),
                 "interference_activity": (0.05, "%.2f")},
    "resolution": {"cell_size_m": (1.0, "%.1f"), "rays_per_site": (10**8, "%d"), "rain_rate_mm_h": (1.0, "%.1f")},
    "candidates": {"min_roof_height_m": (1.0, "%.1f"), "min_roof_area_m2": (10.0, "%.1f"),
                   "min_spacing_m": (10.0, "%.1f")},
}


@st.cache_resource(show_spinner=False)
def experiment(area, variant, profile, backend, overrides_json):
    return ex.load(ui.ROOT, area, variant, profile, backend=backend, overrides=json.loads(overrides_json))


@st.cache_resource(show_spinner=False)
def gpu_probe():
    from bns import runtime
    return runtime.probe_gpu()


def area_label(a: str) -> str:
    key = f"study_area.names.{a}"
    name = t(key) if tr.has(key) else a
    return f"{name} ({t('common.area_role.' + areas[a]['role'])})"


with st.spinner(t("common.checking_gpu")):
    gpu_ok, gpu_message = gpu_probe()

c1, c2, c3 = st.columns(3)
study = [k for k, v in areas.items() if v.get("approved")]
area = c1.selectbox(t("simulation.area"), list(areas), index=list(areas).index(study[0]) if study else 0,
                    format_func=area_label, help=t("simulation.area_help"))
variants = ui.variants(area) or ["osm"]
variant = c2.selectbox(t("simulation.variant"), variants, index=ui.default_variant(area, variants),
                       format_func=ui.variant_name)
profile = c3.selectbox(t("simulation.profile"), usable, index=usable.index("standard") if "standard" in usable else 0,
                       help=t("simulation.profile_help"),
                       format_func=lambda p: t("simulation.profile_option", name=p, cell=f"{profiles[p]['cell_size_m']:g}",
                                               rays=f"{float(profiles[p]['rays_per_site']):.0e}"))
baseline = ex.baseline_values(ui.ROOT, profile)

if st.button(t("simulation.reset"), help=t("simulation.reset_help")):
    for k in [k for k in st.session_state if str(k).startswith("param-")]:
        del st.session_state[k]
    st.rerun()

with st.form("run_form"):
    b1, b2 = st.columns([1, 3])
    backend = b1.selectbox(t("simulation.backend"), ["cpu", "auto", "gpu"] if gpu_ok else ["cpu", "auto"],
                           format_func=lambda b: t(f"simulation.backends.{b}"), help=t("simulation.backend_help"))
    b2.caption(t("simulation.gpu_available") if gpu_ok else t("simulation.gpu_unavailable"),
               help=gpu_message)
    rule = st.radio(t("simulation.sites"), ["rule", "chosen"], horizontal=True,
                    format_func=lambda k: t(f"simulation.site_modes.{k}"))
    d1, d2 = st.columns([1, 3])
    count = d1.number_input(t("simulation.count"), 1, 8, 4)
    chosen = d2.text_input(t("simulation.chosen"), placeholder="way/919688856 way/645196998")
    values = {}
    with st.expander(t("simulation.parameters"), expanded=False):
        for group, params in PARAMS.items():
            st.markdown(f"**{t('simulation.groups.' + group)}**")
            cols = st.columns(3)
            for n, (k, (step, fmt)) in enumerate(params.items()):
                lo, hi = ex.OVERRIDES[k]
                integer = k in ex.INTEGER_OVERRIDES
                default = baseline.get(k)
                key = f"param-{k}-{profile}" if k in ("cell_size_m", "rays_per_site") else f"param-{k}"
                values[k] = cols[n % 3].number_input(
                    t(f"simulation.params.{k}"), min_value=int(lo) if integer else float(lo),
                    max_value=int(hi) if integer else float(hi),
                    value=(int(default) if integer else float(default)) if default is not None else None,
                    step=step, format=fmt, key=key,
                    help=t("simulation.baseline_value", value=f"{default:g}") if default is not None
                    else t("simulation.no_baseline"))
    estimate = st.form_submit_button(t("simulation.check"), type="secondary")

overrides = ex.differences(values, baseline)
if overrides:
    kind = classification.configuration_class(overrides)
    head = t("cls.custom") if kind == classification.CUSTOM else t("cls.sensitivity") \
        if kind == classification.SENSITIVITY else kind
    diffs = ", ".join(f"{t('simulation.params.' + k)} `{v:g}` ({t('simulation.baseline_short')} `{baseline[k]:g}`)"
                      for k, v in overrides.items())
    st.info(t("simulation.differs", kind=head, items=diffs))
else:
    st.success(t("simulation.baseline_values"))

request = {"area": area, "variant": variant, "profile": profile, "backend": backend,
           "buildings": chosen.split() if rule == "chosen" else [], "sites": int(count),
           "overrides": overrides}

if estimate or st.session_state.get("checked_request") == request:
    st.session_state["checked_request"] = request
    try:
        with st.spinner(t("common.preparing_dataset")):
            exp = experiment(area, variant, profile, backend, json.dumps(overrides, sort_keys=True))
        placed = ex.place_sites(exp, request["buildings"]) if request["buildings"] else ex.observed_sites(exp, int(count))
    except Exception as exc:
        ui.error_box(exc)
        st.stop()
    if not placed:
        r = exp.candidate_rule
        st.warning(t("simulation.no_candidates", height=f"{r['min_roof_height_m']:g}", area=f"{r['min_roof_area_m2']:g}",
                     spacing=f"{r['min_spacing_m']:g}",
                     categories=", ".join(t(f"common.height_category.{c}") if tr.has(f"common.height_category.{c}")
                                          else c for c in r["categories"])))
        st.stop()
    st.markdown(t("simulation.ready"))
    ui.result_banner(exp.classification)
    notes = ui.limitation_texts(ex.limitation_items(exp))
    if notes:
        st.warning(t("simulation.limitations") + "\n\n" + "\n".join(f"- {n}" for n in notes))
    st.markdown(t("simulation.backend_line", backend=exp.backend.upper()), help=exp.backend_note)
    col = "simulation.site_columns."
    st.dataframe([{t(col + "site"): s.candidate_id, t(col + "building"): s.building_id, t(col + "roof"): s.roof_height_m,
                   t(col + "category"): t("common.height_category." + ("synthetic" if s.height_category == "placeholder"
                                                                       and exp.quality.get("height_model") else s.height_category)),
                   t(col + "antenna"): s.z, "x [m]": round(s.x), "y [m]": round(s.y)}
                  for s in placed], hide_index=True, use_container_width=True)
    if any(s.height_category != "observed" for s in placed):
        st.caption(t("simulation.not_observed_site"))
    jobs = [j for js in ex.jobs_for(exp, placed).values() for _, j in js]
    work = ex.workload(jobs, PathGainCache(ui.ROOT / "data" / "cache" / "pathgain"), exp.profile.rays_per_site,
                       exp.profile.cell_size_m)
    w = st.columns(4)
    w[0].metric(t("simulation.work.jobs"), work["jobs"], help=t("simulation.work.jobs_help"))
    w[1].metric(t("simulation.work.cached"), work["cached"])
    w[2].metric(t("simulation.work.to_trace"), work["to_trace"])
    est = work["estimate"]
    w[3].metric(t("simulation.work.estimate"), "—" if est is None else t("simulation.work.minutes",
                                                                       value=f"{est['estimated_seconds'] / 60:.1f}"),
                help=None if est is None else t("simulation.work.estimate_help", median=est["median_seconds_per_job"],
                                                count=est["measurements"]))
    if est is None and work["to_trace"]:
        st.caption(t("simulation.work.no_estimate"))
    running = [f for f in control.history(ui.ROOT) if control.state(f).running]
    if running:
        st.info(t("simulation.already_running"))
    elif st.button(t("simulation.start"), type="primary"):
        st.session_state["active"] = str(control.start(ui.ROOT, request))
        st.rerun()

st.divider()
st.subheader(t("simulation.history.title"))
history = control.history(ui.ROOT)
if not history:
    st.caption(t("common.none_yet"))


def render(folder):
    s = control.state(folder)
    req = s.request
    sites = " ".join(req["buildings"]) if req["buildings"] else t("common.sites", count=req["sites"])
    config = (t("simulation.history.custom", values=ui.ltr(", ".join(f"{k}={v:g}" for k, v in req["overrides"].items())))
              if req.get("overrides") else (t("simulation.history.baseline_values") if "overrides" in req else ""))
    title = " · ".join(p for p in (ui.ltr(f"{req['area']}/{req['variant']}"), req["profile"],
                                   req.get("backend", "cpu").upper(), sites, config) if p)
    started = tr.date(req["started_utc"])
    with st.container(border=True):
        st.markdown(f"**{t('simulation.execution.' + s.execution.lower())}** · {title} · "
                    f"{t('simulation.history.started', date=started)}", unsafe_allow_html=True)
        if s.running:
            if s.progress:
                done, total = s.progress
                st.progress(min(done / max(total, 1), 1.0), text=t("simulation.history.traced", done=done, total=total))
            elif s.workload and s.workload["to_trace"] == 0:
                st.progress(1.0, text=t("simulation.history.all_cached"))
            else:
                st.progress(0.0, text=t("simulation.history.preparing"))
            if st.button(t("simulation.history.cancel"), key=f"cancel-{folder.name}"):
                control.cancel(folder)
                st.toast(t("simulation.history.cancelling"))
        elif st.session_state.get("active") == str(folder):
            st.session_state.pop("active")             # the run just ended: refresh the whole page once
            ui.run_list.clear()
            st.rerun()
        elif s.output:
            st.success(t("simulation.history.finished", name=s.output.name))
        elif s.cancelled:
            st.warning(t("simulation.history.cancelled"))
        else:
            st.error(t("simulation.history.failed"))
            with st.expander(t("common.technical_details")):
                st.code(s.error or t("simulation.history.no_result"), language="text")
        with st.expander(t("simulation.history.log")):
            st.code("\n".join(s.log_tail) or "(empty)", language="text")


live = st.fragment(run_every=2)(render)
for f in history[:5]:
    (live if control.state(f).running else render)(f)
