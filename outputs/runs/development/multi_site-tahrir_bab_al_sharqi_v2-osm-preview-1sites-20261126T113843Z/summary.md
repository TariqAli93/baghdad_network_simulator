# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Multi-site experiment multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261126T113843Z

Pipeline test. **Not a finding about Baghdad**: provisional development area (98.8 % placeholder heights, about a third of the built area missing from OSM) and unapproved radio parameters.

- Sites (1): site-001 on way/919688856, roof 55 m (observed), antenna 58 m at (-178, -131)
- 3 sectors per site; every sector of every site on one carrier; interference activity 1; co-located sectors interfere.
- Profile preview: 25 m cells, 1e+08 rays per sector; 808 outdoor cells.

| Scenario | Coverage, all sites | Best single site | Median SINR | 5th-pct rate | Median rate | Interference-limited cells | Additions that lowered coverage | Greedy (SINR) |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | 100.0 % | 100.0 % | 20.3 dB | 31.6 Mbit/s | 135 Mbit/s | 100 % | none | sites [1] -> 100.0 % (target reached) |
| 5G NR mid-band | 100.0 % | 100.0 % | 20.0 dB | 154.1 Mbit/s | 666 Mbit/s | 99 % | none | sites [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band | 99.9 % | 99.9 % | 16.2 dB | 459.8 Mbit/s | 2162 Mbit/s | 73 % | none | sites [1] -> 99.9 % (target reached) |
| Candidate 6G 15 GHz | 98.8 % | 98.8 % | 14.0 dB | 184.4 Mbit/s | 1883 Mbit/s | 35 % | none | sites [1] -> 98.8 % (target reached) |
| 5G NR mmWave | 92.9 % | 92.9 % | 11.1 dB | 36.6 Mbit/s | 1519 Mbit/s | 16 % | none | sites [1] -> 92.9 % (candidates exhausted) |

Trace time 0 s for 0 new traces (15 of 15 were cached); total 3 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. The greedy result is a heuristic over these candidates only.
