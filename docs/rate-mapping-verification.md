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

## The project's implementation

`configs/radio_system.yaml` (`rate_mapping`): α 0.6, SINR_MIN −10 dB, SINR_MAX 30 dB — the
**TR 38.921 downlink values, exactly**. `bns.analysis.link_budget.truncated_shannon_bps`
returns α · B · log2(1 + min(SINR, SINR_MAX)) for SINR ≥ SINR_MIN and 0 below; B is the
carrier bandwidth in Hz, the result is in bit/s. Unit test: zero below −10 dB, α-scaled value
at −10 dB (inclusive), constant from 30 dB up, never above Shannon.

| Check | Result |
|---|---|
| Scaling factor 0.6 | correct (TR 38.921 DL; also TR 36.942 DL) |
| Lower threshold −10 dB, inclusive | correct |
| Upper threshold 30 dB, constant above | correct for TR 38.921 DL; TR 36.942 caps LTE at 4.4 bit/s/Hz (≈ 22 dB) |
| Units | bit/s/Hz × carrier bandwidth = bit/s; no overhead removed (as in the Shannon bound) |
| Shannon bound kept separately | yes (`rate_bps`); the mapped rate is `rate_3gpp_bps`, reported beside it |

## Interpretation and label

It is a **3GPP-specified link-level approximation** (TR 38.921 Table 4.2.7-1, NR downlink
baseline for coexistence studies), **applied to all five bands by decision B3** so that the
controlled experiment uses one mapping. That application is the project's approximation, not a
3GPP statement about each band. It describes one user's link throughput with link adaptation,
not network capacity or user throughput under load.

**To confirm with the supervisor (B3 detail):** whether the 4G scenario should instead use the
LTE mapping of TR 36.942 (cap 4.4 bit/s/Hz). It changes only cells above about 22 dB SINR.
Until then the approved single mapping stays as implemented.
