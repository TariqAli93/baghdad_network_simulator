# Height sensitivity: tahrir_bab_al_sharqi, nr_3500

**Illustrative run on a development fixture with unapproved height models. It shows how strongly the results depend on building heights; none of these numbers is a finding about Baghdad.**

- Sites: 4 rooftop positions on buildings with observed or storey-based heights, antenna 3.0 m above the roof.
- Receivers: 10.0 m cells at 1.5 m; 1e+08 rays per site; 2 reflections + diffraction; seed 1.
- Coverage target for the greedy selection: 95 %.

## Geometry and propagation

| Height model | Mean building height | Line of sight to any site | Reached only by diffraction | Not reached by any site | Median path loss (best site) |
|---|---|---|---|---|---|
| flat_9m | 9.1 m | 85.6 % | 3.0 % | 0.0 % | 93.6 dB |
| low_rise_2_to_4 | 9.1 m | 80.3 % | 3.4 % | 0.0 % | 94.2 dB |
| mixed_1_to_8 | 13.5 m | 67.2 % | 4.5 % | 0.0 % | 96.2 dB |
| lognormal_10m | 11.4 m | 75.0 % | 2.8 % | 0.0 % | 94.8 dB |

## Coverage and sites needed

Coverage = share of outdoor cells whose path loss to the best site is at most the threshold. The threshold stands for transmit power plus antenna gains minus the required received power, which is not decided yet, so several are shown.

| Height model | 110 dB: coverage, all sites | 110 dB: sites for target | 120 dB: coverage, all sites | 120 dB: sites for target | 130 dB: coverage, all sites | 130 dB: sites for target |
|---|---|---|---|---|---|---|
| flat_9m | 97.6 % | 2 | 99.9 % | 2 | 100.0 % | 1 |
| low_rise_2_to_4 | 96.3 % | 3 | 99.5 % | 2 | 100.0 % | 1 |
| mixed_1_to_8 | 91.2 % | not reached with 3 | 97.0 % | 3 | 98.6 % | 2 |
| lognormal_10m | 94.6 % | not reached with 3 | 98.2 % | 2 | 99.4 % | 1 |

## Sites used

| Site | Building | Roof height | Height category |
|---|---|---|---|
| site-001 | way/919688856 | 55.0 m | observed |
| site-002 | way/1154123513 | 15.0 m | observed |
| site-003 | way/645196998 | 12.0 m | observed |
| site-004 | way/939812415 | 10.0 m | observed |
