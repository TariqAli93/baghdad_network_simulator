# Technical reference registry

Every standard, model, parameter source and dataset the project relies on, with what was
checked and how. Compiled 2026-11-26 (Phase 1). Related published studies are compared in
`docs/related-studies.md`.

**Read this first.** The entries were collected by automated research passes that opened the
documents named here, and a sample was re-checked independently. That is enough to build on,
not enough to cite: **before a source goes into the thesis, open it yourself at the URL and
confirm the clause, table or number quoted here.** Where the registry says a value was
computed or could not be verified, it must not be presented as taken from the source.

## How each entry was checked

| Mark | Meaning |
|---|---|
| **Read** | The official document was opened and its text read |
| **Read+** | As *Read*, and confirmed again by a second independent search |
| **Record** | Bibliographic record confirmed in Crossref or arXiv; the content itself was not read |
| **Page** | Web page opened through a summarising fetch tool; wording may be paraphrased |
| **Press** | Secondary source (trade press, vendor blog, news) |
| **Computed** | Derived by calculation from a *Read* formula or table |
| **Open** | Not verified |

IDs in the first column are stable; `configs/scenarios.yaml` and other project files refer
to them.

---

## 1. ITU framework for IMT-2020 and IMT-2030

| ID | Document | Used for | Check |
|---|---|---|---|
| `ITU-M2083` | Rec. ITU-R M.2083-0 (09/2015), "IMT Vision – Framework and overall objectives of the future development of IMT for 2020 and beyond". https://www.itu.int/rec/R-REC-M.2083-0-201509-I/en | IMT-2020 (5G) capability targets | Read |
| `ITU-M2410` | Report ITU-R M.2410-0 (11/2017), "Minimum requirements related to technical performance for IMT-2020 radio interface(s)". https://www.itu.int/pub/R-REP-M.2410-2017 | **Definition of user experienced data rate**; 5G targets | Read |
| `APPROVAL-2026-11-26` | Supervisor approval of the recommended options of `docs/supervisor-checklist.md` (version bc750b3), as reported by the project owner on 2026-11-26; recorded in `configs/approvals.yaml` and `docs/approval-record.md`. No written reference yet | Values approved without a published source (mast height above the roof, antenna position, site rule) | Reported, not documented |
| `ITU-M2412` | Report ITU-R M.2412-0 (2017), "Guidelines for evaluation of radio interface technologies for IMT-2020". https://www.itu.int/pub/R-REP-M.2412-2017 | Reference deployment geometry (dense urban) | Read |
| `ITU-M2160` | Rec. ITU-R M.2160-0 (11/2023), "Framework and overall objectives of the future development of IMT for 2030 and beyond". https://www.itu.int/rec/R-REC-M.2160-0-202311-I/en | IMT-2030 (6G) usage scenarios and research targets | Read |
| `ITU-IMT2030` | ITU-R WP 5D IMT-2030 pages and timeline. https://www.itu.int/en/ITU-R/study-groups/rsg5/rwp5d/imt-2030/Pages/default.aspx | 6G process dates for the roadmap | Page |

Facts taken from them:

| Fact | Value | Where |
|---|---|---|
| User experienced data rate | The 5 % point of the cumulative distribution of user throughput | `ITU-M2410` §4.3. (M.2083 only describes the capability; cite M.2410 for the definition.) |
| 5G requirement, dense urban | 100 Mbit/s downlink, 50 Mbit/s uplink | `ITU-M2410` §4.3 |
| 5G 5th-percentile spectral efficiency, dense urban | 0.225 (downlink) and 0.15 (uplink) bit/s/Hz | `ITU-M2410` §4.4, Table 1 |
| 5G capability targets | Peak 20 Gbit/s; user experienced 100 Mbit/s; latency 1 ms; mobility 500 km/h; 10^6 devices/km²; area capacity 10 Mbit/s/m² | `ITU-M2083` §5, Fig. 3 |
| Dense urban evaluation layout | Macro inter-site distance 200 m, base station 25 m (micro 10 m), carriers 4 GHz and 30 GHz | `ITU-M2412` §8, Table 5(b) |
| 6G research targets (examples, not requirements) | Peak 50 / 100 / 200 Gbit/s; user experienced 300 / 500 Mbit/s; area capacity 30 / 50 Mbit/s/m²; latency 0.1-1 ms | `ITU-M2160` §4. The Recommendation calls these estimated targets for research that may not be reached together |
| 6G usage scenarios | Immersive communication; hyper reliable and low-latency; massive; ubiquitous connectivity; AI and communication; integrated sensing and communication | `ITU-M2160` §3 |
| 6G requirements report | Draft "M.[IMT-2030.TECH PERF REQ]" (Doc 5/116, Feb 2026) scheduled for Study Group 5 approval on 1 December 2026; **not approved at the time of writing** | `ITU-IMT2030`. Re-check after 1 December 2026 |
| 6G proposal window | February 2027 to February 2029; specifications no later than 2030 | `ITU-IMT2030`; `ITU-M2160` §5.2 |

