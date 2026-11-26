# Baghdad Network Simulator

Research tool for the graduation project *Coverage and Data Rate of 4G, 5G and Candidate 6G
in Baghdad — ray-tracing study and 6G roadmap for Iraq*. Ray-traced (Sionna RT) coverage,
SINR and Shannon rate of five scenarios (1.8, 3.5, 28 GHz and candidate 6G at 8 and 15 GHz),
multi-site networks, site planning, validation against 3GPP TR 38.901, and a roadmap
workspace, in a local Streamlit application.

> **Status.** Software: release candidate. Science: **not approved**. The study district,
> building data, radio parameters and site rule await the supervisor's decisions
> (`docs/supervisor-decisions.md`); every result is labelled
> **DEVELOPMENT — NOT APPROVED FOR RESEARCH**.

## Requirements

- Windows 10/11 (developed on Windows 11), 16 GB RAM, about 3 GB free disk.
- Python 3.13 and [uv](https://docs.astral.sh/uv/) 0.9 or newer.
- **LLVM 18.1.8** (the CPU ray-tracing backend needs `LLVM-C.dll`):
  `winget install --id LLVM.LLVM -e --version 18.1.8`
- Optional: an NVIDIA GPU with a current driver for the GPU backend. Nothing extra is
  installed for it; without a GPU everything runs on the CPU.
- No internet connection is needed after installation (maps use local scene coordinates).

## Install

```
git clone <repository> baghdad_network_simulator
cd baghdad_network_simulator
uv sync
uv run pytest                    # unit tests, about 20 s
uv run pytest -m engine          # engine tests through the real ray tracer, a few minutes
```

The development dataset is rebuilt from the committed OpenStreetMap snapshot:

```
uv run python scripts/build_dataset.py --area tahrir_bab_al_sharqi_v2
```

(`git` must not convert line endings in `data/raw/`; `.gitattributes` takes care of it.
If a snapshot reports a SHA-256 mismatch, check out `data/raw` again.)

## Run the application

```
uv run streamlit run app/main.py
```

Open http://localhost:8501. Pages:

| Page | What it does |
|---|---|
| Overview | project status, profiles, latest run |
| Study area | buildings, height provenance, data quality, dataset evaluations |
| Radio scenarios | the five scenarios; radio parameters with approval status |
| Run simulation | choose area, dataset, profile, mode, backend and sites; see cached/new traces and a measured time estimate; start, follow, cancel |
| Coverage analysis | maps (path gain, received power, SINR, rate, coverage, serving site, interference) with statistics |
| Comparison | scenarios, runs (with comparability warnings), site counts, 3GPP check, sensitivity, limitations |
| Site planning | saved site plans; re-evaluate any selection and rerun the SINR greedy from the cache |
| Validation | analytical checks, TR 38.901 comparison, CPU/GPU agreement, MATLAB package status |
| Reports and exports | configuration, provenance, statistics, figures, CSV/JSON/ZIP downloads, printable HTML report |
| 6G roadmap | verified evidence, saved results, open questions, and your own recommendations |

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

`docs/implementation-plan.md` (status per phase), `docs/architecture.md`,
`docs/validation.md`, `docs/supervisor-decisions.md`, `docs/assumptions.md`,
`docs/references.md` (every source, with how it was checked).

## Data licences

OpenStreetMap data © OpenStreetMap contributors, ODbL. External height datasets are kept
out of the repository (`data/cache/`, git-ignored); the small extracts in `data/raw/heights/`
carry their licence in their manifest. GlobalBuildingAtlas is CC BY-NC 4.0 (non-commercial):
its extract must not be redistributed with the project unless that licence is confirmed to
permit the intended use.
