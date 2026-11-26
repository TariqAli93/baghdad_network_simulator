"""Practical rate mapping per scenario (decision B3), read from configs/radio_system.yaml.

The Shannon bound is reported for every band. Beside it, each scenario gets the 3GPP
attenuated, truncated Shannon mapping of its technology:

    lte                     TR 36.942 Annex A Table A.1 (cap: maximum spectral efficiency)
    nr                      TR 38.921 Table 4.2.7-1 (cap: SINR_MAX)
    nr_based_candidate_6g   the NR constants (`based_on: nr`), labelled as a research
                            approximation: no 6G link-level mapping exists

A mapping may name another with `based_on`; its constants are then taken from there, never
copied, so the configuration holds each value once.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from bns.analysis.link_budget import truncated_shannon_bps

_CONSTANTS = ("alpha", "sinr_min_db", "sinr_max_db", "thr_max_bps_hz")


@dataclass(frozen=True)
class RateModel:
    key: str
    label: str
    alpha: float
    sinr_min_db: float
    sinr_max_db: float | None
    thr_max_bps_hz: float | None
    sources: tuple[str, ...]
    caveat: str | None = None
    assumptions: str | None = None

    def rate_bps(self, bandwidth_hz, sinr_linear):
        return truncated_shannon_bps(bandwidth_hz, sinr_linear, alpha=self.alpha, sinr_min_db=self.sinr_min_db,
                                     sinr_max_db=self.sinr_max_db, thr_max_bps_hz=self.thr_max_bps_hz)

    def describe(self) -> str:
        cap = (f"cap {self.thr_max_bps_hz:g} bit/s/Hz" if self.thr_max_bps_hz is not None
               else f"cap at {self.sinr_max_db:g} dB")
        return f"{self.label}: α {self.alpha:g}, from {self.sinr_min_db:g} dB, {cap}"


def _resolve(key: str, mappings: dict, seen: tuple = ()) -> dict:
    if key not in mappings:
        raise ValueError(f"Rate mapping '{key}' is not defined in rate_mappings.")
    if key in seen:
        raise ValueError(f"Rate mappings refer to each other in a loop: {' -> '.join(seen + (key,))}.")
    entry = dict(mappings[key])
    if entry.get("based_on"):
        base = _resolve(entry["based_on"], mappings, seen + (key,))
        if any(c in entry for c in _CONSTANTS):
            raise ValueError(f"Rate mapping '{key}' is based on '{entry['based_on']}' and must not repeat its constants.")
        entry.update({c: base.get(c) for c in _CONSTANTS})
        entry.setdefault("assumptions", base.get("assumptions"))
    return entry


def load(path: Path) -> dict[str, RateModel]:
    """scenario id -> RateModel; empty when the file configures no mapping."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    mappings, assignment = data.get("rate_mappings") or {}, data.get("scenario_rate_mapping") or {}
    if not mappings and not assignment:
        return {}
    out = {}
    for scenario, key in assignment.items():
        e = _resolve(key, mappings)
        if e.get("alpha") is None or e.get("sinr_min_db") is None:
            raise ValueError(f"Rate mapping '{key}' needs alpha and sinr_min_db.")
        if (e.get("sinr_max_db") is None) == (e.get("thr_max_bps_hz") is None):
            raise ValueError(f"Rate mapping '{key}' needs exactly one cap: sinr_max_db or thr_max_bps_hz.")
        if not e.get("sources"):
            raise ValueError(f"Rate mapping '{key}' needs sources (docs/references.md IDs).")
        out[scenario] = RateModel(
            key=key, label=e.get("name", key), alpha=float(e["alpha"]), sinr_min_db=float(e["sinr_min_db"]),
            sinr_max_db=None if e.get("sinr_max_db") is None else float(e["sinr_max_db"]),
            thr_max_bps_hz=None if e.get("thr_max_bps_hz") is None else float(e["thr_max_bps_hz"]),
            sources=tuple(e["sources"]), caveat=e.get("caveat"), assumptions=e.get("assumptions"))
    return out


def approval(path: Path) -> tuple[str, str | None]:
    """(status, approved_by) of the rate mappings as a whole."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data.get("rate_mapping_status", "undecided"), data.get("rate_mapping_approved_by")
