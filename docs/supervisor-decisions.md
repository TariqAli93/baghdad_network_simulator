# Decisions for the supervisor

One place for every open scientific decision. Last updated 2026-11-26 (Phase 2).

How to use this page: each decision has a question, the options, a recommendation with its
reason, and what it affects. **"Blocks" says what cannot be finished without it.** None of
them blocks further development: the software takes each of these as a configurable input.
They block *final research results* only.

Decisions are recorded, once made, in the file named under "Where it goes", with the date
and who decided.

| ID | Decision | Blocks |
|---|---|---|
| D1 | Study district | Final results (all phases) |
| D2 | Source of building heights | Final results (all phases) |
| D3 | Transmit power and antenna rule across bands | Received power, SINR, data rate, site counts |
| D4 | Antenna height and rooftop candidate rule | Site planning |
| D5 | Coverage threshold and coverage target | Coverage, site counts |
| D6 | Receiver noise figure | SINR, data rate |
| D7 | Interference (network load) assumption | SINR, data rate |
| D8 | Rain | Only the rain sensitivity experiment |
| D9 | Data-rate model | Reported data rates |
| D10 | Scope of the validation against 3GPP TR 38.901 | Validation chapter |
| D11 | Accepting the diffraction limitation | Methodology chapter; MATLAB cross-check scope |

---

## D1. Study district

**Question.** Which ~1 km² of Baghdad does the thesis study?

**Options.** Measured in OpenStreetMap on 2026-11-25 (`docs/benchmarks.md`):
Tahrir Square / Bab Al-Sharqi (920 buildings, heights 1-55 m present); Old Rusafa (1,380
buildings, densest, mostly low-rise); Palestine Street (551 buildings, most tagged heights);
or another district the student can survey.

**Recommendation.** Choose the district **where heights can actually be obtained** (D2): if
the student will count storeys on site, pick a district they can walk safely and
completely. On map data alone Tahrir Square / Bab Al-Sharqi is the best compromise.

**Why.** Footprints are adequate in all three; heights are missing in all three. Access for
observation is the binding constraint, not the map.

**Impact on implementation.** One entry in `configs/study_area.yaml` and one command
(`scripts/build_dataset.py --area NAME --fetch`). Nothing else changes.

**Where it goes.** `configs/study_area.yaml` (`role: study district`, `approved: true`).

## D2. Source of building heights

**Question.** Where do the heights of about a thousand buildings come from?

**Why it matters.** In the test area 98.8 % of buildings have no height information. A test
on that area with four different *assumed* height distributions, everything else identical,
changed line-of-sight availability from 86 % to 67 % and the number of sites needed at a
fixed threshold from 2 to "target not reached with the available sites"
(`outputs/runs/height_sensitivity/`). The height method decides the thesis result.

**Options.** Details and measurements in `docs/building-height-data.md`.

| Option | What it gives | Cost | Weakness |
|---|---|---|---|
| A. Field observation | Storeys counted per building, entered as a CSV or in JOSM; category "observed" | Student time on site | Storey height still assumed; large area |
| B. A modelled global dataset | A height per building, estimated from satellite data; category "estimated" | A download; licence terms | Errors of several metres per building; tall buildings underestimated |
| C. Hybrid | B for all buildings, A for the tallest buildings and all candidate sites, plus the sensitivity analysis | Moderate | More to explain |
| D. Assumed distribution only | Results as a range over height models | None | The thesis cannot state one site count per band |

**What was measured (2026-11-26).** Two free datasets give a height for every building in
the test area, but the available sources disagree by a factor of two (median 6.3 m in
GlobalBuildingAtlas, 13.2 m in the European GHSL grid), none has been validated in Iraq, and
the one tagged tower in the area (14 storeys, 55 m) appears as 5.4 m, 10.9 m and 15.0 m in
the three sources measured. Google's dataset does not cover Iraq; Microsoft's and Overture's
add no heights.

**Recommendation.** **C**: a per-building dataset for ordinary buildings, **observed heights
for every tall building and every candidate site**, the storey height (currently 3 m) agreed
explicitly, and a second height source run through the sensitivity analysis so the thesis
reports a range. The buildings that matter most are the tall ones (they host sites and cast
the long shadows); no dataset gets them right, and they are few enough to observe.