## 2. Spectrum: WRC-27 and regional positions

| ID | Document | Used for | Check |
|---|---|---|---|
| `ITU-RES256` | Resolution 256 (WRC-23), studies for IMT identification (WRC-27 agenda item 1.7). https://www.itu.int/dms_pub/itu-r/oth/0c/0a/R0C0A0000100007PDFE.pdf | **Basis of the 8 GHz and 15 GHz scenarios** | Read+ |
| `ITU-WRC27` | WRC-27 conference page. https://www.itu.int/wrc-27/ | Conference dates | Page |
| `ASMG-AI17` | Arab Spectrum Management Group, preliminary views for WRC-27 (Nov 2025). https://www.itu.int/dms_pub/itu-r/md/23/wrc27iris25/c/R23-WRC27IRIS25-C-0006!!PDF-E.pdf | Position of the regional group Iraq belongs to | Read |
| `CEPT-AI17` | Draft CEPT Brief on agenda item 1.7, CPG(25)016 Annex IV-07 (June 2025). https://cept.org/documents/cpg/89977/cpg-25-016-annex-iv-07_draft-cept-brief-on-wrc-27-agenda-item-1_7- | European position, for contrast | Read |
| `CEPT-PTA23-047` | PTA(23)047, "IMT-2030 (6G) Spectrum needs and candidate bands", input to CEPT CPG PTA #8, May 2023, **from Huawei, Ericsson, Nokia, Qualcomm and ZTE**. https://cept.org/Documents/cpg-pta/77266/pta-23-047_imt-2030-6g-spectrum-needs-and-candidate-bands | Industry view of 6G spectrum need | Read |

| Fact | Value | Where |
|---|---|---|
| Bands under study for IMT | 4 400-4 800 MHz; 7 125-8 400 MHz; 14.8-15.35 GHz | `ITU-RES256` |
| **Region 1 (includes Iraq)** | 4 400-4 800 MHz; **7 125-7 250 MHz and 7 750-8 400 MHz**; 14.8-15.35 GHz | `ITU-RES256` |
| Regions 2 and 3 | Whole 7 125-8 400 MHz; 4 400-4 800 MHz in Region 3 only (not Region 2) | `ITU-RES256` |
| Iraq is in Region 1 | Stated in an ITU tutorial; the Radio Regulations article itself was not opened | Page. https://www.itu.int/en/ITU-R/seminars/rrs/RRS-13-Africa/Documents/Tutorial/ITU-R_Basics.pdf |
| WRC-27 | 18 October - 12 November 2027, Shanghai; preparatory meeting CPM27-2 on 5-15 April 2027 | `ITU-WRC27` |
| Arab group view | Identification of 7 125-7 250, 7 750-8 400 MHz and 14.8-15.35 GHz to be considered on the study results, provided incumbent services are protected | `ASMG-AI17` |
| European view | Opposes 7 250-8 400 MHz unless incumbents are protected; does not expect 14.8-15.35 GHz to be feasible | `CEPT-AI17` |
| Iraq's own position | None found | Open |

What this means for the scenarios: an 8.0 GHz carrier 400 MHz wide occupies 7.8-8.2 GHz,
inside the Region 1 part (7.75-8.4 GHz). A 15.0 GHz carrier 400 MHz wide occupies
14.8-15.2 GHz, starting exactly at the lower band edge. Neither band is identified for
mobile use yet; the decision is for WRC-27.

## 3. 3GPP: releases, 6G requirements and band definitions

