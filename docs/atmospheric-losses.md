# Rain and atmospheric gas losses

Investigated 2026-11-26. The ray tracer models neither, so both are added afterwards
(`bns.propagation.atmosphere`). The project description (Stage 4) asks for both "for the
higher bands".

## Decision in force

**Baseline: clear sky.** Gas attenuation is included at every band; rain is not. Rain is
available as a configurable loss for a separate sensitivity experiment
(`configs/atmosphere.yaml`). No rain rate for Baghdad is part of any baseline result until
one is approved (`docs/supervisor-decisions.md`, decision D8).

## How the loss is applied

Loss in dB = specific attenuation (dB/km) × straight-line distance from the site to the
receiver cell. Reflected and diffracted paths are slightly longer, so this is a lower bound;
within 1 km² the difference is far below the other uncertainties. It enters the link budget
as `extra_loss_db` in `bns.analysis.link_budget.received_power_dbm`.

## Gases (ITU-R P.676-13)

The Recommendation gives a calculation method and a figure, not a table. Values for the five
carriers at sea level in the reference atmosphere (1013.25 hPa, 15 °C, 7.5 g/m³ of water
vapour):

| Band | Oxygen | Water vapour | Total (dB/km) |
|---|---|---|---|
| 1.8 GHz | 0.0066 | 0.0002 | 0.0068 |
| 3.5 GHz | 0.0072 | 0.0006 | 0.0078 |
| 8 GHz | 0.0078 | 0.0036 | 0.0114 |
| 15 GHz | 0.0096 | 0.0194 | 0.0291 |
| 28 GHz | 0.0187 | 0.0831 | 0.1018 |

Provenance: computed with the line-by-line method by the open-source library ITU-Rpy 0.4.0
(which implements edition P.676-12) on 2026-11-26, and the same figures were obtained by the
Phase 1 research pass from the tables of P.676-13 Annex 1. The two are not fully independent
(the research pass checked its code against ITU-Rpy). Plausibility: the same code gives
14.8 dB/km at 60 GHz and 0.19 dB/km at 22.2 GHz, the well-known oxygen and water-vapour
peaks. Only these five frequencies are stored; any other frequency is refused rather than
interpolated.

Effect: at most 0.1 dB over 1 km at 28 GHz, less than 0.03 dB at the other bands.
**Negligible for this study, kept for completeness.** Baghdad's real atmosphere is hotter and
usually drier than the reference atmosphere; at these magnitudes the difference does not
matter.

## Rain (ITU-R P.838-3 and P.837)

**Specific attenuation** is `k · R^α` (P.838-3), implemented for 1-1000 GHz from the
Recommendation's own equations. The unit tests check the coefficients against its Table 5 at
1.5, 2, 3.5, 8, 15 and 28 GHz; all agree to the printed precision.

**The rain rate R for Baghdad** is the open question.

- The ITU's method (P.837) reads the rate exceeded for a given share of the year from
  digital maps. The edition in force is **P.837-8** (09/2025); its maps are a 361 MB download
  that has not been made, and no published value for Baghdad was found.
- The previous edition, **P.837-7**, is bundled with ITU-Rpy. Queried at 33.328° N,
  44.4085° E on 2026-11-26 it gives:

| Exceeded for | P.837-7 | P.837-6 (older still) |
|---|---|---|
| 0.1 % of the year (about 9 hours) | 4.1 mm/h | 4.1 mm/h |
| 0.01 % (about 53 minutes) | 18.6 mm/h | 20.5 mm/h |
| 0.001 % (about 5 minutes) | 55.1 mm/h | 62.7 mm/h |

These are traceable to ITU data but come from a superseded edition through a third-party
implementation. They are recorded as **candidates** in `configs/atmosphere.yaml`, marked not
approved. They are consistent with Baghdad's dry climate (about 125-150 mm of rain a year).

**What the candidates would mean** (`uv run python scripts/atmosphere_table.py`, results in
`outputs/atmosphere/loss_table.md`), gas included, vertical polarisation:

| Rain | Band | dB/km | Loss over 500 m |
|---|---|---|---|
| 18.6 mm/h | 3.5 GHz | 0.014 | 0.01 dB |
| 18.6 mm/h | 8 GHz | 0.21 | 0.10 dB |
| 18.6 mm/h | 15 GHz | 1.09 | 0.54 dB |
| 18.6 mm/h | 28 GHz | 3.06 | 1.53 dB |
| 55.1 mm/h | 15 GHz | 3.32 | 1.66 dB |
| 55.1 mm/h | 28 GHz | 8.20 | 4.10 dB |

Reading: with rain this rare and cells this small, rain costs about 1.5 dB at 28 GHz for
under an hour a year and is irrelevant below 8 GHz. It is very unlikely to change a site
count, but that is for the sensitivity experiment to show once coverage thresholds exist.

## The sensitivity experiment (prepared, not yet meaningful)

Once transmit power and the coverage threshold are decided, each rain case reduces received
power by its loss map (`attenuation_map_db`) and coverage and site counts are recomputed
from the cached path-gain maps; no new ray tracing is needed. Until then only the loss table
above can be produced.

## Not modelled

Dust and sand storms, which Iraqi studies treat as a propagation factor at millimetre-wave
bands (`docs/related-studies.md`, Q4), and fog. Both are outside the project description;
the thesis should name dust as a limitation.

## Why ITU-Rpy is not a dependency

It was used once, in a throw-away environment, to obtain the numbers above. Installed it
takes 169 MB (mostly climate maps) and pulls in `astropy`. The project stores the handful of
values it needs with their provenance instead. If the supervisor asks for conditions other
than the reference atmosphere, or for many frequencies, adding it as an optional development
tool is the simplest route.
