"""Research readiness: eight gates, tracked separately and computed from the files.

    methodology         supervisor approvals recorded and unchanged since (approval lock)
    dataset             a dataset of the approved study district is fit for research
    observations        every required worklist building observed (configured priorities)
    candidate_criteria  approved minimum roof height, area and spacing for candidate sites
    convergence         ray-count convergence evaluated and accepted on the final scene
    matlab              MATLAB cross-check executed and assessed with the B1 criterion
    laptop              target-laptop acceptance measured and accepted
    delivery            everything above, plus a written approval reference

The first five are pre-experiment conditions: research runs refuse until all are met
(`require_research_ready`). MATLAB is required before conclusions, the last two before
delivery. A gate is never "met" without the evidence behind it: a reported approval without
a written reference is "reported", a step that has not run is "not executed".
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from bns.analysis import approval_lock

PRE_EXPERIMENT = ("methodology", "dataset", "observations", "candidate_criteria", "convergence")
PASSING = ("met", "reported")


class NotReady(RuntimeError):
    """A research run was requested before the pre-experiment conditions are met."""


@dataclass
class Gate:
    id: str
    title: str
    state: str                      # met | reported | not met | not executed | executed, awaiting review
    detail: str
    needed_before: str              # research runs | conclusions | delivery
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


def _methodology(root: Path) -> Gate:
    approvals = _yaml(root, "approvals.yaml")
    decisions = approvals.get("decisions") or {}
    open_ = [k for k, d in decisions.items() if d.get("status") not in ("approved", "approved_with_condition")]
    bad = [i for i in approval_lock.check(root) if i.state != "locked"]
    reference = str((approvals.get("record") or {}).get("approval_reference", "")).lower()
    written = bool(reference) and not reference.startswith("none")
    data = {"decisions": {k: d.get("status") for k, d in decisions.items()}, "written_reference": written,
            "lock": {i.name: i.state for i in approval_lock.check(root)}}
    if open_ or bad or not decisions:
        why = ([f"decisions not approved: {', '.join(open_)}"] if open_ else []) + \
              ([f"changed or unconfirmed since approval: {', '.join(f'{i.name} ({i.state})' for i in bad)}"] if bad else [])
        return Gate("methodology", "Methodology approval", "not met", "; ".join(why) or "no decisions recorded",
                    "research runs", data)
    conditional = [k for k, d in decisions.items() if d.get("status") == "approved_with_condition"]
    detail = (f"{len(decisions)} decisions approved ({len(conditional)} with an open condition, tracked by the gates "
              f"below); all {len(data['lock'])} approved values unchanged since confirmation")
    if written:
        return Gate("methodology", "Methodology approval", "met", detail, "research runs", data)
    return Gate("methodology", "Methodology approval", "reported",
                detail + "; reported by the project owner, written reference pending", "research runs", data)


def _requirement(area: dict) -> dict:
    return area.get("observations") or {}


def _current(root: Path, name: str, area: dict) -> list[tuple[Path, dict, dict]]:
    """Datasets built for the area's current observation requirement."""
    required = list(_requirement(area).get("required_priorities") or [])
    return [t for t in _datasets(root, name)
            if list(((t[2].get("inputs") or {}).get("required_observations") or {}).get("required_priorities") or [])
            == required]


def _dataset(root: Path, areas: dict) -> Gate:
    if not areas:
        return Gate("dataset", "Dataset fitness", "not met", "no approved study district", "research runs")
    name, area = next(iter(areas.items()))
    built = _datasets(root, name)
    current = _current(root, name, area)
    fit = [t for t in current if t[1].get("fit_for_research")]
    if fit:
        return Gate("dataset", "Dataset fitness", "met", f"{name}/{fit[0][0].name} is fit for research",
                    "research runs", {"variant": fit[0][0].name})
    if not built:
        return Gate("dataset", "Dataset fitness", "not met", f"no dataset of {name} built", "research runs")
    if not current:
        return Gate("dataset", "Dataset fitness", "not met",
                    f"no dataset of {name} built for the current observation requirement; rebuild it "
                    "(scripts/build_dataset.py)", "research runs")
    folder, q, _ = current[0]
    return Gate("dataset", "Dataset fitness", "not met",
                f"{name}/{folder.name}: " + "; ".join(q.get("not_fit_reasons") or ["not fit"]), "research runs",
                {"variant": folder.name, "reasons": q.get("not_fit_reasons") or []})


