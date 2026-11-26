# Field-observation worklist: review and prioritisation (2026-11-27)

Inputs: `outputs/datasets/tahrir_bab_al_sharqi_study/height_worklist.csv` (from
`scripts/height_worklist.py`, settings: mast 3 m, candidates ≥ 10 m with observed heights,
150 m apart, tall ≥ 20 m, near-site 150 m, blocking share 0.5) and the study dataset
`osm+fp_3d_globfp`. Package: `outputs/datasets/tahrir_bab_al_sharqi_study/fieldwork/`.

## 1. Review of the worklist

| Check | Finding |
|---|---|
| Duplicate ids | none (each building once; repaired pieces are merged back to their building) |
| Overlapping categories | one building is both tall and a candidate (the 55 m tower); it is counted once, as P0 |
| Defect found | two "candidate rooftops" were the **Freedom Monument** (way/1154123513, `historic=monument`) and the **Faeq Hassan mural** (way/939812415, `memorial=yes`, `tourism=artwork`). Monuments, memorials and artworks are now excluded from transmitter candidates (they stay obstacles). The worklist fell from **330 to 190** buildings because most "may block" entries surrounded those two low "sites". The earlier development multi-site runs used them as sites; those runs stay labelled development and must not be reported. |
| Defect found | 81 footprints added from 3D-GloBFP had broken OpenStreetMap links; links are now given only for OSM objects |
| Candidates now | 2 with observed heights: the 55 m tower and a 12 m commercial building (A4 asks for 20-40) |

## 2. Priorities (`scripts/fieldwork_package.py`)

| Priority | Buildings | Rule |
|---|---|---|
| P0 | 3 | tall by any source (≥ 20 m) |
| P1 | 1 | candidate transmitter rooftop (the tower is P0) |
| P2 | 34 | the worklist buildings that cast **90 %** of the shadow around the candidates: for each roof-edge antenna (A4) and each outdoor point every 10 m within 150 m, the first building whose **current** height cuts the straight line (`bns.geospatial.sites.shadowing_buildings`) |
| P3 | 152 | the rest of the worklist |
| S | 43 | proposal: large (≥ 1,000 m²) placeholder buildings in the receiver area, for a candidate search by storey count |

Shadow lines: 895 in total; worklist buildings block 587 of them first, P2 covers 532
(90.6 %). Another 17 buildings outside the worklist block a few lines (largest 8): they fall
below the worklist's blocking rule and are listed by the script for information.

## 3. Proposed reduced set (needs the supervisor's approval)

**Proposal:** observe P0 + P1 + P2 (**38 buildings**, P0/P1 measured or documented) plus storey
counts of the S group (43, quick from the street), instead of all 190; cover P3 with the
approved height sensitivity analysis.

Why it is defensible:
- P0/P1 decide antenna heights and the dominant shadows; P2 are the buildings that decide
  the shadowed area near the sites at today's heights.
- P3 buildings are hidden behind others from every candidate antenna: an error in their
  height changes few lines of sight; the sensitivity analysis (A2) already reports the
  spread over assumed heights.

Limits of the argument (why it is a proposal, not a change):
- P2 is computed with **current** heights, 99 % of which are 9 m placeholders; a P3 building
  that is in fact much taller could cast a shadow. A storey count of P3 from the street is
  cheap and removes that risk.
- The candidate set will change after stage 1 (S storey counts); P2/P3 must be recomputed then.
- Only geometry (straight lines, plan footprints) was used; no new propagation runs.

Until approved, `configs/study_area.yaml` keeps `required_priorities: [P0, P1, P2, P3]`, and the
dataset stays unfit for research until all 190 are observed. Approval would mean changing that
list to `[P0, P1, P2]` (and adding `S` if the supervisor wants the candidate search mandatory).
