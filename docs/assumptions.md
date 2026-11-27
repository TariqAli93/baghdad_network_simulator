# Assumptions, provisional values and open decisions

> **Since Phase 2** the open decisions are consolidated in `docs/supervisor-decisions.md`
> (which replaces section 6 below), corrections to the project description are in
> `docs/project-description-corrections.md`, building heights in
> `docs/building-height-data.md`, and rain and gas losses in `docs/atmospheric-losses.md`.
> The configurable assumptions now live in `configs/` (`study_area.yaml`,
> `height_models.yaml`, `radio_system.yaml`, `atmosphere.yaml`), each marked approved or not.
> Sections 1-4 below remain the record of what Phase 0 assumed.
>
> **Since 2026-11-26/27** the supervisor's approvals (as reported by the project owner; no
> written reference) settle most open points of sections 3, 4 and 6; section 9 lists the
> approved configuration and what is still unspecified. Sections 3 and 6 are kept as history.

Every scientific assumption of the project is recorded here with its source and status.

- **Approved**: taken from the project description or decided with the supervisor.
- **Provisional**: needed to run the Phase 0 proof of concept; *not approved*; must not be
  used for thesis results until the supervisor agrees.
- **Unverified**: stated in the project description but not yet checked against a primary
  source (Phase 1).

## 1. Taken from the project description (approved baseline)

| Item | Value | Source |
|---|---|---|
| Study area | ~1 km² urban district of Baghdad with varied building heights | Section 3, Stage 2 |
| Scenarios | 1.8 GHz / 20 MHz, 3.5 GHz / 100 MHz, 28 GHz / 400 MHz, 8 GHz / 400 MHz, 15 GHz / 400 MHz | Table 1 (`configs/scenarios.yaml`) |
| Controlled comparison | Only band, bandwidth and number of sites change; map, transmit power, antenna heights and receiver grid stay fixed | Stage 3 |
| Receiver height | 1.5 m above street level | Stage 6 |
| Building material | Concrete | Stage 4 |
| Propagation mechanisms | Line of sight, up to two reflections, diffraction | Stage 4 |
| Extra losses | Rain and atmospheric gases for the higher bands | Stage 4 |
| Data rate | Shannon, `C = B log2(1 + SINR)`, reported at the 5th percentile; an upper bound | Section 6 |
| Site selection | Greedy, rooftop candidates on tall buildings; target agreed with the supervisor | Stage 8 |
| Validation | Against 3GPP TR 38.901 UMa and UMi, RMSE in dB | Stage 7 |
| 6G scenarios | **Candidate** research assumptions, not finalized 6G specifications | Section 8 |
| 3.5 GHz for Iraq | **Assumed** until operators publish allocations | Section 8 |

## 2. Fixed by the choice of engine (Sionna RT 2.2.0) — to be stated in the thesis

| Item | What the engine does | Status |
|---|---|---|
| Engine | Sionna RT instead of MATLAB SBR | Approved by supervisor (reported by the student, 2026-11-26) |
| Multipath combining | Power sum without phase, averaged over each receiver cell | Engine property |
| Diffraction | First-order, site -> wedge -> receiver, not combined with reflections | Engine limitation |
| Through-wall transmission | Off: buildings are opaque | Project choice, matches the MATLAB method |
| Diffuse scattering | Off | Project choice, matches the MATLAB method |
| Concrete | ITU-R P.2040-4: relative permittivity 5.24, conductivity 0.0462 f^0.7822 S/m (f in GHz) | Engine model, valid 1-100 GHz |
| Ground | Concrete, like the buildings (ITU ground types are undefined above 10 GHz) | Project choice, same as MATLAB's default terrain |
| Wedge table | 1,048,576 slots instead of Sionna's default 10,000 | Project change; see `docs/benchmarks.md`, E4 |
| Receiver antenna | Isotropic | Engine property of radio maps |
| Rain and gas loss | Not in the engine; to be added after tracing from ITU-R P.838 and P.676 | Planned for Phase 4 |

## 3. Provisional values used in Phase 0 only (not approved)

