# Data and software licensing, and what may be distributed

Reviewed 2026-11-26 for release candidate v1.0.0-rc.1. This is an engineering inventory, not
legal advice: the supervisor (and, for any paid or commercial use, the client) must confirm
the conclusions marked *to confirm*.

## 1. Datasets

| Dataset | Where in the project | Licence | Obligations | Distributed in the clean archive? |
|---|---|---|---|---|
| OpenStreetMap snapshots (Overpass) | `data/raw/osm/*.json` | ODbL 1.0 | Attribution "© OpenStreetMap contributors"; derived databases (scene meshes, building tables) stay ODbL; produced works (maps, figures, statistics) need attribution | **Yes**, with attribution |
| 3D-GloBFP extract (figshare v4) | `data/raw/heights/3d_globfp/`, `outputs/datasets/*/3d_globfp_*` | CC BY 4.0 | Attribution (citation in `configs/height_datasets.yaml`) | **Yes**, with attribution |
| GlobalBuildingAtlas LoD1 (Hugging Face) | tile in `data/cache/datasets/gba/` (git-ignored); extract in `data/raw/heights/gba/` (git-ignored since Phase 7) | **CC BY-NC 4.0** (non-commercial) | Attribution; no commercial use; the dataset card warns about combining with the ODbL polygon part | **No.** Per-building values are excluded (see §3) |
| Derived scene variant `osm+gba` | `data/scenes/*/osm+gba` (git-ignored) | OSM ODbL + GBA CC BY-NC | both | **No** |
| ITU-R / 3GPP documents | not stored; cited by URL in `docs/references.md` | publisher terms | citation only | not applicable |
| Project description PDF | outside the repository | the student's | — | **No** |

Historical content: GBA per-building files (`data/raw/heights/gba/*.json`,
`outputs/datasets/tahrir_bab_al_sharqi_v2/gba_buildings.csv`) are in commit `e0d8a8e`
(tags `v0.5.0`, `v0.5.0-multisite-application`). **Do not distribute the git repository
(its history) until the GBA licence question is resolved**; distribute the clean archive
instead (§3). Rewriting history needs explicit approval and was not done.

## 2. Software (installed by `uv sync`, not bundled)

| Package | Licence |
|---|---|
| Sionna RT 2.2.0 | Apache-2.0 |
| Mitsuba 3.9.1, Dr.Jit 1.5.0 | BSD-3-Clause |
| LLVM 18.1.8 (system install) | Apache-2.0 with LLVM exceptions |
| Streamlit, NumPy, SciPy, Matplotlib, Shapely, pyproj, PyYAML, psutil, pyshp, mapbox-earcut | Apache-2.0 / BSD / MIT family |
| Plotly | MIT |
| ITU-Rpy 0.4.0 (`itur`, gas attenuation at custom carriers) | MIT |
| astropy 8.0.3, pyerfa 2.0.1.5, astropy-iers-data (pulled in by ITU-Rpy) | BSD-3-Clause |

The project's own code carries no licence file yet: *to confirm* with the student and
supervisor before publication.

## 3. Restricted artifacts and the clean distribution

`scripts/make_distribution.py` builds `dist/baghdad-network-simulator-<version>.zip` from the
**current commit only** (`git archive`, no history), leaving out the paths listed in
`configs/distribution.yaml` and checking that nothing matching them remains. Excluded today:

- `outputs/datasets/*/gba_evaluation.md` and `gba_evaluation.json` (individual GBA heights)
- `outputs/datasets/*/osm+gba/` (conflict lists with individual GBA heights)
- `outputs/datasets/propagation_*osm+gba*` (comparisons of the GBA variant)
- `scripts/evaluate_gba.py`, `src/bns/geospatial/gba.py` and `tests/unit/test_gba.py` stay in
  (code only, no data); `configs/height_datasets.yaml` keeps only metadata.

*To confirm:* `docs/building-height-data.md` §12 and `docs/implementation-plan.md` quote a
handful of GBA values (for example the tower at 5.4 m) as part of the scientific evaluation.
If the licence review rejects even such quotations, remove them before distribution.

Run archives and reports: the Reports page ZIP contains only a run folder's files (manifest,
summary, notes, figures, CSVs). Runs of the `osm` variant contain no GBA data. A run of any
variant whose name contains `gba` is flagged on the Reports page as derived from
non-commercial data.

## 4. What a user must acquire themselves

- GlobalBuildingAtlas (only if the supervisor approves it as a sensitivity case): download the
  tile named in `configs/height_datasets.yaml` (SHA-256 checked) and run
  `scripts/evaluate_gba.py`.
- 3D-GloBFP full tile (205 MB): only to rebuild the extract (`scripts/import_height_dataset.py`).
- New OpenStreetMap snapshots: `scripts/build_dataset.py --fetch` (internet).

## 5. Attribution text for reports and the thesis

"Building footprints © OpenStreetMap contributors (ODbL). Missing footprints added from, and
building heights evaluated with, 3D-GloBFP (Che et al., 2024, CC BY 4.0). Ray tracing with Sionna
RT (NVIDIA, Apache-2.0)."
Add GlobalBuildingAtlas (Zhu et al., CC BY-NC 4.0) only if it is used.
