# Custom Experiment · Estimated Building Heights · Validation Pending

## Workspace simulation multi_site-tahrir_bab_al_sharqi_study-synthetic_urban-seed42+fp_3d_globfp-preview-2sites-ws-20261127T150723Z

Experiment: Verification: 5G and candidate 6G at 100 MHz (exp-20261127T150425-verification-5g-and-candidate-6g-a098). Placement: Manual placement. Deviations: preview profile (25 m, 1e+08 rays); S1 mechanical_downtilt_deg = 6; S2 tx_power_dbm = 43; carrier c6g_8000: 8 GHz / 100 MHz (preset 8 GHz / 400 MHz).

- Stations (2): S1 rooftop on way/919688856 (roof 55 m), antenna 58 m at (-178, -131), 46 dBm, 3 sector(s) 0/120/240°, tilt 6°; S2 rooftop on 3d_globfp/rec/696321 (roof 12 m), antenna 15 m at (199, -86), 43 dBm, 3 sector(s) 0/120/240°, tilt 10°
- Profile preview: 25 m cells, 1e+08 rays per sector; 405 outdoor cells; backend CPU.

| Carrier | Coverage | Median SINR | 5th-pct rate | Median rate | Mapped 5th-pct rate | Interference-limited | Greedy (SINR) |
|---|---|---|---|---|---|---|---|
| 5G NR mid-band 3.5 GHz / 100 MHz | 100.0 % | 13.9 dB | 97.6 Mbit/s | 469 Mbit/s | 58.5 Mbit/s | 100 % | stations [1] -> 100.0 % (target reached) |
| Candidate 6G upper mid-band 8 GHz / 100 MHz (custom) | 100.0 % | 14.6 dB | 100.1 Mbit/s | 489 Mbit/s | 60.1 Mbit/s | 97 % | stations [1] -> 100.0 % (target reached) |

Trace time 172 s for 12 new traces (0 of 12 were cached); total 173 s.

Shannon rates are theoretical upper bounds for one user with the whole carrier. Candidate 6G carriers are research assumptions, not finalised standards; their rate mapping is an NR-based approximation. The greedy result is a heuristic over these stations only.
