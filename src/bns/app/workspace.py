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

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np
from shapely.geometry import Point

from bns.analysis import classification
from bns.analysis import link_budget as lb
from bns.analysis import metrics
from bns.app import carriers as ca
from bns.analysis import validation_scope as vs
from bns.core.units import dbm_to_watt, linear_to_db
from bns.geospatial import sites
from bns.propagation import atmosphere as atm
from bns.propagation.engine_settings import engine_fingerprint
from bns.simulation import experiment as ex
from bns.simulation.cache import scene_fingerprint
from bns.simulation.jobs import Antenna, PropagationJob
from bns.simulation.network import network, spectral_overlap
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


class NoTransmitter(ValueError):
    """No enabled station transmits on the carrier."""


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
class StationCarrier:
    """One carrier a station transmits on, with its own power and antenna (sector panel, bearing, tilt).
    `carrier_id` names a carrier of the experiment (its frequency and bandwidth)."""

    carrier_id: str
    tx_power_dbm: float
    pattern: str
    sectors: int
    azimuth_deg: float
    downtilt_deg: float
    enabled: bool = True

    @classmethod
    def of(cls, station: "Station", carrier_id: str, **changes) -> "StationCarrier":
        """The carrier with the station's own values (then `changes`)."""
        return replace(cls(carrier_id, station.tx_power_dbm, station.pattern, station.sectors, station.azimuth_deg,
                           station.downtilt_deg), **changes)


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
    # None: the station transmits on every selected carrier of the experiment with the values above (as the
    # experiment scripts, and every station before mixed networks); else exactly these carriers
    carriers: tuple[StationCarrier, ...] | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Station":
        """A station from its saved form (experiments, run manifests); older files have no carriers."""
        d = dict(d)
        cs = d.get("carriers")
        d["carriers"] = None if cs is None else tuple(c if isinstance(c, StationCarrier) else StationCarrier(**c)
                                                     for c in cs)
        return cls(**d)

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


def on_carrier(station: Station, carrier_id: str) -> Station | None:
    """The station as it transmits on the carrier (that carrier's power and antenna), or None if it does not:
    switched off, or with its own carriers and this one missing or disabled."""
    if not station.enabled:
        return None
    if station.carriers is None:
        return station
    e = next((e for e in station.carriers if e.carrier_id == carrier_id and e.enabled), None)
    if e is None:
        return None
    return replace(station, tx_power_dbm=e.tx_power_dbm, pattern=e.pattern, sectors=e.sectors,
                   azimuth_deg=e.azimuth_deg, downtilt_deg=e.downtilt_deg)


def transmitting(stations: list[Station], carrier_id: str) -> list[tuple[int, Station]]:
    """(index among the enabled stations, station as configured on the carrier) of every station on it."""
    enabled = [s for s in stations if s.enabled]
    return [(i, v) for i, v in ((i, on_carrier(s, carrier_id)) for i, s in enumerate(enabled)) if v is not None]


def with_carriers(station: Station, carrier_ids: list[str]) -> Station:
    """The station transmitting on exactly these carriers, each with the station's values (or, if it already has
    its own carriers, those of its first carrier that is on)."""
    first = next((e for e in station.carriers or () if e.enabled), None)
    return replace(station, carriers=tuple(replace(first, carrier_id=c, enabled=True) if first is not None
                                           else StationCarrier.of(station, c) for c in carrier_ids))


def rename_carrier(stations: list[Station], old: str, new: str) -> list[Station]:
    """Stations whose carrier `old` is now called `new` (its frequency or bandwidth was edited)."""
    return [s if s.carriers is None else replace(s, carriers=tuple(replace(e, carrier_id=new) if e.carrier_id == old
                                                                   else e for e in s.carriers)) for s in stations]


def without_carrier(stations: list[Station], carrier_id: str) -> list[Station]:
    """Stations with a removed carrier taken out of their own carriers."""
    return [s if s.carriers is None else replace(s, carriers=tuple(e for e in s.carriers if e.carrier_id != carrier_id))
            for s in stations]


def generation(carrier: dict) -> str:
    """4g, 5g or 6g (candidate) from the carrier's preset (configs/scenarios.yaml ids)."""
    preset = str(carrier.get("preset", carrier.get("id", "")))
    for prefix, gen in (("lte", "4g"), ("nr", "5g"), ("c6g", "6g")):
        if preset.startswith(prefix):
            return gen
    raise ValueError(f"No generation for carrier preset {preset!r}.")


