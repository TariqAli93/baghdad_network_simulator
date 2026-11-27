# Baghdad Network Simulator

Research tool for the graduation project *Coverage and Data Rate of 4G, 5G and Candidate 6G
in Baghdad — ray-tracing study and 6G roadmap for Iraq*. Ray-traced (Sionna RT) coverage,
SINR and Shannon rate of five scenarios (1.8, 3.5, 28 GHz and candidate 6G at 8 and 15 GHz),
multi-site networks, site planning, validation against 3GPP TR 38.901, and a roadmap
workspace, in a local Streamlit application.

> **Status.** Software: delivery candidate after release candidate **v1.0.0-rc.1** (feature
> freeze). Methodology: the research baseline is approved by the supervisor
> (`docs/approval-record.md`). Every result carries its scientific classification (Simulation
> Results, Custom Experiment, Sensitivity Analysis, Preliminary Simulation, Research Baseline ·
> Validation Pending, Validated Research Results); until the field observations, the final-scene
> convergence and the MATLAB comparison exist, no result is a validated finding, and none is a
> measurement.
>
> **Students:** read `START-HERE.txt`, then `docs/user-guide.md` (Arabic: `docs/user-guide.ar.md`)
> and `docs/research-guide.md` (Arabic: `docs/research-guide.ar.md`).

## Requirements

