"""Research readiness: scientific and technical status indicators, computed from the files.

    dataset        a dataset of the study district is built for the current requirements
    heights        building-height completeness (the dataset's quality report)
    observations   progress of the required field observations, per method group
    candidates     candidate rooftops available under the site rule (target 20-40)
    configuration  the configuration files hold the research baseline, or a custom configuration
    convergence    ray-count convergence on the final scene
    validation     analytical and model-to-model (TR 38.901) validation
    matlab         MATLAB cross-check
    laptop         target-laptop acceptance

States: "Ready", "Completed", "Incomplete data", "Validation Pending", "Research Baseline",
"Custom Experiment". These are information: none of them blocks a simulation. Whether a result
is a validated research result is decided per run by bns.analysis.classification. A state is
never "Completed" without the evidence behind it.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from bns.analysis import research_baseline

READY, COMPLETED, INCOMPLETE, PENDING = "Ready", "Completed", "Incomplete data", "Validation Pending"
SYNTHETIC_COMPLETE = "Synthetic Data Complete"
BASELINE, CUSTOM = "Research Baseline", "Custom Experiment"
@dataclass
class Indicator:
    id: str
    title: str
    state: str
    detail: str
    data: dict = field(default_factory=dict)


def _yaml(root: Path, name: str) -> dict:
    path = Path(root) / "configs" / name
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def research_areas(root: Path) -> dict[str, dict]:
    return {n: a for n, a in (_yaml(root, "study_area.yaml").get("areas") or {}).items() if a.get("approved")}


def _datasets(root: Path, area: str) -> list[tuple[Path, dict, dict]]:
    """(folder, quality report, manifest) of every built dataset of the area, newest first."""
    out = []
    for folder in sorted((Path(root) / "outputs" / "datasets" / area).glob("*/")):
        q, m = folder / "quality_report.json", folder / "dataset_manifest.json"
        if q.exists() and m.exists():
            out.append((folder, json.loads(q.read_text(encoding="utf-8")), json.loads(m.read_text(encoding="utf-8"))))
    return sorted(out, key=lambda t: t[2].get("created_utc", ""), reverse=True)


def _current(root: Path, name: str, area: dict) -> list[tuple[Path, dict, dict]]:
    """Datasets built for the area's current observation requirements."""
    req = area.get("observations") or {}
    required = list(req.get("required_priorities") or [])
    rules = req.get("method_requirements") or None

    def built_for(t):
        rec = (t[2].get("inputs") or {}).get("required_observations") or {}
        return list(rec.get("required_priorities") or []) == required and (rec.get("method_requirements") or None) == rules
    return [t for t in _datasets(root, name) if built_for(t)]


def _dataset(root: Path, areas: dict) -> Indicator:
    if not areas:
        return Indicator("dataset", "Dataset availability", INCOMPLETE, "no study district configured")
    name, area = next(iter(areas.items()))
    current = _current(root, name, area)
    if current:
        # the configured primary variant, else a dataset fit for research, else the newest
        primary = [t for t in current if t[0].name == area.get("primary_variant")]
        fit = [t for t in current if t[1].get("fit_for_research")]
        folder, quality, _ = (primary or fit or current)[0]
        return Indicator("dataset", "Dataset availability", READY, f"{name}/{folder.name}",
                         {"area": name, "variant": folder.name, "quality": quality})
    if _datasets(root, name):
        return Indicator("dataset", "Dataset availability", INCOMPLETE,
                         f"the dataset of {name} records older observation requirements; rebuild it "
                         "(scripts/build_dataset.py)", {"area": name})
    return Indicator("dataset", "Dataset availability", INCOMPLETE, f"no dataset of {name} built", {"area": name})


def _heights(root: Path, areas: dict) -> Indicator:
    if not areas:
        return Indicator("heights", "Building-height completeness", INCOMPLETE, "no study district")
    name, area = next(iter(areas.items()))
    current = _current(root, name, area)
    if not current:
        return Indicator("heights", "Building-height completeness", INCOMPLETE, "no current dataset")
    # documented heights: the datasets without a height model (synthetic heights are reported separately)
    empirical = [t for t in current if not t[1].get("height_model")] or current
    fit = [t for t in empirical if t[1].get("fit_for_research")]
    folder, q, _ = (fit or empirical)[0]
    pct = (q.get("height_categories") or {}).get("by_count_percent") or {}
    shares = ", ".join(f"{k} {v:.1f} %" for k, v in pct.items())
    if fit:
        return Indicator("heights", "Building-height completeness", READY,
                         f"{folder.name}: {shares}; remaining placeholders covered by the height sensitivity analysis",
                         {"percent": pct})
    return Indicator("heights", "Building-height completeness", INCOMPLETE,
                     f"{folder.name}: {shares}. " + "; ".join(q.get("not_fit_reasons") or []), {"percent": pct})


