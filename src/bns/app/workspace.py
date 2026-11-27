"""The simulation workspace: editable stations, their propagation jobs, staleness and evaluation (no UI code).

A design is the experiment's settings (dataset, profile, backend, receiver grid) plus a list of
stations. Every enabled station becomes the same PropagationJob objects the experiment scripts
trace (bns.simulation.setup, bns.simulation.experiment), so the cache key alone decides what a
change costs:

    needs ray tracing   anything inside a job key: position, antenna height, pattern, sector
                        bearings, downtilt, number of sectors, receiver height, cell size, rays,
                        backend, dataset
    radio only          transmit power, noise figure, coverage threshold, network load, rain,
                        switching a traced station on or off: recomputed from the cached path
                        gain in NumPy (bns.simulation.network), nothing traced

Results are computed only from the cache entries of exactly the shown stations; when one is
missing the evaluation refuses (MissingTraces) instead of reusing another configuration's maps.

Placement. A station on a roof stands at the site rule's rooftop point of that building (as
experiment.place_sites) with the mast on top of the recorded roof height; whether the roof
satisfies the candidate rule is recorded, not enforced. Monuments, memorials and artworks never
host a station. A station on open ground is HYPOTHETICAL: an antenna at a height the user gives,
never an assessed installation site. Neither changes the classification rules: any departure
from the site rule or the baseline values is a recorded deviation (bns.analysis.classification).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import numpy as np
from shapely.geometry import Point

from bns.analysis import classification
from bns.analysis import metrics
from bns.app import carriers as ca
from bns.analysis import validation_scope as vs
from bns.core.units import linear_to_db
from bns.geospatial import sites
from bns.propagation import atmosphere as atm
from bns.propagation.engine_settings import engine_fingerprint
from bns.simulation import experiment as ex
from bns.simulation.cache import scene_fingerprint
from bns.simulation.jobs import Antenna, PropagationJob
from bns.simulation.network import network
from bns.simulation.radio import RadioInputs
from bns.simulation.setup import bearing_to_scene_azimuth_rad, scene_azimuth_to_bearing_deg

ROOFTOP, HYPOTHETICAL = "rooftop", "hypothetical"
MANUAL, SITE_RULE, PLAN = "manual", "site rule", "plan"      # how a station was placed
RULE_POSITION, SITE_POINT = "rule", "site point"     # where the sector antennas of a rooftop station stand


class PlacementError(ValueError):
    """A station cannot stand there. `code` (outside, monument, rooftop_only, height_needed) and `values`
    let the interface say so in its language; the message is the English diagnostic."""

    def __init__(self, code: str, message: str, **values):
        super().__init__(message)
        self.code, self.values = code, values


class MissingTraces(RuntimeError):
    """Some path gains of the shown stations are not in the cache: the result needs ray tracing."""


@dataclass(frozen=True)
class Context:
    """One loaded experiment and what every job of it shares."""

    exp: ex.Experiment
    scene_fingerprint: str
    engine: dict

    @classmethod
    def from_experiment(cls, exp: ex.Experiment) -> "Context":
        return cls(exp, scene_fingerprint(exp.scene_dir), engine_fingerprint(exp.backend))

    def building(self, building_id: str):
        return next((b for b in self.exp.buildings if b.building_id == building_id), None)


@dataclass(frozen=True)
class StationTemplate:
    """Values a new station starts with: the research baseline unless the user changed them.
    There is no baseline height for an antenna on open ground: the user must give one."""

    tx_power_dbm: float
    pattern: str
    sectors: int
    azimuth_deg: float                 # compass bearing of sector 1 (0 = north, clockwise)
    downtilt_deg: float
    mast_height_m: float               # above the roof
    hypothetical_height_m: float | None = None
    allow_hypothetical: bool = True

    @classmethod
    def baseline(cls, ctx: Context) -> "StationTemplate":
        s, mode = ctx.exp.system, ctx.exp.mode
        return cls(float(s.require("tx_power_dbm", mode=mode)), s.require("tx_antenna_pattern", mode=mode),
                   int(s.require("sectors_per_site", mode=mode)), 0.0,
                   float(s.require("mechanical_downtilt_deg", mode=mode)),
                   float(s.require("antenna_height_above_roof_m", mode=mode)))


@dataclass(frozen=True)
class Station:
    station_id: str
    x: float                           # site point, scene metres (x east, y north)
    y: float
    antenna_height_m: float            # above ground
    mount: str                         # rooftop | hypothetical
    tx_power_dbm: float                # conducted, per sector carrier (as configs/radio_system.yaml)
    pattern: str
    sectors: int
    azimuth_deg: float
    downtilt_deg: float
    building_id: str | None = None
    roof_height_m: float | None = None
    height_category: str | None = None     # of the host roof: observed / estimated / placeholder
    meets_site_rule: bool | None = None    # host roof satisfies the candidate rule (rooftops only)
    enabled: bool = True
    origin: str = MANUAL                   # manual | site rule | plan (kept by the automatic planning)
    antenna_position: str = RULE_POSITION  # rule (configs/site_rule.yaml) | site point (runs before decision A4)
    source_run: str | None = None          # the saved run the station was opened from

    @property
    def bearings_deg(self) -> tuple[float, ...]:
        if self.pattern == "iso":
            return ()
        return tuple((self.azimuth_deg + 360.0 * k / self.sectors) % 360.0 for k in range(self.sectors))

    @property
    def mast_height_m(self) -> float | None:
        return None if self.roof_height_m is None else self.antenna_height_m - self.roof_height_m


@dataclass(frozen=True)
class SectorJob:
    station: int                       # index among the enabled stations (the network's site index)
    sector: int                        # 0-based
    job: PropagationJob


@dataclass(frozen=True)
class RadioSettings:
    """Radio-system values of the design: changing them never needs ray tracing."""

    coverage_threshold: float
    interference_activity: float
    noise_figure_db: float
    rain_rate_mm_h: float

    @classmethod
    def baseline(cls, ctx: Context) -> "RadioSettings":
        v = ex.baseline_values(ctx.exp.root, ctx.exp.profile.name.removesuffix("-custom"))
        return cls(v["coverage_threshold"], v["interference_activity"], v["noise_figure_db"], v["rain_rate_mm_h"])


@dataclass(frozen=True)
class TraceStatus:
    jobs: int
    cached: int
    missing_keys: tuple[str, ...]

    @property
    def missing(self) -> int:
        return len(self.missing_keys)

    @property
    def complete(self) -> bool:
        return self.jobs > 0 and not self.missing_keys


@dataclass
class Evaluation:
    scenario_id: str
    layers: dict                       # name -> [y, x] array (same names as the saved runs)
    summary: dict
    station_ids: list[str]             # serving_station index -> station id
    sectors: list[tuple[str, int]]     # serving_sector index -> (station id, sector number from 1)
    trace_seconds: float               # recorded trace time of the path gains used
    job_keys: tuple[str, ...]
    radio: RadioSettings
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- stations
def next_id(stations: list[Station]) -> str:
    used = {s.station_id for s in stations}
    n = 1
    while f"S{n}" in used:
        n += 1
    return f"S{n}"


def host_building(ctx: Context, x: float, y: float):
    p = Point(x, y)
    return next((b for b in ctx.exp.buildings if b.polygon.covers(p)), None)


def meets_rule(ctx: Context, b) -> bool:
    rule = ctx.exp.candidate_rule
    return (not sites.is_structure_not_building(b.tags or {}) and b.height.height_m >= rule["min_roof_height_m"]
            and b.polygon.area >= rule["min_roof_area_m2"] and b.height.category in rule["categories"])


def _station_at(ctx: Context, x: float, y: float, template: StationTemplate, station_id: str,
                origin: str) -> Station:
    hx, hy = ctx.exp.area.half_extent_m
    if not (-hx <= x <= hx and -hy <= y <= hy):
        raise PlacementError("outside", f"({x:.0f}, {y:.0f}) m is outside the scene (±{hx:g} m × ±{hy:g} m).",
                             x=round(x), y=round(y), hx=hx, hy=hy)
    common = dict(tx_power_dbm=template.tx_power_dbm, pattern=template.pattern, sectors=template.sectors,
                  azimuth_deg=template.azimuth_deg, downtilt_deg=template.downtilt_deg, origin=origin)
    b = host_building(ctx, x, y)
    if b is not None:
        if sites.is_structure_not_building(b.tags or {}):
            raise PlacementError("monument", f"{b.building_id} is a monument, memorial or artwork: never a "
                                 "transmitter site.", building=b.building_id)
        [c] = sites.rooftop_candidates([b], mast_height_m=template.mast_height_m, min_height_m=0.0,
                                       min_area_m2=0.0, min_spacing_m=0.0, max_candidates=1)
        return Station(station_id, c.x, c.y, c.z, ROOFTOP, building_id=b.building_id,
                       roof_height_m=c.roof_height_m, height_category=c.height_category,
                       meets_site_rule=meets_rule(ctx, b), **common)
    if not template.allow_hypothetical:
        raise PlacementError("rooftop_only", "Open ground: only rooftop stations are allowed (hypothetical "
                             "placement is off).")
    if template.hypothetical_height_m is None or template.hypothetical_height_m <= 0:
        raise PlacementError("height_needed", "Open ground: give the antenna height above ground for a "
                             "hypothetical station.")
    return Station(station_id, float(x), float(y), float(template.hypothetical_height_m), HYPOTHETICAL, **common)


def place(ctx: Context, x: float, y: float, template: StationTemplate, stations: list[Station],
          origin: str = MANUAL) -> Station:
    """A new station at (x, y): on a roof, at its rooftop point; on open ground, hypothetical."""
    return _station_at(ctx, x, y, template, next_id(stations), origin)


def move(ctx: Context, station: Station, x: float, y: float, template: StationTemplate,
         stations: list[Station]) -> Station:
    """The station at a new point, keeping its radio and antenna values. On open ground a moved station
    keeps its antenna height if it was hypothetical; a rooftop station needs the template's height."""
    keep = StationTemplate(station.tx_power_dbm, station.pattern, station.sectors, station.azimuth_deg,
                           station.downtilt_deg,
                           station.mast_height_m if station.mast_height_m is not None else template.mast_height_m,
                           station.antenna_height_m if station.mount == HYPOTHETICAL else template.hypothetical_height_m,
                           template.allow_hypothetical)
    moved = _station_at(ctx, x, y, keep, station.station_id, MANUAL)
    return replace(moved, enabled=station.enabled)


