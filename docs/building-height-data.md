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
| 3D-GloBFP tile `1590_43.75_32.5_45.0_33.75_IZ.zip` (figshare) | 205 MB | CC BY 4.0 | **Downloaded and evaluated 2026-11-26 (section 9)** |
| GlobalBuildingAtlas heights `LoD1/africa/e040_n35_e045_n30.json` (Hugging Face) | 378 MB | CC BY-NC 4.0 | **Downloaded and evaluated 2026-11-26 (section 12)** |
| GlobalBuildingAtlas footprints for the same tile (GBA.ODbLPolygon) | 2.09 GB | ODbL | **Still not downloaded.** The only GBA source of the Microsoft footprints that OSM lacks (section 12) |
| UT-GLOBUS `Baghdad_2.gpkg` (Zenodo) | 68.5 MB within a 4.6 GB archive | CC BY 4.0 | A third per-building source |
| ITU-R P.837-8 rain maps (see `docs/atmospheric-losses.md`) | 361 MB | ITU | Current-edition rain rate for Baghdad |

## 9. 3D-GloBFP evaluated in the provisional area (Phase 2-3, 2026-11-26)

Downloaded with approval: figshare record 10.6084/m9.figshare.28890593.v4 (published
2025-12-05, CC BY 4.0), tile `1590_43.75_32.5_45.0_33.75_IZ.zip`, 205,205,235 bytes, MD5
matching the record. The original stays in `data/cache/datasets/3d_globfp/` (git-ignored);
the 2,526 footprints of the study box are extracted with their record numbers to
`data/raw/heights/3d_globfp/tahrir_bab_al_sharqi_v2.geojson` with a manifest (source
checksums, extraction date). Reproduce with `scripts/import_height_dataset.py` and
`scripts/evaluate_height_dataset.py`. Full report:
`outputs/datasets/tahrir_bab_al_sharqi_v2/3d_globfp_evaluation.md`; per-building table
`3d_globfp_buildings.csv`.

**Footprint matching** against the 1,194 OSM buildings (a building counts as matched when
dataset footprints cover at least half of it):

| Result | Count |
|---|---|
| Matched one-to-one | 191 |
| Matched, OSM building split into several dataset footprints | 101 |
| Matched, one dataset footprint spanning several OSM buildings | 568 |
| OSM buildings without a match | 334 |
| Dataset footprints overlapping no OSM building at all | 1,379 (275,628 m²) |
| Dataset duplicates (90 % overlap) | 0 |

One-to-one matches overlap only moderately (median intersection-over-union 0.58). Two
thirds of the matches are blocks that span several OSM buildings. The 1,379 dataset
footprints with no OSM counterpart cover nearly as much ground as the OSM buildings
themselves (about 318,000 m²): **OpenStreetMap is missing many buildings in this area**, a
second data-quality finding independent of heights.

**Heights:**

| Measure | Value |
|---|---|
| All dataset footprints in the receiver area | median 19.9 m, 95th percentile 37.4 m, maximum 96.5 m; 520 footprints above 30 m |
| One-to-one matches with good overlap (IoU ≥ 0.5) | median 21.4 m |
| Same area in GlobalBuildingAtlas (Phase 2 measurement) | median 6.3 m |
| Same area in GHSL (100 m cell averages, Phase 2) | median 13.2 m, maximum 22 m |
| Against the five tagged OSM buildings | mean +26.3 m, RMSE 36.6 m |
| The 55 m tower (way/919688856) | inside an 80 m footprint of 3,350 m² that covers 89 % of it and its neighbours |

**Verdict: not suitable as a height source for this area.** Its heights are systematically
higher than every other source and than the few tags (a three-storey building receives
80 m), its footprints merge neighbouring buildings into blocks, and the one tall building is
assigned the height of a block four times its size. This agrees with the authors' general
statement that such models overestimate low buildings. It remains useful as evidence that
OSM footprints are incomplete. **No other large dataset was downloaded.** GlobalBuildingAtlas
is the remaining per-building candidate (378 MB download, needs approval); its Phase 2
partial read showed a median of 6.3 m but also turned the tower into 5.4 m.

## 10. Hybrid height resolution (implemented)

Every building collects height candidates from all available sources; the configured
priority decides which one is used, and the others are kept as *alternatives* with their
own source, method and reference. Original OSM tags are never overwritten.

Priority in `configs/study_area.yaml` (provisional, decision D2):

1. observation — supervisor-approved field observations (`--observations` CSV)
2. osm_height — a valid OSM `height` tag
3. osm_levels — OSM `building:levels` × storey height
4. dataset — a building-level external dataset matched by footprint
5. model — a supervisor-approved statistical height model
6. placeholder — the explicit development default

**Why storeys rank above a dataset** (the brief proposed the opposite order, to be justified
against accuracy): a storey count is information about the building itself, and its error
comes only from the assumed storey height; the one dataset evaluated here was 26 m too high
on average where tags exist, and modelled datasets report errors of several metres per
building even where they were validated. The order is a configuration line and can be
swapped if the supervisor prefers.

