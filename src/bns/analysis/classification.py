"""Scientific classification of a simulation result: three separate states and the result class.

    configuration  Research Baseline | Custom Experiment | Sensitivity Analysis | not recorded
    dataset        Complete data | Estimated heights | Incomplete data
    validation     Validation Completed | Validation Pending

The result class follows from the three, and is never better than the evidence:

    Validated Research Results              baseline configuration, complete data, validation completed
    Research Baseline · Validation Pending  baseline configuration, complete data, validation pending
    Custom Experiment / Sensitivity Analysis  other values or settings on complete data
    Preliminary Simulation                  estimated or incomplete data, or a configuration that was not
                                            recorded (runs before 2026-11-27)

None of this decides whether a run may execute: any technically valid simulation runs, and the
classification says what its result is. The research baseline is the approved configuration
(values in configs/, the standard profile, the CPU backend, the site rule); a run that departs
from it in any way records the deviations and is a custom experiment (or a sensitivity analysis
when only the threshold, target, load or rain differ). "Completed" validation needs the
convergence on the final scene and a MATLAB comparison meeting the B1 criterion
(bns.analysis.readiness).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BASELINE, CUSTOM, SENSITIVITY = "Research Baseline", "Custom Experiment", "Sensitivity Analysis"
NOT_RECORDED = "Configuration not recorded"
COMPLETE, ESTIMATED, INCOMPLETE = "Complete data", "Estimated heights", "Incomplete data"
VALIDATED, PENDING = "Validation Completed", "Validation Pending"
PRELIMINARY, VALIDATED_RESULTS = "Preliminary Simulation", "Validated Research Results"
# parameters whose variation is a sensitivity analysis of the baseline (threshold, target, load,
# rain: the approved sensitivity dimensions); changing anything else is a custom experiment
SENSITIVITY_KEYS = frozenset({"coverage_threshold", "coverage_target", "interference_activity", "rain_rate_mm_h"})
_OLD_VALIDATION = {"Validated": VALIDATED}           # spelling of the first records (2026-11-27)


@dataclass(frozen=True)
class Classification:
    configuration: str
    dataset: str
    validation: str
    deviations: tuple[str, ...] = field(default=())     # how the configuration departs from the baseline

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
    def details(self) -> str:
        """'Configuration: … · Dataset: … · Validation: …' for banners and report headers."""
        config = "not recorded (run before 2026-11-27)" if self.configuration == NOT_RECORDED else self.configuration
        if self.deviations:
            config += f" ({'; '.join(self.deviations)})"
        validation = "completed" if self.validation == VALIDATED else "pending"
        return f"Configuration: {config} · Dataset: {self.dataset} · Validation: {validation}"

    @property
    def validated(self) -> bool:
        return self.result == VALIDATED_RESULTS

    def as_dict(self) -> dict:
        return {"configuration": self.configuration, "dataset": self.dataset, "validation": self.validation,
                "deviations": list(self.deviations), "result": self.result}


def configuration_class(overrides: dict | None, deviations=()) -> str:
    """Research Baseline only when nothing departs from it; changes to the sensitivity dimensions
    alone are a sensitivity analysis; anything else (values, profile, backend, placement) is custom."""
    if deviations:
        return CUSTOM
    if not overrides:
        return BASELINE
    return SENSITIVITY if set(overrides) <= SENSITIVITY_KEYS else CUSTOM


def dataset_class(quality: dict | None, *, study_district: bool) -> str:
    """Complete: the study district's dataset is fit for research (required observations done).
    Estimated: missing heights come from an assumed height model. Incomplete: placeholder heights,
    or any area other than the study district (never presented as complete)."""
    quality = quality or {}
    if quality.get("fit_for_research") and study_district:
        return COMPLETE
    if quality.get("height_model"):
        return ESTIMATED
    return INCOMPLETE


def validation_class(root: Path) -> str:
    from bns.analysis import readiness

    found = {i.id: i.state for i in readiness.validation_indicators(root)}
    return VALIDATED if all(s == readiness.COMPLETED for s in found.values()) else PENDING


def classify(root: Path, overrides: dict | None, quality: dict | None, *, study_district: bool,
             deviations=()) -> Classification:
    devs = tuple(deviations) + tuple(f"{k} = {v}" for k, v in (overrides or {}).items())
    return Classification(configuration_class(overrides, deviations),
                          dataset_class(quality, study_district=study_district), validation_class(root), devs)


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
        return Classification(rec["configuration"], rec["dataset"],
                              _OLD_VALIDATION.get(rec["validation"], rec["validation"]),
                              tuple(rec.get("deviations") or ()))
    area = manifest.get("area") or {}
    return Classification(NOT_RECORDED, COMPLETE if area.get("fit_for_research") else INCOMPLETE, PENDING)
