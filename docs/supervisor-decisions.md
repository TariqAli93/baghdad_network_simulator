# Decisions for the supervisor

Updated 2026-11-26 (Phases 3-4; evidence added in Phases 5-10). Related questions are merged so that there are **four
decisions needed before final experiments**, three before conclusions, and a short list of
optional refinements. Nothing here is assumed approved. The software runs in development
mode on proposed values meanwhile; research runs refuse unapproved values.

| ID | Decision | Needed before | Blocks development? |
|---|---|---|---|
| A1 | Study district | Final experiments | No |
| A2 | Building data: missing footprints; heights (source, priority, storey height, observations) | Final experiments | No |
| A3 | Radio-system parameters: approve the proposal | Final experiments | No |
| A4 | Base-station sites: antenna height and candidate rule | Final experiments (site planning) | No |
| B1 | Validation scope and what counts as agreement | Scientific conclusions | No |
| B2 | Accepting the engine's limitations | Scientific conclusions | No |
| B3 | Data-rate reporting | Scientific conclusions | No |
| C1-C6 | Optional refinements (C6: GPU backend for research runs) | — | No |

---

## A. Required before final research experiments

### A1. Study district

**Question.** Which ~1 km² of Baghdad does the thesis study?

**Options.** Tahrir Square / Bab Al-Sharqi (currently the provisional development area),
Old Rusafa, Palestine Street, or a district the student can survey.

**Recommendation.** Keep Tahrir Square / Bab Al-Sharqi **if the student can observe the tall
buildings there** (A2); otherwise choose the district where that is possible.

**Evidence.** In the provisional area (`docs/study-area-evaluation.md`): 1.0 km² receiver
area, 899 OSM buildings in it, known heights from 1 m to 55 m, and 4 buildings with known
heights tall enough for sites. Weaknesses: 98.8 % of buildings have no height, and **about a
third of the built area is missing from OSM** (577 footprints, mostly in the south-east,
found in another dataset). No district surveyed in Phase 1 has better height data.

**Impact.** One entry in `configs/study_area.yaml`; no code changes.

### A2. Building data: missing footprints and heights

**Question.** How are the missing buildings added, and where do the heights come from, in
what priority, with what storey height?

