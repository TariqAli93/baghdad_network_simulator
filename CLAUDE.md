# Baghdad Network Simulator

Graduation-project research tool: ray-traced coverage, SINR and Shannon data rate of
4G (1.8 GHz), 5G (3.5 and 28 GHz) and candidate 6G (8 and 15 GHz) over a ~1 km² Baghdad
district, the base-station density each needs, and a 6G roadmap for Iraq.

Primary requirements: `Project_Description_4G_5G_6G_Baghdad.pdf` (the student's project
description). Progress and the phase gates live in `docs/implementation-plan.md`.

## Non-negotiable rules

- Scientific correctness over appearance. Real simulation, never mocked or fabricated data.
- Never change a scientific assumption silently. Record it in `docs/assumptions.md`; values
  the supervisor has not approved are marked *provisional*.
- No fabricated references or results. Report numbers only from runs that were executed.
- CPU-first: no CUDA, no cloud, no paid dependency. The target is a 16 GB laptop.
- Work phase by phase and stop at each gate. No UI work before the simulation core is validated.
- 6G scenarios are *candidate research assumptions*; the 3.5 GHz band for Iraq is *assumed*.

## Commands

```
uv sync                                         # create/update .venv from uv.lock
uv run pytest                                   # unit tests (fast, no ray tracing)
uv run pytest -m engine                         # scientific tests through the real engine
uv run python scripts/build_poc_scene.py        # OSM snapshot -> data/scenes/
uv run python scripts/poc_validate.py all       # experiments E1-E5 -> outputs/runs/phase0/
uv run python scripts/poc_benchmark.py          # time and memory -> outputs/runs/phase0/benchmark/
```

## Engine facts you must respect

- Engine: Sionna RT 2.2.0 (`mitsuba` 3.9.1, `drjit` 1.5.0) on the CPU variant
  `llvm_ad_mono_polarized`. LLVM 18.1.8 must be installed
  (`winget install --id LLVM.LLVM -e --version 18.1.8`).
- Always call `bns.runtime.init()` before anything imports `mitsuba` or `sionna.rt`.
  `bns.propagation.sionna_engine` refuses to import otherwise.
- **Run every simulation in a worker process through `bns.runtime.run_isolated`.** On Windows
  the first compilation of a kernel intermittently crashes the process; results are accepted
  only from a process that exits with code 0, and a failed attempt is retried (compiled
  kernels are cached in `data/cache/drjit`, so retries converge). Details in
  `docs/architecture.md`.
- The ray tracer returns **path gain** (linear, between isotropic antennas), independent of
  transmit power and bandwidth. Received power, SINR and data rate are computed afterwards.
- Rays start on a deterministic lattice: accuracy is set by the ray count, and averaging
  seeds does not improve line-of-sight or reflected power. Only diffraction is random.
- Refraction is off (buildings are opaque). Radio-map diffraction is first-order and is
  never combined with a reflection. Gas and rain loss are not built in.
- Do not revert the enlarged wedge table in `sionna_engine.py`: with Sionna's default of
  10,000 slots a city scene loses more than 1 dB of diffracted power (benchmarks, E4).
- Ray counts follow the cell size (benchmarks, E5): finer cells need more rays. Time grows
  with rays, not with cells; memory stays under 1 GB either way.

## Conventions

- SI units internally (Hz, m, W); dB and dBm only at the edges. Helpers: `bns.core.units`.
- Scene coordinates: metres, z up, origin at the centre of the study box (local transverse
  Mercator). Grid arrays are indexed `[y, x]`.
- Every building height carries its source: `tag:height`, `tag:building:levels` or `assumed`.
- Raw data in `data/raw/` is immutable and hashed; `data/scenes/`, `data/cache/` and large
  run outputs are regenerated and git-ignored.
- Charts use `bns.reporting.plotstyle` (one colour per scenario, everywhere).

## Layout

```
configs/scenarios.yaml          the five scenarios (single source of truth)
src/bns/runtime.py              CPU bootstrap, memory cap, isolated workers
src/bns/core/units.py           conversions, Friis, thermal noise
src/bns/validation/analytic.py  closed-form references (Friis, Fresnel slab, knife edge)
src/bns/geospatial/osm_scene.py OSM footprints -> meshes -> Mitsuba scene
src/bns/propagation/            sionna_engine.py (path-gain maps)
src/bns/reporting/plotstyle.py  chart style
scripts/                        build_poc_scene.py, poc_validate.py, poc_benchmark.py
tests/unit, tests/scientific    pytest
docs/                           implementation-plan, architecture, assumptions, benchmarks
```

Keep `docs/implementation-plan.md` current at the end of every phase: completed work, files,
tests actually run with their results, limitations, measurements, blockers, next phase.
