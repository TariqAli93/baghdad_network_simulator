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

## 9. Optional GPU feasibility check (Phase 5, 2026-11-26)

Not part of the gate: the target laptop has an Intel UHD GPU, so the CPU path stays
mandatory. Nothing was installed: the installed Mitsuba 3.9.1 wheel already contains
`cuda_ad_mono_polarized`, and the NVIDIA driver (610.88) supplies CUDA. A scratch script
traced two cached jobs (3.5 GHz, tower site, one sector) on the RTX 3060 (12 GB), three
times in fresh processes, by patching the CPU-variant guard; production code is unchanged.

| Job | CPU (this PC, cached) | GPU first call | GPU repeat | Agreement with CPU |
|---|---|---|---|---|
| 25 m cells, 1e8 rays | 6.9 s | 0.5-1.2 s | 0.47 s | median |Δ| 0.10 dB, 95 % 2.2 dB |
| 10 m cells, 1e9 rays | 59.5 s | 4.7-5.1 s | 4.74 s | median |Δ| 0.07 dB, 95 % 1.7 dB |

No crash in three processes (the Windows LLVM first-compile crash is specific to the CPU
backend). A GPU path would be a 13-15× speed-up on this PC for site planning, but it would
change the engine fingerprint (separate cache) and would not exist on the laptop; adopting
it is a scope decision for the supervisor, not taken here.

### Preview-profile timing from the multi-site run

60 traces (4 sites × 3 sectors × 5 bands), 25 m cells, 1e8 rays: 5.9-10.2 s per trace
(median 8.0 s), 808 s wall in total; worker start-up, scene loading and first-compilation
retries add 70 % on top of the trace times (44 % in the standard single-site run). Peak
worker commit 0.86 GB.

## 10. Phase 7 timings and an open performance anomaly

- **GPU backend in production code** (`--backend gpu`): the four-site preview experiment (60
  traces) took 50 s of tracing on the RTX 3060 against 808 s on the CPU (16×); the 20-candidate
  site plan traced 240 new maps at a median 0.5-0.6 s each (about 2-3 minutes; the wall time of
  that run was not kept because its folder was regenerated from the cache). Agreement:
  `docs/validation.md` §7.
- **Anomaly** (explained in §11: Windows power throttling). Isotropic transmitters near the ground-level centre of the area
  (TR 38.901 validation) traced slowly and erratically on the CPU: at the standard profile one
  3.5 GHz job took 306 s, then 752 s on a retry, then over 10 minutes, with the worker using
  only about 4 of 16 cores; at the preview profile the first jobs took 98-112 s (1.8 GHz) and
  47 s (3.5 GHz at 25 m), all later ones 1-8 s. A worker crash in that batch also forced each
  retry to repeat the slow first job; the validation script now traces one job per worker.
  Possible causes (not verified): kernel compilation for a new antenna/mechanism combination,
  or contention when many rays land in few cells around an isotropic source. Sector antennas
  on rooftops did not show it (57-66 s per standard trace). To be re-measured on the laptop.
- **Concurrency defect fixed.** Two runs started together shared `data/cache/work/batch-*.json`
  and one deleted the other's batch file; every runner call now uses its own sub-folder.

## 11. Root cause of the slow traces: Windows power throttling (release cycle, 2026-11-26)

Bounded investigation with `scripts/diagnose_trace_time.py` (one job traced repeatedly in one
worker; busy cores = process CPU time / wall time), isotropic antenna at 25 m, 3.5 GHz,
standard profile (10 m, 1e9 rays), development PC (i5-14400F: 6 performance + 4 efficiency
cores, 16 threads):

| Condition | Call 1 | Call 2 | Call 3 |
|---|---|---|---|
| Default scheduling (before the fix) | 86.6 s, 13.6 cores | **391.6 s, 4.8 cores** | — |
| Power throttling disabled for the worker (the fix) | 79.6 s, 14.8 cores | 80.1 s, 14.7 cores | 76.0 s, 15.5 cores |
| EcoQoS forced on the worker (reverse test) | **1,086.5 s, 3.8 cores** | — | — |

