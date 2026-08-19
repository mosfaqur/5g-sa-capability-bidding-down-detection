# W4.4: Cross-Layer (RRC-vs-N2) Divergence Catalogue

Restricted to real handsets only, Pixel 8 and Nothing 3A, this table draws on `features/xlayer.csv` (1418 rows), in which each N2 event is paired against its IMSI's persisted per-IMSI case-a RRC reference (a non-circular join, following the "Cached-reattach (case b) live validation" finding). `capability_size_delta` and `container_hash_match` are excluded from this table, since both are None on every row by design (see the module docstring), leaving 9 of the 11 features evaluated here, which matches the Session D cross-layer model's own 9-feature training set.

| Mode | n | Cross-layer features that fire | Mean num_fields_mismatched | No cross-layer trace? |
|---|---|---|---|---|
| 0 Normal | 204 | none | 0.0 | Yes, flagged |
| 1 Cat-downgrade | 204 | ue_category_delta (nonzero 100.0%, mean|Δ|=15.00) | 1.0 | No |
| 2 CA-disabled | 204 | ca_supported_match (mismatch 100.0%); ca_band_count_delta (nonzero 100.0%, mean|Δ|=1.51) | 2.01 | No |
| 3 MIMO-reduced | 203 | mimo_dl_delta (nonzero 100.0%, mean|Δ|=3.00); mimo_ul_delta (nonzero 50.7%, mean|Δ|=0.51) | 1.51 | No |
| 4 VoNR-denied | 203 | vonr_supported_match (mismatch 49.3%) | 0.49 | No |
| 5 Combined | 200 | ca_supported_match (mismatch 100.0%); vonr_supported_match (mismatch 50.0%); ca_band_count_delta (nonzero 100.0%, mean|Δ|=1.50); mimo_dl_delta (nonzero 100.0%, mean|Δ|=3.00); mimo_ul_delta (nonzero 50.0%, mean|Δ|=0.50) | 4.0 | No |
| 6 Partial/noise | 200 | none | 0.02 | Yes, flagged |

## Per-feature fire rate by mode

| Mode | ca_supported_match | vonr_supported_match | ue_category_delta | ca_band_count_delta | mimo_dl_delta | mimo_ul_delta | nr_band_count_delta | ie_field_count_delta |
|---|---|---|---|---|---|---|---|---|
| 0 Normal | 0% mismatch | 0% mismatch | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) |
| 1 Cat-downgrade | 0% mismatch | 0% mismatch | 100% nonzero (μ|Δ|=15.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) |
| 2 CA-disabled | 100% mismatch | 0% mismatch | 0% nonzero (μ|Δ|=0.00) | 100% nonzero (μ|Δ|=1.51) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.01) | 0% nonzero (μ|Δ|=0.00) |
| 3 MIMO-reduced | 0% mismatch | 0% mismatch | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 100% nonzero (μ|Δ|=3.00) | 51% nonzero (μ|Δ|=0.51) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) |
| 4 VoNR-denied | 0% mismatch | 49% mismatch | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) |
| 5 Combined | 100% mismatch | 50% mismatch | 0% nonzero (μ|Δ|=0.00) | 100% nonzero (μ|Δ|=1.50) | 100% nonzero (μ|Δ|=3.00) | 50% nonzero (μ|Δ|=0.50) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.00) |
| 6 Partial/noise | 0% mismatch | 0% mismatch | 0% nonzero (μ|Δ|=0.01) | 0% nonzero (μ|Δ|=0.01) | 0% nonzero (μ|Δ|=0.00) | 0% nonzero (μ|Δ|=0.01) | 0% nonzero (μ|Δ|=0.03) | 0% nonzero (μ|Δ|=0.01) |

## Notes

Mode 4 (VoNR-denied) fires at only around 49% overall, although this is not noise: it splits cleanly by profile, {'nothing3a': '100% mismatch', 'pixel8': '0% mismatch'}. Pixel 8 never advertises VoNR natively (`vonr_supported=False` on every baseline capture, confirmed elsewhere in this project), so stripping an already-absent VoNR bit is a genuine no-op for that device, whilst Nothing 3A does support VoNR natively, so the attack is fully visible there. This is a real, device-dependent finding rather than a decode defect.

Modes 0 (Normal) and 6 (Partial/noise) leave no cross-layer trace, as expected: mode 0 carries no attack at all, whilst mode 6's target field (`supportedROHC-Profiles`) sits outside all 11 cross-layer features by design, which matches the same finding already established for the single-view 12-feature vector in the W4.1 attack catalogue.
