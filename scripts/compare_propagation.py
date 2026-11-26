"""Trace the same site in two datasets of the same area and compare the path gain.

    uv run python scripts/compare_propagation.py --a tahrir_bab_al_sharqi/osm ^
        --b tahrir_bab_al_sharqi_v2/osm --band nr_3500 --building way/919688856 --profile standard

Uses the radio configuration only for the antenna (pattern, sectors, downtilt, mast height);
the comparison is of propagation (best-sector path gain) and needs no other radio parameter.
Writes outputs/datasets/propagation_<a>_vs_<b>_<band>.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

from bns.analysis.radio_system import RadioSystem
from bns.core.units import linear_to_db
from bns.geospatial import pipeline, sites
from bns.geospatial.grid import outdoor_mask
from bns.geospatial.study_area import load_study_areas
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache
from bns.simulation.setup import SimulationConfig, sector_antennas, site_jobs

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("--a", "--b", "--band", "--building", "--profile"):
        parser.add_argument(name, required=True)
    args = parser.parse_args()
    areas = load_study_areas(ROOT / "configs" / "study_area.yaml")
    system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
    config = SimulationConfig.load(ROOT / "configs" / "simulation.yaml")
    profile = config.profile(args.profile)
    scenario = {s["id"]: s for s in yaml.safe_load(
        (ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))["scenarios"]}[args.band]
    antennas = sector_antennas(system, mode="development", polarization=config.polarization)
    mast = system.require("antenna_height_above_roof_m", mode="development")

    data = {}
    for key in ("a", "b"):
        area_name, variant = getattr(args, key).split("/")
        area = areas[area_name]
        folder = ROOT / "data" / "scenes" / area_name / variant
        buildings = pipeline.load_buildings(folder, area)
        host = [b for b in buildings if b.building_id == args.building]
        [site] = sites.rooftop_candidates(host, mast_height_m=mast, min_height_m=0.0, min_area_m2=0.0,
                                          min_spacing_m=0.0, max_candidates=1)
        grid = area.receiver_grid(profile.cell_size_m, system.require("rx_height_m", mode="development"))
        jobs = site_jobs(folder, float(scenario["frequency_hz"]), (site.x, site.y, site.z), antennas,
                         grid, config, profile.rays_per_site)
        data[key] = {"buildings": buildings, "grid": grid, "jobs": jobs, "site": site,
                     "outdoor": outdoor_mask(grid, [b.polygon for b in buildings])}
    if (data["a"]["site"].x, data["a"]["site"].y, data["a"]["site"].z) != \
            (data["b"]["site"].x, data["b"]["site"].y, data["b"]["site"].z):
        print("The site differs between the datasets; the comparison would not be like for like.")
        return 1

    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    maps = prop.compute(data["a"]["jobs"] + data["b"]["jobs"], cache,
                        work_dir=ROOT / "data" / "cache" / "work")
    best = {k: np.max([maps[j.key()] for j in data[k]["jobs"]], axis=0) for k in ("a", "b")}
    both = data["a"]["outdoor"] & data["b"]["outdoor"]
    reached = both & (best["a"] > 0) & (best["b"] > 0)
    diff = linear_to_db(best["b"][reached] / best["a"][reached])
    only_a = int((both & (best["a"] > 0) & (best["b"] <= 0)).sum())
    only_b = int((both & (best["b"] > 0) & (best["a"] <= 0)).sum())
    newly_indoor = int((data["a"]["outdoor"] & ~data["b"]["outdoor"]).sum())

    lines = [f"# Propagation: {args.a} vs {args.b}", "",
             f"Band {args.band}, site on {args.building} ({data['a']['site'].z:g} m), "
             f"{len(antennas)} sector(s), profile {profile.name} ({profile.cell_size_m:g} m cells, "
             f"{profile.rays_per_site:.0e} rays). Best-sector path gain, outdoor cells in both.", "",
             "| Quantity | Value |", "|---|---|",
             f"| Outdoor cells compared | {int(both.sum())} |",
             f"| Cells that became indoor (new buildings) | {newly_indoor} |",
             f"| Cells reached only in A / only in B | {only_a} / {only_b} |",
             f"| Median change B - A | {np.median(diff):+.2f} dB |",
             f"| Cells changed by more than 1 dB | {100 * np.mean(np.abs(diff) > 1):.1f} % |",
             f"| Cells changed by more than 3 dB | {100 * np.mean(np.abs(diff) > 3):.1f} % |",
             f"| Cells changed by more than 10 dB | {100 * np.mean(np.abs(diff) > 10):.1f} % |",
             "", "For scale: two independent maps of the same scene at this profile differ by more "
             "than about 1.5-2 dB in 5 % of cells (docs/convergence.md), so changes below that are "
             "within the simulation's own noise."]
    out = ROOT / "outputs" / "datasets" / (
        f"propagation_{args.a.replace('/', '-')}_vs_{args.b.replace('/', '-')}_{args.band}.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
