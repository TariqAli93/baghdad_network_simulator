# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Site plan site_plan-tahrir_bab_al_sharqi_v2-osm-preview-20cand-gpu-20261126T120641Z

Greedy heuristic on whole-network SINR coverage; **not a minimum site count**, and not a finding about Baghdad (provisional area, unapproved radio parameters, candidate roofs with placeholder heights).

- 20 candidates (roof ≥ 9 m, ≥ 150 m apart, heights: observed, placeholder), mast 3 m, 3 sectors each.
- Target 95 % of 808 outdoor cells; threshold -10 dB SINR; load 1.
- Profile preview, backend gpu. Traces 1 s (0 new, 300 cached); selection 0.3 s.

| Scenario | Sites selected | Coverage after each addition | Stop | Final median SINR | Final 5th-pct rate | Uncovered cells | All candidates on | Sites per km² |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | site-001 | 100.0 % | target reached | 20.4 dB | 31.6 Mbit/s | 0 | 100.0 % | 1.0 |
| 5G NR mid-band | site-001 | 100.0 % | target reached | 20.0 dB | 156.2 Mbit/s | 0 | 100.0 % | 1.0 |
| Candidate 6G upper mid-band | site-002 | 100.0 % | target reached | 16.6 dB | 359.8 Mbit/s | 0 | 100.0 % | 1.0 |
| Candidate 6G 15 GHz | site-001 | 98.8 % | target reached | 13.9 dB | 190.4 Mbit/s | 10 | 100.0 % | 1.0 |
| 5G NR mmWave | site-001, site-011 | 93.1, 99.8 % | target reached | 5.0 dB | 239.2 Mbit/s | 2 | 100.0 % | 2.0 |
