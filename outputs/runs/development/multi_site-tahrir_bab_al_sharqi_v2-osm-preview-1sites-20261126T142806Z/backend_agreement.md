# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Backend agreement: cpu (multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261126T142746Z) vs gpu (multi_site-tahrir_bab_al_sharqi_v2-osm-preview-1sites-20261126T142806Z)

Same sites, grid, profile, mechanisms, seeds and radio inputs (checked); only the ray-tracing backend differs. Outdoor cells: 808. Weak cells: best-sector path gain below -140 dB.

| Scenario | Path gain |Δ| median / p95 / max | Weak cells (median |Δ|) | Reached by one only | Coverage class changed | SINR |Δ| median / p95 | 5th-pct rate A / B | Median rate A / B |
|---|---|---|---|---|---|---|---|
| 4G LTE | 0.02 / 1.24 / 24.8 dB | 40 (1.33 dB) | 0 | 4 | 0.02 / 0.96 dB | 4.8 / 5.6 Mbit/s | 83 / 83 Mbit/s |
| 5G NR mid-band | 0.01 / 1.13 / 25.2 dB | 47 (1.27 dB) | 0 | 3 | 0.01 / 0.95 dB | 0.8 / 0.9 Mbit/s | 374 / 373 Mbit/s |
| Candidate 6G upper mid-band | 0.01 / 1.10 / 25.8 dB | 54 (1.14 dB) | 0 | 1 | 0.01 / 1.04 dB | 0.1 / 0.1 Mbit/s | 1216 / 1216 Mbit/s |
| Candidate 6G 15 GHz | 0.00 / 1.06 / 26.0 dB | 71 (1.00 dB) | 0 | 2 | 0.01 / 1.03 dB | 0.0 / 0.0 Mbit/s | 1200 / 1200 Mbit/s |
| 5G NR mmWave | 0.00 / 1.03 / 26.1 dB | 98 (0.58 dB) | 0 | 0 | 0.00 / 1.03 dB | 0.0 / 0.0 Mbit/s | 1060 / 1064 Mbit/s |

Differences come from the randomly sampled diffraction and floating-point order; line of sight and reflections are deterministic on both backends.
