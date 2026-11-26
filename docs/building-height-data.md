# Building-height data for Baghdad

Investigated 2026-11-26. Every figure marked "measured" was obtained that day for the test
box around Tahrir Square / Bab Al-Sharqi (33.32196-33.33404° N, 44.40130-44.41570° E, about
1.3 km square). No dataset has been selected: that is decision D2 in
`docs/supervisor-decisions.md`.

## 1. Findings

1. **OpenStreetMap has almost no heights here**: 14 of about 1,200 buildings carry a height
   or storey tag.
2. **Two datasets give a height for every building in the box**, both estimated by machine
   learning from satellite data: GlobalBuildingAtlas (measured) and 3D-GloBFP (per its
   documentation; not yet measured in the box).
3. **The sources disagree by about a factor of two**, and none has been validated anywhere
   in Iraq:

   | Source, at the same 2,531 building locations | Median | 95th percentile | Maximum |
   |---|---|---|---|
   | GlobalBuildingAtlas (per building) | 6.3 m | 12.7 m | 28.3 m |
   | WSF 3D (90 m grid) | 6.4 m | 19.4 m | 48.9 m |
   | GHSL (100 m grid) | 13.2 m | 19.9 m | 22.0 m |
   | 3D-GloBFP (whole regional tile, not the box) | 12.7 m | 27.6 m | 126.0 m |

4. **Tall buildings are lost.** The one high-rise in the box whose height is tagged (the
   "Turkish Restaurant" building, OSM way 919688856: 14 storeys, 55 m) comes out as 5.4 m in
   GlobalBuildingAtlas, 10.9 m in GHSL and 15.0 m in WSF 3D. Tall buildings host the sites
   and cast the longest shadows, so this is the error that matters most.
5. **No source can be ranked by accuracy here**: only about four tagged buildings in the box
   are usable as ground truth.

Consequence: a modelled dataset can supply plausible heights for the mass of low buildings,
but the tall buildings and every candidate site need observed heights, and the thesis needs
a sensitivity analysis over the height source. The project's own test with assumed height
distributions (`outputs/runs/height_sensitivity/`) shows the site count changing with the
height model, everything else being equal.

## 2. Sources compared

"Per building" means the dataset stores a height for each individual building, as opposed
to an average over a grid cell.

