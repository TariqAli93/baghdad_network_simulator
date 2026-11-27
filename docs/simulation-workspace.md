# Simulation workspace: audit, design and implementation

Status (2026-11-27): **implemented on the branch `feature/simulation-workspace`, not merged.** The
Simulation Workspace is the landing page of the application:

```
uv run streamlit run app/main.py            # Arabic by default; ?lang=en for English
```

`master` and the delivery candidate (`dist/…-8e5b5b7.zip`) are unchanged and stay the fallback until
the workspace is verified and merged. The repository is in feature freeze since v1.0.0-rc.1; this work
follows the project owner's request of 2026-11-27 to make the application an interactive simulator.

Decisions of the project owner (2026-11-27, after the prototype review):

1. The workspace replaces the dashboard as the landing page.
2. Manual placement on a roof that satisfies the site rule is not by itself a deviation from the
   research baseline; it is recorded as **manual placement**, separately from automatic selection.
3. Hypothetical transmitter placements are allowed in technically valid locations and are custom
   experiments.
4. Experiments are saved, loaded and run into persistent results before the navigation is changed.

Sections 1-3 describe the audit and the design as reviewed; section 8 describes what was added for
production (experiments, custom carriers, placement, reliability, navigation).

## 1. Audit: the application today

| Step of one experiment | Where it happens now | Friction |
|---|---|---|
| Configure | Run Simulation page: area, dataset, profile, then a parameter form in an expander | Settings are a form, away from any map |
| Place stations | Same page: "candidate rooftops (rule)" with a count, or OSM building ids typed as text | No map to place, move or remove a station |
| Simulate | Same page: "Check sites and workload", then "Start run"; progress in a history list | The result is not shown where the run was started |
| Visualise | Coverage page: pick the saved run again, then a band and a layer | A fourth page; Plotly heatmap, display only |
| Compare | Comparison page (six tabs), Planning page (re-evaluation from the cache) | Two more pages; separate run pickers |

The landing page is a dashboard of cards, readiness indicators and a "next step" suggestion. The maps
are Plotly heatmaps without click handling: a station cannot be selected, placed, moved or removed on
them, and a receiver cell can only be hovered.

The engine side is sound and needs no change. Everything the workspace needs already exists:

| Capability | Module | Used for |
|---|---|---|
| Experiment set-up (dataset, grid, outdoor mask, radio system, classification) | `bns.simulation.experiment.load` | loading a design's context |
| Propagation job and its cache key; sector antennas; bearing convention | `bns.simulation.jobs`, `bns.simulation.setup` | the staleness rule (section 3.3) |
| Isolated workers, retries, publish on a clean exit, cancellation | `bns.runtime`, `bns.simulation.propagation` | the Run action |
| Path-gain cache with checksums | `bns.simulation.cache` | reuse and instant re-evaluation |
| Network model (serving sector, interference, Shannon rate) | `bns.simulation.network`, `bns.simulation.radio` | every result in the workspace |
| Band rate mappings (LTE, NR, NR-based approximation) | `bns.analysis.rate_models` via `experiment.mapped_rate_bps` | rate beside Shannon |
| Rooftop rule, roof-edge antennas, monument exclusion | `bns.geospatial.sites` | placement |
| Interference-aware SINR greedy | `bns.optimization.greedy` | automatic planning over the shown stations |
| Classification and validation scope | `bns.analysis.classification`, `validation_scope` | the result label |
| Saved runs | `bns.app.results` | opening a run in the workspace |
| Arabic/English catalogues, right-to-left | `bns.i18n`, `app/ui.py` | all text |

## 2. Technology evaluation

The question was whether Streamlit's own map and event handling can carry an interactive simulation
workspace, before committing to an architecture. The installed version is Streamlit 1.67.0.

| Need | Plotly in Streamlit (`on_select`) | pydeck in Streamlit (`on_select`) | Custom component (`st.components.v2`) |
|---|---|---|---|
| Select a station or building | yes (point selection) | yes (picking) | yes |
| Click empty ground to place a station | no: selections return data points, not coordinates (workaround: an invisible point lattice) | no: only pickable objects | yes |
| Drag a station | no (layout changes are not returned) | no | yes |
| Hover readout of the result cell | tooltip only | tooltip only | status bar with value, unit, building and station |
| Measure a distance | no | no | yes, in the browser |
| Pan and zoom without a rerun | yes | yes | yes |
| Cost of a click | full script rerun | full script rerun | one event to Python; pan, zoom, hover and measuring stay in the browser |
| Offline | yes | yes, without a basemap | yes: inline JavaScript, no iframe, no build step, no CDN |

