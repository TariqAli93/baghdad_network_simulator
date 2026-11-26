"""Phase 7 model-to-model comparison: ray-traced path loss vs 3GPP TR 38.901 UMa and UMi.

    uv run python scripts/validate_tr38901.py --area tahrir_bab_al_sharqi_v2 [--profile standard]

Controlled configuration (not the rooftop sites, which are outside the models' assumptions):
one isotropic antenna in open street space near the area centre at exactly the model's
base-station height (UMa 25 m, UMi 10 m), users at the receiver height (1.5 m), all five
bands, the project's propagation mechanisms. A second trace with line of sight only
classifies each outdoor cell as LOS (direct path exists) or NLOS. Per band and class:
mean error, standard deviation and RMSE of traced minus 3GPP path loss, compared with the
model's shadow-fading sigma; and the traced LOS share vs the 3GPP LOS probability.

What it is: model-to-model comparison (category 2). It is not a validation against
measurements: 3GPP formulas are statistical fits to measurements in generic city layouts,
and the district here has placeholder building heights. Writes outputs/validation/tr38901-*/.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from shapely.geometry import Point
from shapely.strtree import STRtree

from bns import runtime
from bns.core.units import linear_to_db
from bns.simulation import experiment as ex
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache, scene_fingerprint
from bns.simulation.jobs import Antenna, Mechanisms
from bns.simulation.setup import site_jobs
from bns.validation import tr38901 as m

ROOT = Path(__file__).resolve().parents[1]
LOS_ONLY = Mechanisms(max_depth=0, los=True, specular_reflection=False, diffraction=False, refraction=False,
                      diffuse_reflection=False, edge_diffraction=False)


def open_spot(exp, clearance_m: float):
    """Outdoor point nearest the centre at least `clearance_m` from every building."""
    polys = [b.polygon for b in exp.buildings]
    tree = STRtree(polys)
    xs, ys = np.meshgrid(np.arange(-200, 201, 5.0), np.arange(-200, 201, 5.0))
    order = np.argsort(np.hypot(xs, ys), axis=None)
    for k in order:
        p = Point(xs.flat[k], ys.flat[k])
        near = tree.query(p.buffer(clearance_m))
        if all(polys[i].distance(p) >= clearance_m for i in near):
            return float(p.x), float(p.y)
    raise RuntimeError("No open spot found.")


def stats(err) -> dict:
    err = np.asarray(err, dtype=float)
    if err.size == 0:
        return {"n": 0}
    return {"n": int(err.size), "mean_db": float(err.mean()), "std_db": float(err.std()),
            "rmse_db": float(np.sqrt((err**2).mean())), "median_db": float(np.median(err))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--area", required=True)
    parser.add_argument("--variant", default="osm")
    parser.add_argument("--profile", default="standard")
    parser.add_argument("--clearance", type=float, default=8.0, help="distance from any building [m]")
    args = parser.parse_args()
    started = time.perf_counter()
    exp = ex.load(ROOT, args.area, args.variant, args.profile, "development", backend="cpu")
    x0, y0 = open_spot(exp, args.clearance)
    h_ut = exp.grid.height_m
    iso = [Antenna("iso", exp.config.polarization, (0.0, 0.0, 0.0))]
    cases = {}
    for scen in ("UMa", "UMi"):
        pos = (x0, y0, m.BS_HEIGHT_M[scen])
        cases[scen] = {"pos": pos,
                       "bands": {sc["id"]: site_jobs(exp.scene_dir, sc["frequency_hz"], pos, iso, exp.grid, exp.config,
                                                     exp.profile.rays_per_site)[0] for sc in exp.scenarios},
                       "los": site_jobs(exp.scene_dir, exp.scenarios[1]["frequency_hz"], pos, iso, exp.grid,
                                        type(exp.config)(exp.config.profiles, LOS_ONLY, exp.config.seeds,
                                                         exp.config.polarization, exp.config.backends),
                                        exp.profile.rays_per_site)[0]}
    jobs = [j for c in cases.values() for j in [*c["bands"].values(), c["los"]]]
    cache = PathGainCache(ROOT / "data" / "cache" / "pathgain")
    print(f"WORKLOAD {json.dumps(ex.workload(jobs, cache, exp.profile.rays_per_site, exp.profile.cell_size_m))}", flush=True)
    # one job per worker: a first-compile crash then repeats only the job that crashed
    maps = prop.compute(jobs, cache, work_dir=ROOT / "data" / "cache" / "work", batch_size=1,
                        on_progress=lambda d, t, i: print(f"PROGRESS {d}/{t} {i.get('seconds')} s", flush=True))

    xs, ys = np.meshgrid(exp.grid.x_centers, exp.grid.y_centers)
    d2d = np.hypot(xs - x0, ys - y0)
    outdoor = exp.outdoor
    out = ROOT / "outputs" / "validation" / (f"tr38901-{exp.area.name}-{exp.variant}-{exp.profile.name}-"
                                              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    out.mkdir(parents=True)
    summary, rows = {}, []
    for scen, c in cases.items():
        h_bs = c["pos"][2]
        valid, reasons = m.applicable(scen, d2d, 3.5e9, h_bs, h_ut)
        los = maps[c["los"].key()] > 0
        base = outdoor & valid
        summary[scen] = {"bs_position_m": c["pos"], "applicability_reasons": reasons, "bands": {},
                         "los_share": float(los[base].mean())}
        bins = np.arange(0, 701, 50)
        idx = np.digitize(d2d, bins)
        summary[scen]["los_probability"] = [
            {"d_from_m": float(bins[i - 1]), "d_to_m": float(bins[i]), "cells": int((base & (idx == i)).sum()),
             "traced_los_share": float(los[base & (idx == i)].mean()) if (base & (idx == i)).any() else None,
             "tr38901": float(m.los_probability(scen, (bins[i - 1] + bins[i]) / 2))}
            for i in range(1, len(bins))]
        for sc in exp.scenarios:
            gain = maps[c["bands"][sc["id"]].key()]
            reached = base & (gain > 0)
            pl = -linear_to_db(np.where(gain > 0, gain, 1.0))
            ref_los = m.pathloss_los(scen, d2d, sc["frequency_hz"], h_bs, h_ut)
            ref_nlos = m.pathloss_nlos(scen, d2d, sc["frequency_hz"], h_bs, h_ut)
            ref = np.where(los, ref_los, ref_nlos)
            band = {"unreached_cells": int((base & ~(gain > 0)).sum()), "cells": int(base.sum())}
            d3 = np.sqrt(d2d**2 + (h_bs - h_ut) ** 2)
            for cls, sel in (("LOS", reached & los), ("NLOS", reached & ~los), ("all", reached)):
                band[cls] = {**stats((pl - ref)[sel]), "sigma_sf_db": m.SIGMA_DB.get((scen, cls))}
                if sel.sum() > 10:                      # PL = A + 10 n log10(d3D), least squares
                    slope = np.polyfit(np.log10(d3[sel]), pl[sel], 1)[0]
                    band[cls]["pathloss_exponent"] = float(slope / 10.0)
            summary[scen]["bands"][sc["id"]] = band
            for iy, ix in zip(*np.nonzero(reached), strict=True):
                rows.append([scen, sc["id"], round(float(d2d[iy, ix]), 1), "LOS" if los[iy, ix] else "NLOS",
                             round(float(pl[iy, ix]), 2), round(float(ref[iy, ix]), 2)])
    with open(out / "cells.csv", "w", newline="", encoding="utf-8") as f:
        f.write(f"# {exp.label}\n")
        w = csv.writer(f)
        w.writerow(["scenario", "band", "d2d_m", "class", "traced_pl_db", "tr38901_pl_db"])
        w.writerows(rows)

    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt
    style.apply()
    for scen, c in cases.items():
        fig, axes = plt.subplots(1, len(exp.scenarios), figsize=(20, 4.4), sharey=True)
        dline = np.linspace(10, 750, 300)
        for ax, sc in zip(axes, exp.scenarios, strict=True):
            sel = [r for r in rows if r[0] == scen and r[1] == sc["id"]]
            for cls, colour in (("NLOS", "#b9b8b0"), ("LOS", style.SCENARIO_COLORS[sc["id"]])):
                pts = [r for r in sel if r[3] == cls]
                ax.scatter([r[2] for r in pts], [r[4] for r in pts], s=3, color=colour, label=f"traced {cls}", alpha=0.6)
            ax.plot(dline, m.pathloss_los(scen, dline, sc["frequency_hz"], c["pos"][2], h_ut), color=style.INK,
                    label="TR 38.901 LOS")
            ax.plot(dline, m.pathloss_nlos(scen, dline, sc["frequency_hz"], c["pos"][2], h_ut), color=style.INK,
                    linestyle="--", label="TR 38.901 NLOS")
            b = summary[scen]["bands"][sc["id"]]
            name = sc["label"] if "GHz" in sc["label"] else f"{sc['label']} {sc['frequency_hz'] / 1e9:g} GHz"
            ax.set_title(f"{name}\nRMSE LOS {b['LOS'].get('rmse_db', float('nan')):.1f}"
                         f" / NLOS {b['NLOS'].get('rmse_db', float('nan')):.1f} dB", fontsize=9)
            ax.set_xscale("log")
            ax.set_xlabel("2-D distance [m]")
        axes[0].set_ylabel("path loss [dB]")
        axes[0].invert_yaxis()
        axes[-1].legend(fontsize=7, markerscale=3)
        fig.suptitle(f"{scen}: base station {c['pos'][2]:g} m, isotropic  |  {exp.label}", x=0.05, y=1.06, ha="left",
                     fontsize=11, fontweight="bold")
        fig.savefig(out / f"pathloss_{scen}.png")
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for scen, colour in (("UMa", "#2a78d6"), ("UMi", "#eb6834")):
        lp = summary[scen]["los_probability"]
        mid = [(r["d_from_m"] + r["d_to_m"]) / 2 for r in lp if r["traced_los_share"] is not None]
        ax.plot(mid, [r["traced_los_share"] for r in lp if r["traced_los_share"] is not None], marker="o",
                color=colour, label=f"traced {scen}")
        ax.plot(mid, [m.los_probability(scen, d) for d in mid], color=colour, linestyle="--", label=f"TR 38.901 {scen}")
    ax.set(xlabel="2-D distance [m]", ylabel="share of outdoor cells in LOS", title="Line-of-sight probability")
    ax.legend(fontsize=8)
    fig.savefig(out / "los_probability.png")
    plt.close(fig)

    manifest = {"label": exp.label, "kind": "tr38901_validation", "category": "model-to-model comparison",
                "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "area": {"name": exp.area.name, "variant": exp.variant, "scene_fingerprint": scene_fingerprint(exp.scene_dir),
                         "height_categories_percent": exp.quality["height_categories"]["by_count_percent"]},
                "profile": exp.profile.__dict__, "grid": exp.grid.__dict__, "mechanisms": exp.config.mechanisms.__dict__,
                "backend": "cpu", "jobs": {scen: {"bands": {k: j.key() for k, j in c["bands"].items()},
                                                  "los_only": c["los"].key()} for scen, c in cases.items()},
                "reference": "3GPP TR 38.901 V19.5.0 Tables 7.4.1-1 and 7.4.2-1 (docs/references.md 5.1)",
                "seconds": round(time.perf_counter() - started, 1), "versions": runtime.versions()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [f"# {exp.label}", "", "## Ray tracing vs 3GPP TR 38.901 (model-to-model comparison)", "",
             f"Isotropic antenna at ({x0:.0f}, {y0:.0f}) m, at least {args.clearance:g} m from any building; users at "
             f"{h_ut:g} m; profile {exp.profile.name} ({exp.profile.cell_size_m:g} m cells, {exp.profile.rays_per_site:.0e} rays); "
             f"mechanisms LOS + {exp.config.mechanisms.max_depth} reflections + first-order diffraction. LOS/NLOS from a "
             "line-of-sight-only trace. Error = traced − 3GPP path loss (positive: the ray tracer predicts more loss). "
             "Cells closer than 10 m are outside the models and excluded; unreached cells are counted, not averaged.", "",
             "**Applicability.** Base-station heights equal the models' (25 m, 10 m); 0.5-100 GHz and 10 m-5 km hold. "
             f"Not matched: the district (provisional, {exp.quality['height_categories']['by_count_percent']['placeholder']:.0f} % "
             "placeholder heights; UMi assumes the antenna below the rooftops, here most roofs are 9 m) and the statistical "
             "nature of the models (generic layouts, shadow fading σ). Agreement within about σ is the most that can be "
             "expected; it is a plausibility check, not a validation against measurements.", ""]
    for scen in cases:
        lines += [f"### {scen} (base station {cases[scen]['pos'][2]:g} m); LOS share of outdoor cells {100 * summary[scen]['los_share']:.0f} %", "",
                  "| Band | LOS cells: mean / std / RMSE | NLOS cells: mean / std / RMSE | σ LOS / NLOS | "
                  "Fitted exponent LOS / NLOS | Unreached |",
                  "|---|---|---|---|---|---|"]
        for sc in exp.scenarios:
            b = summary[scen]["bands"][sc["id"]]

            def f(s):
                return "—" if s["n"] == 0 else f"{s['mean_db']:+.1f} / {s['std_db']:.1f} / {s['rmse_db']:.1f} dB (n={s['n']})"
            lines.append(f"| {sc['label']} {sc['frequency_hz'] / 1e9:g} GHz | {f(b['LOS'])} | {f(b['NLOS'])} | "
                         f"{m.SIGMA_DB[(scen, 'LOS')]:g} / {m.SIGMA_DB[(scen, 'NLOS')]:g} dB | "
                         f"{b['LOS'].get('pathloss_exponent', float('nan')):.2f} / {b['NLOS'].get('pathloss_exponent', float('nan')):.2f} | "
                         f"{b['unreached_cells']} of {b['cells']} |")
        lines += ["", "| Distance | Cells | Traced LOS share | TR 38.901 LOS probability |", "|---|---|---|---|"]
        for r in summary[scen]["los_probability"]:
            if r["traced_los_share"] is not None:
                lines.append(f"| {r['d_from_m']:.0f}-{r['d_to_m']:.0f} m | {r['cells']} | {100 * r['traced_los_share']:.0f} % | "
                             f"{100 * r['tr38901']:.0f} % |")
        lines.append("")
    lines.append("Fitted exponent n from PL = A + 10 n log10(d3D) over the reached cells (TR 38.901 below the breakpoint: "
                 "UMa LOS 2.2, NLOS 3.91; UMi LOS 2.1, NLOS 3.53). Published measured exponents near 7-17 GHz: about "
                 "1.8-2.3 in line of sight and 2.6-2.7 without (docs/related-studies.md R4-R6).")
    lines.append(f"Run time {time.perf_counter() - started:.0f} s. Figures: pathloss_UMa.png, pathloss_UMi.png, los_probability.png.")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OUTPUT {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
