# Supervisor approval checklist (release candidate v1.0.0-rc.1)

One page to decide from. Details and the full evidence are in `docs/supervisor-decisions.md`;
numbers below are from **development runs** (provisional area, unapproved inputs). **Nothing
is approved** until the box is ticked and the value is entered in the configuration file
named in the last column (with `status: approved`, `approved_by`).

Status key: ☐ open · ☑ approved (write the decision and date).

## A. Before the final experiments

### A1 — Study district

| | |
|---|---|
| Recommended | Keep **Tahrir Square / Bab Al-Sharqi** (centre 33.3280 N, 44.4085 E; 1 km × 1 km receiver area, 150 m building margin) **only if** the student can observe its tall buildings; otherwise a district the student can survey |
| Evidence | 899 OSM buildings in the receiver area, heights tagged on 8; about a third of the built area missing from OSM; no surveyed district has better height data (`docs/study-area-evaluation.md`) |
| Alternatives | Old Rusafa, Palestine Street, a surveyable district |
| Impact | Every result; one entry in `configs/study_area.yaml` (role `study district`, `approved: true`), a new snapshot, a rebuilt dataset |
| To decide | ☐ district ☐ exact boundary (centre, size, margin) ☐ justification sentence for the thesis |

### A2 — Building data

| Item | Recommended | Evidence | Alternatives | Status |
|---|---|---|---|---|
| Footprint source | OSM, plus the missing footprints from a second source with provenance | ≈ 577 footprints / 124,000 m² missing in the receiver area | 3D-GloBFP footprints (CC BY 4.0, have them); GBA ODbL polygon tile (2.1 GB, **not downloaded**, needs approval); map in JOSM; choose a complete district | ☐ |
| Height source and priority | Observation > OSM height > OSM storeys × storey height > dataset > approved model > placeholder | implemented and configurable (`configs/study_area.yaml`) | — | ☐ |
| Storey height | 3.0 m | common assumption, no local source | 3.2-3.5 m | ☐ |
| Datasets | Neither external dataset as the height source | 3D-GloBFP +26 m too high where tagged; GBA capped near 21 m (tower 55 m → 5.4 m) | GBA as a low-rise sensitivity case | ☐ |
| Missing heights | Report the spread over assumed height models (sensitivity) | heights moved LOS coverage 86 % → 67 % on identical sites | single placeholder | ☐ |
| Manual verification | Observe the worklist buildings: tall ones, candidate roofs, conflicts, near sites (`scripts/height_worklist.py`) | tall buildings decide coverage; the tower and a 12 m structure conflict between sources | — | ☐ |
| Licensing | Use GBA only if its CC BY-NC 4.0 licence fits the project's use; never redistribute its values | `docs/licensing.md` | drop GBA entirely | ☐ |

### A3 — Radio parameters (same for all five bands: a controlled experiment)

| Parameter | Proposed | Source | Impact | Status |
|---|---|---|---|---|
| Transmit power | 46 dBm conducted per sector carrier | 3GPP TR 38.914, TR 36.942, ITU-R M.2292, TR 38.921 | shifts all received power | ☐ |
| Antenna | 3GPP TR 38.901 sector element (8 dBi, 65°, traced), 3 sectors, 10° downtilt, no array gain | TR 38.901 Table 7.3-1, M.2412 | pattern is traced: changing it re-traces | ☐ |
| Receiver | isotropic, 1.5 m | project description | — | ☑ (1.5 m, project description) |
| Noise figure / temperature | 9 dB / 290 K | TR 38.921, ITU-R P.372 | sets the noise floor | ☐ |
| **Coverage threshold** | SINR ≥ −10 dB | TR 38.921, TR 36.942 (lowest SINR with a rate) | **decides the site count**: at 0 dB, full load, 4 sites cover 82 % vs 100 % for 1 (1.8 GHz) | ☐ |
| Coverage target | 95 % of outdoor cells | TR 38.830 Table A.3 | stopping point of site planning | ☐ |
| **Network load** | 1.0 (full buffer) | ITU-R M.2412; M.2292 uses 0.5 | **decides the site count** with the threshold | ☐ |
| Interference | reuse 1, co-located sectors interfere, strongest sector serves, no scheduler | M.2412, M.2292 | worst case | ☐ |

Sensitivity (development): site counts 1/1/1/1/2 (1.8/3.5/8/15/28 GHz) at −10 dB and full load;
1/1/1/2/3 at 0 dB. Choose threshold and load **on their merits before seeing final results**.

### A4 — Site rule

| Item | Recommended | Evidence | Alternatives | Status |
|---|---|---|---|---|
| Candidate roofs | Buildings with observed (or storey-based) heights, minimum height and spacing chosen for 20-40 candidates | a site on an unknown roof has an unknown antenna height | all roofs with placeholder heights (development only) | ☐ |
| Mast height | 3 m (no source found) | 3GPP layouts use 25 m total heights on flat terrain | 5-6 m | ☐ |
| Sector orientation | 0°, 120°, 240° azimuth, 10° downtilt | standard three-sector site | optimised azimuths (out of scope) | ☐ |
| **Antenna position on the roof** | **At the roof edge facing each sector** | controlled experiment: 28 GHz uncovered cells within 250 m 32.4 % (centre) → 2.3 % (edge) (`docs/validation.md` §10) | roof centre (current code) | ☐ |

## B. Before the conclusions

| ID | Decision | Recommended | Status |
|---|---|---|---|
| B1 | Validation scope and agreement | Keep the controlled TR 38.901 comparison (done; UMa LOS within σ, NLOS mismatch reported, not explained away); agree a MATLAB criterion, e.g. median \|Δ\| in LOS cells within the profile's convergence floor, reported with RMSE | ☐ |
| B2 | Engine limitations | Accept as documented (first-order diffraction, no reflection-then-diffraction, non-coherent power, opaque buildings); add 2-3 MATLAB cases on reflection-then-diffraction streets | ☐ |
| B3 | Rate reporting | Shannon upper bound as in the project description; the 3GPP truncated mapping (0.6, −10…30 dB, TR 38.921) beside it is **not implemented** (feature freeze); implement only if approved | ☐ |

## C. Engineering decisions with research impact

| ID | Decision | Recommended | Evidence | Status |
|---|---|---|---|---|
| C6 | GPU backend for research runs | No for thesis results (laptop has no NVIDIA GPU; validation is on CPU); yes for exploration | GPU vs CPU: path gain 0.03 dB median, no coverage-class change, 16× faster | ☐ |
| Convergence | Accept the standard profile (10 m, 1e9 rays, "borderline": two independent maps within 1.4-2.0 dB for 95 % of cells) for final runs, or require more rays/seed averaging | `docs/convergence.md` | ☐ |
| MATLAB | Required before conclusions: run the prepared case on the laptop; agree the criterion (B1) | package `validation/matlab/` | ☐ |
| Laptop | Accept the measured laptop run times (to be recorded with `benchmark.ps1`) as the time budget | `docs/laptop-acceptance.md` | ☐ |

## After approval

Enter each value in `configs/radio_system.yaml`, `configs/study_area.yaml`,
`configs/simulation.yaml` with `status: approved` and `approved_by`, then follow
`docs/research-execution-plan.md`. Research mode refuses to run unless the study area, every
radio parameter it uses, the simulation profile (status `approved`) and the backend
(status `production`) are approved.
