# Dataset quality report: tahrir_bab_al_sharqi_v2

Role: provisional study area. Approved as study district: no.

**NOT fit for research:** the area is a provisional study area, not the study district; the area has not been approved by the supervisor; the building-height methodology has not been approved; 27.0 % of buildings have placeholder heights.

## Where the building heights come from

| Category | Buildings | Share of buildings | Share of footprint area |
|---|---|---|---|
| observed | 9 | 0.8 % | 1.8 % |
| estimated | 862 | 72.3 % | 71.3 % |
| placeholder | 322 | 27.0 % | 26.9 % |

| Source | Buildings | Share of footprint area |
|---|---|---|
| dataset:3D-GloBFP figshare | 858 | 68.7 % |
| osm:building:levels | 4 | 2.6 % |
| osm:height | 9 | 1.8 % |
| placeholder | 322 | 26.9 % |

## Height values

| Category | Min | Median | Max |
|---|---|---|---|
| observed | 1.0 m | 10.0 m | 60.0 m |
| estimated | 1.2 m | 19.2 m | 96.5 m |
| placeholder | 9.0 m | 9.0 m | 9.0 m |

## Geometry

- Buildings: 1193; without any height information: 322; with more than one height source: 5; where sources disagree: 3.
- Relations read: 8; with missing members: 0; duplicate footprint pairs: 2.
- Built share of the receiver area: 23.2 %.
- Elements skipped while reading: none.
- Cleaning: {'dataset 3D-GloBFP figshare: matched buildings': 884, 'dropped_small': 2, 'overlaps_resolved': 301, 'buildings_outside_area_or_too_small': 36, 'footprints_before_merge': 1193, 'solids_after_merge': 949, 'different_height_contacts': 467}.
- Mesh: 14012 triangles, 10589 wedges, 0 non-manifold edges, 0 degenerate triangles.

## Height warnings (3)

- way/919688856: sources disagree: osm:height 55 m vs dataset:3D-GloBFP figshare 80.002 m
- way/745209243: sources disagree: osm:building:levels 9 m vs dataset:3D-GloBFP figshare 80.002 m
- way/1085956708: sources disagree: osm:height 3 m vs dataset:3D-GloBFP figshare 34.9365 m
