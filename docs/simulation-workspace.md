# Simulation workspace: audit, design and prototype (for review)

Status: **prototype for review, 2026-11-27.** The production application (`app/main.py`, ten pages) is
unchanged. The prototype is a separate entry point:

```
uv run streamlit run app/workspace.py            # Arabic by default; ?lang=en for English
```

The repository is in feature freeze since v1.0.0-rc.1. This prototype follows the project owner's
request to reorient the application around simulation. It adds no scientific model and changes no
configuration value, and nothing in the delivered application depends on it. Restructuring the
production navigation waits for the review (section 6).

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

Run: "Trace this band (n)" or "Trace all bands (n)" starts `scripts/trace_jobs.py` in its own process
(`bns.app.workspace_runs`). It only traces, through `propagation.compute` (isolated workers, retries,
cache), and reports `WORKLOAD`, `CURRENT` (band, station, sector, bearing), `PROGRESS` and `DONE`. The
results panel shows progress, the current band and sector, cached / new / remaining traces, elapsed time
and Cancel. The page stays usable while it runs. When the run ends, the workspace evaluates whatever the
design is *now*: if it changed during the run, it stays stale. Cancelling keeps every finished batch.
One batch is one band and dataset, so the band in progress is lost (unchanged behaviour of
`propagation.compute`).

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
| `src/bns/app/workspace_runs.py` | start, follow and cancel a trace run; log protocol |
| `scripts/trace_jobs.py` | traces a job file into the path-gain cache |
| `app/workspace.py` | the prototype page |
| `app/components/network_map.js`, `.css` | the map component (components v2, inline, offline) |
| `src/bns/i18n/locales/{en,ar}/workspace.yaml` | every text, both languages |
| `tests/unit/test_workspace.py`, `test_workspace_runs.py` | 39 tests (identical job keys, staleness, placement, evaluation, per-station power, greedy, classification, saved runs, log parsing) |
| `tests/app/test_workspace.py` | opt-in headless page tests (`-m app`) |

No scientific module, configuration file or production page was changed. Per-station power enters the
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

## 6. Proposed navigation after review

| New section | Built from |
|---|---|
| 1. Simulation Workspace (default) | this prototype; replaces Dashboard, Run Simulation and Coverage as the working pages |
| 2. Scenario Comparison | Comparison page (bands, runs, site plans, model-to-model, sensitivity) + the workspace comparison |
| 3. Automatic Site Planning | Planning page and `plan_sites.py` runs, with "open in workspace" |
| 4. Experiment History | saved runs and app runs (today split between Run Simulation and every run picker), with "open in workspace" |
| 5. Reports | Reports page |
| 6. Settings and Research Details | Study Area, Radio parameters, Validation, Roadmap, assumptions, provenance, the dashboard's readiness indicators |

No scientific function is removed: every current page keeps its content in one of the six sections.

## 7. Limitations and open decisions

Limitations of the prototype:

- A workspace configuration is not yet saved as a run. Proposed next step: "Save as experiment" writes
  the same manifest, summary and arrays as `run_multi_site.py`, through a shared function, so Reports and
  History read it like any run.
- Frequency and bandwidth are shown per scenario, not edited. A custom carrier would be a new scenario
  with its own rate mapping and sources (`configs/scenarios.yaml`, `docs/references.md`).
- Hypothetical stations stand on the scene's ground plane (z = 0, no terrain model). They are always a
  custom experiment and always drawn as hypothetical.
- One trace run at a time; Cancel loses the band in progress (section 3.5).
- Map interactions cannot be driven by Streamlit's AppTest; they were checked in Chrome (section 5).
  Touch input and screen-reader use of the canvas are untested. The toolbar is keyboard-operable, and the
  station list and editor give a non-map path to every station property.
- The 3D view is not built (section 2).

Decisions for the review:

- **R1** Replace the dashboard landing page with the workspace and adopt the six-section navigation
  (section 6)?
- **R2** Should a station placed by hand on a roof that *satisfies* the candidate rule count as a
  deviation (manual placement), or stay research baseline, as `run_multi_site.py --buildings` does today?
- **R3** Allow hypothetical stations in research-facing material at all, or only in custom experiments
  (current prototype: allowed, off by default, always a deviation)?
- **R4** Add "Save as experiment" (section 7, first limitation) before the restructuring?
