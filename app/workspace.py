"""Simulation workspace — prototype for review (Arabic / English).

    uv run streamlit run app/workspace.py            # ?lang=en for English

One screen: settings on the start side, the network map in the middle, results and the selected
object on the end side. Stations are placed, moved and edited on the map. Whatever changes a
propagation job key needs ray tracing (the Run buttons start scripts/trace_jobs.py in its own
process); everything else is recomputed at once from the path-gain cache (bns.app.workspace).
Results are only ever computed from the cache entries of exactly the stations shown.

The production application (app/main.py) is unchanged; this file is the prototype under review.
"""

import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import yaml
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui  # noqa: E402
from ui import t  # noqa: E402

from bns import i18n  # noqa: E402
from bns.app import results  # noqa: E402
from bns.app import workspace as ws  # noqa: E402
from bns.app import workspace_runs as wr  # noqa: E402
from bns.simulation import experiment as ex  # noqa: E402
from bns.simulation.cache import PathGainCache  # noqa: E402

st.set_page_config(page_title=t("workspace.title"), page_icon=":material/cell_tower:", layout="wide",
                   initial_sidebar_state="collapsed")
ui.inject_css()
st.markdown("""<style>
[data-testid="stMainBlockContainer"] {padding: 2.4rem 1rem .6rem 1rem; max-width: 100%;}
[data-testid="stSidebarCollapsedControl"] {display: none;}
.ws-h {font-size: .8rem; font-weight: 600; color: inherit; opacity: .8; margin: .55rem 0 .1rem;
       padding-bottom: .15rem; border-bottom: 1px solid rgba(128,128,128,.28);}
.ws-tag {font-size: .68rem; padding: .05rem .35rem; border-radius: 3px; margin-inline-start: .35rem; font-weight: 500;
         white-space: nowrap;}
.ws-tag.trace {background: rgba(201,140,40,.18); color: #8a5a12;}
.ws-tag.instant {background: rgba(40,140,90,.16); color: #1d6a43;}
.ws-state {display: flex; align-items: baseline; gap: .5rem; padding: .35rem .6rem; border-radius: 5px; font-size: .85rem;
           border-inline-start: 4px solid; margin: .1rem 0 .3rem;}
.ws-state.current {border-color: #1b7f5b; background: rgba(27,127,91,.09);}
.ws-state.stale {border-color: #b7791f; background: rgba(183,121,31,.11);}
.ws-state.running {border-color: #2a78d6; background: rgba(42,120,214,.09);}
.ws-state.empty {border-color: #8a897f; background: rgba(128,128,128,.08);}
.ws-class {font-size: .78rem; opacity: .85; margin-bottom: .25rem;}
table.ws-m {width: 100%; border-collapse: collapse; font-size: .84rem; font-variant-numeric: tabular-nums;}
table.ws-m td {padding: .18rem .3rem; border-bottom: 1px solid rgba(128,128,128,.18); vertical-align: top;}
table.ws-m td.v {text-align: end; white-space: nowrap; font-weight: 600;}
table.ws-m.stale td.v {opacity: .55; font-weight: 500;}
table.ws-m td.n {font-size: .72rem; opacity: .7;}
.ws-note {font-size: .74rem; opacity: .75; line-height: 1.35; margin-top: .15rem;}
.ws-obj {font-size: .84rem; line-height: 1.4;}
.ws-hyp {border-inline-start: 3px dashed #b7791f; padding-inline-start: .5rem; font-size: .8rem;}
[data-testid="stWidgetLabel"] p {font-size: .8rem;}
div[data-testid="stVerticalBlock"] {gap: .5rem;}
</style>""", unsafe_allow_html=True)

ROOT = ui.ROOT
SS = st.session_state
tr = ui.tr()
CACHE = PathGainCache(ROOT / "data" / "cache" / "pathgain")
SIM = yaml.safe_load((ROOT / "configs" / "simulation.yaml").read_text(encoding="utf-8"))
PROFILES = {k: v for k, v in SIM["profiles"].items() if v.get("rays_per_site") is not None}
MAP_LAYERS = ["none", "rx_power_dbm", "sinr_db", "covered", "rate_bps", "rate_3gpp_bps", "serving_station",
              "interference_dbm", "path_gain_db"]
CONTINUOUS = ("rx_power_dbm", "sinr_db", "rate_bps", "rate_3gpp_bps", "interference_dbm", "path_gain_db")
NO_PATH = -9999
HEIGHT_COLOURS = ["#f4efe2", "#e6d3aa", "#d3ad6c", "#b9823e", "#8d5a26", "#5c3818"]
PANEL_HEIGHT = 860


def h(key: str, tag: str | None = None, **values) -> None:
    """A compact section heading; `tag` says whether its controls need ray tracing or are instant."""
    badge = f'<span class="ws-tag {tag}">{t("workspace.tag." + tag)}</span>' if tag else ""
    st.markdown(f'<div class="ws-h">{t(key, **values)}{badge}</div>', unsafe_allow_html=True)


def band(sid: str) -> dict:
    return next(s for s in ui.scenarios() if s["id"] == sid)


def colour(station_id: str) -> str:
    return ui.SITE_COLOURS[(int(station_id[1:]) - 1) % len(ui.SITE_COLOURS)]


def category_name(c: str | None) -> str:
    return t(f"common.height_category.{c}") if c and tr.has(f"common.height_category.{c}") else (c or "—")


# ---------------------------------------------------------------- cached data
@st.cache_resource(show_spinner=False, max_entries=6)
def context(area: str, variant: str, profile: str, backend: str, overrides_json: str) -> ws.Context:
    exp = ex.load(ROOT, area, variant, profile, backend=backend, overrides=json.loads(overrides_json))
    return ws.Context.from_experiment(exp)


@st.cache_resource(show_spinner=False)
def _store() -> dict:
    return {}


def load(key: str):
    """A cache entry (path gain, manifest); valid entries are immutable, so hits are kept in memory."""
    store = _store()
    if key in store:
        return store[key]
    entry = CACHE.get(key)
    if entry is not None:
        if len(store) > 1500:
            store.pop(next(iter(store)))
        store[key] = entry
    return entry


class Presence:
    """PathGainCache.has with the memory of load()."""

    @staticmethod
    def has(key: str) -> bool:
        return key in _store() or load(key) is not None


@st.cache_resource(show_spinner=False, max_entries=60)
def evaluation(signature: str, _ctx, _stations, sid: str, _radio) -> ws.Evaluation:
    return ws.evaluate(_ctx, _stations, band(sid), _radio, load)


@st.cache_data(show_spinner=False, max_entries=6)
def building_payload(area: str, variant: str) -> dict:
    _, blds = ui.buildings(area, variant)
    out = {"id": [], "h": [], "cat": [], "rings": []}
    for b in blds:
        out["id"].append(b.building_id)
        out["h"].append(round(float(b.height.height_m), 1))
        out["cat"].append(ui.height_display_category(b))
        out["rings"].append([[int(round(v * 10)) for xy in list(r.coords)[:-1] for v in xy]
                             for r in (b.polygon.exterior, *b.polygon.interiors)])
    return out


@st.cache_data(show_spinner=False, ttl=60)
def saved_runs() -> list[str]:
    return [str(r.path) for r in results.list_runs(ROOT) if r.kind in ("multi_site", "site_plan") and not r.invalid]


@st.cache_data(show_spinner=False, ttl=300)
def seconds_per_trace(rays: int, cell: float, variant: str) -> float | None:
    measured = ex.measured_trace_seconds(CACHE, rays, cell, variant)
    return float(np.median(measured)) if measured else None


