"""Carriers of an experiment: the five scenario presets and custom frequency/bandwidth variants (no UI code).

A carrier is a scenario dictionary as runs record it (id, label, frequency_hz, bandwidth_hz, status),
extended with its preset (the configs/scenarios.yaml entry it derives from), whether it differs from
that preset, and how gas loss is treated. Radio-system values and the band's rate mapping are always
looked up under the preset (a custom 8 GHz variant of the 5G preset keeps the NR mapping and is
labelled as such); only the frequency enters the ray tracer and the bandwidth the noise and rates.

What a custom carrier may be (docs/assumptions.md section 10; custom experiments only):

    frequency  inside every model the simulation applies at that frequency (supported_ranges_hz):
               the scene materials as the installed Sionna RT defines them (ITU-R P.2040; concrete
               1-100 GHz and 110-330 GHz), gas attenuation (ITU-R P.676 Annex 1: 1-1000 GHz) and the
               antenna element (3GPP TR 38.901: 0.5-100 GHz; the isotropic antenna has no limit).
               Nothing is extrapolated outside them.
    gas loss   the tabulated value at the five preset carriers (unchanged, docs/atmospheric-losses.md);
               at any other carrier ITU-R P.676 Annex 1 through ITU-Rpy, recorded in the carrier with
               the model and its versions. Runs before 2026-11-27 recorded "omitted" (no gas loss
               between 1 and 30 GHz); they are read as recorded.
    bandwidth  above 0.1 MHz and at most a quarter of the carrier frequency: path gain, materials
               and gas loss are evaluated at the centre frequency only.
"""

from __future__ import annotations

import ast
import re
from importlib.util import find_spec
from pathlib import Path

from bns.propagation import atmosphere as atm
from bns.propagation.atmosphere import GAS_DB_PER_KM

TABULATED, P676, OMITTED = "tabulated", "p676", "omitted"   # omitted: runs before 2026-11-27 only
ANTENNA_RANGES_HZ = {"tr38901": (0.5e9, 100e9)}            # 3GPP TR 38.901 scope; "iso" has no limit
MIN_BANDWIDTH_HZ = 0.1e6
MAX_BANDWIDTH_FRACTION = 0.25


class CarrierError(ValueError):
    """An unsupported carrier. `code`: frequency_range, gas_unavailable or bandwidth_range."""

    def __init__(self, code: str, message: str, **values):
        super().__init__(message)
        self.code, self.values = code, values


def _from_scenario(sc: dict) -> dict:
    return {"id": sc["id"], "label": sc["label"], "frequency_hz": float(sc["frequency_hz"]),
            "bandwidth_hz": float(sc["bandwidth_hz"]), "status": sc.get("status", ""), "preset": sc["id"],
            "custom": False, "gas": TABULATED}


def presets(root: Path) -> list[dict]:
    """The five scenario presets, by frequency (configs/scenarios.yaml)."""
    from bns.simulation.experiment import load_scenarios
    return [_from_scenario(sc) for sc in load_scenarios(root)]


def preset(root: Path, preset_id: str) -> dict:
    return next(p for p in presets(root) if p["id"] == preset_id)


def _tabulated(frequency_hz: float) -> bool:
    return any(abs(frequency_hz - f) <= 1e-6 * f for f in GAS_DB_PER_KM)


def _mhz(value_hz: float) -> str:
    return f"{value_hz / 1e6:.6g}".replace(".", "p")


def _itu_table() -> dict:
    """Sionna RT's ITU-R P.2040 material table, read from its source without importing the engine
    (importing sionna.rt needs bns.runtime.init and a worker process)."""
    spec = find_spec("sionna")
    path = Path(next(iter(spec.submodule_search_locations))) / "rt" / "radio_materials" / "itu.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ITU_MATERIALS_PROPERTIES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"No ITU material table in {path}.")


def material_ranges_hz(scene_dir: Path) -> list[tuple[float, float]]:
    """Frequency intervals in which every ITU material of the scene is defined (a material may have
    several, e.g. concrete 1-100 GHz and 110-330 GHz)."""
    xml = (Path(scene_dir) / "scene.xml").read_text(encoding="utf-8")
    names = set(re.findall(r'type="itu-radio-material"[^>]*>\s*<string name="type" value="([^"]+)"', xml))
    if not names:
        raise CarrierError("frequency_range", "The scene names no ITU radio material.")
    table = _itu_table()
    common = [(0.0, float("inf"))]
    for name in sorted(names):
        own = [(r[0] * 1e9, r[1] * 1e9) for r in table[name]]
        common = [(max(a, c), min(b, d)) for a, b in common for c, d in own if max(a, c) <= min(b, d)]
    return sorted(common)