| ID | Document | Used for | Check |
|---|---|---|---|
| `3GPP-REL21` | "Release 21 Timeline", RP-260868, TSG#112 joint session, Singapore, 10 June 2026; news item https://www.3gpp.org/news-events/3gpp-news/rel21-timeline | 6G specification dates | Read+ |
| `3GPP-TR38914` | TR 38.914 V20.1.0 (2026-09), 6G scenarios and requirements (first version approved June 2026). https://www.3gpp.org/ftp/Specs/archive/38_series/38.914/ | **6G bandwidth and target assumptions** | Read |
| `3GPP-RP260798` | RP-260798, way forward on maximum channel bandwidth around 7 GHz, RAN#111, March 2026. https://www.3gpp.org/ftp/tsg_ran/TSG_RAN/TSGR_111/Docs/RP-260798.zip | 400 MHz carrier for 6G | Read |
| `3GPP-TS36101` | TS 36.101 V20.1.0 (2026-09), LTE user-equipment radio requirements | LTE Band 3 definition | Read |
| `3GPP-TS38101-1` | TS 38.101-1 V20.1.0 (2026-09), NR FR1 | Band n78 definition | Read |
| `3GPP-TS38101-2` | TS 38.101-2 V20.1.0 (2026-09), NR FR2 | Bands n257 / n258 / n261 | Read |
| `3GPP-TR38901` | TR 38.901 V19.5.0 = ETSI TR 138 901 V19.5.0 (2026-09), "Study on channel model for frequencies from 0.5 to 100 GHz". https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.05.00_60/tr_138901v190500p.pdf | **Validation model (Phase 7)**; see section 5 | Read |
| `3GPP-TR36942` | TR 36.942 V19.0.0 = ETSI TR 136 942 V19.0.0 (2025-10), Annex A. https://www.etsi.org/deliver/etsi_tr/136900_136999/136942/19.00.00_60/tr_136942v190000p.pdf | Attenuated Shannon rate model (optional) | Read |
| `PODDAR2025` | H. Poddar et al., "Overview of 3GPP Release 19 Study on Channel Modeling Enhancements to TR 38.901 for 6G", arXiv:2507.19266 | Background on the 7-24 GHz update | Page |

| Fact | Value | Where |
|---|---|---|
| Release 21 (first 6G specifications) | Content approved March 2027; Stage 2 frozen June 2028; **Stage 3 frozen December 2028; ASN.1/OpenAPI frozen March 2029** | `3GPP-REL21` |
| 6G carrier bandwidth around 7 GHz | Base station 400 MHz in both directions; device 400 MHz downlink (optional) and 200 MHz uplink | `3GPP-RP260798` (March 2026; its formal approval status in the meeting minutes was not checked) |
| 6G bandwidth assumed for evaluation | 400 MHz aggregated at 7 GHz and at 15 GHz; 1 GHz at 30 GHz | `3GPP-TR38914` Table 4.2-1 |
| 6G carrier bandwidth around 15 GHz | No agreed per-carrier maximum found; only the evaluation assumption above | Open |
| 6G dense urban target | 5th-percentile user data rate 300 Mbit/s downlink, 50 Mbit/s uplink; macro inter-site distance 200 m | `3GPP-TR38914` §5.1 |
| LTE Band 3 | Uplink 1710-1785 MHz, downlink 1805-1880 MHz; channel bandwidths up to 20 MHz | `3GPP-TS36101` Tables 5.5-1, 5.6.1-1 |
| NR n78 | 3300-3800 MHz, TDD; up to 100 MHz | `3GPP-TS38101-1` Tables 5.2-1, 5.3.5-1 |
| NR n257 / n261 / n258 | 26.5-29.5 / 27.5-28.35 / 24.25-27.5 GHz; up to 400 MHz. 28 GHz lies in n257 and n261 | `3GPP-TS38101-2` Tables 5.2-1, 5.3.5-1 |

Note on the 4G scenario: 1.8 GHz is a nominal value. The Band 3 downlink is 1805-1880 MHz,
so 1.8 GHz sits in the gap between uplink and downlink. Simulating at the downlink centre
(1842.5 MHz) instead would change free-space loss by 0.2 dB. Keep 1.8 GHz as the nominal
frequency or switch to 1842.5 MHz, but state which.

### 3.1 Sources of radio-system parameters (added in Phase 3)

Read for the parameter proposal in `docs/radio-parameters.md` (text of each document
extracted and read on 2026-11-26, archive URLs under https://www.3gpp.org/ftp/Specs/archive/
for 3GPP).

| ID | Document | Used for | Check |
|---|---|---|---|
| `ITU-M2292` | Report ITU-R M.2292-0 (12/2013), characteristics of terrestrial IMT-Advanced systems for sharing studies. https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-M.2292-2014-PDF-E.pdf | Macro base-station power, antenna, downtilt, noise figure, reuse and activity factor (Tables 1-4) | Read |
| `3GPP-TR38921` | TR 38.921 V19.0.0, IMT parameters for the 7 GHz and 10 GHz ranges (study for ITU-R sharing work; copy the exact title from 3gpp.org before citing) | 7 GHz-range base-station power, element, array and downtilt; UE noise figure; truncated Shannon mapping (Table 4.2.7-1) | Read |
| `3GPP-TR38830` | TR 38.830 V17.0.0, study on NR coverage enhancements | Coverage link-budget templates, cell-area reliability (Table A.3), UE antenna gains | Read |
| `3GPP-TR38802` | TR 38.802 V14.2.0, study on New Radio access technology physical layer aspects | Evaluation power, noise figure, EIRP caps, load levels (Annex A) | Read |
| `3GPP-TR36814` | TR 36.814 V9.2.0, further advancements for E-UTRA physical layer aspects | LTE macro power (Table A.2.1.1-2) | Read |
| `ITU-P372` | Rec. ITU-R P.372-15 (09/2021), radio noise | Reference noise temperature T0 = 290 K (§1.2.1) | Read |
| `CEPT-ECC-1106` | ECC/DEC/(11)06, harmonised frequency arrangements for 3 400-3 800 MHz (amended 26 Oct 2018). https://docdb.cept.org/download/1531 | Regulatory EIRP context at 3.5 GHz (no obligatory in-block limit) | Read |

