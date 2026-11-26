# Verification of the B3 rate mapping (2026-11-27)

Checked against the primary documents, downloaded from the 3GPP archive on 2026-11-27:
`38921-j00.zip` (3GPP TR 38.921 V19.0.0 (2025-09), SHA-256 88399296…) and `36942-j00.zip`
(3GPP TR 36.942 V19.0.0, SHA-256 6e9cc639…). Text extracted from the Word files and read;
the files are not stored in the repository.

## What the sources say

**TR 38.921 §4.2.7 "Link level performance for 5G NR coexistence", Table 4.2.7-1.** The
throughput of a modem with link adaptation "can be approximated by an attenuated and
truncated form of the Shannon bound":

| SNIR | Throughput (bit/s/Hz) |
|---|---|
| SNIR < SNIR_MIN | 0 |
| SNIR_MIN ≤ SNIR < SNIR_MAX | α · log2(1 + SNIR) |
| SNIR ≥ SNIR_MAX | α · log2(1 + SNIR_MAX) |

| Parameter | DL | UL | Note in the table |
|---|---|---|---|
| α | 0.6 | 0.4 | implementation losses |
| SNIR_MIN | −10 dB | −10 dB | QPSK 1/8 (DL), 1/5 (UL) |
| SNIR_MAX | 30 dB | 22 dB | 256QAM 0.93 (DL), 64QAM 0.93 (UL) |

Stated assumptions: 1:1 antennas, AWGN channel, link adaptation, no HARQ; "targeted for eMBB
coexistence scenario" (the study is for the 7 and 10 GHz ranges).

**TR 36.942 Annex A, Table A.1 (E-UTRA).** The same form with α 0.6 (DL) and SNIR_MIN −10 dB,
but the cap is given as a maximum throughput of 4.4 bit/s/Hz (64QAM 4/5), i.e. SNIR_MAX ≈ 22 dB;
assumptions 1:2 antennas, Typical Urban fading, HARQ.

**TR 36.942 Table A.2 (look-up table, downlink), read 2026-11-27.** 0 from −15 to −11 dB;
0.08 bit/s/Hz at −10 dB; 0.60 at 0 dB; 2.08 at 10 dB; 3.99 at 20 dB; 4.39 at 22 dB; **4.40 from
23 dB up** (to 25 dB, the end of the table). So the LTE cap is a cap on the spectral efficiency,
reached continuously at S⁻¹(4.4 / 0.6) = 22.05 dB; there is no jump.

## The project's implementation (2026-11-27, per band)

`configs/radio_system.yaml` holds the mappings once each (`rate_mappings`) and assigns them per
scenario (`scenario_rate_mapping`); `bns.analysis.rate_models` reads them and
`bns.analysis.link_budget.truncated_shannon_bps` computes the rate (B = carrier bandwidth in
Hz, result in bit/s; 0 below SINR_MIN, inclusive bound):

| Scenario | Mapping | Formula above SINR_MIN | Label |
|---|---|---|---|
| 4G LTE 1.8 GHz | `lte`: α 0.6, −10 dB, Thr_MAX 4.4 bit/s/Hz (TR 36.942 Table A.1 DL) | B · min(α log2(1+SINR), 4.4) | 3GPP mapping |
| 5G NR 3.5 and 28 GHz | `nr`: α 0.6, −10 dB, SINR_MAX 30 dB (TR 38.921 Table 4.2.7-1 DL) | α B log2(1 + min(SINR, SINR_MAX)) | 3GPP mapping |
| Candidate 6G 8 and 15 GHz | `nr_based_candidate_6g`: `based_on: nr` (same constants, not copied) | as NR | **research approximation**: no 6G link-level mapping exists |

| Check | Result |
|---|---|
| Scaling factor 0.6 | correct (TR 38.921 DL; TR 36.942 DL) |
| Lower threshold −10 dB, inclusive | correct for both (Table A.2: 0 at −11 dB, 0.08 at −10 dB) |
| NR upper bound: constant from 30 dB | correct (TR 38.921 DL) |
| LTE upper bound: 4.4 bit/s/Hz, reached at 22.05 dB, continuous | correct; the unit test reproduces the Table A.2 rows listed above to two decimals |
| Units | bit/s/Hz × carrier bandwidth = bit/s; no overhead removed (as in the Shannon bound) |
| Shannon bound kept separately | yes (`rate_bps`); the mapped rate is `rate_3gpp_bps`, reported beside it; each run summary names the mapping used (`rate_3gpp_model`) |

Saved development runs made before 2026-11-27 applied the NR mapping to all five bands (the
approval of 2026-11-26); for the 4G scenario they differ from the LTE mapping only in cells above
about 22 dB SINR. They remain development results.

## Interpretation and label

These are **3GPP-specified link-level approximations** for coexistence studies: TR 36.942 for
E-UTRA (1:2 antennas, Typical Urban fading, HARQ) and TR 38.921 for NR (1:1 antenna, AWGN, no
HARQ). Applying them per band is the project's approximation, approved under B3; for candidate
6G it is explicitly an NR-based research approximation. They describe one user's link
throughput with link adaptation, not network capacity or user throughput under load.
