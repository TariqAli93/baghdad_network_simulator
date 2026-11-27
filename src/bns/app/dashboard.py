"""What the dashboard shows, assembled from saved runs, run control and the configuration (no UI code).

The dashboard answers: what is simulated, is it ready, what happened in the latest simulation, how
the five scenarios compare, and what to do next. Nothing here is computed scientifically; values
come from saved runs and the dataset records, and missing values stay missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from bns.app import control, evidence, results

NEXT_STEPS = ("progress", "first_run", "explore_coverage", "compare", "review_limitations", "report", "new_experiment")


@dataclass
class Dashboard:
    area: dict                          # name, role, centre, receiver size, primary variant
    dataset: dict                       # buildings, synthetic share, documented heights, quality class
    scenarios: list[dict]
    latest: results.Run | None          # newest completed, valid run
    running: control.RunState | None    # a run in progress, if any
    bands: list[dict] = field(default_factory=list)     # evidence.band_table(latest)
    next_step: str = "first_run"


def latest_completed(root: Path) -> results.Run | None:
    """Newest saved run that is not invalidated (any kind), or None."""
    runs = [r for r in results.list_runs(root) if not r.invalid]
    return max(runs, key=lambda r: r.manifest.get("created_utc", ""), default=None)


def running_run(root: Path) -> control.RunState | None:
    for folder in control.history(root):
        s = control.state(folder)
        if s.running:
            return s
    return None


def next_step(*, running: bool, latest: bool, visited: set[str], validated: bool) -> str:
    """One context-aware recommendation, in workflow order."""
    if running:
        return "progress"
    if not latest:
        return "first_run"
    for page, step in (("coverage", "explore_coverage"), ("comparison", "compare")):
        if page not in visited:
            return step
    if not validated and "limitations" not in visited:
        return "review_limitations"
    if "reports" not in visited:
        return "report"
    return "new_experiment"


def study_summary(root: Path) -> tuple[dict, dict]:
    """The study district and its primary dataset (from configs/study_area.yaml and the dataset record)."""
    import json

    areas = yaml.safe_load((Path(root) / "configs" / "study_area.yaml").read_text(encoding="utf-8"))["areas"]
    name, area = next(((n, a) for n, a in areas.items() if a.get("approved")), next(iter(areas.items())))
    variant = area.get("primary_variant") or "osm"
    info = {"name": name, "role": area.get("role"), "center": area.get("center"),
            "receiver_area_m": area.get("receiver_area_m"), "variant": variant}
    quality_path = Path(root) / "outputs" / "datasets" / name / variant / "quality_report.json"
    dataset = {"available": quality_path.exists()}
    if quality_path.exists():
        q = json.loads(quality_path.read_text(encoding="utf-8"))
        cats = (q.get("height_categories") or {}).get("by_count") or {}
        syn = ((q.get("height_model") or {}).get("synthetic") or {})
        dataset.update(buildings=q.get("buildings"), documented=cats.get("observed", 0) + cats.get("estimated", 0),
                       synthetic=syn.get("synthetic_buildings"), synthetic_percent=syn.get("synthetic_percent"),
                       plain_placeholders=syn.get("remaining_placeholders", cats.get("placeholder")),
                       fit_for_research=bool(q.get("fit_for_research")), model=(q.get("height_model") or {}).get("name"))
    return info, dataset


def build(root: Path, visited: set[str] | None = None) -> Dashboard:
    from bns.simulation.experiment import load_scenarios

    area, dataset = study_summary(root)
    latest = latest_completed(root)
    running = running_run(root)
    bands = evidence.band_table(latest) if latest is not None else []
    validated = bool(latest is not None and latest.classification.validated)
    return Dashboard(area, dataset, load_scenarios(root), latest, running, bands,
                     next_step(running=running is not None, latest=latest is not None, visited=visited or set(),
                               validated=validated))


def ranges(bands: list[dict], key: str) -> tuple[float, float] | None:
    """(min, max) of a band-table column over the five scenarios, ignoring missing values."""
    values = [b[key] for b in bands if b.get(key) is not None]
    return (min(values), max(values)) if values else None
