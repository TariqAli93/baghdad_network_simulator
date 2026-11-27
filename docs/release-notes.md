# Release notes

## Delivery candidate (2026-11-27, after v1.0.0-rc.1; not v1.0.0)

- Student package from `scripts/make_distribution.py`: double-click launchers (`1 - Install.cmd`,
  `2 - Start Baghdad Network Simulator.cmd`, `Diagnose problems.cmd`, `Laptop benchmark.cmd`,
  `Research console.cmd`), `START-HERE.txt` (Arabic and English), user guide and research
  execution guide in both languages, `SHA256SUMS.txt` checked by the diagnostics.
- Setup builds the study-district datasets (footprints; Synthetic Urban Model baseline, low,
  high) and offers to install missing uv / LLVM with winget; the launcher runs offline from the
  project's environment, serves on localhost only (no public-IP look-up) and opens the browser
  when the application is ready.
- Development-only files left out of the package (`not_delivered` in `configs/distribution.yaml`).
- Demonstration result on the Synthetic Urban Model: one research-baseline run (study district,
  standard profile, CPU, one site), classified Simulation Results · Validation Pending; it is the
  latest result the dashboard shows after installation.
- Bilingual interface review fixes (dashboard de-duplication, Arabic bidi, recorded status texts
  translated at display time, layout at 1366 × 768, language kept across restarts).
- Not changed: simulation, formulas, research baseline, datasets, validation rules, results.
- Still open for v1.0.0: field observations, final-scene convergence, MATLAB comparison, laptop
  acceptance on the target laptop.

## Unreleased (after v1.0.0-rc.1)

- Supervisor approvals recorded as reported (`docs/approval-record.md`); configuration states updated.
- Approved methodology implemented: roof-edge sector antennas (A4), missing-footprint import from
  3D-GloBFP (A2), 3GPP truncated rate beside Shannon (B3).
- Research mode refuses datasets that are not fit for research; fitness follows the approved A2 method.
- Study dataset `tahrir_bab_al_sharqi_study/osm+fp_3d_globfp` and its observation worklist.
- Second reported approval applied (2026-11-27): per-band rate mappings (LTE TR 36.942 for 4G, NR
  TR 38.921 for 5G, NR-based approximation for candidate 6G), reduced fieldwork P0-P2 + S (81),
  1 m inset, monument exclusion, B1 tolerance 2.0 dB; candidate thresholds left pending.
- Final approval applied (2026-11-27): sectors at compass bearings 0/120/240°; candidate criteria
  12 m / 100 m² / 50 m; P2 storey-based fallback. Approval management removed from the interface:
  the approved values are the research baseline (`configs/research_baseline.yaml`); the Run
  simulation page edits any valid parameter as a custom experiment, with reset to baseline;
  readiness shows scientific status (data, observations, candidates, convergence, validation).
- (Superseded the same day) approval lock and eight readiness gates (`bns.analysis.readiness`);
  research mode refuses until the five pre-experiment gates pass. Shown on the Overview, Radio and
  Study area pages.
- Fix: `run_single_site.py --mode research` now applies the shared research guards.
- Synthetic Urban Model (`synthetic-urban-1`, seed 42): estimated building heights for every
  building without one, classed by tag and footprint, smoothed over neighbours; low/baseline/high
  scenarios on identical footprints; default dataset of the study district. Candidate spacing
  refined 50 -> 125 m (geometric, documented). Results on it are classified "Simulation Results".
- Execution no longer depends on approvals or research mode: any technically valid simulation
  runs (provisional areas, incomplete observations, modified values, preview profile, GPU);
  only technical problems stop a run. Scientific limitations are listed before and during the run,
  and the result is classified (dataset now Complete / Estimated / Incomplete; deviations from the
  baseline recorded). Run control reports the execution state separately.
- Results are labelled with a scientific classification (`bns.analysis.classification`) instead of
  "DEVELOPMENT — NOT APPROVED FOR RESEARCH": configuration, dataset and validation are separate
  states; only validated research-baseline runs on complete data are Validated Research Results. A
  MATLAB comparison counts as validation only if it meets B1. Historical files keep their label;
  the app and new reports show their class.
- Fix: observation acceptance per group (P0-P2 measured or documented; S storey counts); separate
  progress on the Overview and Study area pages.
- Azimuth convention made explicit (compass bearings in manifests and the app); orientations
  unchanged; compass 0/120/240° and candidate thresholds 12 m / 100 m² / 50 m recorded as pending.