The 3GPP band specifications already registered (`3GPP-TS36101`, `3GPP-TS38101-1`,
`3GPP-TS38101-2`) also give the receiver reference sensitivities quoted in
`docs/radio-parameters.md`; `ITU-M2412`, `3GPP-TR38914`, `3GPP-TR36942` and `3GPP-TR38901`
supply the remaining values.

## 4. Mobile market and spectrum in Iraq

| ID | Document | Used for | Check |
|---|---|---|---|
| `IRQ-CMC-WP` | Communications and Media Commission (CMC), "Iraq National ICT Industry Development Whitepaper" (undated; data to early 2024). https://cmc.iq/wp-content/uploads/2025/08/The-role-and-importance-of-developing-broadband-infrastructure-in-the-ICT-and-digitization-sector-in-Iraq-in-English-white-paper.pdf | **Bands in use; the regulator's 5G band plan** | Read |
| `IRQ-NFAT` | CMC, National Frequency Allocation Table. https://cmc.iq/ar/wp-content/uploads/2025/03/Republic-of-Iraq-National-Frequency-Allocation-Table-2-Final.pdf | Current use of candidate bands | Read |
| `IRQ-GSMA-2022` | GSMA, "Iraq Facilitates 4G Rollout with Licence Extensions, Tech Neutrality" (March 2022). https://www.gsma.com/publicpolicy/wp-content/uploads/2022/03/Iraq-Facilitates-4G-Rollout-with-Licence-Extensions-Tech-Neutrality.pdf | Licence terms | Read |
| `IRQ-ZAIN-IR` | Zain Group investor presentation, Q2 2026 (11 Aug 2026). https://d30ezutk4plts9.cloudfront.net/media/documents/Zain_IR_deck__-_Q2_2026.pdf | Zain Iraq network status | Read |
| `IRQ-MEATW` | MEA Tech Watch, "Zain Iraq becomes first operator in the country to launch commercial 5G services" (7 Aug 2026). https://meatechwatch.com/?p=56483 | The claim cited by the project description | Press; existence confirmed twice |
| `IRQ-ASIACELL-LAB` | Asiacell / Al-Nahrain University 5G lab announcements (April 2026 press release; a further release dated 25 Nov 2026). https://www.prnewswire.com/ae/news-releases/with-the-support-and-sponsorship-of-the-communications-and-media-commission-cmc-asiacell-and-al-nahrain-university-announce-the-opening-of-the-first-5g-lab-for-educational-purposes-in-iraq-302741552.html | 5G trial status | Press; April release confirmed twice, November release once |
| `IRQ-CMC-2026` | Rudaw (Arabic), interview with the CMC executive head, 25 Nov 2026. http://www.rudawarabia.net/arabic/categories/iraq/1369562 | Regulator's statement on 5G timing | Press; found by one pass only |
| `IRQ-NMTC` | Shafaq News reports on the national 5G company. https://shafaq.com/en/Economy/Communications-Minister-vows-to-revive-stalled-5G-operator-in-Iraq | State 5G operator history | Press |
| `IRQ-DATAREPORTAL` | DataReportal, "Digital 2027: Iraq" (5 Nov 2026). https://datareportal.com/reports/digital-2027-iraq | Market size | Page |

