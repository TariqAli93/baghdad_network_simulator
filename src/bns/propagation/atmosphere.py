"""Losses the ray tracer does not model: rain and atmospheric gases.

They are added after ray tracing as a specific attenuation (dB/km) times the
straight-line distance from the site to the receiver cell. A reflected or
diffracted path is slightly longer than that, so the loss is a lower bound;
over a 1 km2 area the difference is far below the other uncertainties.

Sources (IDs in docs/references.md):
    ITU-P838   Rec. ITU-R P.838-3: gamma_R = k * R**alpha; k and alpha from
               eqs (2)-(3) with the coefficients of its Tables 1-4. The unit
               tests check the result against its Table 5.
    ITU-P676   Rec. ITU-R P.676-13, Annex 1 (line-by-line). The values for the five
               scenario bands are stored here (GAS_DB_PER_KM); any other carrier is
               computed with the same method through ITURPY (ITU-Rpy 0.4.0, edition
               P.676-12), which reproduces the stored values.

The baseline of the project is clear sky: gases included, no rain. No rain
rate for Baghdad is built in.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bns.geospatial.grid import Grid

# --- rain: ITU-R P.838-3 ------------------------------------------------------------

# (a_j, b_j, c_j) terms, then m and c, for log10(k) and for alpha; Tables 1-4.
_K_H = ([(-5.33980, -0.10008, 1.13098), (-0.35351, 1.26970, 0.45400),
         (-0.23789, 0.86036, 0.15354), (-0.94158, 0.64552, 0.16817)], -0.18961, 0.71147)
_K_V = ([(-3.80595, 0.56934, 0.81061), (-3.44965, -0.22911, 0.51059),
         (-0.39902, 0.73042, 0.11899), (0.50167, 1.07319, 0.27195)], -0.16398, 0.63297)
_ALPHA_H = ([(-0.14318, 1.82442, -0.55187), (0.29591, 0.77564, 0.19822),
             (0.32177, 0.63773, 0.13164), (-5.37610, -0.96230, 1.47828),
             (16.1721, -3.29980, 3.43990)], 0.67849, -1.95537)
_ALPHA_V = ([(-0.07771, 2.33840, -0.76284), (0.56727, 0.95545, 0.54039),
             (-0.20238, 1.14520, 0.26809), (-48.2991, 0.791669, 0.116226),
             (48.5833, 0.791459, 0.116479)], -0.053739, 0.83433)


def _series(terms_m_c, log_f: float) -> float:
    terms, m, c = terms_m_c
    return sum(a * np.exp(-(((log_f - b) / cj) ** 2)) for a, b, cj in terms) + m * log_f + c


def rain_coefficients(frequency_hz: float, polarization: str) -> tuple[float, float]:
    """k and alpha of ITU-R P.838-3 for horizontal ("H") or vertical ("V") polarisation."""
    f_ghz = frequency_hz / 1e9
    if not 1.0 <= f_ghz <= 1000.0:
        raise ValueError("ITU-R P.838-3 is defined for 1-1000 GHz.")
    if polarization not in ("H", "V"):
        raise ValueError("polarization must be 'H' or 'V'.")
    log_f = float(np.log10(f_ghz))
    k_terms, alpha_terms = (_K_H, _ALPHA_H) if polarization == "H" else (_K_V, _ALPHA_V)
    return float(10.0 ** _series(k_terms, log_f)), float(_series(alpha_terms, log_f))


def rain_specific_attenuation_db_per_km(frequency_hz: float, rain_rate_mm_h: float,
                                        polarization: str) -> float:
    """Specific attenuation of rain, gamma_R = k * R**alpha, in dB/km."""
    if rain_rate_mm_h < 0:
        raise ValueError("rain rate must not be negative.")
    if rain_rate_mm_h == 0:
        return 0.0
    k, alpha = rain_coefficients(frequency_hz, polarization)
    return float(k * rain_rate_mm_h**alpha)


# --- gases: ITU-R P.676-13 ----------------------------------------------------------

# Sea-level specific attenuation (oxygen + water vapour) for the reference atmosphere of
# P.676-13 (1013.25 hPa, 15 degC, water-vapour density 7.5 g/m3), in dB/km, for the five
# scenario carriers only. The Recommendation gives a method and a figure, not a table, so
# these were computed with its Annex 1; provenance is recorded in docs/atmospheric-losses.md.
GAS_DB_PER_KM = {
    1.8e9: 0.0068,
    3.5e9: 0.0078,
    8.0e9: 0.0114,
    15.0e9: 0.0291,
    28.0e9: 0.1018,
}


def gas_specific_attenuation_db_per_km(frequency_hz: float) -> float:
    """Gas attenuation for one of the tabulated carriers; other frequencies are refused."""
    for tabulated, value in GAS_DB_PER_KM.items():
        if abs(frequency_hz - tabulated) <= 1e-6 * tabulated:
            return value
    raise ValueError(
        f"Gas attenuation is not tabulated for {frequency_hz / 1e9:g} GHz. Compute it with "
        "ITU-R P.676-13 Annex 1 and add it to GAS_DB_PER_KM with its provenance.")


# Any other carrier (custom carriers of the simulation workspace): the same calculation, ITU-R P.676
# Annex 1 line by line, through ITU-Rpy (the library the five tabulated values were computed with), in
# the same reference atmosphere. The five preset carriers keep their tabulated values, so the research
# baseline and every earlier result stay exactly as they were.
P676_RANGE_HZ = (1e9, 1000e9)            # P.676 Annex 1 line-by-line method
REFERENCE_ATMOSPHERE = {"pressure_hpa": 1013.25, "temperature_k": 288.15, "water_vapour_g_m3": 7.5}


def gas_model() -> dict:
    """The gas-attenuation model used for untabulated carriers, with versions (recorded in every result)."""
    from importlib.metadata import version

    import itur.models.itu676 as itu676

    return {"recommendation": f"ITU-R P.676-{itu676.get_version()} Annex 1 (line by line)",
            "implementation": f"ITU-Rpy {version('itur')}", **REFERENCE_ATMOSPHERE}


def gas_specific_attenuation_p676_db_per_km(frequency_hz: float) -> float:
    """Sea-level gas attenuation (oxygen + water vapour) at any carrier in P676_RANGE_HZ, in dB/km."""
    lo, hi = P676_RANGE_HZ
    if not lo <= frequency_hz <= hi:
        raise ValueError(f"ITU-R P.676 Annex 1 is defined for {lo / 1e9:g}-{hi / 1e9:g} GHz.")
    import warnings

    import itur.models.itu676 as itu676

    a = REFERENCE_ATMOSPHERE
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = itu676.gamma_exact(frequency_hz / 1e9, a["pressure_hpa"], a["water_vapour_g_m3"], a["temperature_k"])
    return float(getattr(value, "value", value))


# --- applying the losses ------------------------------------------------------------


def path_attenuation_db(specific_db_per_km: float, distance_m):
    return specific_db_per_km * np.asarray(distance_m, dtype=float) / 1000.0


def attenuation_map_db(tx_xyz, grid: Grid, specific_db_per_km: float) -> np.ndarray:
    """Loss in dB at every receiver cell, from the straight-line distance to the site."""
    xs, ys = np.meshgrid(grid.x_centers, grid.y_centers)
    distance = np.sqrt((xs - tx_xyz[0]) ** 2 + (ys - tx_xyz[1]) ** 2
                       + (grid.height_m - tx_xyz[2]) ** 2)
    return path_attenuation_db(specific_db_per_km, distance)


def load_conditions(path) -> tuple["Conditions", list[dict]]:
    """Baseline conditions and the rain cases of the sensitivity experiment.

    Each case is {"label", "conditions", "approved", "source"}.
    """
    from pathlib import Path

    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    base = data["baseline"]
    baseline = Conditions(float(base["rain_rate_mm_h"]), bool(base["include_gas"]))
    cases = [{"label": c["label"], "approved": bool(c["approved"]), "source": c["source"],
              "conditions": Conditions(float(c["rain_rate_mm_h"]), bool(base["include_gas"]))}
             for c in data["rain_sensitivity"]["cases"]]
    return baseline, cases


@dataclass(frozen=True)
class Conditions:
    """Atmospheric conditions of a run. Clear sky is rain_rate_mm_h = 0."""

    rain_rate_mm_h: float
    include_gas: bool

    def specific_attenuation_db_per_km(self, frequency_hz: float, polarization: str) -> float:
        gas = gas_specific_attenuation_db_per_km(frequency_hz) if self.include_gas else 0.0
        return gas + rain_specific_attenuation_db_per_km(frequency_hz, self.rain_rate_mm_h,
                                                         polarization)
