"""CPU/GPU backends: separate cache identity, explicit selection; the GPU runs whenever it exists."""

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


def test_an_available_gpu_is_never_refused_and_an_unavailable_one_always_is(monkeypatch):
    monkeypatch.setattr(runtime, "probe_gpu", lambda: (True, "GPU available: test"))
    for mode in ("development", "research"):                       # mode no longer restricts anything
        assert ex.resolve_backend("gpu", config(), mode)[0] == "gpu"
        assert ex.resolve_backend("auto", config(), mode)[0] == "gpu"
    monkeypatch.setattr(runtime, "probe_gpu", lambda: (False, "No NVIDIA driver."))
    with pytest.raises(ex.ExperimentError, match="No NVIDIA driver"):
        ex.resolve_backend("gpu", config(), "development")         # a technical problem still stops the run
    assert ex.resolve_backend("auto", config(), "development")[0] == "cpu"


def test_profile_and_backend_departures_from_the_baseline_are_recorded():
    from pathlib import Path

    from bns.simulation.setup import Profile

    root = Path(__file__).resolve().parents[2]
    assert ex.baseline_deviations(root, Profile("standard", 10.0, 10**9, "approved"), "cpu") == []
    devs = ex.baseline_deviations(root, Profile("preview", 25.0, 10**8, "validated for development"), "gpu")
    assert any(d.startswith("preview profile") for d in devs) and any(d.startswith("GPU backend") for d in devs)