@st.cache_resource(show_spinner=False)
def gpu_probe():
    from bns import runtime
    return runtime.probe_gpu()


# ---------------------------------------------------------------- state
def baseline_profile_values(profile: str) -> dict:
    return ex.baseline_values(ROOT, profile)


def init_state() -> None:
    if "w_area" in SS:
        return
    areas = ui.study_areas()
    study = [k for k, v in areas.items() if v.get("approved")]
    SS.w_area = study[0] if study else next(iter(areas))
    variants = ui.variants(SS.w_area) or ["osm"]
    SS.w_variant = variants[ui.default_variant(SS.w_area, variants)]
    SS.w_profile, SS.w_backend = "standard", "cpu"
    base = baseline_profile_values("standard")
    SS.w_cell, SS.w_rays, SS.w_rx = base["cell_size_m"], base["rays_per_site"], base["rx_height_m"]
    SS.w_stations, SS.w_sel, SS.w_last, SS.w_msg, SS.w_seen = [], {}, {}, None, None
    SS.w_band, SS.w_layer, SS.w_fill, SS.w_cands = "nr_3500", "sinr_db", "plain", False
    SS.w_trace, SS.w_ref, SS.w_origin, SS.w_mode_req = None, None, None, None
    reset_template(base)
    reset_radio(base)
    # start on the newest saved run of the primary dataset (prefer a CPU, research-baseline one), so the
    # first screen shows real stations and real results from the cache
    candidates = [results.load_run(Path(p)) for p in saved_runs()]
    mine = [r for r in candidates if r.manifest["area"]["name"] == SS.w_area
            and r.manifest["area"].get("variant") == SS.w_variant and r.kind == "multi_site"]
    mine.sort(key=lambda r: (r.classification.configuration == "Research Baseline", r.backend == "cpu",
                             r.manifest.get("created_utc", "")), reverse=True)
    if mine:
        open_run(str(mine[0].path), quiet=True)


def reset_template(base: dict) -> None:
    SS.w_t_power, SS.w_t_sectors = float(base["tx_power_dbm"]), int(base["sectors_per_site"])
    SS.w_t_az, SS.w_t_tilt = 0.0, float(base["mechanical_downtilt_deg"])
    SS.w_t_mast, SS.w_t_hyp, SS.w_t_allow = float(base["antenna_height_above_roof_m"]), None, False


def reset_radio(base: dict) -> None:
    SS.w_r_thr, SS.w_r_load = float(base["coverage_threshold"]), float(base["interference_activity"])
    SS.w_r_nf, SS.w_r_rain = float(base["noise_figure_db"]), float(base["rain_rate_mm_h"])
    SS.w_r_target = float(base["coverage_target"])


def profile() -> str:
    return SS.get("w_profile") or "standard"


def backend() -> str:
    return SS.get("w_backend") or "cpu"


def base_profile() -> str:
    return "standard" if profile() == "custom" else profile()


def overrides() -> dict:
    """Grid- and profile-changing values that differ from the research baseline (they enter the job keys)."""
    base = baseline_profile_values(base_profile())
    values = {"rx_height_m": SS.w_rx}
    if profile() == "custom":
        values.update(cell_size_m=float(SS.w_cell), rays_per_site=int(SS.w_rays))
    return ex.differences(values, base)


def current_context() -> ws.Context:
    return context(SS.w_area, SS.w_variant, base_profile(), backend(), json.dumps(overrides(), sort_keys=True))


def template(ctx: ws.Context) -> ws.StationTemplate:
    return replace(ws.StationTemplate.baseline(ctx), tx_power_dbm=float(SS.w_t_power), sectors=int(SS.w_t_sectors),
                   azimuth_deg=float(SS.w_t_az), downtilt_deg=float(SS.w_t_tilt), mast_height_m=float(SS.w_t_mast),
                   hypothetical_height_m=SS.w_t_hyp, allow_hypothetical=bool(SS.w_t_allow))


def radio() -> ws.RadioSettings:
    return ws.RadioSettings(float(SS.w_r_thr), float(SS.w_r_load), float(SS.w_r_nf), float(SS.w_r_rain))


def message(level: str, text: str) -> None:
    SS.w_msg = (level, text)


def placement_text(err: ws.PlacementError) -> str:
    key = f"workspace.place_errors.{err.code}"
    return t(key, **err.values) if tr.has(key) else str(err)


def open_run(path: str, quiet: bool = False) -> None:
    """Load a saved run's settings and stations; its traces are reused from the cache."""
    run = results.load_run(Path(path))
    settings = ws.run_settings(run.manifest)
    SS.w_area, SS.w_variant, SS.w_backend = settings["area"], settings["variant"], settings["backend"]
    SS.w_profile = "custom" if "cell_size_m" in settings["overrides"] or "rays_per_site" in settings["overrides"] \
        else settings["profile"]
    base = baseline_profile_values(settings["profile"])
    SS.w_rx = float(settings["overrides"].get("rx_height_m", base["rx_height_m"]))
    SS.w_cell = float(settings["overrides"].get("cell_size_m", base["cell_size_m"]))
    SS.w_rays = int(settings["overrides"].get("rays_per_site", base["rays_per_site"]))
    try:
        ctx = current_context()
        stations, check = ws.stations_from_run(ctx, run.manifest, run.summary)
    except Exception as exc:                        # missing dataset, unreadable run
        message("error", t("workspace.messages.run_unreadable", run=run.run_id, error=str(exc)))
        return
    r = ws.run_radio(ctx, run.manifest)
    SS.w_r_thr, SS.w_r_load, SS.w_r_nf, SS.w_r_rain = (r.coverage_threshold, r.interference_activity,
                                                       r.noise_figure_db, r.rain_rate_mm_h)
    SS.w_stations, SS.w_sel, SS.w_last = stations, {}, {}
    SS.w_origin = {"run": run.run_id, **check}
    if not quiet or not check["exact"]:
        message("success" if check["exact"] else "warning",
                t("workspace.messages.run_loaded" if check["exact"] else "workspace.messages.run_partial",
                  run=run.run_id, identical=check["identical"], recorded=check["recorded"]))


# ---------------------------------------------------------------- map events
def handle(event: dict) -> None:
    if not event or event.get("n") == SS.w_seen:
        return
    SS.w_seen = event.get("n")
    try:
        ctx = current_context()
    except Exception as exc:                        # noqa: BLE001 - shown to the user
        message("error", str(exc))
        return
    kind, stations = event.get("type"), list(SS.w_stations)
    index = {s.station_id: i for i, s in enumerate(stations)}
    try:
        if kind == "place":
            s = ws.place(ctx, float(event["x"]), float(event["y"]), template(ctx), stations)
            SS.w_stations = stations + [s]
            SS.w_sel = {"kind": "station", "id": s.station_id}
            message("info", t(f"workspace.messages.placed_{s.mount}", station=s.station_id,
                              building=s.building_id or "", height=f"{s.antenna_height_m:g}"))
        elif kind == "move" and event.get("id") in index:
            i = index[event["id"]]
            stations[i] = ws.move(ctx, stations[i], float(event["x"]), float(event["y"]), template(ctx), stations)
            SS.w_stations, SS.w_sel = stations, {"kind": "station", "id": event["id"]}
        elif kind == "select_station":
            SS.w_sel = {"kind": "station", "id": event["id"]}
        elif kind == "select_building":
            SS.w_sel = {"kind": "building", "id": event["id"], "x": event["x"], "y": event["y"]}
        elif kind == "inspect":
            SS.w_sel = {"kind": "cell", "x": float(event["x"]), "y": float(event["y"])}
        elif kind == "delete" and event.get("id") in index:
            remove(event["id"])
        elif kind == "clear":
            SS.w_sel = {}
    except ws.PlacementError as err:
        message("warning", placement_text(err))