| Source | Per building? | Coverage of the test box | Resolution | Data date | Stated accuracy | Licence | Download | Integration | Main limitation |
|---|---|---|---|---|---|---|---|---|---|
| **OpenStreetMap tags** (`height`, `building:levels`) | Yes | 14 of ~1,200 buildings (measured) | Per building | Edits 2016-2026 | None; volunteer values, unverified | ODbL | Already in the project | Done | Almost empty; some tagged objects are monuments |
| **Supervisor-approved observations** (storeys counted on site) | Yes | Whatever is surveyed | Per building | When surveyed | Storey count exact; height depends on the assumed storey height | Own data | None | Done (`--observations` CSV) | Student time; storey height is an assumption |
| **GlobalBuildingAtlas** LoD1 (TU Munich) | **Yes** | 2,531 footprints, all with a height (measured) | Per building, from a 3 m height map | Imagery mainly 2019 | RMSE 5.5 m globally, 5.9 m in Asia, against official 3D city models in 28 cities | **CC BY-NC 4.0** (non-commercial); footprints ODbL | No account. Whole-tile files are 378 MB (heights) and 2.09 GB (footprints); the box was read with partial requests (about 60 MB) | Moderate: line-delimited GeoJSON; needs a spatial join to OSM buildings | Trained on 168 cities, none in the Middle East; the authors state high-rise heights are underestimated; the 55 m tower reads 5.4 m |
| **3D-GloBFP** (Che et al.) | Yes, per its documentation | **Not measured in the box**; the regional tile has 2.59 million buildings | Per building | Nominal 2020 | RMSE 1.9-14.6 m across 33 regions; below 6 m for buildings under 20 m | **CC BY 4.0** | No account; one 205 MB file | Moderate: shapefile; needs a shapefile reader and a spatial join | A model estimate; authors report overestimating low-rise and underestimating high-rise buildings |
| **GHSL GHS-BUILT-H** R2023A (European Commission) | **No**: average per 100 m cell | 182 cells, none missing (measured); values 2.5-22 m | 100 m | 2018 | MAE 2.0 m, RMSE 3.6 m against European data; nothing in Iraq | CC BY 4.0 | No account; 8 MB tile | Easy with a raster reader (`rasterio`) | A cell average: towers disappear (maximum 22 m in the box) |
| **GHS-OBAT** R2024A (European Commission) | Formally yes, but each building just receives the GHSL cell average | Iraq file exists | Per building (from the 100 m grid) | 2018-2020 | MAE 2.9 m against European cadastres | CC BY 4.0 | 223 MB | Easy (CSV) | Adds nothing over GHSL |
| **WSF 3D** (German Aerospace Center) | **No**: average per 90 m cell | 270 cells, 16 % missing (measured) | 90 m | Elevation data 2011-2013 | Not verified; an independent test gives RMSE 6.1 m in Asia | CC BY 4.0 | No account; read by partial request from a 2 GB file | Easy with a raster reader | Anything built after 2012 has no height |
| **Overture Maps** buildings | Only where OSM has it | 2,477 footprints; heights on the same 14 buildings as OSM (measured) | Per building | Release 2026-11-18 | None | ODbL | No account; query by bounding box | Easy | No height beyond OSM; useful as a second footprint source (twice OSM's count) |
| **Microsoft building footprints** | No heights in Iraq | Footprints only; height field is -1 (measured, Phase 0) | | | | CDLA-Permissive-2.0 | | | No heights |
| **Google Open Buildings 2.5D** | Does not cover Iraq | Confirmed from the official country list and the absence of tiles | | | | | | | No coverage |
| **UT-GLOBUS** | Yes, per its documentation | Coverage polygons include the box; contents not opened | Per building | Not verified | RMSE 9.1 m in six US cities | CC BY 4.0 | 68.5 MB inside a 4.6 GB archive | Unknown | Not examined |
| Iraqi or municipal GIS data, academic 3D models of Baghdad | | None found in one search | | | | | | | Absence not proven |

Details worth knowing:

- **GHSL has two layers.** "Net" height (built volume divided by built area) is the one to
  use for building heights; "gross" height (built volume divided by cell area) is much lower
  because it averages over open ground. The figures above are net heights.
- **How a grid would be assigned to buildings**: the European Commission's own per-building
  product takes the mean of the net-height cells a footprint touches, ignores empty cells and
  applies a 2.5 m minimum. Heights assigned this way belong in the "estimated" category with
  that method recorded.
- **GlobalBuildingAtlas against the tagged buildings** (matched by OSM id): 3 storeys → 10.7 m;
  6 storeys → 15.4 m; 7 storeys → 20.9 m; a 12 m tag → 12.4 m; the 14-storey, 55 m tower →
  5.4 m. Reasonable for mid-rise, wrong for the tower.
- **The non-commercial licence** of GlobalBuildingAtlas permits use in a university thesis
  with attribution. Any scene file containing its heights stays non-commercial, which matters
  only if the tool were ever to be sold. This is a reading of the licence text, not legal advice.
- **OpenStreetMap's own definition**: `height` is ground to roof top in metres;
  `building:levels` counts floors above ground, without roof floors. The wiki gives no
  default storey height, so "3 m per storey" is this project's assumption.

## 3. What the pipeline already supports

| Height source | Provenance category | How |
|---|---|---|
| OSM `height` tag | observed | automatic |
| OSM `building:levels` × storey height | estimated | automatic; storey height in `configs/study_area.yaml` |
| Observations for specific buildings | observed | `scripts/build_dataset.py --observations file.csv` |
| An assumed distribution | placeholder | `--height-model NAME --seed N` (`configs/height_models.yaml`) |
| Nothing | placeholder | default height |
| A per-building dataset or a height grid | estimated | **not built yet**: a reader is added once a dataset is chosen |

Every building's record keeps the original source values and names the source, the method
and, where the source gives one, the uncertainty. `quality_report.md` of each built dataset
gives the share of buildings and of footprint area in each category.

## 4. Sensitivity framework

`scripts/run_height_sensitivity.py` builds one scene per height model and compares, for
identical sites and settings: line-of-sight availability, cells reached only by diffraction,
unreached cells, path loss, coverage at given thresholds, and the number of sites the greedy
selection needs. Seeds are fixed; each building's draw depends only on the seed and its id.

Illustrative run on the fixture (four sites on buildings with tagged heights, 3.5 GHz, 10 m
cells, 10^8 rays, seed 1). The models are **not approved** and the numbers are **not
findings**; they show the size of the effect:

| Height model | Mean building height | Line of sight to any site | Median path loss | Coverage at 110 dB | Sites for 95 % at 110 dB |
|---|---|---|---|---|---|
| All 9 m | 9.1 m | 85.6 % | 93.6 dB | 97.6 % | 2 |
| 2-4 storeys | 9.1 m | 80.3 % | 94.2 dB | 96.3 % | 3 |
| Lognormal, median 10 m | 11.4 m | 75.0 % | 94.8 dB | 94.6 % | not reached with 4 available |
| 1-8 storeys | 13.5 m | 67.2 % | 96.2 dB | 91.2 % | not reached with 4 available |

Two models with the same mean height (9.1 m) already differ by one site: the spread of
heights matters, not only the average.

Once a dataset is selected, the same framework compares dataset-based heights against each
other (for example GlobalBuildingAtlas against GHSL, whose medians differ by a factor of two).

## 5. Recommendation (for decision D2)

1. A per-building modelled dataset as the base for ordinary buildings. GlobalBuildingAtlas
   is the only one measured in the box so far; 3D-GloBFP is the alternative with a more
   permissive licence and should be measured before choosing.
2. OSM tags override the dataset where present.
3. **Observed heights for every tall building and every candidate site**, recorded as
   observations. No dataset can be trusted for them.
4. A second height source (GHSL grid averages, or a height model) run through the
   sensitivity framework, and the spread reported with the results.

## 6. Downloads that would need approval

None was made. Each is listed with what it would settle.

| File | Size | Licence | What it settles |
|---|---|---|---|
| 3D-GloBFP tile `1590_43.75_32.5_45.0_33.75_IZ.zip` (figshare) | 205 MB | CC BY 4.0 | Whether 3D-GloBFP covers the box and how it treats the tower; needed before choosing between the two per-building datasets |
| GlobalBuildingAtlas heights `LoD1/africa/e040_n35_e045_n30.json` (Hugging Face) | 378 MB | CC BY-NC 4.0 | Confirms the partial read was complete; needed to use it for the study district |
| GlobalBuildingAtlas footprints for the same tile | 2.09 GB | ODbL | Same; could be avoided by joining heights to OSM footprints |
| UT-GLOBUS `Baghdad_2.gpkg` (Zenodo) | 68.5 MB within a 4.6 GB archive | CC BY 4.0 | A third per-building source |
| ITU-R P.837-8 rain maps (see `docs/atmospheric-losses.md`) | 361 MB | ITU | Current-edition rain rate for Baghdad |

## 7. Not verified

- The accuracy of any source in Baghdad: no validation data exists there.
- 3D-GloBFP inside the test box, and its error for this region.
- That the partial read of GlobalBuildingAtlas returned every building in the box (its
  footprint count, 2,531, matches Overture's 2,477 closely, which supports it).
- WSF 3D's own accuracy figures; the contents and reference year of UT-GLOBUS.
- Whether any Iraqi authority holds a 3D or height dataset for Baghdad.

## 8. Sources

GlobalBuildingAtlas: https://essd.copernicus.org/articles/17/6647/2025/ and
https://github.com/zhu-xlab/GlobalBuildingAtlas · 3D-GloBFP:
https://essd.copernicus.org/articles/16/5357/2024/ and https://zenodo.org/records/15459025 ·
GHSL: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_H_GLOBE_R2023A/ ·
WSF 3D: https://download.geoservice.dlr.de/WSF3D/files/READMEs/ · Overture Maps:
https://docs.overturemaps.org/guides/buildings/ · UT-GLOBUS:
https://zenodo.org/records/11156602 · Google Open Buildings 2.5D:
https://sites.research.google/gr/open-buildings/temporal/ · OpenStreetMap wiki:
https://wiki.openstreetmap.org/wiki/Key:height
