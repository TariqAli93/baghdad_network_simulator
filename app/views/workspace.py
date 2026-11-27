"""Simulation Workspace: configure, place stations, simulate, visualise and compare on one screen.

Settings on the start side, the network map in the middle, results, the run and the selected object on
the end side. An experiment is the editable configuration (bns.app.experiments); a run is an immutable
result written in the multi-site format (bns.app.run_record) by scripts/run_workspace.py in its own
process. Whatever changes a propagation job key needs ray tracing; everything else is recomputed at
once from the path-gain cache (bns.app.workspace). Results are only ever computed from the cache
entries of exactly the stations and carriers shown.
"""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import ui
import yaml
from plotly.subplots import make_subplots
from ui import t

from bns import i18n
from bns.app import carriers as ca
from bns.app import experiments as xp
from bns.app import results
from bns.app import workspace as ws
from bns.app import workspace_runs as wr
from bns.simulation import experiment as ex
from bns.simulation.cache import PathGainCache

st.markdown("""<style>
[data-testid="stMainBlockContainer"] {padding-top: 1.2rem; padding-left: 1rem; padding-right: 1rem; max-width: 100%;}
.ws-h {font-size: .8rem; font-weight: 600; opacity: .85; margin: .55rem 0 .1rem; padding-bottom: .15rem;
       border-bottom: 1px solid rgba(128,128,128,.28);}
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
.ws-class {font-size: .78rem; opacity: .9; margin-bottom: .25rem;}
.ws-exp {font-size: 1.05rem; font-weight: 600;}
.ws-dirty {font-size: .72rem; padding: .05rem .4rem; border-radius: 3px; background: rgba(183,121,31,.16); color: #8a5a12;
           margin-inline-start: .4rem; font-weight: 500;}
.ws-saved {font-size: .72rem; padding: .05rem .4rem; border-radius: 3px; background: rgba(40,140,90,.14); color: #1d6a43;
           margin-inline-start: .4rem; font-weight: 500;}
table.ws-m {width: 100%; border-collapse: collapse; font-size: .84rem; font-variant-numeric: tabular-nums;}
table.ws-m td {padding: .18rem .3rem; border-bottom: 1px solid rgba(128,128,128,.18); vertical-align: top;}
table.ws-m td.v {text-align: end; white-space: nowrap; font-weight: 600;}
table.ws-m.stale td.v {opacity: .55; font-weight: 500;}
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
MAP_LAYERS = ["none", "rx_power_dbm", "sinr_db", "covered", "rate_bps", "rate_3gpp_bps", "serving_station",
              "interference_dbm", "path_gain_db"]
CONTINUOUS = ("rx_power_dbm", "sinr_db", "rate_bps", "rate_3gpp_bps", "interference_dbm", "path_gain_db")
NO_PATH = -9999
HEIGHT_COLOURS = ["#f4efe2", "#e6d3aa", "#d3ad6c", "#b9823e", "#8d5a26", "#5c3818"]
PANEL_HEIGHT = 880
COMPONENT_DIR = Path(__file__).resolve().parents[1] / "components"


def h(key: str, tag: str | None = None, **values) -> None:
    """A compact section heading; `tag` says whether its controls need ray tracing or are instant."""
    badge = f'<span class="ws-tag {tag}">{t("workspace.tag." + tag)}</span>' if tag else ""
    st.markdown(f'<div class="ws-h">{t(key, **values)}{badge}</div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="ws-note">{text}</div>', unsafe_allow_html=True)


def colour(station_id: str) -> str:
    digits = "".join(ch for ch in station_id if ch.isdigit()) or "1"
    return ui.SITE_COLOURS[(int(digits) - 1) % len(ui.SITE_COLOURS)]


def category_name(c: str | None) -> str:
    return t(f"common.height_category.{c}") if c and tr.has(f"common.height_category.{c}") else (c or "—")


def carrier_name(c: dict) -> str:
    """'5G — 3.5 GHz', or for a custom carrier '5G — 3.5 GHz → 8 GHz / 100 MHz'."""
    base = ui.scenario_name({"id": c["preset"], "label": c["label"],
                             "frequency_hz": c.get("preset_frequency_hz", c["frequency_hz"])})
    if not c.get("custom"):
        return base
    return f"{base} → {c['frequency_hz'] / 1e9:g} GHz / {c['bandwidth_hz'] / 1e6:g} MHz"


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


@st.cache_resource(show_spinner=False, max_entries=80)
def evaluation(signature: str, _ctx, _stations, _carrier, _radio) -> ws.Evaluation:
    return ws.evaluate(_ctx, _stations, _carrier, _radio, load)


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


@st.cache_data(show_spinner=False, ttl=60)
def power_plan():
    from bns import runtime
    return runtime.power_plan()


# ---------------------------------------------------------------- experiment <-> session
def profile() -> str:
    return SS.get("w_profile") or "standard"


def backend() -> str:
    return SS.get("w_backend") or "cpu"


def selected_carriers() -> list[dict]:
    return [c for c in SS.w_carriers if c.get("selected")]


def template_values() -> dict:
    return {"tx_power_dbm": float(SS.w_t_power), "sectors": int(SS.w_t_sectors), "azimuth_deg": float(SS.w_t_az),
            "downtilt_deg": float(SS.w_t_tilt), "mast_height_m": float(SS.w_t_mast),
            "hypothetical_height_m": SS.w_t_hyp, "allow_hypothetical": bool(SS.w_t_allow)}


def radio() -> ws.RadioSettings:
    return ws.RadioSettings(float(SS.w_r_thr), float(SS.w_r_load), float(SS.w_r_nf), float(SS.w_r_rain))


def to_experiment() -> xp.Experiment:
    m = SS.w_meta
    return xp.Experiment(m["experiment_id"], m["name"], SS.w_area, SS.w_variant, profile(), float(SS.w_cell),
                         int(SS.w_rays), backend(), float(SS.w_rx), asdict(radio()),
                         [dict(c) for c in SS.w_carriers], [asdict(s) for s in SS.w_stations], template_values(),
                         m.get("created_utc", ""), m.get("modified_utc", ""), dict(m.get("origin") or {}),
                         m.get("notes", ""))


def signature(e: xp.Experiment) -> str:
    d = e.to_dict()
    for k in ("modified_utc", "created_utc"):
        d.pop(k, None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def baseline_values(profile_name: str = "standard") -> dict:
    return ex.baseline_values(ROOT, profile_name)


def default_carriers() -> list[dict]:
    return [{**c, "selected": True} for c in ca.presets(ROOT)]


def apply_template(values: dict, base: dict) -> None:
    SS.w_t_power = float(values.get("tx_power_dbm", base["tx_power_dbm"]))
    SS.w_t_sectors = int(values.get("sectors", base["sectors_per_site"]))
    SS.w_t_az = float(values.get("azimuth_deg", 0.0))
    SS.w_t_tilt = float(values.get("downtilt_deg", base["mechanical_downtilt_deg"]))
    SS.w_t_mast = float(values.get("mast_height_m", base["antenna_height_above_roof_m"]))
    SS.w_t_hyp = values.get("hypothetical_height_m")
    SS.w_t_allow = bool(values.get("allow_hypothetical", False))


def apply_radio(values: dict, base: dict) -> None:
    SS.w_r_thr = float(values.get("coverage_threshold", base["coverage_threshold"]))
    SS.w_r_load = float(values.get("interference_activity", base["interference_activity"]))
    SS.w_r_nf = float(values.get("noise_figure_db", base["noise_figure_db"]))
    SS.w_r_rain = float(values.get("rain_rate_mm_h", base["rain_rate_mm_h"]))


def apply_experiment(e: xp.Experiment, *, saved: bool) -> None:
    """Show an experiment in the workspace (call before the widgets render, or from a callback)."""
    base = baseline_values(xp.base_profile(e))
    SS.w_meta = {"experiment_id": e.experiment_id, "name": e.name, "created_utc": e.created_utc,
                 "modified_utc": e.modified_utc, "origin": e.origin, "notes": e.notes}
    SS.w_area, SS.w_variant, SS.w_profile, SS.w_backend = e.area, e.variant, e.profile, e.backend
    SS.w_cell, SS.w_rays, SS.w_rx = float(e.cell_size_m), int(e.rays_per_site), float(e.rx_height_m)
    apply_radio(e.radio or {}, base)
    apply_template(e.template or {}, base)
    presets = {c["id"]: c for c in default_carriers()}
    rows = {c["preset"]: {**c, "selected": c.get("selected", True)} for c in e.carriers or []}
    SS.w_carriers = [rows.get(pid, {**presets[pid], "selected": not e.carriers}) for pid in presets]
    SS.w_stations = [ws.Station(**s) for s in e.stations]
    SS.w_sel, SS.w_last, SS.w_plan = {}, {}, None
    SS.w_carrier_rev = SS.get("w_carrier_rev", 0) + 1
    SS.w_saved_sig = signature(e) if saved else None


def new_experiment(name: str) -> xp.Experiment:
    base = baseline_values("standard")
    areas = ui.study_areas()
    study = [k for k, v in areas.items() if v.get("approved")]
    area = study[0] if study else next(iter(areas))
    variants = ui.variants(area) or ["osm"]
    return xp.Experiment.new(name, area=area, variant=variants[ui.default_variant(area, variants)], profile="standard",
                             cell_size_m=base["cell_size_m"], rays_per_site=base["rays_per_site"], backend="cpu",
                             rx_height_m=base["rx_height_m"], radio={}, carriers=default_carriers(), stations=[])


def from_run(path: str, name: str) -> tuple[xp.Experiment, dict]:
    """A new experiment holding a saved run's settings and stations (its traces are reused)."""
    run = results.load_run(Path(path))
    st_ = ws.run_settings(run.manifest)
    base = baseline_values(st_["profile"])
    custom = "cell_size_m" in st_["overrides"] or "rays_per_site" in st_["overrides"]
    e = xp.Experiment.new(name, area=st_["area"], variant=st_["variant"], profile="custom" if custom else st_["profile"],
                          cell_size_m=float(st_["overrides"].get("cell_size_m", base["cell_size_m"])),
                          rays_per_site=int(st_["overrides"].get("rays_per_site", base["rays_per_site"])),
                          backend=st_["backend"], rx_height_m=float(st_["overrides"].get("rx_height_m", base["rx_height_m"])),
                          radio={}, carriers=[], stations=[], origin={"opened_from_run": run.run_id})
    ctx = xp.context(ROOT, e)
    stations, check = ws.stations_from_run(ctx, run.manifest, run.summary)
    recorded = {c["id"]: c for c in ws.run_carriers(run.manifest)}
    carriers = [{**recorded.get(p["id"], p), "selected": p["id"] in {c["preset"] for c in recorded.values()}}
                for p in ca.presets(ROOT)]
    return replace(e, radio=asdict(ws.run_radio(ctx, run.manifest)), carriers=carriers,
                   stations=[asdict(s) for s in stations]), check


def message(level: str, text: str) -> None:
    SS.w_msg = (level, text)


def init_state() -> None:
    if "w_meta" in SS:
        return
    SS.w_band, SS.w_layer, SS.w_fill, SS.w_cands = "nr_3500", "sinr_db", "plain", False
    SS.w_run, SS.w_ref, SS.w_msg, SS.w_seen, SS.w_mode_req, SS.w_report = None, None, None, None, None, None
    saved = xp.list_all(ROOT)
    if saved:                                       # the most recently edited experiment
        apply_experiment(saved[0], saved=True)
        return
    # first start: a new experiment on the newest saved run of the study district's primary dataset
    # (prefer a CPU research-baseline run), so the first screen shows real stations and results
    fresh = new_experiment(t("workspace.experiment.first_name"))
    runs = [results.load_run(Path(p)) for p in saved_runs()]
    mine = [r for r in runs if r.manifest["area"]["name"] == fresh.area
            and r.manifest["area"].get("variant") == fresh.variant and r.kind == "multi_site"]
    mine.sort(key=lambda r: (r.classification.configuration == "Research Baseline", r.backend == "cpu",
                             r.manifest.get("created_utc", "")), reverse=True)
    if mine:
        try:
            fresh, _ = from_run(str(mine[0].path), t("workspace.experiment.first_name"))
        except Exception:                           # noqa: BLE001 - fall back to an empty experiment
            pass
    apply_experiment(fresh, saved=False)


def handle_request() -> None:
    """Requests from other pages (Experiment History): open an experiment or a run here."""
    req = SS.pop("w_request", None)
    if not req:
        return
    try:
        if req.get("experiment"):
            apply_experiment(xp.load(ROOT, req["experiment"]), saved=True)
        elif req.get("run"):
            e, check = from_run(req["run"], t("workspace.experiment.from_run_name", run=Path(req["run"]).name[-24:]))
            apply_experiment(e, saved=False)
            message("success" if check["exact"] else "warning",
                    t("workspace.messages.run_loaded" if check["exact"] else "workspace.messages.run_partial",
                      run=Path(req["run"]).name, identical=check["identical"], recorded=check["recorded"]))
    except Exception as exc:                        # noqa: BLE001 - shown to the user
        message("error", str(exc))


# ---------------------------------------------------------------- context and design
def overrides() -> dict:
    return xp.overrides(ROOT, to_experiment())


def current_context() -> ws.Context:
    return context(SS.w_area, SS.w_variant, xp.base_profile(to_experiment()), backend(),
                   json.dumps(overrides(), sort_keys=True))


def template(ctx: ws.Context) -> ws.StationTemplate:
    v = template_values()
    return replace(ws.StationTemplate.baseline(ctx), tx_power_dbm=v["tx_power_dbm"], sectors=v["sectors"],
                   azimuth_deg=v["azimuth_deg"], downtilt_deg=v["downtilt_deg"], mast_height_m=v["mast_height_m"],
                   hypothetical_height_m=v["hypothetical_height_m"], allow_hypothetical=v["allow_hypothetical"])


def placement_text(err: ws.PlacementError) -> str:
    key = f"workspace.place_errors.{err.code}"
    return t(key, **err.values) if tr.has(key) else str(err)


def carrier_text(err: ca.CarrierError) -> str:
    key = f"workspace.carrier_errors.{err.code}"
    return t(key, **err.values) if tr.has(key) else str(err)


# ---------------------------------------------------------------- callbacks
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
    if SS.get("w_stations_area") not in (None, SS.w_area):
        SS.w_stations = []                          # another area: its stations do not belong here
    SS.w_stations_area = SS.w_area
    kept, dropped = ws.rebind(ctx, SS.w_stations, template(ctx))
    SS.w_stations, SS.w_sel, SS.w_last = kept, {}, {}
    if dropped:
        message("warning", t("workspace.messages.dropped", stations=", ".join(dropped)))


def on_profile_change() -> None:
    if profile() != "custom":
        base = baseline_values(profile())
        SS.w_cell, SS.w_rays = base["cell_size_m"], base["rays_per_site"]


def on_reset_baseline() -> None:
    """Research baseline: the five presets, baseline values, standard profile on the CPU (stations kept)."""
    base = baseline_values("standard")
    apply_template({}, base)
    apply_radio({}, base)
    SS.w_profile, SS.w_backend, SS.w_rx = "standard", "cpu", base["rx_height_m"]
    SS.w_cell, SS.w_rays = base["cell_size_m"], base["rays_per_site"]
    SS.w_carriers = default_carriers()
    SS.w_carrier_rev = SS.get("w_carrier_rev", 0) + 1
    tp = ws.StationTemplate.baseline(current_context())          # the configured (baseline) station values
    SS.w_stations = [replace(s, tx_power_dbm=tp.tx_power_dbm, sectors=tp.sectors, azimuth_deg=0.0,
                             downtilt_deg=tp.downtilt_deg, pattern=tp.pattern,
                             antenna_height_m=(s.roof_height_m + tp.mast_height_m) if s.mount == ws.ROOFTOP
                             else s.antenna_height_m) for s in SS.w_stations]
    message("info", t("workspace.messages.reset_baseline"))


def on_carrier_edit() -> None:
    edits = (SS.get(f"w_carrier_table_{SS.w_carrier_rev}") or {}).get("edited_rows") or {}
    if not edits:
        return
    try:
        scene = current_context().exp.scene_dir
    except Exception as exc:                        # noqa: BLE001
        message("error", str(exc))
        return
    rows = [dict(c) for c in SS.w_carriers]
    for i, change in edits.items():
        row = rows[int(i)]
        if "on" in change:
            row["selected"] = bool(change["on"])
        if "f_ghz" in change or "b_mhz" in change:
            f = float(change.get("f_ghz", row["frequency_hz"] / 1e9)) * 1e9
            b = float(change.get("b_mhz", row["bandwidth_hz"] / 1e6)) * 1e6
            try:
                rows[int(i)] = {**ca.customize(row, frequency_hz=f, bandwidth_hz=b, scene_dir=scene),
                                "selected": row["selected"]}
            except ca.CarrierError as err:
                message("warning", carrier_text(err))
    SS.w_carriers = rows
    SS.w_carrier_rev += 1


def on_equal_bandwidth() -> None:
    try:
        scene = current_context().exp.scene_dir
        same = ca.equal_bandwidth(SS.w_carriers, float(SS.w_eq_bw) * 1e6, scene)
    except ca.CarrierError as err:
        message("warning", carrier_text(err))
        return
    SS.w_carriers = [{**c, "selected": old.get("selected", True)} for c, old in zip(same, SS.w_carriers, strict=True)]
    SS.w_carrier_rev += 1


def on_reset_carriers() -> None:
    selected = {c["preset"]: c.get("selected", True) for c in SS.w_carriers}
    SS.w_carriers = [{**c, "selected": selected.get(c["id"], True)} for c in ca.presets(ROOT)]
    SS.w_carrier_rev += 1


# experiment actions
def on_save() -> None:
    try:
        saved = xp.save(ROOT, to_experiment())
    except ValueError as exc:
        message("warning", str(exc))
        return
    SS.w_meta.update(modified_utc=saved.modified_utc, created_utc=saved.created_utc)
    SS.w_saved_sig = signature(saved)
    message("success", t("workspace.experiment.saved", name=saved.name))


def on_save_as() -> None:
    name = (SS.get("w_new_name") or "").strip()
    if not name:
        message("warning", t("workspace.experiment.name_needed"))
        return
    if SS.w_saved_sig is None:                      # never saved: this is its first save, not a copy
        SS.w_meta["name"] = name
        on_save()
        return
    saved = xp.save_as(ROOT, to_experiment(), name)
    apply_experiment(saved, saved=True)
    message("success", t("workspace.experiment.saved", name=saved.name))


def on_rename() -> None:
    name = (SS.get("w_rename") or "").strip()
    if not name:
        message("warning", t("workspace.experiment.name_needed"))
        return
    SS.w_meta["name"] = name
    if SS.w_saved_sig is not None:
        on_save()


def on_new() -> None:
    apply_experiment(new_experiment(t("workspace.experiment.new_name")), saved=False)


def on_open() -> None:
    if SS.get("w_open_pick"):
        apply_experiment(xp.load(ROOT, SS.w_open_pick), saved=True)


def on_duplicate(as_6g: bool = False) -> None:
    name = (SS.get("w_dup_name") or "").strip() or t("workspace.experiment.copy_of", name=SS.w_meta["name"])
    copy = replace(to_experiment(), experiment_id=xp.new_id(name), name=name,
                   origin={"duplicated_from": SS.w_meta["experiment_id"]})
    if as_6g:                                       # same stations, the two candidate 6G presets only
        copy = replace(copy, carriers=[{**c, "selected": c["id"].startswith("c6g")} for c in ca.presets(ROOT)])
    saved = xp.save(ROOT, copy)
    apply_experiment(saved, saved=True)
    message("success", t("workspace.experiment.duplicated", name=saved.name))


def on_open_run() -> None:
    try:
        e, check = from_run(SS.w_run_pick, t("workspace.experiment.from_run_name", run=Path(SS.w_run_pick).name[-24:]))
    except Exception as exc:                        # noqa: BLE001
        message("error", t("workspace.messages.run_unreadable", run=Path(SS.w_run_pick).name, error=str(exc)))
        return
    apply_experiment(e, saved=False)
    message("success" if check["exact"] else "warning",
            t("workspace.messages.run_loaded" if check["exact"] else "workspace.messages.run_partial",
              run=Path(SS.w_run_pick).name, identical=check["identical"], recorded=check["recorded"]))


@st.dialog(t("workspace.experiment.delete_title"))
def confirm_delete() -> None:
    st.markdown(t("workspace.experiment.delete_text", name=SS.w_meta["name"]))
    a, b = st.columns(2)
    if a.button(t("workspace.experiment.delete_confirm"), type="primary", width="stretch"):
        try:
            xp.delete(ROOT, SS.w_meta["experiment_id"])
        except FileNotFoundError:
            pass
        apply_experiment(new_experiment(t("workspace.experiment.new_name")), saved=False)
        message("success", t("workspace.experiment.deleted"))
        st.rerun()
    if b.button(t("workspace.experiment.cancel"), width="stretch"):
        st.rerun()


# Streamlit forgets a widget's value when the widget is not drawn (another page was open): the values
# are kept in w_store at the end of every run and restored here
WIDGET_KEYS = ("w_area", "w_variant", "w_profile", "w_backend", "w_cell", "w_rays", "w_rx", "w_r_thr", "w_r_load",
               "w_r_nf", "w_r_rain", "w_t_power", "w_t_sectors", "w_t_az", "w_t_tilt", "w_t_mast", "w_t_hyp",
               "w_t_allow", "w_band", "w_layer", "w_fill", "w_cands", "w_eq_bw", "w_r_target", "w_rule_n")
for _k, _v in (SS.get("w_store") or {}).items():
    if _k not in SS:
        SS[_k] = _v

# ================================================================ page
init_state()
handle_request()
if SS.get("w_stations_area") is None:
    SS.w_stations_area = SS.w_area

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
carriers = selected_carriers()
design_jobs = ws.jobs(ctx, stations, carriers) if carriers else {}
status = ws.trace_status(design_jobs, Presence) if stations else {}
rad = radio()
active = wr.active(ROOT)
enabled = [s for s in stations if s.enabled]
experiment = to_experiment()
dirty = SS.w_saved_sig != signature(experiment)


def current_eval(c: dict) -> ws.Evaluation | None:
    """The evaluation of the shown stations on this carrier, or None if a trace is missing."""
    if not enabled or not status.get(c["id"]) or not status[c["id"]].complete:
        return None
    sig = json.dumps({"ctx": [SS.w_area, SS.w_variant, profile(), backend(), overrides()],
                      "stations": [asdict(s) for s in stations], "radio": asdict(rad), "carrier": c}, sort_keys=True,
                     default=str)
    e = evaluation(hashlib.sha256(sig.encode()).hexdigest(), ctx, stations, c, rad)
    SS.w_last[c["id"]] = {"eval": e, "grid": exp.grid, "outdoor": exp.outdoor}
    return e


evals = {c["id"]: current_eval(c) for c in carriers}
ids = [c["id"] for c in carriers]
if ids and SS.get("w_band") not in ids:
    SS.w_band = ids[0]                              # the band widget is not drawn yet in this run
sid = SS.get("w_band") if SS.get("w_band") in ids else None
car = next((c for c in carriers if c["id"] == sid), None)
shown = evals.get(sid) if sid else None
previous = SS.w_last.get(sid) if (shown is None and sid) else None
stale = shown is None and previous is not None

# ---------------------------------------------------------------- experiment bar
bar = st.columns([3.2, 0.8, 1.0, 1.1, 1.1], vertical_alignment="center")
with bar[0]:
    badge = f'<span class="ws-dirty">{t("workspace.experiment.unsaved")}</span>' if dirty else \
        f'<span class="ws-saved">{t("workspace.experiment.saved_badge")}</span>'
    import html as _html_name

    st.markdown(f'<div class="ws-exp">{_html_name.escape(SS.w_meta["name"])}{badge}</div>', unsafe_allow_html=True)
bar[1].button(t("workspace.experiment.save"), type="primary" if dirty else "secondary", on_click=on_save,
              width="stretch", help=t("workspace.experiment.save_help"))
with bar[2].popover(t("workspace.experiment.menu"), width="stretch"):
    st.button(t("workspace.experiment.new"), on_click=on_new, width="stretch")
    others = xp.list_all(ROOT)
    if others:
        st.selectbox(t("workspace.experiment.open"), [e.experiment_id for e in others], key="w_open_pick",
                     format_func=lambda i: next(e.name for e in others if e.experiment_id == i))
        st.button(t("workspace.experiment.open_button"), on_click=on_open, width="stretch")
    st.text_input(t("workspace.experiment.save_as"), key="w_new_name", placeholder=t("workspace.experiment.name"))
    st.button(t("workspace.experiment.save_as_button"), on_click=on_save_as, width="stretch")
    st.text_input(t("workspace.experiment.rename"), key="w_rename", placeholder=SS.w_meta["name"])
    st.button(t("workspace.experiment.rename_button"), on_click=on_rename, width="stretch")
    st.text_input(t("workspace.experiment.duplicate"), key="w_dup_name", placeholder=t("workspace.experiment.copy_of",
                                                                                       name=SS.w_meta["name"]))
    st.button(t("workspace.experiment.duplicate_button"), on_click=on_duplicate, width="stretch")
    st.button(t("workspace.experiment.duplicate_6g"), on_click=on_duplicate, kwargs={"as_6g": True}, width="stretch",
              help=t("workspace.experiment.duplicate_6g_help"))
    if SS.w_saved_sig is not None and st.button(t("workspace.experiment.delete"), width="stretch"):
        confirm_delete()
runs_of_this = xp.runs_of(ROOT, SS.w_meta["experiment_id"]) if SS.w_saved_sig is not None else []
with bar[3]:
    if runs_of_this:
        if st.button(t("workspace.experiment.export"), width="stretch", help=t("workspace.experiment.export_help")):
            from bns.reporting import report
            run_dir = next(p for p in (ROOT / "outputs" / "runs").glob(f"*/{runs_of_this[0]}"))
            SS.w_report = (runs_of_this[0], report.build_html(run_dir, lang=ui.lang()))
    else:
        st.caption(t("workspace.experiment.no_runs"))
with bar[4]:
    if SS.get("w_report") and runs_of_this and SS.w_report[0] == runs_of_this[0]:
        st.download_button(t("workspace.experiment.download"), SS.w_report[1].encode("utf-8"),
                           file_name=f"report-{SS.w_report[0]}-{ui.lang()}.html", mime="text/html", width="stretch")
    elif runs_of_this:
        st.caption(t("workspace.experiment.runs", n=len(runs_of_this)))

# one slot that always exists: a message must not shift the map below it (the map would be remounted and
# lose its tool, zoom and pan)
message_slot = st.empty()
if SS.w_msg:
    level, text = SS.w_msg
    getattr(message_slot, {"success": "success", "warning": "warning", "error": "error"}.get(level, "info"))(text)
    SS.w_msg = None

left, centre, right = st.columns([1.1, 3.0, 1.35], gap="small")

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
        note(t("workspace.settings.synthetic_note", pct=f"{syn:.0f}"))

    h("workspace.settings.carriers", "trace")
    rows = [{"on": bool(c.get("selected")),
             "band": ui.scenario_name({"id": c["preset"], "label": c["label"],
                                       "frequency_hz": c.get("preset_frequency_hz", c["frequency_hz"])}),
             "f_ghz": c["frequency_hz"] / 1e9, "b_mhz": c["bandwidth_hz"] / 1e6,
             "state": t("workspace.carrier_state.custom") + (" · " + t("workspace.carrier_state.no_gas")
                                                             if c.get("gas") == ca.OMITTED else "")
             if c.get("custom") else t("workspace.carrier_state.preset")} for c in SS.w_carriers]
    st.data_editor(rows, key=f"w_carrier_table_{SS.w_carrier_rev}", on_change=on_carrier_edit, hide_index=True,
                   width="stretch", num_rows="fixed", column_config={
                       "on": st.column_config.CheckboxColumn(t("workspace.carriers.on"), width="small"),
                       "band": st.column_config.TextColumn(t("workspace.carriers.band"), disabled=True),
                       "f_ghz": st.column_config.NumberColumn(t("workspace.carriers.f"), min_value=0.1, max_value=400.0,
                                                              step=0.1, format="%.3g"),
                       "b_mhz": st.column_config.NumberColumn(t("workspace.carriers.b"), min_value=0.1, max_value=5000.0,
                                                              step=1.0, format="%.4g"),
                       "state": st.column_config.TextColumn(t("workspace.carriers.state"), disabled=True)})
    c1, c2 = st.columns([1, 1.3], vertical_alignment="bottom")
    c1.number_input(t("workspace.carriers.equal_bw"), 0.1, 5000.0, value=100.0, step=10.0, key="w_eq_bw")
    c2.button(t("workspace.carriers.equal_button"), on_click=on_equal_bandwidth, width="stretch",
              help=t("workspace.carriers.equal_help"))
    st.button(t("workspace.carriers.reset"), on_click=on_reset_carriers, width="stretch")
    if car is not None:
        note(t("workspace.settings.carrier", f=ui.ltr(f"{car['frequency_hz'] / 1e9:g} GHz"),
               b=ui.ltr(f"{car['bandwidth_hz'] / 1e6:g} MHz")) + " · " + ui.scenario_status(car)
             + (" " + t("common.candidate_6g_note") if car["preset"].startswith("c6g") else "")
             + (" " + t("workspace.carriers.custom_note") if car.get("custom") else ""))

    h("workspace.settings.new_station", "trace")
    c1, c2 = st.columns(2)
    c1.number_input(t("workspace.fields.mast"), 0.0, 30.0, step=0.5, key="w_t_mast", format="%.1f")
    c2.number_input(t("workspace.fields.sectors"), 1, 6, step=1, key="w_t_sectors")
    c1.number_input(t("workspace.fields.azimuth"), 0.0, 359.9, step=5.0, key="w_t_az", format="%.1f",
                    help=t("workspace.fields.azimuth_help"))
    c2.number_input(t("workspace.fields.downtilt"), -10.0, 30.0, step=1.0, key="w_t_tilt", format="%.1f")
    st.toggle(t("workspace.fields.allow_hypothetical"), key="w_t_allow", help=t("workspace.fields.allow_help"))
    if SS.w_t_allow:
        st.number_input(t("workspace.fields.hyp_height"), min_value=1.0, max_value=300.0, step=1.0, key="w_t_hyp",
                        placeholder=t("workspace.fields.hyp_placeholder"))
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
    st.number_input(t("simulation.params.noise_figure_db"), 0.0, 20.0, step=0.5, key="w_r_nf", format="%.1f")

    h("workspace.settings.resolution", "trace")
    st.segmented_control(t("workspace.fields.profile"), ["preview", "standard", "custom"], key="w_profile",
                         on_change=on_profile_change, format_func=lambda p: t(f"workspace.profiles.{p}"))
    if profile() == "custom":
        c1, c2 = st.columns(2)
        c1.number_input(t("simulation.params.cell_size_m"), 2.0, 50.0, step=1.0, key="w_cell", format="%.1f")
        c2.number_input(t("simulation.params.rays_per_site"), int(1e6), int(1e10), step=int(1e8), key="w_rays")
    per, basis = wr.expected_trace_seconds(CACHE, [sj.job for js in design_jobs.values() for sj in js][:1])
    note(t("workspace.settings.profile_facts", cell=ui.ltr(f"{exp.profile.cell_size_m:g} m"),
           rays=ui.ltr(f"{exp.profile.rays_per_site:.0e}"), cells=int(exp.outdoor.sum()),
           status=t(f"workspace.profile_status.{profile()}"))
         + (" " + t("workspace.settings.per_trace", s=f"{per:.0f}") if per else " " + t("workspace.settings.no_timing")))
    st.segmented_control(t("simulation.backend"), ["cpu", "gpu"], key="w_backend",
                         format_func=lambda b: t(f"simulation.backends.{b}"), help=t("simulation.backend_help"))

    with st.expander(t("workspace.settings.advanced")):
        st.number_input(t("simulation.params.rain_rate_mm_h"), 0.0, 200.0, step=1.0, key="w_r_rain", format="%.1f",
                        help=t("workspace.fields.rain_help"))
        m = exp.config.mechanisms
        note(t("workspace.settings.mechanisms", depth=m.max_depth,
               refl=t("workspace.yes") if m.specular_reflection else t("workspace.no"),
               diff=t("workspace.yes") if m.diffraction else t("workspace.no")))
        rule = exp.candidate_rule
        pos = exp.site_rule.get("antenna_position")
        note(t("workspace.settings.site_rule", height=f"{rule['min_roof_height_m']:g}", area=f"{rule['min_roof_area_m2']:g}",
               spacing=f"{rule['min_spacing_m']:g}",
               position=t(f"planning.positions.{pos}") if tr.has(f"planning.positions.{pos}") else pos))
    st.button(t("workspace.settings.reset_baseline"), on_click=on_reset_baseline, width="stretch",
              help=t("workspace.settings.reset_baseline_help"))

    h("workspace.settings.stations")
    candidates = ws.rule_candidates(ctx)
    c1, c2 = st.columns([1, 1.4])
    n = c1.number_input(t("workspace.fields.rule_count"), 1, max(len(candidates), 1), min(4, max(len(candidates), 1)),
                        key="w_rule_n", label_visibility="collapsed")
    if c2.button(t("workspace.settings.rule_roofs", n=len(candidates)), disabled=not candidates, width="stretch",
                 help=t("workspace.settings.rule_roofs_help")):
        tp = template(ctx)
        SS.w_stations = [ws.from_candidate(ctx, c, tp, f"S{i + 1}") for i, c in enumerate(candidates[:int(n)])]
        SS.w_sel = {}
        st.rerun()
    runs = [p for p in saved_runs() if ui.run(p).manifest["area"]["name"] == SS.w_area]
    if runs:
        st.selectbox(t("workspace.settings.saved_run"), runs, key="w_run_pick", format_func=lambda p: ui.run_title(ui.run(p)))
        st.button(t("workspace.settings.open_run"), width="stretch", on_click=on_open_run,
                  help=t("workspace.settings.open_run_help"))
    if st.button(t("workspace.settings.clear"), disabled=not stations, width="stretch"):
        SS.w_stations, SS.w_sel = [], {}
        st.rerun()

# ================================================================ map (centre)
with centre:
    if ids:
        st.segmented_control(t("common.scenario"), ids, key="w_band", width="stretch",
                             format_func=lambda i: carrier_name(next(c for c in carriers if c["id"] == i)),
                             label_visibility="collapsed")
    else:
        st.warning(t("workspace.carriers.none_selected"))
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
                                            rate_max, ui.lang()], default=str).encode()).hexdigest()[:16]

    heights = [b.height.height_m for b in exp.buildings]
    sel = dict(SS.w_sel)
    pos_cache = {s.station_id: ws.sector_positions(ctx, s, ws.antennas(s, exp.config.polarization)) for s in stations}
    station_items = [{
        "id": s.station_id, "label": s.station_id + ("" if s.enabled else f" ({t('workspace.off')})"),
        "x": s.x, "y": s.y, "mount": s.mount, "enabled": s.enabled, "colour": colour(s.station_id),
        "bearings": list(s.bearings_deg), "sectors_xy": [[p[0], p[1]] for p in pos_cache[s.station_id]][:len(s.bearings_deg)],
        "hover": t(f"workspace.hover_{s.mount}", station=s.station_id, building=s.building_id or "",
                   height=f"{s.antenna_height_m:g}", power=f"{s.tx_power_dbm:g}")} for s in stations]
    texts = {k: t(f"workspace.map.{k}") for k in ("select", "place", "move", "measure", "fit", "tip_select", "tip_place",
                                                   "tip_move", "tip_measure", "tip_fit", "hint_select", "hint_move",
                                                   "hint_measure", "stale_short", "no_path", "indoor", "stale")}
    texts["hint_place"] = t("workspace.map.hint_place_hyp" if SS.w_t_allow else "workspace.map.hint_place")
    data = {
        "geometry_rev": f"{SS.w_area}/{SS.w_variant}", "buildings": building_payload(SS.w_area, SS.w_variant),
        "bounds": list(exp.area.clip_box().bounds), "receiver": list(exp.area.receiver_box().bounds),
        "building_fill": SS.w_fill, "raster": raster, "raster_rev": raster_rev,
        "height_scale": {"vmin": 0.0, "vmax": float(np.percentile(heights, 99)) if heights else 1.0,
                         "colors": HEIGHT_COLOURS, "title": t("workspace.legend.height")},
        "category_colors": ui.CATEGORY_COLOURS, "category_title": t("workspace.legend.category"),
        "category_labels": {k: category_name(k) for k in ui.CATEGORY_COLOURS},
        "candidates": [{"x": c.x, "y": c.y} for c in candidates] if SS.w_cands else [],
        "stations": station_items, "selected": sel, "texts": texts, "rtl": tr.rtl, "height": 700,
        "mode_request": SS.w_mode_req,
        "legend_note": t("workspace.legend.wedges") if stations and raster is None else "",
    }
    MAP = st.components.v2.component("bns_network_map", js=(COMPONENT_DIR / "network_map.js").read_text(encoding="utf-8"),
                                     css=(COMPONENT_DIR / "network_map.css").read_text(encoding="utf-8"))
    result = MAP(data=data, key="w_map", on_event_change=on_map_event, height=700)
    if result is not None and result.get("event") and result["event"].get("n") != SS.w_seen:
        handle(result["event"])                     # the callback did not see it: apply and redraw
        st.rerun()

    # ------------------------------------------------------------ comparison (same layer, same scale)
    with st.expander(t("workspace.compare.title"), expanded=False):
        tab_bands, tab_configs = st.tabs([t("workspace.compare.bands"), t("workspace.compare.configs")])
        with tab_bands:
            ready = {k: e for k, e in evals.items() if e is not None}
            if not ready:
                st.caption(t("workspace.compare.none"))
            else:
                cl = layer if layer in CONTINUOUS else "sinr_db"
                order = [c["id"] for c in carriers if c["id"] in ready]
                by_id = {c["id"]: c for c in carriers}
                fig = make_subplots(rows=1, cols=len(order), shared_yaxes=True, horizontal_spacing=0.01,
                                    subplot_titles=[f"{by_id[k]['frequency_hz'] / 1e9:g} GHz" for k in order])
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
                half = exp.grid.cell_size_m / 2        # the same extent in every map
                fig.update_xaxes(range=[exp.grid.x_centers[0] - half, exp.grid.x_centers[-1] + half], constrain="domain")
                fig.update_yaxes(range=[exp.grid.y_centers[0] - half, exp.grid.y_centers[-1] + half], constrain="domain")
                fig.update_layout(height=260, margin=dict(l=4, r=4, t=30, b=4), plot_bgcolor="#e9e8e3")
                fig.update_annotations(font_size=12)
                ui.chart(fig)
                st.caption(t("workspace.compare.same_scale", layer=t(f"workspace.layers.{cl}")))
                table = []
                for c in carriers:
                    e = evals.get(c["id"])
                    s_ = e.summary if e else {}
                    table.append({t("common.scenario"): carrier_name(c),
                                  t("coverage.metrics.coverage"): None if not e else round(100 * s_["coverage_fraction"], 1),
                                  t("workspace.metrics.rx_median"): None if not e else ui.fmt(s_["rx_power_dbm_median"], ".1f"),
                                  t("coverage.metrics.sinr_median"): None if not e else ui.fmt(s_["sinr_db_median"], ".1f"),
                                  t("workspace.metrics.rate_median"): None if not e else ui.fmt(s_["rate_median_bps"], ".0f", "", 1e-6),
                                  t("workspace.metrics.rate_p5"): None if not e else ui.fmt(s_["rate_p5_bps"], ".1f", "", 1e-6),
                                  t("workspace.metrics.mapped_p5"): None if not e or s_.get("rate_3gpp_p5_bps") is None
                                  else ui.fmt(s_["rate_3gpp_p5_bps"], ".1f", "", 1e-6),
                                  t("workspace.compare.state"): t("workspace.state.current") if e else
                                  t("workspace.compare.needs", n=status[c["id"]].missing if c["id"] in status else 0)})
                st.dataframe(table, hide_index=True, width="stretch")
                st.caption(t("workspace.compare.rates_note"))
        with tab_configs:
            st.caption(t("workspace.compare.configs_note"))
            if st.button(t("workspace.compare.pin"), disabled=not any(evals.values())):
                SS.w_ref = {"label": t("workspace.compare.reference_label", n=len(enabled)), "grid": exp.grid,
                            "evals": {k: e for k, e in evals.items() if e is not None},
                            "stations": [s.station_id for s in enabled]}
                st.rerun()
            ref = SS.w_ref
            if ref:
                table = []
                for c in carriers:
                    a, b = ref["evals"].get(c["id"]), evals.get(c["id"])
                    if a is None or b is None:
                        continue
                    table.append({t("common.scenario"): carrier_name(c),
                                  t("workspace.compare.cov_ref"): round(100 * a.summary["coverage_fraction"], 1),
                                  t("workspace.compare.cov_now"): round(100 * b.summary["coverage_fraction"], 1),
                                  t("workspace.compare.sinr_ref"): ui.fmt(a.summary["sinr_db_median"], ".1f"),
                                  t("workspace.compare.sinr_now"): ui.fmt(b.summary["sinr_db_median"], ".1f"),
                                  t("workspace.compare.p5_ref"): ui.fmt(a.summary["rate_p5_bps"], ".1f", "", 1e-6),
                                  t("workspace.compare.p5_now"): ui.fmt(b.summary["rate_p5_bps"], ".1f", "", 1e-6)})
                st.markdown(f"**{ref['label']}** ({ui.ltr(', '.join(ref['stations']))})", unsafe_allow_html=True)
                if table:
                    st.dataframe(table, hide_index=True, width="stretch")
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
                                              band=carrier_name(car) if car else ""), yaxis=dict(scaleanchor="x"))
                    ui.chart(fig)
                elif a is not None and b is not None:
                    st.warning(t("workspace.compare.not_comparable"))