Decision for the prototype: **keep Streamlit and the Python engine, and add one targeted map component**
(`app/components/network_map.js`, `network_map.css`; about 600 lines of plain JavaScript on a canvas).
Streamlit 1.50+ components v2 mount inline: the JavaScript keeps its state on the same DOM node across
reruns, so the view survives every edit, and an event reaches Python through an `on_event_change`
callback before the page is redrawn. Plotly stays for charts.

A separate web frontend (for example FastAPI with MapLibre, Leaflet or deck.gl) was considered and is not
proposed. It would need a second toolchain, offline map tiles or a tile-free set-up, a second
implementation of the Arabic/English text and right-to-left layout, and new run management. The
prototype shows that Streamlit plus one component meets the interaction needs, so a migration is not
justified.

3D view (secondary): `pydeck` could extrude the 2,521 footprints with their heights offline, without
a basemap. It was not built: it would be a second rendering path for a view that answers no question the
2D map does not. It can be added later as a read-only view if the review asks for it.

## 3. The workspace

### 3.1 Layout and workflow

One screen, three regions, the map dominant (about 60 % of the width):

```
| Settings (start side)       | Band selector                                  | Results (end side)          |
|  study area, dataset        | Layer · building fill · candidate roofs       |  state: current / stale /   |
|  displayed scenario         |  ┌─────────────────────────────────────────┐  |    running / no stations    |
|  new stations: antenna  [T] |  │ Select · Place · Move · Measure · Fit   │  |  classification (one line)  |
|  new stations: power    [I] |  │                                         │  |  coverage, Rx power, SINR,  |
|  receivers              [T] |  │      network map (canvas, offline)      │  |  rates (Shannon + mapping), |
|  load and coverage      [I] |  │                                         │  |  stations, trace time       |
|  resolution and engine  [T] |  │ scale · north · legend · status line    │  |  Simulation: run, progress  |
|  advanced (collapsed)       |  └─────────────────────────────────────────┘  |  Selected object editor     |
|  stations: site rule, run   | Compare bands and configurations (collapsed)   |  Station list               |
```

`[T]` marks controls that need ray tracing ("needs ray tracing"); `[I]` marks instant ones. The tags are
on the section headings, so the cost of a change is visible before it is made.

Workflow: **configure → place stations → simulate → visualise → compare** on this one screen. On launch
the workspace opens the newest saved run of the study district's primary dataset, preferring a CPU
research-baseline run. Today that is the demonstration run on the Synthetic Urban Model, so the first
screen shows real stations with current results from the cache.

### 3.2 Map interactions

| Tool | Action | Result |
|---|---|---|
| Select | click a station / building / receiver cell | station editor / height, provenance and site-rule check / every computed value of that cell |
| Select | drag, wheel, double-click | pan, zoom (in the browser, no rerun) |
| Place station | click a roof | rooftop station at the site rule's rooftop point of that building, mast on the recorded roof height |
| Place station | click open ground | refused by default; with "Allow hypothetical stations" and an explicit antenna height, a **hypothetical** station (hollow dashed diamond on the map) |
| Move | drag a station, or select one and click | the station moves and snaps to the roof it lands on; its radio and antenna values are kept |
| Measure | click two points | distance in metres (local transverse Mercator), in the browser |
| any | Esc, Delete | back to Select / remove the selected station |

Monuments, memorials and artworks are refused as hosts (`sites.is_structure_not_building`). The station
editor gives position (x, y, and latitude/longitude), mast or antenna height, power, sectors, sector-1
bearing, downtilt, pattern, transmitting on/off and Remove. It also shows the nearest transmitting station
against the site-rule spacing, and how many of the station's traces for this band are cached.

Layers: buildings (outline, height, height source), received power, SINR, coverage, data rate (Shannon),
data rate (band mapping), serving station, interference, path gain. Continuous layers use fixed ranges,
the same in every band (`ui.LAYERS`; rates share the largest 99th percentile of the evaluated bands).
Indoor cells are transparent, and unreached outdoor cells have their own "no path" colour. Sector
wedges show each sector's bearing with ±32.5° (the 65° half-power beamwidth of the TR 38.901 element) as
a drawing aid. Dots mark the traced antenna positions at the roof edge.

### 3.3 What needs ray tracing, and what does not

A station becomes exactly the `PropagationJob` objects the experiment scripts trace. The cache key
therefore decides the cost of a change; there is no hand-written list that could drift.

| Change | Job keys | Effect |
|---|---|---|
| position, mast or antenna height, pattern, sector bearing, downtilt | change for that station | its traces are missing → results **stale** until traced |
| fewer sectors (e.g. 3 → 2) | sector 1 keeps its bearing and its key | only the sectors that moved need tracing |
| receiver height, cell size, ray count, backend, dataset | change for every station | everything stale |
| transmit power, noise figure, coverage threshold, network load, rain | unchanged | recomputed from the cache in NumPy, at once |
| switching a traced station on or off | unchanged | recomputed at once |