def rebind(ctx: Context, stations: list[Station], template: StationTemplate) -> tuple[list[Station], list[str]]:
    """The stations on another dataset of the same area: a rooftop station keeps its mast on the roof of
    the same building there (its new height and category); one whose building is missing is dropped."""
    kept, dropped = [], []
    for s in stations:
        if s.mount != ROOFTOP:
            kept.append(s)
            continue
        b = ctx.building(s.building_id)
        if b is None or sites.is_structure_not_building(b.tags or {}):
            dropped.append(s.station_id)
            continue
        mast = s.mast_height_m if s.mast_height_m is not None else template.mast_height_m
        [c] = sites.rooftop_candidates([b], mast_height_m=mast, min_height_m=0.0, min_area_m2=0.0,
                                       min_spacing_m=0.0, max_candidates=1)
        kept.append(replace(s, x=c.x, y=c.y, antenna_height_m=c.z, roof_height_m=c.roof_height_m,
                            height_category=c.height_category, meets_site_rule=meets_rule(ctx, b)))
    return kept, dropped


def from_candidate(ctx: Context, c: sites.Candidate, template: StationTemplate, station_id: str) -> Station:
    b = ctx.building(c.building_id)
    return Station(station_id, c.x, c.y, c.z, ROOFTOP, template.tx_power_dbm, template.pattern, template.sectors,
                   template.azimuth_deg, template.downtilt_deg, building_id=c.building_id,
                   roof_height_m=c.roof_height_m, height_category=c.height_category,
                   meets_site_rule=meets_rule(ctx, b) if b is not None else None, origin=SITE_RULE)


