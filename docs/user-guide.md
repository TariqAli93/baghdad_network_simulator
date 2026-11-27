# User guide

For the student using the Baghdad Network Simulator on Windows. Arabic version:
`docs/user-guide.ar.md`. For the research steps (study area to MATLAB comparison) see
`docs/research-guide.md`.

The application computes, by ray tracing, the coverage, signal quality (SINR) and data rate of
five network scenarios over a 1 km² district of central Baghdad: 4G at 1.8 GHz, 5G at 3.5 and
28 GHz, and candidate 6G at 8 and 15 GHz. **Its results are simulations, not measurements**:
building footprints are real, but almost all building heights come from the Synthetic Urban
Model (estimates), and no field measurement exists. Every result states its classification
(section 6).

## 1. What you need

- Windows 10 or 11 (64-bit). 16 GB of memory is recommended; about 5 GB of free disk space.
- Internet access for the first installation only. Afterwards the application works offline.
- Optional: an NVIDIA graphics card. Without one, everything runs on the processor (CPU).

Whether the application runs well on your own laptop is not yet known: it was developed and
tested on another computer. Run `Laptop benchmark.cmd` once on your laptop (section 7) and give
the result to your supervisor.

## 2. Install (once)

1. If Windows marks the downloaded ZIP file as blocked: right-click it → **Properties** → tick
   **Unblock** → **OK**.
2. Extract the ZIP to a short folder whose path has **no Arabic letters**, for example
   `C:\BaghdadSimulator`. (Some of the 3-D software does not accept such paths.)
3. Open the folder `baghdad-network-simulator` and double-click **`1 - Install.cmd`**.
4. If the window asks to install **uv** (the Python package manager) or **LLVM** (used by the
   ray tracer), type `Y` and press Enter. For LLVM, Windows may ask for administrator
   permission: choose **Yes**.
5. The installation downloads Python and its packages (about 1 GB), builds the five datasets
   from the included map data and checks the computer. Wait until it says
   **Setup complete**, then press a key. If a line says **FAIL**, see section 8.

Running `1 - Install.cmd` again is safe: finished steps are kept.

## 3. Start and stop

- **Start:** double-click **`2 - Start Baghdad Network Simulator.cmd`**. The application opens in
  your web browser at `http://localhost:8501`. No internet is needed.
- **Keep the black window open** while you work. **Close it** to stop the application.
- If the application is already running, the same file just opens it in the browser.
- The application is reachable only from this computer, not from other computers on the network.

## 4. Language

The switch at the top of every page changes between **العربية** and **English**. Your choice is
remembered on this computer, also after a restart. Numbers, units, identifiers and the files the
simulations write (CSV, JSON, figures) stay in English; saved run notes are English records and
are marked as such.

## 5. The pages

| Page | What you do there |
|---|---|
| Dashboard | What the tool does, the latest results, the five scenarios compared, the scientific status and the next step. **Start New Simulation** is the main button. |
| Study Area | The district, its buildings and where each building height comes from (observed, estimated, synthetic). |
| Run Simulation | Choose area, dataset, profile, backend and sites; check the workload; start, follow and cancel runs. |
| Coverage Analysis | Maps of a saved run: signal quality (SINR), received power, data rate, covered cells, serving site, interference, path gain; statistics beside the map. |
| Network Comparison | The five scenarios of one run; several runs side by side; site counts; 3GPP model check; sensitivity; limitations. |
| Site Planning | Saved site plans and re-evaluation of any selection from saved results (nothing is traced). |
| Reports | Printable report (Arabic or English), configuration, statistics, figures, CSV/JSON/ZIP downloads. |
| Research Details → Radio Scenarios | The five scenarios and every radio parameter with its source. |
| Research Details → Validation | What has been checked: analytical checks, 3GPP model comparison, MATLAB package, convergence. |
| Research Details → 6G Roadmap | Verified evidence, results from saved runs, open questions, and your own recommendations (saved when you press Save). |

Showing results never re-runs a simulation. Only one simulation runs at a time.

## 6. What the labels on results mean

Every result carries a coloured banner with its classification:

| Label | Meaning |
|---|---|
| Simulation Results | Research-baseline settings on estimated (synthetic) building heights: a simulation under stated assumptions, not a validated finding. |
| Custom Experiment | Some settings differ from the research baseline (for example the preview profile or the GPU); the banner lists them. |
| Sensitivity Analysis | Only the coverage threshold, target, load or rain differ from the baseline. |
| Preliminary Simulation | Placeholder building heights or an unrecorded configuration (older runs): useful to explore the method only. |
| Validated Research Results | Not reached yet: needs complete measured building data, the final convergence check and the MATLAB comparison. |

"Validation Pending" means the numerical checks of the final study are not done yet. **No result
in this package is a measurement or a validated research result.**

## 7. Diagnostics and benchmark

- **`Diagnose problems.cmd`** checks Python, the packages, LLVM, memory, disk, the datasets, the
  package files (against `SHA256SUMS.txt`) and a short ray-tracing test. Each line is PASS,
  WARN or FAIL. It saves a report in `outputs\acceptance\` that you can send to your supervisor.
- **`Laptop benchmark.cmd`** measures run times on your laptop (connect the charger; it takes a
  while). Results go to `outputs\acceptance\<time>\`; see `docs/laptop-acceptance.md`.

## 8. Troubleshooting

| What you see | What to do |
|---|---|
| "Windows protected your PC" or a security warning when double-clicking | **More info → Run anyway** (or **Run**). Unblocking the ZIP before extracting (section 2) avoids it. |
| Installation: "uv is not installed" / "LLVM ... was not found" | Run `1 - Install.cmd` again and answer `Y`. Without winget, run the command it prints in a PowerShell window, then install again. |
| Installation: "uv sync failed" | The first installation needs internet. Connect and run `1 - Install.cmd` again. |
| The browser did not open | Open `http://localhost:8501` yourself (the black window shows the address). |
| "This site can't be reached" | The black window was closed. Start the application again. |
| The address shows another port (8502 …) | Port 8501 is used by another program; the application took the next free one. |
| A simulation shows "Failed" | Open **Log** under the run on the Run Simulation page. The first run of a new kind can be slow and retry automatically on Windows; that is expected. |
| Simulations are much slower than expected | Connect the charger and choose a performance power mode; keep the laptop awake. |
| "Start run" stays blocked although nothing runs | Close the black window and start the application again. |
| Diagnostics: "package files … changed" | A delivered file was edited. If you did not mean to, extract the package again. |
| Anything else | Run `Diagnose problems.cmd` and send the saved report to your supervisor. |

## 9. Where your files are

- Simulation results: `outputs\runs\development\<run>\` (manifest, statistics, maps, CSV). The
  package comes with demonstration results: one research-baseline run on the Synthetic Urban Model
  (study district, one site, CPU, standard profile; "Simulation Results") and older preliminary
  runs on the development area. Their per-cell CSV files are not included.
- Downloaded reports and exports: your browser's Downloads folder.
- Your 6G roadmap recommendations: `outputs\roadmap\student_recommendations.json`.
- Your language choice: `outputs\app_state\preferences.json`.

To remove the application, delete its folder. uv and LLVM can be removed in Windows
**Settings → Apps**.
