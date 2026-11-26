"""Agreement of two runs of the same experiment traced on different backends (CPU vs GPU).

    uv run python scripts/compare_backends.py CPU_RUN_DIR GPU_RUN_DIR

Both runs must be multi-site runs with the same sites, grid, profile and radio inputs;
only the backend may differ (checked). Per scenario it reports, over outdoor cells:
best-sector path gain (median and 95th-percentile |difference|, weak-signal cells below
-140 dB separately), coverage classification differences, SINR differences, and the
5th-percentile and median Shannon rate. Writes backend_agreement.md/.json into GPU_RUN_DIR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from bns.app.results import load_run

WEAK_DB = -140.0
SAME = ("grid", "profile", "mechanisms", "seeds", "radio_parameters", "sites", "sectors_per_site", "scenarios")


def compare(a, b, sid: str, outdoor) -> dict:
    pa, pb = a.layer(sid, "path_gain_db"), b.layer(sid, "path_gain_db")
    both = outdoor & np.isfinite(pa) & np.isfinite(pb)
    d = np.abs(pa - pb)[both]
    weak = both & (np.minimum(pa, pb) < WEAK_DB)
    sa, sb = a.layer(sid, "sinr_db"), b.layer(sid, "sinr_db")
    sboth = outdoor & np.isfinite(sa) & np.isfinite(sb)
    ds = np.abs(sa - sb)[sboth]
    ca, cb = a.layer(sid, "covered"), b.layer(sid, "covered")
    ra, rb = a.scenario_summary(sid), b.scenario_summary(sid)
    return {
        "outdoor_cells": int(outdoor.sum()),
        "reached_by_one_backend_only": int((outdoor & (np.isfinite(pa) != np.isfinite(pb))).sum()),
        "path_gain_abs_diff_db": {"median": float(np.median(d)), "p95": float(np.percentile(d, 95)),
                                  "max": float(d.max())},
        "weak_cells": int(weak.sum()),
        "weak_cells_abs_diff_db_median": float(np.median(np.abs(pa - pb)[weak])) if weak.any() else None,
        "coverage_class_changed_cells": int((outdoor & (ca != cb)).sum()),
        "coverage_fraction": [ra["coverage_fraction"], rb["coverage_fraction"]],
        "sinr_abs_diff_db": {"median": float(np.median(ds)), "p95": float(np.percentile(ds, 95))},
        "sinr_median_db": [ra["sinr_db_median"], rb["sinr_db_median"]],
        "rate_p5_mbps": [ra["rate_p5_bps"] / 1e6, rb["rate_p5_bps"] / 1e6],
        "rate_p5_relative_diff": abs(rb["rate_p5_bps"] - ra["rate_p5_bps"]) / max(ra["rate_p5_bps"], 1e-9),
        "rate_median_mbps": [ra["rate_median_bps"] / 1e6, rb["rate_median_bps"] / 1e6],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    args = parser.parse_args()
    a, b = load_run(args.a), load_run(args.b)
    def key(run, k):
        v = run.manifest.get(k)
        if k == "profile":                            # status labels are documentation, not physics
            v = {f: v[f] for f in ("name", "cell_size_m", "rays_per_site")}
        return json.dumps(v, sort_keys=True, default=str)

    differ = [k for k in SAME if key(a, k) != key(b, k)]
    if differ:
        print(f"The runs differ in more than the backend: {differ}")
        return 1
    backends = [r.manifest.get("backend", {}).get("name", "cpu") for r in (a, b)]
    outdoor = a.outdoor
    rows = {sc["id"]: compare(a, b, sc["id"], outdoor) for sc in a.scenarios}
    lines = [f"# {a.label}", "", f"## Backend agreement: {backends[0]} ({a.run_id}) vs {backends[1]} ({b.run_id})", "",
             "Same sites, grid, profile, mechanisms, seeds and radio inputs (checked); only the ray-tracing backend "
             f"differs. Outdoor cells: {int(outdoor.sum())}. Weak cells: best-sector path gain below {WEAK_DB:g} dB.", "",
             "| Scenario | Path gain |Δ| median / p95 / max | Weak cells (median |Δ|) | Reached by one only | "
             "Coverage class changed | SINR |Δ| median / p95 | 5th-pct rate A / B | Median rate A / B |",
             "|---|---|---|---|---|---|---|---|"]
    for sc in a.scenarios:
        r = rows[sc["id"]]
        pg, s = r["path_gain_abs_diff_db"], r["sinr_abs_diff_db"]
        weak = "—" if r["weak_cells_abs_diff_db_median"] is None else f"{r['weak_cells_abs_diff_db_median']:.2f} dB"
        lines.append(f"| {sc['label']} | {pg['median']:.2f} / {pg['p95']:.2f} / {pg['max']:.1f} dB | {r['weak_cells']} ({weak}) | "
                     f"{r['reached_by_one_backend_only']} | {r['coverage_class_changed_cells']} | "
                     f"{s['median']:.2f} / {s['p95']:.2f} dB | {r['rate_p5_mbps'][0]:.1f} / {r['rate_p5_mbps'][1]:.1f} Mbit/s | "
                     f"{r['rate_median_mbps'][0]:.0f} / {r['rate_median_mbps'][1]:.0f} Mbit/s |")
    lines += ["", "Differences come from the randomly sampled diffraction and floating-point order; line of sight "
                  "and reflections are deterministic on both backends."]
    (args.b / "backend_agreement.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.b / "backend_agreement.json").write_text(json.dumps({"runs": [a.run_id, b.run_id], "backends": backends,
                                                              "results": rows}, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
