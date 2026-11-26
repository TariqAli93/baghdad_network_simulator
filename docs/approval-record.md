# Approval record

Machine-readable version: `configs/approvals.yaml`. Configuration states updated accordingly
(`configs/radio_system.yaml`, `configs/simulation.yaml`, `configs/study_area.yaml`,
`configs/site_rule.yaml`).

| | |
|---|---|
| What was approved | Every **recommended option** of `docs/supervisor-checklist.md`, as written |
| Checklist version | commit `bc750b3` (tag `v1.0.0-rc.1`) |
| Reported by / on | the project owner, 2026-11-26 |
| Approval reference | **none provided** — a written confirmation (e-mail or signed minutes) is a remaining condition |
| Recorded by | the software maintainer, 2026-11-26; nothing beyond the recommended options was recorded |

## Approved decisions

| ID | Approved option | Condition still open |
|---|---|---|
| A1 | Study district Tahrir Square / Bab Al-Sharqi: centre 33.3280 N 44.4085 E, 1 km × 1 km receiver area, 150 m margin (area `tahrir_bab_al_sharqi_study`, snapshot `tahrir_bab_al_sharqi_v2`, SHA-256 852683848789…) | The recommendation was conditional on the student being able to observe the tall buildings |
| A2 | OSM footprints plus footprints missing from OSM taken from 3D-GloBFP (footprints only); height priority observation > OSM height > OSM storeys × 3.0 m > dataset > model > placeholder; no external dataset as the height source; observe the worklist buildings; missing heights covered by the height sensitivity analysis; GlobalBuildingAtlas only if its licence fits, never redistributed | **Field observations not collected** (worklist: 330 buildings, `outputs/datasets/tahrir_bab_al_sharqi_study/height_worklist.csv`) |
| A3 | All radio parameters as proposed: 46 dBm conducted, TR 38.901 sector element (8 dBi, traced), 3 sectors, 10° downtilt, isotropic receiver at 1.5 m, noise figure 9 dB at 290 K, coverage SINR ≥ −10 dB on 95 % of outdoor cells, reuse 1, load 1.0 | — |
| A4 | Candidate roofs with observed or storey-based heights; minimum height and spacing chosen for 20-40 candidates; 3 m mast; azimuths 0/120/240°, 10° downtilt; antennas at the roof edge facing each sector | The minimum height and spacing can only be set once observed heights exist |
| B1 | Controlled TR 38.901 comparison kept; MATLAB agreement = median \|Δ\| in LOS cells within the profile's convergence floor, with RMSE | MATLAB not yet executed |
| B2 | Engine limitations accepted as documented; 2-3 MATLAB cases on reflection-then-diffraction streets | Those cases are not prepared yet (they need the final scene) |
| B3 | Shannon upper bound plus the 3GPP truncated mapping (α 0.6, −10…30 dB, TR 38.921) beside it | — (implemented) |
| C6 | CPU for thesis results; GPU for exploration only | — |
| Convergence | Standard profile (10 m, 1e9 rays) accepted for final runs | — |
| MATLAB | Required before conclusions, with the B1 criterion | Laptop run pending |
| Laptop | Measured laptop run times accepted as the time budget | Laptop not measured yet |

## What the approval changed in the software

- Configuration states set to `approved` with `approved_by` naming this record.
- Implemented because they were approved: roof-edge antenna placement (A4,
  `configs/site_rule.yaml`), missing-footprint import (A2, `build_dataset.py --add-footprints`),
  the 3GPP truncated rate beside Shannon (B3).
- Research mode now also refuses a dataset that is not fit for research. Under the approved
  A2 method a dataset becomes fit when the method is approved **and** every REQUIRED building
  (configured worklist and priorities, `configs/study_area.yaml`) has a valid fieldwork
  observation — measured or documented heights are recorded as observed, storey counts and
  visual estimates as estimated (placeholders elsewhere are then reported through the
  sensitivity analysis). Today the study dataset is not fit: 0 of 190 required buildings observed.

## Status classification (review 2026-11-27)

| Kind | Decisions | Evidence |
|---|---|---|
| Explicitly approved in writing | **none** | no written reference has been supplied |
| Reported as approved (all recommended options, as written) | A3 values, B1, B2, B3, C6, convergence profile, MATLAB requirement | the project owner's report of 2026-11-26 |
| Approved with an open condition | A1 (observability of the tall buildings), A2 (observations not collected), A4 (thresholds need observed heights), laptop (not measured) | conditions in `configs/approvals.yaml` |
| Inferred or implementation choices (not approved as such) | 1 m inset from the roof edge; the B1 tolerance as a number (the "convergence floor" of the standard profile is 1.4-2.0 dB); the worklist settings of `scripts/height_worklist.py`; P0-P3 prioritisation and the reduced set; excluding monuments from candidates | software decisions, listed for confirmation |

### Exact values still to be confirmed by the supervisor

1. A written approval reference (e-mail or signed minutes) for the recommended options.
2. B1: the MATLAB agreement tolerance as a number (proposal: median |Δ| in LOS cells ≤ 2.0 dB).
3. B3: one mapping for all bands (TR 38.921, cap 30 dB) or the LTE mapping of TR 36.942 for the
   4G scenario (cap 4.4 bit/s/Hz) (`docs/rate-mapping-verification.md`).
4. A2: whether the reduced observation set P0-P2 (+ S storey counts) may replace the full
   worklist (`docs/fieldwork-prioritisation.md`).
5. A4: candidate minimum roof height and spacing, after stage-1 observations; the 1 m inset;
   the exclusion of monuments, memorials and artworks from candidate roofs.
6. GlobalBuildingAtlas: not used (no licence decision needed unless it is to be used).
