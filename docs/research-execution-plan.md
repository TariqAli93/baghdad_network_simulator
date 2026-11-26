# Final research execution plan (after supervisor approval)

Decisions: approved on 2026-11-26 (`docs/approval-record.md`). Steps 1 and 4 are done; step 2
waits for the field observations; everything after it waits for step 2.

| Step | State on 2026-11-26 |
|---|---|
| 1 Study area | done: `tahrir_bab_al_sharqi_study` (approved study district, snapshot `tahrir_bab_al_sharqi_v2`) |
| 2 Footprints and heights | footprints done (`--add-footprints 3d_globfp`: 577 footprints, 125,143 m² added in the receiver area); **heights wait for the observations** of the 330 worklist buildings |
| 3 Quality | not fit: 99.4 % placeholder heights; becomes fit when the worklist is complete (rule in `bns.geospatial.quality`) |
| 4 Radio parameters | done: all approved |
| 5-15 | blocked by step 2 |

Exact commands for the approved district:

```
uv run python scripts/build_dataset.py --area tahrir_bab_al_sharqi_study --add-footprints 3d_globfp --observations <filled height_worklist.csv>
uv run python scripts/plan_sites.py --area tahrir_bab_al_sharqi_study --variant "osm+observations+fp_3d_globfp" --mode research --profile preview --min-height <A4> --min-spacing <A4> --heights observed,estimated
```

All supervisor decisions are approved (`docs/approval-record.md`). Every command below runs in
research mode only with the research baseline on a dataset fit for research and after the
final-scene convergence; until then results are classified as Preliminary Simulations.
Run on the machine whose times were accepted (laptop gate, `docs/laptop-acceptance.md`), on
the CPU backend unless decision C6 approves the GPU. Times are development-PC measurements.

| # | Step | Command / action | Check before moving on |
|---|---|---|---|
| 1 | Import the approved study area | Edit `configs/study_area.yaml`: new area entry with the approved centre, size, margin; `role: study district`, `approved: true`. Fetch a new snapshot: `uv run python scripts/build_dataset.py --area <name> --fetch` | Snapshot written with SHA-256; never overwrite an existing snapshot |
| 2 | Resolve footprints and heights | Add the approved footprint source (A2); record field observations in a CSV (`scripts/height_worklist.py --area <name> ...` gives the list; see its `--help` for the required distance and site settings); rebuild: `uv run python scripts/build_dataset.py --area <name> --observations <file.csv> [--height-dataset <approved dataset>]` | Every height has a provenance record; conflicts listed in the quality report are resolved or explained |
| 3 | Validate geographic data quality | Read `outputs/datasets/<name>/<variant>/quality_report.md`; Study area page | `fit_for_research: true`; placeholder share and missing footprints within what A2 accepted |
| 4 | Apply approved radio parameters | Set `status: approved`, `approved_by` for every parameter in `configs/radio_system.yaml` (A3); the threshold and load exactly as approved | Radio scenarios page shows all parameters approved; `doctor.ps1` reports the count |
| 5 | Generate the approved candidate sites | Implement the A4 placement if it is the roof edge (one change in the candidate generator, with a test); `uv run python scripts/plan_sites.py --area <name> --mode research --profile preview --min-height <A4> --min-spacing <A4> --heights observed,estimated` (first run traces) | 20-40 candidates on roofs with observed or storey-based heights |
| 6 | Preview experiments | Site plan above at preview; single-site and multi-site preview runs on the Run page | Plausible maps; no candidate on a placeholder roof; workload estimate recorded |
| 7 | Confirm convergence | `uv run python scripts/run_convergence.py --area <name>` on the approved dataset; accept the profile only if its criterion holds, then set its `status: approved` | Profile criterion met on the final district (not just the development area) |
| 8 | Final five-band simulations | `uv run python scripts/run_multi_site.py --area <name> --mode research --profile standard --buildings <selected sites>` | Run completes; manifest shows `APPROVED RESEARCH CONFIGURATION`, backend CPU |
| 9 | Single- and multi-site comparisons | The same script with one building (single site) and with the plan's sites; Comparison page | Runs are comparable (no warning on the Across runs tab) |
| 10 | Interference-aware site planning | `uv run python scripts/plan_sites.py --area <name> --mode research --profile standard ...` (traces cached candidates once at standard) | Stop reason per band reported; no minimum claimed |
| 11 | 3GPP model comparisons | `uv run python scripts/validate_tr38901.py --area <name> --profile <accepted profile>` | Report LOS within σ or not; do not claim the NLOS difference is explained without further evidence |
| 12 | MATLAB cross-check | `uv run python scripts/export_matlab_case.py <validation run>`; run `run_case.m` on the laptop; `uv run python scripts/compare_matlab.py validation/matlab/<case>` | Criterion agreed under B1 |
| 13 | Export research results | Reports and exports page: HTML report, CSVs, figures, manifest per run; `scripts/make_distribution.py` for a clean archive | Label reads APPROVED RESEARCH CONFIGURATION; licences per `docs/licensing.md` |
| 14 | Uncertainty and limitations | Height sensitivity (`scripts/run_height_sensitivity.py`), coverage/load sensitivity (`scripts/run_sensitivity.py <run>`), convergence floor, engine limitations (B2), MATLAB differences | Each limitation stated beside the result it affects |
| 15 | Conclusions and roadmap | The student writes conclusions and the roadmap recommendations (6G roadmap page; saved locally) from the approved results | Recommendations cite the verified evidence and the approved runs; no generated conclusions |

## Expected effort (development PC, CPU)

- Standard profile, sector antenna: about 60-75 s per trace; one site × 3 sectors × 5 bands = 15
  traces ≈ 20-25 minutes including start-up and retries.
- Site planning at standard with 30 candidates: 450 traces ≈ 8-10 hours (preview: about 1 hour).
- Isotropic standard traces take about 80 s each since the power-throttling fix
  (`docs/benchmarks.md` §11); before it they took 5-18 minutes when Windows moved the worker
  to the efficiency cores.
- Laptop times: unknown until `benchmark.ps1` has been run there.