def rule_candidates(ctx: Context) -> list[sites.Candidate]:
    """Every receiver-area roof the site rule accepts (tallest first, with the rule's spacing)."""
    return ex.observed_sites(ctx.exp, None)


def antennas(station: Station, polarization: str) -> list[Antenna]:
    """The station's traced antennas, as bns.simulation.setup.sector_antennas describes a site."""
    if station.pattern == "iso":
        return [Antenna("iso", polarization, (0.0, 0.0, 0.0))]
    tilt = float(np.radians(station.downtilt_deg))
    return [Antenna(station.pattern, polarization, (bearing_to_scene_azimuth_rad(b), tilt, 0.0))
            for b in station.bearings_deg]


def sector_positions(ctx: Context, station: Station, ants: list[Antenna]) -> list[tuple[float, float, float]]:
    """Antenna position of every sector (experiment.sector_positions): at the roof edge facing the
    sector when the site rule says so, else the station point. Hypothetical stations use the point."""
    rule = ctx.exp.site_rule
    point = (station.x, station.y, station.antenna_height_m)
    if (station.mount != ROOFTOP or station.antenna_position == SITE_POINT or rule.get("antenna_position") != "roof_edge"
            or station.pattern == "iso"):
        return [point] * len(ants)
    roof = ctx.building(station.building_id).polygon
    xy = sites.edge_positions(roof, station.x, station.y, [a.orientation_rad[0] for a in ants],
                              float(rule["edge_inset_m"]))
    return [(x, y, station.antenna_height_m) for x, y in xy]


