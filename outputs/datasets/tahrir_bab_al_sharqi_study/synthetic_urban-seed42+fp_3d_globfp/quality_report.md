# Dataset quality report: tahrir_bab_al_sharqi_study

Role: study district. Approved as study district: yes.

**NOT fit for research:** 99.4 % of buildings have placeholder heights; observation worklist incomplete: 0 of 81 buildings observed, 0 rows matching no building.

## Where the building heights come from

| Category | Buildings | Share of buildings | Share of footprint area |
|---|---|---|---|
| observed | 10 | 0.4 % | 1.0 % |
| estimated | 4 | 0.2 % | 1.5 % |
| placeholder | 2507 | 99.4 % | 97.5 % |

| Source | Buildings | Share of footprint area |
|---|---|---|
| model:synthetic_urban:apartments | 69 | 16.7 % |
| model:synthetic_urban:commercial | 452 | 39.2 % |
| model:synthetic_urban:large_commercial | 7 | 6.0 % |
| model:synthetic_urban:small_residential | 954 | 7.0 % |
| model:synthetic_urban:standard_residential | 1025 | 28.7 % |
| osm:building:levels | 4 | 1.5 % |
| osm:height | 10 | 1.0 % |

**Synthetic Urban Model** `synthetic_urban` (synthetic-urban-1, baseline scenario, seed 42): 2507 of 2521 buildings (99.4 %) have estimated building heights from the model; 0 plain placeholders remain. Classes: apartments 69, commercial 452, large_commercial 7, small_residential 954, standard_residential 1025. These are modelling assumptions, not measurements; real footprints and known heights are unchanged.

## Height values

| Category | Min | Median | Max |
|---|---|---|---|
| observed | 1.0 m | 10.8 m | 60.0 m |
| estimated | 3.0 m | 13.5 m | 21.0 m |
| placeholder | 3.0 m | 6.0 m | 21.0 m |

## Geometry

- Buildings: 2521; without any height information: 2507; with more than one height source: 1; where sources disagree: 0.
- Relations read: 8; with missing members: 0; duplicate footprint pairs: 2.
- Built share of the receiver area: 35.8 %.
- Elements skipped while reading: none.
- Cleaning: {'footprints added from 3d_globfp': 1327, 'footprints added from 3d_globfp in the receiver area': 577, 'footprint area added from 3d_globfp in the receiver area (m2)': 125143, 'buildings_split_into_pieces': 1, 'dropped_small': 2, 'overlaps_resolved': 518, 'buildings_outside_area_or_too_small': 34, 'footprints_before_merge': 2521, 'solids_after_merge': 2156, 'different_height_contacts': 391}.
- Mesh: 33999 triangles, 25523 wedges, 0 non-manifold edges, 0 degenerate triangles.

## Height warnings (1)

- way/645196998: implausible building:levels='0' ignored