def on_map_event() -> None:
    handle((SS.get("w_map") or {}).get("event"))


def remove(station_id: str) -> None:
    SS.w_stations = [s for s in SS.w_stations if s.station_id != station_id]
    if SS.w_sel.get("id") == station_id:
        SS.w_sel = {}


def update_station(station_id: str, **changes) -> None:
    SS.w_stations = [replace(s, **changes) if s.station_id == station_id else s for s in SS.w_stations]


def on_dataset_change() -> None:
    variants = ui.variants(SS.w_area) or ["osm"]
    if SS.get("w_variant") not in variants:
        SS.w_variant = variants[ui.default_variant(SS.w_area, variants)]
    try:
        ctx = current_context()
    except Exception as exc:                        # noqa: BLE001
        message("error", str(exc))
        return
    if SS.w_stations and SS.get("w_stations_area") not in (None, SS.w_area):
        SS.w_stations = []                          # another area: its stations do not belong here
    kept, dropped = ws.rebind(ctx, SS.w_stations, template(ctx))
    SS.w_stations, SS.w_sel, SS.w_last = kept, {}, {}
    if dropped:
        message("warning", t("workspace.messages.dropped", stations=", ".join(dropped)))


def on_profile_change() -> None:
    base = baseline_profile_values(base_profile())
    if profile() != "custom":
        SS.w_cell, SS.w_rays = base["cell_size_m"], base["rays_per_site"]


def on_open_run() -> None:
    open_run(SS.w_run_pick)


def on_reset() -> None:
    base = baseline_profile_values("standard")
    reset_template(base)
    reset_radio(base)
    SS.w_profile, SS.w_backend, SS.w_rx = "standard", "cpu", base["rx_height_m"]


# ---------------------------------------------------------------- page
init_state()
if SS.get("w_area_seen") != SS.w_area:
    SS.w_stations_area = SS.w_area
    SS.w_area_seen = SS.w_area

top = st.columns([5, 1])
with top[0]:
    st.markdown(f"### {t('workspace.title')}")
    st.caption(t("workspace.caption"))
with top[1]:
    ui.language_switch()

try:
    with st.spinner(t("common.preparing_dataset")):
        ctx = current_context()
except Exception as exc:                            # noqa: BLE001 - a technical problem stops the page
    ui.error_box(exc)
    if backend() != "cpu":
        SS.w_backend = "cpu"
        st.button(t("workspace.back_to_cpu"))
    st.stop()

exp = ctx.exp
stations: list[ws.Station] = SS.w_stations
design_jobs = ws.jobs(ctx, stations)
status = ws.trace_status(design_jobs, Presence) if stations else {}
rad = radio()
active = wr.active(ROOT)
enabled = [s for s in stations if s.enabled]


def current_eval(sid: str) -> ws.Evaluation | None:
    """The evaluation of the shown stations in this band, or None if a trace is missing."""
    if not enabled or not status.get(sid) or not status[sid].complete:
        return None
    sig = json.dumps({"ctx": [SS.w_area, SS.w_variant, profile(), backend(), overrides()],
                      "stations": [asdict(s) for s in stations], "radio": asdict(rad), "band": sid}, sort_keys=True)
    e = evaluation(hashlib.sha256(sig.encode()).hexdigest(), ctx, stations, sid, rad)
    SS.w_last[sid] = {"eval": e, "grid": exp.grid, "outdoor": exp.outdoor}
    return e


evals = {sc["id"]: current_eval(sc["id"]) for sc in exp.scenarios}
sid = SS.get("w_band") or exp.scenarios[0]["id"]
shown = evals.get(sid)
previous = SS.w_last.get(sid) if shown is None else None
stale = shown is None and previous is not None

left, centre, right = st.columns([1.05, 3.1, 1.35], gap="small")