**Sub-decision.** Which dataset: GlobalBuildingAtlas (measured here; non-commercial licence,
fine for a thesis) or 3D-GloBFP (more permissive licence; needs a 205 MB download before it
can be measured).

**Impact on implementation.** All four are already supported: observations through
`--observations`, height models through `--height-model`; a dataset reader is a small
addition once the dataset is chosen. Every building keeps a record of which option its
height came from, and the quality report states the shares.

**Where it goes.** `configs/study_area.yaml` (`height_policy`), `configs/height_models.yaml`
(`approved: true` on the accepted models), `docs/building-height-data.md`.

## D3. Transmit power and antenna rule across bands

**Question.** What transmit power and antenna gain does each scenario use?

**Why it matters.** The project description says "same site and power for all bands". With
identical antennas, free-space loss alone puts 28 GHz about 24 dB behind 1.8 GHz, so the
higher bands will need many more sites almost by construction. Real higher-band systems use
larger arrays in the same physical size, recovering part of that.

**Options.**

| Option | Rule | Used by |
|---|---|---|
| A. Equal power, equal antenna gain | As in the project description | The project description; a pure propagation comparison |
| B. Equal power, equal antenna *size* | Gain grows with frequency squared (+6 dB per doubling) | Testolina 2024, Kang 2024, Aghaei 2026 (`docs/related-studies.md`, R2, R3, A2) |
| C. Per-band values from a reference configuration | For example 44 dBm at 4 GHz and 40 dBm at 28 GHz (ITU evaluation settings as used by Salazar 2021, R1); 33 dBm (R3); 40 dBm (R9) | Individual studies |

**Recommendation.** Report **A as the baseline** (it is what the approved description says
and isolates propagation) **and B as a second case** (it is what the literature does and
what equipment would do). State one transmit power for all bands, taken from a cited
reference configuration.

**Impact on implementation.** None on ray tracing: both cases reuse the same path-gain maps
and differ only in the link budget. Values go in `configs/radio_system.yaml`.

## D4. Antenna height and rooftop candidate rule

**Question.** How high above the roof is the antenna, and which roofs are candidates?

**Options.** Mast: a fixed height above each roof (the tests use 3 m as a placeholder), or a
fixed total height. Candidates: all buildings above a minimum height, with a minimum spacing
between candidates; whether buildings with placeholder heights may host a site.

**Recommendation.** A fixed mast height above the roof; candidates only on buildings whose
height is observed or estimated (not placeholder); minimum height and spacing chosen so that
the district has roughly 20-40 candidates.

**Why.** A site on a building of unknown height has an unknown antenna height, which
undermines the result more than any other single error.

**Impact.** Arguments of `bns.geospatial.sites.rooftop_candidates`; no default exists.

## D5. Coverage threshold and coverage target

**Question.** When is a receiver point "covered", and what share must be covered?

**Options for the threshold.**

| Option | Definition | Consequence |
|---|---|---|
| A. Fixed received power | The same dBm value for every band | Bandwidth plays no role in coverage; simplest; matches the description's wording |
| B. Fixed signal-to-noise ratio | Received power above noise by a margin (Testolina 2024 uses 0 dB) | Wider carriers need more power: 400 MHz needs 13 dB more than 20 MHz |
| C. Minimum data rate | A rate every covered user must reach | Closest to "service", but mixes coverage and capacity |

**Options for the target.** 90 %, 95 %, 99 % (examples from the brief, not approved values).

**Recommendation.** **B** with a stated margin, and **95 %** as the target, reporting 90 %
and 99 % as well.

**Why.** A noise-referenced threshold is the same physical condition at every bandwidth, so
the comparison between generations stays fair. If A is preferred for simplicity, say so in
the thesis and note that it favours the wide carriers.

**Impact.** One function argument each; the greedy selection reruns in seconds on cached maps.

## D6. Receiver noise figure

