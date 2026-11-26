"""How much do the results depend on the unknown building heights?

Builds one scene per height model, traces the same rooftop sites in each, and compares
line-of-sight availability, shadow zones, the role of diffraction, path loss, coverage
and the number of sites the greedy algorithm needs.

    uv run python scripts/run_height_sensitivity.py --area tahrir_bab_al_sharqi ^
        --models flat_9m low_rise_2_to_4 mixed_1_to_8 lognormal_10m --seed 1 ^
        --band nr_3500 --cell-m 10 --samples 100000000 ^
        --mast-height-m 3 --min-site-height-m 10 --site-spacing-m 150 --max-sites 8 ^
        --max-path-loss-db 110 120 130 --coverage-target 0.95

Nothing here is a default: mast height, thresholds and target are radio-system and
planning decisions that the supervisor has not made, so they must be given on the command
line and are recorded with the results. Sites stand only on buildings whose height is
observed or estimated from storeys, so their positions are the same in every variant.

Results: outputs/runs/height_sensitivity/<area>/<run name>/summary.json and summary.md.
The maps themselves (path_gain.npz per variant) stay local.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import yaml

from bns import runtime
from bns.geospatial import heights as ht
from bns.geospatial import osm_source, pipeline, sites
from bns.geospatial.grid import outdoor_mask
from bns.geospatial.study_area import load_study_areas

ROOT = runtime.PROJECT_ROOT
RAW_OSM = ROOT / "data" / "raw" / "osm"


def band_frequency(band_id: str) -> float:
    data = yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))
    for scenario in data["scenarios"]:
        if scenario["id"] == band_id:
            return float(scenario["frequency_hz"])
    raise SystemExit(f"Unknown band '{band_id}'.")


def worker(job: dict, out: Path) -> None:
    """Build one variant, trace every site with three sets of mechanisms, summarise."""
    info = runtime.init()
    from bns.analysis.sensitivity import summarise_variant
    from bns.propagation.sionna_engine import Propagation, open_scene, path_gain_map

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[job["area"]]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")
    model = ht.load_height_models(ROOT / "configs" / "height_models.yaml")[job["model"]]
    data, meta = osm_source.load_snapshot(RAW_OSM, area.snapshot)

    scene_dir = ROOT / "data" / "scenes" / area.name / f"{model.name}-seed{job['seed']}"
    report = pipeline.build_dataset(area, data, scene_dir, policy, meta["sha256"],
                                    height_model=model, seed=job["seed"])
    buildings = pipeline.load_buildings(scene_dir, area)
    grid = area.receiver_grid(job["cell_m"], height_m=1.5)
    outdoor = outdoor_mask(grid, [b.polygon for b in buildings])

    mechanisms = {
        "los": Propagation(max_depth=0, specular_reflection=False),
        "reflected": Propagation(max_depth=2),
        "full": Propagation(max_depth=2, diffraction=True),
    }
    scene = open_scene(scene_dir / "scene.xml", job["frequency_hz"])
    stacks = {name: [] for name in mechanisms}
    start = time.perf_counter()
    for site in job["sites"]:
        position = (site["x"], site["y"], site["z"])
        for name, settings in mechanisms.items():
            result = path_gain_map(scene, position, grid, settings, job["samples"], [job["seed"]])
            stacks[name].append(result.mean)
    seconds = time.perf_counter() - start
    stacks = {name: np.stack(maps) for name, maps in stacks.items()}

    summary = summarise_variant(stacks["los"], stacks["reflected"], stacks["full"], outdoor,
                                thresholds_db=job["max_path_loss_db"],
                                coverage_target=job["coverage_target"])
    heights = np.array([b.height.height_m for b in buildings])
    summary.update({
        "model": {"name": model.name, "kind": model.kind, "params": model.params,
                  "approved": model.approved, "seed": job["seed"]},
        "height_categories_percent": report["height_categories"]["by_count_percent"],
        "building_height_m": {"mean": float(heights.mean()), "median": float(np.median(heights)),
                              "max": float(heights.max())},
        "mesh_wedges": report["mesh"]["wedges"],
        "trace_seconds": round(seconds, 1),
        "runtime": info,
    })
    np.savez_compressed(out / "path_gain.npz", x=grid.x_centers, y=grid.y_centers,
                        outdoor=outdoor, **stacks)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def render(run: dict) -> str:
    a = run["arguments"]
    lines = [
        f"# Height sensitivity: {a['area']}, {a['band']}",
        "",
        "**Illustrative run on a development fixture with unapproved height models. "
        "It shows how strongly the results depend on building heights; none of these numbers "
        "is a finding about Baghdad.**",
        "",
        f"- Sites: {len(run['sites'])} rooftop positions on buildings with observed or "
        f"storey-based heights, antenna {a['mast_height_m']} m above the roof.",
        f"- Receivers: {a['cell_m']} m cells at 1.5 m; {a['samples']:.0e} rays per site; "
        f"2 reflections + diffraction; seed {a['seed']}.",
        f"- Coverage target for the greedy selection: {100 * a['coverage_target']:.0f} %.",
        "",
        "## Geometry and propagation",
        "",
        "| Height model | Mean building height | Line of sight to any site | Reached only by "
        "diffraction | Not reached by any site | Median path loss (best site) |",
        "|---|---|---|---|---|---|",
    ]
    for v in run["variants"]:
        lines.append(
            f"| {v['model']['name']} | {v['building_height_m']['mean']:.1f} m | "
            f"{100 * v['los_fraction_any_site']:.1f} % | {100 * v['diffraction_only_fraction']:.1f} % | "
            f"{100 * v['shadow_fraction_all_sites']:.1f} % | {v['best_path_loss_db']['median']:.1f} dB |")
    lines += ["", "## Coverage and sites needed", "",
              "Coverage = share of outdoor cells whose path loss to the best site is at most the "
              "threshold. The threshold stands for transmit power plus antenna gains minus the "
              "required received power, which is not decided yet, so several are shown.",
              ""]
    header = "| Height model |" + "".join(
        f" {t:g} dB: coverage, all sites | {t:g} dB: sites for target |" for t in a["max_path_loss_db"])
    lines += [header, "|---|" + "---|---|" * len(a["max_path_loss_db"])]
    for v in run["variants"]:
        row = f"| {v['model']['name']} |"
        for c in v["coverage"]:
            needed = str(len(c["greedy_sites"])) if c["target_reached"] else \
                f"not reached with {len(c['greedy_sites'])}"
            row += f" {100 * c['coverage_all_sites']:.1f} % | {needed} |"
        lines.append(row)
    lines += ["", "## Sites used", "", "| Site | Building | Roof height | Height category |",
              "|---|---|---|---|"]
    lines += [f"| {s['candidate_id']} | {s['building_id']} | {s['roof_height_m']:.1f} m | "
              f"{s['height_category']} |" for s in run["sites"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    if "--worker" in sys.argv:          # internal call made by run_isolated below
        internal = argparse.ArgumentParser()
        internal.add_argument("--worker")
        internal.add_argument("--out", type=Path)
        call = internal.parse_args()
        worker(json.loads(call.worker), call.out)
        return 0

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--band", required=True, help="scenario id in configs/scenarios.yaml")
    parser.add_argument("--cell-m", type=float, required=True)
    parser.add_argument("--samples", type=float, required=True)
    parser.add_argument("--mast-height-m", type=float, required=True)
    parser.add_argument("--min-site-height-m", type=float, required=True)
    parser.add_argument("--site-spacing-m", type=float, required=True)
    parser.add_argument("--max-sites", type=int, required=True)
    parser.add_argument("--max-path-loss-db", type=float, nargs="+", required=True)
    parser.add_argument("--coverage-target", type=float, required=True)
    parser.add_argument("--name", default=None, help="run name (default: band and seed)")
    args = parser.parse_args()

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    policy = ht.load_height_policy(ROOT / "configs" / "study_area.yaml")
    data, meta = osm_source.load_snapshot(RAW_OSM, area.snapshot)
    base, _, _ = pipeline.provenance_buildings(area, data, policy, meta["sha256"])
    inside = [b for b in base if area.receiver_box().contains(b.polygon.representative_point())]
    candidates = sites.rooftop_candidates(
        inside, mast_height_m=args.mast_height_m, min_height_m=args.min_site_height_m,
        min_area_m2=0.0, min_spacing_m=args.site_spacing_m, max_candidates=args.max_sites,
        categories=(ht.OBSERVED, ht.ESTIMATED))
    if not candidates:
        print("No building with a known height qualifies as a site.")
        return 1
    site_rows = [asdict(c) for c in candidates]

    run_name = args.name or f"{args.band}-seed{args.seed}"
    run_dir = ROOT / "outputs" / "runs" / "height_sensitivity" / area.name / run_name
    arguments = {k: v for k, v in vars(args).items() if k != "name"}
    variants = []
    for model_name in args.models:
        job = {"area": area.name, "model": model_name, "seed": args.seed, "sites": site_rows,
               "frequency_hz": band_frequency(args.band), "cell_m": args.cell_m,
               "samples": int(args.samples), "max_path_loss_db": args.max_path_loss_db,
               "coverage_target": args.coverage_target}
        final, staging = run_dir / model_name, run_dir / f"{model_name}.staging"
        argv = [sys.executable, str(Path(__file__).resolve()), "--worker", json.dumps(job),
                "--out", str(staging)]
        attempts = runtime.run_isolated(argv, staging, final)
        summary = json.loads((final / "summary.json").read_text(encoding="utf-8"))
        summary["attempts"] = attempts
        variants.append(summary)
        print(f"{model_name}: line of sight {100 * summary['los_fraction_any_site']:.1f} %, "
              f"unreached {100 * summary['shadow_fraction_all_sites']:.1f} %, "
              f"{summary['trace_seconds']} s, {len(attempts)} attempt(s)")

    run = {"arguments": arguments, "osm_snapshot_sha256": meta["sha256"], "sites": site_rows,
           "variants": variants, "versions": runtime.versions(),
           "note": "Development fixture and unapproved height models: illustrative only."}
    (run_dir / "summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (run_dir / "summary.md").write_text(render(run), encoding="utf-8")
    print(f"Summary: {run_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
