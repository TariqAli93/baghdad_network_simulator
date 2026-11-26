# Radio-system parameter proposal (Phase 3)

Proposed 2026-11-26. **None of these values is approved** except the receiver height, which
the project description fixes. They are stored in `configs/radio_system.yaml` with the state
`candidate` (sourced, awaiting the supervisor) or `development` (for software testing only).
Development runs may use them; research runs refuse anything not approved.

Every value was read from the text of the cited document (extracted from the official PDF or
3GPP archive file). Source IDs refer to `docs/references.md`. Read the cited table yourself
before quoting it in the thesis.

## 1. The rule behind the proposal

The thesis compares five carriers under a **controlled experiment**: one common radio system,
so that only frequency and bandwidth differ (`docs/methodology.md`). Each candidate value is
therefore one value for all five bands, taken from sources that use it across bands. Values
that the sources give per band are listed separately for the **deployment interpretation**.

## 2. Proposal

| Parameter | Proposed value | Unit | State | Sources (table) | Why this value | Validity | Expected effect on results |
|---|---|---|---|---|---|---|---|
| Transmit power | **46** conducted, all bands | dBm per sector carrier | candidate | `3GPP-TR38914` Table 5.1.20.1-2; `3GPP-TR36942` Table 4.6; `ITU-M2292` Tables 3-4; `3GPP-TR38921` Table 6.1.5-1 (43 dBm per polarisation, 46 dBm for two) | The macro power used across all of these, independent of band | Macro sites; total power per sector carrier, at the antenna port | Shifts all received power equally. The same total power over wider carriers gives less power per MHz: 33 dBm/MHz at 20 MHz, 26 at 100 MHz, 20 at 400 MHz |
| Antenna pattern | **3GPP TR 38.901 element**, traced | — | candidate | `3GPP-TR38901` Table 7.3-1; `ITU-M2412` Table 9 | Standard sector element: 65° beamwidth, 8 dBi peak, 30 dB front-to-back. Its traced shape was checked against the TR 38.901 formula (`docs/validation.md`) | One element per sector; no array or beamforming gain | Concentrates power in front of each sector |
| Antenna gain added after tracing | **0** | dBi | candidate | `3GPP-TR38901` | The traced pattern already contains the 8 dBi; any other value counts it twice (refused by the software) | With a traced pattern | Guards against double counting |
| Sectors per site | **3** (0°, 120°, 240°) | — | candidate | `ITU-M2412` §8.3 (three TRxPs per site); `ITU-M2292` | Standard macro layout | All sectors on the same carrier | Three traces per site and band; neighbouring sectors interfere |
| Mechanical downtilt | **10** | degrees below horizon | candidate | `ITU-M2292` Tables 3-4 (macro urban); `3GPP-TR38921` Table 8.1.2-1 | Macro urban value in both | Same for every site and band | Moves the strongest signal towards the site |
| Antenna height above roof | 3 | m | **development** | none | **No primary source gives a mast height above a roof.** The sources give total heights for flat layouts (25 m: `ITU-M2412` Table 5(b), `3GPP-TR38901` UMa) | — | Decision D4 |
| Receiver height | **1.5** | m | **approved** (project description, Stage 6) | `ITU-M2412` Table 5(b) | Outdoor user height | Outdoor pedestrians | Fixed |
| Receiver antenna gain | **0** | dBi | candidate | `3GPP-TR36942` §4.2.2; `ITU-M2412` (4 GHz); `3GPP-TR38830` Table A.3 (FR1) | Isotropic user, matching the isotropic receiver of the ray-traced maps | All bands | Shifts received power equally |
| Receiver noise figure | **9** | dB | candidate | `3GPP-TR38914` Table 5.1.20.1-2; `3GPP-TR36942` Table 4.8; `ITU-M2292` Table 1; `3GPP-TR38921` §7.2.1 | Common value across these sources | All bands | Shifts SNR equally |
| Noise reference temperature | **290** | K | candidate | `ITU-P372` §1.2.1; −174 dBm/Hz in `ITU-M2412` Table 5 | Reference temperature T0 | Reference, not the local temperature | Fixes the noise floor (−174 dBm/Hz) |
| Coverage criterion | **SINR ≥ −10 dB** (SNR for one transmitter) | dB | candidate | `3GPP-TR38921` Table 4.2.7-1; `3GPP-TR36942` Annex A | The lowest SINR at which the 3GPP throughput mapping gives any rate; a noise-referenced threshold means the same at every bandwidth | Best-serving sector | Equivalent to a received-power threshold 13 dB higher at 400 MHz than at 20 MHz |
| Coverage target | **95 %** of outdoor cells | — | candidate | `3GPP-TR38830` Table A.3 (95 % for control channels, 90 % for data) | The stricter of the two | Area share | Stops the greedy site selection |
| Frequency reuse | **1** | — | candidate | `ITU-M2412` (evaluation method); `ITU-M2292` Tables 2-4 | Every sector uses the whole carrier | Multi-sector and multi-site runs | Worst case for interference |
| Network load (interference activity) | **100 %** | share of time | candidate | `ITU-M2412` Table 5 (full buffer); sensitivity 50 % from `ITU-M2292` | Worst case | Multi-sector and multi-site runs | Lower load raises SINR; no effect on single-transmitter SNR |
| Weather | **Clear sky**, gas attenuation included | — | baseline (`configs/atmosphere.yaml`) | `ITU-P676`; rain cases in `docs/atmospheric-losses.md` | No approved Baghdad rain rate | All bands | Gas loss ≤ 0.1 dB/km |

