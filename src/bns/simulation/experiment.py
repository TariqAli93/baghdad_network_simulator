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
    """The experiment cannot run as configured (missing dataset, research refusal, ...)."""


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
    extra: dict = field(default_factory=dict)

    @property
    def receiver_buildings(self) -> list[ht.Building]:
        box = self.area.receiver_box()
        return [b for b in self.buildings if box.contains(b.polygon.representative_point())]


def load_scenarios(root: Path) -> list[dict]:
    scenarios = yaml.safe_load((Path(root) / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))["scenarios"]
    for sc in scenarios:
        sc["frequency_hz"], sc["bandwidth_hz"] = float(sc["frequency_hz"]), float(sc["bandwidth_hz"])
    return sorted(scenarios, key=lambda s: s["frequency_hz"])


def resolve_backend(requested: str, config: SimulationConfig, mode: str) -> tuple[str, str]:
    """'cpu', 'gpu' or 'auto' -> the backend to use and why. GPU never silently replaces a refusal."""
    from bns import runtime

    if requested not in ("cpu", "gpu", "auto"):
        raise ExperimentError(f"backend must be cpu, gpu or auto, not {requested!r}.")
    statuses = {k: (v or {}).get("status", "") for k, v in (config.backends or {}).items()}
    if requested == "cpu":
        return "cpu", "CPU selected."
    if requested == "auto" and mode == "research":
        return "cpu", "Auto in research mode: CPU, the only production backend."
    available, message = runtime.probe_gpu()
    if requested == "gpu":
        if not available:
            raise ExperimentError(message)
        if mode == "research" and statuses.get("gpu") != "production":
            raise ExperimentError(f"The GPU backend is '{statuses.get('gpu')}', not approved for research runs.")
        return "gpu", message
    return ("gpu", message) if available else ("cpu", message)


def require_research_profile(profile: Profile, mode: str) -> None:
    """Research runs need a profile whose convergence the supervisor accepted (status 'approved')."""
    if mode == "research" and profile.status != "approved":
        raise ExperimentError(f"Profile '{profile.name}' is '{profile.status or 'not assessed'}', not accepted for research "
                              "(set its status to 'approved' in configs/simulation.yaml after the supervisor's decision).")


def load(root: Path, area_name: str, variant: str, profile_name: str, mode: str,
         backend: str = "cpu") -> Experiment:
    root = Path(root)
    areas = load_study_areas(root / "configs" / "study_area.yaml")
    if area_name not in areas:
        raise ExperimentError(f"Unknown study area '{area_name}'.")
    area = areas[area_name]
    if mode == "research" and not area.is_research_dataset:
        raise ExperimentError(f"Research mode needs an approved study district; {area.name} is a {area.role}.")
    system = RadioSystem.load(root / "configs" / "radio_system.yaml")
    config = SimulationConfig.load(root / "configs" / "simulation.yaml")
    try:
        profile = config.profile(profile_name)
    except KeyError as exc:
        raise ExperimentError(str(exc)) from exc
    require_research_profile(profile, mode)
    label = system.label(USED, mode=mode)             # refuses unapproved values in research mode
    baseline, _ = atm.load_conditions(root / "configs" / "atmosphere.yaml")
    scene_dir = root / "data" / "scenes" / area.name / variant
    if not (scene_dir / "scene.xml").exists():
        raise ExperimentError(f"No dataset {scene_dir}; run scripts/build_dataset.py --area {area.name} first.")
    quality = json.loads((scene_dir / "quality_report.json").read_text(encoding="utf-8"))
    buildings = pipeline.load_buildings(scene_dir, area)
    rx_height = system.require("rx_height_m", mode=mode)
    grid = area.receiver_grid(profile.cell_size_m, rx_height)
    outdoor = outdoor_mask(grid, [b.polygon for b in buildings])
    antennas = sector_antennas(system, mode=mode, polarization=config.polarization)
    mast = system.require("antenna_height_above_roof_m", mode=mode)
    chosen, note = resolve_backend(backend, config, mode)
    return Experiment(root, area, variant, mode, profile, system, config, load_scenarios(root), baseline,
                      label, scene_dir, quality, buildings, grid, outdoor, antennas, mast, chosen, note)


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


def observed_sites(exp: Experiment, count: int, *, min_height_m: float, min_spacing_m: float):
    """Tallest receiver-area buildings whose height is OBSERVED (not estimated or placeholder)."""
    return sites.rooftop_candidates(exp.receiver_buildings, mast_height_m=exp.mast_height_m,
                                    min_height_m=min_height_m, min_area_m2=0.0,
                                    min_spacing_m=min_spacing_m, max_candidates=count,
                                    categories=(ht.OBSERVED,))


def jobs_for(exp: Experiment, placed: list[sites.Candidate]) -> dict[str, list[tuple[int, PropagationJob]]]:
    """Per scenario: (site index, job) for every sector of every site."""
    out = {}
    for sc in exp.scenarios:
        out[sc["id"]] = [(i, job) for i, s in enumerate(placed)
                         for job in site_jobs(exp.scene_dir, sc["frequency_hz"], (s.x, s.y, s.z), exp.antennas,
                                              exp.grid, exp.config, exp.profile.rays_per_site, exp.backend)]
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
