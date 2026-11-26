# Approval record (research provenance)

Machine-readable: `configs/approvals.yaml`. Fingerprints of the research baseline:
`configs/research_baseline.yaml` (`bns.analysis.research_baseline`).

| | |
|---|---|
| Report 1 | 2026-11-26, the project owner: the supervisor accepted every recommended option of `docs/supervisor-checklist.md` (commit `bc750b3`, tag `v1.0.0-rc.1`) |
| Report 2 | 2026-11-27, the project owner: the supervisor approved the follow-up recommendations (reduced fieldwork, 1 m inset, monument exclusion, B1 tolerance, per-band rate mappings) |
| Report 3 (final) | 2026-11-27, the project owner: the supervisor explicitly approved **all** decisions of the project scope, including compass sector bearings, the candidate criteria and the observation methods |
| Written reference / supervisor identity | none supplied; not required to operate the software; none invented |

All decisions are approved. No supervisor decision is pending for the project scope, and the
software does not ask for further approvals.

## 1. The approved research baseline

| ID | Decision | Where |
|---|---|---|
| A1 | Tahrir Square / Bab Al-Sharqi: centre 33.3280 N 44.4085 E, 1 km × 1 km, 150 m margin | `study_area.yaml` (`tahrir_bab_al_sharqi_study`) |
| A2 footprints | OSM plus missing footprints from 3D-GloBFP (footprints only); footprint and height provenance separate | `study_area.yaml` |
| A2 heights | observation > OSM height > OSM storeys × 3.0 m > authorised dataset (none) > approved model > placeholder; missing heights through the height sensitivity analysis; GlobalBuildingAtlas not a height source | `study_area.yaml` `height_policy` |
| A2 observations | P0, P1: measured or documented heights. P2: measured or documented preferred; storey-based estimate (3.0 m per storey) accepted when no reliable measurement or document exists. S: storey counts. P3: height sensitivity analysis. Each row records source, method, uncertainty and notes; estimates are never classified as measured | `study_area.yaml` `method_requirements`, `preferred` |
| A3 | 46 dBm conducted per sector carrier; TR 38.901 element traced (8 dBi peak, 65°), no added gain; 3 sectors; 10° downtilt; no array gain; isotropic receiver 1.5 m; NF 9 dB, 290 K; SINR ≥ −10 dB on 95 % of outdoor cells; reuse 1, load 1.0, co-located sectors interfere, strongest sector serves, no scheduler; clear sky | `radio_system.yaml`, `atmosphere.yaml` |
| A4 | compass bearings 0°, 120°, 240° (0 = north, clockwise); 3 m mast; roof edge facing each sector, 1 m inset; candidates with observed or storey-based heights, roof ≥ 12 m, area ≥ 100 m², spacing ≥ 50 m, target 20-40; monuments, memorials, artworks never candidates; interference-aware SINR greedy | `site_rule.yaml`, `radio_system.yaml` |
| A4 refinement | after the survey the thresholds may be refined to obtain 20-40 candidates, documented with the geometric justification in `site_rule.yaml` (`adjustments`); never tuned to coverage results; no further approval needed | `site_rule.yaml` |
| B1 | TR 38.901 UMa/UMi comparison kept; MATLAB external cross-check; median \|Δ\| in LOS cells ≤ 2.0 dB, RMSE and NLOS reported separately | `approvals.yaml` |
| B2 | engine limitations accepted as documented; 2-3 MATLAB reflection-then-diffraction cases | `validation/matlab/` |
| B3 | Shannon for every band; beside it LTE (TR 36.942) for 4G, NR (TR 38.921) for 5G, NR-based approximation (labelled) for candidate 6G | `radio_system.yaml` |
| C2-C5 | optional sensitivity cases, never the baseline (rain 18.6 mm/h, equal power per MHz, 50 % load, height uncertainty, array gain by arithmetic) | `atmosphere.yaml` |
| C6 | CPU for research-baseline results; GPU and auto for development and custom experiments | `simulation.yaml` |
| Convergence | standard profile 10 m / 1e9 rays, re-measured on the final scene; preview 25 m / 1e8; 5 m disabled | `simulation.yaml` |
| MATLAB, laptop | MATLAB cross-check before conclusions; measured laptop times are the time budget | — |

## 2. Baseline and custom experiments

The approved values are the **research baseline**. Any valid parameter can be changed for a
run (Run simulation page, or `--overrides FILE` of `scripts/run_multi_site.py`); such a run is a
**custom experiment**, records the values it used (`run_class`, `overrides` in its manifest),
and is labelled as development output. A **research-baseline run** (mode research) uses the
baseline unchanged and needs a dataset fit for research and the final-scene convergence. No
approval is requested in either case. `scripts/research_baseline.py` compares the configuration
files with the recorded baseline; `--record` is used only for a deliberate, documented baseline
update (e.g. a candidate-threshold refinement), described in this file.

## 3. Changes the final approval made to the software (2026-11-27)

| Item | Change |
|---|---|
| Sector orientation | sectors now face compass bearings 0/120/240° (ray-tracer yaw 90/330/210°). Runs made before keep the orientation their manifests record (yaw 0/120/240° = compass 90/330/210°); they are not reinterpreted. New orientations give new cache keys |
| Candidate criteria | 12 m / 100 m² / 50 m in `site_rule.yaml`, used by default by the run scripts and the app |
| P2 observations | storey counts accepted for P2 (recorded as estimated); P0/P1 still need measured or documented heights |
| Approval workflow | removed from the interface; the approval lock became the research-baseline fingerprint; readiness gates became scientific status indicators |
| Configuration | the Run simulation page edits transmit power, antenna, threshold, target, load, resolution, rays, rain and candidate criteria, with range checks and a reset to the baseline |

## 4. What is still missing (data and validation, not approvals)

- Field observations: P0-P1 0 of 4, P2 0 of 34, S 0 of 43; the dataset is not fit for research.
- Candidate pool: 1 candidate with today's heights (target 20-40), needs the survey.
- Convergence on the final scene; MATLAB cross-check; laptop benchmark.
