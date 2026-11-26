# Approval record

Machine-readable version: `configs/approvals.yaml`; fingerprints of the approved values:
`configs/approval_lock.yaml`. Configuration states: `configs/radio_system.yaml`,
`configs/simulation.yaml`, `configs/study_area.yaml`, `configs/site_rule.yaml`,
`configs/atmosphere.yaml`.

| | |
|---|---|
| Report 1 | 2026-11-26, the project owner: the supervisor accepted every **recommended option** of `docs/supervisor-checklist.md` as written (checklist version: commit `bc750b3`, tag `v1.0.0-rc.1`) |
| Report 2 | 2026-11-27, the project owner: the supervisor approved the **follow-up recommendations** of the 2026-11-27 review (commits `95f12ff`, `dac5d86`) |
| Approval reference | **none provided** for either report — a written confirmation (e-mail or signed minutes) is a remaining condition |
| Supervisor identity | not recorded (not supplied) |
| Recorded by | the software maintainer, 2026-11-26 and 2026-11-27; nothing beyond the reported options was recorded |

## 1. What was approved, and when

"Original" = the recommended option of the checklist (report 1). "Changed" = a later approved
change or addition (report 2). Exact values are in the configuration files named.

| ID | Original recommendation (2026-11-26) | Approved change or addition (2026-11-27) | Where |
|---|---|---|---|
| A1 | Tahrir Square / Bab Al-Sharqi: centre 33.3280 N 44.4085 E, 1 km × 1 km receiver area, 150 m margin, if its tall buildings can be observed | — | `study_area.yaml` (`tahrir_bab_al_sharqi_study`, snapshot `tahrir_bab_al_sharqi_v2`) |
| A2 footprints | OSM plus the footprints missing from OSM from a second source | 3D-GloBFP **footprints** (not its heights); footprint and height provenance kept separate | `study_area.yaml` `footprint_sources`; `build_dataset.py --add-footprints 3d_globfp` |
| A2 heights | observation > OSM height > OSM storeys × 3.0 m > dataset > model > placeholder; no external dataset as the height source; sensitivity for missing heights | external dataset only if separately authorised (none is); GlobalBuildingAtlas not the primary height source | `study_area.yaml` `height_policy` |
| A2 observations | observe the worklist buildings (190: P0-P3, after the monument correction) | **reduced fieldwork, initial stage:** P0-P2 (38) + candidate survey S (43) = 81; P3 (152) through the height sensitivity analysis; the 190-building list stays on record | `study_area.yaml` `observations` (with `history`) |
| A3 | 46 dBm conducted per sector carrier; TR 38.901 sector element (8 dBi peak, 65°, traced); 3 sectors; 10° downtilt; no array gain; isotropic receiver at 1.5 m; NF 9 dB at 290 K; SINR ≥ −10 dB on 95 % of outdoor cells; reuse 1, load 1.0, co-located sectors interfere, strongest sector serves, no scheduler; clear sky | — | `radio_system.yaml` |
| A4 | candidates with observed or storey-based heights; minimum height and spacing for 20-40 candidates; 3 m mast; 0/120/240°, 10°; antennas at the roof edge facing each sector | **1 m inset** from the edge; **monuments, memorials and artworks never candidates** (kept as obstacles); minimum roof area added to the pending thresholds; the existing SINR greedy | `site_rule.yaml` |
| B1 | keep the TR 38.901 comparison; MATLAB criterion "median \|Δ\| in LOS cells within the convergence floor", with RMSE | **median \|Δ\| in LOS cells ≤ 2.0 dB**, RMSE and NLOS reported separately; MATLAB stays an external cross-check | `approvals.yaml` (`los_median_abs_tolerance_db`) |
| B2 | limitations accepted; 2-3 MATLAB reflection-then-diffraction cases | — | — |
| B3 | Shannon bound plus the TR 38.921 truncated mapping for all bands | **per band:** LTE (TR 36.942, cap 4.4 bit/s/Hz) for 4G; NR (TR 38.921) for 5G; NR values as a labelled research approximation for candidate 6G | `radio_system.yaml` `rate_mappings`, `scenario_rate_mapping` |
| C2-C5 | optional sensitivity experiments | kept as optional sensitivity cases, never the baseline: rain 18.6 mm/h (older ITU map edition, qualified), equal power per MHz, 50 % load, height uncertainty, array gain by link-budget arithmetic only | `atmosphere.yaml` (18.6 mm/h `approved: true`, sensitivity only) |
| C6 | CPU for thesis results; GPU for exploration | GPU and auto for development only | `simulation.yaml` `research_backend: cpu` |
| Convergence | standard profile 10 m / 1e9 rays | must be evaluated again on the final scene; preview 25 m / 1e8 for development; research 5 m disabled | `simulation.yaml` `final_scene_convergence` |
| MATLAB | required before conclusions, with the B1 criterion | — | `validation/matlab/` |
| Laptop | measured run times accepted as the time budget | — | `docs/laptop-acceptance.md` |