Results are computed only from the cache entries of exactly the stations shown, in the displayed band
(`workspace.evaluate`). If one entry is missing, the evaluation refuses (`MissingTraces`). The last
results for that band then stay on screen, faded and hatched under the badge "Results of the previous
configuration. Trace to update them.", and their metrics are greyed. Previous results are never shown as
current.

### 3.4 Classification of a design

The design is classified by the same rules as every run (`classification.classify`, with the design's
own antennas in the validation scope). Departures recorded as deviations:

- a hypothetical station (not a rooftop site);
- a roof outside the candidate rule (height, area, height category);
- per-station power, downtilt, sector count, mast height or pattern that differ from the baseline values;
- sector bearings other than 0/120/240°;
- antennas at the site point instead of the roof edge (only for runs opened from before decision A4);
- the profile and backend deviations `experiment.baseline_deviations` already records.

Changing only the threshold, load or rain gives a Sensitivity Analysis. A station placed by hand on a roof
that satisfies the candidate rule is *not* a deviation, which matches `run_multi_site.py --buildings`
(open decision R2 below).

### 3.5 Profiles and execution

| Profile | Cells | Rays per sector | Basis (configs/simulation.yaml) |
|---|---|---|---|
| Preview | 25 m | 10⁸ | 95 % of cells within 2.9 dB of a 10⁹-ray map |
| Standard (research baseline) | 10 m | 10⁹ | two 10⁹-ray maps within 1.4–2.0 dB for 95 % of cells (borderline, accepted) |
| Custom | user | user | not convergence-checked → custom experiment |

The settings panel states the measured median time per trace on this computer
(`experiment.measured_trace_seconds`). It does not promise real-time ray tracing.

Run: "Run simulation (n traces)" or "This band only (n)" saves the experiment and starts
`scripts/run_workspace.py` in its own process (`bns.app.workspace_runs`). It traces the missing jobs through
`propagation.compute` (isolated workers, retries, cache), evaluates every requested carrier and writes an
immutable run in the multi-site format (section 8.2). The results panel shows the band, station and sector
being traced, cached / to trace / committed / remaining traces, retries, elapsed time, an estimate and
Cancel; the page stays usable. When the run ends, the workspace evaluates whatever the design is *now*:
if it changed during the run, it stays stale. Commit granularity and cancellation: section 8.4.

### 3.6 Comparison

Under the map, "Compare bands and configurations":

- **Five bands**: the selected layer in every band with current results, on one colour scale, and a
  table of coverage, received power, SINR, Shannon and mapped rates. Bands that still need traces are
  listed as such. The text labels Shannon rates as theoretical bounds and the candidate 6G mapping as an
  NR-based approximation.
- **Configurations**: pin the current configuration as a reference, change stations or values, and
  compare per band. On the same receiver grid, a difference map (now minus reference) is drawn with a
  diverging scale.

Automatic planning (end side, "Automatic site planning over these stations") runs the project's
interference-aware SINR greedy (`greedy_sinr_site_selection`, unchanged) over the shown stations, and can
keep only the selected ones switched on. The full candidate planning (`scripts/plan_sites.py`) stays
where it is.

## 4. Implementation

| File | Content |
|---|---|
| `src/bns/app/workspace.py` | stations, placement, jobs, trace status, evaluation, greedy, classification, opening saved runs (no UI code) |
| `src/bns/app/workspace_runs.py` | start, follow and cancel a run; log protocol, commit policy, estimate |
| `scripts/run_workspace.py` | traces what is missing, evaluates every carrier, writes the run |
| `src/bns/app/experiments.py`, `carriers.py`, `run_record.py` | experiments, carriers, run writer (section 8) |
| `app/views/workspace.py`, `history.py`, `research_status.py` | the pages (section 8.5) |
| `app/components/network_map.js`, `.css` | the map component (components v2, inline, offline) |
| `src/bns/i18n/locales/{en,ar}/workspace.yaml` | every text, both languages |
| `tests/unit/test_workspace.py`, `test_workspace_runs.py`, `test_carriers.py`, `test_experiments.py` | identical job keys, staleness, placement, evaluation, per-station power, greedy, classification, saved runs, carriers, experiments, run records, log parsing |
| `tests/app/test_workspace_page.py`, `test_pages.py`, `test_i18n_pages.py` | opt-in headless page tests (`-m app`) |

No configuration value was changed. Per-station power enters the
existing radio model as one power per sector. `link_budget.received_power_dbm` broadcasts it; the
value added to the path gain follows `RadioSystem.tx_power_for_path_gain_dbm`, so no antenna gain is ever
added on top of a traced pattern.

## 5. Verification (executed 2026-11-27, development PC)

Tests:

- `uv run pytest`: 473 passed, including the 40 new unit tests (`test_workspace.py`, `test_workspace_runs.py`).
  Among them: a station on a rule roof traces exactly the jobs `experiment.jobs_for` creates; evaluation
  equals `network.network` for the shown stations; lowering one station's power by 3 dB lowers only the
  power received from it by 3 dB; the greedy over the shown stations equals `greedy_sinr_site_selection`.
- `uv run pytest -m app`: 56 passed. These are every production page in both languages (unchanged) and
  the 4 workspace page tests (`tests/app/test_workspace_page.py`): the page runs in English and Arabic
  without exception; shown SINR and coverage equal the saved run's summary; a load change stays current
  and becomes a Sensitivity Analysis; a receiver-height change makes the results stale and offers tracing.

Saved runs rebuilt from their manifests (`workspace.stations_from_run`, CPU and GPU runs):

- all 13 readable multi-site runs (15 or 60 recorded traces each) and all 7 site plans (300–495 each):
  every recorded job key reproduced. One run folder without a manifest was skipped. Runs from before the
  roof-edge rule (decision A4) reproduce only with their antennas at the site point; the workspace
  records that as a deviation;
- the research-baseline demonstration run
  (`multi_site-…synthetic_urban-seed42+fp_3d_globfp-standard-1sites-20261127T121824Z`): coverage, median
  and 5th-percentile SINR, median and 5th-percentile Shannon rate and median received power are
  bit-identical to its `summary.json` in all five bands; the classification is identical
  (Simulation Results · Research Baseline · Estimated Building Heights · Validation Pending);
- the 4-site preview run on `osm+fp_3d_globfp`: identical except in the last floating-point digit
  (relative 10⁻¹⁶) of three rate percentiles, because the power is applied per sector.

In Chrome (agent-browser, 1600 × 1000, English and Arabic), against the running prototype:

- start: the demonstration run opens as station S1 with current 5G 3.5 GHz results (coverage 100.0 %,
  median SINR 18.5 dB, 5th-percentile Shannon rate 134.7 Mbit/s, band mapping 80.8 Mbit/s);
- select a station, a building and a receiver cell; Place on open ground is refused with the reason
  (hypothetical stations off); Place on a roof (`3d_globfp/rec/696321`, synthetic 12 m) gives S2 at the
  rooftop point with a 15 m antenna and its three roof-edge antenna positions;
- the results turn stale at once (badge, faded and hatched layer, greyed values, "this band needs 3 traces");
- Run "Trace this band (3)" on the standard profile, CPU: the panel showed the band, station and sector
  being traced, "3 already cached · 3 new" and the elapsed time, and the page stayed usable. Measured: the
  three traces took 191.3, 201.7 and 166.3 s; the worker then did not exit cleanly, so `run_isolated`
  traced the batch again (176.6, 192.8, 172.9 s). Total 1,111.8 s, against an estimate of 3.7 min shown
  before the run. The estimate is the median of earlier standard CPU traces on this PC (now 75.7 s over 44
  traces) and leaves out retries, as `experiment.workload` notes. Why these traces took 166–202 s was not
  investigated; slower ones (216 s, 248 s) were already in the cache record. The progress panel now
  reports a retry (`RETRY` line) instead of silently restarting the count;
- after the run the workspace evaluated the new design by itself: 2 stations, 6 sectors, coverage
  100.0 %, median SINR 12.4 dB, 5th-percentile Shannon rate 101.9 Mbit/s, band mapping 61.2 Mbit/s, 98 %
  of cells interference-limited (S1 alone: 93 %);
- in a new session, placing a station on the same roof gave current results at once, with the same
  values (cache reuse, no tracing);
- dragging S2 to another roof snapped it to that roof's rooftop point and made the results stale again;
- Arabic: settings on the right, results on the left, toolbar and legend mirrored, map not mirrored;
  numbers and identifiers kept left-to-right.

## 6. Navigation (implemented)

