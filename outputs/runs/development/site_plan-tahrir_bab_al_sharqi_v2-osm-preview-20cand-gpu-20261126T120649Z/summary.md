# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Site plan site_plan-tahrir_bab_al_sharqi_v2-osm-preview-20cand-gpu-20261126T120649Z

Greedy heuristic on whole-network SINR coverage; **not a minimum site count**, and not a finding about Baghdad (provisional area, unapproved radio parameters, candidate roofs with placeholder heights).

- 20 candidates (roof ≥ 9 m, ≥ 150 m apart, heights: observed, placeholder), mast 3 m, 3 sectors each.
- Target 95 % of 808 outdoor cells; threshold 0 dB SINR; load 1 (sensitivity overrides: {'coverage_threshold': 0.0}).
- Profile preview, backend gpu. Traces 1 s (0 new, 300 cached); selection 0.4 s.

| Scenario | Sites selected | Coverage after each addition | Stop | Final median SINR | Final 5th-pct rate | Uncovered cells | All candidates on | Sites per km² |
|---|---|---|---|---|---|---|---|---|
| 4G LTE | site-003 | 100.0 % | target reached | 18.0 dB | 30.2 Mbit/s | 0 | 46.7 % | 1.0 |
| 5G NR mid-band | site-001 | 99.9 % | target reached | 20.0 dB | 156.2 Mbit/s | 1 | 49.3 % | 1.0 |
| Candidate 6G upper mid-band | site-001 | 96.4 % | target reached | 16.2 dB | 463.3 Mbit/s | 29 | 50.2 % | 1.0 |
| Candidate 6G 15 GHz | site-001, site-002 | 88.0, 96.3 % | target reached | 6.3 dB | 413.6 Mbit/s | 30 | 50.5 % | 2.0 |
| 5G NR mmWave | site-008, site-001, site-012 | 80.6, 91.2, 91.3 % | no candidate raises coverage | 5.5 dB | 363.1 Mbit/s | 70 | 51.0 % | 3.0 |