## 2. Implementation status (2026-11-27)

| Item | Implemented | Verified by |
|---|---|---|
| Per-band rate mappings | `bns.analysis.rate_models`, `link_budget.truncated_shannon_bps` (NR cap at SINR_MAX, LTE cap at Thr_MAX) | unit tests reproduce TR 36.942 Table A.2 DL rows and TR 38.921 Table 4.2.7-1 (`docs/rate-mapping-verification.md`) |
| Reduced fieldwork | required priorities `[P0, P1, P2, S]`; dataset rebuilt (scene fingerprint unchanged), now "0 of 81 observed" | `tests/unit/test_readiness.py` |
| Roof-edge placement, 1 m inset | since 4928b4f (`sites.edge_positions`) | unit tests; antenna-placement experiment (`docs/validation.md` §10) |
| Monument exclusion | since dac5d86 (`sites.is_structure_not_building`); 8 runs invalidated | unit tests; `configs/invalidated_runs.yaml` |
| Approval lock | an approved value that changes is no longer approved until reconfirmed (`bns.analysis.approval_lock`, `scripts/approval_lock.py`) | `tests/unit/test_approval_lock.py` |
| Readiness gates | eight gates computed from files (`bns.analysis.readiness`); research refuses until the five pre-experiment gates pass | `tests/unit/test_readiness.py`; the app's Overview page |
| Research guard in `run_single_site.py` | **defect fixed**: research mode skipped the profile, dataset and readiness checks; it now applies them and refers research single-site runs to `run_multi_site.py` (the approved roof-edge rule) | manual run: refused with the gate reasons |

## 3. Remaining conditions (approvals not yet unconditional)

| Gate | State today | What clears it |
|---|---|---|
| Methodology approval | reported (no written reference) | the written reference |
| Dataset fitness | not met: 99.4 % placeholder heights | the stage-1 observations imported and the dataset rebuilt |
| Mandatory observations | not met: 0 of 81 (P0 3, P1 1, P2 34, S 43) | field observations (`outputs/datasets/tahrir_bab_al_sharqi_study/fieldwork/`) |
| Candidate-site criteria | not met: minimum roof height, area and spacing pending | supervisor's values after stage 1, entered in `site_rule.yaml` and locked |
| Final-scene convergence | not executed | `run_convergence.py` on the final scene and the supervisor's acceptance |
| MATLAB validation | not executed | the laptop run, assessed with B1 (≤ 2.0 dB) |
| Laptop acceptance | not executed | `benchmark.ps1` on the target laptop |
| Final delivery | not met | all of the above |

The first five are pre-experiment conditions: research mode refuses until all pass.

## 4. Not specified by the supervisor (left empty, never invented)

1. A written approval reference for both reports.
2. Minimum candidate roof height, minimum roof area and minimum spacing (after stage 1).
3. The reference direction of the sector azimuths: implemented in the ray tracer's scene frame,
   counter-clockwise from east (0/120/240° = compass bearings 90/330/210°). Confirmation only;
   nothing was changed.

## 5. Changing an approved value

1. Edit the value in its configuration file. From then on `scripts/approval_lock.py` reports it
   as `changed`, the app shows "approval void", and research mode refuses it.
2. Obtain the supervisor's reconfirmation and record it here and in `configs/approvals.yaml`.
3. Renew the lock: `uv run python scripts/approval_lock.py --record --confirmed-by "..." --confirmed-on YYYY-MM-DD`.

## 6. Status classification

| Kind | Items |
|---|---|
| Explicitly approved in writing | **none** (no written reference supplied) |
| Reported as approved, unconditional | A3 values, B3 per-band mappings, C6, sensitivity cases (as sensitivity only) |
| Reported as approved with an open condition | A1, A2, A4, B1, B2, convergence, MATLAB, laptop (section 3) |
| Implementation choices still unconfirmed | the worklist settings of `scripts/height_worklist.py`; the azimuth reference direction |
