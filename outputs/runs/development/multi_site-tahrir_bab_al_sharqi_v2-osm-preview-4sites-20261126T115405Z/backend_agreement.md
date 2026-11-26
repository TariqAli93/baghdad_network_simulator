# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Backend agreement: cpu (multi_site-tahrir_bab_al_sharqi_v2-osm-preview-4sites-20261126T113044Z) vs gpu (multi_site-tahrir_bab_al_sharqi_v2-osm-preview-4sites-20261126T115405Z)

Same sites, grid, profile, mechanisms, seeds and radio inputs (checked); only the ray-tracing backend differs. Outdoor cells: 808. Weak cells: best-sector path gain below -140 dB.

| Scenario | Path gain |Δ| median / p95 / max | Weak cells (median |Δ|) | Reached by one only | Coverage class changed | SINR |Δ| median / p95 | 5th-pct rate A / B | Median rate A / B |
|---|---|---|---|---|---|---|---|
| 4G LTE | 0.03 / 0.45 / 2.8 dB | 0 (—) | 0 | 0 | 0.16 / 1.11 dB | 14.7 / 14.8 Mbit/s | 34 / 34 Mbit/s |
| 5G NR mid-band | 0.02 / 0.41 / 2.8 dB | 0 (—) | 0 | 0 | 0.14 / 1.06 dB | 74.9 / 75.0 Mbit/s | 180 / 182 Mbit/s |
| Candidate 6G upper mid-band | 0.01 / 0.39 / 3.2 dB | 0 (—) | 0 | 0 | 0.11 / 0.94 dB | 302.8 / 301.6 Mbit/s | 750 / 759 Mbit/s |
| Candidate 6G 15 GHz | 0.01 / 0.33 / 3.6 dB | 0 (—) | 0 | 0 | 0.09 / 0.86 dB | 297.5 / 300.1 Mbit/s | 771 / 770 Mbit/s |
| 5G NR mmWave | 0.01 / 0.28 / 4.0 dB | 1 (0.05 dB) | 0 | 0 | 0.06 / 0.75 dB | 290.5 / 294.0 Mbit/s | 751 / 744 Mbit/s |

Differences come from the randomly sampled diffraction and floating-point order; line of sight and reflections are deterministic on both backends.
