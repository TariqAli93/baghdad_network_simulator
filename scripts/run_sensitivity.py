"""Coverage and interference sensitivity of a saved multi-site run (cached path gain, no tracing).

    uv run python scripts/run_sensitivity.py RUN_DIR

For every scenario, every coverage threshold and every interference activity (load) in
the sweep below, the network is re-evaluated from the cached path gain for
  - the first site alone and all sites together, and
  - the SINR-based greedy selection (coverage target from the radio configuration).
Reported: coverage, median and 5th-percentile SINR, 5th-percentile Shannon rate, the
greedy site count and why it stopped. Separately, and labelled illustrative, the
5th-percentile rate when each sector's time is shared equally among the outdoor cells it
serves (bns.simulation.network.equal_share_rate_bps).

The sweep values are provisional, NOT proposals: -10 dB and loads 1.0 and 0.5 are the
sourced candidates (configs/radio_system.yaml); the other points are an evenly spaced
grid chosen before looking at results, to show how the conclusions depend on them.
Writes sensitivity.md, sensitivity.json and sensitivity.png into RUN_DIR.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


from bns.analysis import metrics
from bns.app import planning
from bns.app.results import load_run
from bns.simulation.network import equal_share_rate_bps

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_DB = [-10.0, -6.0, -3.0, 0.0, 3.0, 6.0]
LOADS = [1.0, 0.5, 0.2]
SOURCED = {"threshold": [-10.0], "load": [1.0, 0.5]}


def row(net, outdoor) -> dict:
    s = net.radio.summary
    shared = equal_share_rate_bps(net.radio.rate_bps, net.serving_sector, outdoor)
    return {"coverage": s["coverage_fraction"], "sinr_median_db": s["sinr_db_median"], "sinr_p5_db": s["sinr_db_p5"],
            "rate_p5_mbps": s["rate_p5_bps"] / 1e6,
            "illustrative_equal_share_rate_p5_mbps": metrics.percentile(shared, 5, outdoor) / 1e6,
            "illustrative_equal_share_rate_median_mbps": metrics.percentile(shared, 50, outdoor) / 1e6}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    run = load_run(args.run)
    n_sites = len(run.sites)
    results = {}
    for sc in run.scenarios:
        s = planning.load_stacks(ROOT, run, sc["id"])
        target = s.experiment.system.require("coverage_target", mode=s.experiment.mode)
        outdoor = s.experiment.outdoor
        cases = []
        for load in LOADS:
            for thr in THRESHOLDS_DB:
                one = planning.evaluate(s, (0,), interference_activity=load, coverage_threshold=thr)
                allsites = planning.evaluate(s, tuple(range(n_sites)), interference_activity=load,
                                             coverage_threshold=thr)
                g = planning.greedy(s, target, interference_activity=load, coverage_threshold=thr)
                cases.append({"load": load, "threshold_db": thr,
                              "sourced": thr in SOURCED["threshold"] and load in SOURCED["load"],
                              "site_1_alone": row(one, outdoor), "all_sites": row(allsites, outdoor),
                              "greedy": {"sites": len(g.selected), "selected": [i + 1 for i in g.selected],
                                         "coverage": g.coverage_after[-1] if g.coverage_after else 0.0,
                                         "target": target, "target_reached": g.target_reached,
                                         "stopped_because": g.stopped_because,
                                         "degrading_additions": len(g.degrading_additions)}})
        results[sc["id"]] = cases
        print(f"{sc['id']}: {len(cases)} cases", flush=True)

    out = args.run
    from bns.analysis import classification as cl
    source = cl.from_manifest(run.manifest)
    label = cl.Classification(cl.SENSITIVITY, source.dataset, source.validation).label
    (out / "sensitivity.json").write_text(json.dumps({"label": label, "run": run.run_id, "thresholds_db": THRESHOLDS_DB,
                                                     "loads": LOADS, "sourced": SOURCED, "results": results}, indent=1),
                                          encoding="utf-8")
    lines = [f"# {label}", "", f"## Coverage and interference sensitivity, run {run.run_id}", "",
             f"{n_sites} candidate sites (all sectors on one carrier). Re-evaluated from cached path gain; nothing traced. "
             "Coverage = share of outdoor cells with SINR at or above the threshold. **Bold** rows use only sourced "
             "candidate values (threshold −10 dB; load 1.0 or 0.5); every other row is a provisional sweep point.", "",
             "Terms: *coverage* is a SINR condition; *signal quality* is the SINR distribution; the *Shannon rate* is "
             "the theoretical link capacity of one user with the whole carrier (upper bound); the *equal-share rate* is an "
             "illustrative split of each sector among the outdoor cells it serves, not network capacity and not user "
             "throughput.", ""]
    for sc in run.scenarios:
        lines += [f"### {sc['label']} ({sc['frequency_hz'] / 1e9:g} GHz, {sc['bandwidth_hz'] / 1e6:g} MHz)", "",
                  "| Load | Threshold | Coverage: site 1 / all | Median SINR: site 1 / all | 5th-pct SINR: site 1 / all | "
                  "5th-pct Shannon rate: site 1 / all | Illustrative equal-share 5th-pct rate: site 1 / all | Greedy sites (stop) |",
                  "|---|---|---|---|---|---|---|---|"]
        for c in results[sc["id"]]:
            a, b, g = c["site_1_alone"], c["all_sites"], c["greedy"]
            bold = "**" if c["sourced"] else ""
            lines.append(f"| {bold}{c['load']:g}{bold} | {bold}{c['threshold_db']:+g} dB{bold} | "
                         f"{100 * a['coverage']:.1f} / {100 * b['coverage']:.1f} % | "
                         f"{a['sinr_median_db']:.1f} / {b['sinr_median_db']:.1f} dB | {a['sinr_p5_db']:.1f} / {b['sinr_p5_db']:.1f} dB | "
                         f"{a['rate_p5_mbps']:.1f} / {b['rate_p5_mbps']:.1f} | "
                         f"{a['illustrative_equal_share_rate_p5_mbps']:.3f} / {b['illustrative_equal_share_rate_p5_mbps']:.3f} | "
                         f"{g['sites']} {g['selected']} ({g['stopped_because']}) |")
        lines.append("")
    lines += [f"Rates in Mbit/s. Greedy target {100 * target:.0f} % of outdoor cells over these {n_sites} candidates only. "
              f"Computed in {time.perf_counter() - started:.0f} s."]
    (out / "sensitivity.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt
    style.apply()
    fig, axes = plt.subplots(1, len(LOADS), figsize=(15, 4.2), sharey=True)
    for ax, load in zip(axes, LOADS, strict=True):
        for sc in run.scenarios:
            cs = [c for c in results[sc["id"]] if c["load"] == load]
            colour = style.SCENARIO_COLORS[sc["id"]]
            ax.plot([c["threshold_db"] for c in cs], [100 * c["all_sites"]["coverage"] for c in cs], color=colour,
                    marker="o", label=f"{sc['label']}, {n_sites} sites")
            ax.plot([c["threshold_db"] for c in cs], [100 * c["site_1_alone"]["coverage"] for c in cs], color=colour,
                    linestyle="--", linewidth=1)
        ax.axvline(-10, color=style.INK_MUTED, linewidth=0.8)
        ax.set(title=f"load {load:g}", xlabel="SINR threshold [dB]")
    axes[0].set_ylabel("outdoor cells covered [%] (dashed: site 1 alone)")
    axes[-1].legend(fontsize=7)
    fig.suptitle(label, x=0.05, ha="left", fontsize=10, fontweight="bold")
    fig.savefig(out / "sensitivity.png")
    print("\n".join(lines[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