| Fact | Value | Where |
|---|---|---|
| Operators | Zain Iraq, Asiacell, Korek Telecom; regulator CMC | `IRQ-CMC-WP` |
| 4G | All three launched LTE on **1800 MHz** in January 2021; 2G on 900/1800 MHz, 3G on 2100 MHz | `IRQ-CMC-WP` |
| LTE carrier width used in Iraq | **Not found in any source.** 20 MHz is the Band 3 maximum and a modelling assumption | Open |
| Later 4G spectrum | Zain Iraq holds 2.6 GHz blocks (75 MHz in four governorates, 40 MHz elsewhere) | Zain Sustainability Report 2025, Read |
| Regulator's 5G plan | 700 MHz and 2.6 / 2.3 GHz first; **3.4-3.8 GHz as the key capacity band, with contiguous 100 MHz blocks per licence holder to be evaluated** | `IRQ-CMC-WP` |
| 3.3-3.4 GHz | Military radiolocation; 3.4-3.8 GHz is civil with IMT among its uses | `IRQ-NFAT` |
| 14.8-15.3 GHz today | Fixed links and defence systems | `IRQ-NFAT` |
| 5G spectrum assigned | None found | Open |
| Commercial 5G | **No launch confirmed as of 25 November 2026.** See below | several |
| Market size | 48.3 million people; 50.2 million mobile connections (end 2026) | `IRQ-DATAREPORTAL` |
| 4G population coverage | 96.6 % (ITU figure for 2022, quoted by the CMC) | `IRQ-CMC-WP` |
| Korek | Regulator began shutting its network in 14 provinces in November 2026 over unpaid debt | Iraqi News, Press |

**The "first commercial 5G launch" claim.** The project description says Zain Iraq launched
commercial 5G in 2026, citing `IRQ-MEATW`. That article exists, but it names no source and
gives no date, city, band or vendor, and nothing else found supports it:

- Zain Group's own investor presentation four days later lists Iraq's network as 4G
  (`IRQ-ZAIN-IR`); Zain Iraq's press page shows no 5G launch; its statements say "5G-ready"
  and "ready to launch once licensed".
- Asiacell describes a 5G lab and says it is still preparing a commercial rollout
  (`IRQ-ASIACELL-LAB`).
- The regulator's head is reported on 25 November 2026 as calling the situation a trial
  environment, with a 5G auction and launch planned for 2027 (`IRQ-CMC-2026`).
- The state 5G operator was created in 2025 and then frozen by a court order (`IRQ-NMTC`).

Wording supported by the evidence: *"As of November 2026 no operator had launched commercial
5G in Iraq; operators were running trials and the regulator planned a 5G auction for 2027."*
The two 25 November items are a day old and rest on single sources: confirm them, ideally
with the CMC directly, before the thesis is submitted.

## 5. Propagation models

The 3GPP channel model `3GPP-TR38901` (UMa and UMi path loss and line-of-sight probability)
is registered in section 3.

| ID | Document | Used for | Check |
|---|---|---|---|
| `ITU-P2040` | Rec. ITU-R P.2040-4 (09/2025), building materials, 1 MHz-450 GHz. https://www.itu.int/rec/R-REC-P.2040/en | **Concrete**; reflection formulas used in experiment E2 | Read |
| `ITU-P526` | Rec. ITU-R P.526-16 (11/2025), "Propagation by diffraction". https://www.itu.int/rec/R-REC-P.526/en | Knife-edge reference used in experiment E3 | Read |
| `ITU-P676` | Rec. ITU-R P.676-13 (08/2022), attenuation by atmospheric gases. https://www.itu.int/rec/R-REC-P.676/en | Gas loss | Read |
| `ITU-P838` | Rec. ITU-R P.838-3 (03/2005), specific attenuation model for rain. https://www.itu.int/rec/R-REC-P.838/en | Rain loss | Read |
| `ITU-P837` | Rec. ITU-R P.837-8 (09/2025), characteristics of precipitation. https://www.itu.int/rec/R-REC-P.837/en | Rain rate for Baghdad | Read (method only) |
| `ITU-P1411` | Rec. ITU-R P.1411-13 (09/2025), short-range outdoor propagation, 300 MHz-300 GHz. https://www.itu.int/rec/R-REC-P.1411/en | Possible second comparison model | Read |

### 5.1 3GPP TR 38.901 path loss (Table 7.4.1-1), as the project will implement it

`fc` in GHz, distances in metres, logarithms base 10. `d2D` is the ground distance and `d3D`
the straight-line distance between the antennas. Shadow fading σ in dB.