Sources disagree when they differ by more than 6 m or a quarter of the chosen height; such
buildings are flagged ("conflicting sources") in the building table and the quality report.
Height categories are never upgraded: a dataset height is `estimated`, a model draw stays
`placeholder`, and only an OSM height tag or a field observation is `observed`.

Building tables (`buildings.geojson`) record, per building: identifier, footprint, height,
category, source, method, uncertainty where the source states one, reference (OSM object and
snapshot hash, dataset record and DOI, or observation file), the original OSM tags, the
alternatives and the conflict flag.

## 11. Manual overrides

`scripts/height_worklist.py` lists the buildings whose height should be observed: tall
buildings (by any source), candidate rooftops, buildings with conflicting sources, and
buildings near a candidate site that could block it. It writes a CSV with empty columns
`height_m, method, observer, date, uncertainty_m`; filled rows are applied with
`scripts/build_dataset.py --observations FILE` and become `observed` heights that outrank
every other source, while all earlier values stay attached as alternatives. Blank rows are
ignored. With illustrative arguments the provisional area gives 249 buildings to check, most
of them low buildings of unknown height near the four candidate sites.

## 12. GlobalBuildingAtlas evaluated in the provisional area (Phase 5, 2026-11-26)

Downloaded with approval: `LoD1/africa/e040_n35_e045_n30.json` from Hugging Face
`zhu-xlab/GBA.LoD1`, revision `9da24b3a8dce`, 378,494,857 bytes, SHA-256 `1d1246f8...`
verified against the repository's LFS record; cached in `data/cache/datasets/gba/`
(git-ignored); entry `gba` in `configs/height_datasets.yaml`. Licence **CC BY-NC 4.0**
(non-commercial); the dataset card warns that combining it with the ODbL polygon part may
have licence implications. Full report: `outputs/datasets/tahrir_bab_al_sharqi_v2/gba_evaluation.md`
(`scripts/evaluate_gba.py`).

**What the file is.** One JSON object of 4.28 million records `key -> {height, var}`, no
geometry. Keys name the footprint source: `osm<way id>IRQ` (137,000 Iraqi OSM ways),
`msIraq_<quadkey>_<n>IRQ` (3.94 million Microsoft footprints), `ours...` (derived by the
authors). `var` is not defined in the dataset card and is not used.

**Join.** GBA heights were joined to the OSM buildings by way id (relations cannot be joined:
GBA keys carry no element type). The study-area extract with a manifest is
`data/raw/heights/gba/tahrir_bab_al_sharqi_v2.json`.

| Quantity | Value |
|---|---|
| Receiver-area OSM buildings with a GBA height | 479 of 899 (53 % by count, 79 % by footprint area) |
| GBA heights in the receiver area | median 9.3 m, 5-95 % 4.7-15.9 m, maximum 20.9 m |
| 3D-GloBFP minus GBA, same 370 buildings | median +11.1 m, Spearman 0.32 |
| 14 OSM-tagged buildings (height tag or storeys × 3 m) | mean −8.1 m, RMSE 19.1 m; 12 below 30 m: RMSE 6.2 m |
| The tower way/919688856 (tag 55 m, 14 storeys) | GBA 5.4 m; 3D-GloBFP 80 m |
| way/82967076 (tag 60 m, outside the receiver area) | GBA 13.2 m |

**Assessment.**

- *Heights.* Plausible for ordinary low-rise buildings and closer to the tags than
  3D-GloBFP there, but **capped near 21 m**: every tall building is underestimated by tens of
  metres. Usable at most as a low-rise source, never for tall buildings or candidate sites.
- *Footprints.* The tile cannot recover the 577 footprints missing from OSM (section 9):
  those come from Microsoft and their geometry is only in the 2.09 GB ODbL polygon part.
  Whether they are genuinely missing buildings, newer construction or non-buildings stays
  open until that file (or another footprint source) is approved and compared.
- *Effect on propagation.* Dataset variant `osm+gba` (OSM tags keep priority over GBA;
  placeholder heights replaced where GBA has one: 53 % of buildings estimated, 46 %
  placeholder). Tower site, preview profile: median change 0.0 dB; 23 % of outdoor cells
  change by more than 1 dB, 7-8 % by more than 3 dB, 1.1-1.4 % by more than 10 dB, at both
  3.5 and 28 GHz (`outputs/datasets/propagation_*osm+gba*.md`). Height detail matters
  locally, as in the Phase 2 sensitivity runs.
- *A conflict it exposed.* The 31 m² structure way/645196998 (height tag 12 m) lies inside
  a building that GBA puts at 15.9 m; with GBA heights the overlap rule (the taller footprint
  wins) removes it, and with it a development site. One of the two values is wrong; it
  belongs on the observation worklist.

**Recommendation (for A2).** Do not adopt GBA as the height source. Keep it as a possible
low-rise sensitivity variant if the supervisor accepts the non-commercial licence. Tall
buildings and candidate rooftops need observations. Deciding about the missing footprints
needs approval of a footprint download (GBA ODbL part, 2.09 GB, or Microsoft footprints
directly).

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
