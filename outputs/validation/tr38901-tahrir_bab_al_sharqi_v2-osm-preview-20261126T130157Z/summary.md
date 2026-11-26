# DEVELOPMENT — NOT APPROVED FOR RESEARCH

## Ray tracing vs 3GPP TR 38.901 (model-to-model comparison)

Isotropic antenna at (0, 0) m, at least 8 m from any building; users at 1.5 m; profile preview (25 m cells, 1e+08 rays); mechanisms LOS + 2 reflections + first-order diffraction. LOS/NLOS from a line-of-sight-only trace. Error = traced − 3GPP path loss (positive: the ray tracer predicts more loss). Cells closer than 10 m are outside the models and excluded; unreached cells are counted, not averaged.

**Applicability.** Base-station heights equal the models' (25 m, 10 m); 0.5-100 GHz and 10 m-5 km hold. Not matched: the district (provisional, 99 % placeholder heights; UMi assumes the antenna below the rooftops, here most roofs are 9 m) and the statistical nature of the models (generic layouts, shadow fading σ). Agreement within about σ is the most that can be expected; it is a plausibility check, not a validation against measurements.

### UMa (base station 25 m); LOS share of outdoor cells 85 %

| Band | LOS cells: mean / std / RMSE | NLOS cells: mean / std / RMSE | σ LOS / NLOS | Fitted exponent LOS / NLOS | Unreached |
|---|---|---|---|---|---|
| 4G LTE 1.8 GHz | -4.3 / 4.0 / 5.9 dB (n=684) | -16.7 / 6.1 / 17.8 dB (n=124) | 4 / 6 dB | 1.71 / 2.14 | 0 of 808 |
| 5G NR mid-band 3.5 GHz | -1.5 / 3.3 / 3.6 dB (n=684) | -14.9 / 6.6 / 16.3 dB (n=124) | 4 / 6 dB | 1.70 / 2.25 | 0 of 808 |
| Candidate 6G upper mid-band 8 GHz | -1.3 / 3.5 / 3.8 dB (n=684) | -12.8 / 7.2 / 14.7 dB (n=124) | 4 / 6 dB | 1.69 / 2.44 | 0 of 808 |
| Candidate 6G 15 GHz 15 GHz | -1.3 / 3.6 / 3.8 dB (n=684) | -11.3 / 7.9 / 13.7 dB (n=124) | 4 / 6 dB | 1.68 / 2.63 | 0 of 808 |
| 5G NR mmWave 28 GHz | -1.2 / 3.7 / 3.9 dB (n=684) | -9.9 / 8.4 / 13.0 dB (n=124) | 4 / 6 dB | 1.68 / 2.74 | 0 of 808 |

| Distance | Cells | Traced LOS share | TR 38.901 LOS probability |
|---|---|---|---|
| 0-50 m | 2 | 100 % | 91 % |
| 50-100 m | 10 | 90 % | 47 % |
| 100-150 m | 16 | 81 % | 26 % |
| 150-200 m | 29 | 97 % | 16 % |
| 200-250 m | 43 | 88 % | 11 % |
| 250-300 m | 54 | 96 % | 8 % |
| 300-350 m | 76 | 88 % | 6 % |
| 350-400 m | 117 | 75 % | 5 % |
| 400-450 m | 127 | 74 % | 4 % |
| 450-500 m | 144 | 88 % | 4 % |
| 500-550 m | 89 | 97 % | 3 % |
| 550-600 m | 55 | 84 % | 3 % |
| 600-650 m | 32 | 78 % | 3 % |
| 650-700 m | 14 | 64 % | 3 % |

### UMi (base station 10 m); LOS share of outdoor cells 27 %

| Band | LOS cells: mean / std / RMSE | NLOS cells: mean / std / RMSE | σ LOS / NLOS | Fitted exponent LOS / NLOS | Unreached |
|---|---|---|---|---|---|
| 4G LTE 1.8 GHz | -12.6 / 5.7 / 13.9 dB (n=222) | -19.5 / 6.7 / 20.7 dB (n=586) | 4 / 7.82 dB | 1.82 / 1.33 | 0 of 808 |
| 5G NR mid-band 3.5 GHz | -7.6 / 4.9 / 9.1 dB (n=222) | -18.2 / 6.9 / 19.5 dB (n=586) | 4 / 7.82 dB | 1.84 / 1.43 | 0 of 808 |
| Candidate 6G upper mid-band 8 GHz | -3.4 / 3.6 / 4.9 dB (n=222) | -16.7 / 7.2 / 18.2 dB (n=586) | 4 / 7.82 dB | 1.86 / 1.67 | 0 of 808 |
| Candidate 6G 15 GHz 15 GHz | -3.0 / 3.6 / 4.7 dB (n=222) | -15.7 / 7.4 / 17.4 dB (n=586) | 4 / 7.82 dB | 1.87 / 1.92 | 0 of 808 |
| 5G NR mmWave 28 GHz | -2.9 / 3.7 / 4.7 dB (n=222) | -14.8 / 7.9 / 16.8 dB (n=586) | 4 / 7.82 dB | 1.88 / 2.19 | 0 of 808 |

| Distance | Cells | Traced LOS share | TR 38.901 LOS probability |
|---|---|---|---|
| 0-50 m | 2 | 100 % | 86 % |
| 50-100 m | 10 | 90 % | 33 % |
| 100-150 m | 16 | 81 % | 17 % |
| 150-200 m | 29 | 55 % | 11 % |
| 200-250 m | 43 | 40 % | 8 % |
| 250-300 m | 54 | 33 % | 7 % |
| 300-350 m | 76 | 28 % | 6 % |
| 350-400 m | 117 | 21 % | 5 % |
| 400-450 m | 127 | 20 % | 4 % |
| 450-500 m | 144 | 18 % | 4 % |
| 500-550 m | 89 | 27 % | 3 % |
| 550-600 m | 55 | 25 % | 3 % |
| 600-650 m | 32 | 25 % | 3 % |
| 650-700 m | 14 | 29 % | 3 % |

Fitted exponent n from PL = A + 10 n log10(d3D) over the reached cells (TR 38.901 below the breakpoint: UMa LOS 2.2, NLOS 3.91; UMi LOS 2.1, NLOS 3.53). Published measured exponents near 7-17 GHz: about 1.8-2.3 in line of sight and 2.6-2.7 without (docs/related-studies.md R4-R6).
Run time 2 s. Figures: pathloss_UMa.png, pathloss_UMi.png, los_probability.png.
