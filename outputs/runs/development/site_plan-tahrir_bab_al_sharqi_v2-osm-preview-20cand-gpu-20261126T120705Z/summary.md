# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Site plan site_plan-tahrir_bab_al_sharqi_v2-osm-preview-20cand-gpu-20261126T120705Z

Greedy heuristic on whole-network SINR coverage; **not a minimum site count**, and not a finding about Baghdad (provisional area, unapproved radio parameters, candidate roofs with placeholder heights).

- 20 candidates (roof ≥ 9 m, ≥ 150 m apart, heights: observed, placeholder), mast 3 m, 3 sectors each.
- Target 95 % of 808 outdoor cells; threshold 3 dB SINR; load 0.5 (sensitivity overrides: {'coverage_threshold': 3.0, 'interference_activity': 0.5}).
- Profile preview, backend gpu. Traces 1 s (0 new, 300 cached); selection 0.5 s.

| Scenario | Sites selected | Coverage after each addition | Stop | Final median SINR | Final 5th-pct rate | Uncovered cells | All candidates on | Sites per km² |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | site-003 | 100.0 % | target reached | 21.0 dB | 44.6 Mbit/s | 0 | 46.8 % | 1.0 |
| 5G NR mid-band | site-001 | 99.9 % | target reached | 22.7 dB | 226.0 Mbit/s | 1 | 49.4 % | 1.0 |
| Candidate 6G upper mid-band | site-001, site-002 | 94.3, 97.0 % | target reached | 9.3 dB | 660.4 Mbit/s | 24 | 50.5 % | 2.0 |
| Candidate 6G 15 GHz | site-008, site-001 | 83.8, 93.3 % | no candidate raises coverage | 8.8 dB | 610.2 Mbit/s | 54 | 50.6 % | 2.0 |
| 5G NR mmWave | site-002, site-001, site-006 | 77.1, 92.3, 92.6 % | no candidate raises coverage | 8.3 dB | 574.2 Mbit/s | 60 | 51.1 % | 3.0 |
