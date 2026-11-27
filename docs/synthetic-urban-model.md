# Synthetic Urban Model (study district, 2026-11-27)

The study is a **ray-tracing simulation of central Baghdad** (Tahrir Square / Bab Al-Sharqi) on
real geographic footprints. Building heights are documented for only 14 of 2,521 buildings, so
for simulation experiments every missing height is filled by a reproducible **Synthetic Urban
Model**. The model's heights are **estimated building heights**: modelling assumptions for
simulation, not measurements and not verified statistics about Baghdad. Field observations, when
they exist, replace them through the normal height priority (an observation always wins).

## What each kind of data is

| Kind | In this project | Status |
|---|---|---|
| Real geographic data | OSM footprints and coordinates (snapshot `tahrir_bab_al_sharqi_v2`, SHA-256 85268384…), footprints missing from OSM from 3D-GloBFP | real; footprints identical in every variant |
| Documented building attributes | OSM `height` (10 buildings), `building:levels` × 3.0 m (4 buildings), OSM building tags | real, as mapped; never overwritten |
| Synthetic building attributes | Heights of the other 2,507 buildings from the Synthetic Urban Model; category `placeholder`, source `model:<model>:<class>`, shown as "synthetic" | modelling assumptions |
| Simulation-derived results | Path gain, received power, SINR, rates, coverage, site counts | computed; classified per run (`bns.analysis.classification`) |
| Numerical validation | Analytical engine checks (Phase 0), TR 38.901 model-to-model comparison, CPU/GPU agreement; MATLAB cross-check prepared | partly done; scoped (`docs/validation.md` §11) |
| Real-world empirical validation | Field measurements of signal or heights | **none** |

A run on the Synthetic Urban Model is classified **Simulation Results** (research-baseline values),
**Custom Experiment** or **Sensitivity Analysis**, with dataset **Estimated Building Heights** and
**Validation Pending**. It is never a Validated Research Result, which needs complete empirical data.
"Synthetic Data Complete" (every building has a height) is not empirical validation.

## Algorithm `synthetic-urban-1` (`configs/height_models.yaml`, `bns.geospatial.heights`)

1. **Class.** From the OSM `building` tag when it names the use (house → small residential,
   residential → standard residential, apartments → apartments, commercial/office/retail/public
   uses → commercial, or large commercial from 1,500 m²; tower/skyscraper → high-rise). Otherwise
   from the footprint area: < 80 m² small residential, < 300 m² standard residential, < 1,000 m²
   commercial, < 3,000 m² apartments, larger large commercial. **High-rise only with tagged
   evidence**, never from size alone.
2. **Floors.** Triangular distribution over the class's whole-floor range (below), mode at 0.33
   of the range in the baseline scenario. Each building draws one uniform number from
   (seed, building id): order-independent, and shared by all scenarios.
3. **Neighbourhood.** Floors move 40 % towards the median floors of the buildings within 60 m
   (documented heights and first draws), staying inside the class range: no abrupt jumps.
4. **Height** = floors × 3.0 m (the configured storey height).

| Class | Floors | Height |
|---|---:|---:|
| Small residential | 1-2 | 3-6 m |
| Standard residential | 2-4 | 6-12 m |
| Commercial | 2-6 | 6-18 m |
| Apartment buildings | 3-8 | 9-24 m |
| Large commercial | 4-12 | 12-36 m |
| High-rise (tagged only) | 10-20 | 30-60 m |

These ranges are illustrative modelling assumptions given for the simulation study.

**Scenarios** (same classes, same draws, same footprints): low (mode at each class minimum),
baseline (mode 0.33), high (mode at each class maximum). Per building, low ≤ baseline ≤ high.

**Reproducibility.** Seed 42 (the default of `scripts/build_dataset.py --height-model`). The same
snapshot, configuration and seed rebuild the identical scene (checked: scene fingerprint
7522d10cef42deff for the baseline, rebuilt twice). Where footprints overlap, the building with the
taller height *before* the model keeps the shared ground, so all variants have identical
footprint geometry (checked: same geometry hash for `osm+fp_3d_globfp` and the three scenarios).

**Metadata.** Each variant's quality report and `dataset_manifest.json` record the model name,
kind, all parameters (classes, distributions, rules, version), seed, synthetic share, class
counts, remaining plain placeholders, and the scene fingerprint.

## The three variants

| Variant | Synthetic heights | Median / 90th pct / max (synthetic) | Receiver-area buildings ≥ 12 m |
|---|---|---|---:|
| `synthetic_urban_low-seed42+fp_3d_globfp` | 2,507 of 2,521 (99.4 %), 0 plain placeholders | 6.0 / 9.0 / 18.0 m | 125 |
| `synthetic_urban-seed42+fp_3d_globfp` (default) | 2,507 of 2,521 (99.4 %) | 6.0 / 12.0 / 21.0 m | 272 |
| `synthetic_urban_high-seed42+fp_3d_globfp` | 2,507 of 2,521 (99.4 %) | 9.0 / 15.0 / 27.0 m | 608 |