| Scenario | Formula | σ |
|---|---|---|
| UMa, line of sight | `PL1 = 28.0 + 22 log(d3D) + 20 log(fc)` for 10 m ≤ d2D ≤ d'BP; `PL2 = 28.0 + 40 log(d3D) + 20 log(fc) − 9 log(d'BP² + (hBS − hUT)²)` for d'BP ≤ d2D ≤ 5 km | 4 |
| UMa, no line of sight | `max(PL_UMa-LOS, 13.54 + 39.08 log(d3D) + 20 log(fc) − 0.6 (hUT − 1.5))` for 10 m ≤ d2D ≤ 5 km | 6 |
| UMi street canyon, line of sight | `PL1 = 32.4 + 21 log(d3D) + 20 log(fc)` for 10 m ≤ d2D ≤ d'BP; `PL2 = 32.4 + 40 log(d3D) + 20 log(fc) − 9.5 log(d'BP² + (hBS − hUT)²)` for d'BP ≤ d2D ≤ 5 km | 4 |
| UMi street canyon, no line of sight | `max(PL_UMi-LOS, 35.3 log(d3D) + 22.4 + 21.3 log(fc) − 0.3 (hUT − 1.5))` for 10 m ≤ d2D ≤ 5 km | 7.82 |

- Breakpoint: `d'BP = 4 (hBS − hE)(hUT − hE) fc / c`, here with `fc` in Hz and c = 3.0×10⁸ m/s.
  `hE` = 1 m for UMi, and also for UMa when the user is below 13 m (always, at 1.5 m).
- Optional simpler no-line-of-sight forms: UMa `32.4 + 20 log(fc) + 30 log(d3D)` (σ 7.8);
  UMi `32.4 + 20 log(fc) + 31.9 log(d3D)` (σ 8.2).
- **Validity:** 0.5-100 GHz; user height 1.5-22.5 m; **base station height 25 m (UMa) or
  10 m (UMi)**. The formulas were derived for those heights. Rooftop sites at other heights
  are outside the stated range, which Phase 7 must report for every comparison.
- Line-of-sight probability (Table 7.4.2-1), 1 below 18 m, otherwise:
  UMi `18/d + exp(−d/36)(1 − 18/d)`; UMa `18/d + exp(−d/63)(1 − 18/d)` for a user below 13 m.
- Release 19 (the 7-24 GHz study) left these formulas unchanged; this was checked by
  comparing V18.0.0 with V19.5.0. It added a suburban scenario and near-field models.
- Oxygen loss is set to 0 dB/km below 52 GHz in the TR (Table 7.6.1-1).
- Not confirmed from the text: the relation `d3D = sqrt(d2D² + (hBS − hUT)²)` is defined by a
  figure that could not be read. It is the standard reading.

Breakpoint distances for a 1.5 m user (computed):

| Band | UMa (25 m) | UMi (10 m) |
|---|---|---|
| 1.8 GHz | 288 m | 108 m |
| 3.5 GHz | 560 m | 210 m |
| 8 GHz | 1280 m | 480 m |
| 15 GHz | 2400 m | 900 m |
| 28 GHz | 4480 m | 1680 m |

Within a 1 km² study area the second slope matters only at 1.8 and 3.5 GHz.

### 5.2 Building materials (ITU-R P.2040-4)

- Model: relative permittivity `a·f^b`, conductivity `c·f^d` S/m, `f` in GHz (eqs 57-58).
- **Concrete, Table 3:** a = 5.24, b = 0, c = 0.0462, d = 0.7822, for 1-100 GHz. Sionna RT
  2.2.0 uses the same row.
- Fresnel coefficients at an air interface: eqs (37a) TE and (37b) TM. Single-layer slab:
  eqs (43a) and (44). These are the formulas in `bns.validation.analytic`.
- **MATLAB differs by default.** MATLAB's custom-material defaults (permittivity 5.31,
  conductivity 0.0548 S/m "at 1.9 GHz") reproduce the 2015 version P.2040-1, whose concrete
  row was 5.31, 0, 0.0326, 0.8095. The current row gives 0.0763 S/m at 1.9 GHz. For the
  Phase 7 cross-check the material must be set explicitly in MATLAB.

Concrete at the project's bands (computed from the current row):

| Band | Permittivity | Conductivity |
|---|---|---|
| 1.8 GHz | 5.24 | 0.073 S/m |
| 3.5 GHz | 5.24 | 0.123 S/m |
| 8 GHz | 5.24 | 0.235 S/m |
| 15 GHz | 5.24 | 0.384 S/m |
| 28 GHz | 5.24 | 0.626 S/m |

### 5.3 Diffraction (ITU-R P.526-16)

- Geometry parameter ν: eq (26). Single knife edge, exact: eq (30); approximation
  `J(ν) = 6.9 + 20 log(sqrt((ν − 0.1)² + 1) + ν − 0.1)` dB for ν > −0.78: eq (31).
- Section 6 gives a method for a finitely conducting wedge (building corners, roof ridges),
  the closer physical model for a building edge.

### 5.4 Atmospheric gases (ITU-R P.676-13)

The Recommendation gives the line-by-line method (Annex 1) and a figure, no table of values.
Sea-level specific attenuation for the standard atmosphere, **computed** from Annex 1 by the
research pass (to be reproduced by project code in Phase 4):