def preset_carriers(ctx: Context) -> list[dict]:
    """The five scenario presets of the experiment, as carriers (bns.app.carriers)."""
    return [{"id": sc["id"], "label": sc["label"], "frequency_hz": float(sc["frequency_hz"]),
             "bandwidth_hz": float(sc["bandwidth_hz"]), "status": sc.get("status", ""), "preset": sc["id"],
             "custom": False, "gas": ca.TABULATED} for sc in ctx.exp.scenarios]


def jobs(ctx: Context, stations: list[Station], carriers: list[dict] | None = None) -> dict[str, list[SectorJob]]:
    """Per carrier (default: the five presets): one job per sector of every enabled station, as
    bns.simulation.setup.site_jobs describes it. Only the frequency of a carrier enters a job."""
    exp = ctx.exp
    enabled = [s for s in stations if s.enabled]
    geometry = []
    for s in enabled:
        ants = antennas(s, exp.config.polarization)
        geometry.append(list(zip(ants, sector_positions(ctx, s, ants), strict=True)))
    out = {}
    for sc in carriers if carriers is not None else preset_carriers(ctx):
        out[sc["id"]] = [SectorJob(i, k, PropagationJob(ctx.scene_fingerprint, str(exp.scene_dir), sc["frequency_hz"],
                                                        tuple(float(v) for v in pos), antenna, exp.grid,
                                                        exp.config.mechanisms, int(exp.profile.rays_per_site),
                                                        exp.config.seeds, ctx.engine))
                         for i, g in enumerate(geometry) for k, (antenna, pos) in enumerate(g)]
    return out


def job_labels(design_jobs: dict[str, list[SectorJob]], stations: list[Station]) -> dict[str, dict]:
    """Job key -> what it traces (band, station, sector, bearing), for progress reports."""
    enabled = [s for s in stations if s.enabled]
    out = {}
    for sid, js in design_jobs.items():
        for sj in js:
            s = enabled[sj.station]
            bearing = s.bearings_deg[sj.sector] if s.bearings_deg else None
            out[sj.job.key()] = {"scenario": sid, "station": s.station_id, "sector": sj.sector + 1,
                                 "bearing_deg": None if bearing is None else round(bearing, 1)}
    return out


def trace_status(design_jobs: dict[str, list[SectorJob]], cache) -> dict[str, TraceStatus]:
    out = {}
    for sid, js in design_jobs.items():
        unique = list(dict.fromkeys(sj.job.key() for sj in js))
        missing = tuple(k for k in unique if not cache.has(k))
        out[sid] = TraceStatus(len(unique), len(unique) - len(missing), missing)
    return out


# ---------------------------------------------------------------- radio-system evaluation
def radio_scenario(ctx: Context, carrier: dict) -> dict:
    """The preset under which the carrier's radio values and rate mapping are looked up, with the
    carrier's bandwidth (bns.app.carriers)."""
    preset = next(sc for sc in ctx.exp.scenarios if sc["id"] == carrier.get("preset", carrier["id"]))
    return {**preset, "bandwidth_hz": float(carrier["bandwidth_hz"])}


