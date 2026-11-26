"""Engine settings that change results, readable without starting the engine.

They are part of every propagation cache key (bns.simulation.jobs), so a cached
path-gain map is never reused across engine versions or settings.
"""

from __future__ import annotations

from importlib.metadata import version

CPU_VARIANT = "llvm_ad_mono_polarized"

# Sionna RT keeps diffracting wedges in a hash table and drops a wedge whose slot is
# taken. Its default of 10,000 slots loses more than 1 dB of diffracted power in a city
# scene (docs/benchmarks.md, E4). The larger table changes no physics.
SIONNA_DEFAULT_WEDGE_SLOTS = 10_000
WEDGE_TABLE_SLOTS = 2**20


def engine_fingerprint() -> dict:
    return {"sionna-rt": version("sionna-rt"), "mitsuba": version("mitsuba"),
            "drjit": version("drjit"), "variant": CPU_VARIANT,
            "wedge_table_slots": WEDGE_TABLE_SLOTS}
