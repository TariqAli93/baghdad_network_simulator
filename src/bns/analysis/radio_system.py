"""Radio-system parameters and who has decided them.

Transmit power, antenna gains, noise figure, thresholds and targets are not in
the project description, so they are decisions for the supervisor. Each one is
stored in configs/radio_system.yaml with a status:

    undecided    no value; any calculation that needs it stops with an error
    provisional  a documented value that has not been approved; usable, but
                 every result computed with it must be labelled provisional
    approved     approved by the supervisor (the source says when and by whom)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PARAMETERS = (
    "tx_power_dbm",
    "tx_antenna_gain_dbi",
    "rx_antenna_gain_dbi",
    "noise_figure_db",
    "coverage_threshold_dbm",
    "coverage_target",
    "interference_activity",
    "antenna_height_above_roof_m",
)
STATUSES = ("undecided", "provisional", "approved")


class UndecidedParameter(RuntimeError):
    """A calculation needs a radio-system parameter nobody has decided yet."""


@dataclass(frozen=True)
class RadioSystem:
    entries: dict

    @classmethod
    def load(cls, path: Path) -> "RadioSystem":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        entries = data.get("parameters") or {}
        for name, entry in entries.items():
            if name not in PARAMETERS:
                raise ValueError(f"Unknown radio-system parameter '{name}'.")
            status, value = entry.get("status"), entry.get("value")
            if status not in STATUSES:
                raise ValueError(f"{name}: status must be one of {STATUSES}.")
            if status == "undecided" and value is not None:
                raise ValueError(f"{name}: an undecided parameter must not carry a value.")
            if status != "undecided" and (value is None or not entry.get("source")):
                raise ValueError(f"{name}: a {status} parameter needs a value and a source.")
        return cls(entries)

    def _status(self, name: str) -> str:
        if name not in PARAMETERS:
            raise KeyError(f"Unknown radio-system parameter '{name}'.")
        return self.entries.get(name, {}).get("status", "undecided")

    def require(self, name: str, scenario: str | None = None) -> float:
        """The value of a parameter, or an error naming it if it is undecided."""
        if self._status(name) == "undecided":
            raise UndecidedParameter(
                f"{name} has not been decided. See docs/supervisor-decisions.md, then set it in "
                "configs/radio_system.yaml with status 'provisional' or 'approved' and a source.")
        value = self.entries[name]["value"]
        if isinstance(value, dict):
            if scenario is None:
                raise ValueError(f"{name} is set per scenario; say which scenario.")
            return float(value[scenario])
        return float(value)

    def provisional_parameters(self) -> list[str]:
        return [n for n in PARAMETERS if self._status(n) == "provisional"]

    def approved_parameters(self) -> list[str]:
        return [n for n in PARAMETERS if self._status(n) == "approved"]
