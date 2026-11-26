# Phase 0 feasibility report and benchmarks

Date: 2026-11-26. Every number below was produced by the scripts in `scripts/` on the
machine described in section 2 and is stored in `outputs/runs/phase0/`.

## 1. Verdict

**Sionna RT on the CPU is feasible for this project, and it is the recommended engine.**

- It reproduces free-space loss, ground reflection and knife-edge diffraction within the
  provisional tolerances at all five bands.
- One site on the full 1 km² area (2 reflections + diffraction, 100 million rays) takes
  about 6 s and under 1 GB of memory on the development PC, with no GPU.
- Two engine problems were found and are handled (sections 3.4 and 5). Both must be
  mentioned in the thesis methodology.
- **Still open:** the time measurement on the target laptop (section 8), and real building
  heights (the Baghdad numbers here use placeholder heights and are not findings).

## 2. Environment

| Item | Value |
|---|---|
| Machine | Development PC used as a proxy for the laptop: Intel Core i5-14400F (6 performance cores with 2 threads each + 4 efficient cores = 16 threads), 31.8 GB RAM, Windows 11 Pro 10.0.26300, power plan "Ultimate Performance" |
| GPU | NVIDIA RTX 3060 present but **not used**: CPU variant `llvm_ad_mono_polarized` asserted in every run, `CUDA_VISIBLE_DEVICES` emptied |
| Target laptop (not yet measured) | Intel Core i7-13620H (same core layout, 16 threads), 16 GB RAM, Intel UHD graphics |
| Python | 3.13.9 |
| Engine | `sionna-rt` 2.2.0, `mitsuba` 3.9.1, `drjit` 1.5.0, LLVM 18.1.8 |
| Other | `numpy` 2.5.5, `scipy` 1.18.1, `shapely` 2.2.0, `pyproj` 3.8.0 (full list: `uv.lock`) |
| Memory cap | 10 GB of committed memory per worker (Windows Job Object), emulating the laptop's budget |
| MATLAB | Not installed on this PC; licensed on the laptop; used only for cross-checks in Phase 7 |

## 3. Validation experiments (path gain only)

Provisional tolerances: 0.25 dB worst cell and 0.05 dB RMS against closed forms; 2 dB for
the diffraction checks. Run with `uv run python scripts/poc_validate.py all`.

### 3.1 E1 — free space against the Friis formula: PASS

Empty scene, site at (30, -20, 25) m, receivers at 1.5 m, 400 m x 200 m, 10 m cells,
10 million rays. Reference: Friis path gain averaged over each cell.

| Band | Mean error | RMS error | Worst cell |
|---|---|---|---|
| 1.8, 3.5, 8, 15, 28 GHz (identical to the digits shown) | -0.0001 dB | 0.019 dB | 0.105 dB |

Error against ray count at 3.5 GHz:

| Rays | RMS error | Worst cell |
|---|---|---|
| 100 thousand | 0.733 dB | 4.71 dB |
| 1 million | 0.126 dB | 0.79 dB |
| 10 million | 0.019 dB | 0.105 dB |
| 100 million | 0.0035 dB | 0.022 dB |

Also checked: the brightest cell is the one under the site (grid axes are not swapped), and
two different seeds give the same map to 2 parts in 10 million. **Rays leave the site on a
fixed lattice, so line-of-sight power is deterministic and its accuracy depends only on the
ray count.**

### 3.2 E2 — ground reflection against the Fresnel slab formula: PASS

Concrete ground only (1 m thick), site 25 m high, receivers at 1.5 m, 400 m x 400 m, 5 m
cells, 100 million rays. Reference: direct power plus reflected power weighted by the
ITU-R P.2040 slab reflection coefficient, powers added.

| Polarisation | Mean error | RMS error | Worst cell | Largest reflectance error |
|---|---|---|---|---|
| Vertical (TM), all five bands | +0.0015 dB | 0.013 dB | 0.123 dB | 0.0004 |
| Horizontal (TE), all five bands | +0.0020 dB | 0.011 dB | 0.093 dB | 0.0008 |

- Vertical polarisation shows the Brewster dip: reflectance falls to 0.0006-0.0011 in the
  60-65 m ring; theory puts the minimum at 60.7 m. Horizontal polarisation has no dip
  (minimum 0.186, at the nearest ring), as theory requires.
- With 10 million rays the same test fails the worst-cell tolerance (0.71 dB) purely from
  ray discretisation: smaller cells need more rays. This is why E2 uses 100 million.

