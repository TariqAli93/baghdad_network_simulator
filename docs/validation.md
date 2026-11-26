# Scientific verification

What has been checked, against what, and what is still unchecked. Updated 2026-11-26
(Phases 3-4). Validation against 3GPP TR 38.901 and MATLAB (Phase 7) has not started.

## 1. Checks against physics (real engine)

| Check | Reference | Result | Where |
|---|---|---|---|
| Free space, five bands | Friis averaged over each cell | Worst cell 0.10 dB at 1e7 rays | Phase 0 E1; `tests/scientific/test_engine_sanity.py` |
| Ground reflection, both polarisations | ITU-R P.2040 Fresnel slab; Brewster angle | Worst cell 0.12 dB; dip at the predicted distance for vertical polarisation only | Phase 0 E2 |
| Diffraction behind a block | Knife-edge theory at the shadow boundary; 10 log10(f) scaling | Within 0.35 dB and 0.1 dB | Phase 0 E3 |
| **Whole pipeline: transmit power + traced path gain + gas loss → received power** | Friis + link budget + ITU-R P.676 values | Mean error 0.0002 dB, worst cell < 0.25 dB at 1e8 rays | `tests/scientific/test_pipeline.py` |
| **Traced sector antenna** | 3GPP TR 38.901 Table 7.3-1 formula (independent implementation in `bns.validation.analytic`) | Median deviation < 0.2 dB, 95 % < 0.5 dB; peak 8 dBi and back lobe −22 dBi reproduced | `tests/scientific/test_pipeline.py` |
| **Downtilt direction** | TR 38.901 rotation (positive downtilt points below the horizon) | Confirmed: +10° tilt gives more gain at steep angles than −10°, both matching the formula | `tests/scientific/test_pipeline.py` |
| Cache reuse | Second identical request | Served from the cache, no new trace | `tests/scientific/test_pipeline.py` |
| Ray-count convergence on real geometry | 1e9-ray maps and map-to-map noise | Profiles corrected (`docs/convergence.md`) | `scripts/run_convergence.py` |

## 2. Checks of the calculations (no engine; analytical cases)

| Area | What is verified | Tests |
|---|---|---|
| Unit conversions | dB, dBm, W round trips; FSPL reference value; 6 dB per distance doubling; 20 dB per frequency decade; kT = −173.98 dBm/Hz; noise grows 13.01 dB from 20 to 400 MHz | `test_units.py` |
| Received power | Power + gains + path gain − losses; per-cell losses; no path gives −inf, not an error | `test_link_budget.py`, `test_simulation_radio.py` |
| SINR | Interference summed in watts; strongest site serves; an added interferer lowers SINR; load factor scales interference only; cells with no signal | `test_link_budget.py`, `test_simulation_radio.py` |
| Shannon rate | 1 bit/s/Hz at 0 dB; 4 bit/s/Hz at SINR 15; linear in bandwidth at fixed SINR; sub-linear at fixed received power | `test_link_budget.py` |
| Coverage, percentiles, CDF, RMSE | Hand-computed small arrays; masks; no-signal cells counted as uncovered and as zero rate | `test_metrics.py`, `test_simulation_radio.py` |
| Coverage criterion vs bandwidth | The same received power covers at 20 MHz but not at 400 MHz under an SNR criterion | `test_simulation_radio.py` |
| Invalid propagation values | NaN, negative and > 1 path gains are rejected; tiny gains stay finite | `test_simulation_radio.py` |
| Radio configuration | Approval states; research mode refuses unapproved values; conducted power vs EIRP; double counting refused in three forms | `test_radio_system.py` |
| Cache invalidation | Each of 13 propagation dependencies changes the key; radio parameters are not part of it; scene hash follows meshes and materials; damaged entries are misses | `test_simulation_cache.py` |
| Worker failure and recovery | A crashed worker publishes nothing and is retried; a Python error is not retried; cancellation discards; an earlier good result survives a failed rerun | `test_runtime_workers.py`, `test_simulation_propagation.py` |
| Rain and gas | P.838-3 coefficients reproduce its Table 5 at six frequencies; loss along the straight path | `test_atmosphere.py` |
| Building heights | Provenance categories never upgraded; priority order; conflicts; manual overrides keep earlier values; dataset matching kinds | `test_height_resolution.py`, `test_height_datasets.py`, `test_geospatial_pipeline.py` |
| Greedy site selection | Largest gain first; stops at the target; unreachable targets reported; reproducible ties | `test_greedy.py` |