Phase 0 reports **path gain** only, so no transmit power, antenna gain, noise figure or
coverage threshold was needed, and none was invented.

| Item | Provisional value | Where | Why it was needed |
|---|---|---|---|
| Height of an untagged building | 9 m | `SceneSettings.default_height_m` | 97 % of the buildings in the test box have no height in OpenStreetMap |
| Storey height when only `building:levels` is tagged | 3 m per level | `SceneSettings.storey_height_m` | Convert levels to metres |
| Plausible height limit | 250 m | `SceneSettings.max_plausible_height_m` | Reject obviously wrong tags |
| Antenna above the roof | 3 m | `MAST_HEIGHT_M` in the scripts | A site position is needed to trace anything |
| Site choice | Tallest building within 250 m of the box centre | `rooftop_site` | Same |
| Wall thickness (reflection only) | 0.2 m | `SceneSettings.wall_thickness_m` | Parameter of the ITU slab formula |
| Ground thickness | 1 m | `SceneSettings.ground_thickness_m` | Thick enough to behave as solid ground |
| Footprint simplification | 0.3 m; pieces under 4 m² dropped | `SceneSettings` | Mesh robustness |
| Transmit antenna | Isotropic, vertical polarisation | `open_scene` | Simplest reference antenna |
| Receiver cells | 5 m (block) and 10 m (full box) | scripts | Benchmarking |
| Ray count | 10^8 per site | scripts | Chosen from E5 |
| Tolerances | 0.25 dB worst cell and 0.05 dB RMS against closed forms; 2 dB for diffraction checks | `TOL` in `poc_validate.py` | Pass/fail limits for the engine checks |
| Proof-of-concept area | Tahrir Square / Bab Al-Sharqi, centre 33.3280 N, 44.4085 E | `build_poc_scene.py` | Best compromise in the OSM survey; **not** the chosen study district |

## 4. Building data (the main data risk)

- Source: OpenStreetMap via the Overpass API, snapshot of 2026-11-25 23:55 UTC, stored with
  its SHA-256 in `data/raw/osm/` (ODbL licence). 1,220 building outlines in the 1.3 km box;
  8 buildings mapped as multipolygon relations are **not yet read** (to fix in Phase 2).
- After merging, the box has 453 building solids: 10 with a `height` tag, 4 with
  `building:levels`, **439 with the 9 m placeholder**.
- Survey of seven central districts (2026-11-25): in every district with dense footprints,
  fewer than 4 % of buildings carry a height or levels tag. No dense district is usable
  without adding heights.
- Consequences: (1) every Baghdad number produced in Phase 0 demonstrates the method only;
  (2) Phase 2 must obtain heights, either by field observation entered with JOSM as the
  project description foresees, or from a modelled dataset whose error must then be stated:
  3D-GloBFP (CC BY 4.0, reported RMSE 1.9-14.6 m) or GlobalBuildingAtlas (CC BY-NC 4.0,
  reported RMSE about 5.9 m in Asia). Microsoft's footprints have no heights for Iraq and
  Google Open Buildings 2.5D does not cover Iraq.
- Known bad data to guard against: near Jadriya 82 outlines are each tagged `height=170`, and
  some outlines carry contradicting `height` and `building:levels`. The pipeline warns about
  contradictions and ignores implausible values instead of extruding them.

## 5. Statements in the project description, checked in Phase 1 (2026-11-26)

Sources, clauses and the exact corrected wording are in `docs/references.md`, section 9.