# ================================================================ settings (start side)
with left, st.container(height=PANEL_HEIGHT, border=False):
    areas = ui.study_areas()
    h("workspace.settings.dataset", "trace")
    st.selectbox(t("simulation.area"), list(areas), key="w_area", on_change=on_dataset_change,
                 format_func=lambda a: t(f"study_area.names.{a}") if tr.has(f"study_area.names.{a}") else a)
    st.selectbox(t("simulation.variant"), ui.variants(SS.w_area) or ["osm"], key="w_variant",
                 on_change=on_dataset_change, format_func=ui.variant_name)
    q = exp.quality or {}
    syn = ((q.get("height_model") or {}).get("synthetic") or {}).get("synthetic_percent")
    if syn is not None:
        st.markdown(f'<div class="ws-note">{t("workspace.settings.synthetic_note", pct=f"{syn:.0f}")}</div>',
                    unsafe_allow_html=True)

    sc = band(sid)
    h("workspace.settings.scenario")
    st.markdown(f'<div class="ws-obj"><b>{ui.scenario_name(sc)}</b> · {ui.scenario_status(sc)}<br>'
                + t("workspace.settings.carrier", f=ui.ltr(f"{sc['frequency_hz'] / 1e9:g} GHz"),
                    b=ui.ltr(f"{sc['bandwidth_hz'] / 1e6:g} MHz")) + "</div>", unsafe_allow_html=True)
    note = t("workspace.settings.carrier_note") + (" " + t("common.candidate_6g_note") if sid.startswith("c6g") else "")
    st.markdown(f'<div class="ws-note">{note}</div>', unsafe_allow_html=True)

    h("workspace.settings.new_station", "trace")
    c1, c2 = st.columns(2)
    c1.number_input(t("workspace.fields.mast"), 0.0, 30.0, step=0.5, key="w_t_mast", format="%.1f")
    c2.number_input(t("workspace.fields.sectors"), 1, 6, step=1, key="w_t_sectors")
    c1.number_input(t("workspace.fields.azimuth"), 0.0, 359.9, step=5.0, key="w_t_az", format="%.1f",
                    help=t("workspace.fields.azimuth_help"))
    c2.number_input(t("workspace.fields.downtilt"), -10.0, 30.0, step=1.0, key="w_t_tilt", format="%.1f")
    st.toggle(t("workspace.fields.allow_hypothetical"), key="w_t_allow", help=t("workspace.fields.allow_help"))
    if SS.w_t_allow:
        st.number_input(t("workspace.fields.hyp_height"), min_value=1.0, max_value=300.0, step=1.0,
                        key="w_t_hyp", placeholder=t("workspace.fields.hyp_placeholder"))
    h("workspace.settings.new_station_radio", "instant")
    st.number_input(t("workspace.fields.power"), 0.0, 60.0, step=1.0, key="w_t_power", format="%.1f")
    if st.button(t("workspace.settings.apply_all"), disabled=not stations, width="stretch"):
        tp = template(ctx)
        SS.w_stations = [replace(s, tx_power_dbm=tp.tx_power_dbm, sectors=tp.sectors, azimuth_deg=tp.azimuth_deg,
                                 downtilt_deg=tp.downtilt_deg,
                                 antenna_height_m=(s.roof_height_m + tp.mast_height_m) if s.mount == ws.ROOFTOP
                                 else s.antenna_height_m) for s in stations]
        st.rerun()

    h("workspace.settings.receivers", "trace")
    st.number_input(t("workspace.fields.rx_height"), 0.5, 10.0, step=0.5, key="w_rx", format="%.1f")
    h("workspace.settings.radio", "instant")
    st.slider(t("workspace.fields.load"), 0.0, 1.0, step=0.05, key="w_r_load", help=t("planning.activity_help"))
    st.number_input(t("workspace.fields.threshold"), -20.0, 40.0, step=1.0, key="w_r_thr", format="%.1f",
                    help=t("workspace.fields.threshold_help"))

    h("workspace.settings.resolution", "trace")
    st.segmented_control(t("workspace.fields.profile"), ["preview", "standard", "custom"], key="w_profile",
                         on_change=on_profile_change, format_func=lambda p: t(f"workspace.profiles.{p}"))
    if profile() == "custom":
        c1, c2 = st.columns(2)
        c1.number_input(t("simulation.params.cell_size_m"), 2.0, 50.0, step=1.0, key="w_cell", format="%.1f")
        c2.number_input(t("simulation.params.rays_per_site"), int(1e6), int(1e10), step=int(1e8), key="w_rays")
    per = seconds_per_trace(exp.profile.rays_per_site, exp.profile.cell_size_m, ctx.engine["variant"])
    st.markdown('<div class="ws-note">' + t(
        "workspace.settings.profile_facts", cell=ui.ltr(f"{exp.profile.cell_size_m:g} m"),
        rays=ui.ltr(f"{exp.profile.rays_per_site:.0e}"), cells=int(exp.outdoor.sum()),
        status=t(f"workspace.profile_status.{profile()}"))
        + (" " + t("workspace.settings.per_trace", s=f"{per:.0f}") if per else " " + t("workspace.settings.no_timing"))
        + "</div>", unsafe_allow_html=True)
    backends = ["cpu", "gpu"]
    st.segmented_control(t("simulation.backend"), backends, key="w_backend",
                         format_func=lambda b: t(f"simulation.backends.{b}"), help=t("simulation.backend_help"))

    with st.expander(t("workspace.settings.advanced")):
        st.number_input(t("simulation.params.noise_figure_db"), 0.0, 20.0, step=0.5, key="w_r_nf", format="%.1f")
        st.number_input(t("simulation.params.rain_rate_mm_h"), 0.0, 200.0, step=1.0, key="w_r_rain", format="%.1f",
                        help=t("workspace.fields.rain_help"))
        m = exp.config.mechanisms
        st.markdown('<div class="ws-note">' + t(
            "workspace.settings.mechanisms", depth=m.max_depth,
            refl=t("workspace.yes") if m.specular_reflection else t("workspace.no"),
            diff=t("workspace.yes") if m.diffraction else t("workspace.no")) + "</div>", unsafe_allow_html=True)
        rule = exp.candidate_rule
        st.markdown('<div class="ws-note">' + t(
            "workspace.settings.site_rule", height=f"{rule['min_roof_height_m']:g}", area=f"{rule['min_roof_area_m2']:g}",
            spacing=f"{rule['min_spacing_m']:g}", position=t(f"planning.positions.{exp.site_rule.get('antenna_position')}")
            if tr.has(f"planning.positions.{exp.site_rule.get('antenna_position')}") else exp.site_rule.get("antenna_position"))
            + "</div>", unsafe_allow_html=True)
        st.button(t("simulation.reset"), width="stretch", on_click=on_reset)

    h("workspace.settings.stations")
    candidates = ws.rule_candidates(ctx)
    c1, c2 = st.columns([1, 1.4])
    n = c1.number_input(t("workspace.fields.rule_count"), 1, max(len(candidates), 1), min(4, max(len(candidates), 1)),
                        key="w_rule_n", label_visibility="collapsed")
    if c2.button(t("workspace.settings.rule_roofs", n=len(candidates)), disabled=not candidates,
                 width="stretch", help=t("workspace.settings.rule_roofs_help")):
        tp = template(ctx)
        SS.w_stations = [ws.from_candidate(ctx, c, tp, f"S{i + 1}") for i, c in enumerate(candidates[:int(n)])]
        SS.w_sel, SS.w_origin = {}, None
        st.rerun()
    runs = [p for p in saved_runs() if ui.run(p).manifest["area"]["name"] == SS.w_area]
    if runs:
        st.selectbox(t("workspace.settings.saved_run"), runs, key="w_run_pick", format_func=lambda p: ui.run_title(ui.run(p)))
        st.button(t("workspace.settings.open_run"), width="stretch", on_click=on_open_run)
    if st.button(t("workspace.settings.clear"), disabled=not stations, width="stretch"):
        SS.w_stations, SS.w_sel, SS.w_origin = [], {}, None
        st.rerun()