def preset_carriers(ctx: Context) -> list[dict]:
    """The five scenario presets of the experiment, as carriers (bns.app.carriers)."""
    return [{"id": sc["id"], "label": sc["label"], "frequency_hz": float(sc["frequency_hz"]),
             "bandwidth_hz": float(sc["bandwidth_hz"]), "status": sc.get("status", ""), "preset": sc["id"],
             "custom": False, "gas": ca.TABULATED} for sc in ctx.exp.scenarios]


def jobs(ctx: Context, stations: list[Station], carriers: list[dict] | None = None) -> dict[str, list[SectorJob]]:
    """Per carrier (default: the five presets): one job per sector of every station transmitting on it, with
    that carrier's antenna settings, as bns.simulation.setup.site_jobs describes it. SectorJob.station is the
    index among the enabled stations. Only the frequency of a carrier enters a job."""
    exp = ctx.exp
    geometry = {}

    def placed(v: Station):
        k = (v.station_id, v.pattern, v.sectors, v.azimuth_deg, v.downtilt_deg)
        if k not in geometry:
            ants = antennas(v, exp.config.polarization)
            geometry[k] = list(zip(ants, sector_positions(ctx, v, ants), strict=True))
        return geometry[k]

    out = {}
    for sc in carriers if carriers is not None else preset_carriers(ctx):
        out[sc["id"]] = [SectorJob(i, k, PropagationJob(ctx.scene_fingerprint, str(exp.scene_dir), sc["frequency_hz"],
                                                        tuple(float(c) for c in pos), antenna, exp.grid,
                                                        exp.config.mechanisms, int(exp.profile.rays_per_site),
                                                        exp.config.seeds, ctx.engine))
                         for i, v in transmitting(stations, sc["id"]) for k, (antenna, pos) in enumerate(placed(v))]
    return out


def evaluation_jobs(design_jobs: dict[str, list[SectorJob]], carriers: list[dict], carrier_id: str) -> list[SectorJob]:
    """The jobs a carrier's results need: its own and those of every carrier overlapping it in frequency."""
    me = next(c for c in carriers if c["id"] == carrier_id)
    return [sj for c in carriers if c["id"] == carrier_id or overlap(me, c) > 0 for sj in design_jobs.get(c["id"], [])]


def overlap(victim: dict, other: dict) -> float:
    return spectral_overlap(float(victim["frequency_hz"]), float(victim["bandwidth_hz"]),
                            float(other["frequency_hz"]), float(other["bandwidth_hz"]))


