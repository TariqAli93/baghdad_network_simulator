# Research execution guide

Step by step, from the study area to the MATLAB comparison. Arabic version:
`docs/research-guide.ar.md`. Installation and the Simulation Workspace: `docs/user-guide.md`. The full
technical plan for the final study is `docs/research-execution-plan.md`.

## Before you start: simulation results are not measurements

| | Simulation results (this tool) | Empirical measurements |
|---|---|---|
| Where they come from | Ray tracing on a 3-D model of the district | A receiver measuring real signals in Baghdad |
| Building heights | Real footprints; heights mostly **estimated** by the Synthetic Urban Model | The real city |
| Status in this project | Available (classified "Simulation Results", "Custom Experiment", …) | **None exist** |

Write it this way in the thesis: the results show how the five scenarios behave **under the
stated assumptions**; they do not describe measured coverage of Baghdad. A result becomes
"Validated Research Results" only with measured building data for the study district, the final
convergence check (step 9) and a MATLAB comparison that meets the agreed criterion (step 10).
Candidate 6G (8 and 15 GHz) are research assumptions, and the 5G bands are assumed for Iraq.

Steps 7, 9 and 10 use commands. Double-click **`Research console.cmd`**: it opens a window in
the project folder where you type (or paste) the commands shown below and press Enter. Long runs:
connect the charger and keep the laptop awake.

## 1. Select the study area

**Study Area** page → **Area**: *Tahrir Square / Bab Al-Sharqi* (the approved study district,
about 1 km × 1 km). *Tahrir Square / Bab Al-Sharqi (provisional data)* is a development dataset:
never report Baghdad results from it. The map colours each building by where its height comes
from; the cards count observed/documented, synthetic and placeholder heights.

## 2. Select the Synthetic Urban Model

On **Study Area**, and in the **Simulation Workspace** under *Study area and dataset*, **Dataset**:

| Dataset | Use |
|---|---|
| Synthetic Urban Model (baseline) | the default for the simulations |
| Synthetic Urban Model (low-rise) / (high-rise) | the same footprints with lower / higher estimated heights: height sensitivity |
| `osm+fp_3d_globfp` | OpenStreetMap heights only (most buildings get a placeholder height) |

The synthetic heights are modelling assumptions (seed 42), not measurements
(`docs/synthetic-urban-model.md`).

## 3. Configure a simulation

**Simulation Workspace** (the page the application opens on; `docs/user-guide.md` sections 5-11):

1. **Experiment → New experiment**: every value starts at the research baseline.
2. **Area** and **Dataset** under *Study area and dataset*, as in steps 1-2.
3. **Resolution and engine → Simulation profile**: `standard` (10 m cells, 10⁹ rays) is the research
   baseline; `preview` (25 m, 10⁸ rays) is quicker for exploring and is recorded as a deviation
   (Custom Experiment). **Backend**: `CPU` is the research baseline; `GPU` is faster when an NVIDIA
   card exists and is recorded as a deviation.
4. **Stations**: **Site-rule roofs (n)** with the **Number of roofs** (1 = single site) places the
   stations on the tallest roofs that satisfy the site rule (automatic placement, as in the research
   baseline). **Place station** places one by hand on a chosen roof (manual placement, recorded
   separately); the building ID (`way/…`) is shown when you click a building and next to every site
   on the Site Planning page.
5. Other values (optional): power, antenna, receivers, load, coverage threshold, frequency and
   bandwidth. Changing one makes the run a Custom Experiment (or a Sensitivity Analysis for the
   threshold or load); **Reset to the research baseline** restores all values.
6. The run buttons say how many traces are needed; the Simulation panel shows how many are
   already saved and a time estimate when one was measured on this computer.

## 4. Run the five frequency scenarios

Every run computes **all five scenarios** at once: 4G 1.8 GHz, 5G 3.5 GHz, 5G 28 GHz, candidate 6G
8 GHz and 15 GHz (same sites and radio system; only frequency and bandwidth differ).

1. Tick all five scenarios in **Network scenarios (carriers)** and press **Run simulation (n
   traces)**. The panel shows traced / to trace. One simulation at a time.
2. **Cancel** stops the trace in progress; every committed trace stays saved and running again
   continues from there.
3. When it has finished, the results are on the map and the run is listed in **Experiment
   History**.

Time on the development PC (CPU, standard profile): about 1 minute per trace, 15 traces per site
(3 sectors × 5 bands), so about 20-25 minutes for one site. Your laptop's times are unknown until
you run `Laptop benchmark.cmd`.

## 5. Interpret coverage, SINR and data rates

In the workspace: the band and the layer above the map (or **Experiment History** → the run →
**View**). Grey cells are buildings (indoor cells are never counted).