# ================================================================ map (centre)
with centre:
    st.segmented_control(t("common.scenario"), [s["id"] for s in exp.scenarios], key="w_band", width="stretch",
                         format_func=lambda i: ui.scenario_name(band(i)), label_visibility="collapsed")
    r2, r3, r4 = st.columns([1.4, 1.2, 1.6], vertical_alignment="center")
    r2.selectbox(t("common.layer"), MAP_LAYERS, key="w_layer", label_visibility="collapsed",
                 format_func=lambda k: t(f"workspace.layers.{k}"))
    r3.selectbox(t("workspace.fields.buildings"), ["plain", "height", "category"], key="w_fill",
                 label_visibility="collapsed", format_func=lambda k: t(f"workspace.building_fill.{k}"))

    r4.toggle(t("workspace.fields.show_candidates", n=len(candidates)), key="w_cands")
    layer = SS.w_layer
    source = shown if shown is not None else (previous or {}).get("eval")
    raster = None
    rate_max = None
    if layer in ("rate_bps", "rate_3gpp_bps"):
        tops = [float(np.percentile(e.layers[layer][exp.outdoor & (e.layers[layer] > 0)], 99))
                for e in evals.values() if e is not None and layer in e.layers and (e.layers[layer][exp.outdoor] > 0).any()]
        rate_max = max(tops) / 1e6 if tops else None
    if layer != "none" and source is not None and layer in source.layers:
        grid = exp.grid if shown is not None else previous["grid"]
        outdoor = exp.outdoor if shown is not None else previous["outdoor"]
        z = source.layers[layer]
        spec = {"x0": float(grid.x_centers[0]), "y0": float(grid.y_centers[0]), "dx": float(grid.cell_size_m),
                "nx": int(z.shape[1]), "ny": int(z.shape[0]), "stale": stale, "title": t(f"workspace.layers.{layer}"),
                "no_path_color": "#cfccc2"}
        if layer == "covered":
            vals = np.where(outdoor, z.astype(float), np.nan)
            spec.update(kind="cat", cat_colors=["#f2c7b8", "#256abf"],
                        ticktext=[t("coverage.map.not_covered"), t("coverage.map.covered")], unit="")
        elif layer == "serving_station":
            vals = np.where(outdoor, np.where(z >= 0, z, NO_PATH), np.nan).astype(float)
            spec.update(kind="cat", cat_colors=[colour(i) for i in source.station_ids], ticktext=source.station_ids,
                        unit="")
        else:
            unit, rng, _ = ui.LAYERS[layer]
            vals = z.astype(float)
            if layer in ("rate_bps", "rate_3gpp_bps"):
                vals = vals / 1e6
                rng = (0.0, rate_max or float(np.nanmax(np.where(np.isfinite(vals), vals, np.nan))))
                unit = "Mbit/s"
            vals = np.where(outdoor, np.where(np.isfinite(vals), vals, NO_PATH), np.nan)
            spec.update(kind="seq", colors=[c for _, c in ui.SEQ], vmin=float(rng[0]), vmax=float(rng[1]), unit=unit,
                        decimals=0 if layer in ("rate_bps", "rate_3gpp_bps") else 1,
                        below_note=t("workspace.legend.clamped"))
        flat = np.round(vals, 2).ravel()
        spec["values"] = [None if np.isnan(v) else (int(v) if spec["kind"] == "cat" else float(v)) for v in flat]
        raster = spec
    raster_rev = hashlib.sha256(json.dumps([source.job_keys if source else None, asdict(rad), layer, stale, sid,
                                            rate_max, SS.lang], default=str).encode()).hexdigest()[:16]

    heights = [b.height.height_m for b in exp.buildings]
    sel = dict(SS.w_sel)
    pos_cache = {s.station_id: ws.sector_positions(ctx, s, ws.antennas(s, exp.config.polarization)) for s in stations}
    station_items = [{
        "id": s.station_id, "label": s.station_id + ("" if s.enabled else f" ({t('workspace.off')})"),
        "x": s.x, "y": s.y, "mount": s.mount, "enabled": s.enabled, "colour": colour(s.station_id),
        "bearings": list(s.bearings_deg), "sectors_xy": [[p[0], p[1]] for p in pos_cache[s.station_id]][:len(s.bearings_deg)],
        "hover": t(f"workspace.hover_{s.mount}", station=s.station_id, building=s.building_id or "",
                   height=f"{s.antenna_height_m:g}", power=f"{s.tx_power_dbm:g}")} for s in stations]
    mode_hint = "hint_place_hyp" if SS.w_t_allow else "hint_place"
    texts = {k: t(f"workspace.map.{k}") for k in ("select", "place", "move", "measure", "fit", "tip_select", "tip_place",
                                                   "tip_move", "tip_measure", "tip_fit", "hint_select", "hint_move",
                                                   "hint_measure", "stale_short", "no_path", "indoor")}
    texts["hint_place"] = t(f"workspace.map.{mode_hint}")
    texts["stale"] = t("workspace.map.stale")
    data = {
        "geometry_rev": f"{SS.w_area}/{SS.w_variant}", "buildings": building_payload(SS.w_area, SS.w_variant),
        "bounds": list(exp.area.clip_box().bounds), "receiver": list(exp.area.receiver_box().bounds),
        "building_fill": SS.w_fill, "raster": raster, "raster_rev": raster_rev,
        "height_scale": {"vmin": 0.0, "vmax": float(np.percentile(heights, 99)) if heights else 1.0,
                         "colors": HEIGHT_COLOURS, "title": t("workspace.legend.height")},
        "category_colors": ui.CATEGORY_COLOURS, "category_title": t("workspace.legend.category"),
        "category_labels": {k: category_name(k) for k in ui.CATEGORY_COLOURS},
        "candidates": [{"x": c.x, "y": c.y} for c in candidates] if SS.w_cands else [],
        "stations": station_items, "selected": sel, "texts": texts, "rtl": tr.rtl, "height": 720,
        "mode_request": SS.w_mode_req,
        "legend_note": t("workspace.legend.wedges") if stations and raster is None else "",
    }
    MAP = st.components.v2.component(
        "bns_network_map", js=(Path(__file__).parent / "components" / "network_map.js").read_text(encoding="utf-8"),
        css=(Path(__file__).parent / "components" / "network_map.css").read_text(encoding="utf-8"))
    result = MAP(data=data, key="w_map", on_event_change=on_map_event, height=720)
    if result is not None and result.get("event") and result["event"].get("n") != SS.w_seen:
        handle(result["event"])                     # the callback did not see it: apply and redraw
        st.rerun()

    if SS.w_msg:
        level, text = SS.w_msg
        getattr(st, {"success": "success", "warning": "warning", "error": "error"}.get(level, "info"))(text)
        SS.w_msg = None

    # ------------------------------------------------------------ comparison (same layer, same scale)
    with st.expander(t("workspace.compare.title"), expanded=False):
        tab_bands, tab_configs = st.tabs([t("workspace.compare.bands"), t("workspace.compare.configs")])
        with tab_bands:
            ready = {k: e for k, e in evals.items() if e is not None}
            if not ready:
                st.caption(t("workspace.compare.none"))
            else:
                cl = layer if layer in CONTINUOUS else "sinr_db"
                order = [s["id"] for s in exp.scenarios if s["id"] in ready]
                fig = make_subplots(rows=1, cols=len(order), shared_yaxes=True, horizontal_spacing=0.01,
                                    subplot_titles=[f"{band(k)['frequency_hz'] / 1e9:g} GHz" for k in order])
                unit, rng, _ = ui.LAYERS[cl]
                scale = 1e-6 if cl in ("rate_bps", "rate_3gpp_bps") else 1.0
                if cl in ("rate_bps", "rate_3gpp_bps"):
                    rng, unit = (0.0, rate_max or 1.0), "Mbit/s"
                for k, key in enumerate(order, start=1):
                    zz = np.where(exp.outdoor, ready[key].layers[cl] * scale, np.nan)
                    fig.add_heatmap(x=exp.grid.x_centers, y=exp.grid.y_centers, z=np.where(np.isfinite(zz), zz, np.nan),
                                    colorscale=ui.SEQ, zmin=rng[0], zmax=rng[1], showscale=k == len(order),
                                    colorbar=dict(title=unit), row=1, col=k,
                                    hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z:.1f} " + unit + "<extra></extra>")
                    fig.update_xaxes(showticklabels=False, row=1, col=k)
                    fig.update_yaxes(showticklabels=False, scaleanchor=f"x{k if k > 1 else ''}", row=1, col=k)
                fig.update_layout(height=260, margin=dict(l=4, r=4, t=30, b=4), plot_bgcolor="#e9e8e3")
                fig.update_annotations(font_size=12)
                ui.chart(fig)
                st.caption(t("workspace.compare.same_scale", layer=t(f"workspace.layers.{cl}")))
                rows = []
                for key in [s["id"] for s in exp.scenarios]:
                    e = evals.get(key)
                    s_ = e.summary if e else {}
                    rows.append({t("common.scenario"): ui.scenario_name(band(key)),
                                 t("coverage.metrics.coverage"): None if not e else round(100 * s_["coverage_fraction"], 1),
                                 t("workspace.metrics.rx_median"): None if not e else ui.fmt(s_["rx_power_dbm_median"], ".1f"),
                                 t("coverage.metrics.sinr_median"): None if not e else ui.fmt(s_["sinr_db_median"], ".1f"),
                                 t("workspace.metrics.rate_median"): None if not e else ui.fmt(s_["rate_median_bps"], ".0f", "", 1e-6),
                                 t("workspace.metrics.rate_p5"): None if not e else ui.fmt(s_["rate_p5_bps"], ".1f", "", 1e-6),
                                 t("workspace.metrics.mapped_p5"): None if not e or s_.get("rate_3gpp_p5_bps") is None
                                 else ui.fmt(s_["rate_3gpp_p5_bps"], ".1f", "", 1e-6),
                                 t("workspace.compare.state"): t("workspace.state.current") if e else
                                 t("workspace.compare.needs", n=status[key].missing if key in status else 0)})
                st.dataframe(rows, hide_index=True, width="stretch")
                st.caption(t("workspace.compare.rates_note"))
        with tab_configs:
            st.caption(t("workspace.compare.configs_note"))
            if st.button(t("workspace.compare.pin"), disabled=not any(evals.values())):
                SS.w_ref = {"label": t("workspace.compare.reference_label", n=len(enabled)),
                            "grid": exp.grid, "evals": {k: e for k, e in evals.items() if e is not None},
                            "stations": [s.station_id for s in enabled]}
                st.rerun()
            ref = SS.w_ref
            if ref:
                rows = []
                for key in [s["id"] for s in exp.scenarios]:
                    a, b = ref["evals"].get(key), evals.get(key)
                    if a is None or b is None:
                        continue
                    rows.append({t("common.scenario"): ui.scenario_name(band(key)),
                                 t("workspace.compare.cov_ref"): round(100 * a.summary["coverage_fraction"], 1),
                                 t("workspace.compare.cov_now"): round(100 * b.summary["coverage_fraction"], 1),
                                 t("workspace.compare.sinr_ref"): ui.fmt(a.summary["sinr_db_median"], ".1f"),
                                 t("workspace.compare.sinr_now"): ui.fmt(b.summary["sinr_db_median"], ".1f"),
                                 t("workspace.compare.p5_ref"): ui.fmt(a.summary["rate_p5_bps"], ".1f", "", 1e-6),
                                 t("workspace.compare.p5_now"): ui.fmt(b.summary["rate_p5_bps"], ".1f", "", 1e-6)})
                st.markdown(f"**{ref['label']}** ({ui.ltr(', '.join(ref['stations']))})", unsafe_allow_html=True)
                if rows:
                    st.dataframe(rows, hide_index=True, width="stretch")
                a, b = ref["evals"].get(sid), evals.get(sid)
                cl = layer if layer in ("rx_power_dbm", "sinr_db", "interference_dbm", "path_gain_db") else "sinr_db"
                if a is not None and b is not None and ref["grid"] == exp.grid:
                    diff = np.where(exp.outdoor & np.isfinite(a.layers[cl]) & np.isfinite(b.layers[cl]),
                                    b.layers[cl] - a.layers[cl], np.nan)
                    lim = float(np.nanpercentile(np.abs(diff), 99)) if np.isfinite(diff).any() else 1.0
                    fig = go.Figure(go.Heatmap(x=exp.grid.x_centers, y=exp.grid.y_centers, z=diff, zmid=0,
                                               zmin=-max(lim, 0.1), zmax=max(lim, 0.1),
                                               colorscale=[[0, "#2a78d6"], [0.5, "#f0efec"], [1, "#e34948"]],
                                               colorbar=dict(title="dB")))
                    fig.update_layout(height=360, margin=dict(l=4, r=4, t=30, b=4), plot_bgcolor="#e9e8e3",
                                      title=t("workspace.compare.diff_title", layer=t(f"workspace.layers.{cl}"),
                                              band=ui.scenario_name(band(sid))),
                                      yaxis=dict(scaleanchor="x"))
                    ui.chart(fig)
                elif a is not None and b is not None:
                    st.warning(t("workspace.compare.not_comparable"))