- Not compilation: the slow call was the warm second call in the same process.
- Not the ray count, scene or propagation settings: the identical job ran at full speed in
  every call once throttling was disabled, and needed about 1,180 CPU-seconds whenever it
  ran on the performance cores.
- Cause: Windows 11 power throttling (EcoQoS). A worker launched from a background window can
  be treated as background work and confined to the four efficiency cores at low clocks;
  forcing EcoQoS reproduces the slowdown and the ~4 busy cores exactly.
- Fix: `runtime.init` calls `runtime.disable_power_throttling()` (Win32
  `SetProcessInformation`, ProcessPowerThrottling, execution speed not throttled) in every
  worker. Scheduling only; numerical results are unchanged. `BNS_ALLOW_POWER_THROTTLING=1`
  restores the default for comparison. Unit test added.
- Probably the same cause: the Phase 4 outliers (216 s and 248 s among 57-66 s traces) and the
  Phase 7 standard-profile validation stalls; those measurements are kept as recorded.
- Operational guidance: keep the laptop on AC power in a balanced or performance power mode;
  the laptop's i7-13620H is also hybrid (6 performance + 4 efficiency cores), so the fix
  matters there. Re-measure with `benchmark.ps1`.

## 12. Slow workspace traces: the Windows "Power saver" plan; per-trace commits (2026-11-27)

Observed in the workspace prototype run: three standard-profile CPU traces at 3.5 GHz took 191, 202
and 166 s, then the worker did not exit cleanly and the batch was traced again (177, 193, 173 s);
1,111.8 s in all, against an estimate of 3.7 min from the whole-history median (75 s). Investigated
from the cache records, the System event log and small preview-profile diagnostics in a fresh
worker (nothing written to the project cache):

| Evidence | Result |
|---|---|
| Power plan (System event log, event 12) | Ultimate Performance until 2026-11-27 16:01:31, then **Power saver** (set by explorer.exe), still active |
| Standard traces, same scene, before / after the switch | 76-91 s (demonstration run, 58 m site) / 166-202 s (15 m site) |
| Same job, S1 at 58 m vs S2 at 15 m, preview rays, under Power saver | 17.9-19.2 s vs 18.6-19.4 s: geometry and antenna height are **not** the cause |
| Processor during a trace | 89 % of the 2.5 GHz base clock, no turbo, 100 % busy on 13-15 cores; other processes < 1 core |
| Power throttling, threads, memory | opt-out recorded on, 16 threads, no affinity; peak commit 0.84-0.87 GB |
| Cache keys | all 6 entries under their own keys, stored jobs match, checksums verify, maps in [0, 1] |
| Worker start-up | 2.2 s per worker (demonstration run, 5 workers) to 5.1 s (workspace run, 2 workers) |

Cause: the Power saver plan caps the processor clock (about 2×); this scene is also about 1.2× slower
than the development area, so the whole-history median underestimates it. Contention from the
application or the browser, geometry and compilation were excluded. Not determined: the exit code
of the worker that did not exit cleanly (`propagation.compute` dropped the attempt records) and how
often such exits happen.

Changes (no safety rule relaxed):

- Every worker records the active power plan (`runtime.power_plan`, in the cache entry's runtime
  information); runs log it (`POWER`) and the workspace and `doctor` warn under Power saver.
- `runtime.run_isolated(on_attempt=...)` and `propagation.compute(on_attempt=...)` report every
  worker attempt with its exit code; workspace runs log them (`ATTEMPT`) and count retries.
- Commit granularity: traces expected to take ≥ 30 s get one worker each (`batch_size=1`, already
  supported): a crash at exit or a cancellation then loses at most one trace, for 2-5 s of start-up
  (1-7 % of a 75-200 s trace). Faster traces keep one worker per band (start-up would be 11-70 %).
  A worker that does not exit cleanly still publishes nothing.
- Estimate: this run's own mean trace time once one trace finished, before that the median of the
  12 most recent traces with the same scene, ray count, cell size and backend (else any scene),
  plus 5 s per worker still to start. Retries are not included and are shown separately.
