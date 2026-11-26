"""Saved experiment runs: find them, read their manifests, summaries and maps.

The application shows results from these folders only; it never recomputes
propagation to display a run. Two kinds exist:
  single_site  scripts/run_single_site.py  (bands.npz)
  multi_site   scripts/run_multi_site.py   (network.npz; one site is the single-site case)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from bns.geospatial.grid import Grid

ARRAYS = {"single_site": "bands.npz", "multi_site": "network.npz"}


@dataclass
class Run:
    path: Path
    manifest: dict
    summary: dict

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
        """[{candidate_id, x, y, z, building_id, roof_height_m, height_category}, ...]"""
        if self.kind == "multi_site":
            return self.manifest["sites"]
        c = dict(self.manifest["site"]["candidate"])
        return [c]

    @property
    def sector_azimuths_rad(self) -> list[float]:
        sectors = self.manifest.get("sectors_per_site") or self.manifest.get("site", {}).get("sectors", [])
        return [float(s["orientation_rad"][0]) for s in sectors if s.get("pattern") != "iso"]

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
        """The radio summary of the whole configuration (all sites)."""
        r = self.summary["results"][scenario_id]
        return r["network"] if self.kind == "multi_site" else r

    def site_alone_sinr(self, scenario_id: str, site_index: int) -> np.ndarray | None:
        return self.layer(scenario_id, f"alone{site_index}_sinr_db")


def load_run(path: Path) -> Run:
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    return Run(path, manifest, summary)


def list_runs(root: Path) -> list[Run]:
    """Every complete run under outputs/runs/{development,research}, newest first."""
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
                runs.append(run)
    return sorted(runs, key=lambda r: r.manifest.get("created_utc", ""), reverse=True)


def cdf(values: np.ndarray, floor: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Sorted values and the share at or below each; -inf replaced by `floor` if given."""
    v = np.asarray(values, dtype=float).ravel()
    if floor is not None:
        v = np.where(np.isfinite(v), v, floor)
    v = np.sort(v[np.isfinite(v)])
    return v, np.arange(1, v.size + 1) / max(v.size, 1)