Classes (all scenarios): 954 small residential, 1,025 standard residential, 452 commercial,
69 apartments, 7 large commercial, 0 high-rise (no tagged evidence). The 81 buildings of the
observation worklist (P0-P1 4, P2 34, S 43) and all other placeholder buildings have synthetic
substitutes; the observation records themselves stay empty (no synthetic value is ever recorded
as an observation).

## Candidate rooftops

On a Synthetic Urban Model, roofs with synthetic heights are eligible candidates
(`sites.candidate_categories`); each candidate keeps its height category. With the approved
thresholds (12 m, 100 m², 50 m) the baseline gave 102 candidates. The spacing was refined to
125 m on geometry alone (documented in `configs/site_rule.yaml`, `adjustments`): 29 / 30 / 33
candidates in the low / baseline / high scenarios. Monuments, memorials and artworks stay
excluded. No height was changed to reach a count.

## Height sensitivity (site planning, all five bands, 2026-11-27)

`scripts/plan_sites.py` on each scenario: same footprints, same candidate rule, preview profile
(25 m cells, 1e8 rays), GPU backend, research-baseline radio values (46 dBm, SINR ≥ −10 dB on
95 % of outdoor cells, load 1.0). Classified *Custom Experiment* (preview profile, GPU backend) ·
Estimated Building Heights · Validation Pending. One seed (42), fixed before any result was seen.

| Scenario | Candidates | Run ID | Trace time |
|---|---:|---|---:|
| low | 29 | `site_plan-…-synthetic_urban_low-seed42+fp_3d_globfp-preview-29cand-gpu-20261127T011533Z` | 291 s |
| baseline | 30 | `site_plan-…-synthetic_urban-seed42+fp_3d_globfp-preview-30cand-gpu-20261127T012216Z` | 395 s |
| high | 33 | `site_plan-…-synthetic_urban_high-seed42+fp_3d_globfp-preview-33cand-gpu-20261127T012932Z` | 428 s |

Sites needed: **1 in every band and scenario** (target reached; the documented 55 m tower
`way/919688856` is chosen first everywhere). Final network (that one site), low / baseline / high:

| Band | Coverage | Median received power | Median SINR | 5th-pct SINR | Median Shannon rate | 5th-pct rate |
|---|---|---|---|---|---|---|
| 4G 1.8 GHz | 100 / 100 / 100 % | −37.7 / −37.8 / −37.9 dBm | 17.9 / 17.9 / 17.7 dB | 2.2 / 2.4 / 1.8 dB | 119 / 120 / 118 Mbit/s | 28.2 / 28.9 / 26.7 Mbit/s |
| 5G 3.5 GHz | 100 / 100 / 100 % | −43.6 / −43.6 / −43.8 dBm | 18.1 / 17.9 / 17.7 dB | 2.1 / 2.1 / 1.7 dB | 603 / 598 / 589 Mbit/s | 139.5 / 139.8 / 130.9 Mbit/s |
| 6G 8 GHz | 100 / 99.8 / 99.8 % | −50.9 / −50.8 / −51.0 dBm | 17.7 / 17.4 / 16.4 dB | 1.4 / 1.7 / 1.2 dB | 2364 / 2324 / 2187 Mbit/s | 497 / 523 / 487 Mbit/s |
| 6G 15 GHz | 99.5 / 99.3 / 99.3 % | −56.4 / −56.3 / −56.4 dBm | 15.9 / 15.9 / 14.9 dB | 1.1 / 1.1 / 0.8 dB | 2132 / 2125 / 1994 Mbit/s | 479 / 481 / 458 Mbit/s |
| 5G 28 GHz | 99.0 / 99.0 / 99.0 % | −61.8 / −61.8 / −62.0 dBm | 13.4 / 13.0 / 12.4 dB | 0.7 / −0.3 / −1.2 dB | 1810 / 1755 / 1678 Mbit/s | 448 / 382 / 326 Mbit/s |

Reading: with one 58 m antenna position over a 1 km² area, the −10 dB threshold and full load,
coverage and the site count do not depend on the synthetic heights; the heights matter in the
weak tail (5th-percentile SINR and rate fall by up to 1.9 dB and 27 % at 28 GHz from low to high
scenario) and in the higher bands' median rates (−8 % at 8 GHz, −7 % at 28 GHz). Candidate
selection is the same in all scenarios. These are simulation results on assumed heights, preview
profile and GPU: the next steps are the standard profile on the CPU (research-baseline backend)
and a stricter threshold or load as a sensitivity case.
