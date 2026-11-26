# Preliminary Simulation · Custom Experiment · Incomplete data · Validation Pending

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_study-osm+fp_3d_globfp-preview-1sites-20261126T235306Z

**Preliminary Simulation, not a validated finding about Baghdad**: 99.4 % of buildings have placeholder heights; observation worklist incomplete: 0 of 81 buildings observed, 0 rows matching no building; differs from the research baseline: preview profile (25 m, 1e+08 rays); GPU backend (numerical limits: docs/validation.md §7); tx_power_dbm = 43.0; validation pending (final-scene convergence, MATLAB comparison).

- Sites (1): site-001 on way/919688856, roof 55 m (observed), antenna 58 m at (-178, -131)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile preview: 25 m cells, 1e+08 rays per sector; 405 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 100.0 % | 100.0 % | 17.9 dB | 28.1 Mbit/s | 120 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| 5G NR mid-band | 100.0 % | 100.0 % | 18.2 dB | 134.8 Mbit/s | 605 Mbit/s | 97 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band | 100.0 % | 100.0 % | 16.8 dB | 506.7 Mbit/s | 2246 Mbit/s | 75 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G 15 GHz | 99.8 % | 99.8 % | 14.5 dB | 456.5 Mbit/s | 1944 Mbit/s | 50 % | none | sites [1] -> 99.8 % (target reached) |
| 5G NR mmWave | 99.0 % | 99.0 % | 11.7 dB | 233.4 Mbit/s | 1588 Mbit/s | 29 % | none | sites [1] -> 99.0 % (target reached) |

Trace time 24 s for 15 new traces (0 of 15 were cached); total 28 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
