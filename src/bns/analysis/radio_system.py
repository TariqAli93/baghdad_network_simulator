"""Radio-system parameters, their approval state, and the run mode that may use them.

Each parameter in configs/radio_system.yaml has a state:

    undecided    no value; any calculation that needs it stops with an error
    development  a value for software testing only; must say why, needs no source
    candidate    a sourced value proposed for research, awaiting supervisor approval
    approved     approved by the supervisor (approved_by says who and when)

A run is either in "development" mode (any value except undecided; every output
is labelled DEVELOPMENT - NOT APPROVED FOR RESEARCH) or in "research" mode (only
approved values; anything else stops the run).

Transmit power is declared as conducted power (at the antenna port, before the
antenna gain) or as EIRP (gain already included). An antenna gain may be given
only with conducted power, so a gain can never be counted twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PARAMETERS = (
    "tx_power_dbm",                 # with definition: conducted | eirp
    "tx_antenna_gain_dbi",          # only with conducted power
    "tx_antenna_pattern",           # as traced; "iso" radiates the EIRP equally in all directions
    "sectors_per_site",             # one traced transmitter per sector, evenly spaced in azimuth
    "mechanical_downtilt_deg",      # positive = boresight below the horizon
    "antenna_height_above_roof_m",
    "rx_height_m",
    "rx_antenna_gain_dbi",
    "noise_figure_db",
    "noise_temperature_k",
    "coverage_threshold",           # with definition: rx_power_dbm | snr_db
    "coverage_target",
    "frequency_reuse",
    "interference_activity",        # 1.0 = every other site transmits all the time (full load)
)
STATES = ("undecided", "development", "candidate", "approved")
MODES = ("development", "research")
DEVELOPMENT_LABEL = "DEVELOPMENT — NOT APPROVED FOR RESEARCH"
RESEARCH_LABEL = "APPROVED RESEARCH CONFIGURATION"
_DEFINITIONS = {"tx_power_dbm": ("conducted", "eirp"),
                "coverage_threshold": ("rx_power_dbm", "snr_db")}
# Peak gain of the patterns the ray tracer can apply (Sionna RT 2.2.0). "tr38901" is the
# 3GPP TR 38.901 Table 7.3-1 element: 65 degree beamwidth, 8 dBi maximum.
PATTERN_PEAK_GAIN_DBI = {"iso": 0.0, "tr38901": 8.0}


class UndecidedParameter(RuntimeError):
    """A calculation needs a radio-system parameter nobody has decided yet."""


class UnapprovedParameter(RuntimeError):
    """A research run needs a parameter that the supervisor has not approved."""


@dataclass(frozen=True)
class RadioSystem:
    entries: dict

    @classmethod
    def load(cls, path: Path) -> "RadioSystem":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        entries = data.get("parameters") or {}
        for name, e in entries.items():
            if name not in PARAMETERS:
                raise ValueError(f"Unknown radio-system parameter '{name}'.")
            state, value = e.get("status"), e.get("value")
            if state not in STATES:
                raise ValueError(f"{name}: status must be one of {STATES}.")
            if state == "undecided":
                if value is not None:
                    raise ValueError(f"{name}: an undecided parameter must not carry a value.")
                continue
            if value is None:
                raise ValueError(f"{name}: a {state} parameter needs a value.")
            if state == "development" and not e.get("justification"):
                raise ValueError(f"{name}: a development value must say why it is used.")
            if state in ("candidate", "approved") and not e.get("sources"):
                raise ValueError(f"{name}: a {state} value needs sources (docs/references.md IDs).")
            if state == "approved" and not e.get("approved_by"):
                raise ValueError(f"{name}: an approved value must say who approved it and when.")
            if name in _DEFINITIONS and e.get("definition") not in _DEFINITIONS[name]:
                raise ValueError(f"{name}: definition must be one of {_DEFINITIONS[name]}.")
        power, gain = entries.get("tx_power_dbm", {}), entries.get("tx_antenna_gain_dbi", {})
        pattern = entries.get("tx_antenna_pattern", {}).get("value")
        if power.get("definition") == "eirp" and gain.get("status", "undecided") != "undecided":
            raise ValueError("tx_power_dbm is an EIRP, which already includes the antenna gain; "
                             "giving tx_antenna_gain_dbi as well would count it double.")
        if pattern not in (None, "iso"):
            if power.get("definition") == "eirp":
                raise ValueError(f"The '{pattern}' pattern is traced, so its gain is already in the "
                                 "path gain; an EIRP would count it double. Give conducted power.")
            values = gain.get("value")
            values = values.values() if isinstance(values, dict) else [values]
            if any(v not in (None, 0, 0.0) for v in values):
                raise ValueError(f"The '{pattern}' pattern is traced, so its gain is already in the "
                                 "path gain; tx_antenna_gain_dbi must be 0 to avoid counting it double.")
        return cls(entries)

    def status(self, name: str) -> str:
        if name not in PARAMETERS:
            raise KeyError(f"Unknown radio-system parameter '{name}'.")
        return self.entries.get(name, {}).get("status", "undecided")

    def require(self, name: str, scenario: str | None = None, *, mode: str):
        """The value of a parameter for this run mode, or an error naming it."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}.")
        state = self.status(name)
        if state == "undecided":
            raise UndecidedParameter(
                f"{name} has not been decided (docs/supervisor-decisions.md, "
                "docs/radio-parameters.md).")
        if mode == "research" and state != "approved":
            raise UnapprovedParameter(f"{name} is '{state}', not approved; research runs need approval.")
        value = self.entries[name]["value"]
        if isinstance(value, dict):
            if scenario is None:
                raise ValueError(f"{name} is set per scenario; say which scenario.")
            value = value[scenario]
        return float(value) if isinstance(value, (int, float)) else value

    def definition(self, name: str) -> str | None:
        return self.entries.get(name, {}).get("definition")

    def tx_power_for_path_gain_dbm(self, scenario: str, *, mode: str) -> float:
        """The power to add to the traced path gain.

        Isotropic trace: conducted power plus antenna gain, or the EIRP as given
        (the isotropic model radiates it equally in all directions).
        Traced pattern: conducted power only, because the pattern's gain is
        already inside the path gain (the added gain is forced to 0 on loading).
        """
        power = self.require("tx_power_dbm", scenario, mode=mode)
        if self.definition("tx_power_dbm") == "eirp":
            return power
        return power + self.require("tx_antenna_gain_dbi", scenario, mode=mode)

    def peak_eirp_dbm(self, scenario: str, *, mode: str) -> float:
        """EIRP in the direction of maximum gain, for comparison with regulatory caps."""
        pattern = self.require("tx_antenna_pattern", mode=mode)
        return self.tx_power_for_path_gain_dbm(scenario, mode=mode) + PATTERN_PEAK_GAIN_DBI[pattern]

    def approved_parameters(self) -> list[str]:
        return [n for n in PARAMETERS if self.status(n) == "approved"]

    def label(self, used: list[str], *, mode: str) -> str:
        if mode == "research" and all(self.status(n) == "approved" for n in used):
            return RESEARCH_LABEL
        return DEVELOPMENT_LABEL

    def status_report(self, used: list[str]) -> dict:
        report = {}
        for name in used:
            e = self.entries.get(name, {})
            report[name] = {k: e.get(k) for k in ("value", "unit", "status", "definition",
                                                  "sources", "approved_by", "justification")
                            if e.get(k) is not None} | {"status": self.status(name)}
        return report
