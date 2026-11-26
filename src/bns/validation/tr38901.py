"""3GPP TR 38.901 path loss and line-of-sight probability: UMa and UMi street canyon.

Source: 3GPP TR 38.901 V19.5.0, Table 7.4.1-1 (path loss) and Table 7.4.2-1 (LOS
probability), as transcribed in docs/references.md §5.1. fc in GHz inside the formulas,
distances in metres, path loss in dB (positive), shadow fading not included (sigma is
returned for comparison). d3D = sqrt(d2D^2 + (hBS - hUT)^2).

Validity (checked by `applicable`): 0.5-100 GHz; 10 m <= d2D <= 5 km; 1.5 m <= hUT <=
22.5 m; hBS = 25 m (UMa) or 10 m (UMi). Outside these the formulas are not defined and
results must not be reported as a model comparison without qualification.
"""

from __future__ import annotations

import numpy as np

C = 3.0e8          # m/s, as in the TR's breakpoint definition
H_E = 1.0          # effective environment height for a user below 13 m (UMa) and for UMi
SIGMA_DB = {("UMa", "LOS"): 4.0, ("UMa", "NLOS"): 6.0, ("UMi", "LOS"): 4.0, ("UMi", "NLOS"): 7.82}
BS_HEIGHT_M = {"UMa": 25.0, "UMi": 10.0}


def breakpoint_m(h_bs: float, h_ut: float, fc_hz: float) -> float:
    """d'BP = 4 (hBS - hE)(hUT - hE) fc / c."""
    return 4.0 * (h_bs - H_E) * (h_ut - H_E) * fc_hz / C


def _d3d(d2d, h_bs, h_ut):
    return np.sqrt(np.asarray(d2d, dtype=float) ** 2 + (h_bs - h_ut) ** 2)


def pathloss_los(scenario: str, d2d, fc_hz: float, h_bs: float, h_ut: float) -> np.ndarray:
    f = fc_hz / 1e9
    d2d = np.asarray(d2d, dtype=float)
    d3 = _d3d(d2d, h_bs, h_ut)
    bp = breakpoint_m(h_bs, h_ut, fc_hz)
    if scenario == "UMa":
        pl1 = 28.0 + 22.0 * np.log10(d3) + 20.0 * np.log10(f)
        pl2 = 28.0 + 40.0 * np.log10(d3) + 20.0 * np.log10(f) - 9.0 * np.log10(bp**2 + (h_bs - h_ut) ** 2)
    elif scenario == "UMi":
        pl1 = 32.4 + 21.0 * np.log10(d3) + 20.0 * np.log10(f)
        pl2 = 32.4 + 40.0 * np.log10(d3) + 20.0 * np.log10(f) - 9.5 * np.log10(bp**2 + (h_bs - h_ut) ** 2)
    else:
        raise ValueError("scenario must be 'UMa' or 'UMi'.")
    return np.where(d2d <= bp, pl1, pl2)


def pathloss_nlos(scenario: str, d2d, fc_hz: float, h_bs: float, h_ut: float) -> np.ndarray:
    f = fc_hz / 1e9
    d3 = _d3d(d2d, h_bs, h_ut)
    if scenario == "UMa":
        nlos = 13.54 + 39.08 * np.log10(d3) + 20.0 * np.log10(f) - 0.6 * (h_ut - 1.5)
    elif scenario == "UMi":
        nlos = 35.3 * np.log10(d3) + 22.4 + 21.3 * np.log10(f) - 0.3 * (h_ut - 1.5)
    else:
        raise ValueError("scenario must be 'UMa' or 'UMi'.")
    return np.maximum(pathloss_los(scenario, d2d, fc_hz, h_bs, h_ut), nlos)


def los_probability(scenario: str, d2d) -> np.ndarray:
    """Table 7.4.2-1 for a user below 13 m (UMa) and for UMi street canyon."""
    d = np.maximum(np.asarray(d2d, dtype=float), 1e-9)
    scale = {"UMa": 63.0, "UMi": 36.0}[scenario]
    p = 18.0 / d + np.exp(-d / scale) * (1.0 - 18.0 / d)
    return np.where(d <= 18.0, 1.0, p)


def applicable(scenario: str, d2d, fc_hz: float, h_bs: float, h_ut: float) -> tuple[np.ndarray, list[str]]:
    """Mask of distances where the model is defined, and the reasons any condition fails."""
    reasons = []
    if not 0.5e9 <= fc_hz <= 100e9:
        reasons.append(f"frequency {fc_hz / 1e9:g} GHz outside 0.5-100 GHz")
    if not 1.5 <= h_ut <= 22.5:
        reasons.append(f"user height {h_ut:g} m outside 1.5-22.5 m")
    if abs(h_bs - BS_HEIGHT_M[scenario]) > 1e-6:
        reasons.append(f"base-station height {h_bs:g} m, the model assumes {BS_HEIGHT_M[scenario]:g} m")
    d2d = np.asarray(d2d, dtype=float)
    mask = (d2d >= 10.0) & (d2d <= 5000.0)
    if reasons:
        mask = np.zeros_like(mask)
    return mask, reasons
