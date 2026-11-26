"""Closed-form references the ray tracer is checked against.

Nothing here depends on the ray-tracing engine. Each function states the
physical model it implements so a mismatch with the engine can be traced to
either the model or the engine.

Sources (IDs in docs/references.md):
    ITU-P2040  Rec. ITU-R P.2040-4: concrete, Table 3; Fresnel coefficients,
               eqs (37a) TE and (37b) TM; single-layer slab, eqs (43a) and (44).
    ITU-P526   Rec. ITU-R P.526-16: knife edge, exact eq (30) and
               approximation J(nu) eq (31); nu defined in eq (26).
"""

from __future__ import annotations

import numpy as np
from scipy.special import fresnel as _fresnel_integrals

from bns.core.units import free_space_path_gain, wavelength

EPSILON_0 = 8.8541878128e-12  # F/m

# ITU-R P.2040 concrete, valid 1-100 GHz: eps_r = a, sigma = c * f_GHz**d  [S/m]
_CONCRETE_EPS_R = 5.24
_CONCRETE_SIGMA_C = 0.0462
_CONCRETE_SIGMA_D = 0.7822


def itu_concrete_permittivity(frequency_hz: float) -> complex:
    """Complex relative permittivity of ITU-R P.2040 concrete: eps_r - j*sigma/(eps0*omega)."""
    f_ghz = frequency_hz / 1e9
    if not 1.0 <= f_ghz <= 100.0:
        raise ValueError("ITU-R P.2040 concrete is defined for 1-100 GHz only.")
    sigma = _CONCRETE_SIGMA_C * f_ghz**_CONCRETE_SIGMA_D
    return complex(_CONCRETE_EPS_R, -sigma / (EPSILON_0 * 2.0 * np.pi * frequency_hz))


def fresnel_half_space(theta, eta: complex, polarization: str):
    """Fresnel reflection coefficient of an infinitely thick medium.

    theta is the angle of incidence measured from the surface normal [rad].
    polarization: "TE" (E-field perpendicular to the plane of incidence) or
    "TM" (E-field in the plane of incidence).
    """
    cos_t = np.cos(theta)
    s = np.sqrt(eta - np.sin(theta) ** 2 + 0j)
    if polarization == "TE":
        return (cos_t - s) / (cos_t + s)
    if polarization == "TM":
        return (eta * cos_t - s) / (eta * cos_t + s)
    raise ValueError("polarization must be 'TE' or 'TM'")


def fresnel_slab(theta, eta: complex, thickness_m: float, frequency_hz: float,
                 polarization: str):
    """Reflection coefficient of a single-layer slab with air on both sides.

    ITU-R P.2040 slab formula: R' = R*(1 - e^{-j2q}) / (1 - R^2 * e^{-j2q}),
    q = (2*pi*d/lambda) * sqrt(eta - sin^2(theta)).
    """
    r = fresnel_half_space(theta, eta, polarization)
    s = np.sqrt(eta - np.sin(theta) ** 2 + 0j)
    q = 2.0 * np.pi * thickness_m / wavelength(frequency_hz) * s
    e = np.exp(-2j * q)
    return r * (1.0 - e) / (1.0 - r**2 * e)


def two_ray_noncoherent_gain(ground_distance_m, h_tx_m: float, h_rx_m: float,
                             frequency_hz: float, eta: complex, thickness_m: float,
                             polarization: str):
    """Direct ray plus one ground reflection, powers added (no phase).

    G = (lambda/4pi)^2 * [1/d1^2 + |R(theta)|^2 / d2^2]
    This is what a non-coherent radio map should return over a flat ground.
    A vertically polarized antenna over horizontal ground is the TM case.
    """
    rho = np.asarray(ground_distance_m, dtype=float)
    d1 = np.sqrt(rho**2 + (h_tx_m - h_rx_m) ** 2)
    d2 = np.sqrt(rho**2 + (h_tx_m + h_rx_m) ** 2)
    theta = np.arctan2(rho, h_tx_m + h_rx_m)
    r = fresnel_slab(theta, eta, thickness_m, frequency_hz, polarization)
    lam = wavelength(frequency_hz)
    return (lam / (4.0 * np.pi)) ** 2 * (1.0 / d1**2 + np.abs(r) ** 2 / d2**2)


def cell_average(func, x_centers, y_centers, cell_size_m: float, n_sub: int = 8):
    """Average func(x, y) over each square cell using n_sub x n_sub sub-samples.

    Returns an array of shape [len(y_centers), len(x_centers)]. A radio map
    reports the mean over the cell, which differs from the centre value close
    to the transmitter.
    """
    offsets = (np.arange(n_sub) + 0.5) / n_sub - 0.5
    total = np.zeros((len(y_centers), len(x_centers)))
    xs = np.asarray(x_centers, dtype=float)[None, :]
    ys = np.asarray(y_centers, dtype=float)[:, None]
    for oy in offsets:
        for ox in offsets:
            total += func(xs + ox * cell_size_m, ys + oy * cell_size_m)
    return total / n_sub**2


