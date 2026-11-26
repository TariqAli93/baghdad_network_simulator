# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Site plan site_plan-tahrir_bab_al_sharqi_v2-osm-preview-20cand-gpu-20261126T120657Z

Greedy heuristic on whole-network SINR coverage; **not a minimum site count**, and not a finding about Baghdad (provisional area, unapproved radio parameters, candidate roofs with placeholder heights).

- 20 candidates (roof ≥ 9 m, ≥ 150 m apart, heights: observed, placeholder), mast 3 m, 3 sectors each.
- Target 95 % of 808 outdoor cells; threshold 0 dB SINR; load 0.5 (sensitivity overrides: {'coverage_threshold': 0.0, 'interference_activity': 0.5}).
- Profile preview, backend gpu. Traces 1 s (0 new, 300 cached); selection 0.3 s.

| Scenario | Sites selected | Coverage after each addition | Stop | Final median SINR | Final 5th-pct rate | Uncovered cells | All candidates on | Sites per km² |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | site-001 | 100.0 % | target reached | 23.4 dB | 46.3 Mbit/s | 0 | 76.2 % | 1.0 |
| 5G NR mid-band | site-001 | 100.0 % | target reached | 22.7 dB | 226.0 Mbit/s | 0 | 77.7 % | 1.0 |
| Candidate 6G upper mid-band | site-001 | 97.9 % | target reached | 18.2 dB | 592.3 Mbit/s | 17 | 79.1 % | 1.0 |
| Candidate 6G 15 GHz | site-001, site-008 | 89.1, 98.9 % | target reached | 8.8 dB | 610.2 Mbit/s | 9 | 79.3 % | 2.0 |
| 5G NR mmWave | site-008, site-001 | 81.7, 96.2 % | target reached | 8.1 dB | 461.9 Mbit/s | 31 | 79.6 % | 2.0 |
