"""Compare MATLAB results of a cross-check case with the Sionna values it was exported with.

    uv run python scripts/compare_matlab.py validation/matlab/<case>

Needs matlab_results.csv (written by run_case.m on a machine with MATLAB). Writes
comparison.md and comparison.json into the case folder.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    results = args.case / "matlab_results.csv"
    if not results.exists():
        print(f"No {results}: run run_case.m in MATLAB first. Nothing has been verified.")
        return 1
    spec = json.loads((args.case / "case.json").read_text(encoding="utf-8"))
    with open(args.case / "receivers.csv", encoding="utf-8") as f:
        rx = {int(r["id"]): r for r in csv.DictReader(line for line in f if not line.startswith("#"))}
    with open(results, encoding="utf-8") as f:
        ml = list(csv.DictReader(f))
    out, lines = {}, [f"# MATLAB vs Sionna, case {spec['case']}", "", "| Band | Class | n | Reached by MATLAB | "
                      "Mean (MATLAB - Sionna) | Median | RMSE |", "|---|---|---|---|---|---|---|"]
    for band, freq in zip(spec["bands"], spec["frequencies_hz"], strict=True):
        rows = [r for r in ml if abs(float(r["frequency_hz"]) - freq) < 1.0]
        for cls, name in ((1, "LOS"), (0, "NLOS")):
            sel = [r for r in rows if int(rx[int(r["id"])]["los"]) == cls]
            reached = [r for r in sel if r["matlab_pathloss_db"] not in ("", "NaN", "nan")]
            d = np.array([float(r["matlab_pathloss_db"]) - float(rx[int(r["id"])][f"sionna_pathloss_db_{band}"])
                          for r in reached])
            s = {"n": len(sel), "reached": len(reached)}
            if d.size:
                s.update(mean_db=float(d.mean()), median_db=float(np.median(d)), rmse_db=float(np.sqrt((d**2).mean())))
            out[f"{band}_{name}"] = s
            lines.append(f"| {band} | {name} | {s['n']} | {s['reached']} | "
                         + (" | ".join(f"{s[k]:+.1f} dB" for k in ("mean_db", "median_db", "rmse_db")) if d.size else "— | — | —")
                         + " |")
    (args.case / "comparison.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (args.case / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