def job_labels(design_jobs: dict[str, list[SectorJob]], stations: list[Station]) -> dict[str, dict]:
    """Job key -> what it traces (band, station, sector, bearing), for progress reports."""
    enabled = [s for s in stations if s.enabled]
    out = {}
    for sid, js in design_jobs.items():
        for sj in js:
            s = on_carrier(enabled[sj.station], sid) or enabled[sj.station]
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
    Gas loss is the tabulated value, the recorded ITU-R P.676 value of a custom carrier, or none where a
    run before 2026-11-27 recorded it as omitted."""
    exp = ctx.exp
    f = float(scenario["frequency_hz"])
    gas = ca.gas_db_per_km({"gas": ca.TABULATED, **scenario}) if exp.baseline.include_gas else 0.0
    gamma = gas + atm.rain_specific_attenuation_db_per_km(f, float(radio.rain_rate_mm_h), exp.config.polarization)
    return atm.attenuation_map_db((station.x, station.y, station.antenna_height_m), exp.grid, gamma)


def _network_inputs(ctx: Context, stations: list[Station], scenario: dict, radio: RadioSettings, load):
    """Path-gain stack [sector, y, x] of the stations transmitting on the carrier, sector -> network site
    (0.. over those stations), losses, radio inputs and network site -> index among the enabled stations."""
    sid = scenario["id"]
    if not any(s.enabled for s in stations):
        raise NoTransmitter("No enabled station.")
    tx = transmitting(stations, sid)
    if not tx:
        raise NoTransmitter(f"No station transmits on {sid}.")
    js = jobs(ctx, stations, [scenario])[sid]
    entries = [load(sj.job.key()) for sj in js]
    missing = [sj.job.key() for sj, e in zip(js, entries, strict=True) if e is None]
    if missing:
        raise MissingTraces(f"{len(missing)} of {len(js)} path gains of {sid} are not in the cache.")
    stack = np.stack([e[0] for e in entries])
    site_of = {i: k for k, (i, _) in enumerate(tx)}
    view = dict(tx)
    sector_site = np.array([site_of[sj.station] for sj in js])
    loss = np.stack([loss_db(ctx, scenario, view[sj.station], radio) for sj in js])
    return (js, entries, stack, sector_site, loss, radio_inputs(ctx, [v for _, v in tx], scenario, radio),
            [i for i, _ in tx])


def received_power_w(ctx: Context, stations: list[Station], carrier: dict, radio: RadioSettings, load) -> np.ndarray:
    """Total power [y, x] in watts received from every sector transmitting on the carrier (zero if none)."""
    try:
        _, _, stack, _, loss, inputs, _ = _network_inputs(ctx, stations, carrier, radio, load)
    except NoTransmitter:
        return np.zeros(ctx.exp.grid.shape)
    dbm = lb.received_power_dbm(inputs.tx_power_dbm, stack, rx_gain_dbi=inputs.rx_gain_dbi, extra_loss_db=loss)
    finite = np.isfinite(dbm)
    return np.where(finite, dbm_to_watt(np.where(finite, dbm, 0.0)), 0.0).sum(axis=0)


def other_carriers(ctx: Context, stations: list[Station], scenario: dict, carriers: list[dict] | None,
                   radio: RadioSettings, load) -> tuple[list[dict], np.ndarray | None]:
    """Interference [y, x] in watts from the other carriers that overlap this one (bns.simulation.network.
    spectral_overlap), and which ones they are. None when no transmitting carrier overlaps."""
    found, total = [], None
    for c in carriers or []:
        if c["id"] == scenario["id"] or (share := overlap(scenario, c)) <= 0:
            continue
        tx = transmitting(stations, c["id"])
        if not tx:
            continue
        w = share * received_power_w(ctx, stations, c, radio, load)
        total = w if total is None else total + w
        found.append({"carrier": c["id"], "overlap": share, "stations": [v.station_id for _, v in tx]})
    return found, total


def evaluate(ctx: Context, stations: list[Station], scenario: dict, radio: RadioSettings, load,
             carriers: list[dict] | None = None) -> Evaluation:
    """Network results on one carrier, from cached path gain only: the stations transmitting on it serve and
    interfere with each other; stations on other `carriers` (the experiment's selected carriers) interfere
    with the share of their power inside this carrier's band. serving_station is the index among the
    enabled stations.

    `load(key)` returns (path gain, cache manifest) or None (PathGainCache.get)."""
    exp, sid = ctx.exp, scenario["id"]
    enabled = [s for s in stations if s.enabled]
    js, entries, stack, sector_site, loss, inputs, site_station = _network_inputs(ctx, stations, scenario, radio, load)
    found, external = other_carriers(ctx, stations, scenario, carriers, radio, load)
    net = network(stack, sector_site, exp.outdoor, inputs, loss, external)
    station_of = np.asarray(site_station)
    serving = np.where(net.serving_site >= 0, station_of[np.maximum(net.serving_site, 0)], -1)
    layers = {"path_gain_db": linear_to_db(stack.max(axis=0)), "rx_power_dbm": net.radio.rx_power_dbm,
              "sinr_db": net.radio.sinr_db, "rate_bps": net.radio.rate_bps, "covered": net.radio.covered,
              "serving_station": serving, "serving_sector": net.serving_sector,
              "interference_dbm": net.interference_dbm}
    shares = [0.0] * len(enabled)
    for k, i in enumerate(site_station):
        shares[i] = net.summary["served_share_per_site"][k]
    summary = {**net.summary, "served_share_per_site": shares, "noise_dbm": net.radio.noise_dbm,
               "transmitting_stations": [enabled[i].station_id for i in site_station], "other_carriers": found}
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
           max_sites: int | None = None, carriers: list[dict] | None = None):
    """The project's interference-aware SINR greedy (bns.optimization.greedy) over the shown stations: which
    of them, added one at a time, give the highest network coverage. Indices refer to `stations` (all of
    them are candidates, switched-off ones included). A heuristic over these stations only."""
    from bns.optimization.greedy import greedy_sinr_site_selection

    every = [replace(s, enabled=True) for s in stations]
    _, _, stack, sector_site, loss, inputs, site_station = _network_inputs(ctx, every, scenario, radio, load)
    _, external = other_carriers(ctx, every, scenario, carriers, radio, load)

    def coverage_of(selection):
        keep = np.isin(sector_site, selection)
        remap = {site: k for k, site in enumerate(sorted(selection))}
        sub = replace(inputs, tx_power_dbm=inputs.tx_power_dbm[keep])
        return network(stack[keep], np.array([remap[i] for i in sector_site[keep]]), ctx.exp.outdoor, sub,
                       loss[keep], external).radio.summary["coverage_fraction"]

    g = greedy_sinr_site_selection(coverage_of, len(site_station), target, max_sites)
    if site_station == list(range(len(every))):
        return g                                    # every station transmits on the carrier: same numbering
    return replace(g, selected=[site_station[k] for k in g.selected],
                   degrading_additions=[{**d, "candidate": site_station[d["candidate"]]} for d in g.degrading_additions])


@dataclass
class GenerationResult:
    """A generation's results over its carriers: in every cell the carrier with the highest SINR serves
    (docs/assumptions.md section 11). serving_carrier indexes `carriers`."""

    generation: str
    carriers: list[str]
    layers: dict
    summary: dict


def by_generation(ctx: Context, evaluations: dict, carriers: list[dict]) -> dict[str, GenerationResult]:
    """4G, 5G and candidate 6G results from the carriers' evaluations (carriers without results are left out)."""
    out = {}
    outdoor = ctx.exp.outdoor
    for gen in dict.fromkeys(generation(c) for c in carriers):
        cs = [c["id"] for c in carriers if generation(c) == gen and evaluations.get(c["id"]) is not None]
        if not cs:
            continue
        evs = [evaluations[c] for c in cs]
        sinr = np.stack([e.layers["sinr_db"] for e in evs])
        pick = np.argmax(np.where(np.isnan(sinr), -np.inf, sinr), axis=0)

        def chosen(name):
            if any(name not in e.layers for e in evs):
                return None
            return np.take_along_axis(np.stack([e.layers[name] for e in evs]), pick[None], axis=0)[0]

        best = np.fmax.reduce(sinr, axis=0)
        covered = np.logical_or.reduce([np.asarray(e.layers["covered"], dtype=bool) for e in evs])
        station = chosen("serving_station")
        served = outdoor & (station >= 0)
        layers = {"sinr_db": best, "rx_power_dbm": chosen("rx_power_dbm"), "rate_bps": chosen("rate_bps"),
                  "covered": covered, "serving_station": np.where(served, station, -1),
                  "serving_carrier": np.where(served, pick, -1)}
        if (mapped := chosen("rate_3gpp_bps")) is not None:
            layers["rate_3gpp_bps"] = mapped
        reached = outdoor & np.isfinite(best)
        n_out = int(outdoor.sum())
        summary = {"carriers": cs, "coverage_fraction": float((covered & outdoor).sum() / n_out),
                   "sinr_db_median": float(np.median(best[reached])) if reached.any() else None,
                   "sinr_db_p5": metrics.percentile(np.where(np.isfinite(best), best, -1e9), 5, outdoor),
                   "rate_median_bps": metrics.percentile(layers["rate_bps"], 50, outdoor),
                   "rate_p5_bps": metrics.percentile(layers["rate_bps"], 5, outdoor),
                   "served_share_per_carrier": {c: float(((pick == k) & served).sum() / n_out) for k, c in enumerate(cs)},
                   "selection": "highest SINR among the generation's carriers"}
        out[gen] = GenerationResult(gen, cs, layers, summary)
    return out


# ---------------------------------------------------------------- classification
def _carrier_deviations(base: StationTemplate, s: Station, carriers: list[dict] | None) -> list[str]:
    """A station with its own carriers: which ones it transmits, and the values that differ from the baseline."""
    on = [e for e in s.carriers if e.enabled]
    out = []
    if carriers is not None and [e.carrier_id for e in on] != [c["id"] for c in carriers]:
        out.append(f"{s.station_id} carriers: {', '.join(e.carrier_id for e in on) or 'none'}")
    for e in on:
        for name, value, ref in (("tx_power_dbm", e.tx_power_dbm, base.tx_power_dbm),
                                 ("downtilt_deg", e.downtilt_deg, base.downtilt_deg),
                                 ("sectors", e.sectors, base.sectors)):
            if not np.isclose(float(value), float(ref), rtol=0, atol=1e-9):
                out.append(f"{s.station_id} {e.carrier_id}: {name} = {value:g}")
        if e.pattern != base.pattern:
            out.append(f"{s.station_id} {e.carrier_id}: pattern = {e.pattern}")
        view = replace(s, pattern=e.pattern, sectors=e.sectors, azimuth_deg=e.azimuth_deg)
        if not np.isclose(e.azimuth_deg % 360.0, 0.0, atol=1e-9) and e.pattern != "iso":
            out.append(f"{s.station_id} {e.carrier_id}: sector bearings {'/'.join(f'{b:g}' for b in view.bearings_deg)}°")
    return out


def deviations(ctx: Context, stations: list[Station], carriers: list[dict] | None = None) -> list[str]:
    """How the stations depart from the site rule and the research-baseline values (English, recorded).
    `carriers`: the experiment's selected carriers (a station with its own carriers that leaves some out)."""
    base = StationTemplate.baseline(ctx)
    out = []
    for s in (s for s in stations if s.enabled):
        if s.carriers is not None:                  # power and antenna belong to each carrier
            if s.mount == HYPOTHETICAL:
                out.append(f"{s.station_id} hypothetical location (not a rooftop site)")
            elif not s.meets_site_rule:
                out.append(f"{s.station_id} on {s.building_id}, a roof outside the candidate rule")
            if not np.isclose(float(s.mast_height_m or 0.0), float(base.mast_height_m), rtol=0, atol=1e-9) \
                    and s.mast_height_m is not None:
                out.append(f"{s.station_id} antenna_height_above_roof_m = {s.mast_height_m:g}")
            out += _carrier_deviations(base, s, carriers)
            continue
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
             carriers: list[dict] | None = None, network: list[dict] | None = None) -> classification.Classification:
    """The design's scientific classification, by the rules every run uses, with its placement. `carriers`: those
    simulated; `network`: every carrier of the experiment that transmits (default: `carriers`)."""
    exp = ctx.exp
    overrides = {**{k: v for k, v in exp.overrides.items() if k in ("rx_height_m", "cell_size_m", "rays_per_site")},
                 **radio_overrides(ctx, radio)}
    devs = (ex.baseline_deviations(exp.root, exp.profile, exp.backend)
            + deviations(ctx, stations, network if network is not None else carriers)
            + ca.deviations(carriers or []))
    ants = []
    for s in (s for s in stations if s.enabled):
        views = [s] if s.carriers is None else [on_carrier(s, e.carrier_id) for e in s.carriers if e.enabled]
        for a in (a for v in views for a in antennas(v, exp.config.polarization)):
            if a not in ants:
                ants.append(a)
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
    config = (manifest.get("experiment") or {}).get("config") or {}
    if manifest.get("source") == "workspace" and config.get("stations"):
        # a workspace run keeps the exact design: every station with its own carriers and values
        stations = [replace(Station.from_dict(d), source_run=manifest.get("run_id", "")) for d in config["stations"]]
        recorded = {j["key"] for j in manifest.get("jobs") or [] if isinstance(j, dict)}
        rebuilt = {sj.job.key() for js in jobs(ctx, stations, run_carriers(manifest) or None).values() for sj in js}
        return stations, {"recorded": len(recorded), "identical": len(rebuilt & recorded), "exact": rebuilt == recorded}
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