| Quantity | Meaning |
|---|---|
| Path gain [dB] | Propagation loss only (no power, no interference). Never report it as coverage. |
| Received power [dBm] | Power of the serving (strongest) sector at 1.5 m. |
| SINR [dB] | Signal to interference plus noise: every other sector interferes (same carrier). Signal quality. |
| Coverage [%] | Share of outdoor cells with SINR ≥ −10 dB (research baseline); the target is 95 %. |
| Data rate (Shannon) | B·log₂(1+SINR): the theoretical upper bound for one user with the whole carrier, **not** user throughput or network capacity. |
| Data rate (3GPP mapping) | A truncated LTE/NR mapping beside Shannon (an NR-based approximation for candidate 6G). |
| 5th percentile | The value the weakest 5 % of outdoor cells stay below: the cell-edge experience. |

Higher bands have wider bandwidths (20, 100 and 400 MHz), so their Shannon rates can be higher
even where their SINR is lower.

## 6. Compare the scenarios

- In the workspace: **Compare bands and configurations** below the map (one layer in every band on
  one scale).
- **Scenario Comparison** page: *Scenarios in one run* (table, bar charts, CDFs); *Across runs*
  (a yellow warning lists every difference: such runs are not the same experiment), with *Two runs
  side by side*; *Site counts*; *3GPP model check*; *Sensitivity Analysis*; *Limitations*.
- Height sensitivity: run the same sites on the low-rise, baseline and high-rise datasets and
  compare them *Across runs*.

## 7. Site planning

1. Create a plan in the **Research console** (preview first: about an hour on the development PC
   for 30 candidates; at standard expect many hours):

   ```
   python scripts/plan_sites.py --area tahrir_bab_al_sharqi_study --variant "synthetic_urban-seed42+fp_3d_globfp" --profile preview --max-candidates 30
   ```

2. **Automatic Site Planning** page → the saved plan: sites chosen in order, coverage after each, why the
   search stopped, final map. Below, try other selections, threshold, load or target: these
   sliders are sensitivity checks (nothing is traced).
3. Run the selected sites at the research baseline: in the workspace place a station on each
   selected building (`way/…`) with **Place station**, profile `standard`, backend `CPU`.

The greedy result is a heuristic over these candidates, **not** a proven minimum number of sites.

## 8. Generate reports

**Reports** page → saved run → **Printable report** → **Report language** (العربية / English) →
**Report (HTML, print to PDF)**. Open the downloaded file in the browser and print it to PDF. The
report keeps the classification, the deviations and the limitations; keep them with every number
you quote. Below: CSV per scenario (one row per cell), manifest and summary (JSON), the whole run
folder (ZIP) and the figures (PNG, English).

## 9. Numerical convergence check

Checks whether the ray count is enough for the cell size (`docs/convergence.md`). Long: many
1-billion-ray traces; run it overnight on the charger. In the **Research console**:

```
python scripts/run_convergence.py --area tahrir_bab_al_sharqi_study
```

It traces the district's OpenStreetMap scene and a mixed-height variant, and writes
`outputs\runs\convergence\tahrir_bab_al_sharqi_study\summary.md`. Criteria: 25 m cells within
3 dB and at most 2 % missed cells; 10 m and 5 m within 2 dB and at most 1 %. Only the supervisor
accepts a profile as converged on the final scene (recorded in `configs/simulation.yaml`); that
evidence then applies only to runs on the same scene, profile and backend (`docs/validation.md`).

## 10. MATLAB comparison

MATLAB is not part of this package; it runs on a computer that has MATLAB with Antenna Toolbox
or Communications Toolbox ray tracing.

1. Controlled 3GPP comparison run (**Research console**):

   ```
   python scripts/validate_tr38901.py --area tahrir_bab_al_sharqi_study --variant "synthetic_urban-seed42+fp_3d_globfp" --profile standard
   ```

2. Export the MATLAB case from the folder it wrote under `outputs\validation\`:

   ```
   python scripts/export_matlab_case.py outputs\validation\<the new tr38901-… folder>
   ```

   (A case from the development area is already prepared: `validation\matlab\uma-tahrir_bab_al_sharqi_v2-osm\`.)
3. Copy the case folder (`validation\matlab\<case>\`) to the MATLAB computer, open MATLAB in it
   and run `run_case`. It writes `matlab_results.csv`.
4. Copy `matlab_results.csv` back into the same case folder and compare:

   ```
   python scripts/compare_matlab.py validation\matlab\<case>
   ```

5. Read `comparison.md` in the case folder and the **Validation** page. Agreed criterion
   (decision B1): median |MATLAB − Sionna| in line-of-sight cells ≤ 2.0 dB in every band; RMSE and
   non-line-of-sight cells are reported, not judged.

Nothing is "verified" before step 4 has run on real MATLAB results. A MATLAB comparison is a
model-to-model check, not a measurement: it shows two ray tracers agree, not that either matches
Baghdad.
