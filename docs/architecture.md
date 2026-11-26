# Architecture

Status: Phase 0 (feasibility). Only the parts marked **built** exist; the rest is the agreed
direction and will be refined when each phase starts.

## 1. Layers

```
Streamlit UI                     planned (Phase 10 of the workflow, after validation)
  -> Application services        planned
  -> Simulation controller       planned: job queue, progress, cancel, resume
  -> Worker process              built:   bns.runtime.run_isolated
  -> Engine adapter              built:   bns.propagation.sionna_engine (one function)
  -> Scientific analysis         planned: received power, SINR, Shannon rate, coverage, greedy
  -> Results storage             planned: Parquet + JSON run records (Phase 0 uses .npz + JSON)
  -> Visualisation / reporting   started: bns.reporting.plotstyle
```

The UI never calls the engine directly. Everything the UI can do must also be reachable from
the command line; in Phase 0 the command line is the only interface (`scripts/`).

## 2. Engine decision

**Selected engine: NVIDIA Sionna RT 2.2.0, on the CPU.** Approved by the supervisor as the
alternative to MATLAB. MATLAB (licensed on the student's laptop) is not an engine of this
application; it will be used in Phase 7 to cross-check a few identical cases.

Why:

- It runs on the target class of hardware without a GPU (Mitsuba variant
  `llvm_ad_mono_polarized`), is free, and is scriptable from Python end to end.
- It reproduced three closed-form results within tolerance (see `docs/benchmarks.md`):
  free space, ground reflection including the Brewster dip, and knife-edge diffraction.
- A full 1 km² map takes seconds on the CPU and its memory does not grow with the ray count.
- The development PC has no MATLAB, so a MATLAB engine could not be built or tested here.

### Differences from the MATLAB shooting-and-bouncing-rays method in the project description

| Aspect | MATLAB `raytracing` (SBR) | Sionna RT radio map (this project) | Consequence |
|---|---|---|---|
| Multipath combining | Coherent phasor sum at a point | Non-coherent power sum, averaged over the cell | Maps show local-average power, with no fast-fading ripple. Appropriate for coverage planning; state it in the thesis |
| Diffraction | Up to 1 edge in `coverage`/`sinr`, may follow reflections | First-order only, site -> one wedge -> receiver, never combined with a reflection | A street reached only by "reflection then diffraction" is under-predicted |
| Through-wall transmission | Not modelled | Available (`refraction`), **switched off** | Buildings are opaque in both |
| Diffuse scattering | Not modelled | Available, **switched off** | Same in both |
| Concrete | ITU-R P.2040 | ITU-R P.2040-4, same coefficients; error outside 1-100 GHz | Same material law |
| Ground | Concrete by default | Concrete (ITU ground types stop at 10 GHz) | Same |
| Rain / gas loss | Added per path | **Not built in** | Added by this project after tracing (Phase 4) |
| Weak paths | Dropped 40 dB below the strongest | Kept | Sionna keeps more weak energy |
| Receiver antenna | 2.1 dBi by default | Isotropic (0 dBi) | Set explicitly when cross-checking |

### Known limitations of the engine (Sionna RT 2.2.0)

- Radio-map diffraction is first-order and direct only (above).
- The solver stores at most 10,000 wedges per run. The 1.3 km Baghdad scene has about
  7,000 wedges; experiment E4 checks that diffracted energy is not lost on the larger scene.
- Upstream issues are open on diffraction accuracy (NVlabs/sionna-rt #84, #85, #87, #89, #94).
  Our knife-edge check (E3) passes on planar maps; mesh-based maps (#94) are not used.
- All transmitters in one run share one antenna pattern and one frequency. We trace one site
  and one band per run, so this does not constrain us.

## 3. Running the engine safely on Windows (important)

With Dr.Jit 1.5.0 and LLVM 16 or newer, Dr.Jit compiles kernels through LLVM's ORCv2 JIT.
On Windows this is unstable **while a kernel is being compiled for the first time**: the
process intermittently aborts with `JIT session error: Failed to materialize symbols
{ __ymm@..., __real@... }` or ends with a heap-corruption exit code. It happens with one
thread as well as sixteen, so it is not a threading problem. Once a kernel has been compiled
it is stored in the kernel cache and loaded without the compiler; runs that compile nothing
were stable in every test (see `docs/benchmarks.md` for counts).

Rules that follow, implemented in `bns.runtime`:

1. **Kernel cache in the project:** `DRJIT_CACHE_DIR = data/cache/drjit` (not the Windows
   temp folder, which the system may clean).
2. **Every simulation runs in a worker process** (`run_isolated`). The worker writes into a
   staging folder.
3. **Results count only if the worker exits with code 0.** Otherwise the staging folder is
   discarded and the worker is started again. Each retry starts with more kernels cached, so
   it gets further; an ordinary Python error (exit code 1) is not retried.
4. Each new combination of frequency and settings compiles new kernels once, so the first run
   of a new configuration is the one that may need retries.

This costs retries on first use and nothing afterwards. It should be revisited when Dr.Jit or
LLVM changes; an alternative worth testing is LLVM 15, which makes Dr.Jit use the older MCJIT
interface instead of ORCv2 (not tested: it needs another installer download).

The same worker pattern gives the application what it needs anyway: a responsive UI,
cancellation (terminate the worker), a hard memory cap (Windows Job Object) and recovery.

## 4. What is cached, and why the comparison stays cheap

The ray tracer returns **path gain** between isotropic antennas. It does not depend on
transmit power, bandwidth, noise figure or thresholds. One map is therefore stored per

```
(scene hash, site position incl. antenna height, antenna pattern / orientation / polarisation,
 frequency, propagation settings, receiver grid, ray count, engine versions)
```

and everything else is NumPy arithmetic on cached maps:

- received power = transmit power + antenna gains + 10 log10(path gain) - extra losses;
- SINR = strongest site / (sum of the other sites + noise), summed in linear units;
- coverage, 5th-percentile rate and the greedy site selection re-use the same maps, so
  adding a site during planning never triggers new ray tracing.

A sector antenna pattern cannot be applied after tracing; it is part of the cache key.

## 5. Scene and mesh conventions (`bns.geospatial.osm_scene`)

- OSM lon/lat -> local transverse Mercator centred on the study box (scale 1), metres, z up.
- Footprints are repaired, simplified (0.3 m), clipped to the box, and holes that are tiny or
  hair-thin are filled.
- Where footprints overlap, the taller building keeps the shared ground. Touching footprints
  of equal height are merged into one solid, which removes the party wall between them.
  Touching footprints of different heights keep a coincident wall (counted in the scene
  metadata; a known source of spurious wedges).
- Extrusion: walls and roof share vertices so that roof edges and corners are diffraction
  wedges; **no bottom faces**, and walls start 0.5 m below ground, so footprints do not create
  false wedges at ground level. Ground is one quad. `edge_diffraction` stays off.
- Mesh checks on every build: no edge shared by more than two triangles, no degenerate
  triangle, roofs face up; the wedge count is recorded.
- Receiver cells that touch a footprint are masked as indoor and excluded from statistics.

## 6. Geospatial pipeline and calculation core (Phase 2)

```
configs/study_area.yaml ──► StudyArea ──► OSM snapshot (hashed, read-only)
                                              │ parse ways and multipolygon relations
                                              ▼
                          buildings with a HeightRecord each
                          (observed / estimated / placeholder; original tags kept)
                                              │ optional: manual observations, height model
                                              ▼
                          repair, clip, de-overlap   ──► buildings.geojson (per building, WGS84)
                                              │ merge equal-height neighbours
                                              ▼
                          meshes + scene.xml (Sionna RT) ──► quality_report.md / .json
```

- `bns.geospatial.pipeline.build_dataset` is the single entry point; it is independent of
  the district. A new area needs one entry in `configs/study_area.yaml`.
- **Provenance is per building, meshing is per solid.** Heights and their records live on
  the buildings table. For ray tracing, neighbouring buildings of equal height are merged
  into solids; the table is not affected by the merge.
- **Variants.** The same snapshot can be built with different height sources (OSM only, a
  height model with a seed, observations). Each variant gets its own folder and its own
  quality report, so results always name the variant they came from.
- **Rooftop candidates** (`bns.geospatial.sites`) and the **outdoor receiver grid**
  (`bns.geospatial.grid`) are pure functions of the buildings table.
- **Calculation core** (`bns.analysis`, `bns.optimization`): received power, SINR, Shannon
  rate, coverage, percentiles, CDF, RMSE and greedy site selection are pure NumPy functions
  with analytical tests. They take path gain and explicit radio parameters and know nothing
  about the engine. Radio parameters come from `configs/radio_system.yaml`, where each is
  undecided, provisional or approved; an undecided one stops the calculation.
- **Atmosphere** (`bns.propagation.atmosphere`): rain and gas loss as a per-cell loss map
  added in the link budget.

The Phase 0 scripts (`build_poc_scene.py`, `poc_validate.py`, `poc_benchmark.py`) still use
`osm_scene` directly and are kept so the Phase 0 evidence stays reproducible.

## 7. Production simulation pipeline (Phases 3-4)

```
configs/study_area.yaml ─► dataset (scene + buildings + quality report)    bns.geospatial.pipeline
configs/simulation.yaml ─► profile, mechanisms, seeds                       bns.simulation.setup
configs/radio_system.yaml ─► antenna (pattern, sectors, downtilt, mast)     bns.analysis.radio_system
        │
        ▼  one PropagationJob per site × sector × band          bns.simulation.jobs
   cache lookup by job key ──hit──► path gain                   bns.simulation.cache
        │ miss
        ▼  batches by scene and frequency, one fresh worker each bns.simulation.propagation
   worker (bns.simulation.worker) traces, stages <key>.npz + manifest
        │ only on clean exit: atomic publication into the cache (bns.runtime.run_isolated)
        ▼
   radio-system results from path gain                          bns.simulation.radio
   (power, gas/rain loss, noise, SINR with linear interference, coverage, Shannon rate)
        ▼
   run folder: manifest.json (every input, state and version), summary, figures, arrays
```

- **Propagation is separated from the radio system.** A `PropagationJob` contains only what
  changes the path gain: scene fingerprint (SHA-256 of `scene.xml` and every mesh, so
  geometry, heights and materials), frequency, transmitter position, antenna pattern,
  polarisation and orientation, receiver grid, mechanisms, ray count, seeds, engine versions
  and settings (including the wedge-table size). Its key is the SHA-256 of these fields.
  Transmit power, noise figure, bandwidth, thresholds, targets and load are not in the job,
  so changing them never re-traces; changing anything in the job always does.
- **Atomic publication.** A worker writes into a staging folder; the parent publishes into
  the cache only after a clean exit, data file first and manifest last, each by atomic
  rename. A cache entry counts only if its manifest exists and its checksum matches.
- **Progress and cancellation.** Workers report each finished job as a JSON line; the
  runner passes them to a callback. A cancellation callback kills the worker and discards its
  batch; batches finished before stay cached, so rerunning resumes.
- **Failure recovery.** Crashes (the Windows compiler instability) are retried with the
  kernel cache; Python errors stop immediately; nothing from a failed attempt is kept.
- **Antenna.** Sectors are separate traced transmitters. With the 3GPP TR 38.901 pattern
  traced, its 8 dBi are inside the path gain and no gain is added afterwards; the radio
  configuration refuses combinations that would count a gain twice.
- **Run modes.** Development runs use proposed values and stamp every output
  "DEVELOPMENT — NOT APPROVED FOR RESEARCH"; research runs refuse unapproved parameters and
  non-approved study areas.
- **Profiles** (`configs/simulation.yaml`, `docs/convergence.md`): preview 25 m / 1e8 rays,
  standard 10 m / 1e9 rays; the 5 m research profile is not yet validated and cannot be
  selected.

Engine-specific settings and limits in force: CPU variant `llvm_ad_mono_polarized`;
wedge table 2^20 slots; refraction and diffuse scattering off; radio-map diffraction
first-order and never after a reflection; power sums without phase; isotropic receiver;
no gas or rain inside the engine (added afterwards).

## 7a. Multi-site network, experiments and application (Phases 5-6)

```
bns.simulation.experiment   dataset + grid + sites + jobs + radio inputs (shared by scripts and app)
        │ jobs for every site × sector × band, served from the path-gain cache
        ▼
bns.simulation.network      sectors [k, y, x] + sector->site map
        │  strongest sector serves; all other sectors interfere (linear sum × activity)
        ▼
NetworkResult               radio (power, SINR, rate, coverage), serving sector and site,
                            interference map, interference-limited share, served shares
        ├─ sites_alone          each site by itself (its own sectors still interfere)
        ├─ grown in order       1, 1+2, 1+2+3, ... sites
        └─ greedy (SINR)        bns.optimization.greedy.greedy_sinr_site_selection
```

- **Sites and sectors stay distinct.** Every sector is its own traced transmitter (cache key
  includes its orientation); the site index of each sector is carried alongside, so results
  report serving *site* and serving *sector* separately.
- **Interference model** (`bns.simulation.network.INTERFERENCE_ASSUMPTION`, written into every
  summary): one carrier for all sectors (reuse 1), co-located sectors interfere, power summed
  in watts and scaled by the interference activity (load) of the non-serving sectors, no
  scheduler: the Shannon rate is for one user using the whole carrier, so more sites never
  share load. Adding a site is never assumed to help; the greedy evaluates the whole network
  for each addition and lists additions that would lower coverage.
- **Experiment scripts.** `scripts/run_multi_site.py` (1 site = single-site case; all five
  bands; network, each site alone, growth in order, SINR greedy; CSV per band with local and
  WGS84 coordinates, sites as GeoJSON, figures, manifest with every input and job key).
  `scripts/run_single_site.py` is kept for its existing standard run.
- **Application** (`app/`, Streamlit; `uv run streamlit run app/main.py`). UI code only in
  `app/`; everything else in `bns.app`:
  `results` (find and read saved runs; never re-traces to display), `control` (start the
  experiment script as its own process with a log file and a cancel file under
  `outputs/app_runs/<id>/`; state parsed from the log, so it survives page reloads),
  `planning` (re-evaluate any subset of a saved run's sites, or rerun the SINR greedy, from
  the cached path gain; refuses if a cache entry is missing or the grid changed, warns if
  radio parameters changed). Cancelling stops the running worker; finished batches stay
  cached and a rerun resumes.
- **Raw data stays byte-exact.** `.gitattributes` marks `data/raw/**` as not text, so git
  never converts line endings in hashed snapshots and extracts (`core.autocrlf` once broke
  a snapshot's SHA-256).

## 8. Deviations from the structure in the master brief

| Brief | Here | Reason |
|---|---|---|
| Folder `baghdad-network-simulator/` | existing `baghdad_network_simulator/` | Kept the folder the user created |
| Loose packages `src/core`, `src/domain`, ... | One package `src/bns/` | `import core` style top-level names collide easily; one namespace is safer |
| `propagation/base.py`, `matlab_engine.py`, `sionna_engine.py` | `sionna_engine.py` only | One engine; an interface with a single implementation adds nothing yet. To be introduced if a second engine is ever needed |
| Parquet, Pydantic | `.npz` + JSON in Phase 0 | Arrive with the storage layer and configuration validation (Phases 3-6) |
| Empty folders for later phases | not created | Created when first used |
