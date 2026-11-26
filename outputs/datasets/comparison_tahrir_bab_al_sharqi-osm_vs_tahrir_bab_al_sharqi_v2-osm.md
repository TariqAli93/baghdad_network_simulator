# Dataset comparison: tahrir_bab_al_sharqi/osm vs tahrir_bab_al_sharqi_v2/osm

- A: OSM snapshot a4ee708c09e0; B: OSM snapshot 852683848789.

| Quantity | A | B |
|---|---|---|
| Buildings | 1186 | 1194 |
| From multipolygon relations | 0 | 8 |
| Relations read / with missing members | 0 / 0 | 8 / 0 |
| Elements skipped while reading | {'relation stored without member geometry': 8} | none |
| Duplicate footprint pairs | 2 | 2 |
| Footprint area | 312,231 m² | 318,272 m² |
| Built share of receiver area | 22.65 % | 23.24 % |
| Mesh triangles / wedges | 9873 / 7149 | 10046 / 7261 |
| Mesh defects (non-manifold edges, degenerate triangles) | 0, 0 | 0, 0 |

- Buildings only in A: 0 ({}), 0 m².
- Buildings only in B: 8 ({'relation': 8}), 6,041 m²; 7 of them have courtyards (inner rings).
- Buildings in both whose footprint changed by more than 1 m²: 0 (area changed: 0).

| Building only in B | Footprint | Courtyards | Height | Height source |
|---|---|---|---|---|
| relation/12758059 | 2,388 m² | 1 | 9 m | placeholder |
| relation/12758060 | 924 m² | 1 | 9 m | placeholder |
| relation/13021473 | 157 m² | 0 | 9 m | placeholder |
| relation/15347655 | 111 m² | 1 | 9 m | placeholder |
| relation/15920193 | 1,208 m² | 1 | 9 m | placeholder |
| relation/17480052 | 288 m² | 2 | 9 m | placeholder |
| relation/17480053 | 250 m² | 1 | 9 m | placeholder |
| relation/17480054 | 715 m² | 1 | 9 m | placeholder |