**Missing footprints.** About a third of the built area of the provisional area is not in
OSM. Options: add the missing footprints from a second source with provenance (3D-GloBFP
footprints, CC BY 4.0, already downloaded; or Overture's Microsoft-derived footprints, ODbL),
map them in OSM with JOSM, or choose a district OSM covers completely.
**Recommendation:** add them from 3D-GloBFP's footprints (footprints only, not its heights),
marked with their source, if this district is kept.

**Options.**

| Option | Gives | Weakness |
|---|---|---|
| a. Field observation of selected buildings | Observed heights where it matters most | Student time |
| b. GlobalBuildingAtlas (needs a 378 MB download) | A height for every building (median 6.3 m here) | Turns the 55 m tower into 5.4 m; non-commercial licence |
| c. 3D-GloBFP | Evaluated and **rejected** for this area | Heights 26 m too high on average where tags exist; block footprints (`docs/building-height-data.md`, §9) |
| d. Assumed distributions only | A range of results | No single answer per band |

**Recommendation.** **a + b + d together**: observe every building the worklist names
(tall buildings, candidate rooftops, conflicts, buildings near sites; about 250 with
illustrative settings, `scripts/height_worklist.py`), use GlobalBuildingAtlas for the
remaining ordinary buildings if its download is approved, and report the spread over height
models as the uncertainty. Priority as configured: observation > OSM height tag > OSM storeys
> dataset > approved model > placeholder. Agree the storey height (3 m now).

**Evidence.** On identical sites, changing only the assumed heights moved line-of-sight
coverage from 86 % to 67 % and the sites needed from 2 to "not reached" (Phase 2). The two
per-building datasets disagree with each other by a factor of three and both get the tower
wrong.

**Impact.** All of it is implemented; approval means changing `approved` flags and supplying
the observation file.

**Update (Phase 5).** GlobalBuildingAtlas was downloaded and evaluated
(`docs/building-height-data.md` §12): plausible for low-rise buildings, capped near 21 m (the
55 m tower gets 5.4 m), licence non-commercial. It is now a reader and a dataset variant
(`osm+gba`), **not** a recommended source. Two questions follow:
- *GBA as a low-rise sensitivity case?* Needs a yes to its CC BY-NC 4.0 licence.
- *Missing footprints.* Recovering the 577 footprints OSM lacks needs a footprint download:
  the GBA ODbL polygon tile (2.09 GB) or Microsoft footprints directly. Approve one, or accept
  the incompleteness and choose a district with complete OSM footprints (A1).
- *Licence handling now in place.* GBA per-building values are kept out of the repository
  (git-ignored since Phase 7); only aggregate evaluation results are committed. They were
  committed once, in `e0d8a8e` (Phase 5-6); history was not rewritten. If the licence is
  judged incompatible with the project's use, that commit's GBA files need a decision too.

### A3. Radio-system parameters

**Question.** Approve, change or reject the proposal in `docs/radio-parameters.md`.

**Proposal in one line.** For every band: 46 dBm conducted per sector carrier, 3GPP TR 38.901
sector element (8 dBi, traced), 3 sectors, 10° downtilt, isotropic user antenna, 9 dB noise
figure, noise at 290 K, coverage when SINR ≥ −10 dB on 95 % of outdoor cells, reuse 1,
full load, clear sky. Each value has a primary source and table number.

**Recommendation.** Approve as proposed, for the controlled experiment.

**Evidence.** These are the common values of ITU-R M.2412, M.2292 and 3GPP TR 38.914,
TR 36.942 and TR 38.921 (`docs/radio-parameters.md`). The noise-referenced threshold keeps
the criterion physically equal across bandwidths.

**Points that need an explicit yes or no.**
- Same total power in every band (power per MHz falls with bandwidth), rather than the same
  power per MHz.
- No antenna-array gain in any band (the controlled experiment; arrays only in the
  discussion, `docs/methodology.md`).

**Impact.** Changing `status` to `approved` in `configs/radio_system.yaml`. No re-tracing is
needed for power, noise, threshold, target or load; antenna pattern, sectors and downtilt
are traced, so changing them re-traces.

> **Invalid for research interpretation (2026-11-27).** These numbers come from runs that put sites or candidates on two monuments (Freedom Monument, Faeq Hassan mural); see `configs/invalidated_runs.yaml`. They are kept as a historical record of how the method behaves, not as evidence.

**New evidence (Phase 6).** In the four-site development run every band is
interference-limited at full load (median SINR about 4 dB) yet coverage at SINR ≥ −10 dB stays
at 99.6-100 %: the threshold does not separate one site from four, so the SINR greedy stops
after one site in four of five bands. If the study is to find the site *count* per band,
either a stricter coverage criterion (for example a rate or SINR at the cell edge) or a load
below 1.0 must be chosen, and the choice must be the same for all bands. Both are
re-evaluated from the cache without tracing (Site planning page).

> **Invalid for research interpretation (2026-11-27).** These numbers come from runs that put sites or candidates on two monuments (Freedom Monument, Faeq Hassan mural); see `configs/invalidated_runs.yaml`. They are kept as a historical record of how the method behaves, not as evidence.

**Sensitivity analysis (Phase 7, cached maps, four development sites).** Thresholds −10 to
+6 dB × loads 1.0 / 0.5 / 0.2 (only −10 dB and loads 1.0, 0.5 are sourced; the rest is a
sweep). At full load and 0 dB, four sites cover *less* than one (1.8 GHz: 82 % vs 100 %);
the greedy then keeps one site. At 28 GHz more sites raise coverage at thresholds up to 0 dB.
With 20 rooftop candidates the greedy needs 1/1/1/1/2 sites (1.8/3.5/8/15/28 GHz) at the
candidate values, 1/1/1/2/3 at 0 dB and full load (28 GHz stalls at 91 %), 1/1/2/2/3 at
+3 dB and half load. The required site count is therefore set by the threshold and load
more than by anything else: they must be chosen on their own merits, before results are
known, and kept equal for all bands (`outputs/runs/development/*/sensitivity.md`).

### A4. Base-station sites

**Question.** How high is the antenna above the roof, and which roofs are candidates?

**Recommendation.** One mast height for all sites (3 m used in development, no source
found), candidates only on buildings with observed or storey-based heights, a minimum height
and spacing chosen so that the district has 20-40 candidates.

**Evidence.** A site on a building of unknown height has an unknown antenna height. No
standard gives a mast height above a roof; ITU-R M.2412 and 3GPP use 25 m total heights on
flat layouts.

**Impact.** Arguments of the candidate generator; changing them re-traces only new positions.

**New evidence (Phase 5).** With the antenna 3 m above the centre of a 29 m-wide roof, the
roof's own edge shadows most of the ground within 250 m; at 28 GHz that left 32 % of the
cells within 250 m uncovered, 37 dB below free space + pattern (`docs/validation.md` §6).
The rule therefore needs, besides the mast height, **where on the roof** the antennas stand:
at the roof edge facing each sector (usual practice, and what the 3GPP layouts imply by
having no host building) or at the centre. The candidate generator currently uses an
interior point; an edge placement is a small change once decided.

---

## B. Required before scientific conclusions

### B1. Validation scope and agreement

**Question.** What is compared with 3GPP TR 38.901, and what difference is acceptable?

**Recommendation.** Compare (i) dedicated validation sites at exactly 25 m (UMa) and 10 m
(UMi) and (ii) the real rooftop sites, flagged as outside the formulas' height range; report
RMSE and path-loss exponents beside published measured exponents (1.8-2.3 line of sight,
2.6-2.7 without, near 7-17 GHz). Do not set "within a few dB" as a pass criterion.

**Evidence.** Published comparisons of ray tracers with measurements show errors of 8-21 dB
(`docs/related-studies.md`, R7, R8).

**Done (Phase 7).** (i) Controlled comparison with TR 38.901 UMa/UMi at exactly 25 m and
10 m, LOS/NLOS from a line-of-sight trace, RMSE and fitted exponents
(`docs/validation.md` §8, `outputs/validation/`). (ii) The MATLAB package is prepared
(`validation/matlab/`) but not executed. Still needed: the criterion for "agreement" with
MATLAB (suggestion: median |difference| in LOS cells within the profile's convergence floor,
reported with RMSE, not as pass/fail).

### B2. Accepting the engine's limitations

**Question.** Are these acceptable as documented limitations? Diffraction is first-order and
never follows a reflection; multipath powers are summed without phase; buildings are opaque.

**Recommendation.** Accept and document, and spend two or three MATLAB cross-check cases in
Phase 7 on reflection-then-diffraction streets to quantify the first limitation.

### B3. Data-rate reporting

**Question.** Shannon capacity only, or also a practical mapping?

**Recommendation.** Shannon as in the project description, plus the 3GPP truncated mapping
(factor 0.6, SINR −10 to 30 dB; TR 38.921 Table 4.2.7-1) beside it, since most related
studies use such a form.

---

## C. Optional methodological refinements

| ID | Refinement | Recommendation | Cost |
|---|---|---|---|
| C1 | (moved to A2: missing footprints are required, not optional) | — | — |
| C2 | Rain sensitivity case (18.6 mm/h, previous ITU map edition) | Report once, as sensitivity | None; implemented |
| C3 | Same power per MHz instead of same total power | One sensitivity run | None; no re-tracing |
| C4 | 50 % network load | One sensitivity run | None; no re-tracing |
| C5 | Deployment illustration with array gain per band | Discussion only, by link-budget arithmetic | None |

---

### C6. GPU backend for research runs

**Question.** May final runs use the GPU backend on the development PC?

**Recommendation.** No for the thesis results; yes for exploration. The GPU agrees with the
CPU within 0.03 dB (median) and 0.45 dB (95th percentile) of path gain, with no change in
coverage class and 5th-percentile rates within 1.2 % (`docs/validation.md` §7), and is
13-16× faster. But the laptop has no NVIDIA GPU, and the Phase 0 gate and all validation
are on the CPU path. Research mode therefore refuses the GPU until this is approved
(`configs/simulation.yaml`, `backends.gpu.status`).

## D. Technical decisions taken without the supervisor

Recorded so they are not asked again; each can be reopened.

| Item | Decision | Basis |
|---|---|---|
| Engine | Sionna RT 2.2.0 on CPU; MATLAB only for cross-checks | Phase 0; supervisor approved the engine |
| Wedge-table workaround | 1,048,576 slots instead of 10,000 | Phase 0, E4: default loses > 1 dB |
| Worker isolation | Results accepted only from cleanly exiting workers; retries | Phase 0 instability measurements |
| Cache | Path gain cached per job; key includes scene hash, frequency, position, antenna, grid, mechanisms, rays, seeds, engine versions and settings; radio parameters excluded | `docs/architecture.md` |
| Profiles | Preview 25 m, standard 10 m at 1e8 rays, research 5 m at 1e9 rays | `docs/convergence.md` |
| Five scenarios | Unchanged | Project description, Table 1 |
| Corrections to the project description | Kept beside the PDF | `docs/project-description-corrections.md` |
| Fixture vs provisional area | Phase 0 snapshot frozen; v2 snapshot adds 8 multipolygon buildings | `docs/study-area-evaluation.md` |
| Site wording | "Site count found by the greedy algorithm", never "minimum" | No optimality proof |
