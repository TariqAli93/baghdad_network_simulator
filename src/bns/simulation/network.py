"""A network of physical sites, each with one or more sectors, on one shared carrier.

Input is a stack of traced path-gain maps, one per SECTOR, and a map from sector
to site. The strongest sector serves each outdoor cell; every other sector
interferes, including the other sectors of the serving site (frequency reuse 1,
the candidate assumption in configs/radio_system.yaml). Interference is summed
in watts and multiplied by the interference activity factor (the share of time
the other sectors transmit, i.e. their load). There is no scheduler and no
resource sharing: the rate is the Shannon bound of one user with the whole
carrier, so adding a site changes SINR, never the share of the carrier a user gets.

Path gains are reused from the cache; nothing here traces rays.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bns.analysis import link_budget as lb
from bns.core.units import dbm_to_watt, watt_to_dbm
from bns.simulation.radio import RadioInputs, RadioResult, multi_site

INTERFERENCE_ASSUMPTION = {
    "carrier": "all sectors of all sites share one carrier (reuse 1)",
    "co_located_sectors_interfere": True,
    "interference_activity": "share of time every non-serving sector transmits; 1.0 = full load",
    "scheduling": "none; Shannon bound for one user using the whole carrier",
    "serving_rule": "strongest received sector (after antenna pattern and gas loss)",
}


@dataclass
class NetworkResult:
    radio: RadioResult                # serving index = sector; coverage, SINR and rate
    serving_sector: np.ndarray        # -1 where not served (indoor or unreached)
    serving_site: np.ndarray          # -1 where not served
    interference_dbm: np.ndarray      # after the activity factor; -inf where none
    summary: dict


def _check_sites(sector_site, n_sectors: int) -> np.ndarray:
    sector_site = np.asarray(sector_site, dtype=int)
    if sector_site.shape != (n_sectors,):
        raise ValueError(f"sector_site needs one site index per sector ({n_sectors}).")
    n_sites = int(sector_site.max()) + 1
    if sector_site.min() < 0 or set(sector_site.tolist()) != set(range(n_sites)):
        raise ValueError("Site indices must be 0..n_sites-1 and every site needs a sector.")
    return sector_site


def network(path_gain_stack, sector_site, outdoor, inputs: RadioInputs, extra_loss_db) -> NetworkResult:
    """Radio results of a multi-site, multi-sector network. Shapes: [sector, y, x]."""
    stack = np.asarray(path_gain_stack, dtype=float)
    sector_site = _check_sites(sector_site, stack.shape[0])
    outdoor = np.asarray(outdoor, dtype=bool)
    radio = multi_site(stack, outdoor, inputs, extra_loss_db)

    served = outdoor & (radio.serving >= 0)
    serving_sector = np.where(served, radio.serving, -1)
    serving_site = np.where(served, sector_site[np.maximum(radio.serving, 0)], -1)

    per_sector_dbm = lb.received_power_dbm(inputs.tx_power_dbm, stack, rx_gain_dbi=inputs.rx_gain_dbi,
                                           extra_loss_db=extra_loss_db)
    finite = np.isfinite(per_sector_dbm)
    per_sector_w = np.where(finite, dbm_to_watt(np.where(finite, per_sector_dbm, 0.0)), 0.0)
    signal_w = per_sector_w.max(axis=0)
    interference_w = inputs.interference_activity * (per_sector_w.sum(axis=0) - signal_w)
    with np.errstate(divide="ignore"):
        interference_dbm = np.where(interference_w > 0, watt_to_dbm(np.maximum(interference_w, 1e-300)),
                                    -np.inf)

    n_out = int(outdoor.sum())
    n_sites = int(sector_site.max()) + 1
    noise_w = dbm_to_watt(radio.noise_dbm)
    i_over_n = np.where(served, interference_w / noise_w, np.nan)
    summary = {
        **radio.summary,
        "sites": n_sites,
        "sectors": int(stack.shape[0]),
        "served_share_per_site": [float(((serving_site == s) & outdoor).sum() / n_out) for s in range(n_sites)],
        "served_share_per_sector": [float(((serving_sector == k) & outdoor).sum() / n_out)
                                    for k in range(stack.shape[0])],
        "interference_over_noise_db_median": (float(10 * np.log10(np.nanmedian(i_over_n)))
                                              if served.any() and np.nanmedian(i_over_n) > 0 else None),
        "interference_limited_share": float((served & (interference_w > noise_w)).sum() / n_out),
        "interference_assumption": {**INTERFERENCE_ASSUMPTION,
                                    "interference_activity_value": inputs.interference_activity},
    }
    return NetworkResult(radio, serving_sector, serving_site, interference_dbm, summary)


def sites_alone(path_gain_stack, sector_site, outdoor, inputs: RadioInputs, extra_loss_db) -> list[NetworkResult]:
    """Each site on its own (its own sectors still interfere with each other)."""
    stack = np.asarray(path_gain_stack, dtype=float)
    sector_site = _check_sites(sector_site, stack.shape[0])
    loss = np.broadcast_to(np.asarray(extra_loss_db, dtype=float), stack.shape)
    results = []
    for s in range(int(sector_site.max()) + 1):
        own = sector_site == s
        results.append(network(stack[own], np.zeros(int(own.sum()), dtype=int), outdoor, inputs, loss[own]))
    return results