def radio_inputs(ctx: Context, stations: list[Station], scenario: dict, radio: RadioSettings) -> RadioInputs:
    """The experiment's radio inputs with the design's radio values and one power per sector. The
    power added to the traced path gain follows RadioSystem.tx_power_for_path_gain_dbm: for a traced
    pattern no antenna gain is added (its gain is inside the path gain). `scenario` is a carrier;
    its preset gives the radio values, its bandwidth the noise."""
    exp = ctx.exp
    scenario = radio_scenario(ctx, scenario)
    sid = scenario["id"]
    base = ex.radio_inputs(exp, scenario)
    gain_term = exp.system.tx_power_for_path_gain_dbm(sid, mode=exp.mode) - exp.system.require("tx_power_dbm", sid,
                                                                                              mode=exp.mode)
    powers = [s.tx_power_dbm + gain_term for s in stations if s.enabled for _ in antennas(s, exp.config.polarization)]
    return replace(base, tx_power_dbm=np.asarray(powers, dtype=float)[:, None, None],
                   coverage_threshold=float(radio.coverage_threshold),
                   interference_activity=float(radio.interference_activity),
                   noise_figure_db=float(radio.noise_figure_db))


def loss_db(ctx: Context, scenario: dict, station: Station, radio: RadioSettings) -> np.ndarray:
    """Gas (and, in a rain case, rain) loss from the station point to every cell (as the run scripts).
    Gas loss is the tabulated value, or none where a custom carrier records it as omitted."""
    exp = ctx.exp
    f = float(scenario["frequency_hz"])
    gas = ca.gas_db_per_km({"gas": ca.TABULATED, **scenario}) if exp.baseline.include_gas else 0.0
    gamma = gas + atm.rain_specific_attenuation_db_per_km(f, float(radio.rain_rate_mm_h), exp.config.polarization)
    return atm.attenuation_map_db((station.x, station.y, station.antenna_height_m), exp.grid, gamma)


def _network_inputs(ctx: Context, stations: list[Station], scenario: dict, radio: RadioSettings, load):
    """Path-gain stack [sector, y, x] of the enabled stations, sector -> station, losses and radio inputs."""
    sid = scenario["id"]
    enabled = [s for s in stations if s.enabled]
    if not enabled:
        raise ValueError("No enabled station.")
    js = jobs(ctx, stations, [scenario])[sid]
    entries = [load(sj.job.key()) for sj in js]
    missing = [sj.job.key() for sj, e in zip(js, entries, strict=True) if e is None]
    if missing:
        raise MissingTraces(f"{len(missing)} of {len(js)} path gains of {sid} are not in the cache.")
    stack = np.stack([e[0] for e in entries])
    sector_site = np.array([sj.station for sj in js])
    loss = np.stack([loss_db(ctx, scenario, enabled[sj.station], radio) for sj in js])
    return js, entries, stack, sector_site, loss, radio_inputs(ctx, stations, scenario, radio)


def evaluate(ctx: Context, stations: list[Station], scenario: dict, radio: RadioSettings, load) -> Evaluation:
    """Network results of the enabled stations in one band, from cached path gain only.

    `load(key)` returns (path gain, cache manifest) or None (PathGainCache.get)."""
    exp, sid = ctx.exp, scenario["id"]
    enabled = [s for s in stations if s.enabled]
    js, entries, stack, sector_site, loss, inputs = _network_inputs(ctx, stations, scenario, radio, load)
    net = network(stack, sector_site, exp.outdoor, inputs, loss)
    layers = {"path_gain_db": linear_to_db(stack.max(axis=0)), "rx_power_dbm": net.radio.rx_power_dbm,
              "sinr_db": net.radio.sinr_db, "rate_bps": net.radio.rate_bps, "covered": net.radio.covered,
              "serving_station": net.serving_site, "serving_sector": net.serving_sector,
              "interference_dbm": net.interference_dbm}
    summary = {**net.summary, "noise_dbm": net.radio.noise_dbm}
    mapped = ex.mapped_rate_bps(exp, radio_scenario(ctx, scenario), net.radio.sinr_db)
    if mapped is not None:
        model = ex.rate_mapping(exp, radio_scenario(ctx, scenario))
        layers["rate_3gpp_bps"] = mapped
        summary.update(rate_3gpp_p5_bps=metrics.percentile(mapped, 5, exp.outdoor),
                       rate_3gpp_median_bps=metrics.percentile(mapped, 50, exp.outdoor),
                       rate_3gpp_model=model.describe(), rate_3gpp_caveat=bool(model.caveat))
    seconds = sum(float((e[1] or {}).get("seconds") or 0.0) for e in entries)
    return Evaluation(sid, layers, summary, [s.station_id for s in enabled],
                      [(enabled[sj.station].station_id, sj.sector + 1) for sj in js], seconds,
                      tuple(sj.job.key() for sj in js), radio)


