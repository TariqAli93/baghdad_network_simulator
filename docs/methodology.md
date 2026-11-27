# Methodology: controlled experiment and deployment interpretation

## 1. The question and why it needs a controlled comparison

The research question asks how many sites each generation needs to cover the same district
and what data rate each delivers. A fair answer must change **one thing at a time**. The
project description fixes the map, the transmit power, the antenna heights and the receiver
grid, and lets only the band, the bandwidth and the number of sites change (Stage 3).

## 2. The two layers

### Controlled experiment (primary method)

The five scenarios share one radio system (`docs/radio-parameters.md`):

- the same sites, antenna heights, receiver grid, buildings and propagation settings;
- the same conducted transmit power per carrier (46 dBm), the same sector antenna
  (3GPP TR 38.901 element, 8 dBi), the same downtilt, the same user antenna (0 dBi) and
  noise figure (9 dB);
- the same coverage criterion relative to noise (SINR ≥ −10 dB) and the same target.

Differences in the results then come from two sources only:

1. **Frequency**: free-space spreading loss grows by 20 log10(f) (about 24 dB from 1.8 to
   28 GHz), concrete reflects and diffracts differently, and diffraction into shadow is
   weaker at higher frequency.
2. **Bandwidth**: noise grows with bandwidth (13 dB more at 400 MHz than at 20 MHz), the
   same power is spread over more spectrum, and the Shannon rate grows with bandwidth.

What the controlled experiment shows is the cost of moving the same network to a higher,
wider carrier. It is the primary result of the thesis.

### Deployment interpretation (discussion)

Real systems do not use one radio system across bands. Section 4 of
`docs/radio-parameters.md` lists the per-band differences the standards assume: larger
antenna arrays at higher frequency (array gain grows with frequency at the same physical
size), different powers per MHz, user-side beamforming in millimetre-wave bands, different
noise figures. These would partly compensate the extra loss of the higher bands.

The thesis should **discuss** how such differences could change the conclusions, using the
controlled results plus simple link-budget arithmetic (for example: "an array gain of X dB
at 15 GHz would recover Y dB of the gap"), not by building a second simulator. Any
quantitative deployment case must be labelled as an illustration under stated assumptions.

## 3. Limits of common assumptions across generations

- **A carrier is not a generation.** 4G, 5G and 6G differ in waveform, numerology,
  scheduling, MIMO, beam management and core network, none of which is modelled. The
  scenarios compare *carriers* with the bandwidths the project description assigns. The
  thesis must not imply that frequency alone defines a generation, or that the 8 and 15 GHz
  results describe 6G performance (they are candidate bands; `docs/project-description-corrections.md`).
- **Common power and antennas penalise the higher bands.** With one antenna element for all
  bands, the higher carriers lose the array gain they would have in practice. The site
  counts for 15 and 28 GHz are therefore upper estimates relative to equipment designed for
  those bands.
- **Common total power penalises the wider carriers.** 400 MHz receives the same 46 dBm as
  20 MHz, so its power per MHz is 13 dB lower. A constant-power-density variant is a
  sensitivity case, not the baseline.
- **Shannon capacity is an upper bound.** It ignores overheads, practical modulation limits
  and scheduling. It ranks the scenarios consistently because it is applied identically.
- **One snapshot of a district.** No traffic, mobility, indoor users, vehicles or vegetation.
- **Propagation model limits** (`docs/architecture.md`): power sums without phase,
  first-order diffraction never combined with reflection, buildings opaque, no dust or rain
  in the baseline.

## 4. What the simulation computes, step by step

1. **Propagation (ray tracing)**: path gain from every sector to every receiver cell, for
   each band. Depends only on geometry, frequency, antenna pattern and orientation, the
   grid and the propagation settings; cached and reused.
2. **Losses not in the ray tracer**: atmospheric gas loss (and rain in sensitivity runs),
   from the straight-line distance.
3. **Received power** = transmit power (conducted; the pattern's gain is in the path gain)
   + path gain − extra losses + receiver gain.
4. **Noise** = kT0B + noise figure.
5. **SINR**: the strongest sector serves; all other sectors on the same carrier interfere,
   summed in watts and scaled by the load factor.
6. **Coverage**: share of outdoor cells meeting the criterion.
7. **Data rate**: Shannon B log2(1 + SINR); reported as the 5th-percentile and median user.
8. **Site planning** (Phase 8): greedy selection of rooftop candidates until the coverage
   target is met; reported as "the site count found by the greedy algorithm".

Steps 2-8 are cheap and are recomputed from cached path gain whenever a radio parameter
changes.

## 4a. Building heights for the simulation

The study is a ray-tracing simulation of central Baghdad on real geographic footprints (OSM,
3D-GloBFP for missing footprints). Heights are documented for 14 buildings; all others take
estimated building heights from the reproducible Synthetic Urban Model (seed 42; low, baseline
and high scenarios on identical footprints; `docs/synthetic-urban-model.md`). Results on it are
simulation results under stated height assumptions, reported with the height sensitivity; they
are not an empirical description of Baghdad and are not validated against field measurements.
Field observations, when available, replace synthetic heights through the height priority.

## 5. Run modes

- **Development** (preliminary simulations, custom experiments, sensitivity analyses): any
  valid value may be used; every output carries its classification (configuration, dataset,
  validation; `bns.analysis.classification`).
- No run is refused for scientific reasons: every technically valid simulation executes and is
  classified. Only research-baseline runs (approved values, standard profile, CPU, site rule) on
  the study district's complete data, after the final-scene convergence and a MATLAB comparison
  meeting B1, are Validated Research Results.
- *(Before 2026-11-27 development outputs carried the label "DEVELOPMENT — NOT APPROVED FOR
  RESEARCH"; those files keep it and are shown as Preliminary Simulations.)*
