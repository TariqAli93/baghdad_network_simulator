# Baghdad Network Simulator

Graduation-project research tool: ray-traced coverage, SINR and Shannon data rate of
4G (1.8 GHz), 5G (3.5 and 28 GHz) and candidate 6G (8 and 15 GHz) over a ~1 km² Baghdad
district, the base-station density each needs, and a 6G roadmap for Iraq.

Primary requirements: `Project_Description_4G_5G_6G_Baghdad.pdf` (the student's project
description). Progress and the phase gates live in `docs/implementation-plan.md`.

## Non-negotiable rules

- Scientific correctness over appearance. Real simulation, never mocked or fabricated data.
- Never change a scientific assumption silently. Record it in `docs/assumptions.md`; values
  the supervisor has not approved are marked *provisional*.
- No fabricated references or results. Report numbers only from runs that were executed.
- CPU-first: no CUDA, no cloud, no paid dependency. The target is a 16 GB laptop.
- Work phase by phase and stop at each gate. No UI work before the simulation core is validated.
- 6G scenarios are *candidate research assumptions*; the 3.5 GHz band for Iraq is *assumed*.

## Commands

```
uv sync                                         # create/update .venv from uv.lock
uv run pytest                                   # unit tests (fast, no ray tracing)
uv run pytest -m engine                         # scientific tests through the real engine
uv run python scripts/build_dataset.py --area NAME   # OSM snapshot -> scene + quality report
uv run python scripts/run_single_site.py --area NAME --mode development   # five-band single site
uv run python scripts/run_convergence.py --area NAME # ray-count check behind the profiles
uv run python scripts/run_multi_site.py --area NAME --mode development [--profile preview] [--sites N | --buildings ID...]
uv run python scripts/evaluate_gba.py --area NAME       # GlobalBuildingAtlas heights vs OSM and 3D-GloBFP
uv run python scripts/diagnose_near_site.py RUN_DIR     # pattern vs own-roof shadow near a site
uv run streamlit run app/main.py                       # the application (reads saved runs)
uv run python scripts/plan_sites.py --area NAME --mode development [--backend gpu] [--threshold DB --load X]
uv run python scripts/run_sensitivity.py RUN_DIR        # threshold x load sweep from cached maps
uv run python scripts/validate_tr38901.py --area NAME   # ray tracing vs 3GPP UMa/UMi (CPU, standard)
uv run python scripts/export_matlab_case.py VALIDATION_DIR   # MATLAB cross-check package (laptop)
uv run python scripts/compare_backends.py CPU_RUN GPU_RUN    # CPU/GPU agreement at radio level
uv run python scripts/experiment_antenna_placement.py SINGLE_SITE_RUN   # interior vs roof-edge sectors
.\setup.ps1 / .\doctor.ps1 / .\run.ps1 / .\benchmark.ps1   # install, diagnose, start, laptop acceptance
uv run pytest -m app                                   # every page headless (AppTest)
uv run python scripts/diagnose_trace_time.py           # one job timed repeatedly: compile vs trace, busy cores
uv run python scripts/make_distribution.py             # clean archive: current commit, restricted paths removed
uv run python scripts/fieldwork_package.py --area NAME --variant V   # prioritised observation worklist, map, template
uv run python scripts/import_height_dataset.py / evaluate_height_dataset.py / height_worklist.py
uv run python scripts/run_height_sensitivity.py ...  # compare height models (see its --help)
uv run python scripts/atmosphere_table.py            # rain and gas loss per band
uv run python scripts/research_baseline.py         # config files vs research baseline (--record: documented baseline update)
uv run python scripts/build_poc_scene.py        # Phase 0 scenes (kept for the Phase 0 experiments)
uv run python scripts/poc_validate.py all       # experiments E1-E5 -> outputs/runs/phase0/
uv run python scripts/poc_benchmark.py          # time and memory -> outputs/runs/phase0/benchmark/
```

## Data and parameter rules

- **Study district approved 2026-11-26** (as reported; `docs/approval-record.md`):
  `tahrir_bab_al_sharqi_study` (same boundary as v2; footprints added from 3D-GloBFP). It is
  not fit for research until the observation worklist is filled in. `tahrir_bab_al_sharqi`
  and `_v2` stay development datasets: never report Baghdad results from them.
- **Every building height has a provenance record** (`bns.geospatial.heights`): observed,
  estimated or placeholder, with source, method and the untouched original values. Never
  present a placeholder or a height-model draw as an estimate or a measurement.
- **Radio-system parameters are approved** (`configs/approvals.yaml`); each entry keeps its
  status and sources (`configs/radio_system.yaml`, `docs/radio-parameters.md`). Every output is
  labelled with its scientific classification (`bns.analysis.classification`): configuration
  (Research Baseline / Custom Experiment / Sensitivity Analysis), dataset (complete / incomplete)
  and validation (Validated / Validation Pending), giving Preliminary Simulation, Custom
  Experiment, Sensitivity Analysis, Research Baseline · Validation Pending or Validated Research
  Results. Never call a result validated without the final-scene convergence and a MATLAB
  comparison meeting B1. Never use the old "DEVELOPMENT — NOT APPROVED FOR RESEARCH" label.
  Do not add a default power, gain, noise figure, threshold or target anywhere in code. Never
  add an antenna gain on top of an EIRP or of a traced pattern.