def design_carriers(manifest: dict, presets: list[dict]) -> list[dict]:
    """The experiment carriers of a saved run, with run flags: a workspace run's own list (added carriers and
    custom values included); for script runs the recorded carriers, then the presets they leave out (off)."""
    config = (manifest.get("experiment") or {}).get("config") or {}
    if manifest.get("source") == "workspace" and config.get("carriers"):
        return [dict(c) for c in config["carriers"]]
    recorded = run_carriers(manifest)
    used = {c["preset"] for c in recorded}
    return [{**c, "selected": True} for c in recorded] + [{**p, "selected": False} for p in presets
                                                          if p["id"] not in used]


def run_carriers(manifest: dict) -> list[dict]:
    """The carriers a saved run used (runs before custom carriers recorded the presets only)."""
    out = []
    for sc in manifest.get("scenarios") or []:
        c = {"id": sc["id"], "label": sc["label"], "frequency_hz": float(sc["frequency_hz"]),
             "bandwidth_hz": float(sc["bandwidth_hz"]), "status": sc.get("status", ""),
             "preset": sc.get("preset", sc["id"]), "custom": bool(sc.get("custom", False)),
             "gas": sc.get("gas", ca.TABULATED)}
        for k in ("preset_frequency_hz", "preset_bandwidth_hz", "gas_db_per_km"):
            if k in sc:
                c[k] = float(sc[k])
        if sc.get("gas_model"):
            c["gas_model"] = dict(sc["gas_model"])
        out.append(c)
    return out