def _observations(root: Path, areas: dict) -> Indicator:
    title = "Observation progress"
    if not areas:
        return Indicator("observations", title, INCOMPLETE, "no study district")
    name, area = next(iter(areas.items()))
    req = area.get("observations") or {}
    required_p = list(req.get("required_priorities") or [])
    worklist = Path(root) / str(req.get("worklist", ""))
    if not req.get("worklist") or not worklist.exists():
        return Indicator("observations", title, INCOMPLETE, "no observation worklist configured or found")
    with open(worklist, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    required = [r for r in rows if r["priority"] in required_p]
    sensitivity = Counter(r["priority"] for r in rows if r["priority"] in (req.get("covered_by_sensitivity") or []))
    current = _current(root, name, area)
    record = (current[0][2].get("observation_worklist") or {}) if current else {}
    missing = set(record.get("missing") or []) if current else {r["building_id"] for r in required}
    by_priority = {p: {"required": sum(r["priority"] == p for r in required),
                       "observed": sum(r["priority"] == p and r["building_id"] not in missing for r in required)}
                   for p in required_p}
    observed = sum(v["observed"] for v in by_priority.values())
    # priorities accepting the same observation methods form one group with its own progress
    rules = req.get("method_requirements") or {}
    groups: dict[tuple, dict] = {}
    for p in required_p:
        key = tuple(rules.get(p) or ["any"])
        g = groups.setdefault(key, {"priorities": [], "accepted": list(key),
                                    "preferred": list((req.get("preferred") or {}).get(p) or []),
                                    "required": 0, "observed": 0})
        g["priorities"].append(p)
        g["required"] += by_priority[p]["required"]
        g["observed"] += by_priority[p]["observed"]
    data = {"required": len(required), "observed": observed, "by_priority": by_priority,
            "groups": list(groups.values()), "insufficient": len(record.get("insufficient") or []),
            "covered_by_sensitivity": dict(sensitivity), "stage": req.get("stage"),
            "required_priorities": required_p}
    detail = "; ".join(f"{', '.join(g['priorities'])}: {g['observed']} of {g['required']}" for g in groups.values())
    if data["insufficient"]:
        detail += f"; {data['insufficient']} observed with a method their priority does not accept"
    if not current:
        detail += "; rebuild the dataset for the current requirements (scripts/build_dataset.py)"
    done = bool(current) and bool(required) and observed == len(required)
    return Indicator("observations", title, COMPLETED if done else INCOMPLETE, detail, data)


def _candidates(root: Path, areas: dict) -> Indicator:
    """Candidate rooftops under the site rule, counted on the current dataset (geometry only)."""
    from bns.geospatial import pipeline, sites
    from bns.geospatial.study_area import load_study_areas

    title = "Candidate-site availability"
    rule = _yaml(root, "site_rule.yaml")
    t = rule.get("candidate_thresholds") or {}
    target = list(rule.get("candidate_count_target") or [20, 40])
    values = {k: t.get(k) for k in ("min_roof_height_m", "min_roof_area_m2", "min_spacing_m")}
    if any(v is None for v in values.values()):
        return Indicator("candidates", title, INCOMPLETE, "candidate criteria not set (configs/site_rule.yaml)", values)
    dataset = _dataset(root, areas)
    if dataset.state != READY:
        return Indicator("candidates", title, INCOMPLETE, "no current dataset", values)
    scene = Path(root) / "data" / "scenes" / dataset.data["area"] / dataset.data["variant"]
    if not (scene / "buildings.geojson").exists():
        return Indicator("candidates", title, INCOMPLETE, f"scene {scene.name} not built on this computer", values)
    area = load_study_areas(Path(root) / "configs" / "study_area.yaml")[dataset.data["area"]]
    box = area.receiver_box()
    inside = [b for b in pipeline.load_buildings(scene, area) if box.contains(b.polygon.representative_point())]
    mast = float(((_yaml(root, "radio_system.yaml").get("parameters") or {}).get("antenna_height_above_roof_m")
                  or {}).get("value") or 0.0)
    cats = sites.candidate_categories(rule.get("candidate_height_categories"),
                                      (dataset.data.get("quality") or {}).get("height_model"))
    found = sites.rooftop_candidates(inside, mast_height_m=mast, min_height_m=values["min_roof_height_m"],
                                     min_area_m2=values["min_roof_area_m2"], min_spacing_m=values["min_spacing_m"],
                                     categories=cats)
    data = {**values, "count": len(found), "target": target, "variant": dataset.data["variant"]}
    heights = "observed, storey-based or synthetic heights" if "placeholder" in cats else "observed or storey-based heights"
    rule_text = (f"{dataset.data['variant']}: roof ≥ {values['min_roof_height_m']:g} m, "
                 f"≥ {values['min_roof_area_m2']:g} m², ≥ {values['min_spacing_m']:g} m apart, {heights}")
    if len(found) < target[0]:
        return Indicator("candidates", title, INCOMPLETE,
                         f"{len(found)} candidates ({rule_text}); target {target[0]}-{target[1]}: needs the survey", data)
    note = "" if len(found) <= target[1] else "; above the target: refine the thresholds (documented, geometric)"
    return Indicator("candidates", title, READY, f"{len(found)} candidates ({rule_text}){note}", data)


def _synthetic(root: Path, areas: dict) -> Indicator:
    """Completion of the Synthetic Urban Model on the primary dataset: every building has a height
    (documented or synthetic). Separate from empirical completeness and from validation."""
    title = "Synthetic Urban Model"
    dataset = _dataset(root, areas)
    model = ((dataset.data.get("quality") or {}).get("height_model") or {})
    syn = model.get("synthetic")
    if dataset.state != READY or not syn:
        return Indicator("synthetic", title, INCOMPLETE, "the primary dataset is not a Synthetic Urban Model")
    state = SYNTHETIC_COMPLETE if syn["remaining_placeholders"] == 0 else INCOMPLETE
    return Indicator("synthetic", title, state,
                     f"{dataset.data['variant']}: {syn['synthetic_buildings']} of {syn['buildings']} buildings "
                     f"({syn['synthetic_percent']:.1f} %) with estimated building heights ({syn['algorithm']}, "
                     f"{syn['scenario']} scenario, seed {model.get('seed')}); {syn['remaining_placeholders']} plain "
                     "placeholders. Synthetic completion, not empirical validation.", syn)


def _configuration(root: Path) -> Indicator:
    from bns.analysis.radio_system import RadioSystem
    from bns.simulation.setup import SimulationConfig

    title = "Configuration"
    try:
        RadioSystem.load(Path(root) / "configs" / "radio_system.yaml")
        SimulationConfig.load(Path(root) / "configs" / "simulation.yaml")
    except Exception as exc:                       # invalid values are reported, never run
        return Indicator("configuration", title, INCOMPLETE, f"invalid configuration: {exc}")
    changed = research_baseline.modified(root)
    if changed:
        return Indicator("configuration", title, CUSTOM,
                         "the configuration files differ from the research baseline in: "
                         + ", ".join(i.name for i in changed), {"modified": [i.name for i in changed]})
    return Indicator("configuration", title, BASELINE, "the configuration files hold the approved research baseline")


def convergence_record(root: Path, profile: str | None) -> dict:
    """The final-scene convergence record of a profile (configs/simulation.yaml): {} when not accepted.
    An accepted record names the scene fingerprint and backend it was measured with."""
    entry = ((_yaml(root, "simulation.yaml").get("profiles") or {}).get(profile or "") or {})
    rec = entry.get("final_scene_convergence")
    if isinstance(rec, dict) and rec.get("status") in ("accepted", "completed"):
        return {**rec, "cell_size_m": entry.get("cell_size_m"), "rays_per_site": entry.get("rays_per_site")}
    return {}


def _convergence(root: Path) -> Indicator:
    title = "Simulation convergence"
    profiles = _yaml(root, "simulation.yaml").get("profiles") or {}
    research = [n for n, p in profiles.items() if (p or {}).get("status") == "approved"]
    records = {n: convergence_record(root, n) for n in research}
    if research and all(records.values()):
        return Indicator("convergence", title, COMPLETED,
                         ", ".join(f"{n}: accepted on scene {r.get('scene_fingerprint', '?')[:12]}…, "
                                   f"{r.get('backend', 'cpu').upper()}" for n, r in records.items())
                         + " (applies only to runs on that scene, profile and backend)", records)
    states = {n: (profiles[n].get("final_scene_convergence") if not isinstance(profiles[n].get("final_scene_convergence"), dict)
                  else profiles[n]["final_scene_convergence"].get("status")) or "not evaluated" for n in research}
    return Indicator("convergence", title, PENDING,
                     "measured on the provisional scene (docs/convergence.md); on the final scene: "
                     + ", ".join(f"{n} {s}" for n, s in states.items())
                     + " (scripts/run_convergence.py once the dataset is complete)", states)


def _validation(root: Path) -> Indicator:
    title = "Validation (analytical, TR 38.901)"
    tr = sorted((Path(root) / "outputs" / "validation").glob("*/summary.json"))
    if tr:
        return Indicator("validation", title, COMPLETED,
                         f"analytical engine checks (Phase 0, unit and engine tests) and {len(tr)} TR 38.901 "
                         "model-to-model comparison(s), e.g. " + tr[0].parent.name + "; no field measurements")
    return Indicator("validation", title, PENDING, "no TR 38.901 comparison saved (scripts/validate_tr38901.py)")


def matlab_evidence(root: Path) -> list[dict]:
    """Every saved MATLAB comparison: whether it meets the B1 criterion (|median (MATLAB - Sionna)| in
    LOS cells within the configured tolerance, in every band; NLOS and RMSE reported, not judged) and
    the propagation scope of the run it was exported from (bns.analysis.validation_scope)."""
    from bns.analysis import validation_scope as vs

    tol = float(((_yaml(root, "approvals.yaml").get("decisions") or {}).get("B1_validation") or {})
                .get("los_median_abs_tolerance_db", 2.0))
    out = []
    for path in sorted(p for base in ("validation", "outputs/validation")
                       for p in (Path(root) / base).glob("**/comparison.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        los = {k: v for k, v in rows.items() if k.endswith("_LOS")}
        failing = [k for k, v in los.items() if v.get("median_db") is None or abs(float(v["median_db"])) > tol]
        if not los:
            failing.append("no LOS cells")
        scope = None
        case = path.parent / "case.json"
        if case.exists():
            source = Path(root) / json.loads(case.read_text(encoding="utf-8")).get("source_run", "") / "manifest.json"
            if source.exists():
                scope = vs.from_manifest(json.loads(source.read_text(encoding="utf-8")))
        out.append({"path": path, "case": path.parent.name, "passes": not failing, "failing": failing,
                    "tolerance_db": tol, "scope": scope, "scope_key": vs.key(scope)})
    return out


def _matlab(root: Path) -> Indicator:
    title = "MATLAB comparison"
    found = matlab_evidence(root)
    if not found:
        return Indicator("matlab", title, PENDING, "package prepared (validation/matlab/); not run (needs MATLAB "
                                                   "on the laptop)")
    tol = found[0]["tolerance_db"]
    failing = [f"{e['case']}/{k}" for e in found for k in e["failing"]]
    if failing:
        return Indicator("matlab", title, PENDING,
                         f"{len(found)} comparison(s); LOS median beyond ±{tol:.1f} dB or missing in: " + ", ".join(failing),
                         {"failing": failing})
    scoped = [e["case"] for e in found if e["scope_key"]]
    return Indicator("matlab", title, COMPLETED,
                     f"{len(found)} comparison(s); LOS median within ±{tol:.1f} dB in every band (NLOS, RMSE reported); "
                     "applies only to runs with the same scene, grid, rays, engine, antennas and mechanisms as its "
                     "source run" + ("" if len(scoped) == len(found) else " (source run of some comparisons unknown: "
                                     "they apply to no run)"))


def _laptop(root: Path) -> Indicator:
    found = sorted((Path(root) / "outputs" / "acceptance").glob("*/summary.json"))
    if found:
        return Indicator("laptop", "Laptop acceptance", COMPLETED,
                         f"{len(found)} benchmark run(s), latest {found[-1].parent.name}")
    return Indicator("laptop", "Laptop acceptance", PENDING, "benchmark.ps1 not yet run on the target laptop")


def indicators(root: Path) -> list[Indicator]:
    root = Path(root)
    areas = research_areas(root)
    return [_dataset(root, areas), _heights(root, areas), _observations(root, areas), _synthetic(root, areas),
            _candidates(root, areas), _configuration(root), _convergence(root), _validation(root), _matlab(root),
            _laptop(root)]