### 3.3 E3 — diffraction against knife-edge theory: PASS

One concrete block, 20 m high, 10 m thick, 600 m long, built by the same mesh pipeline as
the city. Site 30 m high, 60 m in front of it, so only the far roof edge diffracts.
Diffracted power only, 10 million rays, 8 seeds, 2 m cells averaged along the block.
Loss is relative to free space.

| Band | Just inside the shadow: ray tracer / theory | 20-60 m behind the block: ray tracer / theory | Extra loss vs 1.8 GHz: measured / expected 10 log(f ratio) |
|---|---|---|---|
| 1.8 GHz | 7.38 / 7.62 dB | 27.98 / 28.19 dB | - |
| 3.5 GHz | 8.02 / 8.24 dB | 30.77 / 31.08 dB | 2.79 / 2.89 dB |
| 8 GHz | 9.12 / 9.32 dB | 34.36 / 34.67 dB | 6.39 / 6.48 dB |
| 15 GHz | 10.23 / 10.43 dB | 37.09 / 37.40 dB | 9.12 / 9.21 dB |
| 28 GHz | 11.62 / 11.83 dB | 39.80 / 40.11 dB | 11.83 / 11.92 dB |

- Agreement is within 0.35 dB in both windows and the frequency scaling is within 0.1 dB.
- Closer than about 25 m behind the block the ray tracer predicts more loss than the
  knife-edge formula (up to about 10 dB at 9 m). This is expected: the formula describes a
  thin absorbing screen, not a thick wedge at a steep angle, so it is only an envelope there.
- Artefact to know about: because powers are added without phase, the map steps up by
  0.25-0.63 dB on the lit side of a shadow boundary (theory: up to 0.97 dB at the boundary).
- Noise of the diffracted power between seeds: about 1 % after 8 seeds in this simple scene.

### 3.4 E4 — Baghdad block: PASS after correcting a Sionna default

Scene: OSM buildings around Tahrir Square / Bab Al-Sharqi. Crop scene 700 m square:
174 building solids (6 with a height tag, 1 with levels, **167 with the 9 m placeholder**),
4,200 triangles, 3,012 wedges. Site on the tallest building near the centre (55 m, tagged)
plus a 3 m mast. Receivers: 400 m x 400 m, 5 m cells, 4,102 outdoor cells. 100 million rays.

> These numbers show that the engine and pipeline work on real geometry. With placeholder
> heights they say nothing reliable about Baghdad.

What each mechanism adds at 3.5 GHz:

| Mechanisms | Outdoor cells with no path | Median path gain | 5th percentile | Time |
|---|---|---|---|---|
| Line of sight only | 64.7 % | -94.7 dB | -99.9 dB | 0.8 s |
| + 1 reflection | 56.8 % | -94.5 dB | -107.3 dB | 1.1 s |
| + 2 reflections | 52.4 % | -94.7 dB | -113.3 dB | 1.1 s |
| + 2 reflections + diffraction (project baseline) | 4.3 % | -103.3 dB | -128.4 dB | 5.0 s |
| 3 reflections + diffraction | 4.3 % | -103.4 dB | -127.7 dB | 4.9 s |
| 5 reflections + diffraction | 4.3 % | -103.3 dB | -127.4 dB | 5.0 s |

- Diffraction, not reflection, is what reaches most shadowed streets here. A third to fifth
  reflection changes the 5th percentile by at most 1 dB, which supports the description's
  choice of two reflections (to be re-checked with real heights).
- Reflected power is deterministic too: two seeds agree to 2 parts in 10 million.

Baseline settings at each band:

| Band | No path | 5th percentile | Median | 95th percentile |
|---|---|---|---|---|
| 1.8 GHz | 4.3 % | -119.7 dB | -95.9 dB | -83.6 dB |
| 3.5 GHz | 4.3 % | -128.2 dB | -103.4 dB | -89.6 dB |
| 8 GHz | 4.3 % | -139.1 dB | -112.5 dB | -96.9 dB |
| 15 GHz | 4.3 % | -147.3 dB | -119.7 dB | -102.5 dB |
| 28 GHz | 4.3 % | -155.5 dB | -126.6 dB | -107.9 dB |

The median falls 30.7 dB from 1.8 to 28 GHz: 23.8 dB of free-space loss plus extra
diffraction loss. The same cells are reached at every band; what changes is how strongly.