| Statement | Result |
|---|---|
| Zain Iraq launched the first commercial 5G service in Iraq in 2026 | **Not supported.** The cited article exists but is uncorroborated; the operator's own investor material lists Iraq as 4G, and the regulator is reported as planning a 5G auction for 2027. As of November 2026 no commercial 5G launch in Iraq could be confirmed |
| 3GPP Release 21 timeline (March 2027 to end 2028, freeze March 2029) | **Confirmed.** Decided in the joint TSG#112 session on 10 June 2026 (cite RP-260868, not "RAN#112"). Stage 3 freezes in December 2028; March 2029 is the ASN.1/OpenAPI freeze |
| 400 MHz is the widest 6G carrier agreed by 3GPP in June 2026 | **Partly correct.** 400 MHz is the agreed maximum carrier for the 7 GHz range (March 2026) and the evaluation bandwidth at 7 and 15 GHz in TR 38.914. It is not "the widest", and no carrier maximum exists yet for 15 GHz |
| WRC-27 agenda item 1.7 bands; Region 1 share 7.75-8.4 GHz | **Partly correct.** Region 1: 7.125-7.25 GHz and 7.75-8.4 GHz. 4.4-4.8 GHz applies to Regions 1 and 3 only. 14.8-15.35 GHz applies to all regions |
| CEPT document PTA(23)047 | **Mis-attributed.** It is an industry contribution to a CEPT group, not a CEPT position |
| 5th-percentile user is the ITU definition of user experienced data rate | **Confirmed**, in Report ITU-R M.2410-0 §4.3 (add this report to the reference list) |
| 1.8 GHz (Band 3) is used by Iraqi operators | **Confirmed** by the regulator. The 20 MHz carrier width is not documented anywhere and stays an assumption |
| 3.5 GHz, 100 MHz assumed for Iraq | **Supported as an assumption.** The regulator's plan names 3.4-3.8 GHz with 100 MHz blocks; nothing is assigned yet |

Still open after Phase 1:

- The rain rate for Baghdad (ITU-R P.837-8 map value) was not found in any published source.
- No per-carrier bandwidth has been agreed for 6G around 15 GHz.
- Iraq's own position on WRC-27 agenda item 1.7 was not found.
- The ITU report with the 6G technical requirements is due for approval on 1 December 2026.
- The two newest Iraqi 5G items (25 November 2026) rest on single press sources.

## 6. Decisions needed from the supervisor before Phase 3

1. **Study district and the source of building heights** (section 4).
2. **Transmit power and antenna.** Identical isotropic antennas at all bands build in about
   24 dB more free-space loss at 28 GHz than at 1.8 GHz. Real higher-band systems recover
   part of it with array gain. The comparison needs a stated rule: equal antenna gain, or
   per-band gains with sources.
3. **Antenna height above the roof**, and the rule for choosing candidate rooftops.
4. **Coverage threshold** (which received-power definition: total carrier power or per
   resource element) and the **coverage target** (90 / 95 / 99 % are examples only).
5. **Receiver noise figure**, and the **interference assumption** (full reuse and full load
   is the usual worst case).
6. **Rain rate and atmospheric conditions** for Baghdad (ITU-R P.837 / P.676 inputs).
7. **Reflection depth**: the description says two. E4 measured how much three and five add
   on the test block; confirm two.
8. **Acceptance tolerances** in section 3, and the **time budget** for a full study on the
   laptop.
9. Whether the **diffraction limitation** (section 2) is acceptable as documented, or
   whether MATLAB cross-checks should target it specifically in Phase 7.

Added by the Phase 1 review (details in `docs/references.md` and `docs/related-studies.md`):

10. **Background section of the thesis:** replace the "first commercial 5G launch" statement
    (section 5) and apply the other corrections listed in `docs/references.md`, section 9.
11. **4G frequency:** keep the nominal 1.8 GHz or use the Band 3 downlink centre, 1842.5 MHz
    (0.2 dB difference in free-space loss).
12. **Rate model:** the description uses pure Shannon capacity. Most related studies apply a
    loss factor or a cap (for example 3GPP TR 36.942: factor 0.6, cap 4.4 bit/s/Hz). Decide
    whether to report such a variant beside the Shannon value.
13. **Rain rate for Baghdad:** to be read from the ITU-R P.837-8 digital maps or supplied.
    Gas loss is negligible at all five bands (at most about 0.15 dB over the study area).
14. **Validation scope:** the 3GPP UMa and UMi formulas are defined for base stations at 25 m
    and 10 m. Decide how to compare rooftop sites of other heights (report as outside the
    stated range, or add validation sites at those heights).
15. **What counts as agreement:** published comparisons of ray tracers with street
    measurements report errors of about 8-12 dB, so a ray tracer and a statistical model
    should not be expected to agree within a few dB.

