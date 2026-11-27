# Simulation Results · Research Baseline · Estimated Building Heights · Validation Pending

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_study-synthetic_urban-seed42+fp_3d_globfp-standard-1sites-20261127T121824Z

**Simulation Results, not a validated finding about Baghdad**: Synthetic Urban Model 'synthetic_urban' (synthetic-urban-1, baseline scenario, seed 42): 99.4 % of buildings have estimated building heights (modelling assumptions, not measurements); no field observations; validation pending (final-scene convergence, MATLAB comparison).

- Sites (1): site-001 on way/919688856, roof 55 m (observed), antenna 58 m at (-178, -131)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile standard: 10 m cells, 1e+09 rays per sector; 3826 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 100.0 % | 100.0 % | 19.4 dB | 27.7 Mbit/s | 129 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| 5G NR mid-band | 100.0 % | 100.0 % | 18.5 dB | 134.7 Mbit/s | 617 Mbit/s | 93 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band | 99.0 % | 99.0 % | 15.6 dB | 435.6 Mbit/s | 2085 Mbit/s | 66 % | none | sites [1] -> 99.0 % (target reached) |
| Candidate 6G 15 GHz | 97.8 % | 97.8 % | 13.2 dB | 270.5 Mbit/s | 1778 Mbit/s | 48 % | none | sites [1] -> 97.8 % (target reached) |
| 5G NR mmWave | 95.9 % | 95.9 % | 10.3 dB | 89.8 Mbit/s | 1423 Mbit/s | 34 % | none | sites [1] -> 95.9 % (target reached) |

Trace time 1272 s for 15 new traces (0 of 15 were cached); total 1275 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
