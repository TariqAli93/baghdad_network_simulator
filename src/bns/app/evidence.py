"""Tables of saved evidence for the Comparison, Reports and Roadmap pages (no new calculation).

Every row carries the label and the identity of the run it comes from, so a page can never
show a number without its provenance.
"""

from __future__ import annotations

import json
from pathlib import Path

from bns.app import results


def band_table(run: results.Run) -> list[dict]:
    rows = []
    for sc in run.scenarios:
        s = run.scenario_summary(sc["id"])
        rows.append({"scenario_id": sc["id"], "scenario": sc["label"], "frequency_ghz": sc["frequency_hz"] / 1e9,
                     "bandwidth_mhz": sc["bandwidth_hz"] / 1e6, "status": sc.get("status", ""),
                     "coverage": s.get("coverage_fraction"), "rx_power_median_dbm": s.get("rx_power_dbm_median"),
                     "sinr_median_db": s.get("sinr_db_median"), "sinr_p5_db": s.get("sinr_db_p5"),
                     "rate_p5_mbps": None if s.get("rate_p5_bps") is None else s["rate_p5_bps"] / 1e6,
                     "rate_median_mbps": None if s.get("rate_median_bps") is None else s["rate_median_bps"] / 1e6,
                     "run": run.run_id, "label": run.label})
    return rows


def site_plans(root: Path) -> list[dict]:
    """One row per saved site plan and scenario: sites selected, density, stop reason, assumptions."""
    rows = []
    for run in results.list_runs(root):
        if run.kind != "site_plan":
            continue
        m = run.manifest
        params = m.get("radio_parameters", {})
        overrides = m.get("overrides_for_sensitivity") or {}
        threshold = overrides.get("coverage_threshold", (params.get("coverage_threshold") or {}).get("value"))
        load = overrides.get("interference_activity", (params.get("interference_activity") or {}).get("value"))
        for sc in run.scenarios:
            r = run.summary["results"][sc["id"]]
            rows.append({"run": run.run_id, "scenario_id": sc["id"], "scenario": sc["label"],
                         "frequency_ghz": sc["frequency_hz"] / 1e9, "threshold_db": threshold, "load": load,
                         "overrides": bool(overrides), "candidates": len(run.sites), "sites": r["sites"],
                         "site_density_per_km2": r["site_density_per_km2"],
                         "coverage": (r["coverage_after"] or [None])[-1], "target": r["target"],
                         "stopped_because": r["stopped_because"], "profile": m["profile"]["name"],
                         "backend": run.backend, "label": run.label})
    return rows


def validation_summary(root: Path) -> dict | None:
    """Latest TR 38.901 comparison: RMSE per scenario, band and LOS class."""
    folders = results.list_validations(root)
    if not folders:
        return None
    summary = json.loads((folders[0] / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((folders[0] / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for scen, s in summary.items():
        for band, b in s["bands"].items():
            for cls in ("LOS", "NLOS"):
                st = b[cls]
                if st.get("n"):
                    rows.append({"model": scen, "scenario_id": band, "class": cls, "n": st["n"],
                                 "mean_error_db": st["mean_db"], "std_db": st["std_db"], "rmse_db": st["rmse_db"],
                                 "sigma_sf_db": st["sigma_sf_db"]})
    return {"folder": folders[0], "manifest": manifest, "summary": summary, "rows": rows}