## 3. Is the test count meaningful?

There are 240 tests (234 unit, 6 engine). The count is not the point; what matters is which
mistakes they would catch.

**Strong:** every scientific function has at least one test against a value computed by hand
or a published formula, not just "it runs". The engine tests compare the ray tracer with
physics, not with itself. The double-counting and approval rules are tested in their failure
direction (the software must refuse), which is where a silent error would do most harm.

**Weak or missing:**

- The engine tests use an empty scene or one block. Nothing checks propagation in the city
  against an independent reference; that is Phase 7 (3GPP TR 38.901, MATLAB) and, ultimately,
  measurements the project does not have.
- A large share of the unit tests are structural (geospatial bookkeeping, file formats,
  configuration loading, mesh topology). They protect against regressions but say nothing
  about physical correctness.
- The multi-site SINR has analytical tests but has not yet been run on real multi-site maps.
- The greedy selection is tested on hand-built tables, not yet on ray-traced coverage.
- Some tests were written in the same step as their code rather than first: the TR 38.901
  pattern reference, `load_buildings`, the height-policy loader and the repository's rain
  cases. They pass, but were never seen failing.
- Scripts (`scripts/*.py`) have no tests of their own; they are exercised by running them.

## 4. Effect of the recovered multipolygon buildings

The v2 dataset adds 8 buildings (6,041 m², 7 with courtyards) that the Phase 0 snapshot
lacked. Measured with `scripts/compare_propagation.py` (3.5 GHz, 58 m site, three sectors,
standard profile; report in
`outputs/datasets/propagation_tahrir_bab_al_sharqi-osm_vs_tahrir_bab_al_sharqi_v2-osm_nr_3500.md`):

| Quantity | Value |
|---|---|
| Outdoor cells compared | 6,153 |
| Cells that became indoor (covered by a recovered building) | 71 |
| Median change | 0.00 dB |
| Cells changed by more than 1 / 3 / 10 dB | 10.2 % / 1.8 % / 0.4 % |

Changes below about 2 dB are within the map-to-map noise of the profile; the cells above
3 dB are the recovered buildings' own shadows. The correction matters locally, not for
area statistics; the missing third of the built area (`docs/study-area-evaluation.md`) is a
far larger effect.

## 6. Near-site coverage gap at 28 GHz (Phase 5)

The single-site development run left 32 % of the outdoor cells within 250 m of the tower
uncovered at 28 GHz. The Phase 4 report attributed this to the downtilted vertical pattern.
`scripts/diagnose_near_site.py` tested that against a second explanation without tracing
anything new: for every near cell it compares the traced best-sector path gain with free
space + the TR 38.901 element gain of the best sector, and checks whether the straight line
from the antenna passes below the host roof's edge (the host building shadows the ground).

| 28 GHz, cells within 250 m | Cells | Uncovered | Behind own roof edge | Median pattern gain | Median excess loss |
|---|---|---|---|---|---|
| uncovered | 414 | 100 % | 100 % | +1.5 dBi | +36.8 dB |
| covered | 863 | 0 % | 81 % | +5.7 dBi | +24.8 dB |
| line of sight clears own roof | 167 | 0 % | 0 % | +4.5 dBi | −0.3 dB |

