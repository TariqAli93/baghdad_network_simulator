"""Scientific classification of a simulation result: three separate states and the result class.

    configuration  Research Baseline | Custom Experiment | Sensitivity Analysis | Not recorded
    dataset        Complete data (fit for research) | Incomplete data
    validation     Validated | Validation Pending

The result class follows from the three, and is never better than the evidence:

    Validated Research Results            baseline configuration, complete data, validated
    Research Baseline · Validation Pending  baseline configuration, complete data, not yet validated
    Custom Experiment / Sensitivity Analysis  other values on complete data
    Preliminary Simulation                any run on incomplete data, or a run whose configuration
                                          was not recorded (runs before 2026-11-27)

"Validated" needs the convergence on the final scene and a MATLAB comparison that meets the B1
criterion (bns.analysis.readiness). Nothing here concerns approvals: the supervisor approved the
research baseline; these classes describe what a result is, scientifically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

BASELINE, CUSTOM, SENSITIVITY = "Research Baseline", "Custom Experiment", "Sensitivity Analysis"
NOT_RECORDED = "Configuration not recorded"
COMPLETE, INCOMPLETE = "Complete data", "Incomplete data"
VALIDATED, PENDING = "Validated", "Validation Pending"
PRELIMINARY, VALIDATED_RESULTS = "Preliminary Simulation", "Validated Research Results"
# parameters whose variation is a sensitivity analysis of the baseline (threshold, target, load,
# rain: the approved sensitivity dimensions); changing anything else is a custom experiment
SENSITIVITY_KEYS = frozenset({"coverage_threshold", "coverage_target", "interference_activity", "rain_rate_mm_h"})


@dataclass(frozen=True)
class Classification:
    configuration: str
    dataset: str
    validation: str

    @property
    def result(self) -> str:
        if self.dataset != COMPLETE or self.configuration == NOT_RECORDED:
            return PRELIMINARY
        if self.configuration != BASELINE:
            return self.configuration
        return VALIDATED_RESULTS if self.validation == VALIDATED else f"{BASELINE} · {PENDING}"

    @property
    def label(self) -> str:
        parts = [self.result] + [s for s in (self.configuration, self.dataset, self.validation)
                                 if s not in self.result]
        return " · ".join(parts)

    @property
    def validated(self) -> bool:
        return self.result == VALIDATED_RESULTS

    @property
    def details(self) -> str:
        """'Configuration: … · Dataset: … · Validation: …' for banners and report headers."""
        config = "not recorded (run before 2026-11-27)" if self.configuration == NOT_RECORDED else self.configuration
        return f"Configuration: {config} · Dataset: {self.dataset} · Validation: {self.validation}"

    def as_dict(self) -> dict:
        return {**asdict(self), "result": self.result}


def configuration_class(overrides: dict | None) -> str:
    if not overrides:
        return BASELINE
    return SENSITIVITY if set(overrides) <= SENSITIVITY_KEYS else CUSTOM


def dataset_class(quality: dict | None) -> str:
    return COMPLETE if (quality or {}).get("fit_for_research") else INCOMPLETE


def validation_class(root: Path) -> str:
    from bns.analysis import readiness

    found = {i.id: i.state for i in readiness.validation_indicators(root)}
    return VALIDATED if all(s == readiness.COMPLETED for s in found.values()) else PENDING


def classify(root: Path, overrides: dict | None, quality: dict | None) -> Classification:
    return Classification(configuration_class(overrides), dataset_class(quality), validation_class(root))


# labels written into run files before 2026-11-27; the files keep them (provenance), displays and new
# reports show the scientific class instead
HISTORICAL_LABELS = ("DEVELOPMENT — NOT APPROVED FOR RESEARCH", "DEVELOPMENT - NOT APPROVED FOR RESEARCH",
                     "APPROVED RESEARCH CONFIGURATION")


def display_text(text: str) -> str:
    """Saved text with historical approval labels replaced by the result class they stand for."""
    for old in HISTORICAL_LABELS:
        text = text.replace(old, PRELIMINARY)
    return text


def from_manifest(manifest: dict) -> Classification:
    """The classification a run recorded; for runs before 2026-11-27 (none recorded): configuration not
    recorded, dataset from the recorded fitness, validation pending -> Preliminary Simulation."""
    rec = manifest.get("classification")
    if rec:
        return Classification(rec["configuration"], rec["dataset"], rec["validation"])
    area = manifest.get("area") or {}
    return Classification(NOT_RECORDED, COMPLETE if area.get("fit_for_research") else INCOMPLETE, PENDING)
