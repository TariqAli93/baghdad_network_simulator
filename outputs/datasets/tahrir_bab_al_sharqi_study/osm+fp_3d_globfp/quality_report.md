# Dataset quality report: tahrir_bab_al_sharqi_study

Role: study district. Approved as study district: yes.

**NOT fit for research:** 99.4 % of buildings have placeholder heights; observation worklist incomplete: 0 of 190 buildings observed, 0 rows matching no building.

## Where the building heights come from

| Category | Buildings | Share of buildings | Share of footprint area |
|---|---|---|---|
| observed | 10 | 0.4 % | 1.0 % |
| estimated | 4 | 0.2 % | 1.5 % |
| placeholder | 2507 | 99.4 % | 97.5 % |

| Source | Buildings | Share of footprint area |
|---|---|---|
| osm:building:levels | 4 | 1.5 % |
| osm:height | 10 | 1.0 % |
| placeholder | 2507 | 97.5 % |

## Height values

| Category | Min | Median | Max |
|---|---|---|---|
| observed | 1.0 m | 10.8 m | 60.0 m |
| estimated | 3.0 m | 13.5 m | 21.0 m |
| placeholder | 9.0 m | 9.0 m | 9.0 m |

## Geometry

- Buildings: 2521; without any height information: 2507; with more than one height source: 1; where sources disagree: 0.
- Relations read: 8; with missing members: 0; duplicate footprint pairs: 2.
- Built share of the receiver area: 35.8 %.
- Elements skipped while reading: none.
- Cleaning: {'footprints added from 3d_globfp': 1327, 'footprints added from 3d_globfp in the receiver area': 577, 'footprint area added from 3d_globfp in the receiver area (m2)': 125143, 'buildings_split_into_pieces': 1, 'dropped_small': 2, 'overlaps_resolved': 518, 'buildings_outside_area_or_too_small': 34, 'footprints_before_merge': 2521, 'solids_after_merge': 1536, 'different_height_contacts': 43}.
- Mesh: 30576 triangles, 22389 wedges, 0 non-manifold edges, 1 degenerate triangles.

## Height warnings (1)

- way/645196998: implausible building:levels='0' ignored
