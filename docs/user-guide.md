# User guide

For the student operating the Baghdad Network Simulator on Windows. Installation is in the
README; this guide follows a typical session. Every result carries its scientific
classification: configuration (Research Baseline, Custom Experiment or Sensitivity Analysis),
dataset (complete or incomplete) and validation. Today every result is a **Preliminary
Simulation** (incomplete building data, validation pending): it shows how the method behaves,
not validated findings about Baghdad (`docs/approval-record.md`).

## 1. Install and check (once)

```
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\doctor.ps1
```

`setup.ps1` needs the internet the first time (Python 3.13 and about 1 GB of packages) and
LLVM 18.1.8 (installing it through winget may ask for administrator approval; setup prints
the command and does not install it itself). Afterwards everything works offline. `doctor`
prints PASS / WARN / FAIL per check; fix every FAIL before simulating. Without an NVIDIA GPU
the GPU line says INFO: that is expected, the CPU does everything.

## 2. Start the application

```
.\run.ps1
```

The browser opens http://localhost:8501. Stop the application with Ctrl+C in the PowerShell
window. The sidebar groups the ten pages: Project (Overview, Study area, Radio scenarios),
Simulation (Run simulation, Coverage analysis, Comparison, Site planning), Evidence
(Validation, Reports and exports, 6G roadmap).

## 3. Look at existing results

- **Overview**: status per phase, profiles, the latest run.
- **Study area**: buildings coloured by height provenance (observed / estimated /
  placeholder) or height, the data-quality verdict, dataset evaluations.
- **Coverage analysis**: pick a saved run, a scenario and a layer (path gain, received power,
  SINR, rate, coverage, serving site, interference). Grey cells are buildings (indoor, never
  counted). Statistics and a CDF are beside the map.
- **Comparison**: the five scenarios of one run; several runs side by side (a yellow warning
  names every configuration difference: such runs are not the same experiment); site counts;
  the 3GPP check; sensitivity; limitations.

## 4. Configure and run a simulation

On **Run simulation**:

1. Choose area, dataset variant, profile (preview for exploring, standard for final runs) and
   mode. Research mode refuses until the supervisor has approved the area, the radio
   parameters and the profile.
2. Choose the backend: CPU (production), Auto (GPU if one works) or GPU (development only).
3. Choose the sites: the tallest buildings with an observed height (number, minimum height,
   spacing) or named buildings (`way/...` ids from the Study area page).
4. Press **Check sites and workload**: the sites, how many traces are already cached and how
   many are new, and an estimate from traces measured on this machine (or none if nothing
   comparable was measured yet).
5. Press **Start run**. Progress shows traced / to trace. **Cancel** stops the running
   worker; finished batches stay cached, so starting the same run again resumes.

One run at a time. A run that is all cached takes seconds. First traces of a new kind of job
compile kernels and can crash and retry once or twice on Windows: this is handled
automatically (only clean results are kept).

From the command line the same runs are `scripts/run_multi_site.py`; site planning is
`scripts/plan_sites.py` (see the README).

## 5. Site planning

**Site planning** shows saved plans: the sites chosen in order, coverage after each, why the
search stopped ("target reached", "no candidate raises coverage" = a local stall, not proof
the target is unreachable, "candidates exhausted"), uncovered areas and the final map. Below,
re-evaluate any selection and rerun the greedy with other threshold, load or target values;
these sliders are sensitivity checks, not approved values. Nothing is traced there.

## 6. Export

**Reports and exports**: configuration, approval status, provenance, statistics, figures
(PNG), CSV files (one row per receiver cell with coordinates), manifest and summary (JSON), the
whole run folder as ZIP, and a printable HTML report (open it in the browser and print to
PDF). Every export keeps the run's label and the limitations.

## 7. Roadmap

**6G roadmap** separates verified facts (with their source IDs), provisional results read from
saved runs, and open questions. Write your own recommendations per stage and press Save; they
are stored in `outputs/roadmap/student_recommendations.json` and never generated.

## 8. When something goes wrong

| Symptom | What to do |
|---|---|
| "This run cannot start: …" | The message names the reason (research mode, missing dataset, no site satisfies the rule). |
| Snapshot SHA-256 mismatch (doctor) | Git converted line endings; check out `data/raw` again (`.gitattributes` prevents it in this repository). |
| A run says "Failed" | Open its log on the Run page; Python errors stop immediately, native crashes are retried up to 8 times. |
| Traces much slower than the estimate | Workers opt out of Windows power throttling; keep the laptop on AC power and in a performance power mode (`docs/benchmarks.md` §11). |
| Port 8501 in use | `.\run.ps1 -Port 8502`. |
| A stale run blocks "Start run" | The app checks that the process is alive; if Windows reused the process id, restart the application. |
