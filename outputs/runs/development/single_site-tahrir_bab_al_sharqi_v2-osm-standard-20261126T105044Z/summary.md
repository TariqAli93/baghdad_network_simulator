# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Single-site experiment single_site-tahrir_bab_al_sharqi_v2-osm-standard-20261126T105044Z

Pipeline test and teaching aid. **Not a finding about Baghdad**: the area is a provisional development area (98.8 % of buildings have placeholder heights) and the radio parameters are unapproved proposals.

- Site: way/919688856, roof 55 m (observed), antenna 58 m above ground at (-178, -131) m; 3 sector(s), pattern tr38901.
- Grid: 100 x 100 cells of 10 m at 1.5 m; 6153 outdoor cells. Profile standard: 1e+09 rays per sector.
- Clear sky (gas attenuation only). Coverage: snr_db at or above -10.

| Scenario | Peak EIRP | Noise | Reached (propagation only) | Median received power | Coverage | Median SINR | 5th-percentile Shannon rate | Median Shannon rate |
|---|---|---|---|---|---|---|---|---|
| 4G LTE (1.8 GHz, 20 MHz) | 54 dBm | -92.0 dBm | 100.0 % | -41.5 dBm | 99.9 % | 19.9 dB | 31.4 Mbit/s | 132 Mbit/s |
| 5G NR mid-band (3.5 GHz, 100 MHz) | 54 dBm | -85.0 dBm | 100.0 % | -47.4 dBm | 99.8 % | 19.2 dB | 145.9 Mbit/s | 639 Mbit/s |
| Candidate 6G upper mid-band (8 GHz, 400 MHz) | 54 dBm | -79.0 dBm | 100.0 % | -54.8 dBm | 98.6 % | 15.2 dB | 325.7 Mbit/s | 2033 Mbit/s |
| Candidate 6G 15 GHz (15 GHz, 400 MHz) | 54 dBm | -79.0 dBm | 100.0 % | -60.4 dBm | 96.1 % | 12.6 dB | 84.1 Mbit/s | 1709 Mbit/s |
| 5G NR mmWave (28 GHz, 400 MHz) | 54 dBm | -79.0 dBm | 100.0 % | -65.9 dBm | 89.1 % | 9.7 dB | 14.9 Mbit/s | 1344 Mbit/s |

Trace time 1832 s (cached maps are not re-traced); total 1834 s; largest worker peak commit 0.862 GB.

Shannon rates are theoretical upper bounds for one user with the whole carrier, not expected user throughput.
