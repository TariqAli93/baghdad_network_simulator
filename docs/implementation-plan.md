# Implementation plan and progress

Phases follow the master brief. A phase starts only after the previous gate is accepted.
Each phase ends with: completed work, files, tests actually run, limitations, measurements,
blockers, next phase.

| Phase | Subject | Status |
|---|---|---|
| 0 | Feasibility and environment audit | **Done on the development PC; laptop rerun pending** |
| 1 | Literature and standards review | **Done (2026-11-26)**, tag `v0.2.0-literature-review`; student to read and confirm the sources |
| 2 | Study area and 3D city model | **Technically ready (2026-11-26); not scientifically complete** until the district and the height methodology are approved |
| 3 | Radio scenario configuration | **Technically done (2026-11-26)**; sourced proposal awaiting approval (A3) |
| 4 | Production ray-tracing pipeline | **Technically done (2026-11-26)**; standard profile corrected after convergence check |
| 5 | Single-site coverage | Development run done on all five bands; research runs wait for A1-A3 |
| 6 | Multi-site SINR and data rate | Calculation done and tested; used for the three sectors of one site; multi-site runs not yet made |
| 7 | Scientific validation (3GPP TR 38.901, MATLAB cross-check) | Not started |
| 8 | Base-station site planning (greedy) | Greedy selection function done and tested; used in the height-sensitivity experiment |
| 9 | Comparative analysis | Not started |
| 10 | 6G roadmap workspace | Not started |
| - | Streamlit application | Not started (after the simulation core is validated) |

---

## Phase 0 report (2026-11-26)

### Completed

- Read the project description and audited the machine (details in `docs/benchmarks.md`).
- Engine selected and proven on the CPU: Sionna RT 2.2.0, LLVM 18.1.8, no GPU used.
- Reproducible environment: `pyproject.toml`, `uv.lock`, `requirements.lock`, Python 3.13.
- Proof of concept: OSM snapshot -> cleaned footprints -> 3D scene -> path-gain maps, with
  five experiments (E1-E5) and a benchmark, all run from the command line.
- Two engine problems found, measured and worked around:
  1. **Unstable kernel compilation on Windows** -> every simulation runs in a worker process
     and only clean exits count (`bns.runtime.run_isolated`).
  2. **Sionna's default wedge table loses diffracted power in city scenes** (1.3 dB on the
     test box) -> table enlarged from 10,000 to 1,048,576 slots.
- One data problem found: **OpenStreetMap has almost no building heights in Baghdad**
  (97 % of the test box uses a 9 m placeholder).

### Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project rules and commands |
| `pyproject.toml`, `uv.lock`, `requirements.lock`, `.python-version`, `.gitignore` | Environment |
| `configs/scenarios.yaml` | The five scenarios |
| `src/bns/runtime.py` | CPU bootstrap, memory cap, CPU topology, isolated workers |
| `src/bns/core/units.py` | Unit conversions, Friis, thermal noise |
| `src/bns/validation/analytic.py` | Closed-form references |
| `src/bns/geospatial/osm_scene.py` | OSM -> footprints -> meshes -> scene; indoor mask |
| `src/bns/propagation/sionna_engine.py` | Path-gain maps |
| `src/bns/reporting/plotstyle.py` | Chart style |
| `scripts/build_poc_scene.py`, `poc_validate.py`, `poc_benchmark.py` | Phase 0 command line |
| `tests/unit/*`, `tests/scientific/test_engine_sanity.py` | Tests |
| `docs/architecture.md`, `assumptions.md`, `benchmarks.md`, this file | Documentation |
| `data/raw/osm/tahrir_bab_al_sharqi.json` (+ `.meta.json`) | Immutable OSM snapshot with SHA-256 |

### Tests and experiments executed

See `docs/benchmarks.md` for every number. Summary:

| Check | Result |
|---|---|
| Unit tests (`uv run pytest`) | 44 passed |
| Engine tests (`uv run pytest -m engine`) | 3 passed |
| E1 free space vs Friis, five bands | Pass |
| E2 ground reflection vs Fresnel slab, both polarisations, Brewster dip | Pass |
| E3 diffraction vs knife-edge theory and frequency scaling | Pass |
| E4 Baghdad block: mechanism ladder, five bands, scene-size invariance | Pass (after enlarging the wedge table) |
| E5 rays needed per cell size | Informative |
| Benchmark under a 10 GB memory cap | Completed; 20 of 20 repeat runs clean; 90 maps back to back without slowdown |

### Feasibility gate

| Criterion | Outcome on the development PC |
|---|---|
| Analytic checks E1, E2 within tolerance | Met |
| Diffraction check E3 within tolerance | Met |
| Mesh checks pass on the Baghdad scene | Met (0 non-manifold edges, 0 degenerate triangles) |
| 1 km², 10 m cells, 2 reflections + diffraction, one site and band, peak memory <= 8 GB | Met with a wide margin (under 1 GB) |
| No crash in 20 consecutive runs | Met for runs that compile nothing; first-time compilation needs retries |
| Full study fits an acceptable time on the **laptop** | **Open: must be measured on the laptop** |

**Recommendation: proceed with Sionna RT.** The gate is passed on the proxy machine; it is
formally closed once the laptop rerun (below) is in and the supervisor has seen the two
engine limitations and the building-height gap.

### Limitations

- Benchmarked on a desktop proxy, not the laptop. The desktop cools better; laptop times
  will be longer.
- Radio-map diffraction is first-order and never follows a reflection.
- Diffraction is the noisy part of a map: the ray count must rise with finer cells (E5).
- First run of each new configuration may need several attempts because of the compiler
  instability; this costs time, not correctness (unclean runs are discarded).
- All Baghdad numbers use placeholder heights and are **not findings**.
- 8 buildings mapped as OSM relations are not read yet.
- No transmit power, noise, SINR, rain or gas loss yet: Phase 0 is path gain only.

### To close Phase 0 (student, on the laptop)

1. Install LLVM: `winget install --id LLVM.LLVM -e --version 18.1.8`
2. Install `uv`, copy the project folder, then `uv sync`
3. `uv run python scripts/build_poc_scene.py` (reuses the stored OSM snapshot)
4. On AC power: `uv run python scripts/poc_validate.py all`
5. `uv run python scripts/poc_benchmark.py --mem-cap-gb 10`
6. Send back `outputs/runs/phase0/benchmark/summary.json` and the `result.json` files.

### Next phase

Phase 1 (literature and standards review) and, in parallel with the supervisor, the
decisions listed in `docs/assumptions.md` section 6 — first of all the study district and
the source of building heights, which blocks Phase 2.

---

## Phase 1 report (2026-11-26)

Started at the user's request while the Phase 0 laptop rerun is still pending; Phase 1 is
desk research and does not depend on it.

### Completed

- **Reference registry** (`docs/references.md`): 47 entries covering the ITU IMT-2020 and
  IMT-2030 framework, WRC-27 agenda item 1.7 and regional positions, the 3GPP 6G timeline
  and requirements, band definitions, 3GPP TR 38.901 (exact UMa and UMi formulas and their
  validity limits), the ITU-R recommendations for materials, diffraction, gases and rain,
  the ray-tracing method papers, and the Iraqi market and spectrum sources. Each entry says
  how it was checked.
- **Related studies** (`docs/related-studies.md`): ten studies compared, three alternates,
  four studies on Iraq, and what they imply for this project.
- **Project description checked** against primary sources: eight statements examined, one
  not supported, four needing corrected wording (`docs/references.md`, section 9).
- `configs/scenarios.yaml`: each scenario's basis rewritten from the verified sources and
  linked to registry entries. Frequencies and bandwidths are unchanged.
- `docs/assumptions.md`: section 5 now holds the verification results; six decisions added
  to the list for the supervisor.

### How it was verified

1. Four research passes, each restricted to documents it actually opened, with a URL per
   claim and explicit "not verified" marks.
2. Bibliographic data of 36 papers confirmed against Crossref or arXiv records by script
   (one accepted manuscript has no record yet).
