"""Carriers of an experiment: the five scenario presets and custom frequency/bandwidth variants (no UI code).

A carrier is a scenario dictionary as runs record it (id, label, frequency_hz, bandwidth_hz, status),
extended with its preset (the configs/scenarios.yaml entry it derives from), whether it differs from
that preset, and how gas loss is treated. Radio-system values and the band's rate mapping are always
looked up under the preset (a custom 8 GHz variant of the 5G preset keeps the NR mapping and is
labelled as such); only the frequency enters the ray tracer and the bandwidth the noise and rates.

What a custom carrier may be (docs/assumptions.md, A-custom-carriers; custom experiments only):

    frequency  inside the validity range of every material in the scene, as the installed Sionna RT
               defines it (ITU-R P.2040; concrete: 1-100 GHz), and gas loss must be available:
               tabulated (the five preset carriers, docs/atmospheric-losses.md) or, between 1 and
               30 GHz, omitted and recorded (at most about 0.19 dB/km there, the 22.2 GHz water-vapour
               line). Above 30 GHz an untabulated carrier is refused: near 60 GHz oxygen absorbs about
               15 dB/km and the project has no model to compute it.
    bandwidth  above 0.1 MHz and at most a quarter of the carrier frequency: path gain, materials
               and gas loss are evaluated at the centre frequency only.
"""

from __future__ import annotations

import ast
import re
from importlib.util import find_spec
from pathlib import Path

from bns.propagation.atmosphere import GAS_DB_PER_KM

TABULATED, OMITTED = "tabulated", "omitted"
GAS_OMISSION_MAX_HZ = 30e9
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


def customize(base: dict, *, frequency_hz: float, bandwidth_hz: float, scene_dir: Path) -> dict:
    """The carrier `base` with another frequency and/or bandwidth, or the preset itself if both are its
    values. Unsupported values are refused (CarrierError), never adjusted."""
    f, b = float(frequency_hz), float(bandwidth_hz)
    root_preset = {**base, "frequency_hz": base.get("preset_frequency_hz", base["frequency_hz"]),
                   "bandwidth_hz": base.get("preset_bandwidth_hz", base["bandwidth_hz"])}
    pf, pb = float(root_preset["frequency_hz"]), float(root_preset["bandwidth_hz"])
    ranges = material_ranges_hz(scene_dir)
    if not any(lo <= f <= hi for lo, hi in ranges):
        valid = ", ".join(f"{lo / 1e9:g}-{hi / 1e9:g}" for lo, hi in ranges)
        raise CarrierError("frequency_range", f"{f / 1e9:g} GHz is outside {valid} GHz, where the scene's materials "
                           "are defined (ITU-R P.2040 in Sionna RT).", f=f"{f / 1e9:g}", ranges=valid)
    tabulated = _tabulated(f)
    if not tabulated and f > GAS_OMISSION_MAX_HZ:
        raise CarrierError("gas_unavailable", f"Gas attenuation is not tabulated for {f / 1e9:g} GHz and cannot be "
                           f"neglected above {GAS_OMISSION_MAX_HZ / 1e9:g} GHz.", f=f"{f / 1e9:g}",
                           max=f"{GAS_OMISSION_MAX_HZ / 1e9:g}")
    if not MIN_BANDWIDTH_HZ <= b <= MAX_BANDWIDTH_FRACTION * f:
        raise CarrierError("bandwidth_range", f"{b / 1e6:g} MHz is outside {MIN_BANDWIDTH_HZ / 1e6:g} MHz to "
                           f"{MAX_BANDWIDTH_FRACTION * f / 1e6:g} MHz (a quarter of the carrier).",
                           b=f"{b / 1e6:g}", lo=f"{MIN_BANDWIDTH_HZ / 1e6:g}",
                           hi=f"{MAX_BANDWIDTH_FRACTION * f / 1e6:g}")
    if abs(f - pf) <= 1e-6 * pf and abs(b - pb) <= 1e-6 * pb:
        return _from_scenario({**root_preset, "id": root_preset["preset"]})
    return {"id": f"{root_preset['preset']}.f{_mhz(f)}b{_mhz(b)}", "label": root_preset["label"], "frequency_hz": f,
            "bandwidth_hz": b, "status": root_preset["status"], "preset": root_preset["preset"], "custom": True,
            "gas": TABULATED if tabulated else OMITTED, "preset_frequency_hz": pf, "preset_bandwidth_hz": pb}


def equal_bandwidth(carriers: list[dict], bandwidth_hz: float, scene_dir: Path) -> list[dict]:
    """Every carrier with the same bandwidth (a controlled equal-bandwidth comparison)."""
    return [customize(c, frequency_hz=c["frequency_hz"], bandwidth_hz=bandwidth_hz, scene_dir=scene_dir)
            for c in carriers]


def radio_scenario(root: Path, carrier: dict) -> dict:
    """The scenario under which radio values and the rate mapping are looked up: the preset, with the
    carrier's bandwidth."""
    return {**preset(root, carrier["preset"]), "bandwidth_hz": float(carrier["bandwidth_hz"])}


def gas_db_per_km(carrier: dict) -> float:
    """Sea-level gas attenuation of the carrier: tabulated, or 0 where it is omitted (recorded)."""
    if carrier.get("gas") == OMITTED:
        return 0.0
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
    return out
