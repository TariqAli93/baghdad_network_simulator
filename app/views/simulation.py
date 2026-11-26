import json

import streamlit as st
import ui
import yaml

from bns.analysis import classification
from bns.app import control
from bns.simulation import experiment as ex
from bns.simulation.cache import PathGainCache

ui.page_header("Run simulation", "Single- or multi-site coverage for all five scenarios. Runs in its own process; "
               "finished traces are cached, so a cancelled run resumes where it stopped.")

areas = ui.study_areas()
profiles = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))["profiles"]
usable = [k for k, v in profiles.items() if v.get("rays_per_site") is not None]
# parameter -> (label, step, number format); ranges come from bns.simulation.experiment.OVERRIDES
PARAMS = {
    "Radio": {"tx_power_dbm": ("Transmit power [dBm, conducted]", 1.0, "%.1f"),
              "mechanical_downtilt_deg": ("Downtilt [deg]", 1.0, "%.1f"),
              "sectors_per_site": ("Sectors per site", 1, "%d"),
              "antenna_height_above_roof_m": ("Mast height above roof [m]", 0.5, "%.1f"),
              "rx_height_m": ("Receiver height [m]", 0.5, "%.1f"),
              "noise_figure_db": ("Noise figure [dB]", 0.5, "%.1f")},
    "Coverage and load": {"coverage_threshold": ("Coverage threshold, SINR [dB]", 1.0, "%.1f"),
                          "coverage_target": ("Coverage target [share of outdoor cells]", 0.01, "%.2f"),
                          "interference_activity": ("Network load (interference activity)", 0.05, "%.2f")},
    "Resolution and environment": {"cell_size_m": ("Cell size [m]", 1.0, "%.1f"),
                                   "rays_per_site": ("Rays per sector", 10**8, "%d"),
                                   "rain_rate_mm_h": ("Rain rate [mm/h] (0 = clear sky)", 1.0, "%.1f")},
    "Candidate sites": {"min_roof_height_m": ("Minimum roof height [m]", 1.0, "%.1f"),
                        "min_roof_area_m2": ("Minimum roof area [m²]", 10.0, "%.1f"),
                        "min_spacing_m": ("Minimum spacing [m]", 10.0, "%.1f")},
}


@st.cache_resource(show_spinner="Preparing the dataset...")
def experiment(area, variant, profile, backend, overrides_json):
    return ex.load(ui.ROOT, area, variant, profile, backend=backend, overrides=json.loads(overrides_json))


@st.cache_resource(show_spinner="Checking for a GPU...")
def gpu_probe():
    from bns import runtime
    return runtime.probe_gpu()


gpu_ok, gpu_message = gpu_probe()
backends = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8")).get("backends", {})

c1, c2, c3 = st.columns(3)
study = [k for k, v in areas.items() if v.get("approved")]
area = c1.selectbox("Area", list(areas), index=list(areas).index(study[0]) if study else 0,
                    format_func=lambda a: f"{a} ({areas[a]['role']})",
                    help="Every area with a built dataset can be simulated; only the study district can give "
                         "complete data. Other areas are for comparison and experimentation.")
variants = ui.variants(area) or ["osm"]
variant = c2.selectbox("Dataset variant", variants)
profile = c3.selectbox("Profile", usable, index=usable.index("standard") if "standard" in usable else 0,
                       help="Sets the baseline cell size and ray count below; "
                            + "; ".join(f"{k}: {v.get('status', '')}" for k, v in profiles.items()),
                       format_func=lambda p: f"{p} — {profiles[p]['cell_size_m']} m, "
                       f"{float(profiles[p]['rays_per_site']):.0e} rays")
baseline = ex.baseline_values(ui.ROOT, profile)

if st.button("Reset to research baseline", help="Restore every parameter below to the research-baseline values."):
    for k in [k for k in st.session_state if str(k).startswith("param-")]:
        del st.session_state[k]
    st.rerun()

with st.form("run_form"):
    b1, b2 = st.columns([1, 3])
    backend = b1.selectbox("Ray-tracing backend", ["cpu", "auto", "gpu"] if gpu_ok else ["cpu", "auto"],
                           format_func=lambda b: {"cpu": "CPU", "auto": "Auto (GPU if available)", "gpu": "GPU"}[b],
                           help="CPU is the research backend. GPU maps agree closely with CPU maps in most cells "
                                "but differed by up to 26 dB in single cells on a harder case (docs/validation.md "
                                "§7); they are cached separately.")
    b2.caption(gpu_message)
    rule = st.radio("Sites", ["candidate rooftops (site rule)", "chosen buildings"], horizontal=True)
    d1, d2 = st.columns([1, 3])
    count = d1.number_input("Number of sites (1 = single site)", 1, 8, 4)
    chosen = d2.text_input("Building ids, in order (for 'chosen buildings')", placeholder="way/919688856 way/645196998")
    values = {}
    with st.expander("Experiment parameters (research-baseline values unless you change them)", expanded=False):
        for group, params in PARAMS.items():
            st.markdown(f"**{group}**")
            cols = st.columns(3)
            for n, (k, (label, step, fmt)) in enumerate(params.items()):
                lo, hi = ex.OVERRIDES[k]
                integer = k in ex.INTEGER_OVERRIDES
                default = baseline.get(k)
                key = f"param-{k}-{profile}" if k in ("cell_size_m", "rays_per_site") else f"param-{k}"
                values[k] = cols[n % 3].number_input(
                    label, min_value=int(lo) if integer else float(lo), max_value=int(hi) if integer else float(hi),
                    value=(int(default) if integer else float(default)) if default is not None else None,
                    step=step, format=fmt, key=key,
                    help=f"Research baseline: {default:g}" if default is not None else "No baseline value")
    estimate = st.form_submit_button("Check sites and workload", type="secondary")