# ================================================================ results, run and inspector (end side)
with right, st.container(height=PANEL_HEIGHT, border=False):
    n_missing = status[sid].missing if sid in status else 0
    if not enabled:
        state_kind, state_text = "empty", t("workspace.state.no_stations")
    elif not carriers:
        state_kind, state_text = "empty", t("workspace.carriers.none_selected")
    elif active is not None:
        state_kind, state_text = "running", t("workspace.state.running")
    elif shown is not None:
        state_kind, state_text = "current", t("workspace.state.current_band", band=carrier_name(car))
    else:
        state_kind, state_text = "stale", t("workspace.state.stale" if stale else "workspace.state.not_simulated",
                                            n=n_missing)
    h("workspace.results.title")
    st.markdown(f'<div class="ws-state {state_kind}">{state_text}</div>', unsafe_allow_html=True)

    if enabled and carriers:
        c = ws.classify(ctx, stations, rad, carriers)
        head, details = i18n.classification_texts(tr, c)
        place_key = {"Automatic placement": "automatic", "Manual placement": "manual",
                     "Hypothetical placement": "hypothetical"}.get(c.placement)
        st.markdown(f'<div class="ws-class"><b>{head}</b>'
                    + (f" · {t('cls.placements.' + place_key)}" if place_key else "") + "</div>", unsafe_allow_html=True)
        with st.popover(t("workspace.results.class_details"), width="stretch"):
            st.markdown(details, unsafe_allow_html=True)
            if c.deviations:
                st.markdown(t("workspace.results.deviations"))
                st.markdown("\n".join(f"- {i18n.deviation_text(tr, d)}" for d in c.deviations))
            notes = ui.limitation_texts([x for x in ex.limitation_items(exp) if x[0] != "limitations.deviations"])
            if notes:
                st.markdown(t("simulation.limitations"))
                st.markdown("\n".join(f"- {x}" for x in notes))

    ev = shown if shown is not None else (previous or {}).get("eval")
    if ev is not None:
        import html as _html

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
                 t("workspace.metrics.mapped_note")),
                ("workspace.metrics.interference_limited", ui.fmt(s_.get("interference_limited_share"), ".0%"), ""),
                ("workspace.metrics.stations", f"{len(ev.station_ids)} · {s_['sectors']} {t('workspace.metrics.sectors')}", ""),
                ("workspace.metrics.duration", t("workspace.metrics.trace_time", s=f"{ev.trace_seconds:.0f}"),
                 t("workspace.metrics.duration_note"))]
        body = "".join(f'<tr title="{_html.escape(n_, quote=True)}"><td>{t(k)}</td><td class="v">{ui.ltr(v)}</td></tr>'
                       for k, v, n_ in rows)
        st.markdown(f'<table class="ws-m {"stale" if stale else ""}">{body}</table>', unsafe_allow_html=True)
        note(t("workspace.metrics.footnote", thr=f"{ev.radio.coverage_threshold:g}")
             + (" " + t("workspace.metrics.approximation") if s_.get("rate_3gpp_caveat") else ""))
        if stale:
            note(t("workspace.results.stale_note"))

    # ------------------------------------------------------------ simulation
    h("workspace.run.title")
    plan_ = power_plan()
    if plan_ and plan_.get("power_saver"):
        st.warning(t("workspace.run.power_saver", name=plan_.get("name", "")))
    band_missing = list(status[sid].missing_keys) if sid in status else []
    all_missing = list(dict.fromkeys(k for s_ in status.values() for k in s_.missing_keys))

    def minutes(n: int) -> str:
        jobs_ = [sj.job for js in design_jobs.values() for sj in js]
        per_, _ = wr.expected_trace_seconds(CACHE, jobs_[:1])
        if not per_ or not n:
            return ""
        size = wr.batch_size(per_)
        workers = n if size == 1 else max(1, len(carriers))
        return t("workspace.run.estimate", m=f"{(per_ * n + workers * wr.WORKER_START_SECONDS) / 60:.1f}")

    def start(carrier_ids: list[str]) -> None:
        if SS.w_saved_sig is None or dirty:                # a run records a saved configuration
            on_save()
        SS.w_run = str(wr.start(ROOT, to_experiment().to_dict(), carrier_ids,
                                target=float(baseline_values().get("coverage_target") or 0.95)))
        SS.w_report = None

    if active is None:
        if not enabled or not carriers:
            st.caption(t("workspace.run.place_first"))
        else:
            b1, b2 = st.columns(2)
            label_all = t("workspace.run.all", n=len(all_missing)) if all_missing else t("workspace.run.save_results")
            if b1.button(label_all, type="primary", width="stretch", help=minutes(len(all_missing)) or
                         t("workspace.run.save_results_help")):
                start(ids)
                st.rerun()
            if b2.button(t("workspace.run.band", n=len(band_missing)) if band_missing else t("workspace.run.band_save"),
                         width="stretch", disabled=sid is None, help=minutes(len(band_missing)) or None):
                start([sid])
                st.rerun()
            if all_missing and minutes(len(all_missing)):
                note(t("workspace.run.estimate_note", band=minutes(len(band_missing)) or "—", all=minutes(len(all_missing))))
            note(t("workspace.run.commit_note"))

    def progress_view(folder: Path) -> None:
        s_ = wr.state(folder)
        if s_.running:
            total = max(s_.total, 1)
            cur = s_.current or {}
            what = ""
            if cur:
                cc = next((c for c in SS.w_carriers if c["id"] == cur.get("scenario")), None)
                bearing = cur.get("bearing_deg")
                what = t("workspace.run.current", band=carrier_name(cc) if cc else cur.get("scenario", ""),
                         station=cur.get("station", ""), sector=cur.get("sector", ""),
                         bearing="" if bearing is None else f" ({bearing:g}°)")
            if s_.evaluating:
                st.progress(1.0, text=t("workspace.run.evaluating"))
            else:
                st.progress(min(s_.done / total, 1.0), text=t("workspace.run.progress", done=s_.done, total=s_.total))
            w = s_.workload or {}
            remaining = s_.remaining_seconds
            lines = [what, t("workspace.run.counts", cached=w.get("cached", 0), new=w.get("to_trace", 0),
                             committed=s_.committed, left=max(s_.total - s_.committed, 0)),
                     t("workspace.run.elapsed", s=f"{s_.elapsed_seconds:.0f}")
                     + (" · " + t("workspace.run.remaining", m=f"{remaining / 60:.1f}") if remaining else ""),
                     t("workspace.run.retried", n=s_.retries) if s_.retries else ""]
            note("<br>".join(x for x in lines if x))
            if st.button(t("simulation.history.cancel"), key=f"cancel-{folder.name}",
                         help=t("workspace.run.cancel_help", committed=s_.committed)):
                wr.cancel(folder)
                st.toast(t("workspace.run.cancelling", committed=s_.committed))
        else:
            SS.w_run = None
            if s_.execution == "Completed":
                message("success", t("workspace.run.finished", n=s_.committed, s=f"{s_.wall_seconds or 0:.0f}",
                                     run=s_.output.name if s_.output else ""))
            elif s_.cancelled:
                message("warning", t("workspace.run.cancelled", committed=s_.committed))
            else:
                message("error", t("workspace.run.failed", error=s_.error or ""))
            saved_runs.clear()
            ui.run_list.clear()
            st.rerun(scope="app")

    folder = Path(SS.w_run) if SS.get("w_run") else (active.folder if active else None)
    if folder is not None:
        st.fragment(run_every=1.5)(progress_view)(folder)

    # ------------------------------------------------------------ automatic planning over the shown stations
    if len(stations) > 1 and car is not None:
        with st.expander(t("workspace.plan.title")):
            st.caption(t("planning.heuristic"))
            st.number_input(t("planning.target"), 0.5, 1.0, value=float(baseline_values().get("coverage_target") or 0.95),
                            step=0.01, key="w_r_target", format="%.2f")
            every = [replace(s, enabled=True) for s in stations]
            every_status = ws.trace_status(ws.jobs(ctx, every, [car]), Presence)
            if not every_status[sid].complete:
                st.caption(t("workspace.plan.needs", n=every_status[sid].missing))
            elif st.button(t("workspace.plan.run", band=carrier_name(car)), width="stretch"):
                g = ws.greedy(ctx, stations, car, rad, load, target=float(SS.w_r_target))
                SS.w_plan = {"band": sid, "selected": [stations[i].station_id for i in g.selected],
                             "coverage": g.coverage_after, "reached": g.target_reached, "reason": g.stopped_because}
            plan = SS.get("w_plan")
            if plan and plan["band"] == sid:
                st.markdown(t("planning.greedy_result", sites=ui.ltr(", ".join(plan["selected"])),
                              coverage=f"{plan['coverage'][-1]:.1%}",
                              reached=t("planning.reached") if plan["reached"] else t("planning.not_reached"),
                              reason="" if plan["reason"] == "target reached" else f" (*{ui.recorded(plan['reason'])}*)"),
                            unsafe_allow_html=True)
                if st.button(t("workspace.plan.keep"), width="stretch", help=t("workspace.plan.keep_help")):
                    SS.w_stations = [replace(s, enabled=s.station_id in plan["selected"],
                                             origin=ws.PLAN if s.origin != ws.MANUAL else s.origin) for s in stations]
                    st.rerun()

    # ------------------------------------------------------------ selected object
    h("workspace.inspect.title")
    if sel.get("kind") == "station" and any(s.station_id == sel["id"] for s in stations):
        s = next(x for x in stations if x.station_id == sel["id"])
        key = f"w_st_{s.station_id}_{hashlib.sha256(json.dumps(asdict(s), sort_keys=True).encode()).hexdigest()[:8]}_"
        if s.mount == ws.ROOFTOP:
            b_ = ctx.building(s.building_id)
            st.markdown('<div class="ws-obj">' + t(
                "workspace.inspect.rooftop", station=s.station_id, building=ui.ltr(s.building_id),
                roof=f"{s.roof_height_m:g}",
                category=category_name(ui.height_display_category(b_) if b_ else s.height_category),
                rule=t("workspace.inspect.rule_yes") if s.meets_site_rule else t("workspace.inspect.rule_no"))
                + "</div>", unsafe_allow_html=True)
            note(t(f"workspace.inspect.origin_{s.origin.replace(' ', '_')}"))
        else:
            st.markdown(f'<div class="ws-hyp">{t("workspace.inspect.hypothetical", station=s.station_id)}</div>',
                        unsafe_allow_html=True)
        lon, lat = exp.area.transformer().transform(s.x, s.y, direction="INVERSE")
        near = ws.nearest_station_m(s, stations)
        note(t("workspace.inspect.position", x=f"{s.x:.1f}", y=f"{s.y:.1f}", lat=f"{lat:.5f}", lon=f"{lon:.5f}")
             + ("<br>" + t("workspace.inspect.nearest", d=f"{near:.0f}", rule=f"{exp.candidate_rule['min_spacing_m']:g}")
                if near is not None else ""))

        def edit(field, value_key, convert=float, s=s, key=key):
            def apply():                            # runs before the next script run: values bound here
                value = SS[value_key]
                if field == "antenna_height_m" and s.mount == ws.ROOFTOP:
                    update_station(s.station_id, antenna_height_m=s.roof_height_m + float(value))
                elif field == "xy":
                    try:
                        moved = ws.move(current_context(), s, float(SS[key + "x"]), float(SS[key + "y"]),
                                        template(current_context()), SS.w_stations)
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
        note(t("workspace.inspect.bearings", b=ui.ltr(" / ".join(f"{b:g}°" for b in s.bearings_deg) or "—")))
        e1, e2 = st.columns(2)
        e1.toggle(t("workspace.fields.enabled"), value=s.enabled, key=key + "on", on_change=edit("enabled", key + "on", bool))
        if e2.button(t("workspace.inspect.remove"), key=key + "rm", width="stretch"):
            remove(s.station_id)
            st.rerun()
        if car is not None:
            traced = [sj.job.key() for sj in ws.jobs(ctx, [replace(s, enabled=True)], [car])[sid]]
            have = sum(Presence.has(k) for k in traced)
            note(t("workspace.inspect.traced", have=have, n=len(traced), band=carrier_name(car)))
    elif sel.get("kind") == "building":
        b = ctx.building(sel["id"])
        if b is not None:
            cat = ui.height_display_category(b)
            st.markdown('<div class="ws-obj">' + t(
                "workspace.inspect.building", building=ui.ltr(b.building_id), height=f"{b.height.height_m:.1f}",
                category=category_name(cat), area=f"{b.polygon.area:.0f}",
                rule=t("workspace.inspect.rule_yes") if ws.meets_rule(ctx, b) else t("workspace.inspect.rule_no"))
                + "</div>", unsafe_allow_html=True)
            note(t("workspace.inspect.provenance", source=ui.ltr(b.height.source), method=b.height.method))
            if cat == "synthetic":
                note(t("workspace.inspect.synthetic"))
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
            note(t("workspace.inspect.cell", x=f"{v['x']:.0f}", y=f"{v['y']:.0f}", band=carrier_name(car) if car else "")
                 + (f" · {t('workspace.map.stale_short')}" if stale else ""))
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
        picked = st.dataframe(rows, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                              key=f"w_list_{sel.get('id', '')}")
        rows_sel = picked.selection.rows if picked is not None and hasattr(picked, "selection") else []
        if rows_sel:
            SS.w_sel = {"kind": "station", "id": stations[rows_sel[0]].station_id}
            st.rerun()
    origin = SS.w_meta.get("origin") or {}
    if origin:
        k, v = next(iter(origin.items()))
        note(t(f"workspace.experiment.origin_{k}", source=ui.ltr(v)))

SS.w_store = {k: SS[k] for k in WIDGET_KEYS if k in SS}