def _intersect(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return sorted((max(x, u), min(y, v)) for x, y in a for u, v in b if max(x, u) <= min(y, v))


def supported_ranges_hz(scene_dir: Path, patterns=("tr38901",)) -> list[tuple[float, float]]:
    """Frequency intervals where every model applied at the carrier is defined: the scene's materials
    (Sionna RT), gas attenuation (ITU-R P.676 Annex 1) and the antenna patterns in use."""
    ranges = _intersect(material_ranges_hz(scene_dir), [atm.P676_RANGE_HZ])
    for pattern in set(patterns):
        if pattern in ANTENNA_RANGES_HZ:
            ranges = _intersect(ranges, [ANTENNA_RANGES_HZ[pattern]])
    return ranges


def customize(base: dict, *, frequency_hz: float, bandwidth_hz: float, scene_dir: Path,
              patterns=("tr38901",)) -> dict:
    """The carrier `base` with another frequency and/or bandwidth, or the preset itself if both are its
    values. Unsupported values are refused (CarrierError), never adjusted. `patterns`: the antenna
    patterns of the stations that will transmit on it."""
    f, b = float(frequency_hz), float(bandwidth_hz)
    root_preset = {**base, "frequency_hz": base.get("preset_frequency_hz", base["frequency_hz"]),
                   "bandwidth_hz": base.get("preset_bandwidth_hz", base["bandwidth_hz"])}
    pf, pb = float(root_preset["frequency_hz"]), float(root_preset["bandwidth_hz"])
    ranges = supported_ranges_hz(scene_dir, patterns)
    if not any(lo <= f <= hi for lo, hi in ranges):
        valid = ", ".join(f"{lo / 1e9:g}-{hi / 1e9:g}" for lo, hi in ranges)
        raise CarrierError("frequency_range", f"{f / 1e9:g} GHz is outside {valid} GHz, where the scene's materials "
                           "(ITU-R P.2040 in Sionna RT), gas attenuation (ITU-R P.676) and the antenna model are "
                           "defined.", f=f"{f / 1e9:g}", ranges=valid)
    tabulated = _tabulated(f)
    gas = {}
    if not tabulated:
        try:
            gas = {"gas_db_per_km": round(atm.gas_specific_attenuation_p676_db_per_km(f), 6),
                   "gas_model": atm.gas_model()}
        except Exception as exc:                    # ITU-Rpy missing or failing: refuse, never guess
            raise CarrierError("gas_unavailable", f"Gas attenuation at {f / 1e9:g} GHz cannot be computed: {exc}",
                               f=f"{f / 1e9:g}") from exc
    if not MIN_BANDWIDTH_HZ <= b <= MAX_BANDWIDTH_FRACTION * f:
        raise CarrierError("bandwidth_range", f"{b / 1e6:g} MHz is outside {MIN_BANDWIDTH_HZ / 1e6:g} MHz to "
                           f"{MAX_BANDWIDTH_FRACTION * f / 1e6:g} MHz (a quarter of the carrier).",
                           b=f"{b / 1e6:g}", lo=f"{MIN_BANDWIDTH_HZ / 1e6:g}",
                           hi=f"{MAX_BANDWIDTH_FRACTION * f / 1e6:g}")
    if abs(f - pf) <= 1e-6 * pf and abs(b - pb) <= 1e-6 * pb:
        return _from_scenario({**root_preset, "id": root_preset["preset"]})
    return {"id": f"{root_preset['preset']}.f{_mhz(f)}b{_mhz(b)}", "label": root_preset["label"], "frequency_hz": f,
            "bandwidth_hz": b, "status": root_preset["status"], "preset": root_preset["preset"], "custom": True,
            "gas": TABULATED if tabulated else P676, **gas, "preset_frequency_hz": pf, "preset_bandwidth_hz": pb}


def equal_bandwidth(carriers: list[dict], bandwidth_hz: float, scene_dir: Path, patterns=("tr38901",)) -> list[dict]:
    """Every carrier with the same bandwidth (a controlled equal-bandwidth comparison)."""
    return [customize(c, frequency_hz=c["frequency_hz"], bandwidth_hz=bandwidth_hz, scene_dir=scene_dir,
                      patterns=patterns) for c in carriers]


def radio_scenario(root: Path, carrier: dict) -> dict:
    """The scenario under which radio values and the rate mapping are looked up: the preset, with the
    carrier's bandwidth."""
    return {**preset(root, carrier["preset"]), "bandwidth_hz": float(carrier["bandwidth_hz"])}


def gas_db_per_km(carrier: dict) -> float:
    """Sea-level gas attenuation of the carrier: tabulated, computed with ITU-R P.676 (the recorded value),
    or 0 where a run before 2026-11-27 recorded it as omitted."""
    if carrier.get("gas") == OMITTED:
        return 0.0
    if carrier.get("gas") == P676:
        return float(carrier["gas_db_per_km"])
    for f, value in GAS_DB_PER_KM.items():
        if abs(carrier["frequency_hz"] - f) <= 1e-6 * f:
            return value
    raise CarrierError("gas_unavailable", f"No gas attenuation for {carrier['frequency_hz'] / 1e9:g} GHz.")


def deviations(carriers: list[dict]) -> list[str]:
    """How the carriers depart from their presets (English, recorded in the classification)."""
    out = []
    for c in carriers:
        if c.get("custom"):
            out.append(f"carrier {c['preset']}: {c['frequency_hz'] / 1e9:g} GHz / {c['bandwidth_hz'] / 1e6:g} MHz "
                       f"(preset {c['preset_frequency_hz'] / 1e9:g} GHz / {c['preset_bandwidth_hz'] / 1e6:g} MHz)")
        if c.get("gas") == OMITTED:
            out.append(f"gas attenuation not included at {c['frequency_hz'] / 1e9:g} GHz (not tabulated)")
        elif c.get("gas") == P676:
            model = c.get("gas_model") or {}
            out.append(f"gas attenuation at {c['frequency_hz'] / 1e9:g} GHz: {c['gas_db_per_km']:g} dB/km, "
                       f"{model.get('recommendation', 'ITU-R P.676')} ({model.get('implementation', 'ITU-Rpy')})")
    return out
