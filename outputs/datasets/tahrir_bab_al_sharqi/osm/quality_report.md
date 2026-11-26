# Dataset quality report: tahrir_bab_al_sharqi

Role: development fixture. Approved as study district: no.

**NOT fit for research:** the area is a development fixture, not the study district; the area has not been approved by the supervisor; the building-height methodology has not been approved; 98.8 % of buildings have placeholder heights.

## Where the building heights come from

| Category | Buildings | Share of buildings | Share of footprint area |
|---|---|---|---|
| observed | 10 | 0.8 % | 1.8 % |
| estimated | 4 | 0.3 % | 2.7 % |
| placeholder | 1172 | 98.8 % | 95.5 % |

| Source | Buildings | Share of footprint area |
|---|---|---|
| osm:building:levels | 4 | 2.7 % |
| osm:height | 10 | 1.8 % |
| placeholder | 1172 | 95.5 % |

## Height values

| Category | Min | Median | Max |
|---|---|---|---|
| observed | 1.0 m | 10.8 m | 60.0 m |
| estimated | 3.0 m | 13.5 m | 21.0 m |
| placeholder | 9.0 m | 9.0 m | 9.0 m |

## Geometry

- Buildings: 1186; without any height information: 1172.
- Built share of the receiver area: 22.6 %.
- Elements skipped while reading: {'relation stored without member geometry': 8}.
- Cleaning: {'dropped_small': 2, 'overlaps_resolved': 317, 'buildings_outside_area_or_too_small': 35, 'footprints_before_merge': 1186, 'solids_after_merge': 453, 'different_height_contacts': 55}.
- Mesh: 9873 triangles, 7149 wedges, 0 non-manifold edges, 0 degenerate triangles.

## Height warnings (1)

- way/645196998: implausible building:levels='0' ignored