## 7. Deviations from the master brief

| Brief | What was done | Why |
|---|---|---|
| Target laptop runs the benchmark | Benchmarked on a development PC (i5-14400F, 32 GB) as a proxy, CPU only, with a 10 GB memory cap | The laptop was not available; decided with the user. The time part of the gate is decided on the laptop |
| MATLAB primary if licensed | Sionna RT is the single engine; MATLAB only cross-checks | MATLAB is not on the development PC; supervisor approved Sionna RT |
| `requirements.lock` | `uv.lock` is the lock; `requirements.lock` is exported from it | `uv` manages the environment |
| Parquet for numerical results | `.npz` + JSON in Phase 0 | Storage layer comes later |
| Project structure | See `docs/architecture.md`, section 7 | |

## 8. Multi-site assumptions (Phase 6, provisional)

Development values; part of decision A3 (`docs/supervisor-decisions.md`).

| Assumption | Value used | Status |
|---|---|---|
| Carrier sharing | every sector of every site on one carrier (reuse 1) | candidate (`frequency_reuse`) |
| Interference activity (load of non-serving sectors) | 1.0, full load | candidate (`interference_activity`) |
| Co-located sectors | interfere like any other sector | modelling choice, stated in every summary |
| Serving rule | strongest received sector after pattern and gas loss | modelling choice (no handover margin) |
| Scheduling and load sharing | none: Shannon bound for one user with the whole carrier | modelling choice; rates are upper bounds, more sites cannot raise them by sharing load |
| Candidate sites (development run) | the four receiver-area roofs with observed height ≥ 10 m, ≥ 100 m apart, antenna at an interior roof point, 3 m mast | development; A4 open (roof-edge placement, see `docs/validation.md` §6) |

## 9. Approved research baseline (reported 2026-11-26 and 2026-11-27, final)

Values live in the configuration files (single source of truth); this table says where, and
what is still open. Reconciled record: `docs/approval-record.md`.

| Assumption | Approved | File | Note |
|---|---|---|---|
| Study district | Tahrir Sq / Bab Al-Sharqi, 33.3280 N 44.4085 E, 1000 × 1000 m, 150 m margin | `study_area.yaml` | research results need the field observations |
| Footprints | OSM + missing footprints from 3D-GloBFP (footprints only) | `study_area.yaml` | footprint and height provenance recorded separately |
| Heights | observation > OSM height > OSM storeys × 3.0 m > authorised dataset (none) > model > placeholder; for simulation experiments the Synthetic Urban Model fills every missing height (seed 42, low/baseline/high) | `study_area.yaml`, `height_models.yaml` | synthetic heights are modelling assumptions (`docs/synthetic-urban-model.md`); 3D-GloBFP heights and GlobalBuildingAtlas not height sources |
| Observations | P0-P1 measured or documented (4); P2 measured or documented preferred, storey-based fallback (34); S storey counts (43); P3 via height sensitivity | `study_area.yaml` | 190 before 2026-11-27 (kept in `history`); storey counts stay *estimated* |
| Radio system | 46 dBm conducted per sector carrier; TR 38.901 element traced (8 dBi peak, 65°), added gain 0; 3 sectors; 10° downtilt; no array gain; isotropic rx at 1.5 m; NF 9 dB; 290 K | `radio_system.yaml` | gain double counting refused on loading |
| Coverage | SINR ≥ −10 dB on 95 % of outdoor cells | `radio_system.yaml` | |
| Interference | reuse 1, load 1.0, co-located sectors interfere, strongest sector serves, no scheduler | `radio_system.yaml` | |
| Atmosphere | clear sky (gas, no rain) | `atmosphere.yaml` | rain 18.6 mm/h only as a sensitivity case |
| Rates | Shannon (all bands) + LTE TR 36.942 (4G), NR TR 38.921 (5G), NR-based approximation (candidate 6G) | `radio_system.yaml` | `docs/rate-mapping-verification.md` |
| Site rule | 3 m mast; roof edge facing each sector, 1 m inset; candidates with observed or storey-based heights, roof ≥ 12 m, ≥ 100 m², ≥ 50 m apart, 20-40; monuments never candidates; SINR greedy | `site_rule.yaml`, `radio_system.yaml` | thresholds may be refined after the survey (documented, geometric) |
| Sector bearings | compass 0/120/240° (0 = north, clockwise) = ray-tracer yaw 90/330/210° | `radio_system.yaml` | runs before 2026-11-27 used yaw 0/120/240° (compass 90/330/210°), recorded in their manifests |
| Profiles, backend | standard 10 m / 1e9 (research baseline), preview 25 m / 1e8, 5 m disabled; CPU for research-baseline runs, GPU and auto for development and custom experiments | `simulation.yaml` | standard to be re-evaluated on the final scene |
| Validation | TR 38.901 UMa/UMi kept; MATLAB external; median \|Δ\| in LOS cells ≤ 2.0 dB, RMSE and NLOS separately; 2-3 reflection-then-diffraction cases | `approvals.yaml` | MATLAB not run yet |