| Band | dB/km |
|---|---|
| 1.8 GHz | 0.007 |
| 3.5 GHz | 0.008 |
| 8 GHz | 0.011 |
| 15 GHz | 0.029 |
| 28 GHz | 0.10 |

Over the longest path in a 1 km² area this is at most about 0.15 dB at 28 GHz. Gas loss is
negligible for this study at every band; include it for completeness and say so.

### 5.5 Rain (ITU-R P.838-3 and P.837-8)

Specific attenuation `γ = k·R^α` dB/km, with R the rain rate in mm/h. Coefficients from
Table 5 (horizontal / vertical polarisation):

| Band | k | α |
|---|---|---|
| 1.8 GHz (computed from eqs 2-3; not tabulated) | 0.0000658 / 0.0000819 | 1.0479 / 0.9264 |
| 3.5 GHz | 0.0001155 / 0.0002346 | 1.4189 / 1.1387 |
| 8 GHz | 0.004115 / 0.003450 | 1.3905 / 1.3797 |
| 15 GHz | 0.04481 / 0.05008 | 1.1233 / 1.0440 |
| 28 GHz | 0.2051 / 0.1964 | 0.9679 / 0.9277 |

**The rain rate for Baghdad is not settled.** No published value was found. The maps of the
edition in force, P.837-8, are a 361 MB download that has not been made. The previous
edition, P.837-7, gives 18.6 mm/h exceeded 0.01 % of the time (read through the ITU-Rpy
library in Phase 2; `docs/atmospheric-losses.md`). That value is a candidate for a
sensitivity case only; the project baseline is clear sky. Rain matters mainly at 15 and
28 GHz.

### 5.6 A second statistical model (ITU-R P.1411-13)

Site-general path loss `L = 10α log(d) + β + 10γ log(f)` with coefficient sets for terminals
below rooftops (Table 4) and for one terminal above rooftop height (Table 8), which matches
rooftop base stations. Above-rooftop line of sight: α 2.29, β 28.6, γ 1.96, σ 3.48 dB, for
2.2-73 GHz and 55-1200 m. Above-rooftop without line of sight, urban high-rise: α 4.39,
β −6.27, γ 2.30, σ 6.89 dB, for 2.2-66.5 GHz and 260-1200 m. The 1.8 GHz scenario is below
the lower limit of Table 8. Optional for Phase 7.

## 6. Data-rate model

| ID | Document | Used for | Check |
|---|---|---|---|
| `SHANNON1949` | C. E. Shannon, "Communication in the Presence of Noise", Proc. IRE, vol. 37, no. 1, pp. 10-21, 1949. DOI 10.1109/JRPROC.1949.232969 | Capacity formula | Record |

`3GPP-TR36942` (registered in section 3) gives the attenuated, truncated Shannon bound.

The project description uses `C = B log2(1 + SINR)` as an upper bound. System studies often
report a more realistic variant; TR 36.942 Annex A defines one for LTE: throughput
`= α log2(1 + SINR)` bit/s/Hz with α = 0.6, zero below −10 dB, capped at 4.4 bit/s/Hz
(downlink). Several of the related studies use similar forms. Whether to report this beside
the pure Shannon value is a decision for the supervisor; the pure Shannon value stays the
project baseline.

## 7. Ray-tracing method and tools

| ID | Reference | Used for | Check |
|---|---|---|---|
| `YUN2015` | Z. Yun and M. F. Iskander, "Ray Tracing for Radio Propagation Modeling: Principles and Applications", IEEE Access, vol. 3, pp. 1089-1100, 2015. DOI 10.1109/ACCESS.2015.2453991 | Survey of the method | Record |
| `LING1989` | H. Ling, R.-C. Chou, S.-W. Lee, "Shooting and bouncing rays: calculating the RCS of an arbitrarily shaped cavity", IEEE Trans. Antennas Propag., vol. 37, no. 2, pp. 194-205, 1989. DOI 10.1109/8.18706 | Origin of shooting and bouncing rays | Record |
| `KOUYOUMJIAN1974` | R. G. Kouyoumjian and P. H. Pathak, "A uniform geometrical theory of diffraction for an edge in a perfectly conducting surface", Proc. IEEE, vol. 62, no. 11, pp. 1448-1461, 1974. DOI 10.1109/PROC.1974.9651 | Diffraction theory | Record |
| `LUEBBERS1984` | R. Luebbers, "Finite conductivity uniform GTD versus knife edge diffraction in prediction of propagation path loss", IEEE Trans. Antennas Propag., vol. 32, no. 1, pp. 70-76, 1984. DOI 10.1109/TAP.1984.1143189 | Diffraction by real (non-metal) edges | Record |
| `HOYDIS2023` | J. Hoydis, F. Aït Aoudia, S. Cammerer, M. Nimier-David, N. Binder, G. Marcus, A. Keller, "Sionna RT: Differentiable Ray Tracing for Radio Propagation Modeling", 2023 IEEE Globecom Workshops, pp. 317-321. DOI 10.1109/GCWkshps58843.2023.10465179; arXiv:2303.11103 | The engine | Record |
| `SIONNA-TR` | F. Aït Aoudia, J. Hoydis, M. Nimier-David, B. Nicolet, S. Cammerer, A. Keller, "Sionna RT: Technical Report", arXiv:2504.21719; https://nvlabs.github.io/sionna/rt/tech-report/ | How the solvers work (radio maps, diffraction) | Page |
| `MATHWORKS-RT` | MathWorks, "RayTracing - Ray tracing propagation model". https://www.mathworks.com/help/comm/ref/rfprop.raytracing.html | MATLAB method for the Phase 7 cross-check | Page |
| `MATHWORKS-URBAN` | MathWorks, "Urban Link and Coverage Analysis Using Ray Tracing". https://www.mathworks.com/help/comm/ug/urban-channel-link-analysis-and-visualization-using-ray-tracing.html | The example cited by the project description (its old URL no longer works) | Page |