# ================================================================ results and inspector (end side)
with right, st.container(height=PANEL_HEIGHT, border=False):
    n_missing = status[sid].missing if sid in status else 0
    if not enabled:
        state_kind, state_text = "empty", t("workspace.state.no_stations")
    elif active is not None:
        state_kind, state_text = "running", t("workspace.state.running")
    elif shown is not None:
        state_kind, state_text = "current", t("workspace.state.current_band", band=ui.scenario_name(sc))
    else:
        state_kind, state_text = "stale", t("workspace.state.stale" if stale else "workspace.state.not_simulated",
                                            n=n_missing)
    h("workspace.results.title")
    st.markdown(f'<div class="ws-state {state_kind}">{state_text}</div>', unsafe_allow_html=True)

    if enabled:
        c = ws.classify(ctx, stations, rad)
        head, details = i18n.classification_texts(tr, c)
        st.markdown(f'<div class="ws-class"><b>{head}</b></div>', unsafe_allow_html=True)
        with st.popover(t("workspace.results.class_details"), width="stretch"):
            st.markdown(details, unsafe_allow_html=True)
            devs = [d for d in c.deviations]
            if devs:
                st.markdown(t("workspace.results.deviations"))
                st.markdown("\n".join(f"- {i18n.deviation_text(tr, d)}" for d in devs))
            notes = ui.limitation_texts([x for x in ex.limitation_items(exp) if x[0] != "limitations.deviations"])
            if notes:
                st.markdown(t("simulation.limitations"))
                st.markdown("\n".join(f"- {x}" for x in notes))

    ev = shown if shown is not None else (previous or {}).get("eval")
    if ev is not None:
        s_ = ev.summary
        mapped = s_.get("rate_3gpp_p5_bps")
        rows = [("coverage.metrics.coverage", ui.fmt(s_["coverage_fraction"], ".1%"),
                 t("workspace.metrics.coverage_note", thr=f"{ev.radio.coverage_threshold:g}")),
                ("workspace.metrics.rx_median", ui.fmt(s_["rx_power_dbm_median"], ".1f", " dBm"), ""),
                ("workspace.metrics.rx_p5", ui.fmt(s_["rx_power_dbm_p5"], ".1f", " dBm"), ""),
                ("coverage.metrics.sinr_median", ui.fmt(s_["sinr_db_median"], ".1f", " dB"), ""),
                ("coverage.metrics.sinr_p5", ui.fmt(s_["sinr_db_p5"], ".1f", " dB"), ""),
                ("workspace.metrics.rate_median", ui.fmt(s_["rate_median_bps"], ".0f", " Mbit/s", 1e-6),
                 t("workspace.metrics.shannon")),
                ("workspace.metrics.rate_p5", ui.fmt(s_["rate_p5_bps"], ".1f", " Mbit/s", 1e-6), t("workspace.metrics.shannon")),
                ("workspace.metrics.mapped_p5", ui.fmt(mapped, ".1f", " Mbit/s", 1e-6) if mapped is not None else "—",
                 t("workspace.metrics.mapped_note") + (" " + t("workspace.metrics.approximation")
                                                        if s_.get("rate_3gpp_caveat") else "")),
                ("workspace.metrics.interference_limited", ui.fmt(s_.get("interference_limited_share"), ".0%"), ""),
                ("workspace.metrics.stations", f"{len(ev.station_ids)} · {s_['sectors']} {t('workspace.metrics.sectors')}", ""),
                ("workspace.metrics.duration", t("workspace.metrics.trace_time", s=f"{ev.trace_seconds:.0f}"),
                 t("workspace.metrics.duration_note"))]
        import html as _html

        body = "".join(f'<tr title="{_html.escape(n_, quote=True)}"><td>{t(k)}</td><td class="v">{ui.ltr(v)}</td></tr>'
                       for k, v, n_ in rows)
        st.markdown(f'<table class="ws-m {"stale" if stale else ""}">{body}</table>', unsafe_allow_html=True)
        st.markdown(f'<div class="ws-note">{t("workspace.metrics.footnote", thr=f"{ev.radio.coverage_threshold:g}")}'
                    + (" " + t("workspace.metrics.approximation") if s_.get("rate_3gpp_caveat") else "") + "</div>",
                    unsafe_allow_html=True)
        if stale:
            st.markdown(f'<div class="ws-note">{t("workspace.results.stale_note")}</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------ run
    h("workspace.run.title")
    band_missing = list(status[sid].missing_keys) if sid in status else []
    all_missing = list(dict.fromkeys(k for s_ in status.values() for k in s_.missing_keys))
    per = seconds_per_trace(exp.profile.rays_per_site, exp.profile.cell_size_m, ctx.engine["variant"])

    def minutes(n: int) -> str:
        return t("workspace.run.estimate", m=f"{per * n / 60:.1f}") if per and n else ""

    if active is None:
        if not enabled:
            st.caption(t("workspace.run.place_first"))
        elif not all_missing:
            st.caption(t("workspace.run.all_cached"))
        else:
            labels = ws.job_labels(design_jobs, stations)
            b1, b2 = st.columns(2)
            go_band = b1.button(t("workspace.run.band", n=len(band_missing)), type="primary", disabled=not band_missing,
                                width="stretch", help=minutes(len(band_missing)) or None)
            go_all = b2.button(t("workspace.run.all", n=len(all_missing)), disabled=not all_missing,
                               width="stretch", help=minutes(len(all_missing)) or None)
            if minutes(len(all_missing)):
                st.markdown(f'<div class="ws-note">{t("workspace.run.estimate_note", band=minutes(len(band_missing)) or "—", all=minutes(len(all_missing)))}</div>',
                            unsafe_allow_html=True)
            if go_band or go_all:
                chosen = design_jobs[sid] if go_band else [sj for js in design_jobs.values() for sj in js]
                SS.w_trace = str(wr.start(ROOT, [sj.job for sj in chosen], labels,
                                          {"scope": sid if go_band else "all", "area": SS.w_area,
                                           "variant": SS.w_variant, "profile": exp.profile.name,
                                           "backend": exp.backend}))
                st.rerun()

    def progress_view(folder: Path) -> None:
        s_ = wr.state(folder)
        if s_.running:
            total = max(s_.total, 1)
            cur = s_.current or {}
            what = ""
            if cur:
                bearing = cur.get("bearing_deg")
                what = t("workspace.run.current", band=ui.scenario_name(band(cur["scenario"])), station=cur["station"],
                         sector=cur["sector"], bearing="" if bearing is None else f" ({bearing:g}°)")
            st.progress(min(s_.done / total, 1.0), text=t("workspace.run.progress", done=s_.done, total=s_.total))
            w = s_.workload or {}
            st.markdown('<div class="ws-note">' + "<br>".join(x for x in (
                what, t("workspace.run.counts", cached=w.get("cached", 0), new=w.get("to_trace", 0),
                        left=max(s_.total - s_.done, 0)),
                t("workspace.run.elapsed", s=f"{s_.elapsed_seconds:.0f}"),
                t("workspace.run.retried", n=s_.retries) if s_.retries else "") if x) + "</div>", unsafe_allow_html=True)
            if st.button(t("simulation.history.cancel"), key=f"cancel-{folder.name}"):
                wr.cancel(folder)
                st.toast(t("simulation.history.cancelling"))
        else:
            SS.w_trace = None
            if s_.finished:
                message("success", t("workspace.run.finished", n=s_.total, s=f"{s_.trace_seconds or 0:.0f}"))
            elif s_.cancelled:
                message("warning", t("workspace.run.cancelled"))
            else:
                message("error", t("workspace.run.failed", error=s_.error or ""))
            st.rerun(scope="app")

    folder = Path(SS.w_trace) if SS.w_trace else (active.folder if active else None)
    if folder is not None:
        st.fragment(run_every=1.5)(progress_view)(folder)

    # ------------------------------------------------------------ automatic planning over the shown stations
    if len(stations) > 1:
        with st.expander(t("workspace.plan.title")):
            st.caption(t("planning.heuristic"))
            st.number_input(t("planning.target"), 0.5, 1.0, step=0.01, key="w_r_target", format="%.2f")
            every = [replace(s, enabled=True) for s in stations]
            every_status = ws.trace_status(ws.jobs(ctx, every), Presence)
            if not every_status[sid].complete:
                st.caption(t("workspace.plan.needs", n=every_status[sid].missing))
            elif st.button(t("workspace.plan.run", band=ui.scenario_name(sc)), width="stretch"):
                g = ws.greedy(ctx, stations, sc, rad, load, target=float(SS.w_r_target))
                SS.w_plan = {"band": sid, "selected": [stations[i].station_id for i in g.selected],
                             "coverage": g.coverage_after, "reached": g.target_reached, "reason": g.stopped_because}
            plan = SS.get("w_plan")
            if plan and plan["band"] == sid:
                st.markdown(t("planning.greedy_result", sites=ui.ltr(", ".join(plan["selected"])),
                              coverage=f"{plan['coverage'][-1]:.1%}",
                              reached=t("planning.reached") if plan["reached"] else t("planning.not_reached"),
                              reason="" if plan["reason"] == "target reached" else f" (*{ui.recorded(plan['reason'])}*)"),
                            unsafe_allow_html=True)
                if st.button(t("workspace.plan.keep"), width="stretch"):
                    SS.w_stations = [replace(s, enabled=s.station_id in plan["selected"]) for s in stations]
                    st.rerun()

    # ------------------------------------------------------------ selected object
    h("workspace.inspect.title")
    if sel.get("kind") == "station" and any(s.station_id == sel["id"] for s in stations):
        s = next(x for x in stations if x.station_id == sel["id"])
        key = f"w_st_{s.station_id}_{hashlib.sha256(json.dumps(asdict(s), sort_keys=True).encode()).hexdigest()[:8]}_"
        if s.mount == ws.ROOFTOP:
            st.markdown('<div class="ws-obj">' + t(
                "workspace.inspect.rooftop", station=s.station_id, building=ui.ltr(s.building_id),
                roof=f"{s.roof_height_m:g}", category=category_name(ui.height_display_category(ctx.building(s.building_id))
                                                         if ctx.building(s.building_id) else s.height_category),
                rule=t("workspace.inspect.rule_yes") if s.meets_site_rule else t("workspace.inspect.rule_no"))
                + "</div>", unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ws-hyp">{t("workspace.inspect.hypothetical", station=s.station_id)}</div>',
                        unsafe_allow_html=True)
        lon, lat = exp.area.transformer().transform(s.x, s.y, direction="INVERSE")
        near = ws.nearest_station_m(s, stations)
        st.markdown('<div class="ws-note">' + t("workspace.inspect.position", x=f"{s.x:.1f}", y=f"{s.y:.1f}",
                                                 lat=f"{lat:.5f}", lon=f"{lon:.5f}")
                    + ("<br>" + t("workspace.inspect.nearest", d=f"{near:.0f}",
                                  rule=f"{exp.candidate_rule['min_spacing_m']:g}") if near is not None else "")
                    + "</div>", unsafe_allow_html=True)

        def edit(field, value_key, convert=float, s=s, key=key):
            def apply():                            # runs before the next script run: values bound here
                value = SS[value_key]
                if field == "antenna_height_m" and s.mount == ws.ROOFTOP:
                    update_station(s.station_id, antenna_height_m=s.roof_height_m + float(value))
                elif field == "xy":
                    try:
                        moved = ws.move(ctx, s, float(SS[key + "x"]), float(SS[key + "y"]), template(ctx), stations)
                        SS.w_stations = [moved if x.station_id == s.station_id else x for x in SS.w_stations]
                    except ws.PlacementError as err:
                        message("warning", placement_text(err))
                else:
                    update_station(s.station_id, **{field: convert(value)})
            return apply

        c1, c2 = st.columns(2)
        c1.number_input("x [m]", value=float(round(s.x, 1)), step=5.0, key=key + "x", on_change=edit("xy", key + "x"))
        c2.number_input("y [m]", value=float(round(s.y, 1)), step=5.0, key=key + "y", on_change=edit("xy", key + "y"))
        if s.mount == ws.ROOFTOP:
            c1.number_input(t("workspace.fields.mast"), 0.0, 30.0, value=float(s.mast_height_m), step=0.5,
                            key=key + "mast", on_change=edit("antenna_height_m", key + "mast"), format="%.1f")
        else:
            c1.number_input(t("workspace.fields.hyp_height"), 1.0, 300.0, value=float(s.antenna_height_m), step=1.0,
                            key=key + "z", on_change=edit("antenna_height_m", key + "z"), format="%.1f")
        c2.number_input(t("workspace.fields.power"), 0.0, 60.0, value=float(s.tx_power_dbm), step=1.0,
                        key=key + "p", on_change=edit("tx_power_dbm", key + "p"), format="%.1f")
        c1.number_input(t("workspace.fields.sectors"), 1, 6, value=int(s.sectors), step=1, key=key + "n",
                        on_change=edit("sectors", key + "n", int), disabled=s.pattern == "iso")
        c2.number_input(t("workspace.fields.azimuth"), 0.0, 359.9, value=float(s.azimuth_deg), step=5.0,
                        key=key + "az", on_change=edit("azimuth_deg", key + "az"), format="%.1f",
                        disabled=s.pattern == "iso")
        c1.number_input(t("workspace.fields.downtilt"), -10.0, 30.0, value=float(s.downtilt_deg), step=1.0,
                        key=key + "tilt", on_change=edit("downtilt_deg", key + "tilt"), format="%.1f",
                        disabled=s.pattern == "iso")
        c2.selectbox(t("workspace.fields.pattern"), ["tr38901", "iso"], index=["tr38901", "iso"].index(s.pattern)
                     if s.pattern in ("tr38901", "iso") else 0, key=key + "pat", on_change=edit("pattern", key + "pat", str),
                     format_func=lambda p_: t(f"workspace.patterns.{p_}"))
        st.markdown('<div class="ws-note">' + t("workspace.inspect.bearings", b=ui.ltr(
            " / ".join(f"{b:g}°" for b in s.bearings_deg) or "—")) + "</div>", unsafe_allow_html=True)
        e1, e2 = st.columns(2)
        e1.toggle(t("workspace.fields.enabled"), value=s.enabled, key=key + "on", on_change=edit("enabled", key + "on", bool))
        if e2.button(t("workspace.inspect.remove"), key=key + "rm", width="stretch"):
            remove(s.station_id)
            st.rerun()
        traced = [sj.job.key() for sj in ws.jobs(ctx, [replace(s, enabled=True)])[sid]]
        have = sum(Presence.has(k) for k in traced)
        st.markdown(f'<div class="ws-note">{t("workspace.inspect.traced", have=have, n=len(traced), band=ui.scenario_name(sc))}</div>',
                    unsafe_allow_html=True)
    elif sel.get("kind") == "building":
        b = ctx.building(sel["id"])
        if b is not None:
            cat = ui.height_display_category(b)
            st.markdown('<div class="ws-obj">' + t(
                "workspace.inspect.building", building=ui.ltr(b.building_id), height=f"{b.height.height_m:.1f}",
                category=category_name(cat), area=f"{b.polygon.area:.0f}",
                rule=t("workspace.inspect.rule_yes") if ws.meets_rule(ctx, b) else t("workspace.inspect.rule_no"))
                + "</div>", unsafe_allow_html=True)
            st.markdown('<div class="ws-note">' + t("workspace.inspect.provenance", source=ui.ltr(b.height.source),
                                                     method=b.height.method) + "</div>", unsafe_allow_html=True)
            if cat == "synthetic":
                st.markdown(f'<div class="ws-note">{t("workspace.inspect.synthetic")}</div>', unsafe_allow_html=True)
            if st.button(t("workspace.inspect.place_here"), width="stretch"):
                handle({"type": "place", "x": sel["x"], "y": sel["y"], "n": f"btn-{b.building_id}"})
                st.rerun()
    elif sel.get("kind") == "cell":
        e = shown if shown is not None else (previous or {}).get("eval")
        grid = exp.grid if shown is not None else (previous or {}).get("grid", exp.grid)
        outdoor = exp.outdoor if shown is not None else (previous or {}).get("outdoor", exp.outdoor)
        v = ws.cell_values(e, grid, outdoor, sel["x"], sel["y"]) if e is not None else None
        if v is None:
            st.caption(t("workspace.inspect.no_cell"))
        elif not v["outdoor"]:
            st.caption(t("workspace.inspect.indoor"))
        else:
            def val(name, spec, unit, scale=1.0):
                x = v.get(name)
                return "—" if x is None else (t("workspace.map.no_path") if not np.isfinite(x) else f"{x * scale:{spec}}{unit}")
            serving = v.get("serving_station", -1)
            items = [("workspace.layers.rx_power_dbm", val("rx_power_dbm", ".1f", " dBm")),
                     ("workspace.layers.sinr_db", val("sinr_db", ".1f", " dB")),
                     ("workspace.layers.rate_bps", val("rate_bps", ".1f", " Mbit/s", 1e-6)),
                     ("workspace.layers.rate_3gpp_bps", val("rate_3gpp_bps", ".1f", " Mbit/s", 1e-6)),
                     ("workspace.layers.covered", t("coverage.map.covered") if v.get("covered") else t("coverage.map.not_covered")),
                     ("workspace.layers.serving_station", t("workspace.inspect.serving", station=e.sectors[v["serving_sector"]][0],
                                                            sector=e.sectors[v["serving_sector"]][1])
                      if serving >= 0 else "—"),
                     ("workspace.layers.interference_dbm", val("interference_dbm", ".1f", " dBm")),
                     ("workspace.layers.path_gain_db", val("path_gain_db", ".1f", " dB"))]
            st.markdown(f'<div class="ws-note">{t("workspace.inspect.cell", x=f"{v["x"]:.0f}", y=f"{v["y"]:.0f}", band=ui.scenario_name(sc))}'
                        + (f" · {t('workspace.map.stale_short')}" if stale else "") + "</div>", unsafe_allow_html=True)
            body = "".join(f'<tr><td>{t(k)}</td><td class="v">{ui.ltr(x)}</td></tr>' for k, x in items)
            st.markdown(f'<table class="ws-m {"stale" if stale else ""}">{body}</table>', unsafe_allow_html=True)
    else:
        st.caption(t("workspace.inspect.none"))

    # ------------------------------------------------------------ station list
    if stations:
        h("workspace.inspect.list", n=len(stations))
        rows = [{"": s.station_id, t("workspace.columns.mount"): t(f"workspace.mounts.{s.mount}"),
                 t("workspace.columns.host"): s.building_id or "—", t("workspace.columns.height"): round(s.antenna_height_m, 1),
                 t("workspace.columns.power"): s.tx_power_dbm, t("workspace.columns.sectors"): s.sectors,
                 t("workspace.columns.on"): s.enabled} for s in stations]
        picked = st.dataframe(rows, hide_index=True, width="stretch", on_select="rerun",
                              selection_mode="single-row", key=f"w_list_{sel.get('id', '')}")
        rows_sel = (picked.selection.rows if picked is not None and hasattr(picked, "selection") else [])
        if rows_sel:
            SS.w_sel = {"kind": "station", "id": stations[rows_sel[0]].station_id}
            st.rerun()
    if SS.w_origin:
        o = SS.w_origin
        st.markdown('<div class="ws-note">' + t("workspace.results.origin", run=ui.ltr(o["run"]), identical=o["identical"],
                                                 recorded=o["recorded"]) + "</div>", unsafe_allow_html=True)
