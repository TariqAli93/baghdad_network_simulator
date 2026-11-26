# Corrections to the project description

The project description (`Project_Description_4G_5G_6G_Baghdad.pdf`, November 2026) is the
project's primary requirement document and is **kept unchanged**. This file records, beside
it, every statement in it that the Phase 1 review found to need correction or qualification.
The thesis should follow the corrected statements; the PDF remains the record of what was
originally proposed.

- Verification date for every row: **2026-11-26**.
- Source IDs refer to `docs/references.md`, which gives the URL, the clause and how each
  source was checked.
- "Impact on the simulation" says whether the correction changes anything that is computed.
  **None of these corrections changes the five baseline scenarios** (frequencies and
  bandwidths in Table 1 of the PDF and in `configs/scenarios.yaml`).

## 1. Corrections

| # | Where in the PDF | Original statement | Corrected statement | Primary source | Impact on the simulation |
|---|---|---|---|---|---|
| C1 | §2 Background; ref. [10] | "Zain Iraq became the first operator in the country to launch commercial 5G services in 2026." | No commercial 5G launch in Iraq could be confirmed as of November 2026. Operators were running trials, no 5G spectrum had been assigned, and the regulator was reported to plan a 5G auction for 2027. The cited article is a single uncorroborated report. | `IRQ-ZAIN-IR`, `IRQ-CMC-WP`, `IRQ-ASIACELL-LAB`, `IRQ-CMC-2026`; the original claim is `IRQ-MEATW` | None on the calculations. The 5G scenarios describe a network that does **not yet exist** in Iraq; results for them are projections, not a description of a deployed network. The roadmap (Stage 10) must start from "5G not yet launched". |
| C2 | §2 Background; ref. [4] | Release 21 timeline cited as "3GPP TSG RAN#112, Release 21 timeline agreement, Singapore, June 2026". | The timeline was agreed in the joint TSG#112 session (RAN, SA and CT plenaries) on 10 June 2026, document RP-260868. | `3GPP-REL21` | None. Citation only. |
| C3 | §2 Background | "...between March 2027 and the end of 2028, with a final freeze planned for March 2029." | Content approved March 2027; Stage 3 (protocol) freeze December 2028; ASN.1/OpenAPI freeze March 2029. The dates in the PDF are right; the two freezes should be named. | `3GPP-REL21` | None. Roadmap dates only. |
| C4 | §4 Stage 3 | "The 6G bandwidth is set to 400 MHz, the widest carrier agreed by 3GPP in June 2026." | 400 MHz is the maximum carrier bandwidth agreed for the range around 7 GHz (base station; devices 400 MHz downlink optional, 200 MHz uplink), in March 2026. For 15 GHz no carrier maximum has been agreed; 400 MHz there is the bandwidth 3GPP assumes for evaluation. It is not the widest bandwidth under discussion (1 GHz is assumed near 30 GHz). | `3GPP-RP260798`, `3GPP-TR38914` | None on the values: both candidate scenarios keep 400 MHz. The 15 GHz bandwidth is an **evaluation assumption**, weaker than the 8 GHz one, and must be labelled so. |
| C5 | Table 1, row "6G, upper mid-band" | "WRC-27 candidate, ITU Region 1 (includes Iraq): 7.75-8.4 GHz" | In Region 1 the bands under study are 7.125-7.25 GHz and 7.75-8.4 GHz. | `ITU-RES256` | None. The 8.0 GHz carrier with 400 MHz occupies 7.8-8.2 GHz, inside 7.75-8.4 GHz (checked by a unit test). |
| C6 | §2 Background | "WRC-27 is studying the 4.4-4.8 GHz, 7.125-8.4 GHz and 14.8-15.35 GHz bands." | Correct as a list. Regional limits: 4.4-4.8 GHz in Regions 1 and 3 only; the whole 7.125-8.4 GHz in Regions 2 and 3 only; 14.8-15.35 GHz in all regions. None of these bands is identified for mobile use yet. | `ITU-RES256` | None. The 15.0 GHz carrier occupies 14.8-15.2 GHz, starting at the lower band edge (checked by a unit test). |
| C7 | Ref. [9] | "CEPT, IMT-2030 (6G) spectrum needs and candidate bands, document PTA(23)047." | PTA(23)047 is an input contribution by Huawei, Ericsson, Nokia, Qualcomm and ZTE to a CEPT group (May 2023), not a CEPT position. CEPT's own view is in its draft Brief on agenda item 1.7. | `CEPT-PTA23-047`, `CEPT-AI17` | None. |
| C8 | §6, "User data rate" | "...reported at the 5th-percentile user (the ITU definition of user experienced data rate)". | Correct. The definition is in Report ITU-R M.2410-0 §4.3, which is not in the PDF's reference list; M.2083 only describes the capability. | `ITU-M2410` | None. Confirms the metric the project computes. |
| C9 | Table 1, row "4G LTE" | "1.8 GHz, 20 MHz, Band 3, in use by Iraqi operators" | LTE on 1800 MHz (Band 3) is confirmed by the regulator for all three operators. The 20 MHz carrier width is not documented in any source found; it is the largest Band 3 channel and a modelling assumption. 1.8 GHz is nominal (the Band 3 downlink is 1805-1880 MHz). | `IRQ-CMC-WP`, `3GPP-TS36101` | Small. If operators use narrower carriers, the 4G data rates are overstated in proportion to bandwidth. The nominal frequency changes free-space loss by 0.2 dB. |
| C10 | Table 1, row "5G NR, mid-band"; §8 | "Typical first 5G band (assumed for Iraq)" | Still an assumption, now with support: the regulator's plan names 3.4-3.8 GHz as the main 5G capacity band, with 100 MHz blocks per licence holder to be evaluated. Nothing had been assigned as of November 2026, and the plan ranks 700 MHz and 2.6 / 2.3 GHz ahead of it for the short term. | `IRQ-CMC-WP`, `IRQ-NFAT` | None on the values. |
| C11 | Ref. [7] | Sionna RT cited by arXiv number only. | Published as J. Hoydis et al., 2023 IEEE Globecom Workshops, pp. 317-321. | `HOYDIS2023` | None. |
| C12 | Ref. [6] | Salazar, Arévalo, Játiva, no venue given. | 2021 Global Congress on Electrical Engineering (GC-ElecEng), pp. 55-60, DOI 10.1109/GC-ElecEng52322.2021.9788150. | `docs/related-studies.md`, R1 | None. |
| C13 | Ref. [8] | MathWorks example, no URL. | The example's former URL no longer works; the current one is in the registry. | `MATHWORKS-URBAN` | None. |