The project description cites `HOYDIS2023` by its arXiv number only; the published version
is the 2023 IEEE Globecom Workshops paper above.

## 8. Data and software

| ID | Source | Licence | Used for |
|---|---|---|---|
| `OSM` | OpenStreetMap, via the Overpass API; snapshot hashes in `data/raw/osm/` | ODbL 1.0 | Building footprints |
| `SIONNA-RT` | Sionna RT 2.2.0, https://nvlabs.github.io/sionna/rt/ | Apache 2.0 | Ray tracing |
| `GLOBFP3D` | 3D-GloBFP building heights, https://zenodo.org/records/15487006 | CC BY 4.0 | Candidate source of building heights (Phase 2) |
| `GBA` | GlobalBuildingAtlas, https://github.com/zhu-xlab/GlobalBuildingAtlas | CC BY-NC 4.0 | Candidate source of building heights (Phase 2) |

## 9. Corrections this review implies for the project description

| Statement in the project description | Finding | Suggested wording |
|---|---|---|
| Zain Iraq launched Iraq's first commercial 5G in 2026 | Not supported; contradicted by operator and regulator sources (section 4) | No commercial 5G as of November 2026; trials under way; auction planned for 2027 |
| Reference [4]: "3GPP TSG RAN#112, Release 21 timeline agreement" | Dates correct; the decision was taken in the joint TSG#112 session | "3GPP TSG#112 joint session, Release 21 Timeline, RP-260868, Singapore, 10 June 2026" |
| "final freeze planned for March 2029" | Correct; it is the ASN.1/OpenAPI freeze, after the Stage 3 freeze of December 2028 | Name both milestones |
| "400 MHz, the widest carrier agreed by 3GPP in June 2026" | 400 MHz is right for the 7 GHz range, but agreed in March 2026, with 200 MHz device uplink; it is not the widest (1 GHz is assumed near 30 GHz); for 15 GHz only an evaluation assumption exists | "400 MHz, the maximum carrier bandwidth agreed for the 7 GHz range (3GPP RAN#111, March 2026) and the bandwidth assumed for 7 and 15 GHz in TR 38.914" |
| "ITU Region 1 (includes Iraq): 7.75-8.4 GHz" | Incomplete | "7.125-7.25 GHz and 7.75-8.4 GHz" |
| WRC-27 bands listed without regions | 4.4-4.8 GHz is under study for Regions 1 and 3 only | Add the regional limits |
| Reference [9]: "CEPT, ... document PTA(23)047" | It is an industry contribution to a CEPT group, not a CEPT position | Attribute it to its five authors; cite the draft CEPT Brief for CEPT's view |
| "5th-percentile user (the ITU definition of user experienced data rate)" | Correct; the definition is in Report M.2410-0, which is not in the reference list | Add M.2410-0 |
| "1.8 GHz, 20 MHz, Band 3, in use by Iraqi operators" | Band confirmed by the regulator; the 20 MHz carrier is not documented | Call 20 MHz an assumption |
| "3.5 GHz ... assumed for Iraq" | Supported: the regulator's plan names 3.4-3.8 GHz with 100 MHz blocks; nothing is assigned yet | "proposed by the regulator, not yet assigned" |
| Reference [7], Sionna RT, arXiv only | Published at IEEE Globecom Workshops 2023 | Cite the published version |
| Reference [6], Salazar et al. | Verified; see `docs/related-studies.md` | Add venue, pages and DOI |
