# MATLAB cross-check, case `uma-tahrir_bab_al_sharqi_v2-osm`

**Status: prepared, not executed.** MATLAB is not installed on the development PC; run this on
the laptop that has MATLAB. Nothing is verified until `scripts/compare_matlab.py` has run on the
results. DEVELOPMENT — NOT APPROVED FOR RESEARCH.

## What is compared

Path loss between isotropic antennas from one transmitter at 25 m (UMa
configuration of `outputs\validation\tr38901-tahrir_bab_al_sharqi_v2-osm-preview-20261126T130157Z`) to 200 receivers at 1.5 m, at
3.5 GHz, 28 GHz. Identical geometry (`scene.stl`,
exported from the same meshes Sionna traced), materials (concrete), transmitter and receiver
coordinates (`case.json`, `receivers.csv`).

## Run

1. Copy this folder to the laptop. Open MATLAB in it.
2. `run_case` — writes `matlab_results.csv` (one row per receiver and frequency).
3. Copy `matlab_results.csv` back into this folder and run
   `uv run python scripts/compare_matlab.py validation/matlab/uma-tahrir_bab_al_sharqi_v2-osm`.

## Known differences between the engines (expect disagreement from these, not only from errors)

| Aspect | Sionna RT (project) | MATLAB SBR |
|---|---|---|
| Quantity | cell average over 25 m cells, non-coherent | point receiver; `run_case.m` sums ray powers non-coherently to match |
| Reflections | up to 2 | `MaxNumReflections` 2 |
| Diffraction | first-order, never combined with a reflection, randomly sampled wedges | `MaxNumDiffractions` 1 (UTD); may combine with reflections depending on release |
| Materials | ITU-R P.2040 concrete as a slab (buildings 0.2 m, ground 1.0 m) | ITU-R P.2040 concrete, half-space |
| Transmission through walls | off | not modelled |
| Ray launching | Fibonacci lattice, 1e+08 rays | SBR angular separation "low" (about 0.2°) |

Agreement criterion (to be agreed with the supervisor, decision B1): for example median
|difference| within the convergence floor of the profile (about 2 dB) in LOS cells.