## 2. Statements that changed because the engine changed

These are not errors in the PDF. The PDF describes a MATLAB-based method; the supervisor
approved Sionna RT instead (`docs/architecture.md`, section 2). The thesis methodology must
describe what was actually done.

| Where in the PDF | PDF | What the project does | Impact |
|---|---|---|---|
| §4 Stages 4-7; §5 | MATLAB `propagationModel` with shooting and bouncing rays; `txsite`, `coverage`, `sigstrength`, `sinr`; `nrPathLoss` | Sionna RT 2.2.0 for ray tracing; received power, SINR, data rate and the 3GPP formulas computed by this project's own tested code; MATLAB only for cross-checks | Results are power sums averaged over each receiver cell, without fast fading. Diffraction is first-order and never follows a reflection |
| §4 Stage 2 | City model imported into MATLAB Site Viewer | OpenStreetMap footprints converted by this project into a Sionna RT scene | None on the principle; the height problem below applies either way |
| §7 deliverables | "the MATLAB scripts" | Python package, scripts and tests in this repository | Deliverable changes form |

## 3. Qualifications that must accompany the results

These are not corrections of single sentences but limits on what the project can claim.

1. **Candidate 6G is not 6G.** The 8 GHz and 15 GHz scenarios use frequency ranges that are
   only *under study* for mobile use (decision at WRC-27, late 2027) and bandwidths that are
   3GPP *evaluation assumptions* or early agreements. The first 6G specifications are due in
   2028-2029. Results for these scenarios are projections under stated assumptions, not
   predictions of commercial 6G performance.
2. **5G in Iraq is assumed, not observed** (C1, C10).
3. **Building heights.** The PDF says "some heights are estimated from the number of
   floors". In fact almost none are available: in the test area 97 % of buildings have no
   height information in OpenStreetMap. Until measured or documented heights are obtained,
   results depend on an assumed height distribution, and must be reported with a sensitivity
   analysis (`docs/building-height-data.md`).
4. **Expected result.** §7 of the PDF expects that higher bands need more sites. The
   simulation may confirm or reject this; with identical antennas at every band (the current
   assumption) the outcome is strongly influenced by that assumption
   (`docs/supervisor-decisions.md`).
5. **Research gap.** The literature search found no study that determines, for one real
   district, the number of sites needed at each of 1.8, 3.5, 8, 15 and 28 GHz, and no
   ray-tracing coverage study of Baghdad. This is a statement about one search, not proof
   that no such study exists: the search covered English-language sources reachable online
   on 2026-11-26 (publisher pages, arXiv, Crossref, open repositories), examined 23 studies
   in detail, could not open several paywalled papers, and did not systematically cover
   Arabic-language journals, theses or operator reports. The thesis should word the gap as
   "to the best of our knowledge, within the scope of this search".
6. **Accuracy.** Published comparisons of ray tracers with measurements report errors of
   roughly 8 to 21 dB. Site counts are estimates with that uncertainty; there are no field
   measurements in this project (the PDF's §8 already says so).
