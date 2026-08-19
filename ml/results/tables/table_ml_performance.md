# Table: Per-Class Classification Performance (W5.1/W5.2/W5.3)

The single-event Random Forest (RF), a 12-feature N2-only baseline, and the sliding-window RF (N=3, 36 features) are both trained on the full 6-profile dataset (4,225 and 3,783 rows respectively). The cross-layer consistency RF, using 9 of 11 features and restricted to real handsets only, Pixel 8 and Nothing 3A, with capability_size_delta and container_hash_match excluded per the project's testbed architecture notes, is trained on a smaller 1,418 rows. The final comparison column is single-event F1 minus cross-layer F1, so a positive value means the single-view model scores higher on that class.

| Label | Single-event P | Single-event R | Single-event F1 | Window P | Window R | Window F1 | Cross-layer P | Cross-layer R | Cross-layer F1 | Single-view − Cross-layer F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 Normal | 0.731 | 0.714 | 0.722 | 0.818 | 0.830 | 0.824 | 0.403 | 1.000 | 0.575 | +0.147 |
| 1 Cat-downgrade | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | +0.000 |
| 2 CA-disabled | 0.873 | 0.877 | 0.875 | 0.864 | 0.867 | 0.866 | 1.000 | 1.000 | 1.000 | -0.125 |
| 3 MIMO-reduced | 0.853 | 0.866 | 0.859 | 0.886 | 0.867 | 0.876 | 1.000 | 1.000 | 1.000 | -0.141 |
| 4 VoNR-denied | 0.844 | 0.853 | 0.848 | 0.874 | 0.870 | 0.872 | 0.990 | 0.493 | 0.658 | +0.191 |
| 5 Combined | 0.890 | 0.872 | 0.881 | 0.883 | 0.857 | 0.870 | 1.000 | 1.000 | 1.000 | -0.119 |
| 6 Partial/noise | 0.741 | 0.751 | 0.746 | 0.783 | 0.811 | 0.797 | 0.000 | 0.000 | 0.000 | +0.746 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Overall** | | | **0.848 acc / 0.847 macro-F1** | | | **0.872 acc / 0.872 macro-F1** | | | **0.786 acc / 0.748 macro-F1** | +0.100 |
