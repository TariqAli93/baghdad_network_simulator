# Dataset quality report: tahrir_bab_al_sharqi_v2

Role: provisional study area. Approved as study district: no.

**NOT fit for research:** the area is a provisional study area, not the study district; the area has not been approved by the supervisor; 98.8 % of buildings have placeholder heights.

## Where the building heights come from

| Category | Buildings | Share of buildings | Share of footprint area |
|---|---|---|---|
| observed | 10 | 0.8 % | 1.8 % |
| estimated | 4 | 0.3 % | 2.6 % |
| placeholder | 1180 | 98.8 % | 95.6 % |

| Source | Buildings | Share of footprint area |
|---|---|---|
| osm:building:levels | 4 | 2.6 % |
| osm:height | 10 | 1.8 % |
| placeholder | 1180 | 95.6 % |

## Height values

| Category | Min | Median | Max |
|---|---|---|---|
| observed | 1.0 m | 10.8 m | 60.0 m |
| estimated | 3.0 m | 13.5 m | 21.0 m |
| placeholder | 9.0 m | 9.0 m | 9.0 m |

## Geometry

- Buildings: 1194; without any height information: 1180; with more than one height source: 1; where sources disagree: 0.
- Relations read: 8; with missing members: 0; duplicate footprint pairs: 2.
- Built share of the receiver area: 23.2 %.
- Elements skipped while reading: none.
- Cleaning: {'buildings_split_into_pieces': 1, 'dropped_small': 2, 'overlaps_resolved': 319, 'buildings_outside_area_or_too_small': 34, 'footprints_before_merge': 1194, 'solids_after_merge': 454, 'different_height_contacts': 52}.
- Mesh: 10046 triangles, 7261 wedges, 0 non-manifold edges, 0 degenerate triangles.

## Height warnings (1)

- way/645196998: implausible building:levels='0' ignored
