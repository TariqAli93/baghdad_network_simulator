# Assumptions, provisional values and open decisions

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

## 5. Statements in the project description still to be verified (Phase 1)

These are time-sensitive and were **not** checked in Phase 0. They must be confirmed against
primary sources before they appear in any report generated by this project.

| Statement | Reference given | What to check |
|---|---|---|
| Zain Iraq launched the first commercial 5G service in Iraq in 2026 | [10] MEA Tech Watch, Aug 2026 | Operator or regulator announcement; band used |
| 3GPP Release 21 timeline (March 2027 to end 2028, freeze March 2029) | [4] RAN#112, June 2026 | 3GPP meeting report |
| 400 MHz is the widest 6G carrier agreed by 3GPP in June 2026 | Stage 3 text | 3GPP meeting report |
| WRC-27 agenda item 1.7 bands: 4.4-4.8, 7.125-8.4, 14.8-15.35 GHz; Region 1 share 7.75-8.4 GHz | [5] Resolution 256 (WRC-23) | ITU Resolution text, including which sub-bands apply to Region 1 |
| 1.8 GHz (Band 3) is used by Iraqi operators | Table 1 | Operator or regulator data |

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

## 7. Deviations from the master brief

| Brief | What was done | Why |
|---|---|---|
| Target laptop runs the benchmark | Benchmarked on a development PC (i5-14400F, 32 GB) as a proxy, CPU only, with a 10 GB memory cap | The laptop was not available; decided with the user. The time part of the gate is decided on the laptop |
| MATLAB primary if licensed | Sionna RT is the single engine; MATLAB only cross-checks | MATLAB is not on the development PC; supervisor approved Sionna RT |
| `requirements.lock` | `uv.lock` is the lock; `requirements.lock` is exported from it | `uv` manages the environment |
| Parquet for numerical results | `.npz` + JSON in Phase 0 | Storage layer comes later |
| Project structure | See `docs/architecture.md`, section 6 | |
