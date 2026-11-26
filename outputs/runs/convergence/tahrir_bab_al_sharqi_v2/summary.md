# Ray-count convergence: tahrir_bab_al_sharqi_v2

Each value: share of outdoor cells within the given difference from a 1-billion-ray map of the same case, as the 95th percentile of |difference| in dB, and the share of cells the reference reaches but the cheaper map misses.

## 25 m cells (criterion: 95 % within 3.0 dB, at most 2 % missed)

| Scene | Site (antenna height) | Band | 1e+06 rays | 3e+06 rays | 1e+07 rays | 3e+07 rays | 1e+08 rays | 2nd 1e9 map (floor) |
|---|---|---|---|---|---|---|---|---|
| osm | site-001 (58 m) | nr_3500 | 29.53 dB, 8.4 % | 26.13 dB, 3.8 % | 6.87 dB, 0.4 % | 2.41 dB, 0.1 % | 1.45 dB, 0.0 % | 0.65 dB, 0.0 % |
| osm | site-003 (15 m) | nr_3500 | 33.51 dB, 13.1 % | 26.98 dB, 1.4 % | 6.46 dB, 0.0 % | 2.84 dB, 0.0 % | 1.36 dB, 0.0 % | 0.58 dB, 0.0 % |
| osm | site-004 (13 m) | nr_3500 | 28.04 dB, 16.2 % | 15.98 dB, 5.0 % | 9.61 dB, 1.1 % | 3.76 dB, 0.0 % | 1.84 dB, 0.0 % | 0.60 dB, 0.0 % |
| osm | site-001 (58 m) | nr_28000 | 32.12 dB, 8.4 % | 27.78 dB, 3.6 % | 5.44 dB, 0.5 % | 2.48 dB, 0.0 % | 1.45 dB, 0.0 % | 0.70 dB, 0.0 % |
| osm | site-003 (15 m) | nr_28000 | 37.13 dB, 13.1 % | 31.57 dB, 0.9 % | 6.92 dB, 0.0 % | 2.82 dB, 0.0 % | 1.44 dB, 0.0 % | 0.56 dB, 0.0 % |
| osm | site-004 (13 m) | nr_28000 | 34.59 dB, 16.0 % | 20.48 dB, 5.0 % | 10.79 dB, 1.1 % | 4.21 dB, 0.0 % | 1.71 dB, 0.0 % | 0.60 dB, 0.0 % |
| mixed_1_to_8-seed1 | site-001 (58 m) | nr_3500 | 23.50 dB, 7.8 % | 19.76 dB, 2.7 % | 16.12 dB, 0.1 % | 4.34 dB, 0.0 % | 2.87 dB, 0.0 % | 1.01 dB, 0.0 % |
| mixed_1_to_8-seed1 | site-001 (58 m) | nr_28000 | 24.03 dB, 7.8 % | 27.30 dB, 2.0 % | 14.46 dB, 0.0 % | 4.10 dB, 0.0 % | 2.13 dB, 0.0 % | 0.96 dB, 0.0 % |

Smallest tested ray count meeting the criterion in every case: 1e+08.

## 10 m cells (criterion: 95 % within 2.0 dB, at most 1 % missed)

