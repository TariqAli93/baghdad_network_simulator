"""CPU/GPU backends: separate cache identity, explicit selection, research runs stay on CPU."""

import dataclasses

import pytest

from bns import runtime
from bns.propagation.engine_settings import backend_of, engine_fingerprint
from bns.simulation import experiment as ex
from bns.simulation.setup import SimulationConfig

BACKENDS = {"cpu": {"status": "production"}, "gpu": {"status": "validated for development"}}


def config():
    return SimulationConfig({}, None, (1,), "V", BACKENDS)


def test_backend_is_part_of_the_engine_fingerprint_and_can_be_read_back():
    cpu, gpu = engine_fingerprint("cpu"), engine_fingerprint("gpu")
    assert cpu != gpu and cpu["variant"] == "llvm_ad_mono_polarized" and gpu["variant"] == "cuda_ad_mono_polarized"
    assert backend_of(cpu) == "cpu" and backend_of(gpu) == "gpu"
    with pytest.raises(ValueError):
        engine_fingerprint("tpu")


def test_cpu_and_gpu_jobs_never_share_a_cache_key():
    from bns.geospatial.grid import Grid
    from bns.simulation.jobs import Antenna, Mechanisms, PropagationJob

    def job(backend):
        return PropagationJob("scene", None, 3.5e9, (0.0, 0.0, 30.0), Antenna("iso", "V", (0.0, 0.0, 0.0)),
                              Grid((0.0, 0.0), (100.0, 100.0), 10.0, 1.5),
                              Mechanisms(2, True, True, True, False, False, False), 10**8, (1,),
                              engine_fingerprint(backend))

    assert job("cpu").key() != job("gpu").key()


def test_auto_uses_the_gpu_only_when_the_probe_succeeds(monkeypatch):
    monkeypatch.setattr(runtime, "probe_gpu", lambda: (True, "GPU available: test"))
    assert ex.resolve_backend("auto", config(), "development")[0] == "gpu"
    monkeypatch.setattr(runtime, "probe_gpu", lambda: (False, "no driver"))
    assert ex.resolve_backend("auto", config(), "development") == ("cpu", "no driver")


def test_explicit_gpu_fails_with_the_diagnostic_instead_of_falling_back(monkeypatch):
    monkeypatch.setattr(runtime, "probe_gpu", lambda: (False, "No NVIDIA GPU or driver found"))
    with pytest.raises(ex.ExperimentError, match="No NVIDIA GPU"):
        ex.resolve_backend("gpu", config(), "development")


def test_research_runs_refuse_a_backend_that_is_not_production(monkeypatch):
    monkeypatch.setattr(runtime, "probe_gpu", lambda: (True, "GPU available: test"))
    with pytest.raises(ex.ExperimentError, match="not approved for research"):
        ex.resolve_backend("gpu", config(), "research")
    assert ex.resolve_backend("auto", config(), "research")[0] == "cpu"
    approved = dataclasses.replace(config(), backends={**BACKENDS, "gpu": {"status": "production"}})
    assert ex.resolve_backend("gpu", approved, "research")[0] == "gpu"


def test_research_runs_require_a_profile_accepted_for_research():
    from bns.simulation.setup import Profile

    with pytest.raises(ex.ExperimentError, match="not accepted for research"):
        ex.require_research_profile(Profile("standard", 10.0, 10**9, "borderline convergence"), "research")
    ex.require_research_profile(Profile("standard", 10.0, 10**9, "borderline convergence"), "development")
    ex.require_research_profile(Profile("standard", 10.0, 10**9, "approved"), "research")


def test_research_runs_refuse_a_dataset_that_is_not_fit_for_research():
    unfit = {"fit_for_research": False, "not_fit_reasons": ["98.8 % of buildings have placeholder heights"]}
    with pytest.raises(ex.ExperimentError, match="placeholder heights"):
        ex.require_research_dataset(unfit, "research")
    ex.require_research_dataset(unfit, "development")
    ex.require_research_dataset({"fit_for_research": True, "not_fit_reasons": []}, "research")
