"""Scientific classification of a simulation result: three separate states and the result class.

    configuration  Research Baseline | Custom Experiment | Sensitivity Analysis | not recorded
    dataset        Complete data | Estimated heights | Incomplete data
    validation     Validation Completed | Validation Pending

The result class follows from the three, and is never better than the evidence:

    Validated Research Results              baseline configuration, complete data, validation completed
    Research Baseline · Validation Pending  baseline configuration, complete data, validation pending
    Simulation Results                      baseline configuration on estimated building heights (e.g. the
                                            Synthetic Urban Model): a simulation, never a validated finding
    Custom Experiment / Sensitivity Analysis  other values or settings on complete or estimated data
    Preliminary Simulation                  incomplete data (placeholder heights), or a configuration that
                                            was not recorded (runs before 2026-11-27)

None of this decides whether a run may execute: any technically valid simulation runs, and the
classification says what its result is. The research baseline is the approved configuration
(values in configs/, the standard profile, the CPU backend, the site rule); a run that departs
from it in any way records the deviations and is a custom experiment (or a sensitivity analysis
when only the threshold, target, load or rain differ). "Completed" validation needs evidence
for the run's own propagation scope (bns.analysis.validation_scope): an accepted convergence
record and a MATLAB comparison meeting the B1 criterion, both for the same scene, grid, rays,
engine, antennas and mechanisms. Evidence never transfers to runs outside that scope; it does
carry over across radio-system values (power, noise, threshold, load, rates), which do not change
the path gain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BASELINE, CUSTOM, SENSITIVITY = "Research Baseline", "Custom Experiment", "Sensitivity Analysis"
NOT_RECORDED = "Configuration not recorded"
COMPLETE, ESTIMATED, INCOMPLETE = "Complete data", "Estimated Building Heights", "Incomplete data"
VALIDATED, PENDING = "Validation Completed", "Validation Pending"
PRELIMINARY, VALIDATED_RESULTS = "Preliminary Simulation", "Validated Research Results"
SIMULATION_RESULTS = "Simulation Results"           # complete synthetic heights, not empirical
_OLD_DATASET = {"Estimated heights": ESTIMATED}
# parameters whose variation is a sensitivity analysis of the baseline (threshold, target, load,
# rain: the approved sensitivity dimensions); changing anything else is a custom experiment
SENSITIVITY_KEYS = frozenset({"coverage_threshold", "coverage_target", "interference_activity", "rain_rate_mm_h"})
_OLD_VALIDATION = {"Validated": VALIDATED}           # spelling of the first records (2026-11-27)
# how the transmitting sites were placed: a dimension of its own, never folded into the result class.
# Manual placement on a roof that satisfies the site rule keeps the baseline parameter class; a
# hypothetical location is always a recorded deviation (a custom experiment).
AUTOMATIC_PLACEMENT, MANUAL_PLACEMENT = "Automatic placement", "Manual placement"
HYPOTHETICAL_PLACEMENT = "Hypothetical placement"


@dataclass(frozen=True)
class Classification:
    configuration: str
    dataset: str
    validation: str
    deviations: tuple[str, ...] = field(default=())     # how the configuration departs from the baseline
    validation_scope: str = ""                          # key of the run's propagation scope (validation_scope)
    placement: str = ""                                 # automatic / manual / hypothetical; "" = not recorded

    @property
    def result(self) -> str:
        if self.dataset == INCOMPLETE or self.configuration == NOT_RECORDED:
            return PRELIMINARY
        if self.configuration != BASELINE:
            return self.configuration
        if self.dataset == ESTIMATED:              # every height known, but estimated: never validated research
            return SIMULATION_RESULTS
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
                "deviations": list(self.deviations), "validation_scope": self.validation_scope, "result": self.result,
                **({"placement": self.placement} if self.placement else {})}


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


def validation_class(root: Path, scope: dict | None, *, profile: str | None) -> str:
    """Validation Completed only when evidence covers this run's propagation scope: a MATLAB comparison
    meeting B1 whose source run has the same scope, and an accepted final-scene convergence record for
    the same profile (cell size, rays), scene and backend. Anything else: Validation Pending."""
    from bns.analysis import readiness
    from bns.analysis import validation_scope as vs
    from bns.propagation.engine_settings import backend_of

    if not scope:
        return PENDING
    k = vs.key(scope)
    matlab = any(e["passes"] and e["scope_key"] == k for e in readiness.matlab_evidence(root))
    conv = readiness.convergence_record(root, profile)
    converged = bool(conv) and conv.get("scene_fingerprint") == scope["scene_fingerprint"] \
        and conv.get("backend", "cpu") == backend_of(scope["engine"]) \
        and float(conv.get("cell_size_m") or -1) == scope["grid"]["cell_size_m"] \
        and int(float(conv.get("rays_per_site") or -1)) == scope["rays_per_site"]
    return VALIDATED if matlab and converged else PENDING


def classify(root: Path, overrides: dict | None, quality: dict | None, *, study_district: bool,
             deviations=(), scope: dict | None = None, profile: str | None = None,
             placement: str = "") -> Classification:
    from bns.analysis import validation_scope as vs

    devs = tuple(deviations) + tuple(f"{k} = {v}" for k, v in (overrides or {}).items())
    return Classification(configuration_class(overrides, deviations),
                          dataset_class(quality, study_district=study_district),
                          validation_class(root, scope, profile=profile), devs, vs.key(scope), placement)


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
        return Classification(rec["configuration"], _OLD_DATASET.get(rec["dataset"], rec["dataset"]),
                              _OLD_VALIDATION.get(rec["validation"], rec["validation"]),
                              tuple(rec.get("deviations") or ()), rec.get("validation_scope", ""),
                              rec.get("placement", ""))
    area = manifest.get("area") or {}
    return Classification(NOT_RECORDED, COMPLETE if area.get("fit_for_research") else INCOMPLETE, PENDING)
