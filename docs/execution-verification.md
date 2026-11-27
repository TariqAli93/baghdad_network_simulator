# Execution verification (2026-11-27)

Check that technically valid simulations execute regardless of scientific standing, after the
legacy approval restrictions were removed (`scripts/run_multi_site.py`, real tracing, one rooftop
site `way/919688856`, all five bands). The run folders stay local under
`outputs/runs/development/` (listed in `.gitignore`, shown in the application); they are not part
of the repository.

| Run ID | Dataset | Profile | Backend | Values | Trace / total time | Classification |
|---|---|---|---|---|---|---|
| `multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261126T235144Z` | `tahrir_bab_al_sharqi_v2/osm` (provisional area) | preview (25 m, 1e8) | CPU | research baseline | 151.9 s / 155.3 s (15 traces) | Preliminary Simulation · Custom Experiment (preview profile) · Incomplete data · Validation Pending |
| `multi_site-tahrir_bab_al_sharqi_study-osm+fp_3d_globfp-preview-1sites-20261126T235306Z` | `tahrir_bab_al_sharqi_study/osm+fp_3d_globfp` (0 of 81 observations) | preview | GPU | tx_power_dbm = 43 | 23.9 s / 28.1 s (15 traces) | Preliminary Simulation · Custom Experiment (preview, GPU, 43 dBm) · Incomplete data · Validation Pending |
| `multi_site-tahrir_bab_al_sharqi_study-osm+fp_3d_globfp-standard-1sites-20261126T235539Z` | study dataset | standard (10 m, 1e9) | GPU | research baseline; old `--mode research` flag | 142.7 s / 148.8 s (15 traces) | Preliminary Simulation · Custom Experiment (GPU) · Incomplete data · Validation Pending |

Results (coverage at SINR ≥ −10 dB / median SINR / median Shannon rate):

| Band | v2, preview, CPU | study, preview, GPU, 43 dBm | study, standard, GPU |
|---|---|---|---|
| 4G LTE 1.8 GHz | 100.0 % / 21.4 dB / 142 Mbit/s | 100.0 % / 17.9 dB / 120 Mbit/s | 100.0 % / 20.0 dB / 133 Mbit/s |
| 5G NR 3.5 GHz | 100.0 % / 21.4 dB / 713 Mbit/s | 100.0 % / 18.2 dB / 605 Mbit/s | 100.0 % / 19.0 dB / 632 Mbit/s |
| Candidate 6G 8 GHz | 99.8 % / 19.8 dB / 2643 Mbit/s | 100.0 % / 16.8 dB / 2246 Mbit/s | 99.8 % / 15.6 dB / 2092 Mbit/s |
| Candidate 6G 15 GHz | 99.6 % / 18.0 dB / 2397 Mbit/s | 99.8 % / 14.5 dB / 1944 Mbit/s | 98.4 % / 13.4 dB / 1803 Mbit/s |
| 5G NR 28 GHz | 99.5 % / 14.9 dB / 1996 Mbit/s | 99.0 % / 11.7 dB / 1588 Mbit/s | 96.4 % / 10.6 dB / 1454 Mbit/s |

These are preliminary simulations (one site; placeholder heights for 99 % of buildings;
validation pending), recorded only to show that execution works. They are not findings about
Baghdad. Before the change, the v2 run stopped with "Research mode needs an approved study
district". Technical errors still stop a run (unit tests: invalid value, unknown area, missing
scene, unconverged profile, unavailable GPU).

## Through the application (Start button)

| Run ID | Set in the UI | Execution | Classification |
|---|---|---|---|
| `multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261127T001247Z` | area `tahrir_bab_al_sharqi_v2` (variant `osm`, the configured default), preview, CPU, 1 site, transmit power 43 dBm | Ready → Running ("all traces cached; computing radio results") → Completed; 15 of 15 traces from the cache, 0 s tracing, 2.1 s total; folder saved (manifest, summary, arrays, figures, CSV) | Preliminary Simulation · Custom Experiment (preview profile; tx_power_dbm = 43.0) · Incomplete data · Validation Pending |

Coverage / median SINR / median Shannon rate: LTE 100.0 % / 21.4 dB / 142 Mbit/s; NR 3.5 GHz
100.0 % / 21.2 dB / 706 Mbit/s; 8 GHz 99.6 % / 18.8 dB / 2509 Mbit/s; 15 GHz 99.5 % / 16.5 dB /
2211 Mbit/s; 28 GHz 99.4 % / 12.3 dB / 1670 Mbit/s. Shown on Coverage analysis with its
classification banner; the Reports page offers the HTML report (generated: 477 kB, four
figures, classification and the custom value). Local only (`.gitignore`).
