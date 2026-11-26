"""Engine settings that change results, readable without starting the engine.

They are part of every propagation cache key (bns.simulation.jobs), so a cached
path-gain map is never reused across engine versions or settings.
"""

from __future__ import annotations

from importlib.metadata import version

CPU_VARIANT = "llvm_ad_mono_polarized"
GPU_VARIANT = "cuda_ad_mono_polarized"
# Execution backends. CPU is the production path (the target laptop has no NVIDIA GPU);
# GPU is optional. The variant is part of the engine fingerprint, hence of every cache
# key: CPU and GPU maps are cached separately and never mixed.
VARIANTS = {"cpu": CPU_VARIANT, "gpu": GPU_VARIANT}

# Sionna RT keeps diffracting wedges in a hash table and drops a wedge whose slot is
# taken. Its default of 10,000 slots loses more than 1 dB of diffracted power in a city
# scene (docs/benchmarks.md, E4). The larger table changes no physics.
SIONNA_DEFAULT_WEDGE_SLOTS = 10_000
WEDGE_TABLE_SLOTS = 2**20


def engine_fingerprint(backend: str = "cpu") -> dict:
    if backend not in VARIANTS:
        raise ValueError(f"backend must be one of {sorted(VARIANTS)}, not {backend!r}.")
    return {"sionna-rt": version("sionna-rt"), "mitsuba": version("mitsuba"),
            "drjit": version("drjit"), "variant": VARIANTS[backend],
            "wedge_table_slots": WEDGE_TABLE_SLOTS}


def backend_of(engine: dict) -> str:
    """'cpu' or 'gpu' from an engine fingerprint."""
    for name, variant in VARIANTS.items():
        if engine.get("variant") == variant:
            return name
    raise ValueError(f"Unknown engine variant {engine.get('variant')!r}.")