def greedy(ctx: Context, stations: list[Station], scenario: dict, radio: RadioSettings, load, *, target: float,
           max_sites: int | None = None):
    """The project's interference-aware SINR greedy (bns.optimization.greedy) over the shown stations: which
    of them, added one at a time, give the highest network coverage. Indices refer to `stations` (all of
    them are candidates, switched-off ones included). A heuristic over these stations only."""
    from bns.optimization.greedy import greedy_sinr_site_selection

    every = [replace(s, enabled=True) for s in stations]
    _, _, stack, sector_site, loss, inputs = _network_inputs(ctx, every, scenario, radio, load)

    def coverage_of(selection):
        keep = np.isin(sector_site, selection)
        remap = {site: k for k, site in enumerate(sorted(selection))}
        sub = replace(inputs, tx_power_dbm=inputs.tx_power_dbm[keep])
        return network(stack[keep], np.array([remap[i] for i in sector_site[keep]]), ctx.exp.outdoor, sub,
                       loss[keep]).radio.summary["coverage_fraction"]

    return greedy_sinr_site_selection(coverage_of, len(every), target, max_sites)


# ---------------------------------------------------------------- classification
def deviations(ctx: Context, stations: list[Station]) -> list[str]:
    """How the stations depart from the site rule and the research-baseline values (English, recorded)."""
    base = StationTemplate.baseline(ctx)
    out = []
    for s in (s for s in stations if s.enabled):
        if s.mount == HYPOTHETICAL:
            out.append(f"{s.station_id} hypothetical location (not a rooftop site)")
        elif not s.meets_site_rule:
            out.append(f"{s.station_id} on {s.building_id}, a roof outside the candidate rule")
        for name, value, ref in (("tx_power_dbm", s.tx_power_dbm, base.tx_power_dbm),
                                 ("mechanical_downtilt_deg", s.downtilt_deg, base.downtilt_deg),
                                 ("sectors_per_site", s.sectors, base.sectors),
                                 ("antenna_height_above_roof_m", s.mast_height_m, base.mast_height_m)):
            if value is not None and not np.isclose(float(value), float(ref), rtol=0, atol=1e-9):
                out.append(f"{s.station_id} {name} = {value:g}")
        if (s.mount == ROOFTOP and s.antenna_position == SITE_POINT
                and ctx.exp.site_rule.get("antenna_position") == "roof_edge"):
            out.append(f"{s.station_id} antennas at the site point (site rule: roof edge)")
        if s.pattern != base.pattern:
            out.append(f"{s.station_id} tx_antenna_pattern = {s.pattern}")
        if not np.isclose(s.azimuth_deg % 360.0, 0.0, atol=1e-9) and s.pattern != "iso":
            out.append(f"{s.station_id} sector bearings {'/'.join(f'{b:g}' for b in s.bearings_deg)}°")
    return out


def placement(stations: list[Station]) -> str:
    """How the transmitting stations were placed (a classification dimension of its own): hypothetical
    if any stands on open ground, manual if any was placed or moved by hand, else automatic (site rule
    or automatic planning). Manual placement on a rule roof keeps the baseline parameter class."""
    on = [s for s in stations if s.enabled]
    if any(s.mount == HYPOTHETICAL for s in on):
        return classification.HYPOTHETICAL_PLACEMENT
    if any(s.origin == MANUAL for s in on):
        return classification.MANUAL_PLACEMENT
    return classification.AUTOMATIC_PLACEMENT


