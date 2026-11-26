# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_v2-osm-preview-4sites-20261126T121714Z

Pipeline test. **Not a finding about Baghdad**: provisional development area (98.8 % placeholder heights, about a third of the built area missing from OSM) and unapproved radio parameters.

- Sites (4): site-001 on way/919688856, roof 55 m (observed), antenna 58 m at (-178, -131); site-002 on way/1154123513, roof 15 m (observed), antenna 18 m at (65, 28); site-003 on way/645196998, roof 12 m (observed), antenna 15 m at (-171, 286); site-004 on way/939812415, roof 10 m (observed), antenna 13 m at (328, 273)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile preview: 25 m cells, 1e+08 rays per sector; 808 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 100.0 % | 100.0 % | 3.4 dB | 14.8 Mbit/s | 34 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| 5G NR mid-band | 100.0 % | 100.0 % | 4.0 dB | 75.0 Mbit/s | 182 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band | 100.0 % | 100.0 % | 4.4 dB | 301.6 Mbit/s | 759 Mbit/s | 100 % | none | sites [2] -> 100.0 % (target reached) |
| Candidate 6G 15 GHz | 99.9 % | 98.8 % | 4.5 dB | 300.1 Mbit/s | 770 Mbit/s | 99 % | none | sites [1] -> 98.8 % (target reached) |
| 5G NR mmWave | 99.6 % | 93.1 % | 4.2 dB | 294.0 Mbit/s | 744 Mbit/s | 94 % | none | sites [1, 2] -> 99.5 % (target reached) |

Trace time 0 s for 0 new traces (60 of 60 were cached); total 20 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
