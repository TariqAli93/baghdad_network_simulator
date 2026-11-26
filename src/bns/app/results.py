"""Saved experiment runs: find them, read their manifests, summaries and maps.

The application shows results from these folders only; it never recomputes
propagation to display a run. Two kinds exist:
  single_site  scripts/run_single_site.py  (bands.npz)
  multi_site   scripts/run_multi_site.py   (network.npz; one site is the single-site case)
  site_plan    scripts/plan_sites.py       (plan.npz; final network of the selected sites per scenario)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from bns.geospatial.grid import Grid

ARRAYS = {"single_site": "bands.npz", "multi_site": "network.npz", "site_plan": "plan.npz"}

# Fields that must match before two runs are compared as the same experiment.
COMPARABLE = {
    "area": lambda m: (m["area"]["name"], m["area"].get("variant"), m["area"].get("scene_fingerprint")),
    "receiver grid": lambda m: json.dumps(m["grid"], sort_keys=True),
    "profile": lambda m: (m["profile"]["name"], m["profile"]["cell_size_m"], m["profile"]["rays_per_site"]),
    "propagation mechanisms": lambda m: json.dumps(m.get("mechanisms"), sort_keys=True),
    "antennas": lambda m: json.dumps(m.get("sectors_per_site") or m.get("site", {}).get("sectors"), sort_keys=True),
    "radio parameters": lambda m: json.dumps(m.get("radio_parameters"), sort_keys=True),
    "sensitivity overrides": lambda m: json.dumps(m.get("overrides_for_sensitivity") or {}, sort_keys=True),
    "backend": lambda m: (m.get("backend") or {}).get("name", "cpu"),
    "mode": lambda m: m.get("mode"),
}


def invalidated(root: Path) -> dict[str, str]:
    """run id -> reason, from configs/invalidated_runs.yaml (runs kept but not to be interpreted)."""
    import yaml

    path = Path(root) / "configs" / "invalidated_runs.yaml"
    if not path.exists():
        return {}
    return {str(k): str(v) for k, v in ((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("runs")
                                        or {}).items()}


@dataclass
class Run:
    path: Path
    manifest: dict
    summary: dict
    invalid: str | None = None       # reason, when the run is invalid for research interpretation

    @property
    def run_id(self) -> str:
        return self.manifest.get("run_id", self.path.name)

    @property
    def kind(self) -> str:
        return self.manifest.get("kind", "single_site")

    @property
    def label(self) -> str:
        return self.manifest.get("label", "")

    @property
    def is_development(self) -> bool:
        return self.manifest.get("mode") != "research"

    @property
    def scenarios(self) -> list[dict]:
        return self.manifest["scenarios"]

    @property
    def grid(self) -> Grid:
        g = self.manifest["grid"]
        return Grid(tuple(g["center_xy"]), tuple(g["size_xy"]), float(g["cell_size_m"]), float(g["height_m"]))

    @property
    def sites(self) -> list[dict]:
        """[{candidate_id, x, y, z, building_id, roof_height_m, height_category}, ...] (candidates for a plan)"""
        if self.kind in ("multi_site", "site_plan"):
            return self.manifest["sites"]
        c = dict(self.manifest["site"]["candidate"])
        return [c]

    def sites_for(self, scenario_id: str) -> list[dict]:
        """Sites transmitting in this scenario's maps (a plan's selection, in selection order)."""
        if self.kind != "site_plan":
            return self.sites
        by_id = {s["candidate_id"]: s for s in self.sites}
        return [by_id[i] for i in self.summary["results"][scenario_id]["selected"]]

    @property
    def backend(self) -> str:
        return (self.manifest.get("backend") or {}).get("name", "cpu")

    @property
    def sector_azimuths_rad(self) -> list[float]:
        sectors = self.manifest.get("sectors_per_site") or self.manifest.get("site", {}).get("sectors", [])
        return [float(s["orientation_rad"][0]) for s in sectors if s.get("pattern") != "iso"]

    @property
    def sector_bearings_deg(self) -> list[float]:
        """Compass bearings of the recorded sector yaws (the recorded engine values, only converted)."""
        from bns.simulation.setup import scene_azimuth_to_bearing_deg
        return [scene_azimuth_to_bearing_deg(a) for a in self.sector_azimuths_rad]

    @cached_property
    def arrays(self):
        return np.load(self.path / ARRAYS[self.kind])

    @property
    def outdoor(self) -> np.ndarray:
        return self.arrays["outdoor"]

    def layer(self, scenario_id: str, name: str) -> np.ndarray | None:
        key = f"{scenario_id}_{name}"
        return self.arrays[key] if key in self.arrays.files else None

    def layers(self) -> list[str]:
        sid = self.scenarios[0]["id"]
        return [k[len(sid) + 1:] for k in self.arrays.files if k.startswith(sid + "_") and "_alone" not in k]

    def scenario_summary(self, scenario_id: str) -> dict:
        """The radio summary of the whole configuration (all sites; a plan's final selection)."""
        r = self.summary["results"][scenario_id]
        if self.kind == "multi_site":
            return r["network"]
        if self.kind == "site_plan":
            return r["final"] or {}
        return r

    def site_alone_sinr(self, scenario_id: str, site_index: int) -> np.ndarray | None:
        return self.layer(scenario_id, f"alone{site_index}_sinr_db")


def load_run(path: Path) -> Run:
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    return Run(path, manifest, summary)


def list_runs(root: Path) -> list[Run]:
    """Every complete run under outputs/runs/{development,research}, newest first."""
    bad = invalidated(root)
    runs = []
    for mode in ("research", "development"):
        folder = Path(root) / "outputs" / "runs" / mode
        if not folder.exists():
            continue
        for d in folder.iterdir():
            if not (d / "manifest.json").exists() or not (d / "summary.json").exists():
                continue
            try:
                run = load_run(d)
            except (ValueError, KeyError):
                continue
            if (d / ARRAYS.get(run.kind, "")).exists():
                run.invalid = bad.get(run.run_id)
                runs.append(run)
    # newest first, invalid runs after every valid one (kept for reproducibility, never the default)
    runs.sort(key=lambda r: r.manifest.get("created_utc", ""), reverse=True)
    return [r for r in runs if not r.invalid] + [r for r in runs if r.invalid]


def differences(a: Run, b: Run) -> list[str]:
    """Material configuration differences between two runs (empty: comparable as one experiment)."""
    out = []
    for name, key in COMPARABLE.items():
        try:
            if key(a.manifest) != key(b.manifest):
                out.append(name)
        except (KeyError, TypeError):
            out.append(f"{name} (not recorded)")
    return out


def list_validations(root: Path) -> list[Path]:
    """TR 38.901 comparison folders under outputs/validation, newest first."""
    folder = Path(root) / "outputs" / "validation"
    return sorted((d for d in folder.glob("tr38901-*") if (d / "summary.json").exists()), reverse=True) \
        if folder.exists() else []


def cdf(values: np.ndarray, floor: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Sorted values and the share at or below each; -inf replaced by `floor` if given."""
    v = np.asarray(values, dtype=float).ravel()
    if floor is not None:
        v = np.where(np.isfinite(v), v, floor)
    v = np.sort(v[np.isfinite(v)])
    return v, np.arange(1, v.size + 1) / max(v.size, 1)
