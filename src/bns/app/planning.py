"""Re-evaluate a saved multi-site run from the path-gain cache (no ray tracing).

The traced path gain of every sector is in the cache under the job keys the run
recorded. With them, the network can be re-evaluated for a subset of sites or a
different coverage target or interference activity, and the SINR-based greedy
selection rerun, in NumPy only. If a cache entry is missing, or the configuration
files changed since the run, this says so instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from bns.optimization.greedy import SinrGreedyResult, greedy_sinr_site_selection
from bns.simulation import experiment as ex
from bns.simulation.cache import PathGainCache
from bns.simulation.network import NetworkResult, network


class PlanningError(RuntimeError):
    pass


@dataclass
class Stacks:
    experiment: ex.Experiment
    scenario: dict
    stack: np.ndarray            # [sector, y, x] path gain
    sector_site: np.ndarray      # site index per sector
    loss_db: np.ndarray          # [sector, y, x] gas loss
    config_changed: list[str]    # radio parameters whose status or value differ from the run


def load_stacks(root, run, scenario_id: str) -> Stacks:
    if run.kind not in ("multi_site", "site_plan"):
        raise PlanningError("Re-evaluation needs a multi-site run or a site plan.")
    m = run.manifest
    exp = ex.load(root, m["area"]["name"], m["area"]["variant"], m["profile"]["name"], m["mode"],
                  backend="cpu")                    # nothing is traced here; cached maps carry their backend
    if exp.grid.__dict__ != {**m["grid"], "center_xy": tuple(m["grid"]["center_xy"]),
                             "size_xy": tuple(m["grid"]["size_xy"])}:
        raise PlanningError("The receiver grid of the current configuration differs from the run's.")
    now = exp.system.status_report(list(m["radio_parameters"]))
    changed = [k for k, v in m["radio_parameters"].items() if now.get(k) != v]
    cache = PathGainCache(root / "data" / "cache" / "pathgain")
    site_index = {s["candidate_id"]: i for i, s in enumerate(m["sites"])}
    jobs = [j for j in m["jobs"] if j["scenario"] == scenario_id]
    maps = []
    for j in jobs:
        entry = cache.get(j["key"])
        if entry is None:
            raise PlanningError(f"Path gain {j['key'][:12]} is no longer in the cache; rerun the experiment.")
        maps.append(entry[0])
    scenario = next(s for s in exp.scenarios if s["id"] == scenario_id)
    sector_site = np.array([site_index[j["site"]] for j in jobs])
    sites = m["sites"]
    loss = np.stack([ex.gas_loss_db(exp, scenario, (sites[i]["x"], sites[i]["y"], sites[i]["z"]))
                     for i in sector_site])
    return Stacks(exp, scenario, np.stack(maps), sector_site, loss, changed)


def evaluate(s: Stacks, selection: tuple[int, ...], *, interference_activity: float | None = None,
             coverage_threshold: float | None = None) -> NetworkResult:
    if not selection:
        raise PlanningError("Select at least one site.")
    inputs = ex.radio_inputs(s.experiment, s.scenario)
    if interference_activity is not None:
        inputs = replace(inputs, interference_activity=float(interference_activity))
    if coverage_threshold is not None:
        inputs = replace(inputs, coverage_threshold=float(coverage_threshold))
    keep = np.isin(s.sector_site, selection)
    remap = {site: k for k, site in enumerate(sorted(selection))}
    return network(s.stack[keep], np.array([remap[i] for i in s.sector_site[keep]]), s.experiment.outdoor,
                   inputs, s.loss_db[keep])


def greedy(s: Stacks, target: float, *, interference_activity: float | None = None,
           coverage_threshold: float | None = None, max_sites: int | None = None) -> SinrGreedyResult:
    n_sites = int(s.sector_site.max()) + 1
    return greedy_sinr_site_selection(
        lambda sel: evaluate(s, sel, interference_activity=interference_activity,
                             coverage_threshold=coverage_threshold).radio.summary["coverage_fraction"],
        n_sites, target, max_sites)
