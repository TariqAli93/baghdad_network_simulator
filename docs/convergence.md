# How many rays a map needs (Phase 4 convergence check)

Run 2026-11-26 with `scripts/run_convergence.py --area tahrir_bab_al_sharqi_v2`; full tables
in `outputs/runs/convergence/tahrir_bab_al_sharqi_v2/summary.md`.

## Set-up

- Full provisional area: 1 km × 1 km receivers at 1.5 m, traced at 5 m cells; 10 m and 25 m
  results are the same maps averaged over 2 × 2 and 5 × 5 cells.
- 8 cases: three sites (antenna heights 58 m, 15 m and 13 m) × two bands (3.5 and 28 GHz) on
  the OSM scene, plus the tallest site in both bands on a scene with a wider spread of
  assumed heights (1-8 storeys).
- Project baseline mechanisms (line of sight, 2 reflections, diffraction), isotropic antenna.
- Each map is compared with a 1-billion-ray map of the same case. A second 1-billion-ray map
  with another seed gives the noise floor: the reference itself is not exact, because the
  diffraction part of the solver is random.
- Measure: 95th percentile of the absolute difference over outdoor cells (dB), and the share
  of cells the reference reaches but the cheaper map misses.
- Criteria (provisional, chosen here): 25 m, within 3 dB and at most 2 % missed;
  10 m and 5 m, within 2 dB and at most 1 % missed.

## Results (worst of the 8 cases)

| Cell size | 1e7 rays | 1e8 rays | Two 1e9 maps (floor) |
|---|---|---|---|
| 25 m | 16.1 dB, 1.1 % missed | **2.9 dB, 0 %** | 1.0 dB, 0 % |
| 10 m | 32.1 dB, 11.9 % | 5.2 dB, 0.5 % | **2.0 dB, 0 %** |
| 5 m | 31.7 dB, 24.2 % | 25.9 dB, 4.1 % | 3.7 dB, 0.1 % |

The same pattern holds in every case: the low sites (13-15 m), whose signal reaches much of
the area only by diffraction, and the scene with taller buildings converge most slowly.
Both bands behave alike, as expected, because ray density does not depend on frequency.

## Profiles that follow (in `configs/simulation.yaml`)

| Profile | Cells | Rays per sector | Status |
|---|---|---|---|
| Preview | 25 m | 1e8 | Meets its criterion in all 8 cases |
| Standard | 10 m | 1e9 | Two independent maps agree within 1.4-2.0 dB; there is no finer reference to check against |
| Research | 5 m | not set | Not validated: even 1e9 rays leave about 3 dB of map-to-map noise; seed averaging or more rays must be measured first |

Cost on the development PC (Phase 0 benchmark): about 6 s per 1e8 rays and 60 s per 1e9 rays
per sector, independent of the cell size. Memory stays under 1 GB.

## Correction to Phase 0

Phase 0 (`docs/benchmarks.md`, E5) concluded that 1e8 rays were enough for 10 m cells. That
was measured on a 400 m × 400 m block around one tall site. On the full 1 km² area the far
cells receive too few rays and 1e8 rays give 3.9-5.2 dB at the 95th percentile. The standard
profile was therefore raised to 1e9 rays, ten times the cost. Phase 0's statement stays in
its report as what was measured then; this file supersedes it for the profiles.

## What this means for the time budget

Site planning traces every candidate site in every band, with three sectors each. At the
standard profile that is about 3 minutes per candidate and band on the development PC; 30
candidates in 5 bands is roughly 7.5 hours, and the target laptop will be slower. The
preview profile is ten times faster and suitable for exploring candidates; final runs need
the standard profile. Whether that budget is acceptable belongs to the laptop measurement
that closes the Phase 0 gate.
