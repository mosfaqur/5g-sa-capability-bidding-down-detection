# W4.2: Feature Significance (Mann-Whitney U, label 0 vs each attack mode)

This table covers all 6 study profiles, with a56 excluded per Bug 21, and boolean features cast to 0/1. Effect size is rank-biserial correlation, r = 1 minus 2U/(n1·n2), on a range of [-1,1], where |r|≥0.5 is large, 0.3 to 0.5 is medium, 0.1 to 0.3 is small and below 0.1 is negligible.

| Feature | Mode | n(normal) | n(mode) | U | p-value | effect r | note |
|---|---|---|---|---|---|---|---|
| ue_category | 1 Cat-down | 604 | 605 | 365420 | 2.498e-238 | -1.000 |  |
| ue_category | 2 CA-dis | 604 | 604 | 182710 | 9.516e-01 | -0.002 |  |
| ue_category | 3 MIMO-red | 604 | 604 | 182710 | 9.516e-01 | -0.002 |  |
| ue_category | 4 VoNR-den | 604 | 604 | 182710 | 9.516e-01 | -0.002 |  |
| ue_category | 5 Combined | 604 | 601 | 182404 | 8.552e-01 | -0.005 |  |
| ue_category | 6 Partial | 604 | 603 | 183514 | 7.760e-01 | -0.008 |  |
| ca_supported | 1 Cat-down | 604 | 605 | 182660 | 9.899e-01 | 0.000 |  |
| ca_supported | 2 CA-dis | 604 | 604 | 334616 | 6.266e-190 | -0.834 |  |
| ca_supported | 3 MIMO-red | 604 | 604 | 182408 | 1.000e+00 | 0.000 |  |
| ca_supported | 4 VoNR-den | 604 | 604 | 182408 | 1.000e+00 | 0.000 |  |
| ca_supported | 5 Combined | 604 | 601 | 332954 | 2.493e-189 | -0.834 |  |
| ca_supported | 6 Partial | 604 | 603 | 182156 | 9.899e-01 | -0.000 |  |
| ca_band_count | 1 Cat-down | 604 | 605 | 182712 | 9.998e-01 | -0.000 |  |
| ca_band_count | 2 CA-dis | 604 | 604 | 334616 | 3.612e-181 | -0.834 |  |
| ca_band_count | 3 MIMO-red | 604 | 604 | 182660 | 9.604e-01 | -0.001 |  |
| ca_band_count | 4 VoNR-den | 604 | 604 | 182660 | 9.604e-01 | -0.001 |  |
| ca_band_count | 5 Combined | 604 | 601 | 332954 | 1.534e-180 | -0.834 |  |
| ca_band_count | 6 Partial | 604 | 603 | 183364 | 8.033e-01 | -0.007 |  |
| mimo_layers_dl | 1 Cat-down | 604 | 605 | 182610 | 9.843e-01 | 0.001 |  |
| mimo_layers_dl | 2 CA-dis | 604 | 604 | 182408 | 1.000e+00 | 0.000 |  |
| mimo_layers_dl | 3 MIMO-red | 604 | 604 | 334616 | 2.072e-181 | -0.834 |  |
| mimo_layers_dl | 4 VoNR-den | 604 | 604 | 182408 | 1.000e+00 | 0.000 |  |
| mimo_layers_dl | 5 Combined | 604 | 601 | 332954 | 8.789e-181 | -0.834 |  |
| mimo_layers_dl | 6 Partial | 604 | 603 | 182206 | 9.842e-01 | -0.001 |  |
| mimo_layers_ul | 1 Cat-down | 604 | 605 | 182812 | 9.837e-01 | -0.001 |  |
| mimo_layers_ul | 2 CA-dis | 604 | 604 | 182408 | 1.000e+00 | 0.000 |  |
| mimo_layers_ul | 3 MIMO-red | 604 | 604 | 244016 | 2.828e-55 | -0.338 |  |
| mimo_layers_ul | 4 VoNR-den | 604 | 604 | 182710 | 9.516e-01 | -0.002 |  |
| mimo_layers_ul | 5 Combined | 604 | 601 | 242804 | 4.901e-55 | -0.338 |  |
| mimo_layers_ul | 6 Partial | 604 | 603 | 183514 | 7.760e-01 | -0.008 |  |
| vonr_supported | 1 Cat-down | 604 | 605 | 182608 | 9.837e-01 | 0.001 |  |
| vonr_supported | 2 CA-dis | 604 | 604 | 182408 | 1.000e+00 | 0.000 |  |
| vonr_supported | 3 MIMO-red | 604 | 604 | 182106 | 9.516e-01 | 0.002 |  |
| vonr_supported | 4 VoNR-den | 604 | 604 | 303208 | 5.798e-132 | -0.662 |  |
| vonr_supported | 5 Combined | 604 | 601 | 301702 | 1.776e-131 | -0.662 |  |
| vonr_supported | 6 Partial | 604 | 603 | 180698 | 7.760e-01 | 0.008 |  |
| volte_supported | 1 Cat-down | 604 | 605 | n/a | n/a | 0.000 | constant, identical, no variance |
| volte_supported | 2 CA-dis | 604 | 604 | n/a | n/a | 0.000 | constant, identical, no variance |
| volte_supported | 3 MIMO-red | 604 | 604 | n/a | n/a | 0.000 | constant, identical, no variance |
| volte_supported | 4 VoNR-den | 604 | 604 | n/a | n/a | 0.000 | constant, identical, no variance |
| volte_supported | 5 Combined | 604 | 601 | n/a | n/a | 0.000 | constant, identical, no variance |
| volte_supported | 6 Partial | 604 | 603 | n/a | n/a | 0.000 | constant, identical, no variance |
| nr_band_count | 1 Cat-down | 604 | 605 | 182562 | 9.801e-01 | 0.001 |  |
| nr_band_count | 2 CA-dis | 604 | 604 | 182308 | 9.865e-01 | 0.001 |  |
| nr_band_count | 3 MIMO-red | 604 | 604 | 182510 | 9.863e-01 | -0.001 |  |
| nr_band_count | 4 VoNR-den | 604 | 604 | 182510 | 9.863e-01 | -0.001 |  |
| nr_band_count | 5 Combined | 604 | 601 | 182354 | 8.847e-01 | -0.005 |  |
| nr_band_count | 6 Partial | 604 | 603 | 182764 | 9.111e-01 | -0.004 |  |
| psm_supported | 1 Cat-down | 604 | 605 | n/a | n/a | 0.000 | constant, identical, no variance |
| psm_supported | 2 CA-dis | 604 | 604 | n/a | n/a | 0.000 | constant, identical, no variance |
| psm_supported | 3 MIMO-red | 604 | 604 | n/a | n/a | 0.000 | constant, identical, no variance |
| psm_supported | 4 VoNR-den | 604 | 604 | n/a | n/a | 0.000 | constant, identical, no variance |
| psm_supported | 5 Combined | 604 | 601 | n/a | n/a | 0.000 | constant, identical, no variance |
| psm_supported | 6 Partial | 604 | 603 | n/a | n/a | 0.000 | constant, identical, no variance |
| total_capability_size_bytes | 1 Cat-down | 604 | 605 | 182562 | 9.803e-01 | 0.001 |  |
| total_capability_size_bytes | 2 CA-dis | 604 | 604 | 212716 | 4.808e-07 | -0.166 |  |
| total_capability_size_bytes | 3 MIMO-red | 604 | 604 | 187560 | 3.897e-01 | -0.028 |  |
| total_capability_size_bytes | 4 VoNR-den | 604 | 604 | 192560 | 9.060e-02 | -0.056 |  |
| total_capability_size_bytes | 5 Combined | 604 | 601 | 217604 | 1.875e-09 | -0.199 |  |
| total_capability_size_bytes | 6 Partial | 604 | 603 | 182814 | 9.057e-01 | -0.004 |  |
| ie_field_count | 1 Cat-down | 604 | 605 | 182562 | 9.801e-01 | 0.001 |  |
| ie_field_count | 2 CA-dis | 604 | 604 | 182308 | 9.865e-01 | 0.001 |  |
| ie_field_count | 3 MIMO-red | 604 | 604 | 182510 | 9.863e-01 | -0.001 |  |
| ie_field_count | 4 VoNR-den | 604 | 604 | 182510 | 9.863e-01 | -0.001 |  |
| ie_field_count | 5 Combined | 604 | 601 | 182354 | 8.847e-01 | -0.005 |  |
| ie_field_count | 6 Partial | 604 | 603 | 182764 | 9.111e-01 | -0.004 |  |
| session_timestamp_delta | 1 Cat-down | 604 | 605 | 173170 | 1.160e-01 | 0.052 |  |
| session_timestamp_delta | 2 CA-dis | 604 | 604 | 167958 | 1.715e-02 | 0.079 |  |
| session_timestamp_delta | 3 MIMO-red | 604 | 604 | 162986 | 1.357e-03 | 0.106 |  |
| session_timestamp_delta | 4 VoNR-den | 604 | 604 | 160323 | 2.694e-04 | 0.121 |  |
| session_timestamp_delta | 5 Combined | 604 | 601 | 160721 | 5.801e-04 | 0.114 |  |
| session_timestamp_delta | 6 Partial | 604 | 603 | 161818 | 8.062e-04 | 0.111 |  |

