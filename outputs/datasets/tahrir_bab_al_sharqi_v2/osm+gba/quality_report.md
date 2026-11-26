# Dataset quality report: tahrir_bab_al_sharqi_v2

Role: provisional study area. Approved as study district: no.

**NOT fit for research:** the area is a provisional study area, not the study district; the area has not been approved by the supervisor; the building-height methodology has not been approved; 45.9 % of buildings have placeholder heights.

## Where the building heights come from

| Category | Buildings | Share of buildings | Share of footprint area |
|---|---|---|---|
| observed | 9 | 0.8 % | 1.8 % |
| estimated | 636 | 53.3 % | 73.3 % |
| placeholder | 548 | 45.9 % | 24.9 % |

| Source | Buildings | Share of footprint area |
|---|---|---|
| dataset:GlobalBuildingAtlas GBA.LoD1 | 632 | 70.6 % |
| osm:building:levels | 4 | 2.6 % |
| osm:height | 9 | 1.8 % |
| placeholder | 548 | 24.9 % |

## Height values

| Category | Min | Median | Max |
|---|---|---|---|
| observed | 1.0 m | 10.0 m | 60.0 m |
| estimated | 1.4 m | 8.8 m | 28.3 m |
| placeholder | 9.0 m | 9.0 m | 9.0 m |

## Geometry

- Buildings: 1193; without any height information: 548; with more than one height source: 13; where sources disagree: 6.
- Relations read: 8; with missing members: 0; duplicate footprint pairs: 2.
- Built share of the receiver area: 23.2 %.
- Elements skipped while reading: none.
- Cleaning: {'dataset GlobalBuildingAtlas GBA.LoD1: matched buildings': 645, 'buildings_split_into_pieces': 1, 'dropped_small': 2, 'overlaps_resolved': 328, 'buildings_outside_area_or_too_small': 35, 'footprints_before_merge': 1193, 'solids_after_merge': 854, 'different_height_contacts': 415}.
- Mesh: 13380 triangles, 10035 wedges, 0 non-manifold edges, 0 degenerate triangles.

## Height warnings (6)

- way/1085956708: sources disagree: osm:height 3 m vs dataset:GlobalBuildingAtlas GBA.LoD1 14.23 m
- way/1154123513: sources disagree: osm:height 15 m vs dataset:GlobalBuildingAtlas GBA.LoD1 1.71 m
- way/1176936667: sources disagree: osm:height 11.5 m vs dataset:GlobalBuildingAtlas GBA.LoD1 2.81 m
- way/82967076: sources disagree: osm:height 60 m vs dataset:GlobalBuildingAtlas GBA.LoD1 13.18 m
- way/919688856: sources disagree: osm:height 55 m vs dataset:GlobalBuildingAtlas GBA.LoD1 5.43 m
- way/939812415: sources disagree: osm:height 10 m vs dataset:GlobalBuildingAtlas GBA.LoD1 1.89 m
