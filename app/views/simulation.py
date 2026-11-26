import streamlit as st
import ui
import yaml

from bns.app import control
from bns.simulation import experiment as ex
from bns.simulation.cache import PathGainCache

ui.page_header("Run simulation", "Single- or multi-site coverage for all five scenarios. Runs in its own process; "
               "finished traces are cached, so a cancelled run resumes where it stopped.")

areas = ui.study_areas()
profiles = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))["profiles"]
usable = [k for k, v in profiles.items() if v.get("rays_per_site") is not None]


@st.cache_resource(show_spinner="Preparing the dataset...")
def experiment(area, variant, profile, mode, backend):
    return ex.load(ui.ROOT, area, variant, profile, mode, backend=backend)


@st.cache_resource(show_spinner="Checking for a GPU...")
def gpu_probe():
    from bns import runtime
    return runtime.probe_gpu()


gpu_ok, gpu_message = gpu_probe()
backends = yaml.safe_load((ui.ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8")).get("backends", {})


with st.form("run_form"):
    c1, c2, c3, c4 = st.columns(4)
    area = c1.selectbox("Area", list(areas), index=list(areas).index("tahrir_bab_al_sharqi_v2")
                        if "tahrir_bab_al_sharqi_v2" in areas else 0)
    variants = ui.variants(area) or ["osm"]
    variant = c2.selectbox("Dataset variant", variants, index=variants.index("osm") if "osm" in variants else 0)
    profile = c3.selectbox("Profile", usable, help="; ".join(f"{k}: {v.get('status', '')}" for k, v in profiles.items()),
                           format_func=lambda p: f"{p} — {profiles[p]['cell_size_m']} m, "
                           f"{float(profiles[p]['rays_per_site']):.0e} rays")
    mode = c4.selectbox("Mode", ["development", "research"],
                        help="Research mode refuses any unapproved parameter or dataset.")
    b1, b2 = st.columns([1, 3])
    backend = b1.selectbox("Ray-tracing backend", ["cpu", "auto", "gpu"] if gpu_ok else ["cpu", "auto"],
                           format_func=lambda b: {"cpu": "CPU (production)", "auto": "Auto (GPU if available)",
                                                  "gpu": "GPU"}[b],
                           help="CPU is the production backend. GPU is "
                                f"'{backends.get('gpu', {}).get('status', 'not configured')}': research runs refuse it. "
                                "CPU and GPU maps are cached separately.")
    b2.caption(gpu_message)
    rule = st.radio("Sites", ["tallest buildings with an observed height", "chosen buildings"], horizontal=True)
    d1, d2, d3 = st.columns(3)
    count = d1.number_input("Number of sites (1 = single site)", 1, 8, 4)
    min_height = d2.number_input("Minimum roof height [m]", 0.0, 100.0, 10.0, 1.0)
    spacing = d3.number_input("Minimum spacing [m]", 0.0, 500.0, 100.0, 10.0)
    chosen = st.text_input("Building ids, in order (for 'chosen buildings')", placeholder="way/919688856 way/645196998")
    estimate = st.form_submit_button("Check sites and workload", type="secondary")

request = {"area": area, "variant": variant, "profile": profile, "mode": mode, "backend": backend,
           "buildings": chosen.split() if rule == "chosen buildings" else [],
           "sites": int(count), "min_height_m": float(min_height), "min_spacing_m": float(spacing)}

if estimate or st.session_state.get("checked_request") == request:
    st.session_state["checked_request"] = request
    try:
        exp = experiment(area, variant, profile, mode, backend)
        placed = (ex.place_sites(exp, request["buildings"]) if request["buildings"] else
                  ex.observed_sites(exp, int(count), min_height_m=float(min_height), min_spacing_m=float(spacing)))
    except Exception as exc:
        st.error(f"This run cannot start: {exc}")
        st.stop()
    if not placed:
        st.warning("No building satisfies these site rules.")
        st.stop()
    ui.development_banner(exp.label)
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
             + (" ".join(req["buildings"]) if req["buildings"] else f"{req['sites']} site(s)"))
    with st.container(border=True):
        st.markdown(f"**{title}** · started {req['started_utc'][:19].replace('T', ' ')} UTC")
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