- Every uncovered cell is behind the roof edge, and its excess loss (37 dB) dwarfs the
  4 dB pattern difference to covered cells: the gap is the **host roof's own shadow** (a 3 m
  mast at the representative point of a roof about 29 m across), not the pattern.
- Where the line of sight clears the roof, the traced map agrees with free space + pattern
  within 0.3 dB (median): an end-to-end check of the traced antenna pattern in a city scene.
- The shadow loss grows with frequency as diffraction should: behind the roof edge the
  median excess loss is 21.1 dB at 3.5 GHz and 30.0 dB at 28 GHz (10·log10(28/3.5) = 9 dB).
- Nothing was tuned. Antenna position (roof edge vs centre) and mast height are a site-rule
  decision (A4); a sector antenna on a real rooftop is normally mounted at the edge.

## 7. GPU and CPU traces agree (optional check)

**Radio-level agreement (Phase 7).** The four-site preview experiment was run twice through the
production pipeline, once per backend (`scripts/compare_backends.py`; result in the GPU run's
`backend_agreement.md`). Over 808 outdoor cells and all five bands: best-sector path gain
|Δ| median 0.01-0.03 dB, 95th percentile 0.28-0.45 dB, maximum 2.8-4.0 dB; no cell reached by
one backend only; **no cell changed coverage class**; SINR |Δ| median 0.06-0.16 dB, 95th
percentile 0.75-1.11 dB; 5th-percentile Shannon rate within 1.2 %, median rate within 1.2 %.
Only one cell was below −140 dB (weak-signal check therefore thin). The −10 dB threshold
saturates coverage, so the classification test is weak too; the differences are, however, an
order of magnitude below the preview convergence floor (2.9 dB).

**Original single-job check:**

The same two cached jobs traced with the CUDA variant on the RTX 3060 matched the CPU maps:
median |Δ| 0.10 dB (preview) and 0.07 dB (standard), 95th percentile 2.2 and 1.7 dB (cells
dominated by randomly sampled diffraction), a handful of cells reached by one backend only.
CPU remains the production engine (`docs/benchmarks.md` §9).

## 8. Ray tracing vs 3GPP TR 38.901 (Phase 7, model-to-model)

Category 2 of four (analytical verification; model-to-model; MATLAB cross-check; field
measurements). `scripts/validate_tr38901.py`; results in
`outputs/validation/tr38901-tahrir_bab_al_sharqi_v2-osm-preview-*/` (summary, per-cell CSV,
figures). Formulas: `bns.validation.tr38901` (V19.5.0 Tables 7.4.1-1 and 7.4.2-1; 6 unit tests
including breakpoint table, continuity and hand values).

**Configuration.** Isotropic antenna in open street space at the area centre, at exactly 25 m
(UMa) and 10 m (UMi); users 1.5 m; all five bands; project mechanisms; LOS/NLOS from a
line-of-sight-only trace; cells closer than 10 m excluded. **Preview profile** (25 m, 1e8): the
standard profile was attempted but its isotropic traces ran 5-12 minutes each with only about
4 of 16 cores busy (`docs/benchmarks.md` §10); the preview profile is validated for development and its
2.9 dB convergence floor is small against the models' 4-8 dB shadow-fading σ.

| | UMa LOS | UMa NLOS | UMi LOS | UMi NLOS |
|---|---|---|---|---|
| Mean error (traced − 3GPP), 3.5-28 GHz | −1.2 to −1.5 dB | −9.9 to −14.9 dB | −2.9 to −7.6 dB | −14.8 to −18.2 dB |
| RMSE, 3.5-28 GHz | 3.6-3.9 dB | 13.0-16.3 dB | 4.7-9.1 dB | 16.8-19.5 dB |
| RMSE, 1.8 GHz | 5.9 dB | 17.8 dB | 13.9 dB | 20.7 dB |
| σ of the model | 4 dB | 6 dB | 4 dB | 7.82 dB |
| Fitted exponent (traced) | 1.68-1.71 | 2.14-2.74 | 1.82-1.88 | 1.33-2.19 |
| Exponent of the model (below breakpoint) | 2.2 | 3.91 | 2.1 | 3.53 |
| Traced LOS share of outdoor cells | 85 % | | 27 % | |

