# Implementation plan and progress

Phases follow the master brief. A phase starts only after the previous gate is accepted.
Each phase ends with: completed work, files, tests actually run, limitations, measurements,
blockers, next phase.

| Phase | Subject | Status |
|---|---|---|
| 0 | Feasibility and environment audit | **Done on the development PC; laptop rerun pending** |
| 1 | Literature and standards review | Not started |
| 2 | Study area and 3D city model | Not started (pipeline prototype exists from Phase 0) |
| 3 | Radio scenario configuration | Not started (`configs/scenarios.yaml` exists) |
| 4 | Ray-tracing engine (losses, adapter hardening) | Not started |
| 5 | Single-site coverage | Not started |
| 6 | Multi-site SINR and data rate | Not started |
| 7 | Scientific validation (3GPP TR 38.901, MATLAB cross-check) | Not started |
| 8 | Base-station site planning (greedy) | Not started |
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
