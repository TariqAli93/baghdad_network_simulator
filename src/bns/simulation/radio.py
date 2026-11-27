"""Radio-system results from cached path gain: received power, SNR/SINR, coverage, rate.

Inputs are path-gain maps (propagation only, from the ray tracer) and explicit
radio-system inputs. The outputs are radio-system results and carry the label
of the configuration that produced them; a path-gain map alone is never
reported as coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bns.analysis import link_budget as lb
from bns.analysis import metrics
from bns.core.units import dbm_to_watt, linear_to_db, noise_power_dbm


@dataclass(frozen=True)
class RadioInputs:
    tx_power_dbm: float                 # power to add to the traced path gain (see RadioSystem)
    rx_gain_dbi: float
    noise_figure_db: float
    noise_temperature_k: float
    bandwidth_hz: float
    coverage_definition: str            # "rx_power_dbm" or "snr_db"
    coverage_threshold: float
    interference_activity: float

    def __init__(self, *, eirp_dbm=None, tx_power_dbm=None, **rest):
        # eirp_dbm is accepted as a synonym for an isotropic radiator
        object.__setattr__(self, "tx_power_dbm", tx_power_dbm if tx_power_dbm is not None else eirp_dbm)
        for name, value in rest.items():
            object.__setattr__(self, name, value)
        if self.coverage_definition not in ("rx_power_dbm", "snr_db"):
            raise ValueError("coverage_definition must be 'rx_power_dbm' or 'snr_db'.")


@dataclass
class RadioResult:
    rx_power_dbm: np.ndarray        # best transmitter
    sinr_db: np.ndarray             # SNR for one transmitter
    serving: np.ndarray             # index of the serving transmitter, -1 if none
    rate_bps: np.ndarray            # Shannon upper bound
    covered: np.ndarray             # outdoor cells meeting the criterion
    noise_dbm: float
    summary: dict


def _check(path_gain: np.ndarray) -> np.ndarray:
    gain = np.asarray(path_gain, dtype=float)
    if not np.all(np.isfinite(gain)):
        raise ValueError("Path gain contains NaN or infinite values.")
    if np.any(gain < 0) or np.any(gain > 1):
        raise ValueError("Path gain must lie between 0 (no path) and 1.")
    return gain


def multi_site(path_gain_stack, outdoor, inputs: RadioInputs, extra_loss_db, external_interference_w=None) -> RadioResult:
    """Strongest transmitter serves, all others interfere (same carrier), shape [tx, y, x].
    external_interference_w: power [y, x] in watts from other carriers inside this band (never serving)."""
    gain = _check(path_gain_stack)
    outdoor = np.asarray(outdoor, dtype=bool)
    rx_dbm = lb.received_power_dbm(inputs.tx_power_dbm, gain, rx_gain_dbi=inputs.rx_gain_dbi,
                                   extra_loss_db=extra_loss_db)
    received_w = np.where(np.isfinite(rx_dbm), dbm_to_watt(np.where(np.isfinite(rx_dbm), rx_dbm, 0.0)), 0.0)
    noise_dbm = float(noise_power_dbm(inputs.bandwidth_hz, inputs.noise_figure_db, inputs.noise_temperature_k))
    sinr = lb.sinr(received_w, dbm_to_watt(noise_dbm), interference_activity=inputs.interference_activity,
                   external_interference_w=external_interference_w)
    sinr_db = linear_to_db(sinr.sinr)
    best_dbm = rx_dbm.max(axis=0)
    rate = lb.shannon_capacity_bps(inputs.bandwidth_hz, sinr.sinr)
    measure = best_dbm if inputs.coverage_definition == "rx_power_dbm" else sinr_db
    covered = outdoor & (measure >= inputs.coverage_threshold)
    reached = outdoor & np.isfinite(best_dbm)
    summary = {
        "transmitters": int(gain.shape[0]),
        "outdoor_cells": int(outdoor.sum()),
        "unreached_fraction": float(1 - reached.sum() / outdoor.sum()),
        "coverage_definition": inputs.coverage_definition,
        "coverage_threshold": inputs.coverage_threshold,
        "coverage_fraction": metrics.coverage_fraction(measure, inputs.coverage_threshold, outdoor),
        "noise_dbm": noise_dbm,
        "rx_power_dbm_median": float(np.median(best_dbm[reached])) if reached.any() else None,
        "rx_power_dbm_p5": float(np.percentile(best_dbm[reached], 5)) if reached.any() else None,
        "sinr_db_median": float(np.median(sinr_db[reached])) if reached.any() else None,
        "sinr_db_p5": metrics.percentile(np.where(np.isfinite(sinr_db), sinr_db, -1e9), 5, outdoor),
        "rate_median_bps": metrics.percentile(rate, 50, outdoor),
        "rate_p5_bps": metrics.percentile(rate, 5, outdoor),
        "rate_note": "Shannon capacity B*log2(1+SINR): a theoretical upper bound, not user throughput",
    }
    return RadioResult(best_dbm, sinr_db, sinr.serving, rate, covered, noise_dbm, summary)


def single_site(path_gain, outdoor, inputs: RadioInputs, extra_loss_db) -> RadioResult:
    """One transmitter: SINR is the SNR."""
    gain = np.asarray(path_gain, dtype=float)
    return multi_site(gain[None, ...], outdoor, inputs, np.asarray(extra_loss_db)[None, ...])
