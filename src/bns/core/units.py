"""Unit conversions and the basic link-budget relations.

Conventions used everywhere in the project:
    dB      ratio of two powers, 10*log10
    dBm     power relative to 1 mW
    W       power, linear
    Hz, m   frequency and distance in SI units
Path gain is the linear ratio received/transmitted power between isotropic
antennas (always <= 1); path loss in dB is -10*log10(path gain).
"""

from __future__ import annotations

import numpy as np

SPEED_OF_LIGHT = 299_792_458.0  # m/s
BOLTZMANN = 1.380649e-23  # J/K
T0_KELVIN = 290.0  # reference noise temperature


def db_to_linear(db):
    """Power ratio in dB -> linear ratio."""
    return 10.0 ** (np.asarray(db, dtype=float) / 10.0)


def linear_to_db(ratio):
    """Linear power ratio -> dB. Zero maps to -inf (no path), never to an error."""
    ratio = np.asarray(ratio, dtype=float)
    with np.errstate(divide="ignore"):
        return 10.0 * np.log10(ratio)


def dbm_to_watt(dbm):
    return 10.0 ** ((np.asarray(dbm, dtype=float) - 30.0) / 10.0)


def watt_to_dbm(watt):
    return linear_to_db(watt) + 30.0


def wavelength(frequency_hz):
    return SPEED_OF_LIGHT / np.asarray(frequency_hz, dtype=float)


def free_space_path_gain(distance_m, frequency_hz):
    """Friis: (lambda / (4*pi*d))**2 between isotropic antennas."""
    d = np.asarray(distance_m, dtype=float)
    return (wavelength(frequency_hz) / (4.0 * np.pi * d)) ** 2


def free_space_path_loss_db(distance_m, frequency_hz):
    return -linear_to_db(free_space_path_gain(distance_m, frequency_hz))


def thermal_noise_watt(bandwidth_hz, temperature_k: float = T0_KELVIN):
    """k*T*B, before the receiver noise figure."""
    return BOLTZMANN * temperature_k * np.asarray(bandwidth_hz, dtype=float)


def noise_power_dbm(bandwidth_hz, noise_figure_db: float = 0.0,
                    temperature_k: float = T0_KELVIN):
    """Receiver noise power: k*T*B plus the noise figure."""
    return watt_to_dbm(thermal_noise_watt(bandwidth_hz, temperature_k)) + noise_figure_db