def cell_averaged_friis(tx_xyz, x_centers, y_centers, z_rx_m: float,
                        cell_size_m: float, frequency_hz: float, n_sub: int = 8):
    """Free-space path gain averaged over each cell of a horizontal grid."""
    tx, ty, tz = tx_xyz

    def gain(x, y):
        d = np.sqrt((x - tx) ** 2 + (y - ty) ** 2 + (z_rx_m - tz) ** 2)
        return free_space_path_gain(d, frequency_hz)

    return cell_average(gain, x_centers, y_centers, cell_size_m, n_sub)


# --- Antenna pattern reference ----------------------------------------------------


def _rotation(orientation_rad) -> np.ndarray:
    """3GPP TR 38.901 eq. (7.1-1): LCS -> GCS for bearing alpha, downtilt beta, slant gamma."""
    a, b, c = orientation_rad
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    rx = np.array([[1, 0, 0], [0, np.cos(c), -np.sin(c)], [0, np.sin(c), np.cos(c)]])
    return rz @ ry @ rx


def tr38901_element_gain_dbi(direction_gcs, orientation_rad=(0.0, 0.0, 0.0)) -> float:
    """Gain of the 3GPP TR 38.901 Table 7.3-1 element towards a direction, in dBi.

    Vertical cut -min(12((theta-90)/65)^2, 30), horizontal cut -min(12(phi/65)^2, 30),
    combined as -min(-(A_V + A_H), 30), plus 8 dBi maximum gain. theta is the zenith
    and phi the azimuth angle in the antenna's own frame; a positive downtilt points
    the boresight below the horizon.
    """
    d = np.asarray(direction_gcs, dtype=float)
    local = _rotation(orientation_rad).T @ (d / np.linalg.norm(d))
    theta = np.degrees(np.arccos(np.clip(local[2], -1.0, 1.0)))
    phi = np.degrees(np.arctan2(local[1], local[0]))
    a_v = -min(12.0 * ((theta - 90.0) / 65.0) ** 2, 30.0)
    a_h = -min(12.0 * (phi / 65.0) ** 2, 30.0)
    return 8.0 - min(-(a_v + a_h), 30.0)


# --- Diffraction references -------------------------------------------------------


def edge_path_lengths(tx_xyz, rx_xyz, edge_x: float, edge_z: float):
    """Shortest TX -> edge -> RX path for a straight edge parallel to the y axis.

    Returns (diffracted_length, direct_length). The diffraction point follows
    from unfolding the two half-planes around the edge (Fermat's principle).
    """
    tx, ty, tz = (np.asarray(v, dtype=float) for v in tx_xyz)
    rx, ry, rz = (np.asarray(v, dtype=float) for v in rx_xyz)
    s1 = np.hypot(edge_x - tx, edge_z - tz)
    s2 = np.hypot(rx - edge_x, rz - edge_z)
    diffracted = np.sqrt((s1 + s2) ** 2 + (ry - ty) ** 2)
    direct = np.sqrt((rx - tx) ** 2 + (ry - ty) ** 2 + (rz - tz) ** 2)
    return diffracted, direct


def fresnel_nu(diffracted_length, direct_length, frequency_hz: float, in_shadow=True):
    """Fresnel-Kirchhoff parameter from the excess path: nu = 2*sqrt(delta/lambda)."""
    delta = np.maximum(np.asarray(diffracted_length) - np.asarray(direct_length), 0.0)
    nu = 2.0 * np.sqrt(delta / wavelength(frequency_hz))
    return np.where(in_shadow, nu, -nu)


def knife_edge_gain(nu):
    """Power relative to free space behind an absorbing knife edge (exact Fresnel integral).

    |F(nu)|^2 = 0.5 * [(0.5 - C(nu))^2 + (0.5 - S(nu))^2]; equals 1/4 (-6.02 dB)
    on the shadow boundary nu = 0. It ignores material and polarization, so it
    is an envelope for a real wedge, not an exact prediction.
    """
    s, c = _fresnel_integrals(np.asarray(nu, dtype=float))
    return 0.5 * ((0.5 - c) ** 2 + (0.5 - s) ** 2)


def knife_edge_loss_db_p526(nu):
    """ITU-R P.526 approximation J(nu), valid for nu > -0.78 (0 dB below that)."""
    nu = np.asarray(nu, dtype=float)
    j = 6.9 + 20.0 * np.log10(np.sqrt((nu - 0.1) ** 2 + 1.0) + nu - 0.1)
    return np.where(nu > -0.78, j, 0.0)