- **v1.0.0 is not released**: field observations, laptop acceptance, MATLAB and the written approval
  reference are open (`docs/implementation-plan.md`, last section).

# v1.0.0-rc.1 (software release candidate)

**What this release is.** The software for the graduation project is feature-complete and
frozen. It is **not** a scientific result: the study district, building data, radio
parameters, site rule, convergence profile, GPU use and the MATLAB criterion await the
supervisor (`docs/supervisor-checklist.md`); every result is labelled
DEVELOPMENT — NOT APPROVED FOR RESEARCH. Laptop compatibility is **not yet tested**
(`docs/laptop-acceptance.md`).

## Contents

- Geospatial pipeline: OSM snapshots (hashed, never overwritten), footprint repair,
  multipolygons, height provenance (observed / estimated / placeholder) with configurable
  priority, external height datasets as candidates, 3-D scenes for Sionna RT.
- Five baseline scenarios (1.8, 3.5, 28 GHz; candidate 6G 8 and 15 GHz).
- Sionna RT 2.2.0 engine in isolated workers with retries and cancellation; CPU (production),
  optional GPU and Auto backends; path-gain cache keyed by every propagation input.
- Radio results: received power, SINR with linear co-channel interference, coverage, Shannon
  upper bound, 5th percentile, CDFs; single site, multi-site, sectors and serving sites.
- Coverage/load sensitivity; SINR-based greedy site planning with selection history.
- Validation: analytical engine checks (Phase 0), 3GPP TR 38.901 UMa/UMi comparison, CPU/GPU
  agreement, near-site diagnosis and roof-edge experiment; MATLAB cross-check package.
- Streamlit application, ten pages; reports and exports; 6G roadmap workspace.
- Windows scripts: `setup.ps1`, `doctor.ps1`, `run.ps1`, `benchmark.ps1`; clean distribution
  builder `scripts/make_distribution.py`.

## Changes in this release cycle (since v0.6.0)

- **Fixed: slow, erratic CPU traces.** Windows power throttling (EcoQoS) could confine a
  worker to the efficiency cores of a hybrid CPU: the same trace took 87 s on 13.6 busy cores
  and then 392 s on 4.8; forcing EcoQoS reproduced it (1,086 s on 3.8 cores). Workers now opt out of power throttling at start-up
  (`runtime.disable_power_throttling`); scheduling only, results unchanged
  (`docs/benchmarks.md` §11).
- **Research-mode guard**: research runs also require a simulation profile accepted by the
  supervisor (status `approved`); the standard profile ("borderline convergence") is refused.
- **Engine tests no longer overwrite** the committed Phase 0 records (temporary output folder).
- **Licensing**: data inventory and attribution (`docs/licensing.md`); restricted artifacts
  listed in `configs/distribution.yaml` and left out of the clean archive; Reports page warns
  for runs derived from non-commercial data.
- Diagnostics and laptop acceptance tooling (`scripts/doctor.py`, `scripts/diagnose_trace_time.py`).
- Release acceptance fixes: the git-attributes test skips outside a git checkout; the
  development demonstration runs now ship with their arrays and figures (about 9 MB), so the
  installed application opens them.
- Documentation: user guide, supervisor checklist, research execution plan, laptop acceptance
  procedure, these notes.

## Known issues and limitations

| Item | Status / guidance |
|---|---|
| First compilation of a new kernel can crash the worker on Windows (LLVM JIT) | Handled by retries; kernels are cached so retries converge |
| Slow traces under Windows power throttling | Fixed (workers opt out); reverse test reproduced 1,086 s vs 78 s; re-measure on the laptop |
| Laptop compatibility and run times | Not tested; run `benchmark.ps1` there |
| Standard profile "borderline convergence"; research profile (5 m) not validated | Supervisor decision; research mode refuses until approved |
| NLOS disagreement with TR 38.901 (10-18 dB less loss) | Attributed to an open, placeholder-height district; **not demonstrated** |
| Breakpoint behaviour (non-coherent power sum) | Plausible explanation, not demonstrated |
| Shannon rate only; truncated 3GPP mapping not implemented | B3 decision |
| No scheduler or load model | Equal-share rate is illustrative only |
| Antenna placement at the roof centre in the candidate generator | A4 decision; edge placement is a small change once approved |
| MATLAB cross-check | Prepared, not executed |
| GlobalBuildingAtlas values in git history (`e0d8a8e`) | Distribute the clean archive, not the repository; history rewrite needs approval |
| One run at a time from the app; stale run detection relies on process id and start time | Restart the app if a dead run blocks "Start run" |
| Project's own code has no licence file | To decide before publication |