- **Propagation and radio system stay separate**: ray tracing goes through
  `bns.simulation.propagation` (cached by job key); received power, SINR and rates through
  `bns.simulation.radio`. A path-gain map is never reported as coverage.
- **Profiles** come from `configs/simulation.yaml` (`docs/convergence.md`); do not lower a
  ray count without a new convergence measurement.
- **Baseline atmosphere is clear sky** (gas included, no rain). Rain cases in
  `configs/atmosphere.yaml` are unapproved sensitivity cases.
- Open decisions live in `docs/supervisor-decisions.md`; corrections to the project
  description in `docs/project-description-corrections.md`. The PDF itself is never edited.
- New code is written test-first (`tests/unit`), with analytical cases for anything scientific.

## Engine facts you must respect

- Engine: Sionna RT 2.2.0 (`mitsuba` 3.9.1, `drjit` 1.5.0) on the CPU variant
  `llvm_ad_mono_polarized` (production). Optional GPU backend `cuda_ad_mono_polarized` (same wheel, NVIDIA
  driver only): status "validated for development" in `configs/simulation.yaml`; a GPU run is a
  custom experiment (not the research baseline). The variant is in every cache key, so CPU and GPU maps are never mixed. LLVM 18.1.8 must be installed
  (`winget install --id LLVM.LLVM -e --version 18.1.8`).
- Always call `bns.runtime.init()` before anything imports `mitsuba` or `sionna.rt`.
  `bns.propagation.sionna_engine` refuses to import otherwise.
- **Run every simulation in a worker process through `bns.runtime.run_isolated`.** On Windows
  the first compilation of a kernel intermittently crashes the process; results are accepted
  only from a process that exits with code 0, and a failed attempt is retried (compiled
  kernels are cached in `data/cache/drjit`, so retries converge). Details in
  `docs/architecture.md`.
- The ray tracer returns **path gain** (linear, between isotropic antennas), independent of
  transmit power and bandwidth. Received power, SINR and data rate are computed afterwards.
- Rays start on a deterministic lattice: accuracy is set by the ray count, and averaging
  seeds does not improve line-of-sight or reflected power. Only diffraction is random.
- Refraction is off (buildings are opaque). Radio-map diffraction is first-order and is
  never combined with a reflection. Gas and rain loss are not built in.
- Do not revert the enlarged wedge table in `sionna_engine.py`: with Sionna's default of
  10,000 slots a city scene loses more than 1 dB of diffracted power (benchmarks, E4).
- Workers opt out of Windows power throttling (EcoQoS) in `runtime.init`; without it a worker
  can be confined to the efficiency cores (78 s became 1,086 s, benchmarks §11). Keep it.
- Ray counts follow the cell size (benchmarks, E5): finer cells need more rays. Time grows
  with rays, not with cells; memory stays under 1 GB either way.

## Conventions

- SI units internally (Hz, m, W); dB and dBm only at the edges. Helpers: `bns.core.units`.
- Scene coordinates: metres, z up, origin at the centre of the study box (local transverse
  Mercator). Grid arrays are indexed `[y, x]`.
- Every building height carries a category (observed / estimated / placeholder), a source
  (`manual:`, `osm:height`, `osm:building:levels`, `dataset:`, `model:`, `placeholder`) and
  its alternatives; the priority between sources is in `configs/study_area.yaml`.
- Snapshots are never overwritten; a new download gets a new snapshot name. The Phase 0
  fixture (`tahrir_bab_al_sharqi`) is frozen; development work uses `tahrir_bab_al_sharqi_v2`.
- Raw data in `data/raw/` is immutable and hashed; `data/scenes/`, `data/cache/` and large
  run outputs are regenerated and git-ignored.
- Charts use `bns.reporting.plotstyle` (one colour per scenario, everywhere).
- `data/raw/**` is binary for git (`.gitattributes`): never let git convert hashed raw files.
- GlobalBuildingAtlas (CC BY-NC 4.0) per-building values stay local (git-ignored); only aggregate
  evaluation results are in the repository.
- Runs started at the same time each get a private work folder (`bns.simulation.propagation`).
- Site planning is the SINR greedy over physical sites (`scripts/plan_sites.py`); threshold/load
  overrides are sensitivity cases (development only, recorded). Never claim a minimum site count.
- Feature freeze since v1.0.0-rc.1: only defect fixes and approved research execution.
- Observations: method_class measured/documented = observed, storey_count/visual_estimate =
  estimated; P0-P1 need measured/documented, P2 prefers them (storey-count fallback), S a storey
  count (`method_requirements`); mandatory buildings come from the configured worklist (study_area.yaml), never from
  the submitted file. Monuments, memorials and artworks are never transmitter candidates.