What this supports and what it does not:

- **UMa line of sight agrees within σ** from 3.5 GHz up (RMSE 3.6-3.9 dB < 4 dB). The traced
  LOS exponent (1.7) is just below the measured 1.8-2.3 range near 7-17 GHz
  (`docs/related-studies.md` R4-R6).
- **Beyond the breakpoint the traced loss is lower than 3GPP's** (largest at 1.8 GHz, where
  d'BP = 288 m for UMa and 108 m for UMi lie inside the area). Plausible cause, consistent with
  experiment E2 but not demonstrated here: the radio map sums the direct and ground-reflected
  powers non-coherently, so the two-ray interference that produces the 3GPP breakpoint cannot
  appear.
- **NLOS does not agree, and this is a mismatch of environment, not a verified engine error.**
  The district is open and low (Tahrir Square at the centre, 99 % of roofs a 9 m placeholder):
  85 % of cells see a 25 m antenna directly, against a 3GPP LOS probability of 3-26 % beyond
  50 m. Its NLOS cells sit just behind low roofs, so they lose far less than 3GPP's statistical
  NLOS (−10 to −18 dB error). The NLOS exponent rises with frequency (UMa 2.1 → 2.7) and is
  close to measured 2.6-2.7 at 8-15 GHz, but on 124 cells and placeholder heights that is not
  evidence of accuracy.
- UMi assumes the antenna below the rooftops; here 10 m is just above most (9 m) roofs, so UMi
  is outside its intended geometry and reported with that qualification.
- Not done: comparison with the real rooftop sites (outside both models' height assumptions)
  and any check against measurements.

## 9. MATLAB cross-check (prepared, not executed)

`validation/matlab/uma-tahrir_bab_al_sharqi_v2-osm/`: scene as STL from the same meshes, the
UMa transmitter, 200 receivers (100 LOS, 100 NLOS, seed 0) with the Sionna path loss at 3.5 and
28 GHz, `run_case.m` (SBR, 2 reflections, 1 diffraction, concrete, non-coherent power sum),
README listing the engine differences. Run it on the laptop, then
`scripts/compare_matlab.py`. **No MATLAB result exists yet; nothing is verified by MATLAB.**

## 10. Antenna position on the roof (Phase 7 controlled experiment)

Tower way/919688856 (roof 55 m, 833 m², 3 m mast), standard profile, CPU. Only the sector
positions change: the interior point of the roof vs the roof edge in each sector's direction
(1 m inside; 11.0, 12.4 and 19.2 m from the interior point).

| Band | Placement | Coverage | Uncovered within 250 m | Median SINR | 5th-pct rate |
|---|---|---|---|---|---|
| 3.5 GHz | interior | 99.8 % | 0.4 % | 19.2 dB | 146 Mbit/s |
| 3.5 GHz | edge | 100.0 % | 0.1 % | 22.7 dB | 170 Mbit/s |
| 28 GHz | interior | 89.1 % | 32.4 % | 9.7 dB | 15 Mbit/s |
| 28 GHz | edge | 96.7 % | 2.3 % | 14.5 dB | 164 Mbit/s |

Together with §6 this is controlled evidence that the gap is the host roof's own shadow:
changing nothing but the antenna position removes most of it. It is one building with
placeholder surroundings, so it demonstrates the mechanism, not its size in general. The
interior-point placement stays in the candidate generator until A4 decides; nothing was tuned.

## 5. Not yet verified

- Agreement with 3GPP TR 38.901 for the real rooftop sites (outside the models' heights).
- MATLAB cross-check: package prepared (§9), not executed.
- Any comparison with field measurements.
- The research profile (5 m cells).
- Anything on the target laptop (Phase 0 gate open).