**Finding: Sionna's default wedge table loses diffracted power in city scenes.** The solver
remembers diffracting wedges in a hash table with 10,000 slots and discards a wedge whose
slot is taken. Check: buildings outside the block cannot obstruct any path inside it, so
diffracted power in the block must not fall when the scene grows from the 700 m crop to the
full 1.3 km box (453 solids, 7,149 wedges).

| Wedge table | Diffracted power in the block, full scene relative to crop | Median cell |
|---|---|---|
| Sionna default, 10,000 slots | -0.83 dB | -0.90 dB |
| Enlarged, 1,048,576 slots (used by this project) | -0.03 dB | -0.01 dB |

Enlarging the table recovers 1.3 dB of diffracted power in the full scene (1.4 dB in an
earlier run) and 0.5 dB even in the crop. The enlarged table is set in
`bns.propagation.sionna_engine`; it changes no physics. Remaining run-to-run variation of
total diffracted power is a few tenths of a percent (a handful of residual collisions decided
by thread timing), far below the per-cell noise.

Per-cell noise of diffracted power on this block: about 12 % after 8 seeds, i.e. roughly
one third (about 1.2 dB) for a single 100-million-ray run with 5 m cells.

### 3.5 E5 — how many rays a map needs (informative)

> **Superseded for the profiles (Phase 4, `docs/convergence.md`).** The numbers below were
> measured on a 400 m block. On the full 1 km² area 1e8 rays at 10 m cells give 3.9-5.2 dB
> (95th percentile) against a 1e9-ray map; the standard profile now uses 1e9 rays.

Same block, baseline settings, 3.5 GHz. Each map is compared with a 1-billion-ray map over
outdoor cells; the 10 m results are the same maps averaged 2 x 2.

| Rays | Time | 5 m cells: median / 95 % of cells within / cells missed | 10 m cells: median / 95 % within / missed |
|---|---|---|---|
| 1 million | 0.1 s | 1.28 dB / 30.0 dB / 25.7 % | 0.85 dB / 27.9 dB / 14.0 % |
| 10 million | 0.5 s | 0.65 dB / 24.6 dB / 8.6 % | 0.41 dB / 6.2 dB / 2.9 % |
| 100 million | 4.9 s | 0.26 dB / 3.8 dB / 1.6 % | 0.12 dB / 1.8 dB / 0.5 % |
| 1 billion vs another 1 billion (different seed) | 50 s | 0.11 dB / 1.6 dB / 0.1 % | 0.06 dB / 0.9 dB / 0.0 % |

"Cells missed" are cells the reference reaches but the cheaper map leaves empty. The tail
comes from diffraction, which is the only random part of the solver.

Provisional ray counts that follow (to be approved):

| Grid | Rays per site | Basis |
|---|---|---|
| 10 m cells | 100 million | 95 % of cells within 1.8 dB of the 1-billion-ray map, 0.5 % missed |
| 5 m cells | 1 billion | Two independent runs agree within 1.6 dB in 95 % of cells |
| 25 m cells | not measured yet | Expected to need fewer rays; measure in Phase 5 |

## 4. Benchmark

Full 1.3 km scene (453 solids, 9,873 triangles, 7,149 wedges), receivers 1 km x 1 km,
project baseline (2 reflections + diffraction), one site, 10 GB memory cap. Run with
`uv run python scripts/poc_benchmark.py`.

### 4.1 One site, 10 m cells, 100 million rays, all 16 threads

| Band | First call | Repeat call |
|---|---|---|
| 1.8 GHz | 6.8 s | 6.1 s |
| 3.5 GHz | 7.0 s | 6.4 s |
| 8 GHz | 7.2 s | 6.5 s |
| 15 GHz | 7.4 s | 6.7 s |
| 28 GHz | 7.3 s | 6.6 s |

Peak committed memory 0.87 GB, peak physical memory 0.35 GB. Scene load 0.07 s.
6,224 of 10,000 cells are outdoors; 0.4 % of them receive no path.

### 4.2 What changes the cost

| Variation (3.5 GHz) | Time per map | Peak committed memory |
|---|---|---|
| 10 million rays | 0.64 s | 0.85 GB |
| 100 million rays | 6.2 s | 0.85 GB |
| 1 billion rays | 61 s | 0.85 GB |
| 5 m cells instead of 10 m (100 million rays) | 6.1 s | 0.87 GB |
| 6 threads, one per performance core | 9.8 s | 0.85 GB |
| 12 threads on the performance cores | 6.6 s | 0.85 GB |
| All 16 threads | 6.2 s | 0.85 GB |