3. A second, independent reader re-read the 44 figures quoted from the 13 main studies:
   all present in the sources, three needing caveats (recorded in the table).
4. Pivotal facts re-checked by separate searches: the Release 21 timeline and the
   Resolution 256 regional split were confirmed; for the Iraqi 5G claim, the cited article
   and the Asiacell lab announcement were confirmed to exist and no corroboration of a Zain
   launch was found; the regulator interview of 25 November could not be found a second time.

### Files

| File | Change |
|---|---|
| `docs/references.md` | New |
| `docs/related-studies.md` | New |
| `docs/assumptions.md` | Sections 5 and 6 updated |
| `configs/scenarios.yaml` | Basis text and `sources` per scenario |
| `tests/unit/test_references.py` | New: scenarios cite existing registry entries; candidate carriers fit inside the bands under study |
| `src/bns/validation/analytic.py` | Docstring now names the ITU equations it implements |

### Tests

`uv run pytest`: 49 passed (5 new). No simulation code changed, so the engine tests and
experiments were not rerun.

### Findings that change the thesis

- **No commercial 5G launch in Iraq could be confirmed as of November 2026**; the project
  description's opening statement rests on one uncorroborated article.
- Region 1's part of the 7-8 GHz band is 7.125-7.25 and 7.75-8.4 GHz. The 8 GHz and 15 GHz
  scenario carriers fit inside the bands under study.
- 400 MHz is the agreed maximum carrier for the 7 GHz range; for 15 GHz it is only an
  evaluation assumption.
- The 3GPP UMa and UMi formulas are defined for base stations at 25 m and 10 m: rooftop
  sites at other heights are outside their stated range.
- Gas loss is negligible at all five bands. Rain loss cannot be stated until a rain rate for
  Baghdad is obtained.
- Published ray-tracing comparisons with measurements show errors of 8-21 dB; site counts
  must be presented as estimates.
- No published study answers the project's research question, and none ray-traces Baghdad.

### Limitations

- The review was done by automated research passes. It maps the literature and verifies
  facts; it does not replace the student reading the sources, which the thesis requires.
- Several sources are 2026 preprints or accepted manuscripts and may change.
- Some pages were read through a summarising tool; those entries are marked "Page".
- The newest Iraqi 5G items are one day old and rest on single press sources.
- Paywalled papers were read as preprints or author copies where available.

### Open items

- Rain rate for Baghdad (ITU-R P.837-8 digital maps, or from the supervisor).
- The ITU report with 6G technical requirements is due for approval on 1 December 2026.
- Iraq's own position on WRC-27 agenda item 1.7.
- Phase 0 laptop benchmark (unchanged).

### Next phase

Phase 2 (study area and 3D city model) is blocked on the supervisor's choice of district and
of the source of building heights (`docs/assumptions.md`, section 6, item 1).

---

## Phase 2 report (2026-11-26)

**Status: technically ready, not scientifically complete.** The geospatial pipeline works
for any area and was exercised on the development fixture. It becomes scientifically
complete only when the supervisor has approved the study district (D1) and the
building-height methodology (D2) and a dataset is built for that district.
The Phase 0 laptop acceptance gate is still open.

### Completed

- **Phase 1 closed**: commit `7136ee3` "docs: complete literature review and standards
  verification", tag `v0.2.0-literature-review`, after the full suite passed.
- **Corrections record** (`docs/project-description-corrections.md`): 13 corrections with
  original statement, corrected statement, source, date and impact; the PDF is unchanged and
  the five scenarios are unchanged.
- **Reusable geospatial pipeline** (`bns.geospatial`, `scripts/build_dataset.py`):
  configurable study areas; OpenStreetMap extraction with a hashed local snapshot; local
  metric coordinates; footprint validation and repair; multipolygon relations; height
  provenance per building; missing-height detection; rooftop candidates; outdoor receiver
  grid; 3D scene for Sionna RT; quality report.
- **Height provenance**: every building has identifier, footprint, height, source, method,
  category (observed / estimated / placeholder), uncertainty where the source gives one,
  reference, and the untouched original values. Observations and height models add a new
  record on top; nothing is overwritten.
- **Building-height investigation** (`docs/building-height-data.md`): twelve sources
  examined; five measured in the test area.
- **Height sensitivity framework** (`scripts/run_height_sensitivity.py`) with seeded,
  configurable height models, run on the fixture.
- **Calculation core** (`bns.analysis`, `bns.optimization`): received power, SINR,
  interference aggregation, Shannon rate, coverage, percentiles, CDF, RMSE, greedy site
  selection; radio parameters in a config where each is undecided, provisional or approved.
- **Rain and gas losses** (`bns.propagation.atmosphere`, `docs/atmospheric-losses.md`):
  ITU-R P.838-3 implemented and checked against its table; gas values stored for the five
  bands; clear sky as the documented baseline; rain as unapproved sensitivity cases.
- **Supervisor decisions** (`docs/supervisor-decisions.md`): eleven decisions with options,
  recommendation, justification, impact and what each blocks.

### Files

| File | Purpose |
|---|---|
| `configs/study_area.yaml`, `height_models.yaml`, `radio_system.yaml`, `atmosphere.yaml` | New configuration, each value marked approved or not |
| `src/bns/geospatial/study_area.py`, `osm_source.py`, `heights.py`, `sites.py`, `grid.py`, `quality.py`, `pipeline.py` | New |
| `src/bns/geospatial/osm_scene.py` | Footprint cleaning split into two steps so per-building records survive it |
| `src/bns/analysis/link_budget.py`, `metrics.py`, `sensitivity.py`, `radio_system.py` | New |
| `src/bns/optimization/greedy.py` | New |
| `src/bns/propagation/atmosphere.py` | New |
| `src/bns/propagation/sionna_engine.py` | `Grid` moved to `bns.geospatial.grid` (no behaviour change) |
| `scripts/build_dataset.py`, `run_height_sensitivity.py`, `atmosphere_table.py` | New |
| `tests/unit/test_link_budget.py`, `test_metrics.py`, `test_greedy.py`, `test_geospatial_pipeline.py`, `test_atmosphere.py`, `test_sensitivity.py`, `test_radio_system.py`, `tests/conftest.py` | New, written before the code they test |
| `docs/project-description-corrections.md`, `supervisor-decisions.md`, `building-height-data.md`, `atmospheric-losses.md` | New |
| `docs/architecture.md`, `assumptions.md`, `references.md`, `CLAUDE.md`, this file | Updated |
| `outputs/datasets/tahrir_bab_al_sharqi/osm/quality_report.*`, `outputs/runs/height_sensitivity/…/summary.*`, `outputs/atmosphere/loss_table.*` | Results of the runs below |

### Review before commit

- Duplicated logic removed: the Phase 0 helpers `resolve_height`, `indoor_mask` and
  `local_transformer` now delegate to `heights.height_from_osm_tags`, `grid.footprint_mask`
  and `study_area.local_transformer`. The Phase 0 scene rebuilds identically (453 solids,
  9,873 triangles, 7,149 wedges). The Phase 0 OSM reader is kept, marked as frozen.
- Static check (ruff, rules F and B): no unused imports or undefined names.
- Re-running the Phase 0 experiments during Phase 2 changed only timings and float noise
  (about 1e-7 dB in the values inspected); the committed Phase 0 records were kept, not
  replaced.

### Tests and runs executed

| Check | Result |
|---|---|
| `uv run pytest` | 158 passed (109 new) |
| `uv run pytest -m engine` | 3 passed |
| `scripts/build_dataset.py --area tahrir_bab_al_sharqi` | 1,186 buildings; same mesh as Phase 0 (9,873 triangles, 7,149 wedges, 0 defects) |
| `scripts/run_height_sensitivity.py` (4 height models, 4 sites, 3.5 GHz) | Completed, each variant on the first attempt, 45-59 s per variant |
| `scripts/atmosphere_table.py` | Completed |