- Windows 10/11 (developed on Windows 11), 16 GB RAM, about 3 GB free disk.
- Python 3.13 and [uv](https://docs.astral.sh/uv/) 0.9 or newer.
- **LLVM 18.1.8** (the CPU ray-tracing backend needs `LLVM-C.dll`):
  `winget install --id LLVM.LLVM -e --version 18.1.8`
- Optional: an NVIDIA GPU with a current driver for the GPU backend. Nothing extra is
  installed for it; without a GPU everything runs on the CPU.
- No internet connection is needed after installation (maps use local scene coordinates).

## Install (Windows PowerShell)

Unpack the delivery archive into a path without Arabic letters and double-click
**`1 - Install.cmd`** (or, in PowerShell: `powershell -ExecutionPolicy Bypass -File .\setup.ps1`).

`setup.ps1` checks for uv and LLVM (if one is missing and winget exists it asks whether to install
it, otherwise it prints the command), creates the environment exactly from `uv.lock`
(`uv sync --frozen`), builds the datasets from the committed OpenStreetMap snapshot and
3D-GloBFP extract (development area; study district with footprints and the Synthetic Urban
Model baseline, low and high) and runs the diagnostics. **Internet** is needed the first time
(Python 3.13 and about 1 GB of packages); afterwards everything runs offline. **Administrator
approval** may be needed only for installing LLVM through winget.

| Double-click | Script | What it does |
|---|---|---|
| `1 - Install.cmd` | `setup.ps1` | first-time installation (safe to repeat) |
| `2 - Start Baghdad Network Simulator.cmd` | `run.ps1` | start the application and open the browser |
| `Diagnose problems.cmd` | `doctor.ps1 -Save` | diagnostics (PASS / WARN / FAIL), package checksums |
| `Laptop benchmark.cmd` | `benchmark.ps1` | target-laptop acceptance measurements (`docs/laptop-acceptance.md`) |
| `Research console.cmd` | — | a PowerShell window with the project's Python, for the research commands |

Tests: `uv run pytest` (unit, about 10 s), `uv run pytest -m engine` (real ray tracer, about a
minute), `uv run pytest -m app` (every page headless on the saved development data).

(`git` must not convert line endings in `data/raw/`; `.gitattributes` takes care of it.
If a snapshot reports a SHA-256 mismatch, check out `data/raw` again.)

## Run the application

```
.\run.ps1                        # or: uv run streamlit run app/main.py
```

Open http://localhost:8501. Arabic (default, right-to-left) or English; the choice is kept on
the computer. Pages:

| Page | What it does |
|---|---|
| Dashboard | what the tool does, latest results, five-scenario comparison, scientific status, next step |
| Study Area | buildings, height provenance, data quality |
| Run Simulation | choose area, dataset, profile, backend and sites; see cached/new traces and a measured time estimate; start, follow, cancel |
| Coverage Analysis | maps (path gain, received power, SINR, rate, coverage, serving site, interference) with statistics |
| Network Comparison | scenarios, runs (with comparability warnings), site counts, 3GPP check, sensitivity, limitations |
| Site Planning | saved site plans; re-evaluate any selection and rerun the SINR greedy from the cache |
| Reports | printable report (Arabic or English), configuration, provenance, statistics, figures, CSV/JSON/ZIP downloads |
| Research Details: Radio Scenarios | the five scenarios; radio parameters with their sources |
| Research Details: Validation | analytical checks, TR 38.901 comparison, CPU/GPU agreement, MATLAB package status |
| Research Details: 6G Roadmap | verified evidence, saved results, open questions, and your own recommendations |

Only one simulation runs at a time from the app. Showing saved results never re-traces.

## Command line

```
uv run python scripts/run_multi_site.py --area tahrir_bab_al_sharqi_v2 --mode development --profile preview --sites 4 [--backend cpu|gpu|auto]
uv run python scripts/plan_sites.py --area tahrir_bab_al_sharqi_v2 --mode development --profile preview [--backend gpu] [--threshold 0 --load 0.5]
uv run python scripts/run_sensitivity.py outputs/runs/development/<multi-site run>
uv run python scripts/validate_tr38901.py --area tahrir_bab_al_sharqi_v2 --profile standard
uv run python scripts/export_matlab_case.py outputs/validation/<tr38901 run>
uv run python scripts/compare_backends.py <cpu run> <gpu run>
```

Every script prints `--help`. Results go to `outputs/runs/<mode>/<run id>/` with a
`manifest.json` that records every input, approval state, dataset hash, engine version and
backend. Path-gain maps are cached in `data/cache/pathgain/` by a key of everything that
changes them, so repeated or extended runs only trace what is new.

## Profiles and run time

| Profile | Cells | Rays per sector | Status | One trace, development PC (CPU / GPU) |
|---|---|---|---|---|
| preview | 25 m | 1e8 | validated for development | about 8 s / 0.5 s |
| standard | 10 m | 1e9 | borderline convergence | about 60 s / 5 s |
| research | 5 m | — | not determined (disabled) | — |

A site has three sectors and each band is traced separately: one site in five bands is 15
traces. Times on the target laptop are not yet measured (Phase 0 laptop gate).

## MATLAB cross-check

`validation/matlab/<case>/` holds a self-contained case (scene as STL, coordinates,
`run_case.m`). Run it in MATLAB on the laptop, copy `matlab_results.csv` back and run
`scripts/compare_matlab.py`. MATLAB is not an application dependency.

## Where to read more

For operating the tool: `docs/user-guide.md` / `docs/user-guide.ar.md`. For the research steps:
`docs/research-guide.md` / `docs/research-guide.ar.md`. For the supervisor: `docs/supervisor-checklist.md`.
For the final study: `docs/research-execution-plan.md`. For the laptop: `docs/laptop-acceptance.md`.
Release notes and known issues: `docs/release-notes.md`. Data licences: `docs/licensing.md`.

`docs/implementation-plan.md` (status per phase), `docs/architecture.md`,
`docs/validation.md`, `docs/supervisor-decisions.md`, `docs/assumptions.md`,
`docs/references.md` (every source, with how it was checked).

## Distribution

Distribute the clean archive, not the git repository: `uv run python scripts/make_distribution.py`
writes `dist/baghdad-network-simulator-<version>.zip` from the current commit only (no history),
without the restricted and development-only paths listed in `configs/distribution.yaml`
(`docs/licensing.md`), with `SHA256SUMS.txt` inside (checked by the diagnostics) and a `.sha256`
file beside it. The build fails if a file the student needs (`required` in that file) is missing.

## Data licences

OpenStreetMap data © OpenStreetMap contributors, ODbL. External height datasets are kept
out of the repository (`data/cache/`, git-ignored); the small extracts in `data/raw/heights/`
carry their licence in their manifest. GlobalBuildingAtlas is CC BY-NC 4.0 (non-commercial):
its extract must not be redistributed with the project unless that licence is confirmed to
permit the intended use.
