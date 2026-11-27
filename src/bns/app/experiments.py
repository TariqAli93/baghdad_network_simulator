"""Experiments: editable workspace configurations, kept apart from the runs made from them (no UI code).

An experiment is a configuration a user edits and saves: dataset, simulation settings, radio values,
carriers and stations. Saving rewrites only that configuration (outputs/experiments/<id>.json, an
atomic replace). A completed simulation is a run (outputs/runs/<mode>/<run id>/), immutable, which
records the experiment it came from and a copy of the configuration it executed; an experiment's
runs are found from those records, so editing, renaming or deleting an experiment never touches a
result. Deleting moves the configuration to outputs/experiments/.deleted/ (recoverable).
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Experiment:
    experiment_id: str
    name: str
    area: str
    variant: str
    profile: str                   # preview | standard | custom
    cell_size_m: float
    rays_per_site: int
    backend: str
    rx_height_m: float
    radio: dict                    # bns.app.workspace.RadioSettings fields
    carriers: list[dict]           # bns.app.carriers
    stations: list[dict]           # bns.app.workspace.Station fields
    template: dict = field(default_factory=dict)   # values for new stations
    created_utc: str = ""
    modified_utc: str = ""
    origin: dict = field(default_factory=dict)     # saved_as_from / duplicated_from / opened_from_run
    notes: str = ""
    schema: int = SCHEMA

    @classmethod
    def new(cls, name: str, **values) -> "Experiment":
        now = _now()
        return cls(experiment_id=new_id(name), name=name, created_utc=now, modified_utc=now, **values)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Experiment":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


ENV = "BNS_EXPERIMENTS_DIR"                 # tests point this at a temporary folder


def folder(root: Path) -> Path:
    return Path(os.environ[ENV]) if os.environ.get(ENV) else Path(root) / "outputs" / "experiments"


def new_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().encode("ascii", "ignore").decode()).strip("-")[:32]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return "-".join(p for p in ("exp", stamp, slug, secrets.token_hex(2)) if p)


def _path(root: Path, experiment_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", experiment_id):
        raise ValueError(f"Not an experiment id: {experiment_id!r}")
    return folder(root) / f"{experiment_id}.json"


def save(root: Path, experiment: Experiment) -> Experiment:
    """Write the configuration (atomically) and return it with its modification time."""
    if not experiment.name.strip():
        raise ValueError("An experiment needs a name.")
    saved = replace(experiment, name=experiment.name.strip(), modified_utc=_now())
    path = _path(root, saved.experiment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{secrets.token_hex(4)}.tmp")
    tmp.write_text(json.dumps(saved.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return saved


def load(root: Path, experiment_id: str) -> Experiment:
    return Experiment.from_dict(json.loads(_path(root, experiment_id).read_text(encoding="utf-8")))


def list_all(root: Path) -> list[Experiment]:
    """Every readable experiment, most recently modified first (unreadable files are skipped)."""
    out = []
    base = folder(root)
    for path in base.glob("*.json") if base.exists() else []:
        try:
            out.append(Experiment.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except (ValueError, TypeError, KeyError):
            continue
    return sorted(out, key=lambda e: e.modified_utc, reverse=True)


def save_as(root: Path, experiment: Experiment, name: str) -> Experiment:
    now = _now()
    copy = replace(experiment, experiment_id=new_id(name), name=name, created_utc=now, modified_utc=now,
                   origin={"saved_as_from": experiment.experiment_id})
    return save(root, copy)


def duplicate(root: Path, experiment_id: str, name: str) -> Experiment:
    original = load(root, experiment_id)
    now = _now()
    return save(root, replace(original, experiment_id=new_id(name), name=name, created_utc=now, modified_utc=now,
                              origin={"duplicated_from": experiment_id}))


def rename(root: Path, experiment_id: str, name: str) -> Experiment:
    return save(root, replace(load(root, experiment_id), name=name))


def delete(root: Path, experiment_id: str) -> None:
    """Move the configuration to .deleted/ (runs made from it stay in the history)."""
    path = _path(root, experiment_id)
    trash = folder(root) / ".deleted"
    trash.mkdir(parents=True, exist_ok=True)
    os.replace(path, trash / f"{experiment_id}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json")


def runs_of(root: Path, experiment_id: str) -> list[str]:
    """Run ids made from this experiment, newest first (from the runs' own manifests)."""
    found = []
    for manifest in (Path(root) / "outputs" / "runs").glob("*/*/manifest.json"):
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (m.get("experiment") or {}).get("id") == experiment_id:
            found.append((m.get("created_utc", ""), manifest.parent.name))
    return [name for _, name in sorted(found, reverse=True)]


# ---------------------------------------------------------------- configuration -> workspace objects
def base_profile(experiment: Experiment) -> str:
    return "standard" if experiment.profile == "custom" else experiment.profile


def overrides(root: Path, experiment: Experiment) -> dict:
    """Grid- and profile-changing values that differ from the research baseline (they enter job keys)."""
    from bns.simulation import experiment as ex

    values = {"rx_height_m": float(experiment.rx_height_m)}
    if experiment.profile == "custom":
        values.update(cell_size_m=float(experiment.cell_size_m), rays_per_site=int(experiment.rays_per_site))
    return ex.differences(values, ex.baseline_values(root, base_profile(experiment)))


def context(root: Path, experiment: Experiment):
    """The loaded experiment context (bns.app.workspace.Context) this configuration runs in."""
    from bns.app import workspace as ws
    from bns.simulation import experiment as ex

    return ws.Context.from_experiment(ex.load(root, experiment.area, experiment.variant, base_profile(experiment),
                                              backend=experiment.backend, overrides=overrides(root, experiment)))


def stations(experiment: Experiment) -> list:
    from bns.app import workspace as ws
    return [ws.Station(**s) for s in experiment.stations]


def radio(experiment: Experiment):
    from bns.app import workspace as ws
    return ws.RadioSettings(**experiment.radio)
