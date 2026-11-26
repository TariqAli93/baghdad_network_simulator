"""Rain and gas loss per band for the baseline and the rain-sensitivity cases.

    uv run python scripts/atmosphere_table.py

Pure arithmetic from ITU-R P.838-3 and the stored P.676-13 values; no ray tracing.
Writes outputs/atmosphere/loss_table.md and loss_table.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from bns.propagation import atmosphere as atm

ROOT = Path(__file__).resolve().parents[1]
DISTANCES_M = (250.0, 500.0, 1000.0)
POLARIZATION = "V"      # the transmit antenna used so far is vertically polarised


def main() -> int:
    scenarios = sorted(yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(
        encoding="utf-8"))["scenarios"], key=lambda s: float(s["frequency_hz"]))
    baseline, cases = atm.load_conditions(ROOT / "configs" / "atmosphere.yaml")
    rows = []
    for label, conditions, approved in [("clear sky (baseline)", baseline, True)] + [
            (c["label"], c["conditions"], c["approved"]) for c in cases]:
        for s in scenarios:
            f = float(s["frequency_hz"])
            gamma = conditions.specific_attenuation_db_per_km(f, POLARIZATION)
            rows.append({"case": label, "approved": approved, "scenario": s["id"],
                         "frequency_ghz": f / 1e9, "rain_rate_mm_h": conditions.rain_rate_mm_h,
                         "specific_attenuation_db_per_km": gamma,
                         "loss_db": {f"{int(d)} m": float(atm.path_attenuation_db(gamma, d))
                                     for d in DISTANCES_M}})

    out = ROOT / "outputs" / "atmosphere"
    out.mkdir(parents=True, exist_ok=True)
    (out / "loss_table.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = ["# Rain and gas loss per band", "",
             "Loss added to the ray-traced path loss, vertical polarisation. Only the clear-sky "
             "row is part of the project baseline; the rain rows are unapproved sensitivity cases.",
             "", "| Conditions | Band | dB/km | Loss over 250 m | 500 m | 1000 m |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        loss = r["loss_db"]
        lines.append(f"| {r['case']} ({r['rain_rate_mm_h']:g} mm/h) | {r['frequency_ghz']:g} GHz | "
                     f"{r['specific_attenuation_db_per_km']:.3f} | {loss['250 m']:.2f} dB | "
                     f"{loss['500 m']:.2f} dB | {loss['1000 m']:.2f} dB |")
    (out / "loss_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
