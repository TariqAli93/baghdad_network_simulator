# Related studies

Ten published studies closest to this project, three alternates, and the studies found for
Iraq. Compiled 2026-11-26 (Phase 1). Standards and models are in `docs/references.md`.

**How this was checked.** Each study's landing page or PDF was opened by a first reader. The
bibliographic data of every study were then confirmed against the Crossref or arXiv record,
and every figure quoted below was re-read from the PDF text by a second, independent reader
(for study R7 from the publisher's web page). Three figures carry caveats, stated where they
occur. **Open each paper yourself before citing it**: this table is a map, not a substitute
for reading, and the preprints may change before publication.

## 1. Comparison table

| # | Study | Bands | Area | Method | Main result | Use for this project |
|---|---|---|---|---|---|---|
| R1 | Salazar, Arévalo, Játiva, 2021 | 4 and 28 GHz | Quito, 4.94 km², OpenStreetMap | MATLAB shooting-and-bouncing rays; concrete; base station 25 m, user 1.5 m | Path-loss exponent about 2.7 at 4 GHz and about 3.4 at 28 GHz | The reference the project description cites; same tool chain; no site counts or data rates |
| R2 | Testolina, Polese, Melodia, 2024 | 3.5, 12.7, 28 GHz | Boston, 1.5 × 1.5 km, city 3D data | Sionna ray tracer; existing cell sites, about 18 per km² | From the same sites, 12.7 GHz matches 3.5 GHz outdoor coverage over 88 % of the area and 28 GHz over 75 %; 3.52× average rate gain for 400 MHz at FR3 over 100 MHz at FR1 | **Closest to the research question**, but with a fixed site grid instead of solving for the number of sites |
| R3 | Kang et al., 2024 | 6, 12, 18, 24 GHz (100-400 MHz) | New York, Herald Square, 1120 × 510 m | Wireless InSite; 18 rooftop sites about 200 m apart | With blockage, users at 18 and 24 GHz do much worse about 35 % of the time; for about 65 % of indoor users the lower bands give higher rates | Same method class on a real map; shows the rate model most studies use |
| R4 | Shakya et al., ICC 2025 | 6.75 and 16.95 GHz | Downtown Brooklyn, 40 m to about 1 km | Measurement, 1 GHz bandwidth; transmitter 4 m, receiver 1.5 m | Measured exponents: line of sight 1.79 and 1.85; no line of sight 2.56 and 2.59 (3GPP UMi: 2.19 / 2.1 and 3.19) | Measured benchmarks next to the 8 and 15 GHz scenarios, already compared with TR 38.901 |
| R5 | Liu et al., 2026 (preprint) | 8 and 15 GHz | University campus, Beijing; rooftop transmitter about 27.8 m | Measurement with large antenna arrays | Exponents: line of sight 2.25 and 2.33; no line of sight 2.56 and 2.69. At 15 % outage, 15 GHz is about 3 dB behind 8 GHz | **The only measurements found at exactly the project's two 6G bands** |
| R6 | Ying et al., 2026 | 6.75 and 16.95 GHz | Brooklyn, about 1.2 × 1.7 km; OpenStreetMap corrected by field survey | Ray tracer (NYURay): 1 million rays, 5 reflections, diffraction | Ray-traced exponents within 0.03-0.14 of the measured ones, and closer to them than 3GPP's | A template for validation: compare exponents with measurement and 3GPP |
| R7 | Lodato et al., 2026 | 27 GHz | Turin, about 600 × 650 m, 14,725 measured points | In-house tracer, MATLAB and Sionna RT against a walk test | Median absolute error 9.3 / 7.6 / 9.9 dB; correlation 0.53 / 0.46 / 0.50 (in-house / MATLAB / Sionna) | **How large the error of MATLAB and Sionna ray tracing is against real measurements** |
| R8 | Deylamy et al., 2026 (accepted) | 3.9 GHz | University of Glasgow; OpenStreetMap | MATLAB ray tracing and Sionna RT, 2 reflections + 1 diffraction, against 2,258 measured samples | Mean absolute error 16.4 dB (MATLAB) and 21.3 dB (Sionna) uncalibrated; 8.8 and 9.0 dB after a linear calibration | Nearly this project's tool chain and settings, with measured error |
| R9 | Taus, Tsai, Andrews, 2026 (preprint) | 1.8 GHz, 10 MHz | San Francisco and Florence, about 1.1 km across | Sionna RT maps for about 11,000 candidate sites; greedy selection; rate from SINR | Against an existing operator layout: mean rate 21.2 → 36.1 Mbps, 5 % edge rate 5.5 → 10.4 Mbps | **Closest in method**: greedy site selection on ray-traced maps with SINR-based rates |
| R10 | Gemmi, Lo Cigno, Maccari, 2022 | Millimetre wave (line of sight only) | 15 areas of about 0.7 km² in three Italian cities; LiDAR | Visibility analysis and a set-cover heuristic | 60-120 base stations per km² generally suffice for line-of-sight street coverage | Published site densities for the millimetre-wave end of the comparison |

## 2. Notes on each study

**R1.** A. Salazar S., G. V. Arévalo, R. Játiva E., "Propagation, blockage and coverage
evaluation in 5G urban wireless networks", 2021 Global Congress on Electrical Engineering
(GC-ElecEng), pp. 55-60. DOI 10.1109/GC-ElecEng52322.2021.9788150.
The simulated carriers are 4 GHz with 20 MHz and 28 GHz with 100 MHz (its Tables IV and V).
Concrete is set to permittivity 5.31 and conductivity 0.0548 S/m, the older ITU values that
MATLAB uses by default (see `docs/references.md`, section 5.2). Up to ten reflections; rain,
gas and fog losses added. It compares with free-space, close-in and NYU models, not with
3GPP TR 38.901, and reports no SINR, data rate or site count. The paper prints "4 MHz" and
"28 MHz" where it means GHz.

**R2.** P. Testolina, M. Polese, T. Melodia, "Sharing Spectrum and Services in the 7-24 GHz
Upper Midband", IEEE Communications Magazine, vol. 62, no. 8, pp. 170-177, 2024.
DOI 10.1109/MCOM.001.2400086 (read as preprint arXiv:2402.08649).
Coverage is defined as signal-to-noise ratio above 0 dB, relative to 3.5 GHz. Transmit power
and antenna heights are not stated in the text read. The authors call the analysis
preliminary.

**R3.** S. Kang, M. Mezzavilla, S. Rangan, A. Madanayake, S. B. Venkatakrishnan,
G. Hellbourg, M. Ghosh, H. Rahmani, A. Dhananjay, "Cellular Wireless Networks in the Upper
Mid-Band", IEEE Open Journal of the Communications Society, vol. 5, pp. 2058-2075, 2024.
DOI 10.1109/OJCOMS.2024.3373368.
Rate model: bandwidth × min(4.8, 0.57 × log2(1 + SNR)) bit/s. Sites were placed by hand;
33 dBm maximum power; antenna arrays grow with frequency. The interference case is described
as a worst-case bound.

**R4.** D. Shakya, M. Ying, T. S. Rappaport, P. Ma, I. Al-Wazani, Y. Wu, Y. Wang, D. Calin,
H. Poddar, A. Bazzi, M. Chafii, Y. Xing, A. Ghosh, "Urban Outdoor Propagation Measurements
and Channel Models at 6.75 GHz FR1(C) and 16.95 GHz FR3 Upper Mid-Band Spectrum for 5G and
6G", ICC 2025, pp. 3291-3296. DOI 10.1109/ICC52391.2025.11161884.
Exponents use a 1 m reference distance, omnidirectional. Shadow-fading spread: 2.57 and
6.53 dB at 6.75 GHz, 4.05 and 8.78 dB at 16.95 GHz (line of sight, no line of sight). The
transmitter is at street-lamp height (4 m), not on a rooftop.

**R5.** E. Liu, P. Tang, H. Miao, Q. Zhen, J. Zhang, "Measurement-Based Massive MIMO Channel
Characterization and Performance Evaluation at FR3 (8 and 15 GHz) Under Equal Physical
Aperture", arXiv:2604.15680, April 2026. **Preprint, not peer reviewed.**
The 3 dB figure is for coherent beamforming; 3.9 dB without. No comparison with TR 38.901.

**R6.** M. Ying, D. Shakya, P. Ma, G. Qian, T. S. Rappaport, "Site-specific location
calibration and validation of ray-tracing simulator NYURay at upper mid-band frequencies",
npj Wireless Technology, vol. 2, article 8, 2026. DOI 10.1038/s44459-025-00014-x (read as
preprint arXiv:2507.22027).
Measured / ray-traced / 3GPP exponents: 6.75 GHz 1.79 / 1.86 / 2.19 (line of sight) and
2.56 / 2.66 / 3.19 (no line of sight); 16.95 GHz 1.85 / 1.88 / 2.10 and 2.59 / 2.73 / 3.19.
The building model was corrected with laser and LiDAR measurements, and antenna positions
were calibrated: this is the accuracy achievable with much better geometry than plain
OpenStreetMap. Ray tracing underestimates delay spread. No error in dB is reported.

**R7.** F. Lodato, P. Salvo, M. Folli, S. Valbonesi, A. Garzia, G. Ruello, R. Suman,
M. Perobelli, R. Massa, A. Iodice, "Ray Tracing Simulators for 5G New Radio Systems:
Comparative Analysis Through Urban Measurements at 27 GHz", Network, vol. 6, no. 2,
article 26, 2026. DOI 10.3390/network6020026.
*Caveat.* The text says RMSE and mean absolute error are "around 10-12 dB" for all tools,
but the paper's own bar chart shows overall RMSE of roughly 12-15 dB, and only
distance-binned values are tabulated (its Table 8: mean absolute error 8.3-14.3 dB, RMSE
10.8-18.5 dB depending on tool and distance). Quote the tabulated values. Sionna tends to
overestimate received power; MATLAB is the most stable of the three. Diffraction on,
scattering and transmission off, concrete buildings.

**R8.** A. Deylamy, H. Abu Ali, N. Afraz, S. Ansari, B. Kizilkaya, "Measurement-Calibrated
RSRP Prediction for Real-World Search and Rescue Robots", accepted for 2026 IEEE Globecom
Workshops; https://eprints.gla.ac.uk/396630/. **Accepted manuscript; no DOI yet.**
RMSE uncalibrated / calibrated: MATLAB 21.5 / 11.3 dB, Sionna 25.1 / 11.4 dB, simple
log-distance model 18.0 / 9.9 dB (its Table II). Note that the plain log-distance model is
no worse than either ray tracer here. The authors list OpenStreetMap-only geometry, no
vegetation and no measured antenna pattern as limitations.

**R9.** L. Taus, R. Tsai, J. G. Andrews, "Optimal Transmitter Placement in Realistic Urban
Environments", arXiv:2604.28153 (version 3, September 2026). **Preprint, submitted.**
Greedy selection on a submodular objective, with a proven guarantee of at least 1 − 1/e
(about 63 %) of the best achievable value of that objective. Rate is
bandwidth × log2(1 + SINR/2). Candidate sites on a 10 m grid at 20 m above ground. The
scenes are those shipped with Sionna: about 1.1 × 1.1 km (San Francisco) and 1.0 × 1.1 km
(Florence). The gains quoted are against one operator's layout (+70.4 % mean, +88.0 % edge).

**R10.** G. Gemmi, R. Lo Cigno, L. Maccari, "On Cost-Effective, Reliable Coverage for LoS
Communications in Urban Areas", IEEE Transactions on Network and Service Management,
vol. 19, no. 3, pp. 2767-2779, 2022. DOI 10.1109/TNSM.2022.3190634.
Line of sight only, links up to 300 m, users at 1.5 m, base stations on building facades.
*Caveat.* The summary says 95 % coverage is reached at 75 base stations per km² when 4 % of
buildings may host one, while the discussion of its Figure 6 gives 90 % at 75 and 95 % at
105; check the figure before quoting. The authors call the results an optimistic bound
because only buildings obstruct.

## 3. Alternates

| # | Study | Why it may be useful |
|---|---|---|
| A1 | D. Shakya, D. Chizhik, J. Du, R. A. Valenzuela, T. S. Rappaport, "Dense Urban Outdoor-Indoor Coverage from 3.5 to 28 GHz", ICC 2022, pp. 932-937. DOI 10.1109/ICC45855.2022.9838919 | The same question (density and power per band, 3.5 / 7 / 14 / 28 GHz) answered with measurement-based statistical models instead of ray tracing, on a synthetic street grid with 12 sites per km². At 28 GHz with 1 W per polarisation, 90 % of outdoor users exceed 250 Mbps |
| A2 | F. Aghaei, M. Monemi, M. Rasti, M. Uysal, "FR3 for 6G Networks: A Comparative Study against FR1 and FR2 Across Diverse Environments", arXiv:2604.07482, 2026 (accepted for EuCNC 2026; preprint read) | Ray tracing (Wireless InSite; 6 reflections, 1 diffraction) at 4.6, 8.2, 15 and 28 GHz with 17 rooftop sites 350 m apart, on statistically generated city layouts. In its high-rise layout 8.2 GHz gives the best cell-edge rates |
| A3 | M. U. Sheikh, R. Jäntti, J. Hämäläinen, "Impact of Interference Suppression under Ray Tracing and 3GPP Street Canyon Model", IEEE VTC2020-Spring. DOI 10.1109/VTC2020-Spring48590.2020.9129448 | Ray tracing against the 3GPP street-canyon model at 28 GHz on a synthetic grid: mean received power −72.3 dBm against −69.3 dBm, mean SINR 2.6 dB against 8.4 dB. Shows the two approaches can differ by several dB in SINR |

## 4. Studies on Iraq

Bibliographic data confirmed in Crossref; content read by one reader only.

| # | Study | What it did |
|---|---|---|
| Q1 | S. Nafea, E. K. Hamza, "Design and Analysis WIMAX Network Based on Coverage Planning", Journal of Engineering (University of Baghdad), vol. 26, no. 2, pp. 99-110, 2020. DOI 10.31026/j.eng.2020.02.08 | WiMAX at 3.5 GHz over Baghdad with the ICS Telecom planning tool; 12 to 24 base stations. Not 5G, but the only Baghdad coverage-planning paper that could be opened |
| Q2 | A. M. Al-Kadhimi, "Investigating 5G Wireless Networks Deployment with Diverse Frequency Bands for Basra City", Diyala Journal of Engineering Sciences, vol. 17, no. 4, pp. 56-74, 2024. DOI 10.24237/djes.2024.17404 | 5G planning for Basra at 1.8, 2.1 and 3.6 GHz; abstract only. 1.8 GHz gave the best coverage |
| Q3 | H. J. Saadoon, T. M. Jamel, H. F. Khazaal, "The Effects of Different Weather Conditions on 5G Millimeter Waves Propagations at 38 GHz and 73 GHz for Kut-City in Iraq", Wasit Journal of Engineering Sciences, vol. 10, no. 2, pp. 20-33, 2022. DOI 10.31185/ejuow.Vol10.Iss2.274 | Statistical channel simulation (NYUSIM) with Iraqi weather data. (Author order differs between the article and its Crossref record.) |
| Q4 | Z. S. Hammed, S. Y. Ameen, S. R. M. Zeebaree, "Investigation of 5G Wireless Communication with Dust and Sand Storms", Journal of Communications, vol. 18, no. 1, pp. 36-46, 2023. DOI 10.12720/jcm.18.1.36-46 | Dust-storm attenuation at 28 and 73 GHz (NYUSIM). Relevant to the roadmap: dust is an Iraqi propagation factor that this project does not model |

Not opened, record only: A. Al-Shuwaili, T. M. Jamel, "5G Channel Characterization at
Millimeter-Wave for Baghdad City: An NYUSIM-based Approach", 18th International
Multi-Conference on Systems, Signals & Devices (SSD), pp. 468-473, 2021.
DOI 10.1109/SSD52085.2021.9429348. Worth obtaining: it is the one Baghdad millimetre-wave
paper found.

**No published ray-tracing coverage study of Baghdad was found, and none comparing 4G, 5G
and 6G candidate bands for any Iraqi city.**

## 5. What the literature means for this project

These are this review's readings of the studies, offered as starting points for the
student's own literature chapter, not as conclusions to copy. Points 3 and 8 rest on details
that were read once and not re-checked.

1. **The gap is real.** No study found answers the project's question: how many sites each
   of 1.8, 3.5, 8, 15 and 28 GHz needs to cover one real district, with the data rate each
   delivers. R2 compares coverage across bands from a fixed site grid; R9 selects sites
   greedily but at one band; R10 gives densities but for line of sight only. Combining the
   three is the project's contribution, and Baghdad adds a city nobody has studied this way.
2. **Expect large errors against reality.** Where ray tracers were compared with street
   measurements, typical absolute errors were 8-12 dB with operator-grade inputs (R7), and
   16-21 dB on uncalibrated OpenStreetMap geometry, falling to about 9 dB after calibration
   against measurements (R8). In R8 a simple distance law did as well as the ray tracers. The thesis should present site counts as estimates with this uncertainty,
   and agreement with 3GPP TR 38.901 within a few dB should not be expected or claimed.
3. **Geometry matters more than solver settings.** R6 reached close agreement only after
   correcting the building model with field measurements; a further study (Manukyan et al.,
   WCNC 2026, DOI 10.1109/WCNC65185.2026.11555460) found antenna height and orientation
   mattered more than solver options on OpenStreetMap-extruded scenes. This supports putting
   effort into building heights and site positions in Phase 2.
4. **Benchmarks for a sanity check.** Measured path-loss exponents near the 6G candidate
   bands are about 1.8-2.3 with line of sight and 2.6-2.7 without (R4, R5, R6), lower than
   the 3GPP UMi value of 3.19 without line of sight. Phase 7 can report the simulated
   exponents beside these.
5. **Rate models differ between studies.** Pure Shannon capacity (the project description)
   is the least conservative choice: R3 uses a factor 0.57 and a cap of 4.8 bit/s/Hz, R9 a
   3 dB penalty, A1 a 40 % overhead and a 3 dB penalty. Results are only comparable with
   other studies if the rate model is stated; reporting one such variant beside the Shannon
   value would make the comparison easier (a decision for the supervisor).
6. **Greedy selection is an accepted method**, with a known guarantee: for objectives of
   this type the greedy choice reaches at least 1 − 1/e of the best possible value for the
   same number of sites (G. L. Nemhauser, L. A. Wolsey, M. L. Fisher, "An analysis of
   approximations for maximizing submodular set functions—I", Mathematical Programming,
   vol. 14, pp. 265-294, 1978, DOI 10.1007/BF01588971; applied to transmitter placement in
   R9). That is a statement about coverage for a given number of sites, not a proof that
   the number of sites found is the minimum, so the project keeps the wording "the site
   count found by the greedy algorithm".
7. **Site densities in the literature**, for orientation: about 12 per km² (A1, 400 m
   spacing), about 18 per km² (R2, existing sites), 60-120 per km² for line-of-sight
   millimetre-wave coverage (R10). The ITU and 3GPP dense-urban evaluation layouts use
   200 m spacing, which corresponds to about 29 sites per km² on a hexagonal grid (computed).
8. **Antenna assumptions drive the higher bands.** R2, R3 and A2 let antenna arrays grow
   with frequency (equal physical size), which offsets part of the extra path loss. With
   identical antennas at all bands, as currently assumed here, the higher bands will look
   worse than in those studies. This is decision 2 in `docs/assumptions.md`, section 6.

## 6. Looked for but not verified

These may be useful but could not be opened; only their database records were seen.

- Lee, Choi, Kim, "Cell Coverage Analysis of 28 GHz Millimeter Wave in Urban Microcell
  Environment Using 3-D Ray Tracing", IEEE Trans. Antennas Propag., 2018,
  DOI 10.1109/TAP.2018.2797531.
- Hinga and Atayero, "Deterministic 5G mmWave Large-Scale 3D Path Loss Model for Lagos
  Island, Nigeria", IEEE Access, 2021, DOI 10.1109/ACCESS.2021.3114771.
- Zhang, Ryu, Subramanian, Sampath, "Coverage and channel characteristics of millimeter wave
  band using ray tracing", ICC 2015, DOI 10.1109/ICC.2015.7248516.
- A Nokia white paper on coverage of 7-15 GHz from existing sites (page not accessible).