## Features flagged as non-discriminative (max |effect r| < 0.05 across all 6 modes)

- ie_field_count: max |r| = 0.0047
- nr_band_count: max |r| = 0.0047
- psm_supported: max |r| = 0.0000
- volte_supported: max |r| = 0.0000

`volte_supported` and `psm_supported` are fixed `False` everywhere by construction, since no Long Term Evolution (LTE) or NAS Power Saving Mode (PSM) concept is reachable from a New Radio (NR) RRC capability container, as extract_features.py's own docstring notes; they are kept only for CSV schema completeness, so their zero effect size is expected rather than a finding. `ie_field_count` and `nr_band_count`, by contrast, are genuinely non-discriminative for these 6 attack modes, because none of the implemented modifiers add or remove IEs, or touch the band list itself: only CA combinations, MIMO layer values, the VoNR bit and accessStratumRelease are touched (see the W4.1 attack catalogue).

`session_timestamp_delta` shows small but statistically significant effects on 4 of the 6 modes (r=0.05 to 0.12), which sit well below the conventional 'small' effect-size threshold of |r|<0.1 and most likely reflect a collection-order or session-timing artefact, since different modes were collected in different campaign runs with different inter-event pacing, rather than a genuine protocol signal of the attack itself. This feature should therefore be treated with caution if used for training.