| Section | Built from |
|---|---|
| 1. Simulation Workspace (default) | `app/views/workspace.py`; replaces the Dashboard and Run Simulation pages |
| 2. Scenario Comparison | Comparison page (bands, runs, site plans, model-to-model, sensitivity) and two runs side by side on one scale |
| 3. Automatic Site Planning | Planning page (`plan_sites.py` runs); the workspace runs the same greedy over its own stations |
| 4. Experiment History | new: experiments, completed runs, background simulations; the Coverage page is its run viewer |
| 5. Reports | Reports page (workspace runs included) |
| 6. Settings and Research Details | Research status (the dashboard's readiness section), Study Area, Radio, Validation, 6G Roadmap |

The navigation is a top bar (`st.navigation(position="top")`), so the map keeps the full width. No
scientific function was removed: the run scripts are unchanged and their runs appear in the history.

## 7. Limitations

- Hypothetical stations stand on the scene's ground plane (z = 0, no terrain model).
- One simulation at a time (runs share the CPU); the workspace shows a run started elsewhere.
- Map interactions cannot be driven by Streamlit's AppTest; they were checked in Chrome (sections 5, 9).
  Touch input and screen-reader use of the canvas are untested. The toolbar is keyboard-operable, and the
  station list and editor give a non-map path to every station property.
- The 3D view is not built (section 2).
- Gas loss for custom carriers: resolved in the final integration (section 10.1): ITU-R P.676 through
  ITU-Rpy at any carrier other than the five presets.
- The user guides: rewritten around the workspace in the final integration (section 10.4).

## 8. Production implementation (branch `feature/simulation-workspace`)

### 8.1 Experiments and runs

An **experiment** is an editable configuration (`bns.app.experiments`, `outputs/experiments/<id>.json`,
git-ignored): dataset and variant, profile, cell size, rays, backend, receiver height, radio values,
carriers (the five presets with a run flag, custom frequency/bandwidth), stations with every property,
and the values for new stations. Actions: new, save (atomic replace), save as, rename, duplicate,
duplicate as candidate 6G (same stations, the two 6G presets), open, delete with confirmation (moved to
`outputs/experiments/.deleted/`), run again, export report. A **run** is an immutable result folder; an
experiment's runs are found from the runs' own manifests (`experiment.id`), so saving, renaming or
deleting an experiment never touches a result, and a run started in the background never races a save.

### 8.2 Run format

`scripts/run_workspace.py` writes the existing multi-site format (`bns.app.run_record`): `manifest.json`,
`summary.json` (network, every station alone, the network grown in order, additions that lowered
coverage, the SINR greedy), `network.npz`, `summary.md`, `cells_<carrier>.csv`, `sites.geojson` and the
figures. Additions: `"source": "workspace"`, the experiment with a copy of the executed configuration,
every station with its own antennas and bearings, the carriers, gas treatment, value (dB/km) and model
version per carrier, and the placement in the classification. History, Comparison and Reports read it like any run; the Planning
page refuses to re-evaluate it (per-station values belong to the workspace).

### 8.3 Carriers (custom frequency and bandwidth)

`bns.app.carriers`, `docs/assumptions.md` section 10. A custom frequency must lie where every model
applied at it is defined (`supported_ranges_hz`): the scene materials in the installed Sionna RT (read
from its ITU-R P.2040 table without importing the engine: concrete 1-100 and 110-330 GHz), ITU-R P.676
Annex 1 (1-1000 GHz) and the antenna element of the stations (TR 38.901: 0.5-100 GHz), so 1-100 GHz with
sector antennas. Gas loss is the stored value at the five presets and ITU-R P.676 through ITU-Rpy at any
other carrier (section 10.1); the bandwidth must lie between 0.1 MHz and a quarter of the carrier. Unsupported
values are refused with the reason, never adjusted. Radio values and the rate mapping come from the
preset. Any change from a preset makes a Custom Experiment and is named in the deviations;
"Equal bandwidth" gives every carrier one bandwidth for controlled comparisons. Candidate 6G presets
have exactly the same tools as 4G and 5G and are always labelled as candidate research scenarios.

### 8.4 Reliability, cancellation and progress

Investigation of the slow prototype run: `docs/benchmarks.md` section 12 (cause: the Windows Power saver
plan, about 2×; a retry after an unclean worker exit doubled the run). Changes:

- every worker attempt is reported with its exit code (`run_isolated(on_attempt=...)`), so a retry is
  never silent; workers record the power plan, and the workspace and `doctor` warn under Power saver;
- commit granularity: traces expected to take 30 s or more get one worker each, so a crash at exit or a
  cancellation loses at most one trace; a worker that does not exit cleanly still publishes nothing, and
  the cache verifies every entry's checksum before reuse;
- progress: the band, station and sector being traced, traces cached before, to trace, committed and
  left, retries, elapsed time and an estimate (this run's own trace times, else recent traces of the same
  scene and profile, plus worker start-up; retries not included, stated as an estimate).

### 8.5 Classification

Configuration (research baseline / custom experiment / sensitivity analysis), **placement**
(automatic / manual / hypothetical), dataset (complete / estimated heights / incomplete) and validation
(completed / pending) are recorded separately; execution (ready / running / completed / cancelled /
failed) is shown separately again. `run_multi_site.py` and `plan_sites.py` now record placement too.
The dataset class keeps its existing names ("Complete data" is the documented class).

## 9. Production verification (2026-11-27, development PC, branch `feature/simulation-workspace`)

Tests: `uv run pytest` 509 passed; `uv run pytest -m app` 59 passed (every page in English and Arabic,
the workspace as landing page, a radio change becoming a custom experiment and the reset restoring the
baseline, staleness, the saved run's values shown exactly). App tests use a temporary experiments
folder (`BNS_EXPERIMENTS_DIR`), never the user's.

In Chrome against `app/main.py` (port 8765), English and Arabic, every item of the request's section 12:

| Check | Result |
|---|---|
| Place a station manually | S1 by clicking the roof of way/919688856 (Place tool): rooftop point, mast on the 55 m roof |
| Add a second station | S2 on 3d_globfp/rec/696321 (12 m synthetic roof) from the building inspector ("Place a station on this roof") |
| Edit stations independently | S1 downtilt 6°, S2 43 dBm; saved experiment and run manifest record S1 46 dBm / 6°, S2 43 dBm / 10° |
| Candidate 6G selected and configured | carriers 5G 3.5 GHz and candidate 6G 8 GHz, equal bandwidth 100 MHz (8 GHz custom, labelled; preset NR-based mapping kept) |
| A real simulation completes | preview profile, CPU: 12 traces; batch 1 (6 traces) ended with exit code 0xC0000374 and was traced again, as the clean-exit rule requires (shown as a retry); 175.9 s in all; run written |
| Real results on the map | SINR, received power, coverage and rates of the run's carriers; 8 GHz / 100 MHz: coverage 100.0 %, median SINR 14.6 dB, 5th-percentile Shannon rate 100.1 Mbit/s (mapped 60.1 Mbit/s), 97 % interference-limited cells |
| Save and reopen | saved as "Verification: 5G and candidate 6G at 100 MHz"; a new experiment, then Open: name, carriers, both stations and current results back (from the cache) |
| History and Reports | both runs in Experiment History (source workspace, classification "Custom Experiment · manual placement"); report exported from the workspace (HTML, interface language) and shown on the Reports page with all deviations |
| Stale marking | receiver height 1.5 → 2 m: "Stale: this band needs 6 traces", faded and hatched map, greyed values, 12 traces offered; back to 1.5 m: current again from the cache |
| Cached traces reused | "Duplicate as candidate 6G": the 8 GHz preset (400 MHz) is current at once from the 100 MHz run's traces (the bandwidth is not in the job key); a run of that band wrote 6 of 6 traces from the cache in 1 s |
| Identical station locations | Scenario Comparison, two runs side by side: "identical station locations"; 6G 8 GHz / 400 MHz and 5G 3.5 GHz / 100 MHz on one SINR scale |
| Arabic and English | workspace, history, comparison, reports in both; right-to-left layout, map not mirrored |

Cancellation and resume (standard profile, CPU, candidate 6G 15 GHz, one station, 3 traces), through the
run interface the workspace uses: one worker per trace (expected 91 s from this scene's recent traces);
trace 1 committed after 85.7 s (2 s worker overhead), estimate for the rest 176 s; cancelled → "Cancelled",
1 committed trace kept. Restarted: "3 jobs, 1 cached, 2 to trace"; both traced (98.7 s and 83.2 s per
worker, clean exits); run written in 184.3 s.

Findings fixed during the verification: widget values lost after visiting another page (Streamlit drops
the state of widgets that are not drawn); a placement message above the map remounted the map (tool, zoom
and pan lost); a first "Save as" recorded a copy of an unsaved experiment; reports did not list
per-station deviations; side-by-side maps had different extents.

Known: right after switching the language, two keyed selectors (layer, building fill) keep the previous
language's option text until the next interaction or a reload.

Concurrent use: during the verification a second instance of the application (port 8501, started from
this folder at 17:53 local time) was in use. Its session created the experiment "شبكة العرض التوضيحي"
and ran it (8 GHz, standard profile, 471 s, with retries after first-compile crashes, one trace per
worker). It is kept as found. Verification data left in place (not committed): the experiments
"Verification: …" in `outputs/experiments/` and the runs `…-ws-20261127T150723Z`, `…T150920Z`,
`…T152310Z` in `outputs/runs/development/`.

## 10. Final production integration (2026-11-27)

### 10.1 Gas attenuation at custom carriers: ITU-Rpy

Authorised addition of `itur` (ITU-Rpy) after compatibility and licence checks:

| Check | Result |
|---|---|
| Version and lock | `itur==0.4.0` in `pyproject.toml` and `uv.lock`; `uv sync --frozen --dry-run`: "Would make no changes" |
| Licences | ITU-Rpy MIT; astropy 8.0.3, pyerfa 2.0.1.5 and astropy-iers-data BSD-3-Clause (`docs/licensing.md`) |
| Environment | Python 3.13, NumPy 2.5.5, SciPy 1.18.1, pyproj 3.8.0, Sionna RT 2.2.0: unit, app and engine suites pass |
| Recommendation edition | ITU-R P.676-12 Annex 1 (`itur.models.itu676.get_version()` = 12), recorded with every value |
| The five presets | ITU-Rpy gives 0.006750 / 0.007810 / 0.011416 / 0.029058 / 0.101756 dB/km at 1.8 / 3.5 / 8 / 15 / 28 GHz; stored 0.0068 / 0.0078 / 0.0114 / 0.0291 / 0.1018 (largest difference 0.00005 dB/km, the stored rounding) |
| Offline | import and calculation in a process whose network calls are disabled (`tests/unit/test_atmosphere.py`) |
| Clean installation | installed from the lock file by `1 - Install.cmd`; the doctor checks the pin (`package itur: 0.4.0`) |

Supported frequency range of a custom carrier: the intersection of the models applied at it
(`bns.app.carriers.supported_ranges_hz`).

| Model | Defined for |
|---|---|
| Scene materials (ITU-R P.2040 in the installed Sionna RT; concrete) | 1-100 GHz and 110-330 GHz |
| Gas attenuation (ITU-R P.676 Annex 1) | 1-1000 GHz |
| Antenna element: 3GPP TR 38.901 sector pattern / isotropic | 0.5-100 GHz / no limit |
| Ray-tracing numerics | no frequency limit in the radio map; ray counts were measured only at the five carriers (`docs/convergence.md`) |
| **Result** | **1-100 GHz with sector antennas**; 1-100 and 110-330 GHz with isotropic antennas only |

Nothing is extrapolated outside it; the bandwidth limit (0.1 MHz to a quarter of the carrier) is unchanged.

Scientifically meaningful calculation change (recorded in `docs/assumptions.md` section 10): before this
integration a custom carrier between 1 and 30 GHz ran **without** gas loss (recorded "omitted") and one
above 30 GHz was refused. Now every custom carrier gets its P.676 value (for example 0.0095 dB/km at
6 GHz, 0.1089 at 20 GHz, 14.78 at 60 GHz). The five presets keep their stored values, so the research
baseline and every earlier run are unchanged; runs recorded "omitted" are read as recorded and never
recomputed. Gas loss is applied after ray tracing: the path-gain cache does not depend on it. The value,
edition and library version are stored in the carrier, in the run manifest (`atmosphere.gas`,
`gas_db_per_km`, `gas_models`, `versions.itur`) and in the classification's deviations; the workspace's
evaluation cache is keyed by the whole carrier record, and a saved run's results are shown for a carrier
only when its gas treatment, value and model match.

### 10.2 Demonstration experiment

`outputs/experiments/demo-research-baseline-network.json` ("Demonstration: research-baseline network ·
عرض توضيحي"): the research-baseline run of the study district on the Synthetic Urban Model as an
experiment (S1 on the site-rule roof, the five presets, standard profile, CPU), with its workspace run
`…-standard-1sites-ws-20261127T162816Z` written from the 15 cached traces (no new tracing). Coverage,
median SINR and 5th-percentile rates equal those of the original run in every band. It is the only
experiment file tracked (`.gitignore`) and is required in the delivery archive. A fresh installation has
no path-gain cache: the workspace shows the saved run's results (marked "read from the saved run of
27 November 2026, 16:28") because the experiment's design matches that run exactly.

### 10.3 Verification in the installed candidate (development PC, Chrome, both languages)

A candidate archive of the branch was installed into a new folder with `1 - Install.cmd`
(234 s with a warm uv cache, 0 FAIL, `package itur: 0.4.0` PASS, 419 of 419 files match
`SHA256SUMS.txt`; the one WARN was the port of the development instance). Started with `run.ps1`:

| Check | Result |
|---|---|
| Opens into the workspace | yes, in Arabic, on the demonstration experiment with its saved results |
| Language switch | the whole workspace changes at once: layer, building fill, saved run, band and profile selectors, station properties, results, classification, progress during a run; experiment names keep their Unicode text |
| Custom carrier | 15 → 20 GHz accepted, shown as "custom · gas 0.109 dB/km (P.676)", the experiment becomes a Custom Experiment; a real preview run of that band (3 traces, 41 s) recorded `p676`, 0.108931 dB/km, "ITU-R P.676-12 Annex 1" and "ITU-Rpy 0.4.0" in its manifest |
| Run, progress, save | preview profile, 12 traces in 115 s and 15 traces in 144 s, every worker attempt exit code 0; progress shows the trace in progress, cached / to trace / committed / left, elapsed time and estimate, in either language mid-run; the experiment is saved before the run |
| Results and inspection | result layers, legend, a receiver cell's values; the map hatched as stale after a receiver-height change |
| History and comparison | two runs with identical stations chosen in the History open under Across runs; "Two runs side by side" states the identical station locations |

Defects found and fixed during this verification (all display or localisation):

- the results state box laid its text out as side-by-side columns (a flex container); the saved run is
  now named by its date, not its folder name;
- the Cancel button covered the last progress line (Streamlit pulls the element after a markdown block
  up by 1 rem; the workspace's blocks have no paragraph margin to absorb it);
- in Arabic a custom carrier's label ("15 GHz → 20 GHz / 400 MHz") and receiver-cell and station
  coordinates were reordered by the bidirectional algorithm: the values are now isolated left-to-right
  and the arrow follows the reading direction; the P.676 state reads "توهين غازي … dB/km (P.676)";
- the second map of "Two runs side by side" was stretched (a shared y axis ignored its aspect lock);
- the runs chosen for comparison, the comparison metric and the sites chosen on the Automatic Site
  Planning page fell back to their defaults when the language changed (`ui.multiselect`, as `ui.select`).

Known limitation: other view choices without a stored value (Planning layer, scenario and sensitivity
sliders; Study Area colouring; the Sensitivity load; the Reports figure) return to their defaults when
the language is switched. Nothing is lost from experiments or runs.

### 10.4 User guides

`docs/user-guide.md` and `docs/user-guide.ar.md` are rewritten around the workspace (create an
experiment, study area and dataset, place and configure stations, 4G/5G/candidate 6G, custom frequency
and bandwidth, run and cancel, results, save/reopen/duplicate, 5G versus candidate 6G with identical
stations, reports, classification labels), with screenshots of the installed candidate in each language
(`docs/images/user-guide/{ar,en}/`). The research guides and the README point to the new pages.

### 10.5 Reliability

- Committed traces are kept on cancel and a resume traces only the missing ones
  (`tests/unit/test_simulation_propagation.py`; real standard-profile run in section 9).
- A worker that does not exit cleanly never writes to the cache (same tests; section 9).
- Estimates divide by (1 − observed retry rate, at most 0.5) and add the worker start-up
  (`bns.app.workspace_runs`).
- Path-gain job keys hold every propagation input (scene, frequency, position, antenna, grid,
  mechanisms, rays, seeds, engine; `docs/benchmarks.md` section 12); gas and rain are applied after
  tracing and recorded per run.
- Power plans are diagnostic only: the workspace warns about Power saver, the doctor reports PASS for
  any other plan (Balanced included, unit test) and nothing changes the plan. During this verification
  the development PC ran Ultimate Performance; a Balanced plan was not exercised on it.

### 10.6 Merge and delivery candidate

`feature/simulation-workspace` was merged into `master` without fast-forward (merge commit `159cdd1`;
history and the 8 tags unchanged; nothing pushed). The merge commit was written with `git commit-tree`
because a running instance of the application held one file of the demonstration run open; its tree is
exactly the feature branch's tree. One defect found in the first candidate's clean installation was
fixed on `master` (`bfd7b35`): without a path-gain cache, an experiment opened from a workspace run
showed "not simulated" instead of that run's results.

Candidate built from `bfd7b35` (`scripts/make_distribution.py`, 16.8 MB, 464 files, SHA-256 in its
`.sha256` file), extracted into a new folder and installed with `1 - Install.cmd` on the development PC
(not the target laptop):

| Check | Result |
|---|---|
| Clean installation | 222 s (warm uv cache), 0 FAIL; `package itur: 0.4.0` PASS; 433 of 433 files match `SHA256SUMS.txt`; one WARN: port 8501 used by another instance |
| Unit tests in the package (`UV_OFFLINE=1`) | 529 passed, 1 skipped (git checkout test outside a checkout) |
| App tests in the package | 59 passed, 1 skipped (instant radio recomputation needs the demonstration traces in the path-gain cache; a fresh installation has none) |
| Engine tests in the package | first two runs 6 passed, 1 failed: the worker of `test_ground_reflection_matches_fresnel_and_shows_brewster_dip` crashed 8 times in a row (exit code 0xC0000005, about 1.4 s each), so the test gave up; the same test then passed in 5 of 6 separate runs (3 of them from an empty kernel cache) and the full suite passed (7 passed). This is the intermittent Windows first-compilation crash of `docs/architecture.md`; no engine code changed in this integration |
| Opens into the workspace | yes, Arabic by default, on the demonstration experiment with the saved run's results (coverage 100.0 % at 3.5 GHz); English switch complete |
| Every page, both languages | 9 pages × 2 languages load without an error |
| Report export | the workspace's Export report produces the download |

The previous candidate (`dist/baghdad-network-simulator-delivery-candidate-8e5b5b7.zip`) and the
v1.0.0-rc.1 archives stay in `dist/` as the fallback. Not claimed: target-laptop acceptance
(`docs/laptop-acceptance.md`), scientific validation (final-scene convergence and MATLAB comparison).