- **Time is proportional to the ray count and does not depend on the number of cells.**
- **Memory does not depend on the ray count or the grid.** The 16 GB laptop is not a
  constraint, and splitting a run into chunks to save memory is unnecessary.
- The four efficient cores add only about 6 %.

### 4.3 Sustained load

90 maps back to back in one process (9.5 minutes): fastest 6.07 s, median 6.26 s, slowest
7.77 s. No slowdown from heat on this desktop.

On two other occasions a long call ran much slower (a second 1-billion-ray call took 160 s
instead of 61 s; one 1-billion-ray call in E5 took 328 s instead of 50 s). The sustained test
did not reproduce it, so the cause is transient activity elsewhere on the PC and was not
identified. Time measurements for the gate should therefore be repeated, not taken once.

### 4.4 Extrapolation to a full study (development PC)

Assuming 25 candidate sites (a placeholder count) x 5 bands = 125 maps, each traced once and
cached:

| Setting | Per map | 125 maps |
|---|---|---|
| 10 m cells, 100 million rays | 6.3 s | about 13 minutes |
| 5 m cells, 1 billion rays | 61 s | about 2.1 hours |

Site planning, SINR and data-rate calculations re-use these maps and add no ray tracing.
The laptop will be slower by a factor that has to be measured; even a five-fold slowdown
would leave the 10 m study at about one hour.

## 5. Stability of the compiler layer (Windows)

Symptom: while a kernel is compiled for the first time the worker may abort with
`JIT session error: Failed to materialize symbols` or end with Windows exit codes
0xC0000005, 0xC0000374 or 0xC0000409. It happens with 1 thread as well as 16.

| Situation | Observed |
|---|---|
| Runs that compile nothing (kernels already cached) | 35 of 35 fresh processes exited cleanly on the first attempt (20 benchmark runs + 15 stress runs) |
| First run of a new configuration | 1 to 5 attempts until a clean exit: E1 3, E2 2, E3 4, E4 3, E5 3, benchmark cases 1-5 |
| First run with a completely empty cache (one configuration) | Clean on the first attempt in the one case measured, 9.5 s |

Handling (`bns.runtime.run_isolated`): results are accepted only from a worker that exits
with code 0; otherwise its output is discarded and it is restarted. Compiled kernels persist
in `data/cache/drjit`, so retries converge. All results in this report come from clean exits.

Every new frequency or setting compiles its own kernels once, so the first full study on a
machine will include such retries; later runs will not.

## 6. Limitations of these measurements

- Proxy hardware. The desktop has better cooling and a higher power limit than the laptop.
- One site position, one district, placeholder building heights.
- The knife-edge check covers a single clean wedge. Diffraction around real, irregular
  buildings is not validated by it; Phase 7 compares against 3GPP TR 38.901 and MATLAB.
- Radio-map diffraction is first-order and cannot follow a reflection, so streets reachable
  only by "reflect, then diffract" are under-predicted. The 4.3 % of unreached cells in E4
  includes such cases.
- Tolerances and ray counts are provisional until approved.
- No transmit power, noise, SINR, rain or gas loss yet.

## 7. Reproduce on this PC

```
uv sync
uv run pytest
uv run pytest -m engine
uv run python scripts/build_poc_scene.py
uv run python scripts/poc_validate.py all
uv run python scripts/poc_benchmark.py --mem-cap-gb 10
```

Results are reproducible within tolerance, not bit for bit: line-of-sight and reflected
power repeat to about 2 parts in 10 million; diffracted power repeats within the noise
quoted in sections 3.4 and 3.5.

## 8. Reproduce on the target laptop (closes the gate)

1. `winget install --id LLVM.LLVM -e --version 18.1.8`
2. Install `uv` (https://docs.astral.sh/uv/), copy the project folder including
   `data/raw/osm/`, then `uv sync`.
3. Plug in the charger, close other programs.
4. `uv run python scripts/build_poc_scene.py`
5. `uv run python scripts/poc_validate.py all` — all five must print PASS.
6. `uv run python scripts/poc_benchmark.py --mem-cap-gb 10` — expect retries on first use.
7. Report `outputs/runs/phase0/benchmark/summary.json`. The numbers that decide the gate are
   the `gate` times per band, the `sustained` fastest / median / slowest, and peak memory.