def _observations(root: Path, areas: dict) -> Gate:
    if not areas:
        return Gate("observations", "Mandatory observations", "not met", "no approved study district", "research runs")
    name, area = next(iter(areas.items()))
    req = _requirement(area)
    required_p = list(req.get("required_priorities") or [])
    worklist = Path(root) / str(req.get("worklist", ""))
    if not req.get("worklist") or not worklist.exists():
        return Gate("observations", "Mandatory observations", "not met", "no observation worklist configured or found",
                    "research runs")
    with open(worklist, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    required = [r for r in rows if r["priority"] in required_p]
    sensitivity = Counter(r["priority"] for r in rows if r["priority"] in (req.get("covered_by_sensitivity") or []))
    current = _current(root, name, area)
    missing = set(((current[0][2].get("observation_worklist") or {}).get("missing")) or []) if current else \
        {r["building_id"] for r in required}
    by_priority = {p: {"required": sum(r["priority"] == p for r in required),
                       "observed": sum(r["priority"] == p and r["building_id"] not in missing for r in required)}
                   for p in required_p}
    observed = sum(v["observed"] for v in by_priority.values())
    data = {"required": len(required), "observed": observed, "by_priority": by_priority,
            "covered_by_sensitivity": dict(sensitivity), "stage": req.get("stage"),
            "required_priorities": required_p}
    detail = f"{observed} of {len(required)} required buildings observed ({', '.join(required_p)})"
    if not current:
        detail += "; the built dataset records an older requirement: rebuild it (scripts/build_dataset.py)"
    state = "met" if current and observed == len(required) and required else "not met"
    return Gate("observations", "Mandatory observations", state, detail, "research runs", data)


def _candidates(root: Path) -> Gate:
    rule = _yaml(root, "site_rule.yaml")
    t = rule.get("candidate_thresholds") or {}
    values = {k: t.get(k) for k in ("min_roof_height_m", "min_roof_area_m2", "min_spacing_m")}
    pending = [k for k, v in values.items() if v is None]
    if rule.get("status") == "approved" and t.get("status") == "approved" and not pending:
        return Gate("candidate_criteria", "Candidate-site criteria", "met",
                    ", ".join(f"{k} {v:g}" for k, v in values.items()), "research runs", values)
    detail = (f"pending: {', '.join(pending)} (chosen after the stage-1 observations, for "
              f"{'-'.join(str(v) for v in rule.get('candidate_count_target') or [])} candidates)") if pending \
        else f"thresholds are '{t.get('status')}', not approved"
    return Gate("candidate_criteria", "Candidate-site criteria", "not met", detail, "research runs", values)


def _convergence(root: Path) -> Gate:
    profiles = _yaml(root, "simulation.yaml").get("profiles") or {}
    approved = {n: p for n, p in profiles.items() if (p or {}).get("status") == "approved"}
    if not approved:
        return Gate("convergence", "Final-scene convergence", "not met", "no profile approved", "research runs")
    states = {n: str(p.get("final_scene_convergence", "not evaluated")) for n, p in approved.items()}
    if all(s == "accepted" for s in states.values()):
        return Gate("convergence", "Final-scene convergence", "met",
                    ", ".join(f"{n}: accepted on the final scene" for n in states), "research runs", states)
    return Gate("convergence", "Final-scene convergence", "not executed",
                ", ".join(f"profile {n}: {s}" for n, s in states.items())
                + " (scripts/run_convergence.py on the final scene, then the supervisor's acceptance)",
                "research runs", states)


def _external(root: Path, gid: str, title: str, decision: str, evidence: list[Path], needed: str, what: str) -> Gate:
    d = (_yaml(root, "approvals.yaml").get("decisions") or {}).get(decision) or {}
    if d.get("status") == "approved" and not d.get("condition"):
        return Gate(gid, title, "met", f"{what} accepted (configs/approvals.yaml)", needed)
    if evidence:
        return Gate(gid, title, "executed, awaiting review",
                    f"{len(evidence)} result file(s), e.g. {evidence[0].as_posix()}; not yet assessed", needed)
    return Gate(gid, title, "not executed", d.get("condition") or f"{what} not executed", needed)


def gates(root: Path) -> list[Gate]:
    root = Path(root)
    areas = research_areas(root)
    out = [_methodology(root), _dataset(root, areas), _observations(root, areas), _candidates(root),
           _convergence(root)]
    matlab = sorted(p.relative_to(root) for base in ("validation", "outputs/validation")
                    for p in (root / base).glob("**/comparison.json"))
    laptop = sorted(p.relative_to(root) for p in (root / "outputs" / "acceptance").glob("*/summary.json"))
    out.append(_external(root, "matlab", "MATLAB validation", "matlab", matlab, "conclusions",
                         "MATLAB cross-check (B1: median |Δ| in LOS cells ≤ 2.0 dB)"))
    out.append(_external(root, "laptop", "Laptop acceptance", "laptop", laptop, "delivery", "laptop benchmark"))
    others = [g for g in out]
    written = out[0].data.get("written_reference", False)
    blocking = [g.title for g in others if g.state != "met"] + ([] if written else ["written approval reference"])
    out.append(Gate("delivery", "Final delivery readiness", "met" if not blocking else "not met",
                    "all gates met" if not blocking else "waiting for: " + ", ".join(blocking), "delivery"))
    return out


def require_research_ready(root: Path) -> None:
    """Refuse a research run unless every pre-experiment gate passes."""
    failing = [g for g in gates(root) if g.id in PRE_EXPERIMENT and g.state not in PASSING]
    if failing:
        raise NotReady("Research mode is locked until the pre-experiment conditions are met: "
                       + "; ".join(f"{g.title}: {g.state} ({g.detail})" for g in failing) + ".")
