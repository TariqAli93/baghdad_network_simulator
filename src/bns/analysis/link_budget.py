"""From ray-traced path gain to received power, SINR and data rate.

Propagation and radio system are kept apart on purpose: the ray tracer supplies
path gain only, and every radio-system quantity (transmit power, antenna gains,
noise, bandwidth) enters here as an explicit argument. Nothing in this module
has a default power level, noise figure or threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bns.core.units import linear_to_db


def received_power_dbm(tx_power_dbm, path_gain, tx_gain_dbi=0.0, rx_gain_dbi=0.0,
                       extra_loss_db=0.0):
    """Received power = transmit power + antenna gains + path gain - extra losses.

    path_gain is the linear path gain between isotropic antennas (0 = no path,
    which gives -inf dBm). extra_loss_db carries losses the ray tracer does not
    model (rain, gases); it may be a scalar or an array matching the map.
    """
    return (np.asarray(tx_power_dbm, dtype=float) + tx_gain_dbi + rx_gain_dbi
            + linear_to_db(path_gain) - np.asarray(extra_loss_db, dtype=float))


@dataclass(frozen=True)
class SinrResult:
    sinr: np.ndarray            # linear; 0 where no site is received
    serving: np.ndarray         # index of the serving site; -1 where no site is received
    signal_w: np.ndarray
    interference_w: np.ndarray  # after the activity factor


def sinr(received_w, noise_w: float, *, interference_activity: float) -> SinrResult:
    """Signal-to-interference-plus-noise ratio with the strongest site serving.

    received_w has shape [sites, ...]: the power received from every site at
    every receiver, in watts. All sites are assumed to use the same carrier.
    Interference is the sum, in watts, of all non-serving sites, multiplied by
    interference_activity: 1.0 means every other site transmits at full power
    all the time (the usual worst case), 0.0 means no interference.
    The caller must choose that factor; there is no default.
    """
    received = np.asarray(received_w, dtype=float)
    if received.ndim < 2:
        raise ValueError("received_w must have shape [sites, ...].")
    if np.any(received < 0) or not np.all(np.isfinite(received)):
        raise ValueError("received_w must be finite and non-negative (watts).")
    if noise_w < 0:
        raise ValueError("noise_w must be non-negative (watts).")
    if not 0.0 <= interference_activity <= 1.0:
        raise ValueError("interference_activity must be between 0 and 1.")

    serving = np.argmax(received, axis=0)
    signal = np.max(received, axis=0)
    interference = interference_activity * (received.sum(axis=0) - signal)
    denominator = interference + noise_w
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(signal > 0, signal / denominator, 0.0)
    return SinrResult(ratio, np.where(signal > 0, serving, -1), signal, interference)


def shannon_capacity_bps(bandwidth_hz, sinr_linear):
    """C = B * log2(1 + SINR), in bit/s. A theoretical upper bound, not user throughput."""
    ratio = np.asarray(sinr_linear, dtype=float)
    if np.any(ratio < 0):
        raise ValueError("SINR must be given as a non-negative linear ratio, not in dB.")
    return np.asarray(bandwidth_hz, dtype=float) * np.log2(1.0 + ratio)


def truncated_shannon_bps(bandwidth_hz, sinr_linear, *, alpha: float, sinr_min_db: float, sinr_max_db: float):
    """Practical rate beside the Shannon bound (decision B3; 3GPP TR 38.921 Table 4.2.7-1).

    0 below sinr_min_db; alpha * B * log2(1 + SINR) between; the value at sinr_max_db above.
    The constants come from the approved configuration (configs/radio_system.yaml, rate_mapping).
    """
    ratio = np.asarray(sinr_linear, dtype=float)
    if np.any(ratio < 0):
        raise ValueError("SINR must be given as a non-negative linear ratio, not in dB.")
    lo, hi = 10 ** (sinr_min_db / 10), 10 ** (sinr_max_db / 10)
    rate = alpha * np.asarray(bandwidth_hz, dtype=float) * np.log2(1.0 + np.minimum(ratio, hi))
    return np.where(ratio >= lo, rate, 0.0)
