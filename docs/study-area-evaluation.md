# Provisional study area: Tahrir Square / Bab Al-Sharqi

Evaluated 2026-11-26. The area is the **provisional development area**
(`tahrir_bab_al_sharqi_v2` in `configs/study_area.yaml`); the final study district needs the
supervisor's approval (decision A1). Nothing here is a finding about Baghdad's networks.

## 1. Datasets

| Dataset | Snapshot | Role | Buildings | Note |
|---|---|---|---|---|
| `tahrir_bab_al_sharqi` | 2026-11-25 (SHA-256 a4ee708c…) | Frozen development fixture (Phase 0) | 1,186 | Its query omitted multipolygon geometry; kept unchanged so Phase 0 stays reproducible |
| `tahrir_bab_al_sharqi_v2` | 2026-11-26 09:11 UTC (SHA-256 85268384…) | Provisional study area | 1,194 | Corrected query; all 8 multipolygon buildings recovered |

Comparison (`scripts/compare_datasets.py`, report in `outputs/datasets/`):

- 8 buildings recovered from multipolygon relations, 6,041 m² of footprint, 7 of them with
  courtyards (inner rings); no relation had missing members.
- No other building changed between the two snapshots (0 footprints changed by more than 1 m²).
- Total footprint 312,231 m² → 318,272 m² (+1.9 %); built share of the receiver area
  22.65 % → 23.24 %.
- Mesh: 9,873 → 10,046 triangles, 7,149 → 7,261 diffraction wedges; no defects in either.
- 2 pairs of near-duplicate OSM footprints in both (reported, resolved by the footprint
  cleaner, which gives overlapping ground to the taller building).
- Effect on propagation: see `docs/validation.md`, section 4.

## 2. Against the criteria for a study district

| Criterion | Measured | Assessment |
|---|---|---|
| About 1 km² usable area | Receiver area 1.00 km² (1,000 m × 1,000 m) plus 150 m of surrounding buildings; 61.5 % of 10 m cells are outdoors | Met |
| Building density | 899 OSM buildings with their centre in the receiver area; median footprint 154 m² (5th-95th percentile 23-817 m²) | Met in the north, **not in the south** (below) |
| Varied heights | Known heights 1-60 m, but only 8 known in the receiver area (1, 1, 3, 9, 10, 12, 15, 55 m); external sources disagree (medians 6.3-19.9 m) | Probably met; **not measurable** with current data |
| Representative street geometry | Half of the outdoor cells lie within 57 m of a mapped building; 48 % lie more than 60 m from one | Mixed: dense blocks in the north, large open or unmapped areas in the south |
| Rooftop candidates | 4 buildings with known heights of at least 10 m, 150 m apart (55, 15, 12, 10 m) | **Insufficient** for site planning without observed heights |
| Data quality | 98.8 % of buildings without height information; OSM incomplete (below) | **Not adequate** yet |

## 3. OpenStreetMap is incomplete here

Building footprints from another source (the 3D-GloBFP dataset, `docs/building-height-data.md`
§9) that overlap no OSM building at all, inside the receiver area:

| Part of the receiver area | Footprints missing from OSM |
|---|---|
| North-west | 55 |
| North-east | 147 |
| South-west | 35 |
| South-east | 340 |
| **Total** | **577 footprints, about 124,000 m²** |

OSM maps about 232,000 m² of buildings inside the receiver area, so roughly **a third of the
built area is missing**, concentrated in the south-east, where OSM has only 43 buildings.
A scene built from OSM alone treats that ground as open, which overstates line of sight and
coverage there. This is an independent result from the height problem and applies whatever
height source is chosen.

Options (decision A2): add the missing footprints from a second source with their own
provenance (3D-GloBFP's footprints are CC BY 4.0, Overture's Microsoft-derived footprints are
ODbL), map them in OSM (JOSM), or choose a district that OSM covers completely. Not yet done.

## 4. Verdict

Suitable as a **development area** (it exercises every part of the pipeline, including
multipolygons, courtyards, overlaps and a 55 m tower). **Not yet suitable as the study
district**: about a third of its built area is missing from OSM, almost no heights are known,
and it offers too few candidate sites of known height. All three are fixable with the
measures in decisions A1 and A2; the software needs no change to switch districts (one entry
in `configs/study_area.yaml`, then `scripts/build_dataset.py --area NAME --fetch`).