def radio_overrides(ctx: Context, radio: RadioSettings) -> dict:
    base = RadioSettings.baseline(ctx)
    return {k: getattr(radio, k) for k in ("coverage_threshold", "interference_activity", "noise_figure_db",
                                           "rain_rate_mm_h")
            if not np.isclose(float(getattr(radio, k)), float(getattr(base, k)), rtol=0, atol=1e-9)}


def classify(ctx: Context, stations: list[Station], radio: RadioSettings,
             carriers: list[dict] | None = None) -> classification.Classification:
    """The design's scientific classification, by the rules every run uses, with its placement."""
    exp = ctx.exp
    overrides = {**{k: v for k, v in exp.overrides.items() if k in ("rx_height_m", "cell_size_m", "rays_per_site")},
                 **radio_overrides(ctx, radio)}
    devs = (ex.baseline_deviations(exp.root, exp.profile, exp.backend) + deviations(ctx, stations)
            + ca.deviations(carriers or []))
    ants = [a for s in stations if s.enabled for a in antennas(s, exp.config.polarization)]
    from dataclasses import asdict

    scope = vs.scope(scene_fingerprint=ctx.scene_fingerprint, grid=asdict(exp.grid),
                     rays_per_site=exp.profile.rays_per_site, engine=ctx.engine,
                     antennas=[asdict(a) for a in ants], mechanisms=asdict(exp.config.mechanisms),
                     seeds=exp.config.seeds)
    return classification.classify(exp.root, overrides, exp.quality, study_district=exp.area.is_research_dataset,
                                   deviations=devs, scope=scope, profile=exp.profile.name,
                                   placement=placement(stations))


# ---------------------------------------------------------------- saved runs
def run_settings(manifest: dict) -> dict:
    """Area, variant, profile, backend and grid-changing overrides of a saved run (to load its experiment)."""
    overrides = manifest.get("overrides") or {}
    return {"area": manifest["area"]["name"], "variant": manifest["area"].get("variant", "osm"),
            "profile": manifest["profile"]["name"].removesuffix("-custom"),
            "backend": (manifest.get("backend") or {}).get("name", "cpu"),
            "overrides": {k: v for k, v in overrides.items() if k in ("rx_height_m", "cell_size_m", "rays_per_site")}}


def run_radio(ctx: Context, manifest: dict) -> RadioSettings:
    base = RadioSettings.baseline(ctx)
    o = {**(manifest.get("overrides_for_sensitivity") or {}), **(manifest.get("overrides") or {})}
    return RadioSettings(*(float(o.get(k, getattr(base, k))) for k in ("coverage_threshold", "interference_activity",
                                                                     "noise_figure_db", "rain_rate_mm_h")))