These values are the research baseline (`configs/research_baseline.yaml`). A run with other values
is a custom or sensitivity experiment and records the values it used; no approval is needed.


## 10. Simulation workspace: custom carriers and placement (2026-11-27, custom experiments only)

Decisions recorded by the project owner on 2026-11-27 (`docs/simulation-workspace.md`): the workspace
is the landing page; manual placement on a roof that satisfies the site rule is not by itself a
deviation from the research baseline, but is recorded as **manual placement** (never as an automatic
selection); hypothetical placements are allowed and are custom experiments. Placement is a
classification dimension of its own (`bns.analysis.classification`: automatic / manual / hypothetical).

| Assumption | Value used | Status |
|---|---|---|
| Custom carrier frequency | the intersection of every model applied at the carrier (`bns.app.carriers.supported_ranges_hz`): the scene materials as the installed Sionna RT defines them (ITU-R P.2040; concrete 1-100 GHz and 110-330 GHz, read from the engine's table), gas attenuation (ITU-R P.676 Annex 1: 1-1000 GHz) and the antenna element (3GPP TR 38.901 pattern: 0.5-100 GHz; the isotropic antenna adds no limit). With the baseline sector antenna: **1-100 GHz**. Nothing outside is extrapolated. Numerical limits: none narrower (the radio map and the rate formulas do not depend on the frequency; the ray count follows the cell size, `docs/convergence.md`, and was measured only at the five carriers) | technical limit, *provisional* |
| Gas loss at a custom carrier | **changed 2026-11-27** (authorised addition of ITU-Rpy). The five preset carriers keep their tabulated values (`docs/atmospheric-losses.md`), so the research baseline and every earlier run are unchanged. Any other carrier gets the sea-level specific attenuation of ITU-R P.676 Annex 1 (line by line) in the same reference atmosphere, computed by ITU-Rpy 0.4.0 (edition P.676-12, the edition that library implements); the value, the edition and the library version are stored in the carrier and in the run manifest. ITU-Rpy reproduces the five stored values to 0.0001 dB/km (`tests/unit/test_atmosphere.py`). Before this change an untabulated carrier between 1 and 30 GHz ran without gas loss (recorded "omitted", at most 0.19 dB/km) and one above 30 GHz was refused; runs recorded that way are read as recorded and never recomputed. Gas loss is applied after ray tracing, so the path-gain cache does not depend on it; the evaluation of a run compares the recorded carrier, including its gas value | *provisional* |
| Custom bandwidth | 0.1 MHz up to a quarter of the carrier frequency: path gain, materials and gas loss are evaluated at the centre frequency only | technical limit, *provisional* |
| Radio values and rate mapping of a custom carrier | those of its preset (e.g. NR for a variant of the 5G preset, the NR-based approximation for a candidate 6G preset), with the carrier's bandwidth for noise and rates; the mapping is per Hz and does not depend on the frequency | *provisional* |
| Classification | any carrier that differs from its preset makes the run a Custom Experiment and names the values; selecting fewer than five presets is not a deviation | rule |
