"""Everything an experiment needs before tracing: dataset, grid, sites, jobs, radio inputs.

Shared by the experiment scripts and the application, so that a run started from
either describes its inputs the same way. Nothing here traces rays or chooses a
radio parameter: values come from the configuration files in the chosen mode.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from bns.analysis.radio_system import RadioSystem
from bns.geospatial import heights as ht
from bns.geospatial import pipeline, sites
from bns.geospatial.grid import Grid, outdoor_mask
from bns.geospatial.study_area import StudyArea, load_study_areas
from bns.propagation import atmosphere as atm
from bns.simulation.cache import PathGainCache
from bns.simulation.jobs import Antenna, PropagationJob
from bns.simulation.radio import RadioInputs
from bns.simulation.setup import Profile, SimulationConfig, sector_antennas, site_jobs

# radio parameters every coverage experiment uses (they set the output label)
USED = ["tx_power_dbm", "tx_antenna_gain_dbi", "tx_antenna_pattern", "sectors_per_site",
        "mechanical_downtilt_deg", "antenna_height_above_roof_m", "rx_height_m",
        "rx_antenna_gain_dbi", "noise_figure_db", "noise_temperature_k", "coverage_threshold",
        "interference_activity"]


class ExperimentError(RuntimeError):
    """The experiment cannot run: a technical problem (missing dataset or scene, invalid value,
    unknown area or profile, unavailable backend). Scientific limitations never raise this."""


# Parameters a user may change for a custom or sensitivity experiment, with their valid range.
# Anything not listed stays as configured. The approved configuration is the research baseline.
RADIO_OVERRIDES = {"tx_power_dbm": (0.0, 60.0), "mechanical_downtilt_deg": (-10.0, 30.0),
                   "sectors_per_site": (1, 6), "antenna_height_above_roof_m": (0.0, 30.0),
                   "rx_height_m": (0.5, 10.0), "noise_figure_db": (0.0, 20.0),
                   "coverage_threshold": (-20.0, 40.0), "coverage_target": (0.5, 1.0),
                   "interference_activity": (0.0, 1.0)}
OTHER_OVERRIDES = {"cell_size_m": (2.0, 50.0), "rays_per_site": (10**6, 10**10), "rain_rate_mm_h": (0.0, 200.0),
                   "min_roof_height_m": (0.0, 300.0), "min_roof_area_m2": (0.0, 100000.0),
                   "min_spacing_m": (0.0, 2000.0)}
OVERRIDES = {**RADIO_OVERRIDES, **OTHER_OVERRIDES}
INTEGER_OVERRIDES = ("sectors_per_site", "rays_per_site")
BASELINE = "research baseline"
CUSTOM = "custom experiment"


def baseline_values(root: Path, profile_name: str) -> dict:
    """The research-baseline value of every parameter a user may change (from the config files)."""
    root = Path(root)
    radio = (yaml.safe_load((root / "configs" / "radio_system.yaml").read_text(encoding="utf-8")) or {})["parameters"]
    out = {k: radio[k]["value"] for k in RADIO_OVERRIDES}
    profile = SimulationConfig.load(root / "configs" / "simulation.yaml").profile(profile_name)
    out.update(cell_size_m=float(profile.cell_size_m), rays_per_site=int(profile.rays_per_site))
    conditions, _ = atm.load_conditions(root / "configs" / "atmosphere.yaml")
    out["rain_rate_mm_h"] = float(conditions.rain_rate_mm_h)
    rule = yaml.safe_load((root / "configs" / "site_rule.yaml").read_text(encoding="utf-8")) or {}
    out.update({k: (rule.get("candidate_thresholds") or {}).get(k)
                for k in ("min_roof_height_m", "min_roof_area_m2", "min_spacing_m")})
    return {k: ((int(v) if k in INTEGER_OVERRIDES else float(v)) if v is not None else None) for k, v in out.items()}


def differences(values: dict, baseline: dict) -> dict:
    """The entries of `values` that differ from the baseline (these are the run's overrides)."""
    return {k: v for k, v in values.items() if k in OVERRIDES and v is not None and
            (baseline.get(k) is None or not np.isclose(float(v), float(baseline[k]), rtol=0, atol=1e-9))}


def run_class(overrides: dict | None) -> str:
    return CUSTOM if overrides else BASELINE


def validate_overrides(overrides: dict | None) -> dict:
    """Refuse unknown parameters and values outside their technical range; return clean values."""
    clean = {}
    for k, v in (overrides or {}).items():
        if k not in OVERRIDES:
            raise ExperimentError(f"'{k}' cannot be changed for an experiment (changeable: {', '.join(OVERRIDES)}).")
        try:
            value = float(v)
        except (TypeError, ValueError) as exc:
            raise ExperimentError(f"{k} must be a number, not {v!r}.") from exc
        lo, hi = OVERRIDES[k]
        if not np.isfinite(value) or not lo <= value <= hi:
            raise ExperimentError(f"{k} = {v} is outside its valid range {lo:g} to {hi:g}.")
        if k in INTEGER_OVERRIDES:
            if value != int(value):
                raise ExperimentError(f"{k} must be a whole number, not {v}.")
            value = int(value)
        clean[k] = value
    return clean


def custom_radio_system(system: RadioSystem, overrides: dict) -> RadioSystem:
    """The radio system with experiment values; changed values are marked as development values
    (never as approved) and pass the same checks as the configuration file."""
    entries = {k: dict(v) for k, v in system.entries.items()}
    for k, v in overrides.items():
        if k in RADIO_OVERRIDES:
            e = entries[k]
            e.update(value=v, status="development",
                     justification="custom experiment value (differs from the research baseline)")
            e.pop("approved_by", None)
    try:
        return RadioSystem.from_entries(entries)
    except ValueError as exc:
        raise ExperimentError(str(exc)) from exc


@dataclass
class Experiment:
    root: Path
    area: StudyArea
    variant: str
    mode: str
    profile: Profile
    system: RadioSystem
    config: SimulationConfig
    scenarios: list[dict]
    baseline: atm.Conditions
    label: str
    scene_dir: Path
    quality: dict
    buildings: list[ht.Building]
    grid: Grid
    outdoor: np.ndarray
    antennas: list[Antenna]
    mast_height_m: float
    backend: str = "cpu"
    backend_note: str = ""
    site_rule: dict = field(default_factory=lambda: {"antenna_position": "interior"})
    extra: dict = field(default_factory=dict)
    overrides: dict = field(default_factory=dict)     # values that differ from the research baseline
    classification: object = None                     # bns.analysis.classification.Classification

    @property
    def run_class(self) -> str:
        """Configuration class: research baseline, custom experiment or sensitivity analysis."""
        return self.classification.configuration if self.classification is not None else run_class(self.overrides)

    @property
    def candidate_rule(self) -> dict:
        """Candidate rooftop criteria in effect (site rule, with experiment overrides)."""
        t = self.site_rule.get("candidate_thresholds") or {}
        rule = {k: self.overrides.get(k, t.get(k)) for k in ("min_roof_height_m", "min_roof_area_m2", "min_spacing_m")}
        rule["categories"] = list(sites.candidate_categories(self.site_rule.get("candidate_height_categories"),
                                                             self.quality.get("height_model")))
        return rule

    @property
    def receiver_buildings(self) -> list[ht.Building]:
        box = self.area.receiver_box()
        return [b for b in self.buildings if box.contains(b.polygon.representative_point())]


def load_scenarios(root: Path) -> list[dict]:
    scenarios = yaml.safe_load((Path(root) / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))["scenarios"]
    for sc in scenarios:
        sc["frequency_hz"], sc["bandwidth_hz"] = float(sc["frequency_hz"]), float(sc["bandwidth_hz"])
    return sorted(scenarios, key=lambda s: s["frequency_hz"])


def resolve_backend(requested: str, config: SimulationConfig, mode: str = "development") -> tuple[str, str]:
    """'cpu', 'gpu' or 'auto' -> the backend to use and why. Refuses only what cannot run (no GPU)."""
    from bns import runtime

    if requested not in ("cpu", "gpu", "auto"):
        raise ExperimentError(f"backend must be cpu, gpu or auto, not {requested!r}.")
    if requested == "cpu":
        return "cpu", "CPU selected."
    available, message = runtime.probe_gpu()
    if requested == "gpu":
        if not available:
            raise ExperimentError(message)
        return "gpu", message
    return ("gpu", message) if available else ("cpu", message)


def baseline_deviations(root: Path, profile: Profile, backend: str) -> list[str]:
    """Settings outside the parameter overrides that depart from the research baseline: the profile
    (only an approved, converged profile belongs to it) and the backend (the research backend)."""
    sim = yaml.safe_load((Path(root) / "configs" / "simulation.yaml").read_text(encoding="utf-8")) or {}
    out = []
    entry = (sim.get("profiles") or {}).get(profile.name.removesuffix("-custom")) or {}
    if entry.get("status") != "approved" and not profile.name.endswith("-custom"):
        out.append(f"{profile.name} profile ({profile.cell_size_m:g} m, {profile.rays_per_site:.0e} rays)")
    research_backend = sim.get("research_backend", "cpu")
    if backend != research_backend:
        out.append(f"{backend.upper()} backend (numerical limits: docs/validation.md §7)")
    return out


def load(root: Path, area_name: str, variant: str, profile_name: str, mode: str = "development",
         backend: str = "cpu", overrides: dict | None = None) -> Experiment:
    """Prepare an experiment. Only technical problems stop it (unknown area or profile, missing scene,
    invalid values, unavailable backend); its scientific standing is recorded in `classification`.
    `mode` is kept for older callers and output folders; it no longer restricts anything."""
    root = Path(root)
    overrides = validate_overrides(overrides)
    mode = "development"                               # internal: no approval checks on parameter values
    areas = load_study_areas(root / "configs" / "study_area.yaml")
    if area_name not in areas:
        raise ExperimentError(f"Unknown study area '{area_name}'.")
    area = areas[area_name]
    system = RadioSystem.load(root / "configs" / "radio_system.yaml")
    config = SimulationConfig.load(root / "configs" / "simulation.yaml")
    try:
        profile = config.profile(profile_name)
    except KeyError as exc:
        raise ExperimentError(str(exc)) from exc
    if overrides:
        overrides = differences(overrides, baseline_values(root, profile_name))
    if overrides:
        system = custom_radio_system(system, overrides)
    if "cell_size_m" in overrides or "rays_per_site" in overrides:
        profile = Profile(f"{profile.name}-custom", overrides.get("cell_size_m", profile.cell_size_m),
                          overrides.get("rays_per_site", profile.rays_per_site),
                          "custom (not convergence-checked)")
    baseline, _ = atm.load_conditions(root / "configs" / "atmosphere.yaml")
    if "rain_rate_mm_h" in overrides:
        baseline = atm.Conditions(rain_rate_mm_h=overrides["rain_rate_mm_h"], include_gas=baseline.include_gas)
    scene_dir = root / "data" / "scenes" / area.name / variant
    if not (scene_dir / "scene.xml").exists():
        raise ExperimentError(f"No dataset {scene_dir}; run scripts/build_dataset.py --area {area.name} first.")
    try:
        quality = json.loads((scene_dir / "quality_report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExperimentError(f"The dataset {scene_dir} has no readable quality report: {exc}") from exc
    buildings = pipeline.load_buildings(scene_dir, area)
    rx_height = system.require("rx_height_m", mode=mode)
    grid = area.receiver_grid(profile.cell_size_m, rx_height)
    outdoor = outdoor_mask(grid, [b.polygon for b in buildings])
    if not outdoor.any():
        raise ExperimentError("The receiver grid has no outdoor cell: nothing to compute.")
    antennas = sector_antennas(system, mode=mode, polarization=config.polarization)
    mast = system.require("antenna_height_above_roof_m", mode=mode)
    chosen, note = resolve_backend(backend, config, mode)
    rule_path = root / "configs" / "site_rule.yaml"
    site_rule = yaml.safe_load(rule_path.read_text(encoding="utf-8")) if rule_path.exists() else \
        {"antenna_position": "interior"}
    from dataclasses import asdict

    from bns.analysis import classification
    from bns.analysis import validation_scope as vs
    from bns.propagation.engine_settings import engine_fingerprint
    from bns.simulation.cache import scene_fingerprint

    scope = vs.scope(scene_fingerprint=scene_fingerprint(scene_dir), grid=asdict(grid),
                     rays_per_site=profile.rays_per_site, engine=engine_fingerprint(chosen),
                     antennas=[asdict(a) for a in antennas], mechanisms=asdict(config.mechanisms), seeds=config.seeds)
    classes = classification.classify(root, overrides, quality, study_district=area.is_research_dataset,
                                      deviations=baseline_deviations(root, profile, chosen), scope=scope,
                                      profile=profile.name)
    label = classes.label                              # what the result is, scientifically
    return Experiment(root, area, variant, mode, profile, system, config, load_scenarios(root), baseline,
                      label, scene_dir, quality, buildings, grid, outdoor, antennas, mast, chosen, note, site_rule,
                      overrides=overrides, classification=classes)


def limitation_items(exp: Experiment) -> list[tuple[str, dict]]:
    """The scientific limitations of a run of this experiment as (translation key, values) pairs
    (bns.i18n, section `limitations`); shown, never blocking."""
    c = exp.classification
    # dataset reasons; quality reports written before 2026-11-27 also listed the approval state, which
    # repeats the area's role and is no longer a limitation
    reasons = [r for r in (exp.quality.get("not_fit_reasons") or []) if "approved" not in r]
    items: list[tuple[str, dict]] = []
    if not exp.area.is_research_dataset:
        items.append(("limitations.not_study_district", {"area": exp.area.name, "role": exp.area.role}))
        reasons = [r for r in reasons if "not the study district" not in r]
    model = exp.quality.get("height_model") or {}
    syn = model.get("synthetic")
    worklist = exp.quality.get("observation_worklist") or {}
    placeholder_pct = ((exp.quality.get("height_categories") or {}).get("by_count_percent") or {}).get("placeholder", 0.0)
    for r in reasons:
        if "placeholder heights" in r:
            if not syn:     # on a synthetic dataset those buildings carry synthetic heights (stated below)
                items.append(("limitations.placeholder_share", {"pct": placeholder_pct}))
        elif r.startswith("observation worklist"):
            if not syn:
                items.append(("limitations.worklist_incomplete",
                              {"observed": worklist.get("observed", 0), "listed": worklist.get("listed", 0),
                               "unmatched": worklist.get("unmatched", 0)}))
        else:
            items.append(("limitations.dataset_note", {"text": r}))
    if syn:
        items.append(("limitations.synthetic", {"name": model.get("name"), "algorithm": syn.get("algorithm"),
                                                "scenario": syn.get("scenario"), "seed": model.get("seed"),
                                                "pct": syn.get("synthetic_percent", 0.0)}))
    elif c is not None and c.dataset == classification_module().ESTIMATED:
        items.append(("limitations.height_model", {}))
    if c is not None and c.deviations:
        items.append(("limitations.deviations", {"items": "; ".join(c.deviations)}))
    if c is not None and c.validation != classification_module().VALIDATED:
        items.append(("limitations.validation_pending", {}))
    return items


def limitations(exp: Experiment, lang: str = "en") -> list[str]:
    """The limitations as sentences (English by default, for run logs and manifests)."""
    from bns.i18n import translate
    return [translate(lang, key, **values) for key, values in limitation_items(exp)]


def classification_module():
    from bns.analysis import classification
    return classification


def caveat(exp: Experiment) -> str:
    """One sentence on what a run of this experiment may be used for, from the facts."""
    c = exp.classification
    if c is not None and c.validated:
        return "Validated research result: research baseline on a dataset fit for research, validation completed."
    return f"**{c.result if c else 'Preliminary Simulation'}, not a validated finding about Baghdad**: " \
        + "; ".join(limitations(exp)) + "."


def place_sites(exp: Experiment, building_ids: list[str]) -> list[sites.Candidate]:
    """One site on each named building, in the given order."""
    by_id = {b.building_id: b for b in exp.buildings}
    missing = [i for i in building_ids if i not in by_id]
    if missing:
        raise ExperimentError(f"Buildings not in the dataset: {missing}")
    placed = []
    for number, bid in enumerate(building_ids, start=1):
        [c] = sites.rooftop_candidates([by_id[bid]], mast_height_m=exp.mast_height_m, min_height_m=0.0,
                                       min_area_m2=0.0, min_spacing_m=0.0, max_candidates=1)
        placed.append(sites.Candidate(f"site-{number:03d}", c.x, c.y, c.z, c.building_id, c.roof_height_m,
                                      c.footprint_area_m2, c.height_category))
    return placed


def observed_sites(exp: Experiment, count: int | None = None):
    """Tallest receiver-area rooftops that satisfy the candidate rule (site rule with experiment
    overrides): heights observed or storey-based, minimum roof height, area and spacing;
    monuments, memorials and artworks never qualify."""
    r = exp.candidate_rule
    missing = [k for k in ("min_roof_height_m", "min_roof_area_m2", "min_spacing_m") if r.get(k) is None]
    if missing:
        raise ExperimentError(f"Candidate criteria not set: {', '.join(missing)} (configs/site_rule.yaml).")
    return sites.rooftop_candidates(exp.receiver_buildings, mast_height_m=exp.mast_height_m,
                                    min_height_m=r["min_roof_height_m"], min_area_m2=r["min_roof_area_m2"],
                                    min_spacing_m=r["min_spacing_m"], max_candidates=count,
                                    categories=tuple(r["categories"]))


def sector_positions(exp: Experiment, site: sites.Candidate) -> list[tuple[float, float, float]]:
    """Antenna position of every sector of a site, following the site rule (decision A4)."""
    if exp.site_rule.get("antenna_position") != "roof_edge" or exp.antennas[0].pattern == "iso":
        return [(site.x, site.y, site.z)] * len(exp.antennas)
    roof = next(b.polygon for b in exp.buildings if b.building_id == site.building_id)
    xy = sites.edge_positions(roof, site.x, site.y, [a.orientation_rad[0] for a in exp.antennas],
                              float(exp.site_rule["edge_inset_m"]))
    return [(x, y, site.z) for x, y in xy]


def jobs_for(exp: Experiment, placed: list[sites.Candidate]) -> dict[str, list[tuple[int, PropagationJob]]]:
    """Per scenario: (site index, job) for every sector of every site, each sector at its position."""
    positions = {i: sector_positions(exp, s) for i, s in enumerate(placed)}
    out = {}
    for sc in exp.scenarios:
        out[sc["id"]] = [(i, site_jobs(exp.scene_dir, sc["frequency_hz"], positions[i][k], [antenna], exp.grid,
                                       exp.config, exp.profile.rays_per_site, exp.backend)[0])
                         for i in range(len(placed)) for k, antenna in enumerate(exp.antennas)]
    return out


def radio_inputs(exp: Experiment, scenario: dict) -> RadioInputs:
    sid, sys_, mode = scenario["id"], exp.system, exp.mode
    return RadioInputs(
        tx_power_dbm=sys_.tx_power_for_path_gain_dbm(sid, mode=mode),
        rx_gain_dbi=sys_.require("rx_antenna_gain_dbi", sid, mode=mode),
        noise_figure_db=sys_.require("noise_figure_db", sid, mode=mode),
        noise_temperature_k=sys_.require("noise_temperature_k", sid, mode=mode),
        bandwidth_hz=scenario["bandwidth_hz"],
        coverage_definition=sys_.definition("coverage_threshold"),
        coverage_threshold=sys_.require("coverage_threshold", sid, mode=mode),
        interference_activity=sys_.require("interference_activity", sid, mode=mode))


def rate_mapping(exp: Experiment, scenario: dict):
    """The B3 practical rate model of this scenario (configs/radio_system.yaml), or None if absent."""
    from bns.analysis import rate_models

    path = exp.root / "configs" / "radio_system.yaml"
    models = rate_models.load(path)
    if not models:
        return None
    if scenario["id"] not in models:
        raise ExperimentError(f"No rate mapping is assigned to scenario {scenario['id']} (scenario_rate_mapping).")
    return models[scenario["id"]]


def mapped_rate_bps(exp: Experiment, scenario: dict, sinr_db: np.ndarray) -> np.ndarray | None:
    """Rate of the scenario's B3 mapping for a SINR map (dB; -inf where unreached), or None."""
    model = rate_mapping(exp, scenario)
    if model is None:
        return None
    sinr = np.where(np.isfinite(sinr_db), 10.0 ** (np.where(np.isfinite(sinr_db), sinr_db, 0.0) / 10.0), 0.0)
    return model.rate_bps(scenario["bandwidth_hz"], sinr)


def gas_loss_db(exp: Experiment, scenario: dict, position_m) -> np.ndarray:
    gamma = exp.baseline.specific_attenuation_db_per_km(scenario["frequency_hz"], exp.config.polarization)
    return atm.attenuation_map_db(position_m, exp.grid, gamma)


def measured_trace_seconds(cache: PathGainCache, rays_per_site: int, cell_size_m: float,
                           variant: str | None = None) -> list[float]:
    """Trace times recorded in the cache for jobs with this ray count, cell size and variant (this PC)."""
    seconds = []
    for meta in cache.root.glob("*/*.json"):
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            job = m["job"]
            if (int(job["rays_per_site"]) == int(rays_per_site)
                    and float(job["grid"]["cell_size_m"]) == float(cell_size_m)
                    and (variant is None or job["engine"]["variant"] == variant)):
                seconds.append(float(m["seconds"]))
        except (KeyError, ValueError, TypeError):
            continue
    return seconds


def workload(jobs: list[PropagationJob], cache: PathGainCache, rays_per_site: int, cell_size_m: float) -> dict:
    """How many jobs are cached, how many must be traced, and the time measured so far for such jobs."""
    unique = {j.key(): j for j in jobs}
    cached = sum(1 for k in unique if cache.has(k))
    to_trace = len(unique) - cached
    variant = jobs[0].engine["variant"] if jobs else None
    measured = measured_trace_seconds(cache, rays_per_site, cell_size_m, variant)
    estimate = None
    if measured:
        median = statistics.median(measured)
        estimate = {"median_seconds_per_job": round(median, 1), "max_seconds_per_job": round(max(measured), 1),
                    "measurements": len(measured),
                    "estimated_seconds": round(median * to_trace, 0),
                    "variant": variant,
                    "note": "Trace time only, measured on this PC with this backend. Worker start-up, scene "
                            "loading and kernel-compilation retries added 44 % (standard run) and 70 % "
                            "(preview run) on CPU. Not a laptop estimate."}
    return {"jobs": len(unique), "cached": cached, "to_trace": to_trace, "estimate": estimate}
