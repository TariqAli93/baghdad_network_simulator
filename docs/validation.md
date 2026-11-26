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

## 5. Not yet verified

- Agreement with 3GPP TR 38.901 UMa/UMi path loss (Phase 7).
- MATLAB cross-check of identical cases (Phase 7).
- The research profile (5 m cells).
- Anything on the target laptop (Phase 0 gate open).