| Scene | Site (antenna height) | Band | 1e+06 rays | 3e+06 rays | 1e+07 rays | 3e+07 rays | 1e+08 rays | 2nd 1e9 map (floor) |
|---|---|---|---|---|---|---|---|---|
| osm | site-001 (58 m) | nr_3500 | 14.34 dB, 22.1 % | 21.62 dB, 16.3 % | 25.63 dB, 8.0 % | 23.82 dB, 2.1 % | 4.04 dB, 0.4 % | 1.55 dB, 0.0 % |
| osm | site-003 (15 m) | nr_3500 | 30.11 dB, 46.5 % | 30.79 dB, 22.8 % | 28.17 dB, 4.3 % | 11.93 dB, 0.3 % | 3.85 dB, 0.0 % | 1.46 dB, 0.0 % |
| osm | site-004 (13 m) | nr_3500 | 28.57 dB, 37.8 % | 20.94 dB, 23.0 % | 16.36 dB, 11.9 % | 10.75 dB, 2.8 % | 4.37 dB, 0.5 % | 1.56 dB, 0.0 % |
| osm | site-001 (58 m) | nr_28000 | 18.20 dB, 22.1 % | 24.85 dB, 16.3 % | 28.30 dB, 8.0 % | 26.17 dB, 2.0 % | 4.11 dB, 0.4 % | 1.59 dB, 0.0 % |
| osm | site-003 (15 m) | nr_28000 | 34.86 dB, 46.5 % | 35.27 dB, 22.3 % | 32.14 dB, 4.3 % | 14.04 dB, 0.3 % | 3.97 dB, 0.0 % | 1.43 dB, 0.0 % |
| osm | site-004 (13 m) | nr_28000 | 34.07 dB, 37.5 % | 25.20 dB, 23.0 % | 19.41 dB, 11.9 % | 12.06 dB, 2.8 % | 4.73 dB, 0.5 % | 1.65 dB, 0.0 % |
| mixed_1_to_8-seed1 | site-001 (58 m) | nr_3500 | 26.87 dB, 17.3 % | 23.74 dB, 12.3 % | 22.35 dB, 6.4 % | 22.01 dB, 1.7 % | 5.19 dB, 0.2 % | 2.02 dB, 0.0 % |
| mixed_1_to_8-seed1 | site-001 (58 m) | nr_28000 | 29.47 dB, 17.5 % | 26.58 dB, 12.5 % | 25.22 dB, 6.4 % | 24.47 dB, 1.9 % | 4.56 dB, 0.2 % | 1.94 dB, 0.0 % |

Smallest tested ray count meeting the criterion in every case: none.

## 5 m cells (criterion: 95 % within 2.0 dB, at most 1 % missed)

| Scene | Site (antenna height) | Band | 1e+06 rays | 3e+06 rays | 1e+07 rays | 3e+07 rays | 1e+08 rays | 2nd 1e9 map (floor) |
|---|---|---|---|---|---|---|---|---|
| osm | site-001 (58 m) | nr_3500 | 28.45 dB, 31.7 % | 16.88 dB, 24.0 % | 17.51 dB, 17.9 % | 24.12 dB, 10.4 % | 23.92 dB, 3.2 % | 3.13 dB, 0.1 % |
| osm | site-003 (15 m) | nr_3500 | 29.32 dB, 63.5 % | 27.77 dB, 45.5 % | 27.89 dB, 24.0 % | 28.29 dB, 7.4 % | 16.75 dB, 0.5 % | 2.97 dB, 0.0 % |
| osm | site-004 (13 m) | nr_3500 | 34.22 dB, 52.6 % | 27.92 dB, 36.7 % | 19.48 dB, 24.2 % | 15.32 dB, 12.3 % | 9.94 dB, 4.1 % | 3.16 dB, 0.0 % |
| osm | site-001 (58 m) | nr_28000 | 35.08 dB, 31.7 % | 21.15 dB, 24.1 % | 19.46 dB, 17.9 % | 27.45 dB, 10.4 % | 25.93 dB, 3.2 % | 3.18 dB, 0.1 % |
| osm | site-003 (15 m) | nr_28000 | 33.68 dB, 63.5 % | 31.56 dB, 45.5 % | 31.65 dB, 24.0 % | 31.90 dB, 7.4 % | 19.84 dB, 0.5 % | 2.94 dB, 0.0 % |
| osm | site-004 (13 m) | nr_28000 | 41.66 dB, 52.6 % | 33.19 dB, 36.7 % | 23.30 dB, 24.2 % | 17.60 dB, 12.3 % | 11.83 dB, 4.1 % | 3.22 dB, 0.1 % |
| mixed_1_to_8-seed1 | site-001 (58 m) | nr_3500 | 31.29 dB, 29.2 % | 25.11 dB, 20.1 % | 23.14 dB, 13.4 % | 21.75 dB, 8.0 % | 20.14 dB, 2.7 % | 3.66 dB, 0.1 % |
| mixed_1_to_8-seed1 | site-001 (58 m) | nr_28000 | 37.08 dB, 29.3 % | 28.89 dB, 20.2 % | 25.50 dB, 13.5 % | 24.40 dB, 8.2 % | 21.53 dB, 2.7 % | 3.61 dB, 0.1 % |

Smallest tested ray count meeting the criterion in every case: none.

