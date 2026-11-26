"""Single-site experiment: one rooftop site, all five scenarios, identical receiver grid.

    uv run python scripts/run_single_site.py --area tahrir_bab_al_sharqi_v2 --variant osm ^
        --profile standard --mode development [--building way/919688856]

The site stands on the given building (default: the tallest building in the receiver area
whose height is observed). Propagation comes from the cached path-gain maps (traced if
missing); the radio system from configs/radio_system.yaml in the chosen mode; the weather is
the clear-sky baseline of configs/atmosphere.yaml.

Every output carries its scientific classification (bns.analysis.classification).
Research mode stops unless every parameter used is approved.

Writes outputs/runs/<mode>/<run id>/: manifest.json, summary.json, summary.md, figures
(PNG) and per-band arrays (bands.npz; git-ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
import yaml

from bns import runtime
from bns.analysis import classification
from bns.analysis.radio_system import RadioSystem
from bns.core.units import linear_to_db
from bns.geospatial import heights as ht
from bns.geospatial import pipeline, sites
from bns.geospatial.grid import outdoor_mask
from bns.geospatial.study_area import load_study_areas
from bns.propagation import atmosphere as atm
from bns.simulation import experiment as ex
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache, scene_fingerprint
from bns.simulation.radio import RadioInputs, multi_site
from bns.simulation.setup import SimulationConfig, sector_antennas, site_jobs

ROOT = Path(__file__).resolve().parents[1]
USED = ["tx_power_dbm", "tx_antenna_gain_dbi", "tx_antenna_pattern", "sectors_per_site",
        "mechanical_downtilt_deg", "antenna_height_above_roof_m", "rx_height_m",
        "rx_antenna_gain_dbi", "noise_figure_db", "noise_temperature_k", "coverage_threshold",
        "interference_activity"]


def figures(out: Path, grid, results: dict, outdoor, site, label: str, scenarios: list[dict]) -> list[str]:
    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt

    style.apply()
    half = grid.cell_size_m / 2
    extent = [grid.x_centers[0] - half, grid.x_centers[-1] + half,
              grid.y_centers[0] - half, grid.y_centers[-1] + half]
    names = []
    for key, title, cmap, vmin, vmax, unit in (
            ("path_gain_db", "Path gain, best sector (propagation only)", style.SEQUENTIAL, -160, -60, "dB"),
            ("rx_power_dbm", "Received power, best sector", style.SEQUENTIAL, -120, -20, "dBm"),
            ("sinr_db", "SINR, three sectors on one carrier", style.SEQUENTIAL, -10, 40, "dB")):
        fig, axes = plt.subplots(1, 5, figsize=(19, 4.4), sharey=True)
        for ax, sc in zip(axes, scenarios, strict=True):
            shown = np.where(outdoor, results[sc["id"]][key], np.nan)
            colours = cmap.copy()
            colours.set_under(style.SURFACE)
            im = ax.imshow(shown, origin="lower", extent=extent, cmap=colours, vmin=vmin, vmax=vmax)
            ax.plot(site[0], site[1], marker="^", color=style.INK, markersize=6, linestyle="none")
            ax.set_title(f"{sc['label']}\n{sc['frequency_hz'] / 1e9:g} GHz, {sc['bandwidth_hz'] / 1e6:g} MHz",
                         fontsize=9)
            ax.grid(False)
            ax.set_xlabel("x [m]")
        axes[0].set_ylabel("y [m]")
        fig.colorbar(im, ax=axes, label=unit, shrink=0.85, extend="min")
        fig.suptitle(f"{title}  |  {label}", x=0.05, ha="left", fontsize=11, fontweight="bold")
        name = f"{key}.png"
        fig.savefig(out / name)
        plt.close(fig)
        names.append(name)

    fig, axes = plt.subplots(1, 5, figsize=(19, 4.0), sharey=True)
    for ax, sc in zip(axes, scenarios, strict=True):
        ax.imshow(np.where(outdoor, results[sc["id"]]["covered"].astype(float), np.nan), origin="lower",
                  extent=extent, cmap=style.SEQUENTIAL, vmin=-0.5, vmax=1.5)
        ax.plot(site[0], site[1], marker="^", color=style.INK, markersize=6, linestyle="none")
        ax.set_title(f"{sc['label']}: {100 * results[sc['id']]['summary']['coverage_fraction']:.1f} % covered",
                     fontsize=9)
        ax.grid(False)
    fig.suptitle(f"Coverage (dark = SINR at or above threshold; grey = buildings)  |  {label}",
                 x=0.05, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(out / "coverage.png")
    plt.close(fig)
    names.append("coverage.png")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for sc in scenarios:
        colour = style.SCENARIO_COLORS[sc["id"]]
        r = results[sc["id"]]
        sinr = np.sort(np.where(np.isfinite(r["sinr_db"][outdoor]), r["sinr_db"][outdoor], -60))
        rate = np.sort(r["rate_bps"][outdoor] / 1e6)
        p = np.arange(1, sinr.size + 1) / sinr.size
        a1.plot(sinr, p, color=colour, label=sc["label"])
        a2.plot(rate, p, color=colour, label=sc["label"])
    a1.set(title="SINR of outdoor cells", xlabel="SINR [dB]", ylabel="share of outdoor cells at or below",
           xlim=(-20, 60))
    a2.set(title="Shannon rate (upper bound)", xlabel="rate [Mbit/s]", xscale="log", xlim=(1, 1e4))
    a2.legend(fontsize=8)
    fig.suptitle(label, x=0.05, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(out / "cdf.png")
    plt.close(fig)
    names.append("cdf.png")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--variant", default="osm")
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--mode", choices=("development", "research"), required=True)
    parser.add_argument("--building", help="OSM id of the host building")
    parser.add_argument("--replot", type=Path, help="redraw the figures of an existing run folder")
    args = parser.parse_args()
    started = time.perf_counter()

    if args.replot:
        from bns.geospatial.grid import Grid

        manifest = json.loads((args.replot / "manifest.json").read_text(encoding="utf-8"))
        arrays = np.load(args.replot / "bands.npz")
        summaries = json.loads((args.replot / "summary.json").read_text(encoding="utf-8"))["results"]
        g = manifest["grid"]
        grid = Grid(tuple(g["center_xy"]), tuple(g["size_xy"]), g["cell_size_m"], g["height_m"])
        results = {sc["id"]: {k: arrays[f"{sc['id']}_{k}"] for k in
                              ("path_gain_db", "rx_power_dbm", "sinr_db", "rate_bps", "covered")}
                   | {"summary": summaries[sc["id"]]} for sc in manifest["scenarios"]}
        names = figures(args.replot, grid, results, arrays["outdoor"], manifest["site"]["position_m"],
                        classification.from_manifest(manifest).label, manifest["scenarios"])
        print(f"Redrew {names} in {args.replot}")
        return 0

    area = load_study_areas(ROOT / "configs" / "study_area.yaml")[args.area]
    if args.mode == "research" and not area.is_research_dataset:
        print(f"Research mode needs an approved study district; {area.name} is a {area.role}.")
        return 1
    try:                    # the same research guards as every other experiment (bns.simulation.experiment)
        ex.require_research_ready(ROOT, args.mode)
        ex.require_research_profile(SimulationConfig.load(ROOT / "configs" / "simulation.yaml").profile(args.profile),
                                    args.mode)
    except ex.ExperimentError as exc:
        print(exc)
        return 1
    system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
    config = SimulationConfig.load(ROOT / "configs" / "simulation.yaml")
    profile = config.profile(args.profile)
    scenarios = sorted(yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))
                       ["scenarios"], key=lambda s: float(s["frequency_hz"]))
    for sc in scenarios:
        sc["frequency_hz"], sc["bandwidth_hz"] = float(sc["frequency_hz"]), float(sc["bandwidth_hz"])
    baseline, _ = atm.load_conditions(ROOT / "configs" / "atmosphere.yaml")

    scene_dir = ROOT / "data" / "scenes" / area.name / args.variant
    if not (scene_dir / "scene.xml").exists():
        print(f"No dataset {scene_dir}; run scripts/build_dataset.py first.")
        return 1
    quality = json.loads((scene_dir / "quality_report.json").read_text(encoding="utf-8"))
    classes = classification.classify(ROOT, {}, quality)
    label = classes.label
    try:
        ex.require_research_dataset(quality, args.mode)
    except ex.ExperimentError as exc:
        print(exc)
        return 1
    if args.mode == "research":
        # this Phase 4 script puts every sector at one interior roof point; the approved site rule
        # (roof edge, configs/site_rule.yaml) is applied by run_multi_site.py (--sites 1 / --buildings)
        print("Research single-site runs use scripts/run_multi_site.py, which applies the approved site rule "
              "(roof-edge antennas); this script places the sectors at an interior roof point.")
        return 1
    buildings = pipeline.load_buildings(scene_dir, area)
    inside = [b for b in buildings if area.receiver_box().contains(b.polygon.representative_point())]
    mast = system.require("antenna_height_above_roof_m", mode=args.mode)
    rx_height = system.require("rx_height_m", mode=args.mode)
    hosts = [b for b in inside if (args.building and b.building_id == args.building)
             or (not args.building and b.height.category == ht.OBSERVED)]
    if not hosts:
        print("No host building found.")
        return 1
    [site] = sites.rooftop_candidates(hosts, mast_height_m=mast, min_height_m=0.0, min_area_m2=0.0,
                                      min_spacing_m=0.0, max_candidates=1)
    position = (site.x, site.y, site.z)
    grid = area.receiver_grid(profile.cell_size_m, rx_height)
    outdoor = outdoor_mask(grid, [b.polygon for b in buildings])
    antennas = sector_antennas(system, mode=args.mode, polarization=config.polarization)

    jobs = {sc["id"]: site_jobs(scene_dir, sc["frequency_hz"], position, antennas, grid, config,
                                profile.rays_per_site) for sc in scenarios}
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    trace_start = time.perf_counter()
    maps = prop.compute([j for js in jobs.values() for j in js], cache,
                        work_dir=ROOT / "data" / "cache" / "work",
                        on_progress=lambda d, t, i: print(f"  traced {d}/{t} in {i.get('seconds')} s",
                                                          flush=True))
    trace_seconds = time.perf_counter() - trace_start

    results, job_records = {}, []
    for sc in scenarios:
        sid = sc["id"]
        stack = np.stack([maps[j.key()] for j in jobs[sid]])
        inputs = RadioInputs(
            tx_power_dbm=system.tx_power_for_path_gain_dbm(sid, mode=args.mode),
            rx_gain_dbi=system.require("rx_antenna_gain_dbi", sid, mode=args.mode),
            noise_figure_db=system.require("noise_figure_db", sid, mode=args.mode),
            noise_temperature_k=system.require("noise_temperature_k", sid, mode=args.mode),
            bandwidth_hz=sc["bandwidth_hz"],
            coverage_definition=system.definition("coverage_threshold"),
            coverage_threshold=system.require("coverage_threshold", sid, mode=args.mode),
            interference_activity=system.require("interference_activity", sid, mode=args.mode))
        gamma = baseline.specific_attenuation_db_per_km(sc["frequency_hz"], config.polarization)
        loss = atm.attenuation_map_db(position, grid, gamma)
        radio = multi_site(stack, outdoor, inputs, np.broadcast_to(loss, stack.shape))
        best_gain = stack.max(axis=0)
        reached = outdoor & (best_gain > 0)
        results[sid] = {
            "path_gain_db": linear_to_db(best_gain), "rx_power_dbm": radio.rx_power_dbm,
            "sinr_db": radio.sinr_db, "rate_bps": radio.rate_bps, "covered": radio.covered,
            "summary": {
                **radio.summary,
                "propagation_only": {
                    "outdoor_cells_reached_fraction": float(reached.sum() / outdoor.sum()),
                    "path_gain_db_median": float(np.median(linear_to_db(best_gain[reached]))),
                    "path_gain_db_p5": float(np.percentile(linear_to_db(best_gain[reached]), 5))},
                "peak_eirp_dbm": system.peak_eirp_dbm(sid, mode=args.mode),
                "tx_power_into_trace_dbm": inputs.tx_power_dbm,
                "gas_attenuation_db_per_km": gamma},
        }
        for j in jobs[sid]:
            m = cache.get(j.key())[1]
            job_records.append({"scenario": sid, "key": j.key(), "sector_orientation_rad": j.antenna.orientation_rad,
                                "trace_seconds": m.get("seconds"),
                                "worker_peak_commit_gb": m.get("worker_peak_commit_gb"),
                                "worker_peak_working_set_gb": m.get("worker_peak_working_set_gb")})

    run_id = (f"single_site-{area.name}-{args.variant}-{args.profile}-"
              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    out = ROOT / "outputs" / "runs" / args.mode / run_id
    out.mkdir(parents=True)
    np.savez_compressed(out / "bands.npz", x=grid.x_centers, y=grid.y_centers, outdoor=outdoor,
                        **{f"{sid}_{k}": v for sid, r in results.items()
                           for k, v in r.items() if k != "summary"})
    names = figures(out, grid, results, outdoor, position, label, scenarios)
    memory = psutil.Process().memory_info()
    manifest = {
        "label": label, "run_id": run_id, "mode": args.mode, "classification": classes.as_dict(),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "area": {"name": area.name, "role": area.role, "approved": area.approved,
                 "snapshot": area.snapshot, "variant": args.variant,
                 "osm_snapshot_sha256": quality["osm_snapshot_sha256"],
                 "scene_fingerprint": scene_fingerprint(scene_dir),
                 "height_categories_percent": quality["height_categories"]["by_count_percent"],
                 "fit_for_research": quality["fit_for_research"],
                 "not_fit_reasons": quality["not_fit_reasons"]},
        "site": {"candidate": site.__dict__, "position_m": position,
                 "sectors": [a.__dict__ for a in antennas]},
        "profile": profile.__dict__, "grid": grid.__dict__,
        "mechanisms": config.mechanisms.__dict__, "seeds": list(config.seeds),
        "radio_parameters": system.status_report(USED),
        "atmosphere": {"baseline": baseline.__dict__},
        "scenarios": scenarios,
        "jobs": job_records,
        "timing": {"trace_wall_seconds": round(trace_seconds, 1),
                   "total_wall_seconds": round(time.perf_counter() - started, 1),
                   "trace_seconds_sum_of_jobs": round(sum(j["trace_seconds"] or 0 for j in job_records), 1)},
        "memory": {"script_peak_commit_gb": round(memory.peak_pagefile / 2**30, 3),
                   "script_peak_working_set_gb": round(memory.peak_wset / 2**30, 3),
                   "max_worker_peak_commit_gb": max(j["worker_peak_commit_gb"] or 0 for j in job_records)},
        "versions": runtime.versions(),
        "figures": names,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    summary = {sid: r["summary"] for sid, r in results.items()}
    (out / "summary.json").write_text(json.dumps({"label": label, "results": summary}, indent=2),
                                      encoding="utf-8")

    lines = [f"# {label}", "", f"## Single-site experiment {run_id}", "",
             "Pipeline test and teaching aid. **Not a finding about Baghdad**: the area is a provisional "
             f"development area ({quality['height_categories']['by_count_percent']['placeholder']:.1f} % of "
             "buildings have placeholder heights) and the radio parameters are unapproved proposals.", "",
             f"- Site: {site.building_id}, roof {site.roof_height_m:g} m ({site.height_category}), antenna "
             f"{site.z:g} m above ground at ({site.x:.0f}, {site.y:.0f}) m; {len(antennas)} sector(s), "
             f"pattern {antennas[0].pattern}.",
             f"- Grid: {grid.shape[1]} x {grid.shape[0]} cells of {grid.cell_size_m:g} m at {grid.height_m:g} m; "
             f"{int(outdoor.sum())} outdoor cells. Profile {profile.name}: {profile.rays_per_site:.0e} rays per sector.",
             f"- Clear sky (gas attenuation only). Coverage: {inputs.coverage_definition} at or above "
             f"{inputs.coverage_threshold:g}.", "",
             "| Scenario | Peak EIRP | Noise | Reached (propagation only) | Median received power | "
             "Coverage | Median SINR | 5th-percentile Shannon rate | Median Shannon rate |",
             "|---|---|---|---|---|---|---|---|---|"]
    for sc in scenarios:
        s = summary[sc["id"]]
        lines.append(
            f"| {sc['label']} ({sc['frequency_hz'] / 1e9:g} GHz, {sc['bandwidth_hz'] / 1e6:g} MHz) | "
            f"{s['peak_eirp_dbm']:.0f} dBm | {s['noise_dbm']:.1f} dBm | "
            f"{100 * s['propagation_only']['outdoor_cells_reached_fraction']:.1f} % | "
            f"{s['rx_power_dbm_median']:.1f} dBm | {100 * s['coverage_fraction']:.1f} % | "
            f"{s['sinr_db_median']:.1f} dB | {s['rate_p5_bps'] / 1e6:.1f} Mbit/s | "
            f"{s['rate_median_bps'] / 1e6:.0f} Mbit/s |")
    lines += ["", f"Trace time {trace_seconds:.0f} s (cached maps are not re-traced); total "
                  f"{time.perf_counter() - started:.0f} s; largest worker peak commit "
                  f"{manifest['memory']['max_worker_peak_commit_gb']} GB.",
              "", "Shannon rates are theoretical upper bounds for one user with the whole carrier, "
                  "not expected user throughput."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nOutputs: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
