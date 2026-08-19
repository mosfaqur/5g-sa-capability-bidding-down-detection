# W4.3: Intra-class Consistency

Table A sets out the coefficient of variation (σ/|μ|) of each feature within each (mode, profile) group, across its repeated runs, against a target of at least 100 events per class per profile. The a56 profile is kept for completeness, although it carries only label-0 data (n=96, below target, per Bug 21). Boolean features (`ca_supported`, `vonr_supported`, `volte_supported`, `psm_supported`) are cast to 0/1, and CoV is undefined (n/a) whenever the group mean is 0, that is, fully constant at the False/0 value. Cells with a CoV above 0.3 on a continuous feature are flagged below the table as showing high within-class variance.

| mode | profile | n | ue_category | ca_supported | ca_band_count | mimo_layers_dl | mimo_layers_ul | vonr_supported | volte_supported | nr_band_count | psm_supported | total_capability_size_bytes | ie_field_count | session_timestamp_delta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 Normal | sw-std | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 0 Normal | sw-ext | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 0 Normal | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 0 Normal | pixel8 | 104 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.320 |
| 0 Normal | realme | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.355 |
| 0 Normal | nothing3a | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.231 |
| 0 Normal | a56 | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.644 |
| 1 Cat-down | sw-std | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 1 Cat-down | sw-ext | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 1 Cat-down | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 1 Cat-down | pixel8 | 104 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.327 |
| 1 Cat-down | realme | 101 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.272 |
| 1 Cat-down | nothing3a | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.231 |
| 2 CA-dis | sw-std | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 2 CA-dis | sw-ext | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 2 CA-dis | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 2 CA-dis | pixel8 | 104 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.288 |
| 2 CA-dis | realme | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.232 |
| 2 CA-dis | nothing3a | 100 | 0.006 | n/a | n/a | 0.000 | 0.000 | 0.000 | n/a | 0.030 | n/a | 0.008 | 0.010 | 0.231 |
| 3 MIMO-red | sw-std | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.247 |
| 3 MIMO-red | sw-ext | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 3 MIMO-red | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.234 |
| 3 MIMO-red | pixel8 | 103 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.315 |
| 3 MIMO-red | realme | 101 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.260 |
| 3 MIMO-red | nothing3a | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.231 |
| 4 VoNR-den | sw-std | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.232 |
| 4 VoNR-den | sw-ext | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 4 VoNR-den | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.234 |
| 4 VoNR-den | pixel8 | 103 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.292 |
| 4 VoNR-den | realme | 101 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.259 |
| 4 VoNR-den | nothing3a | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.231 |
| 5 Combined | sw-std | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.232 |
| 5 Combined | sw-ext | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 5 Combined | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 5 Combined | pixel8 | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.277 |
| 5 Combined | realme | 101 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.272 |
| 5 Combined | nothing3a | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.232 |
| 6 Partial | sw-std | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.232 |
| 6 Partial | sw-ext | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.233 |
| 6 Partial | sw-min | 100 | 0.000 | n/a | n/a | 0.000 | 0.000 | n/a | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.248 |
| 6 Partial | pixel8 | 100 | 0.006 | 0.000 | 0.050 | 0.000 | 0.050 | 10.000 | n/a | 0.032 | n/a | 0.029 | 0.008 | 0.260 |
| 6 Partial | realme | 103 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.004 | 0.000 | 0.373 |
| 6 Partial | nothing3a | 100 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | n/a | 0.000 | n/a | 0.000 | 0.000 | 0.231 |

## Cells flagged as high within-class variance (continuous feature, CoV > 0.3)

| Mode | Profile | Feature | CoV | n |
|---|---|---|---|---|
| 0 Normal | pixel8 | session_timestamp_delta | 0.32 | 104 |
| 0 Normal | realme | session_timestamp_delta | 0.355 | 100 |
| 0 Normal | a56 | session_timestamp_delta | 0.644 | 96 |
| 1 Cat-down | pixel8 | session_timestamp_delta | 0.327 | 104 |
| 3 MIMO-red | pixel8 | session_timestamp_delta | 0.315 | 103 |
| 6 Partial | realme | session_timestamp_delta | 0.373 | 103 |

Table B, by contrast, sets out σ of each feature's per-profile mean across the 6 study profiles, per mode, as a measure of the cross-device consistency of the attack's signature (a56 excluded). A near-zero σ means that every profile's baseline or attacked value for that feature agrees, whilst a large σ means the feature's value remains profile-dependent even under the same attack label. This is expected for features with real device diversity, such as `nr_band_count` and `total_capability_size_bytes`, both of which vary by device fingerprint regardless of the attack applied.

| mode | ue_category | ca_supported | ca_band_count | mimo_layers_dl | mimo_layers_ul | vonr_supported | volte_supported | nr_band_count | psm_supported | total_capability_size_bytes | ie_field_count | session_timestamp_delta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 Normal | 0.516 | 0.408 | 0.632 | 1.329 | 0.516 | 0.516 | 0.000 | 7.266 | 0.000 | 495.123 | 3.251 | 6.863 |
| 1 Cat-down | 0.000 | 0.408 | 0.632 | 1.329 | 0.516 | 0.516 | 0.000 | 7.266 | 0.000 | 495.123 | 3.251 | 7.159 |
| 2 CA-dis | 0.514 | 0.000 | 0.000 | 1.329 | 0.516 | 0.516 | 0.000 | 7.268 | 0.000 | 485.977 | 3.252 | 7.442 |
| 3 MIMO-red | 0.516 | 0.408 | 0.632 | 0.000 | 0.000 | 0.516 | 0.000 | 7.266 | 0.000 | 494.840 | 3.251 | 8.399 |
| 4 VoNR-den | 0.516 | 0.408 | 0.632 | 1.329 | 0.516 | 0.000 | 0.000 | 7.266 | 0.000 | 494.530 | 3.251 | 9.324 |
| 5 Combined | 0.516 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 7.266 | 0.000 | 485.188 | 3.251 | 10.093 |
| 6 Partial | 0.514 | 0.408 | 0.629 | 1.329 | 0.514 | 0.514 | 0.000 | 7.248 | 0.000 | 494.201 | 3.248 | 11.137 |

## Boolean-feature anomalies (minority value <5% of group, not captured by CoV)

| Mode | Profile | Feature | Minority-value count | n | Note |
|---|---|---|---|---|---|
| 6 Partial | pixel8 | vonr_supported | 1 | 100 | Likely a single-event decode/capture anomaly rather than a real device-behaviour change, and outside the label's targeted field in any case |
