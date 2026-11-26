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
