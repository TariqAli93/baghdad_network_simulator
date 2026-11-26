"""Phase 8 site planning: SINR-based greedy selection of physical sites among rooftop candidates.

    uv run python scripts/plan_sites.py --area tahrir_bab_al_sharqi_v2 --mode development ^
        [--profile preview] [--backend cpu|gpu|auto] [--max-candidates 20] [--min-height 9] ^
        [--min-spacing 150] [--heights observed,estimated,placeholder] ^
        [--threshold DB] [--target SHARE] [--load ACTIVITY]

Candidates are rooftops in the receiver area (tallest first, at least --min-spacing apart),
each a physical site with the configured sectors. For every scenario, sites are added one at
a time, choosing the candidate that gives the highest coverage of the WHOLE network (every
selected sector interferes; strongest sector serves). The objective is the configured
coverage definition (SINR at or above the threshold on outdoor cells). The search stops when
the target is met, when no remaining candidate raises coverage (a local stall: the target may
still be reachable with several sites added together), or when candidates run out. Coverage
with ALL candidates transmitting is reported for reference. The result is what the greedy
heuristic found, not a minimum.

--threshold/--target/--load override the radio configuration for a sensitivity case in
development mode only (recorded in the manifest); research mode refuses overrides.
Writes outputs/runs/<mode>/site_plan-.../ (manifest, summary, history CSV, maps, figures).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from bns import runtime
from bns.geospatial import sites as site_rules
from bns.optimization.greedy import greedy_sinr_site_selection
from bns.reporting import export
from bns.simulation import experiment as ex
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache, scene_fingerprint
from bns.simulation.network import network

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--variant", default="osm")
    parser.add_argument("--profile", default="preview")
    parser.add_argument("--mode", choices=("development", "research"), required=True)
    parser.add_argument("--backend", choices=("cpu", "gpu", "auto"), default="cpu")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--min-height", type=float, default=9.0)
    parser.add_argument("--min-spacing", type=float, default=150.0)
    parser.add_argument("--heights", default="observed,estimated,placeholder",
                        help="height categories allowed for candidate roofs")
    parser.add_argument("--threshold", type=float, help="coverage threshold override [dB] (development only)")
    parser.add_argument("--target", type=float, help="coverage target override (development only)")
    parser.add_argument("--load", type=float, help="interference activity override (development only)")
    parser.add_argument("--cancel-file", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    overrides = {k: v for k, v in (("coverage_threshold", args.threshold), ("coverage_target", args.target),
                                   ("interference_activity", args.load)) if v is not None}
    try:
        if overrides and args.mode == "research":
            raise ex.ExperimentError("Research mode does not accept overrides of the radio configuration.")
        exp = ex.load(ROOT, args.area, args.variant, args.profile, args.mode, backend=args.backend)
        categories = tuple(c.strip() for c in args.heights.split(",") if c.strip())
        candidates = site_rules.rooftop_candidates(exp.receiver_buildings, mast_height_m=exp.mast_height_m,
                                                   min_height_m=args.min_height, min_area_m2=0.0,
                                                   min_spacing_m=args.min_spacing, max_candidates=args.max_candidates,
                                                   categories=categories)
    except Exception as exc:
        print(f"ERROR {exc}", flush=True)
        return 1
    if not candidates:
        print("ERROR no rooftop satisfies the candidate rule.", flush=True)
        return 1
    print(f"BACKEND {exp.backend}: {exp.backend_note}", flush=True)
    print(f"CANDIDATES {len(candidates)}", flush=True)
    target = overrides.get("coverage_target", exp.system.require("coverage_target", mode=args.mode))
    jobs = ex.jobs_for(exp, candidates)
    all_jobs = [j for js in jobs.values() for _, j in js]
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    work = ex.workload(all_jobs, cache, exp.profile.rays_per_site, exp.profile.cell_size_m)
    print(f"WORKLOAD {json.dumps(work)}", flush=True)
    cancel = (lambda: args.cancel_file.exists()) if args.cancel_file else None
    t0 = time.perf_counter()
    try:
        traced = prop.compute(all_jobs, cache, work_dir=ROOT / "data" / "cache" / "work", should_cancel=cancel,
                              on_progress=lambda d, t, i: print(f"PROGRESS {d}/{t} {i.get('seconds')} s", flush=True))
    except runtime.Cancelled:
        print("CANCELLED finished traces stay cached; run again to resume.", flush=True)
        return 2
    trace_seconds = time.perf_counter() - t0

    t1 = time.perf_counter()
    results, maps, history_rows = {}, {}, []
    area_km2 = exp.area.receiver_size_m[0] * exp.area.receiver_size_m[1] / 1e6
    for sc in exp.scenarios:
        sid = sc["id"]
        inputs = ex.radio_inputs(exp, sc)
        if "coverage_threshold" in overrides:
            inputs = replace(inputs, coverage_threshold=overrides["coverage_threshold"])
        if "interference_activity" in overrides:
            inputs = replace(inputs, interference_activity=overrides["interference_activity"])
        stack = np.stack([traced[j.key()] for _, j in jobs[sid]])
        sector_site = np.array([i for i, _ in jobs[sid]])
        loss = np.stack([ex.gas_loss_db(exp, sc, (candidates[i].x, candidates[i].y, candidates[i].z))
                         for i in sector_site])

        def evaluate(selection, stack=stack, sector_site=sector_site, loss=loss, inputs=inputs):
            keep = np.isin(sector_site, selection)
            remap = {s: k for k, s in enumerate(sorted(selection))}
            return network(stack[keep], np.array([remap[s] for s in sector_site[keep]]), exp.outdoor, inputs, loss[keep])

        s0 = time.perf_counter()
        g = greedy_sinr_site_selection(lambda sel: evaluate(sel).radio.summary["coverage_fraction"],
                                       len(candidates), target)
        select_seconds = time.perf_counter() - s0
        everything = evaluate(tuple(range(len(candidates))))
        final = evaluate(tuple(g.selected)) if g.selected else None
        for e in g.evaluations:
            chosen = g.selected[e["step"] - 1] if e["step"] <= len(g.selected) else None
            for c, v in e["coverage_with"].items():
                history_rows.append([sid, e["step"], candidates[c].candidate_id, round(v, 5), round(e["before"], 5),
                                     round(v - e["before"], 5), int(c == chosen)])
        order = sorted(g.selected)
        if final is not None:
            ss = final.serving_site
            maps[sid] = {"sinr_db": final.radio.sinr_db, "covered": final.radio.covered,
                         "rate_bps": final.radio.rate_bps,
                         # index into the selected sites, in selection order
                         "serving_site": np.where(ss >= 0, np.array([g.selected.index(i) for i in order])[np.maximum(ss, 0)], -1),
                         "uncovered": exp.outdoor & ~final.radio.covered}
        results[sid] = {
            "selected": [candidates[i].candidate_id for i in g.selected],
            "selected_building_ids": [candidates[i].building_id for i in g.selected],
            "coverage_after": g.coverage_after, "target": target, "target_reached": g.target_reached,
            "stopped_because": g.stopped_because,
            "stop_explanation": {
                "target reached": "the coverage target was met",
                "no candidate raises coverage": "no single remaining candidate raises coverage (local stall; not a "
                                                "proof that the target is unreachable)",
                "candidates exhausted": "every candidate was selected",
                "site limit reached": "the site limit was reached"}[g.stopped_because],
            "degrading_additions": [{**d, "candidate": candidates[d["candidate"]].candidate_id}
                                    for d in g.degrading_additions],
            "sites": len(g.selected), "site_density_per_km2": len(g.selected) / area_km2,
            "final": None if final is None else {k: v for k, v in final.summary.items()
                                                  if k != "served_share_per_sector"},
            "uncovered_outdoor_cells": None if final is None else int(maps[sid]["uncovered"].sum()),
            "all_candidates_reference": {k: everything.summary[k] for k in ("coverage_fraction", "sinr_db_median",
                                                                             "rate_p5_bps")},
            "selection_seconds": round(select_seconds, 2),
            "evaluations": sum(len(e["coverage_with"]) for e in g.evaluations),
        }
        print(f"{sid}: {len(g.selected)} sites -> {g.coverage_after[-1] if g.coverage_after else 0:.3f} "
              f"({g.stopped_because})", flush=True)
    selection_seconds = time.perf_counter() - t1

    run_id = (f"site_plan-{exp.area.name}-{exp.variant}-{exp.profile.name}-{len(candidates)}cand-{exp.backend}-"
              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    out = ROOT / "outputs" / "runs" / args.mode / run_id
    out.mkdir(parents=True)
    np.savez_compressed(out / "plan.npz", x=exp.grid.x_centers, y=exp.grid.y_centers, outdoor=exp.outdoor,
                        **{f"{sid}_{k}": v for sid, mm in maps.items() for k, v in mm.items()})
    with open(out / "selection_history.csv", "w", newline="", encoding="utf-8") as f:
        f.write(f"# {exp.label}\n")
        w = csv.writer(f)
        w.writerow(["scenario", "step", "candidate", "coverage_if_added", "coverage_before", "change", "selected"])
        w.writerows(history_rows)
    transformer = exp.area.transformer()
    export.sites_geojson(out / "candidates.geojson", transformer, candidates, exp.label)
    for sid, mm in maps.items():
        export.cells_csv(out / f"cells_{sid}.csv", exp.grid, transformer, exp.outdoor,
                         {"sinr_db": mm["sinr_db"], "covered": mm["covered"], "serving_site": mm["serving_site"],
                          "rate_mbps": mm["rate_bps"] / 1e6}, exp.label)

    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt
    style.apply()
    half = exp.grid.cell_size_m / 2
    extent = [exp.grid.x_centers[0] - half, exp.grid.x_centers[-1] + half,
              exp.grid.y_centers[0] - half, exp.grid.y_centers[-1] + half]
    fig, axes = plt.subplots(1, 5, figsize=(19, 4.4), sharey=True)
    for ax, sc in zip(axes, exp.scenarios, strict=True):
        r = results[sc["id"]]
        if sc["id"] in maps:
            ax.imshow(np.where(exp.outdoor, maps[sc["id"]]["covered"].astype(float), np.nan), origin="lower",
                      extent=extent, cmap=style.SEQUENTIAL, vmin=-0.5, vmax=1.5)
        ax.plot([c.x for c in candidates], [c.y for c in candidates], "o", color=style.INK_MUTED, markersize=3)
        chosen = [c for c in candidates if c.candidate_id in r["selected"]]
        ax.plot([c.x for c in chosen], [c.y for c in chosen], "^", color=style.INK, markersize=7)
        ax.set_title(f"{sc['label']}: {r['sites']} sites, {100 * (r['coverage_after'] or [0])[-1]:.1f} %\n({r['stopped_because']})",
                     fontsize=9)
        ax.grid(False)
    fig.suptitle(f"Final coverage (dark) with selected sites (triangles) among candidates (dots)  |  {exp.label}",
                 x=0.05, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(out / "plan_coverage.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for sc in exp.scenarios:
        cov = results[sc["id"]]["coverage_after"]
        ax.plot(range(1, len(cov) + 1), [100 * v for v in cov], marker="o", color=style.SCENARIO_COLORS[sc["id"]],
                label=sc["label"])
    ax.axhline(100 * target, color=style.INK_MUTED, linestyle="--", linewidth=1)
    ax.set(xlabel="sites selected", ylabel="outdoor cells covered [%]", title="Greedy selection history")
    ax.legend(fontsize=8)
    fig.suptitle(exp.label, x=0.05, ha="left", fontsize=9)
    fig.savefig(out / "plan_history.png")
    plt.close(fig)

    manifest = {
        "label": exp.label, "run_id": run_id, "kind": "site_plan", "mode": args.mode,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backend": {"name": exp.backend, "requested": args.backend, "note": exp.backend_note,
                    "variant": all_jobs[0].engine["variant"],
                    "status": (exp.config.backends or {}).get(exp.backend, {}).get("status")},
        "area": {"name": exp.area.name, "role": exp.area.role, "approved": exp.area.approved, "variant": exp.variant,
                 "osm_snapshot_sha256": exp.quality["osm_snapshot_sha256"],
                 "scene_fingerprint": scene_fingerprint(exp.scene_dir),
                 "height_categories_percent": exp.quality["height_categories"]["by_count_percent"],
                 "fit_for_research": exp.quality["fit_for_research"], "receiver_area_km2": area_km2},
        "candidate_rule": {"min_height_m": args.min_height, "min_spacing_m": args.min_spacing,
                           "max_candidates": args.max_candidates, "height_categories": list(categories),
                           "mast_height_m": exp.mast_height_m, "antenna_position": "interior point of the roof"},
        "sites": [c.__dict__ for c in candidates],
        "sectors_per_site": [a.__dict__ for a in exp.antennas],
        "profile": exp.profile.__dict__, "grid": exp.grid.__dict__, "mechanisms": exp.config.mechanisms.__dict__,
        "seeds": list(exp.config.seeds),
        "radio_parameters": exp.system.status_report(ex.USED + ["coverage_target", "frequency_reuse"]),
        "overrides_for_sensitivity": overrides,
        "objective": "share of outdoor cells with SINR at or above the threshold, whole network, all selected sectors "
                     "interfering",
        "scenarios": exp.scenarios, "workload_before_run": work,
        "jobs": [{"scenario": sid, "site": candidates[i].candidate_id, "key": j.key()}
                 for sid, js in jobs.items() for i, j in js],
        "timing": {"trace_wall_seconds": round(trace_seconds, 1), "selection_seconds": round(selection_seconds, 1),
                   "total_wall_seconds": round(time.perf_counter() - started, 1)},
        "versions": runtime.versions(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"label": exp.label, "results": results}, indent=2, default=str),
                                      encoding="utf-8")
    cats = sorted({c.height_category for c in candidates})
    lines = [f"# {exp.label}", "", f"## Site plan {run_id}", "",
             "Greedy heuristic on whole-network SINR coverage; **not a minimum site count**, and not a finding about "
             "Baghdad (provisional area, unapproved radio parameters"
             + (", candidate roofs with placeholder heights" if "placeholder" in cats else "") + ").", "",
             f"- {len(candidates)} candidates (roof ≥ {args.min_height:g} m, ≥ {args.min_spacing:g} m apart, heights: "
             f"{', '.join(cats)}), mast {exp.mast_height_m:g} m, {len(exp.antennas)} sectors each.",
             f"- Target {100 * target:.0f} % of {int(exp.outdoor.sum())} outdoor cells; threshold "
             f"{overrides.get('coverage_threshold', exp.system.require('coverage_threshold', mode=args.mode)):g} dB SINR; "
             f"load {overrides.get('interference_activity', exp.system.require('interference_activity', mode=args.mode)):g}"
             + (f" (sensitivity overrides: {overrides})" if overrides else "") + ".",
             f"- Profile {exp.profile.name}, backend {exp.backend}. Traces {trace_seconds:.0f} s "
             f"({work['to_trace']} new, {work['cached']} cached); selection {selection_seconds:.1f} s.", "",
             "| Scenario | Sites selected | Coverage after each addition | Stop | Final median SINR | Final 5th-pct rate | "
             "Uncovered cells | All candidates on | Sites per km² |", "|---|---|---|---|---|---|---|---|---|"]
    for sc in exp.scenarios:
        r = results[sc["id"]]
        f = r["final"] or {}
        lines.append(f"| {sc['label']} | {', '.join(r['selected']) or '—'} | "
                     f"{', '.join(f'{100 * v:.1f}' for v in r['coverage_after'])} % | {r['stopped_because']} | "
                     f"{f.get('sinr_db_median', float('nan')):.1f} dB | {f.get('rate_p5_bps', 0) / 1e6:.1f} Mbit/s | "
                     f"{r['uncovered_outdoor_cells']} | {100 * r['all_candidates_reference']['coverage_fraction']:.1f} % | "
                     f"{r['site_density_per_km2']:.1f} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OUTPUT {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
