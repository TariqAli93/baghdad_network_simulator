# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261126T142746Z

Pipeline test. **Not a finding about Baghdad**: provisional development area (98.8 % placeholder heights, about a third of the built area missing from OSM) and unapproved radio parameters.

- Sites (1): site-001 on way/1178630153, roof 3 m (estimated), antenna 6 m at (12, -427)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile preview: 25 m cells, 1e+08 rays per sector; 808 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 96.3 % | 96.3 % | 12.3 dB | 4.8 Mbit/s | 83 Mbit/s | 92 % | none | sites [1] -> 96.3 % (target reached) |
| 5G NR mid-band | 93.2 % | 93.2 % | 11.1 dB | 0.8 Mbit/s | 374 Mbit/s | 86 % | none | sites [1] -> 93.2 % (candidates exhausted) |
| Candidate 6G upper mid-band | 91.0 % | 91.0 % | 9.1 dB | 0.1 Mbit/s | 1216 Mbit/s | 76 % | none | sites [1] -> 91.0 % (candidates exhausted) |
| Candidate 6G 15 GHz | 87.3 % | 87.3 % | 8.8 dB | 0.0 Mbit/s | 1200 Mbit/s | 68 % | none | sites [1] -> 87.3 % (candidates exhausted) |
| 5G NR mmWave | 80.8 % | 80.8 % | 7.7 dB | 0.0 Mbit/s | 1060 Mbit/s | 57 % | none | sites [1] -> 80.8 % (candidates exhausted) |

Trace time 114 s for 15 new traces (0 of 15 were cached); total 117 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