def stations_from_run(ctx: Context, manifest: dict, summary: dict | None = None,
                      scenario_id: str | None = None) -> tuple[list[Station], dict]:
    """The stations of a saved multi-site run or site plan, and whether they reproduce its recorded jobs.

    A site plan's candidates are all loaded; those not selected for `scenario_id` (default: the first
    scenario) are switched off. The check compares the rebuilt job keys with the recorded ones."""
    sectors = manifest.get("sectors_per_site") or (manifest.get("site") or {}).get("sectors") or []
    if not sectors:
        raise ValueError("The run records no sector antennas.")
    pattern = sectors[0]["pattern"]
    bearings = [scene_azimuth_to_bearing_deg(s["orientation_rad"][0]) for s in sectors]
    tilt = float(np.degrees(sectors[0]["orientation_rad"][1]))
    n = len(sectors)
    azimuth = 0.0 if pattern == "iso" else bearings[0]
    spaced = sorted(round((b - azimuth) % 360.0, 6) % 360.0 for b in bearings)
    if pattern != "iso" and not np.allclose(spaced, [360.0 * k / n for k in range(n)], atol=1e-6):
        raise ValueError("The run's sectors are not evenly spaced; the workspace cannot describe them.")
    params = manifest.get("radio_parameters") or {}
    power = float((manifest.get("overrides") or {}).get("tx_power_dbm", (params.get("tx_power_dbm") or {}).get("value")))
    run_id = manifest.get("run_id", "")
    rule = manifest.get("site_rule") or {}
    recorded = (manifest.get("classification") or {}).get("placement")
    by_hand = bool(rule.get("buildings")) or recorded in (classification.MANUAL_PLACEMENT,
                                                          classification.HYPOTHETICAL_PLACEMENT)
    chosen = None
    if manifest.get("kind") == "site_plan":
        results = (summary or {}).get("results") or {}
        sid = scenario_id or next(iter(results), None)
        chosen = set((results.get(sid) or {}).get("selected") or [])
    recorded_positions = manifest.get("sector_positions_m") or {}
    rule_position = ((manifest.get("antenna_rule") or {}).get("antenna_position")
                     or (manifest.get("candidate_rule") or {}).get("antenna_position"))
    stations = []
    for number, site in enumerate(manifest["sites"], start=1):
        # sectors at the site point: recorded so, or no record and no roof-edge rule (runs before decision A4)
        point = (site["x"], site["y"], site["z"])
        if site["candidate_id"] in recorded_positions:
            at_point = all(np.allclose(p, point, atol=1e-6) for p in recorded_positions[site["candidate_id"]])
        else:
            at_point = rule_position != "roof_edge"
        b = ctx.building(site["building_id"])
        stations.append(Station(f"S{number}", float(site["x"]), float(site["y"]), float(site["z"]), ROOFTOP, power,
                                pattern, n if pattern != "iso" else 1, azimuth, tilt, building_id=site["building_id"],
                                roof_height_m=float(site["roof_height_m"]), height_category=site.get("height_category"),
                                meets_site_rule=meets_rule(ctx, b) if b is not None else None,
                                enabled=chosen is None or site["candidate_id"] in chosen,
                                origin=MANUAL if by_hand else SITE_RULE, source_run=run_id,
                                antenna_position=SITE_POINT if at_point else RULE_POSITION))
    recorded = {j["key"] for j in manifest.get("jobs") or [] if isinstance(j, dict)}
    rebuilt = {sj.job.key() for js in jobs(ctx, [replace(s, enabled=True) for s in stations],
                                           run_carriers(manifest) or None).values() for sj in js}
    return stations, {"recorded": len(recorded), "identical": len(rebuilt & recorded), "exact": rebuilt == recorded}


def run_carriers(manifest: dict) -> list[dict]:
    """The carriers a saved run used (runs before custom carriers recorded the presets only)."""
    out = []
    for sc in manifest.get("scenarios") or []:
        c = {"id": sc["id"], "label": sc["label"], "frequency_hz": float(sc["frequency_hz"]),
             "bandwidth_hz": float(sc["bandwidth_hz"]), "status": sc.get("status", ""),
             "preset": sc.get("preset", sc["id"]), "custom": bool(sc.get("custom", False)),
             "gas": sc.get("gas", ca.TABULATED)}
        for k in ("preset_frequency_hz", "preset_bandwidth_hz"):
            if k in sc:
                c[k] = float(sc[k])
        out.append(c)
    return out


def nearest_station_m(station: Station, stations: list[Station]) -> float | None:
    d = [float(np.hypot(station.x - s.x, station.y - s.y)) for s in stations
         if s.station_id != station.station_id and s.enabled]
    return min(d) if d else None


def cell_values(evaluation: Evaluation, grid, outdoor, x: float, y: float) -> dict | None:
    """Every computed value of the receiver cell containing (x, y), or None outside the grid."""
    xs, ys = grid.x_centers, grid.y_centers
    half = grid.cell_size_m / 2.0
    if not (xs[0] - half <= x <= xs[-1] + half and ys[0] - half <= y <= ys[-1] + half):
        return None
    i = int(np.clip(np.round((y - ys[0]) / grid.cell_size_m), 0, len(ys) - 1))
    j = int(np.clip(np.round((x - xs[0]) / grid.cell_size_m), 0, len(xs) - 1))
    out = {"x": float(xs[j]), "y": float(ys[i]), "row": i, "col": j, "outdoor": bool(outdoor[i, j])}
    for name, arr in evaluation.layers.items():
        v = arr[i, j]
        out[name] = bool(v) if arr.dtype == bool else (int(v) if np.issubdtype(arr.dtype, np.integer) else float(v))
    return out

