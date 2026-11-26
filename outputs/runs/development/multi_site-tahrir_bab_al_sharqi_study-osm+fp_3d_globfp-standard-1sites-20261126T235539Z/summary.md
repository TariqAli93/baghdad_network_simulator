# Preliminary Simulation · Custom Experiment · Incomplete data · Validation Pending

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_study-osm+fp_3d_globfp-standard-1sites-20261126T235539Z

**Preliminary Simulation, not a validated finding about Baghdad**: 99.4 % of buildings have placeholder heights; observation worklist incomplete: 0 of 81 buildings observed, 0 rows matching no building; differs from the research baseline: GPU backend (numerical limits: docs/validation.md §7); validation pending (final-scene convergence, MATLAB comparison).

- Sites (1): site-001 on way/919688856, roof 55 m (observed), antenna 58 m at (-178, -131)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile standard: 10 m cells, 1e+09 rays per sector; 3826 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 100.0 % | 100.0 % | 20.0 dB | 27.1 Mbit/s | 133 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| 5G NR mid-band | 100.0 % | 100.0 % | 19.0 dB | 134.7 Mbit/s | 632 Mbit/s | 93 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band | 99.8 % | 99.8 % | 15.6 dB | 451.9 Mbit/s | 2092 Mbit/s | 66 % | none | sites [1] -> 99.8 % (target reached) |
| Candidate 6G 15 GHz | 98.4 % | 98.4 % | 13.4 dB | 321.3 Mbit/s | 1803 Mbit/s | 48 % | none | sites [1] -> 98.4 % (target reached) |
| 5G NR mmWave | 96.4 % | 96.4 % | 10.6 dB | 111.5 Mbit/s | 1454 Mbit/s | 34 % | none | sites [1] -> 96.4 % (target reached) |

Trace time 143 s for 15 new traces (0 of 15 were cached); total 149 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