- Execution is never restricted for scientific or approval reasons: any technically valid run
  executes (any area with a scene, any profile, backend, value). Only technical problems stop a
  run (`ExperimentError`: unknown area/profile, missing scene, invalid value, no GPU). `--mode` is
  kept for old commands and has no effect. Scientific standing is the run's classification.
- All supervisor decisions are approved (final 2026-11-27, `docs/approval-record.md`): do not ask
  for further approvals. The approved values are the research baseline
  (`configs/research_baseline.yaml`). Other values run as custom experiments (`--overrides`, Run
  simulation page) and are recorded in the manifest. Configuration (baseline / custom /
  sensitivity, with deviations: values, profile, backend, placement), dataset (complete /
  estimated / incomplete; only the study district can be complete) and validation are recorded
  separately; execution state (Running / Completed / Cancelled / Failed) is separate again.
- Sectors face compass bearings 0/120/240° (0 = north, clockwise); the ray tracer's yaw is
  counter-clockwise from east, yaw = 90° − bearing (`setup.bearing_to_scene_azimuth_rad`). Runs
  before 2026-11-27 used yaw 0/120/240°; never reinterpret their manifests.
- Rate mappings per band (`rate_mappings` in `radio_system.yaml`): LTE for 4G, NR for 5G, NR-based
  approximation (labelled) for candidate 6G; always beside Shannon, never instead.
- Distribute `scripts/make_distribution.py` archives, never the repository (GBA values in history).
- Validation categories stay separate: analytical, model-to-model (TR 38.901), MATLAB (prepared,
  not executed), field measurements (none).
- The app (`app/`) holds UI code only; anything computed lives in `bns` (`bns.app` for run
  discovery, run control and re-evaluation from the cache). The app never re-traces to show a run.
- Multi-site: sectors are traced transmitters, sites group them; every non-serving sector
  interferes (reuse 1, activity from the radio configuration); never assume an added site helps.

## Layout

```
configs/scenarios.yaml          the five scenarios (single source of truth)
configs/study_area.yaml         study areas and the OSM height policy
configs/height_models.yaml      assumed height distributions for the sensitivity analysis
configs/radio_system.yaml       power, antenna, noise, thresholds with approval states
configs/simulation.yaml         profiles, mechanisms, seeds
configs/height_datasets.yaml    external height datasets (manifests, checksums)
configs/atmosphere.yaml         clear-sky baseline and rain sensitivity cases
src/bns/simulation/             jobs, cache, propagation (runner), worker, radio, setup
src/bns/runtime.py              CPU bootstrap, memory cap, isolated workers
src/bns/core/units.py           conversions, Friis, thermal noise
src/bns/analysis/               link_budget (received power, SINR, Shannon), metrics (coverage,
                                percentiles, CDF, RMSE), sensitivity, radio_system
src/bns/optimization/greedy.py  greedy site selection (coverage masks; and on network SINR)
src/bns/simulation/network.py   multi-site network: serving sector/site, interference
src/bns/simulation/experiment.py  shared experiment set-up (scripts and app)
src/bns/app/                    saved runs, run control, re-evaluation (no UI code)
app/                            Streamlit application (main.py, ui.py, views/: 10 pages)
src/bns/validation/tr38901.py   3GPP UMa/UMi path loss, LOS probability, applicability
src/bns/validation/matlab_case.py  STL export and receiver sampling for the MATLAB package
src/bns/reporting/report.py     printable HTML report of a run
configs/roadmap.yaml            6G roadmap evidence (every claim cites a registry ID)
validation/matlab/              MATLAB cross-check cases (prepared, run on the laptop)
src/bns/validation/analytic.py  closed-form references (Friis, Fresnel slab, knife edge)
src/bns/geospatial/             study_area, osm_source (snapshots, parsing), heights (provenance,
                                height models), sites (rooftop candidates), grid (receivers,
                                outdoor mask), quality (reports), pipeline (build_dataset),
                                osm_scene (footprint cleaning, meshing, scene files)
src/bns/propagation/            sionna_engine (path-gain maps), atmosphere (rain, gases)
src/bns/reporting/plotstyle.py  chart style
scripts/                        build_dataset, run_height_sensitivity, atmosphere_table,
                                and the Phase 0 scripts
tests/unit, tests/scientific    pytest
docs/                           implementation-plan, architecture, assumptions, benchmarks,
                                references (source registry), related-studies,
                                project-description-corrections, supervisor-decisions,
                                building-height-data, atmospheric-losses
```

Every scenario in `configs/scenarios.yaml` cites entries of `docs/references.md` by ID; a
unit test fails if an ID is missing. Add a registry entry (with how it was checked) before
citing a new source anywhere in the project.

Keep `docs/implementation-plan.md` current at the end of every phase: completed work, files,
tests actually run with their results, limitations, measurements, blockers, next phase.