New code was written test-first; each new test file was run and seen to fail before its
implementation existed. Three small tests (`load_buildings`, height-policy loading, the
repository's rain cases) were added after their functions and passed immediately.

### Measurements

- **Fixture data quality**: heights observed for 0.8 % of buildings (1.8 % of footprint
  area), estimated from storeys for 0.3 % (2.7 %), placeholder for 98.8 % (95.5 %).
  The dataset is reported as not fit for research.
- **Height sensitivity** (illustrative, unapproved models): line of sight to any site
  67-86 %; sites needed for 95 % coverage at a 110 dB threshold: 2, 3, or not reached with
  the 4 available sites, depending only on the height model.
- **Height datasets in the test area**: medians 6.3 m (GlobalBuildingAtlas) to 13.2 m
  (GHSL); the 55 m tower appears as 5-15 m in all of them.
- **Rain candidate** (previous ITU edition): 18.6 mm/h exceeded 0.01 % of the year, costing
  1.5 dB over 500 m at 28 GHz; gas loss at most 0.1 dB per km.

### Limitations

- The fixture's OSM snapshot was fetched in Phase 0 with a query that omits the geometry of
  multipolygon relations, so its 8 relation buildings are missing. The query is fixed for
  future snapshots; the Phase 0 snapshot is kept unchanged so Phase 0 stays reproducible.
- No reader for an external height dataset exists yet; it waits for the dataset choice.
- Different-height neighbours still share a coincident wall (55 cases on the fixture).
- Gas attenuation is stored for the five scenario bands and the reference atmosphere only.
- The sensitivity run used four sites, because only four tagged buildings in the fixture are
  high enough and far enough apart; it demonstrates the framework, not a site plan.
- Received power, SINR and data rate have been tested as functions but not yet computed on
  real maps: that needs the undecided radio parameters.

### Remaining blockers

| Blocker | Who | Blocks |
|---|---|---|
| Study district (D1) | Supervisor | Final dataset; all research results |
| Height methodology and dataset (D2) | Supervisor; then a download approval | Final dataset; all research results |
| Radio parameters (D3-D7) | Supervisor | Running Phases 5-6 for results (not their code) |
| Phase 0 laptop benchmark | Student | Phase 0 acceptance gate |
| Approval for dataset downloads (205 MB to 2 GB) | User | Measuring 3D-GloBFP; using GlobalBuildingAtlas |

### Acceptance criteria for calling Phase 2 scientifically complete

1. The study district is in `configs/study_area.yaml` with `role: study district` and
   `approved: true`.
2. A fresh snapshot of that district is stored with its hash, relations included.
3. The height methodology is approved and recorded; storey height agreed.
4. No candidate site stands on a building with a placeholder height, and every building
   above an agreed height has an observed height.
5. The district's quality report states the share of each height category and the dataset is
   reported "fit for research", or the remaining placeholder share is explicitly accepted.
6. A height sensitivity run on the district, with approved height sources, is attached.
7. Mesh checks pass (no non-manifold edge, no degenerate triangle).

### Next

Non-blocked work that can continue: single-site coverage maps and their storage (Phase 5
code), the 3GPP TR 38.901 formulas with tests (Phase 7 code), and a reader for whichever
height dataset is approved for download. None of it produces research results until D1-D7
are decided.

---

## Phase 2 finalisation and Phases 3-4 report (2026-11-26)

**Status.** Phase 2: committed (`fa9e351`, tag `v0.3.0-geospatial-pipeline`), technically
ready, **scientifically pending** (district, building data and height method not approved).
Phases 3 and 4: technically done; the radio proposal awaits approval. Phase 0 laptop gate:
**open**. Nothing here is a research result.

### Completed

1. **Building-height datasets.** 3D-GloBFP downloaded with approval (source, licence CC BY 4.0,
   coverage and checksum verified first), study box extracted with a manifest, matched to OSM
   and evaluated: **unsuitable here** (heights 26 m too high on average where tags exist;
   blocks spanning several buildings; the 55 m tower assigned 80 m). No other large dataset
   was downloaded. `docs/building-height-data.md` §9.
2. **Corrected, versioned dataset.** `tahrir_bab_al_sharqi_v2` from a new snapshot; all 8
   multipolygon buildings recovered (7 with courtyards); the Phase 0 fixture unchanged;
   snapshots can no longer be overwritten; repaired building pieces get unique ids.
   `docs/study-area-evaluation.md`.
3. **OSM completeness finding.** About a third of the built area of the receiver area
   (577 footprints, 124,000 m², mostly south-east) is missing from OSM.
4. **Hybrid height resolution.** Configurable priority (observation > OSM height > OSM
   storeys > dataset > approved model > placeholder, with the evidence for putting storeys
   above datasets); every candidate kept as an alternative; conflicts flagged; manual
   overrides; an observation worklist generator.
5. **Phase 3, radio configuration.** Three states per parameter (development, candidate,
   approved) and two run modes; a sourced proposal for every parameter
   (`docs/radio-parameters.md`); conducted power vs EIRP; three forms of gain double counting
   refused; the controlled-experiment methodology written down (`docs/methodology.md`).
6. **Phase 4, production pipeline.** `bns.simulation`: propagation jobs with complete cache
   keys, an atomic path-gain cache, a batching runner with progress, cancellation and crash
   recovery, an engine worker, traced sector antennas, radio results from cached path gain.
   `docs/architecture.md` §7.
7. **Convergence check** on the full area: the standard profile had to be raised from 1e8 to
   1e9 rays; preview set to 25 m / 1e8; research (5 m) left unvalidated. `docs/convergence.md`.
8. **Single-site development experiment** (below).
9. **Supervisor decisions** regrouped into four needed before final experiments, three before
   conclusions, optional refinements and settled technical choices.

### Tests and runs executed

| Check | Result |
|---|---|
| `uv run pytest` | 234 passed (77 new since Phase 2) |
| `uv run pytest -m engine` | 6 passed (3 new: whole-pipeline received power vs Friis + link budget; traced TR 38.901 pattern vs formula; downtilt direction) |
| `scripts/run_convergence.py` | 8 cases, 479 s for the part not already cached |
| `scripts/run_single_site.py --profile standard --mode development` | Completed; 15 traces |
| `scripts/compare_propagation.py` | Completed (fixture vs v2) |
| `scripts/import_height_dataset.py`, `evaluate_height_dataset.py`, `height_worklist.py`, `compare_datasets.py` | Completed |
| Research mode on the provisional area | Refused, as intended |

Coverage of the tests is reviewed in `docs/validation.md` §3, including the tests that were
written in the same step as their code.

### Single-site development experiment

`outputs/runs/development/single_site-tahrir_bab_al_sharqi_v2-osm-standard-20261126T105044Z/`
— **DEVELOPMENT — NOT APPROVED FOR RESEARCH.** Site on the 55 m tower (antenna 58 m, three
sectors, TR 38.901 element, 10° downtilt), 1 km² at 10 m cells, 1e9 rays per sector,
candidate radio parameters, clear sky, provisional area with 98.8 % placeholder heights.

| Scenario | Median received power | Coverage (SINR ≥ −10 dB) | Median SINR | 5th-percentile Shannon rate | Median Shannon rate |
|---|---|---|---|---|---|
| 1.8 GHz, 20 MHz | −41.5 dBm | 99.9 % | 19.9 dB | 31 Mbit/s | 132 Mbit/s |
| 3.5 GHz, 100 MHz | −47.4 dBm | 99.8 % | 19.2 dB | 146 Mbit/s | 639 Mbit/s |
| 8 GHz, 400 MHz | −54.8 dBm | 98.6 % | 15.2 dB | 326 Mbit/s | 2,033 Mbit/s |
| 15 GHz, 400 MHz | −60.4 dBm | 96.1 % | 12.6 dB | 84 Mbit/s | 1,709 Mbit/s |
| 28 GHz, 400 MHz | −65.9 dBm | 89.1 % | 9.7 dB | 15 Mbit/s | 1,344 Mbit/s |

What the pipeline shows (for understanding the method, not as findings): received power
falls by about 24 dB from 1.8 to 28 GHz, as free-space loss predicts; SINR here is limited
by the site's own neighbouring sectors (reuse 1, full load); the 400 MHz carriers have the
highest median rates but the 28 GHz 5th percentile collapses where cells lie below the
downtilted beam. These numbers depend on the unapproved parameters and on placeholder
heights, and would change with real building data.

*Corrected in Phase 5 (below):* the near-site gap is caused mainly by the host roof's own
edge shadowing the ground (3 m mast on a roof about 29 m wide), not by the vertical pattern.

**Timing and memory.** 15 traces: 13 took 57-66 s, two took 216 s and 248 s (cause not
identified; a similar transient slowdown was seen in Phase 0); 31 minutes in total including
first-time compilation and retries. Peak committed memory per worker 0.86 GB; the script
itself 0.62 GB.

### Limitations

- Single site only; multi-site SINR and greedy site selection not yet run on ray-traced maps.
- Standard profile costs about 1 minute per sector and band; site planning at this profile
  needs hours (`docs/convergence.md`).
- The provisional area lacks a third of its buildings and almost all heights.
- The research profile (5 m) is not validated.
- No 3GPP TR 38.901 or MATLAB validation yet.

### Remaining scientific blockers

A1 district, A2 building data (missing footprints, heights, field observations, optional
GlobalBuildingAtlas download), A3 radio parameters, A4 site rule; then B1-B3 before
conclusions (`docs/supervisor-decisions.md`). Phase 0 laptop gate.

### Phase 5 readiness

| Requirement | State |
|---|---|
| Pipeline from dataset to coverage maps, all five bands | Ready, demonstrated |
| Validated profile | Ready (standard, 10 m, 1e9) |
| Correct propagation physics in the pipeline | Verified in free space and for the antenna pattern; not yet against an urban reference |
| Approved study district and building data | **Missing** (A1, A2) |
| Approved radio parameters | **Missing** (A3) |
| Approved site rule | **Missing** (A4) |

**Phase 5 is technically ready and scientifically blocked.** Research runs will start as
soon as A1-A4 are approved; until then development runs can be repeated for teaching and
for testing multi-site and site-selection code (Phases 6 and 8).

---

## Phases 5-6 report: single site completed, multi-site network, application (2026-11-26)

**Status.** Phase 3-4 committed as `c55252f` (message "feat: radio configuration states and
production ray-tracing pipeline"; tags `v0.4.0` and `v0.4.0-radio-simulation` on the same
commit; not pushed). Work on branch `phase-5-6-coverage-multisite`. Phase 5: software
complete, **scientifically blocked** (A1-A4). Phase 6: first version complete, development
results only. Phase 0 laptop gate: **open**. Nothing here is a research result; every run is
labelled DEVELOPMENT — NOT APPROVED FOR RESEARCH.

### Requirements checked before building (reuse first)

| Requirement | Before | Now |
|---|---|---|
| Path gain, received power, SINR, Shannon rate, 5th percentile, CDF, outdoor filter | implemented and tested (Phase 4) | reused unchanged |
| Several sectors per site, co-located interference | implemented (`multi_site`) | reused; documented in `bns.simulation.network` |
| Several physical sites, site vs sector, serving-site map, interference map | missing | `bns.simulation.network` |
| Single vs multi-site comparison, adding sites one at a time | missing | `scripts/run_multi_site.py` |
| Reproducible exports | arrays and JSON only | CSV per band (cell, coordinates, values), sites as GeoJSON |
| Greedy selection on SINR (not a union of masks) | union-of-masks greedy only | `greedy_sinr_site_selection` |
| 28 GHz near-site gap | explained by the vertical pattern (untested) | diagnosed: own-roof shadow (below) |
| Application | none | Streamlit app (`app/`) |
| GlobalBuildingAtlas evaluation | metadata only | downloaded (approved, checksum verified) and evaluated |

### Completed

1. **GlobalBuildingAtlas** (`scripts/evaluate_gba.py`, `bns.geospatial.gba`,
   `docs/building-height-data.md` §12). LoD1 tile (378,494,857 bytes, SHA-256 verified,
   CC BY-NC 4.0). Heights joined to OSM ways by id: 479 of 899 receiver-area buildings
   (79 % of footprint area). Plausible for low-rise (median 9.3 m) but capped near 21 m: the
   55 m tower gets 5.4 m, a 60 m building 13.2 m; over 14 tagged buildings RMSE 19.1 m
   (6.2 m on the 12 below 30 m). It cannot recover the missing footprints: they are
   Microsoft footprints whose geometry is only in the ODbL polygon part, which was not
   downloaded. A separate dataset variant `osm+gba` was built (OSM tags keep priority; 53 %
   of heights estimated). Limited propagation comparison against `osm` (tower site,
   preview): median change 0.0 dB; 23 % of cells change by more than 1 dB, 7-8 % by more
   than 3 dB, 1.1-1.4 % by more than 10 dB, at 3.5 and 28 GHz. In `osm+gba` the tagged 12 m
   structure way/645196998 (31 m²) disappears inside a building GBA puts at 15.9 m (the
   taller footprint wins): a data conflict for field checking.
2. **Raw-data integrity defect found and fixed.** `core.autocrlf=true` had rewritten the v2
   OSM snapshot with CRLF line endings on checkout, breaking its SHA-256 (content intact).
   `.gitattributes` now marks `data/raw/**` as not text; the files were restored byte-exact;
   a unit test guards the setting.
3. **Multi-site network** (`bns.simulation.network`): sector stack + sector-to-site map;
   strongest sector serves; every other sector (co-located ones included) interferes, summed
   in watts × interference activity; serving sector and site maps, interference map,
   interference-limited share, served share per site and sector; each site alone.
4. **Experiment set-up shared by scripts and the application** (`bns.simulation.experiment`):
   dataset, grid, site placement (named buildings or the tallest observed-height roofs),
   jobs, radio inputs, gas loss, workload from cache status and measured trace times.
5. **SINR-based greedy** (`bns.optimization.greedy.greedy_sinr_site_selection`): evaluates
   the whole network for every candidate addition, records additions that would lower
   coverage, stops when none raises it. A heuristic, not a proven minimum.
6. **28 GHz near-site diagnosis** (`scripts/diagnose_near_site.py`, `docs/validation.md` §6):
   all 414 uncovered cells within 250 m lie behind the host roof's own edge; median excess
   loss 37 dB over free space + pattern while their pattern gain is still +1.5 dBi; cells
   whose line of sight clears the roof match free space + pattern within 0.3 dB. The
   pattern-only explanation is withdrawn. Nothing was tuned; mast height and antenna
   placement belong to the site rule (A4).
7. **Application** (`app/`, `bns.app`): Streamlit; pages Overview, Study area, Radio
   scenarios, Run simulation (form, site check, workload and cache status, start, progress,
   cancel, log, history), Coverage analysis (maps of path gain, received power, SINR, rate,
   coverage, serving site, interference; sites and sector azimuths; statistics; CDF),
   Comparison (five scenarios, CDFs, rates, single site vs network), Site planning
   (re-evaluation of any subset of sites and the SINR greedy from cached path gain;
   interference activity as a sensitivity slider), Validation (Phase 0 checks, convergence).
   Saved runs are shown without re-tracing.
8. **Profile status** recorded in `configs/simulation.yaml`: preview "validated for
   development", standard "borderline convergence", research "not determined (disabled)".
9. **GPU feasibility** (optional; nothing installed): the installed Mitsuba wheel contains
   `cuda_ad_mono_polarized`; on the RTX 3060 two cached jobs traced 13-15× faster with maps
   matching the CPU (median |Δ| 0.07-0.10 dB). Not integrated: the target laptop has no
   NVIDIA GPU, so the CPU stays the production path (`docs/benchmarks.md` §9).

### Multi-site development experiment

> **Invalid for research interpretation (2026-11-27).** These numbers come from runs that put sites or candidates on two monuments (Freedom Monument, Faeq Hassan mural); see `configs/invalidated_runs.yaml`. They are kept as a historical record of how the method behaves, not as evidence.

`outputs/runs/development/multi_site-tahrir_bab_al_sharqi_v2-osm-preview-4sites-20261126T113044Z/`
— **DEVELOPMENT — NOT APPROVED FOR RESEARCH.** Four sites on the four receiver-area roofs
with observed heights of at least 10 m (55, 15, 12, 10 m; 3 m masts), three sectors each,
all twelve sectors on one carrier at full load, preview profile (25 m, 1e8 rays), 808
outdoor cells.

| Scenario | Coverage: network / best site alone | Median SINR: network / site 1 alone | 5th-pct rate: network / site 1 alone | Median rate: network / site 1 alone |
|---|---|---|---|---|
| 1.8 GHz | 100.0 / 100.0 % | 3.5 / 20.3 dB | 15 / 32 Mbit/s | 34 / 135 Mbit/s |
| 3.5 GHz | 100.0 / 100.0 % | 3.9 / 20.0 dB | 75 / 154 Mbit/s | 180 / 666 Mbit/s |
| 8 GHz | 100.0 / 100.0 % | 4.3 / 16.2 dB | 303 / 460 Mbit/s | 750 / 2,162 Mbit/s |
| 15 GHz | 99.9 / 98.9 % | 4.5 / 14.0 dB | 298 / 184 Mbit/s | 771 / 1,883 Mbit/s |
| 28 GHz | 99.6 / 92.9 % | 4.3 / 11.1 dB | 291 / 37 Mbit/s | 751 / 1,519 Mbit/s |

What it shows about the method: with every sector interfering at full load the network is
interference-limited almost everywhere (94-100 % of cells) and the median SINR falls to
about 4 dB in every band. Coverage at the candidate threshold (SINR ≥ −10 dB) barely moves,
so this threshold cannot separate configurations; the SINR greedy therefore stops at one
site in four bands and at two at 28 GHz. Extra sites help only the cell edge at the high
bands (28 GHz 5th percentile 37 → 291 Mbit/s) and lower the median everywhere, because the
model has no load sharing: a Shannon rate per user with the whole carrier cannot show the
capacity gain of more sites. No addition lowered coverage in this run (the mechanism is
covered by unit tests). These are consequences of unapproved assumptions (A3: threshold,
activity, reuse; B3: rate reporting), not findings.

**Timing and memory.** 60 traces in 808 s wall (5.9-10.2 s each, median 8.0 s; worker
start-up, scene loading and first-compilation retries add 70 %); peak worker commit
0.86 GB, script 0.61 GB. The same run from the cache takes 3 s.

### Tests and runs executed

- `uv run pytest`: **254 passed**, 6 engine tests deselected (20 new: network 7, SINR greedy
  3, exports 2, GBA 3, application support 4, repository 1).
- `uvx ruff check --isolated --select F,E9 src scripts tests app`: all checks passed.
- Engine tests were not rerun: no engine code changed.
- Runs: GBA evaluation; `build_dataset --height-dataset gba`; two propagation comparisons;
  the 4-site run; the near-site diagnosis at 28 and 3.5 GHz; the GPU benchmark (3 repeats);
  the application with every page opened, one run started (served from the cache) and one
  cancelled from the interface.

### Limitations

- Development data only: 98.8 % placeholder heights, a third of the buildings missing.
- No load model, scheduler or user distribution; the Shannon rate is a per-user upper bound.
- The −10 dB coverage threshold saturates; it needs a supervisor decision (A3).
- Greedy over four candidates only; 20-40 candidates need the A4 site rule.
- Interference activity, reuse and the multi-site results are not checked against a
  system-level reference (3GPP calibration, MATLAB).
- The application is local and single-user, one run at a time.

### Remaining scientific blockers

A1 district; A2 building data (missing footprints: approval to download the GBA ODbL polygon
tile or another footprint source; heights: field observations; GBA at most as a low-rise
sensitivity case, and only if its non-commercial licence is acceptable); A3 radio parameters
including the coverage threshold and interference activity; A4 site rule including mast
height and antenna placement at the roof edge; B1-B3. Phase 0 laptop gate.

### Next

1. Supervisor decisions A1-A4 (the near-site and multi-site findings sharpen A3 and A4).
2. Phase 7: TR 38.901 and MATLAB cross-checks on the laptop; close the laptop gate.
3. Site planning at scale (A4 candidates) with the preview profile, final runs at standard.
4. Application: Reports and Roadmap pages once results exist.

---

## Phases 7-10 report: validation, site planning, comparison, roadmap, application (2026-11-26)

**Status.** Phase 5-6 checkpoint: `e0d8a8e`, tags `v0.5.0` and `v0.5.0-multisite-application`
(the requested message differs from the commit's; history not rewritten). Work on branch
`phase-7-10-validation-planning-roadmap`. **Software: release candidate. Science: blocked**
(A1-A4, B1-B3, laptop gate, convergence acceptance, MATLAB execution). Every run is labelled
DEVELOPMENT — NOT APPROVED FOR RESEARCH.

### Reused, not rebuilt

Geospatial pipeline, height provenance, Sionna RT engine and worker isolation, path-gain
cache, radio configuration states, single- and multi-site network, SINR greedy, run control,
saved-run loading, plot style.

### New

1. **Optional GPU backend** (straightforward: the CUDA variant ships in the installed wheel).
   `--backend cpu|gpu|auto` in the scripts and the Run page; GPU probe in a separate process
   with a diagnostic; backend in every cache key and manifest; research runs refuse a
   non-production backend (GPU status: *validated for development*). Radio-level agreement on
   the four-site experiment: path gain |Δ| median ≤ 0.03 dB, p95 ≤ 0.45 dB, no coverage-class
   change, 5th-percentile rate within 1.2 %; 16× faster (`docs/validation.md` §7).
2. **Defect fixed:** concurrent runs shared batch files in `data/cache/work`; each call now
   has a private folder (regression test added).
> **Invalid for research interpretation (2026-11-27).** These numbers come from runs that put sites or candidates on two monuments (Freedom Monument, Faeq Hassan mural); see `configs/invalidated_runs.yaml`. They are kept as a historical record of how the method behaves, not as evidence.

3. **Sensitivity** (`scripts/run_sensitivity.py`, cached maps): thresholds −10…+6 dB × loads
   1.0/0.5/0.2. At full load and 0 dB four sites cover less than one (1.8 GHz 82 % vs 100 %);
   only at 28 GHz do more sites raise coverage at thresholds up to 0 dB. An *illustrative*
   equal-share rate is reported separately from the Shannon bound.
4. **Phase 7 validation** (`docs/validation.md` §8-10): TR 38.901 UMa/UMi formulas with tests;
   controlled comparison (isotropic, 25 m / 10 m, five bands, LOS/NLOS from a LOS-only trace,
   preview profile). UMa LOS within σ (RMSE 3.6-3.9 dB, 3.5-28 GHz); NLOS 10-18 dB less loss
   than 3GPP because the open, placeholder-height district is far more line-of-sight (85 %)
   than the model's layout. MATLAB package prepared (`validation/matlab/`), not executed.
5. **28 GHz near-site gap, controlled experiment** (`scripts/experiment_antenna_placement.py`):
   only the sector positions moved from the roof's interior point to the roof edge (11-19 m
   away, same 3 m mast, tilt, profile, backend). Uncovered cells within 250 m: 32.4 % → 2.3 %
   at 28 GHz, 0.4 % → 0.1 % at 3.5 GHz; 28 GHz 5th-percentile rate 15 → 164 Mbit/s. Evidence
   for the roof-shadow mechanism on one building; placement stays decision A4.
6. **Phase 8 site planning** (`scripts/plan_sites.py`, Site planning page): 20 rooftop
   candidates, SINR greedy on whole-network coverage, selection history, final maps,
   uncovered cells, all-candidates reference, stop reasons distinguished, overrides only as
   recorded sensitivity cases.

   | Case | 1.8 | 3.5 | 8 | 15 | 28 GHz | All 20 candidates on |
   |---|---|---|---|---|---|---|
   | −10 dB, load 1.0 (candidate) | 1 | 1 | 1 | 1 | 2 | 100 % |
   | 0 dB, load 1.0 | 1 | 1 | 1 | 2 | 3 (stall at 91.3 %) | 47-51 % |
   | 0 dB, load 0.5 | 1 | 1 | 1 | 2 | 2 | 76-80 % |
   | +3 dB, load 0.5 | 1 | 1 | 2 | 2 (stall 93.3 %) | 3 (stall 92.6 %) | 47-51 % |

   Sites selected (greedy, target 95 %, preview, GPU backend, placeholder-height candidates):
   not a minimum, and with a 55 m tower among the candidates. Switching all candidates on lowers
   coverage sharply: adding sites is not assumed to help, and up to 40 degrading additions were
   recorded per run.
7. **Phase 9 comparison** (Comparison page): scenarios in one run (coverage vs frequency,
   received power, median SINR, SINR and rate CDFs, single vs network, coverage vs number of
   sites), across runs with a comparability check (area, grid, profile, mechanisms, antennas,
   radio parameters, overrides, backend, mode) and a warning naming every difference, site
   counts and density, TR 38.901 RMSE, sensitivity, limitations.
8. **Phase 10 roadmap** (6G roadmap page, `configs/roadmap.yaml`): four stages; each item is
   verified (registry ID required, unit-tested), a provisional result read from saved runs, or
   an open question; student recommendations are typed and saved locally; no generated
   conclusions and no deployment dates.
9. **Reports and exports** page: configuration, approval status, provenance, statistics,
   plan results, validation, notes, figures (PNG download), CSV, manifest/summary JSON, run
   folder ZIP, printable HTML report keeping label and limitations.
10. **Application**: 10 pages; backend selection; site plans shown on Coverage and Site
    planning; a defect on the Site planning page (KeyError for plans) fixed.
11. **Licensing**: GBA per-building values untracked and git-ignored (they are in `e0d8a8e`).
12. **README** with installation and operation.

### Tests and runs executed

- `uv run pytest`: **273 passed** (19 new: backends 5, TR 38.901 6, MATLAB case 2, report 2,
  network 1, propagation concurrency 1, app comparability 1, roadmap references 1).
- `uv run pytest -m engine`: **6 passed** in 53 s (full regression of the engine path; the
  Phase 0 records they rewrite were restored afterwards).
- `uvx ruff check --isolated --select F,E9`: all checks passed.
- Application: all 10 pages opened without errors after a server restart; research mode refused
  with its reason; plans shown on Coverage and Site planning; report HTML generated. The user
  also started a run (standard, cancelled after one trace) and an auto-backend run (served from
  the GPU cache) from the Run page; both ended as reported.
- Runs: four-site experiment on GPU; CPU/GPU comparison; sensitivity sweep; four site plans;
  TR 38.901 comparison (standard attempted and stopped, preview completed); antenna-position
  experiment (CPU, standard); MATLAB export.

### Limitations

- All results rest on the provisional area (99 % placeholder heights) and unapproved values.
- TR 38.901 comparison at preview resolution; standard-profile isotropic traces showed an
  unexplained slowdown (`docs/benchmarks.md` §10).
- Site planning over 20 candidates on placeholder roofs; candidate rule not approved.
- No scheduler or load model; the equal-share rate is illustrative only.
- MATLAB cross-check not executed; no field measurements.

### Remaining scientific blockers

A1, A2 (incl. GBA licence and the footprint download), A3 (threshold and load decide the site
count), A4 (mast height and roof-edge placement), B1 (agreement criterion), B2, B3, C6 (GPU for
research), Phase 0 laptop gate, final convergence acceptance, MATLAB execution.

### Steps to final delivery

1. Supervisor decisions A1-A4 and B1-B3; update `configs/*.yaml` approval states.
2. Laptop: install (README), run engine tests and the Phase 0 benchmark (closes the gate),
   run the MATLAB case and `scripts/compare_matlab.py`.
3. Rebuild the approved district dataset; run site planning at preview, final runs at
   standard on the CPU; regenerate comparison, sensitivity and validation outputs.
4. Write conclusions and roadmap recommendations from the approved results.

---

## Release candidate v1.0.0-rc.1: stabilisation and delivery readiness (2026-11-26)

**Status.** Software: release candidate (feature freeze). Science: **not approved**. Laptop:
**not tested**. Phase 7-10 was already committed as `0fb4052` (tag `v0.6.0`) with a different
message than requested; it was not rewritten. This cycle is on branch `release-1.0.0-rc.1`.

### Defects fixed

1. **Slow, erratic CPU traces — root cause found.** Windows 11 power throttling (EcoQoS)
   confined workers to the four efficiency cores: the same trace took 87 s on 13.6 busy cores,
   then 392 s on 4.8; forcing EcoQoS reproduced it (1,086 s on 3.8 cores); with the worker
   opted out, three calls took 76-80 s on ~15 cores. Fix in `runtime.init` (scheduling only),
   unit test, `docs/benchmarks.md` §11. A later uncached five-band run traced in 114 s against
   an estimate of 119 s (previously 70 % overhead).
2. **Research-mode gap:** research runs now also require a profile accepted for research.
3. **Engine tests overwrote the committed Phase 0 records:** now write to a temporary folder.
4. **UI:** Overview status table out of date; duplicated frequencies in scenario names;
   truncated profile labels; excessive top padding at laptop size.

### Added for delivery (no new features)

`setup.ps1`, `doctor.ps1` (+ `scripts/doctor.py`), `run.ps1`, `benchmark.ps1`,
`scripts/diagnose_trace_time.py`, `scripts/make_distribution.py` with
`configs/distribution.yaml`; headless page tests (`pytest -m app`); documents:
`docs/licensing.md`, `docs/supervisor-checklist.md`, `docs/research-execution-plan.md`,
`docs/laptop-acceptance.md`, `docs/user-guide.md`, `docs/release-notes.md`; a Reports-page
warning for runs derived from non-commercial data.

### Regression verification (development PC)

| Check | Result |
|---|---|
| Unit tests | 275 passed |
| Engine tests | 6 passed (47 s); Phase 0 records untouched |
| Application pages (headless AppTest) | 12 passed: all 10 pages, research refusal, export controls |
| Browser check at 1280 × 720 | Overview, Run simulation, Coverage, Site planning laid out correctly after the fixes |
| CPU execution, uncached | 15 traces 114 s; workers recorded `power_throttling_disabled: true`, 16 threads |
| GPU execution, uncached | 15 traces 16 s |
| CPU vs GPU (second, harder case) | median \|Δ\| ≤ 0.02 dB, p95 1.0-1.2 dB, single cells up to 26 dB, 0-4 of 808 cells change class: not interchangeable cell by cell (GPU stays development-only) |
| Cached execution, cancellation, concurrent isolation, comparability warnings | unit tests (runner, control, differences) and earlier UI checks; the user also cancelled a run from the app |
| Site planning | four saved plans re-evaluated from cache in the app |
| Exports | HTML report built for all 11 saved runs (label and limitations present); every CSV starts with the label; no run folder contains restricted data |
| Distribution archive | 10.0 MB, 347 files, 7 restricted or tool files excluded and verified absent; no git history |
| Fresh install of the archive (development PC) | setup.ps1: 0 failures, 20 s (environment from the local uv cache); unit 274 passed + 1 skipped (git-only check); pages 12 passed; engine 6 passed in 82 s from an empty kernel cache |

Acceptance found two delivery defects, both fixed: the git-attributes test failed outside a
git checkout, and the archive held run manifests without their arrays, so no saved run could
be opened; the development runs (arrays and figures, OSM-derived, about 9 MB) now ship as
demonstration results.

### Remaining before final delivery

Supervisor decisions (`docs/supervisor-checklist.md`); laptop acceptance (`benchmark.ps1`);
MATLAB case on the laptop; then `docs/research-execution-plan.md`.

---

## Final research execution cycle: approvals recorded, execution blocked by field observations (2026-11-26)

**Status.** `master` = `bc750b3` (`v1.0.0-rc.1`, fast-forward merge done earlier). Approvals
recorded as reported by the project owner (`docs/approval-record.md`). **v1.0.0 not released**:
mandatory gates remain open (below). Changes of this cycle are uncommitted on `master`'s working
tree (the user's own theme edit and roadmap file left untouched).

### Done

1. **Approval record** (`configs/approvals.yaml`, `docs/approval-record.md`): every recommended
   checklist option approved as reported; no written reference; conditions listed. Radio
   parameters, height policy, standard profile, site rule and study district set to approved.
2. **Approved methodology implemented** (needed to apply the approvals, not new scope):
   roof-edge sector antennas (A4, `configs/site_rule.yaml`, `sites.edge_positions`,
   `experiment.sector_positions`); missing-footprint import from 3D-GloBFP with footprint
   provenance and placeholder heights (A2, `build_dataset.py --add-footprints`); the 3GPP
   truncated rate beside Shannon (B3, `link_budget.truncated_shannon_bps`, map layer and
   percentiles).
3. **Research-mode protection extended**: refuses a dataset that is not fit for research; the
   fitness rule follows the approved A2 method (placeholders allowed only outside a completed
   observation worklist, method approved, no unmatched rows).
4. **Study dataset** `tahrir_bab_al_sharqi_study/osm+fp_3d_globfp`: 2,521 buildings, 577
   footprints (125,143 m²) added in the receiver area, mesh valid (0 non-manifold edges),
   checksum manifest `outputs/datasets/tahrir_bab_al_sharqi_study/osm+fp_3d_globfp/dataset_manifest.json`
   (scene fingerprint 7230170d…). **Not fit for research**: 99.4 % placeholder heights.
5. **Observation worklist** for the fieldwork: 330 buildings (3 tall, 4 candidate roofs, 324
   that may block a candidate site), `outputs/datasets/tahrir_bab_al_sharqi_study/height_worklist.csv`.
6. **Rehearsal** (development mode, CPU, preview, 4 observed sites, roof-edge sectors, B3) on
   the study dataset: 60 traces in 577 s; 405 outdoor cells at 25 m (808 before the added
   footprints); every run artefact as required. Labelled development; **not a result**.
7. Research mode refused the study dataset with "99.4 % of buildings have placeholder heights".

### Not done, and why (no results fabricated)

| Gate | State | What unblocks it |
|---|---|---|
| Final dataset (A2) | observations missing | student fieldwork on the 330 worklist buildings, then `build_dataset.py ... --observations <file>` |
| Candidate thresholds (A4) | cannot be set (only 4 roofs with observed heights) | the observations |
| Experiments A-E as research runs | blocked by the dataset | the two rows above |
| Convergence on the final scene | not run | after the final dataset exists |
| MATLAB cross-check (B1) and reflection-then-diffraction cases (B2) | not executed; MATLAB not on this PC | laptop run; cases need the final scene |
| Laptop acceptance | not measured | `benchmark.ps1` on the laptop |
| Written approval reference | missing | supervisor's written confirmation |

### Tests

Unit 280 passed; engine 6 passed (Phase 0 records untouched); pages 12 passed; lint clean.

---

## Final research readiness: external blockers (2026-11-27)

**Status.** Branch `final-research-readiness` (from `4928b4f`). `v1.0.0-rc.1` unchanged; no
`v1.0.0`. Research mode stays locked: the study dataset is not fit (0 of 190 required
buildings observed).

Done:
1. **Worklist reviewed** (`docs/fieldwork-prioritisation.md`): no duplicates; two "candidate
   rooftops" were monuments (Freedom Monument, Faeq Hassan mural) — monuments, memorials and
   artworks are now excluded from candidates (test added); worklist 330 → 190; broken OSM links
   for 3D-GloBFP footprints fixed.
2. **Prioritised** P0 3, P1 1, P2 34 (90.6 % of the shadow lines around the candidates, 3-D
   line-of-sight test with current heights), P3 152, plus S 43 (proposal: candidate search).
   Reduced set P0-P2 (38) + S storey counts proposed, not adopted.
3. **Fieldwork package** `outputs/datasets/tahrir_bab_al_sharqi_study/fieldwork/`: A3 map
   (PDF/PNG), priorities CSV with reasons and coordinates, observation template, guide
   (methods, safety, two stages, import).
4. **Observation import hardened**: `method_class` (measured / documented → observed;
   visual_estimate / storey_count → estimated, storeys × 3.0 m), invalid values rejected with
   reasons; completeness judged against the configured required list, not the submitted file;
   each observation file gives a new dataset version (`+observations-<sha8>`) with an automatic
   `dataset_manifest.json`.
5. **B3 verified** against TR 38.921 V19.0.0 Table 4.2.7-1 (exact match) and TR 36.942 Annex A
   (`docs/rate-mapping-verification.md`).
6. **Approval status classified** (`docs/approval-record.md`): nothing in writing; six values to
   confirm.

Tests: unit 293 passed; pages 12 passed; lint clean. No simulation was run in this cycle.

Remaining gates: field observations (stage 1, then stage 2), supervisor confirmations (six
items), written approval, laptop acceptance, MATLAB on the final scene (the current package uses
the development scene and must be regenerated with `scripts/export_matlab_case.py` from a
TR 38.901 run on the final dataset), then the research execution plan.

### Addendum: invalidated runs (2026-11-27)

The confirmed monument defect invalidates eight saved runs for research interpretation
(`configs/invalidated_runs.yaml`): the three four-site development runs, the four-site
rehearsal on the study dataset, and the four site plans. Their files are unchanged; the
application lists them after valid runs, marks them INVALID with the reason, leaves them out of
the roadmap and sensitivity evidence, and states the reason at the top of their printable
report; the clean distribution leaves them out of the demonstration results. Still valid as
development demonstrations: the standard single-site run (tower), the three one-site runs, the
antenna-placement experiment and the TR 38.901 comparison. The CPU/GPU agreement measured in an
invalidated run remains valid as an engine comparison only.

### Addendum: approved supervisor configuration applied (2026-11-27)

Under the feature freeze, configuration and guards only; no simulation was run.

- **Recorded** the second reported approval (no written reference): reduced fieldwork
  (P0-P2 + S, 81 buildings), 1 m inset, monument exclusion, B1 ≤ 2.0 dB, per-band B3 mappings,
  sensitivity cases (`configs/approvals.yaml`, `docs/approval-record.md`).
- **Configs:** `radio_system.yaml` (`rate_mappings` lte/nr/nr_based_candidate_6g,
  `scenario_rate_mapping`; azimuth convention stated), `site_rule.yaml` (references to the
  radio parameters instead of copies; candidate target, exclusions, pending thresholds),
  `study_area.yaml` (required `[P0, P1, P2, S]` with history; footprint sources; external
  dataset none; height sensitivity enabled), `simulation.yaml` (`research_backend: cpu`,
  `final_scene_convergence: not evaluated`), `atmosphere.yaml` (18.6 mm/h sensitivity case).
- **Code:** LTE cap in `link_budget.truncated_shannon_bps`; `bns.analysis.rate_models`;
  `bns.analysis.approval_lock` + `scripts/approval_lock.py` (changed approved values lose
  their approval); `bns.analysis.readiness` (eight gates; research refuses until the five
  pre-experiment gates pass); `bns.app.configuration` (display rows); app pages Overview,
  Radio, Study area show the approved configuration, gates and observation progress.
- **Defect fixed:** `scripts/run_single_site.py --mode research` skipped the profile, dataset
  and site-rule checks; it now applies the shared guards and refers research single-site runs
  to `run_multi_site.py`.
- **Dataset record:** study dataset rebuilt for the new requirement (scene fingerprint
  unchanged); quality report: 0 of 81 observed, not fit.
- **Tests run 2026-11-27:** `uv run pytest` 320 passed (18 deselected); `uv run pytest -m app`
  12 passed; `uv run pytest -m engine` 6 passed. App screenshots: `outputs/app_screenshots/2026-11-27/`.
- **Blockers unchanged:** observations, candidate thresholds, final-scene convergence, MATLAB,
  laptop, written reference.

### Addendum: configuration checkpoint (2026-11-27)

- **Observation acceptance (defect fixed):** a required building was completed by any filled
  row, so a visual estimate could complete P0. Now per group (`method_requirements`): P0-P2
  (38) need measured or documented heights, S (43) a storey-count record with the storey
  count. Readiness ignores datasets judged under other rules; dataset record rebuilt (scene
  fingerprint unchanged, 0 of 81). Overview and Study area show the two groups separately.
- **Azimuth convention:** verified that engine yaw, TR 38.901 pattern reference, roof-edge
  placement and map arrows share one frame (yaw counter-clockwise from east, x east, y north);
  a different yaw is a different cache key. Implemented sectors = compass 90/330/210°. Proposal
  compass 0/120/240° recorded as pending, **not applied**. New manifests record compass bearings.
- **Candidate thresholds:** evaluation values 12 m / 100 m² / 50 m give 1 candidate with today's
  heights; kept pending (`approvals.yaml`, `pending_proposals`). Mast 3 m and inset 1 m unchanged.
- **Tests run:** see the commit message of this checkpoint.

### Addendum: final approval and simplified research configuration (2026-11-27)

- All supervisor decisions recorded as approved (final report, as reported by the project owner;
  no written reference, none invented). No pending decision remains (`configs/approvals.yaml`).
- Sectors now face compass bearings 0/120/240° (yaw 90/330/210°); historical manifests keep their
  recorded yaw. Candidate criteria 12 m / 100 m² / 50 m in `site_rule.yaml`, used by default. P2
  accepts storey-based estimates (recorded as estimated); dataset record rebuilt, scene unchanged.
- The approval lock became the research-baseline fingerprint (`bns.analysis.research_baseline`,
  `configs/research_baseline.yaml`, `scripts/research_baseline.py`); readiness gates became
  scientific indicators (`bns.analysis.readiness`). Experiments accept validated overrides
  (`experiment.load(overrides=...)`, `run_multi_site.py --overrides`), are classified research
  baseline / custom experiment and record both in the manifest. Run simulation page: parameter
  editor with ranges and reset to baseline; Overview, Radio, Study area without approval workflow.
- Candidate pool with today's heights: 1 (target 20-40): the survey is needed.
- Tests run: see the commit message.

### Addendum: scientific result classification replaces the approval label (2026-11-27)

- `bns.analysis.classification`: configuration (Research Baseline / Custom Experiment / Sensitivity
  Analysis / not recorded), dataset (complete / incomplete), validation (Validated / Validation
  Pending) and the result class (Preliminary Simulation, Custom Experiment, Sensitivity Analysis,
  Research Baseline · Validation Pending, Validated Research Results). Sensitivity Analysis =
  changes only to threshold, target, load or rain. Validated = final-scene convergence and a MATLAB
  comparison whose LOS median is within the B1 tolerance in every band.
- Run scripts record `classification` in the manifest and use its label in figures, notes and
  exports; the app (banners, pages, run titles), the printable report and saved-note displays show
  it. Historical files are unchanged; displays and new reports show their class (Preliminary
  Simulation) and caption their saved figures.
- Tests run: see the commit message.

### Addendum: execution independent of classification (2026-11-27)

- Removed at the source every remaining approval/research-mode restriction: `experiment.load`
  (non-study area, readiness guard, profile status, dataset fitness, site-rule status, overrides),
  `resolve_backend` (GPU in research), `rate_mapping` (approval status), `readiness.require_research_ready`,
  `research_baseline.require_baseline`, `run_single_site.py` (five refusals), `plan_sites.py`
  (overrides, height categories), required `--mode` in the run scripts, and the Run simulation
  page's run-type selector and stop. `--mode` remains accepted and has no effect.
- Kept technical checks: unknown area/profile, missing scene or quality report, invalid values,
  empty outdoor grid, unavailable GPU, radio double counting.
- Classification: deviations from the baseline (values, preview profile, GPU backend, interior
  placement) make a custom experiment; dataset Complete (study district fit for research) /
  Estimated (height model) / Incomplete; validation Pending / Completed. Run control reports
  execution (Running / Completed / Cancelled / Failed) and the run's LIMITATION lines.
- Verified through the real pipeline: see the commit message.

### Addendum: scoped validation and dataset defaults (2026-11-27)

- Validation evidence is scoped to the propagation inputs (`bns.analysis.validation_scope`);
  `classification.validation_class(root, scope, profile=...)` needs a B1-passing MATLAB comparison
  from a run with the same scope and an accepted convergence record for the same scene, profile and
  backend. Radio-only changes keep the scope. The classification records `validation_scope`.
- `primary_variant` per area (study: `osm+fp_3d_globfp`; v2 and fixture: `osm`) is the default
  variant on Run simulation and Study area; no alphabetical choice.
- Dataset classes unchanged (Complete data / Estimated heights / Incomplete data).
- One run through the Start button: see `docs/execution-verification.md`.

### Addendum: Synthetic Urban Model (2026-11-27)

- New height-model kind `synthetic_urban` (`bns.geospatial.heights`, `configs/height_models.yaml`):
  class from tag or footprint area, triangular floors per class, neighbourhood smoothing, 3 m per
  storey, seed 42, scenarios low/baseline/high sharing each building's draw. Known heights never
  change; synthetic heights keep category placeholder with source `model:<model>:<class>`.
- Footprint overlaps are now resolved with the pre-model height, so every height-model variant has
  the footprints of the variant without a model (checked identical).
- Built the three study variants; the baseline is the study district's `primary_variant`.
  Metadata in quality reports and manifests (parameters, seed, synthetic share, classes).
- Candidates on synthetic datasets include synthetic roofs; spacing refined 50 -> 125 m
  (29/30/33 candidates low/baseline/high); research baseline re-recorded with that note.
- Readiness: "Synthetic Urban Model" indicator (Synthetic Data Complete), height completeness
  reported on documented heights. Classification: "Estimated Building Heights" -> "Simulation
  Results" (baseline values), never validated research results.
- Propagation caches: keys include the scene fingerprint, so the new scenes never reuse traces of
  other scenes; no cache had to be deleted.
- Height sensitivity and checks: `docs/synthetic-urban-model.md`.

### Addendum: Arabic/English interface and simplified dashboard (2026-11-27)

- `bns.i18n`: YAML catalogues per feature (`src/bns/i18n/locales/{ar,en}/*.yaml`), dotted keys,
  `str.format` interpolation, CLDR plural forms (Arabic six, English two), English fallback then the
  key, localized dates (Western digits for all numbers), `validate()` for key and placeholder parity.
  Arabic is the default; the choice is kept in the session and in `?lang=`.
- Every page goes through `t()`; Arabic is right-to-left (CSS on Streamlit's test ids) while charts,
  tables, code, numbers and inputs stay left-to-right; Arabic chart texts and band names carry Unicode
  direction isolates. Saved run records (Markdown notes, figures) remain English source records and
  are labelled as such; the roadmap claims are translated item by item and a unit test keeps the
  English text identical to `configs/roadmap.yaml`.
- Dashboard (`bns.app.dashboard`): header with language switch and execution status, four cards from
  real data, one primary action, latest completed run, five-scenario comparison, scientific status,
  one context-aware next step. Navigation: seven workflow pages plus "Research details" (radio,
  validation, roadmap).
- Printable report: `build_html(..., lang="ar"|"en")`, `<html lang dir>`, Arabic font stack; the
  English output is unchanged. CSV/JSON/GeoJSON exports keep their English schema.
- No change to simulation, formulas, baseline, provenance, validation rules or caches.
- Tests: `tests/unit/test_i18n.py` (parity, used keys, plurals, fallback, terminology, roadmap sync,
  classification, Arabic report), `tests/unit/test_dashboard.py`, `tests/app/test_i18n_pages.py`
  (every page in both languages, RTL styles, switch, `?lang=`).
