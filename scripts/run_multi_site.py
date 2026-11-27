"""Multi-site experiment: several rooftop sites with sectors on one carrier, all five scenarios.

    uv run python scripts/run_multi_site.py --area tahrir_bab_al_sharqi_study ^
        [--profile preview] [--sites 4 --min-height 10 --min-spacing 100] [--buildings way/1 way/2]

Sites stand on the named buildings (in that order) or, by default, on the tallest
receiver-area buildings whose height is OBSERVED. One site gives the single-site case.
For every scenario the script reports:
  - the network of all sites (strongest sector serves, every other sector interferes),
  - every site alone, and the network grown site by site in the given order,
  - a greedy selection on network SINR coverage (interference included).
Path gains come from the cache (traced only if missing); nothing is traced twice.

Every output carries its scientific classification (bns.analysis.classification).
Writes outputs/runs/<mode>/<run id>/: manifest.json, summary.json, summary.md, figures,
network.npz (git-ignored), cells_<scenario>.csv and sites.geojson.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil

from bns import runtime
from bns.analysis import metrics
from bns.analysis.classification import AUTOMATIC_PLACEMENT, MANUAL_PLACEMENT
from bns.core.units import linear_to_db
from bns.optimization.greedy import greedy_sinr_site_selection
from bns.reporting import export
from bns.simulation import experiment as ex
from bns.simulation.setup import scene_azimuth_to_bearing_deg
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache, scene_fingerprint
from bns.simulation.network import network, sites_alone

ROOT = Path(__file__).resolve().parents[1]
MAP_KEYS = ("path_gain_db", "rx_power_dbm", "sinr_db", "rate_bps", "covered", "serving_site",
            "serving_sector", "interference_dbm")


def summarise(result) -> dict:
    keep = ("coverage_fraction", "unreached_fraction", "sinr_db_median", "sinr_db_p5", "rate_median_bps",
            "rate_p5_bps", "rx_power_dbm_median", "interference_limited_share",
            "interference_over_noise_db_median", "served_share_per_site")
    return {k: result.summary[k] for k in keep}


def figures(out: Path, exp, placed, maps: dict, curves: dict, alone: dict) -> list[str]:
    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    style.apply()
    grid, outdoor, scenarios = exp.grid, exp.outdoor, exp.scenarios
    half = grid.cell_size_m / 2
    extent = [grid.x_centers[0] - half, grid.x_centers[-1] + half, grid.y_centers[0] - half, grid.y_centers[-1] + half]

    def mark(ax):
        for s in placed:
            ax.plot(s.x, s.y, marker="^", color=style.INK, markersize=6, linestyle="none")
            ax.annotate(s.candidate_id[-1], (s.x, s.y), xytext=(4, 4), textcoords="offset points", fontsize=7)

    names = []
    for key, title, vmin, vmax, unit in (("sinr_db", "SINR, all sites and sectors on one carrier", -10, 40, "dB"),
                                         ("interference_dbm", "Interference power (all non-serving sectors)",
                                          -130, -50, "dBm")):
        fig, axes = plt.subplots(1, 5, figsize=(19, 4.4), sharey=True)
        for ax, sc in zip(axes, scenarios, strict=True):
            colours = style.SEQUENTIAL.copy()
            colours.set_under(style.SURFACE)
            im = ax.imshow(np.where(outdoor, maps[sc["id"]][key], np.nan), origin="lower", extent=extent,
                           cmap=colours, vmin=vmin, vmax=vmax)
            mark(ax)
            ax.set_title(f"{sc['label']}\n{sc['frequency_hz'] / 1e9:g} GHz, {sc['bandwidth_hz'] / 1e6:g} MHz", fontsize=9)
            ax.grid(False)
            ax.set_xlabel("x [m]")
        axes[0].set_ylabel("y [m]")
        fig.colorbar(im, ax=axes, label=unit, shrink=0.85, extend="min")
        fig.suptitle(f"{title}  |  {exp.label}", x=0.05, ha="left", fontsize=11, fontweight="bold")
        fig.savefig(out / f"network_{key}.png")
        plt.close(fig)
        names.append(f"network_{key}.png")

    site_colours = ListedColormap(["#2a6f97", "#c0504d", "#5b8c3a", "#8064a2", "#d08c2b", "#4b9b9b"][:len(placed)])
    fig, axes = plt.subplots(1, 5, figsize=(19, 4.4), sharey=True)
    for ax, sc in zip(axes, scenarios, strict=True):
        m = maps[sc["id"]]["serving_site"].astype(float)
        ax.imshow(np.where(outdoor & (m >= 0), m, np.nan), origin="lower", extent=extent, cmap=site_colours,
                  vmin=-0.5, vmax=len(placed) - 0.5, interpolation="nearest")
        mark(ax)
        ax.set_title(sc["label"], fontsize=9)
        ax.grid(False)
    fig.suptitle(f"Serving site (strongest sector)  |  {exp.label}", x=0.05, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(out / "serving_site.png")
    plt.close(fig)
    names.append("serving_site.png")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for sc in scenarios:
        c = style.SCENARIO_COLORS[sc["id"]]
        steps = curves[sc["id"]]
        a1.plot(range(1, len(steps) + 1), [100 * v for v in steps], color=c, marker="o", label=sc["label"])
        sinr = maps[sc["id"]]["sinr_db"][outdoor]
        multi = np.sort(np.where(np.isfinite(sinr), sinr, -60))
        single = alone[sc["id"]][0]
        single = np.sort(np.where(np.isfinite(single[outdoor]), single[outdoor], -60))
        p = np.arange(1, multi.size + 1) / multi.size
        a2.plot(multi, p, color=c, label=f"{sc['label']}, {len(placed)} sites")
        a2.plot(single, p, color=c, linestyle="--", linewidth=1)
    a1.set(title="Coverage as sites are added (given order)", xlabel="sites", ylabel="outdoor cells covered [%]",
           xticks=range(1, len(placed) + 1))
    a2.set(title="SINR: network (solid) vs site 1 alone (dashed)", xlabel="SINR [dB]",
           ylabel="share of outdoor cells at or below", xlim=(-20, 60))
    a2.legend(fontsize=7)
    fig.suptitle(exp.label, x=0.05, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(out / "network_cdf.png")
    plt.close(fig)
    names.append("network_cdf.png")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--variant", default="osm")
    parser.add_argument("--profile", default="preview")
    parser.add_argument("--mode", choices=("development", "research"), default="development",
                        help="kept for older commands; it no longer restricts anything (the result is "
                             "classified automatically)")
    parser.add_argument("--buildings", nargs="+", help="OSM ids of the host buildings, in order")
    parser.add_argument("--sites", type=int, default=4, help="number of candidate-rule sites (default 4)")
    parser.add_argument("--min-height", type=float, help="minimum roof height [m] (default: configs/site_rule.yaml)")
    parser.add_argument("--min-spacing", type=float, help="minimum distance between sites [m] (default: site rule)")
    parser.add_argument("--overrides", type=Path,
                        help="JSON file of parameters that differ from the research baseline (custom experiment)")
    parser.add_argument("--backend", choices=("cpu", "gpu", "auto"), default="cpu",
                        help="ray-tracing backend (default cpu; gpu needs an NVIDIA driver)")
    parser.add_argument("--cancel-file", type=Path, help="stop cleanly when this file appears")
    args = parser.parse_args()
    args.mode = "development"       # no approval checks on parameter values; classification is automatic
    started = time.perf_counter()

    try:
        overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides else {}
        overrides.update({k: v for k, v in (("min_roof_height_m", args.min_height),
                                            ("min_spacing_m", args.min_spacing)) if v is not None})
        exp = ex.load(ROOT, args.area, args.variant, args.profile, args.mode, backend=args.backend,
                      overrides=overrides)
        placed = (ex.place_sites(exp, args.buildings) if args.buildings else ex.observed_sites(exp, args.sites))
    except Exception as exc:                        # research refusals, missing data
        print(f"ERROR {exc}", flush=True)
        return 1
    if not placed:
        print("ERROR no site could be placed with these rules.", flush=True)
        return 1
    print(f"SITES {len(placed)}: " + ", ".join(f"{s.candidate_id} on {s.building_id} ({s.roof_height_m:g} m "
                                                f"{s.height_category})" for s in placed), flush=True)
    print(f"BACKEND {exp.backend}: {exp.backend_note}", flush=True)
    print(f"CLASS {exp.classification.label}", flush=True)
    for note in ex.limitations(exp):
        print(f"LIMITATION {note}", flush=True)
    target = exp.system.require("coverage_target", mode=args.mode)
    jobs = ex.jobs_for(exp, placed)
    all_jobs = [j for js in jobs.values() for _, j in js]
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    work = ex.workload(all_jobs, cache, exp.profile.rays_per_site, exp.profile.cell_size_m)
    print(f"WORKLOAD {json.dumps(work)}", flush=True)

    trace_start = time.perf_counter()
    cancel = (lambda: args.cancel_file.exists()) if args.cancel_file else None
    try:
        traced = prop.compute(all_jobs, cache, work_dir=ROOT / "data" / "cache" / "work", should_cancel=cancel,
                              on_progress=lambda d, t, i: print(f"PROGRESS {d}/{t} {i.get('seconds')} s", flush=True))
    except runtime.Cancelled:
        print("CANCELLED finished traces stay cached; run again to resume.", flush=True)
        return 2
    trace_seconds = time.perf_counter() - trace_start

    maps, alone_maps, curves, results = {}, {}, {}, {}
    for sc in exp.scenarios:
        sid = sc["id"]
        inputs = ex.radio_inputs(exp, sc)
        stack = np.stack([traced[j.key()] for _, j in jobs[sid]])
        sector_site = np.array([i for i, _ in jobs[sid]])
        loss = np.stack([ex.gas_loss_db(exp, sc, (placed[i].x, placed[i].y, placed[i].z)) for i in sector_site])
        net = network(stack, sector_site, exp.outdoor, inputs, loss)
        alone = sites_alone(stack, sector_site, exp.outdoor, inputs, loss)

        def coverage_of(selection, stack=stack, sector_site=sector_site, loss=loss, inputs=inputs):
            keep = np.isin(sector_site, selection)
            remap = {s: k for k, s in enumerate(sorted(selection))}
            sub = np.array([remap[s] for s in sector_site[keep]])
            return network(stack[keep], sub, exp.outdoor, inputs, loss[keep]).radio.summary["coverage_fraction"]

        grown = [coverage_of(tuple(range(n))) for n in range(1, len(placed) + 1)]
        greedy = greedy_sinr_site_selection(coverage_of, len(placed), target)
        mapped = ex.mapped_rate_bps(exp, sc, net.radio.sinr_db)
        if mapped is not None:
            net.summary.update({"rate_3gpp_p5_bps": metrics.percentile(mapped, 5, exp.outdoor),
                                "rate_3gpp_median_bps": metrics.percentile(mapped, 50, exp.outdoor),
                                "rate_3gpp_model": ex.rate_mapping(exp, sc).describe(),
                                "rate_3gpp_note": "3GPP truncated Shannon of the band's technology, decision B3; "
                                                  "beside, not instead of, the Shannon bound"
                                                  + (f". {ex.rate_mapping(exp, sc).caveat.strip()}"
                                                     if ex.rate_mapping(exp, sc).caveat else "")})
        maps[sid] = {"path_gain_db": linear_to_db(stack.max(axis=0)), "rx_power_dbm": net.radio.rx_power_dbm,
                     "sinr_db": net.radio.sinr_db, "rate_bps": net.radio.rate_bps, "covered": net.radio.covered,
                     "serving_site": net.serving_site, "serving_sector": net.serving_sector,
                     "interference_dbm": net.interference_dbm,
                     **({"rate_3gpp_bps": mapped} if mapped is not None else {})}
        alone_maps[sid] = [a.radio.sinr_db for a in alone]
        curves[sid] = grown
        results[sid] = {
            "network": {**net.summary, "noise_dbm": net.radio.noise_dbm},
            "sites_alone": [summarise(a) for a in alone],
            "grown_in_given_order": [{"sites": list(range(1, n + 1)), "coverage_fraction": v}
                                     for n, v in enumerate(grown, start=1)],
            "additions_that_lowered_coverage": [
                {"added_site": n + 1, "change": grown[n] - grown[n - 1]}
                for n in range(1, len(grown)) if grown[n] < grown[n - 1]],
            "greedy_sinr": {"selected_sites": [s + 1 for s in greedy.selected], "coverage_after": greedy.coverage_after,
                            "target": target, "target_reached": greedy.target_reached,
                            "stopped_because": greedy.stopped_because,
                            "degrading_additions": [{**d, "candidate": d["candidate"] + 1}
                                                    for d in greedy.degrading_additions],
                            "note": "greedy heuristic over these candidates only; not a proven minimum"},
        }

    run_id = (f"multi_site-{exp.area.name}-{exp.variant}-{exp.profile.name}-{len(placed)}sites-"
              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    out = ROOT / "outputs" / "runs" / args.mode / run_id
    out.mkdir(parents=True)
    np.savez_compressed(out / "network.npz", x=exp.grid.x_centers, y=exp.grid.y_centers, outdoor=exp.outdoor,
                        **{f"{sid}_{k}": v for sid, m in maps.items() for k, v in m.items()},
                        **{f"{sid}_alone{n}_sinr_db": a for sid, al in alone_maps.items() for n, a in enumerate(al)})
    transformer = exp.area.transformer()
    for sid, m in maps.items():
        export.cells_csv(out / f"cells_{sid}.csv", exp.grid, transformer, exp.outdoor,
                         {**{k: m[k] for k in MAP_KEYS if k != "rate_bps"}, "rate_mbps": m["rate_bps"] / 1e6},
                         exp.label)
    export.sites_geojson(out / "sites.geojson", transformer, placed, exp.label)
    names = figures(out, exp, placed, maps, curves, alone_maps)

    job_records = []
    for sid, js in jobs.items():
        for i, j in js:
            m = cache.get(j.key())[1]
            job_records.append({"scenario": sid, "site": placed[i].candidate_id, "key": j.key(),
                                "sector_orientation_rad": j.antenna.orientation_rad, "trace_seconds": m.get("seconds"),
                                "worker_peak_commit_gb": m.get("worker_peak_commit_gb")})
    memory = psutil.Process().memory_info()
    manifest = {
        "label": exp.label, "run_id": run_id, "kind": "multi_site", "mode": args.mode,
        "run_class": exp.run_class, "overrides": exp.overrides,
        "classification": replace(exp.classification, placement=MANUAL_PLACEMENT if args.buildings
                                  else AUTOMATIC_PLACEMENT).as_dict(),
        "backend": {"name": exp.backend, "requested": args.backend, "note": exp.backend_note,
                    "variant": all_jobs[0].engine["variant"],
                    "status": (exp.config.backends or {}).get(exp.backend, {}).get("status"),
                    "gpu": runtime.gpu_description() if exp.backend == "gpu" else None},
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "area": {"name": exp.area.name, "role": exp.area.role, "approved": exp.area.approved, "variant": exp.variant,
                 "osm_snapshot_sha256": exp.quality["osm_snapshot_sha256"],
                 "scene_fingerprint": scene_fingerprint(exp.scene_dir),
                 "height_categories_percent": exp.quality["height_categories"]["by_count_percent"],
                 "height_model": {k: (exp.quality.get("height_model") or {}).get(k) for k in ("name", "kind", "seed")}
                 | {"synthetic": ((exp.quality.get("height_model") or {}).get("synthetic") or {}).get("synthetic_percent")}
                 if exp.quality.get("height_model") else None,
                 "fit_for_research": exp.quality["fit_for_research"]},
        "site_rule": ({"buildings": args.buildings} if args.buildings else
                      {**exp.candidate_rule, "count": args.sites}),
        "sites": [s.__dict__ for s in placed],
        "sectors_per_site": [a.__dict__ for a in exp.antennas],
        "sector_bearings_deg": [scene_azimuth_to_bearing_deg(a.orientation_rad[0]) for a in exp.antennas],
        "azimuth_convention": "orientation_rad[0]: yaw counter-clockwise from east (scene x east, y north); "
                              "sector_bearings_deg: compass, clockwise from north",
        "antenna_rule": exp.site_rule,
        "sector_positions_m": {placed[i].candidate_id: ex.sector_positions(exp, placed[i]) for i in range(len(placed))},
        "profile": exp.profile.__dict__, "grid": exp.grid.__dict__,
        "mechanisms": exp.config.mechanisms.__dict__, "seeds": list(exp.config.seeds),
        "radio_parameters": exp.system.status_report(ex.USED + ["coverage_target", "frequency_reuse"]),
        "atmosphere": {"baseline": exp.baseline.__dict__},
        "scenarios": exp.scenarios, "workload_before_run": work, "jobs": job_records,
        "timing": {"trace_wall_seconds": round(trace_seconds, 1),
                   "total_wall_seconds": round(time.perf_counter() - started, 1)},
        "memory": {"script_peak_commit_gb": round(memory.peak_pagefile / 2**30, 3),
                   "max_worker_peak_commit_gb": max(j["worker_peak_commit_gb"] or 0 for j in job_records)},
        "versions": runtime.versions(), "figures": names,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"label": exp.label, "results": results}, indent=2, default=str),
                                      encoding="utf-8")

    lines = [f"# {exp.label}", "", f"## Multi-site experiment {run_id}", "",
             ex.caveat(exp), "",
             f"- Sites ({len(placed)}): " + "; ".join(
                 f"{s.candidate_id} on {s.building_id}, roof {s.roof_height_m:g} m ({s.height_category}), "
                 f"antenna {s.z:g} m at ({s.x:.0f}, {s.y:.0f})" for s in placed),
             f"- {len(exp.antennas)} sectors per site; every sector of every site on one carrier; interference "
             "activity " + f"{ex.radio_inputs(exp, exp.scenarios[0]).interference_activity:g}; co-located sectors interfere.",
             f"- Profile {exp.profile.name}: {exp.profile.cell_size_m:g} m cells, {exp.profile.rays_per_site:.0e} rays per sector; "
             f"{int(exp.outdoor.sum())} outdoor cells.", "",
             "| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | "
             "Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for sc in exp.scenarios:
        r = results[sc["id"]]
        n = r["network"]
        best = max(a["coverage_fraction"] for a in r["sites_alone"])
        g = r["greedy_sinr"]
        lowered = ", ".join(f"site {d['added_site']} ({100 * d['change']:+.1f} pt)"
                            for d in r["additions_that_lowered_coverage"]) or "none"
        lines.append(f"| {sc['label']} | {100 * n['coverage_fraction']:.1f} % | {100 * best:.1f} % | "
                     f"{n['sinr_db_median']:.1f} dB | {n['rate_p5_bps'] / 1e6:.1f} Mbit/s | "
                     f"{n['rate_median_bps'] / 1e6:.0f} Mbit/s | {100 * n['interference_limited_share']:.0f} % | "
                     f"{lowered} | sites {g['selected_sites']} -> {100 * g['coverage_after'][-1]:.1f} % "
                     f"({g['stopped_because']}) |")
    lines += ["", f"Trace time {trace_seconds:.0f} s for {work['to_trace']} new traces "
                  f"({work['cached']} of {work['jobs']} were cached); total {time.perf_counter() - started:.0f} s.",
              "", "Shannon rates are theoretical upper bounds for one user with the whole carrier. "
                  "The greedy result is a heuristic over these candidates only."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nOUTPUT {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