**Options.** 7 dB (used by Kang 2024, R3, and the default of MATLAB's `sinr`); another value
from a cited specification.

**Recommendation.** 7 dB for all bands, cited.

**Impact.** `configs/radio_system.yaml`; shifts every SINR by the same amount.

## D7. Interference assumption

**Question.** How busy are the other sites when a user is served?

**Options.** All other sites transmit at full power all the time, on the same carrier (the
worst case; `interference_activity: 1.0`); or a load factor below 1.

**Recommendation.** Full load, full frequency reuse, stated as a worst-case bound.

**Why.** It needs no further assumption and is the common reference case (R3 describes its
own interference case the same way).

## D8. Rain

**Question.** Is rain part of the results, and with which rain rate?

**Options.**

| Option | Rain rate | Status of the number |
|---|---|---|
| A. Clear sky only | none | Nothing to justify; current baseline |
| B. Sensitivity case with the previous ITU maps | 18.6 mm/h exceeded 0.01 % of the year (ITU-R P.837-7 via ITU-Rpy) | Traceable, but a superseded edition |
| C. Sensitivity case with the current ITU maps | Value to be read from ITU-R P.837-8 | Needs a 361 MB download from the ITU |
| D. Local measurements | From Iraqi meteorological data | Needs a source |

**Recommendation.** **A for all baseline results, plus B or C as a labelled sensitivity
case.** Rain at these rates costs about 1.5 dB at 28 GHz over 500 m for under an hour a
year and nothing measurable below 8 GHz (`docs/atmospheric-losses.md`).

## D9. Data-rate model

**Options.** Pure Shannon capacity (the project description); additionally an attenuated,
capped variant (3GPP TR 36.942 Annex A: factor 0.6, cap 4.4 bit/s/Hz; similar forms in R3,
R9, A1).

**Recommendation.** Shannon as the baseline, the TR 36.942 variant reported beside it.

**Why.** Shannon alone gives rates no network reaches; a cited practical variant makes the
numbers comparable with other studies at no extra simulation cost.

## D10. Scope of the validation against 3GPP TR 38.901

**Question.** The 3GPP urban formulas are defined for base stations at 25 m (macro) and 10 m
(micro). The project's rooftop sites have other heights. What is compared with what?

**Options.** A: compare the actual rooftop sites and flag every comparison outside the
stated range. B: add dedicated validation transmitters at exactly 25 m and 10 m and compare
those. C: both.

**Recommendation.** **C.** B gives a clean like-for-like check; A shows how far the real
sites deviate.

**Also needed.** An agreed expectation: published comparisons of ray tracing with
measurements report errors of roughly 8-21 dB, so agreement within a few dB should not be
set as a pass criterion.

## D11. Accepting the diffraction limitation

**Question.** In the chosen engine, diffraction in coverage maps is first-order and cannot
follow a reflection. Is that acceptable as a documented limitation?

**Options.** Accept and document; or accept and additionally target it in the MATLAB
cross-check (MATLAB allows one diffraction after reflections in coverage maps).

**Recommendation.** Accept, and include two or three such cases in the Phase 7 MATLAB
cross-check to put a number on the effect.

---

## Settled without the supervisor

These were decided from the project description or documented primary sources and are
recorded here so they are not asked again. Any of them can be reopened.

| Item | Decision | Basis |
|---|---|---|
| The five scenarios | Unchanged from the project description | Table 1 of the PDF; consistency with the bands under study is unit-tested |
| 4G frequency | Keep the nominal 1.8 GHz | The description; the Band 3 downlink centre (1842.5 MHz) differs by 0.2 dB |
| Corrections to citations and wording | As listed in `docs/project-description-corrections.md` | Primary sources in `docs/references.md` |
| Reflection depth | 2 | The description; a third to fifth reflection changed the 5th percentile by at most 1 dB in Phase 0 (to be re-checked on the study district) |
| Through-wall transmission, diffuse scattering | Off | Matches the method in the description |
| Building and ground material | Concrete, ITU-R P.2040-4 | The description; the Recommendation |
| Gas attenuation | Included at all bands | ITU-R P.676-13; negligible but applicable |
| Baseline weather | Clear sky | No approved rain rate (D8) |
| Engine settings | Wedge table enlarged; 10^8 rays for 10 m cells, 10^9 for 5 m | Measured in Phase 0 (`docs/benchmarks.md`) |
| Site-selection wording | "Site count found by the greedy algorithm", never "minimum" | The algorithm gives no proof of optimality |
| Not modelled | Dust storms, vegetation, vehicles, indoor users | Outside the description; to be named as limitations |

## Waiting on the student, not the supervisor

- **Phase 0 laptop benchmark** (`docs/benchmarks.md`, section 8). The acceptance gate for
  the target laptop is still open.
- **Reading the sources** in `docs/references.md` and `docs/related-studies.md` before
  citing them.
- **Confirming the Iraqi 5G status** with the regulator before submission.