Resulting peak EIRP: 46 dBm + 8 dBi = **54 dBm** per sector, well below the evaluation caps
of 73 dBm (`ITU-M2412`, 30 GHz macro) and 78 dBm (`3GPP-TR38802`, UMa).

## 3. Conducted power, EIRP and double counting

- **Conducted power** is measured at the antenna port, before any antenna gain. M.2412,
  TR 38.802, TR 36.814, TR 38.830 and TR 38.914 quote conducted power.
- **EIRP** includes the antenna gain. M.2292's EIRP rows already include +16 or +18 dBi,
  −3 dB feeder loss and, in the "average" rows, a 50 % activity factor; TR 36.942's 15 dBi
  already includes feeder loss.
- In this project the ray tracer either traces an isotropic antenna (then a gain or an EIRP
  is added afterwards) or traces the sector pattern (then the gain is already inside the
  path gain). `configs/radio_system.yaml` states which, and the software refuses:
  an EIRP together with an added gain; an EIRP together with a traced pattern; a traced
  pattern together with a non-zero added gain (`tests/unit/test_radio_system.py`).
- An isotropic trace with a gain added afterwards would radiate that gain in every
  direction, which no real antenna does. That is why the proposal traces the pattern.

## 4. Per-band values for the deployment interpretation

These are not used in the controlled experiment. They show how real systems differ by band.

| Quantity | Per-band values in the sources |
|---|---|
| Base-station power | 44 dBm per 20 MHz at 4 GHz and 40 dBm per 80 MHz at 30 GHz (`ITU-M2412` Table 5(b), dense urban macro); TR 38.802 Table A.2.1-1: 44 dBm below and 40 dBm above 6 GHz, scaled with bandwidth; 15 GHz: not found (ITU-R working documents are restricted) |
| Antenna arrays | Up to 256 elements in M.2412; 192 (4 GHz) and 256 (28 GHz) in TR 38.830; "up to" 576 (4 GHz), 2304 (7 and 15 GHz) and 4096 (30 GHz) elements in TR 38.914 Table 4.2-1. Array gain grows with frequency at fixed size |
| User noise figure | 7 dB at 4 GHz and 10 dB at 30 GHz (`ITU-M2412`); 9 dB baseline and 13 dB optional at 7-10 GHz (`3GPP-TR38921`) |
| User antenna gain | 0 dBi (FR1), 5 dBi (FR2 with user beamforming) (`ITU-M2412`, `3GPP-TR38830`) |
| Receiver reference sensitivity | LTE Band 3, 20 MHz: −91 dBm (`3GPP-TS36101` Table 7.3.1-1, conducted); n78, 100 MHz, 30 kHz: about −85.5 dBm from −96.1 + 10 log10(273/24) (`3GPP-TS38101-1` Table 7.3.2-1b, conducted, per port, computed); n257/n261, 400 MHz, power class 3: −79.3 dBm **EIS**, which already includes the user antenna gain (`3GPP-TS38101-2` Table 7.3.2.3-1) |
| Coverage link-budget targets | Maximum coupling loss 143 dB (basic) and 153 dB (extended), frequency-independent (`3GPP-TR38914` §5.1.20.1); urban targets 10 Mbit/s at 4 GHz, 25 Mbit/s at 28 GHz (`3GPP-TR38830`) |

Receiver sensitivities are not comparable across bands as a coverage threshold: they refer
to different bandwidths, and the millimetre-wave value includes antenna gain.

## 5. What could not be sourced

- A mast height above the roof (decision D4).
- Base-station power, arrays and noise figure specifically at 8 GHz and at 15 GHz.
- Any Iraqi licence coverage obligation; the regulator's white paper gives policy targets
  (4G availability, 5G coverage shares), not a coverage definition.
- A minimum-SINR coverage criterion in ITU-R M.2412 (none exists there).

## 6. How to approve a value

Change its `status` to `approved` in `configs/radio_system.yaml` and add `approved_by` with
the name and date. The unit tests check that every source ID exists in the registry.