def _radio_values(stations: list[Station]) -> list[tuple]:
    """What the radio evaluation takes from each transmitting station besides its traced path gain."""
    return [(s.station_id, float(s.tx_power_dbm), s.x, s.y, float(s.antenna_height_m),
             None if s.carriers is None else tuple(asdict(e) for e in s.carriers)) for s in stations if s.enabled]


def _overlapping(carrier: dict, carriers: list[dict]) -> list[tuple]:
    return sorted((c["id"], float(c["frequency_hz"]), float(c["bandwidth_hz"])) for c in carriers
                  if c["id"] != carrier["id"] and overlap(carrier, c) > 0)


def evaluation_from_run(ctx: Context, stations: list[Station], carrier: dict, radio: RadioSettings,
                        run_dir: Path, carriers: list[dict] | None = None) -> Evaluation | None:
    """A saved workspace run's results for this carrier, if the run computed exactly this design: the same
    job keys (propagation), the same radio values, station powers and positions, and the same carrier
    (frequency, bandwidth, gas treatment, value and model version). Then its arrays are what evaluate() would compute from the
    cache, so they can be shown where the cache does not hold the traces (e.g. a new installation).
    Otherwise None: results of another configuration are never shown as this one's."""
    import json as _json

    run_dir = Path(run_dir)
    try:
        manifest = _json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        summary = _json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    config = (manifest.get("experiment") or {}).get("config") or {}
    if manifest.get("source") != "workspace" or not config:
        return None
    sid = carrier["id"]
    recorded = [c for c in manifest.get("scenarios") or [] if c.get("id") == sid]
    keys = [sj.job.key() for sj in jobs(ctx, stations, [carrier])[sid]]
    run_keys = [j["key"] for j in manifest.get("jobs") or [] if j.get("scenario") == sid]
    run_stations = [Station.from_dict(d) for d in config.get("stations") or []]
    same_carrier = bool(recorded) and all(recorded[0].get(k) == carrier.get(k)
                                          for k in ("frequency_hz", "bandwidth_hz", "preset", "gas",
                                                    "gas_db_per_km", "gas_model"))
    network_of_run = [{"id": c["id"], "frequency_hz": c["frequency_hz"], "bandwidth_hz": c["bandwidth_hz"]}
                      for c in manifest.get("network_carriers") or run_carriers(manifest)]
    same_neighbours = _overlapping(carrier, network_of_run) == _overlapping(carrier, carriers or [carrier])
    if not (same_carrier and same_neighbours and keys and keys == run_keys and config.get("radio") == asdict(radio)
            and _radio_values(run_stations) == _radio_values(stations)):
        return None
    with np.load(run_dir / "network.npz") as arrays:
        def layer(name):
            key = f"{sid}_{name}"
            return arrays[key] if key in arrays.files else None
        layers = {name: layer(name) for name in ("path_gain_db", "rx_power_dbm", "sinr_db", "rate_bps", "covered",
                                                 "serving_sector", "interference_dbm", "rate_3gpp_bps")}
        layers["serving_station"] = layer("serving_site")
    layers = {k: v for k, v in layers.items() if v is not None}
    jobs_ = [j for j in manifest["jobs"] if j.get("scenario") == sid]
    order = [site["candidate_id"] for site in manifest.get("sites") or []] or list(dict.fromkeys(j["site"]
                                                                                             for j in jobs_))
    sectors, count = [], {}
    for j in jobs_:
        count[j["site"]] = count.get(j["site"], 0) + 1
        sectors.append((j["site"], count[j["site"]]))
    return Evaluation(sid, layers, dict(summary["results"][sid]["network"]), order, sectors,
                      float(sum(j.get("trace_seconds") or 0.0 for j in jobs_)), tuple(keys), radio,
                      extra={"from_run": run_dir.name})


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

