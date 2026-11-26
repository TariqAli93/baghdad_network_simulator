# Target-laptop acceptance (closes the Phase 0 gate)

Target: Intel Core i7-13620H (6 P + 4 E cores, 16 threads), 16 GB RAM, Intel UHD Graphics,
Windows 11. **Status: not yet run.** Nothing below is a laptop result until the table at the
end is filled in from an actual run. Development-PC figures (i5-14400F, 32 GB, RTX 3060) are
in `docs/benchmarks.md` and are not a substitute.

## Procedure

1. On AC power, balanced or best-performance power mode, other heavy programs closed.
2. Copy the clean archive (`scripts/make_distribution.py` on the development PC) or clone the
   repository; open PowerShell in the folder.
3. `powershell -ExecutionPolicy Bypass -File .\setup.ps1` — installation (internet the first
   time; LLVM via winget may ask for administrator approval). Record: success, time, any
   prompt.
4. `.\doctor.ps1 -Save` — environment diagnostics; all PASS except optional items (no NVIDIA
   GPU: the GPU line is INFO, which is expected).
5. `powershell -ExecutionPolicy Bypass -File .\benchmark.ps1` — unit and engine tests, cold
   kernel compilation and warm repeat, standard-profile trace time and peak memory, one
   five-band single-site run uncached then cached, JIT retry counts. Results in
   `outputs\acceptance\<time>\summary.json` and logs.
6. Optional, for the sustained-workload and stability part of the gate (about an hour or
   more): `.\benchmark.ps1 -Full` (adds `scripts/poc_benchmark.py gate stability sustained`).
7. In the application (`.\run.ps1`): start a preview run with one new site, cancel it during
   tracing, confirm the page shows "Cancelled" and that rerunning resumes from the cache;
   open every page; export a report.

## Pass criteria (proposed; supervisor to confirm)

| Item | Criterion |
|---|---|
| Installation | `setup.ps1` completes; doctor has no FAIL |
| Engine tests | 6 passed |
| Peak memory | worker peak commit below 8 GB (2 GB under a 10 GB cap) |
| Retries | first-compile retries converge (no step fails after 8 attempts) |
| Cached run | the second single-site run traces nothing |
| Cancellation | stops within one batch; resume works |
| Time budget | standard trace time × planned traces fits the time the student can spend (supervisor decides) |

## Recorded results (fill in from the laptop; keep development-PC numbers out of this table)

| Item | Result | Date |
|---|---|---|
| setup.ps1 | | |
| doctor (FAIL / WARN count) | | |
| unit tests / engine tests | | |
| cold compile + first preview trace / warm repeat | | |
| standard trace (sector), busy cores, peak commit | | |
| single-site preview run uncached / cached | | |
| JIT error lines (retries) | | |
| cancellation and resume | | |
| sustained (90 maps) and stability (20 processes), if run | | |