overrides = ex.differences(values, baseline)
if overrides:
    st.info(f"**{classification.configuration_class(overrides)}** — differs from the research baseline in: "
            + ", ".join(f"{k} {v:g} (baseline {baseline[k]:g})" for k, v in overrides.items())
            + ". The run records the values it used.")
else:
    st.success("**Research Baseline** values.")

request = {"area": area, "variant": variant, "profile": profile, "backend": backend,
           "buildings": chosen.split() if rule == "chosen buildings" else [], "sites": int(count),
           "overrides": overrides}

if estimate or st.session_state.get("checked_request") == request:
    st.session_state["checked_request"] = request
    try:
        exp = experiment(area, variant, profile, backend, json.dumps(overrides, sort_keys=True))
        placed = ex.place_sites(exp, request["buildings"]) if request["buildings"] else ex.observed_sites(exp, int(count))
    except Exception as exc:
        st.error(f"This run cannot start: {exc}")
        st.stop()
    if not placed:
        r = exp.candidate_rule
        st.warning(f"No rooftop satisfies the candidate rule (roof ≥ {r['min_roof_height_m']:g} m, "
                   f"≥ {r['min_roof_area_m2']:g} m², ≥ {r['min_spacing_m']:g} m apart, heights "
                   f"{', '.join(r['categories'])}). Choose buildings, or change the candidate criteria.")
        st.stop()
    st.markdown("**Execution:** Ready — the result will be classified as:")
    ui.result_banner(exp.classification)
    notes = ex.limitations(exp)
    if notes:
        st.warning("**Scientific limitations of this run** (they do not prevent it):\n\n"
                   + "\n".join(f"- {n}" for n in notes))
    st.markdown(f"**Backend:** {exp.backend.upper()} — {exp.backend_note}")
    st.dataframe([{"site": s.candidate_id, "building": s.building_id, "roof [m]": s.roof_height_m,
                   "roof height": s.height_category, "antenna [m]": s.z, "x [m]": round(s.x), "y [m]": round(s.y)}
                  for s in placed], hide_index=True, use_container_width=True)
    if any(s.height_category != "observed" for s in placed):
        st.warning("At least one site stands on a building whose height is not observed.")
    jobs = [j for js in ex.jobs_for(exp, placed).values() for _, j in js]
    work = ex.workload(jobs, PathGainCache(ui.ROOT / "data" / "cache" / "pathgain"), exp.profile.rays_per_site,
                       exp.profile.cell_size_m)
    w = st.columns(4)
    w[0].metric("Traces (sectors × sites × bands)", work["jobs"])
    w[1].metric("Already cached", work["cached"])
    w[2].metric("To trace", work["to_trace"])
    est = work["estimate"]
    w[3].metric("Estimated trace time", "—" if est is None else f"{est['estimated_seconds'] / 60:.1f} min",
                help=None if est is None else f"median {est['median_seconds_per_job']} s per trace over "
                f"{est['measurements']} measured traces with this profile and backend. {est['note']}")
    if est is None and work["to_trace"]:
        st.caption("No trace with this profile and backend has been measured on this PC yet, so there is no "
                   "time estimate.")
    running = [f for f in control.history(ui.ROOT) if control.state(f).running]
    if running:
        st.info("A run is already in progress; wait for it or cancel it below.")
    elif st.button("Start run", type="primary"):
        st.session_state["active"] = str(control.start(ui.ROOT, request))
        st.rerun()

st.divider()
st.subheader("Runs started here")
history = control.history(ui.ROOT)
if not history:
    st.caption("None yet.")


def render(folder):
    s = control.state(folder)
    req = s.request
    title = (f"{req['area']}/{req['variant']} · {req['profile']} · {req.get('backend', 'cpu').upper()} · "
             + (" ".join(req["buildings"]) if req["buildings"] else f"{req['sites']} site(s)")
             + (" · custom: " + ", ".join(f"{k}={v:g}" for k, v in req["overrides"].items())
                if req.get("overrides") else (" · research-baseline values" if "overrides" in req else "")))
    with st.container(border=True):
        st.markdown(f"**{s.execution}** · {title} · started {req['started_utc'][:19].replace('T', ' ')} UTC")
        if s.running:
            if s.progress:
                done, total = s.progress
                st.progress(min(done / max(total, 1), 1.0), text=f"traced {done} of {total}")
            elif s.workload and s.workload["to_trace"] == 0:
                st.progress(1.0, text="all traces cached; computing radio results")
            else:
                st.progress(0.0, text="preparing")
            if st.button("Cancel", key=f"cancel-{folder.name}"):
                control.cancel(folder)
                st.toast("Cancelling: the running worker stops; traces of finished batches stay cached.")
        elif st.session_state.get("active") == str(folder):
            st.session_state.pop("active")             # the run just ended: refresh the whole page once
            ui.run_list.clear()
            st.rerun()
        elif s.output:
            st.success(f"Finished: `{s.output.name}`. Open it on **Coverage analysis**.")
        elif s.cancelled:
            st.warning("Cancelled. Starting the same run again resumes from the cache.")
        else:
            st.error(f"Failed: {s.error or 'the process stopped without a result'}")
        with st.expander("Log"):
            st.code("\n".join(s.log_tail) or "(empty)", language="text")


live = st.fragment(run_every=2)(render)
for f in history[:5]:
    (live if control.state(f).running else render)(f)
