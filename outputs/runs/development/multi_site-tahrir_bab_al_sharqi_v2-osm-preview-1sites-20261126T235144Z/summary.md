# Preliminary Simulation · Custom Experiment · Incomplete data · Validation Pending

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261126T235144Z

**Preliminary Simulation, not a validated finding about Baghdad**: tahrir_bab_al_sharqi_v2 is a provisional study area, not the study district: results do not describe the study district's research dataset; the area is a provisional study area, not the study district; the area has not been approved by the supervisor; 98.8 % of buildings have placeholder heights; differs from the research baseline: preview profile (25 m, 1e+08 rays); validation pending (final-scene convergence, MATLAB comparison).

- Sites (1): site-001 on way/919688856, roof 55 m (observed), antenna 58 m at (-178, -131)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile preview: 25 m cells, 1e+08 rays per sector; 808 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 100.0 % | 100.0 % | 21.4 dB | 30.8 Mbit/s | 142 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| 5G NR mid-band | 100.0 % | 100.0 % | 21.4 dB | 153.7 Mbit/s | 713 Mbit/s | 99 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band | 99.8 % | 99.8 % | 19.8 dB | 603.3 Mbit/s | 2643 Mbit/s | 79 % | none | sites [1] -> 99.8 % (target reached) |
| Candidate 6G 15 GHz | 99.6 % | 99.6 % | 18.0 dB | 564.0 Mbit/s | 2397 Mbit/s | 51 % | none | sites [1] -> 99.6 % (target reached) |
| 5G NR mmWave | 99.5 % | 99.5 % | 14.9 dB | 490.5 Mbit/s | 1996 Mbit/s | 35 % | none | sites [1] -> 99.5 % (target reached) |

Trace time 152 s for 15 new traces (0 of 15 were cached); total 155 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
