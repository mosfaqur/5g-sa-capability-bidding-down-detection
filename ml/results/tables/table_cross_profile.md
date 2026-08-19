# Table: Cross-Profile (Leave-One-Profile-Out) Generalisation (W6.3)

This table reports per-class F1 when each profile is held out entirely: the model is trained on the remaining 5 profiles and tested only on the held-out profile's own rows. Sigma is the standard deviation of that class's F1 across the 6 held-out folds, and a value above 0.05 is flagged per the project's threshold. All 7 classes are flagged here, and the causal breakdown is discussed at length elsewhere in the project's documentation: in short, sw-min and pixel8 collapse because device-fixed traits alias with attack-target features once that device's own baseline is withheld from training.

| Label | nothing3a | pixel8 | realme | sw-std | sw-ext | sw-min | sigma | flagged |
|---|---|---|---|---|---|---|---|---|
| 0 Normal | 0.655 | 0.000 | 0.000 | 0.000 | 0.408 | 0.000 | 0.261 | yes |
| 1 Cat-downgrade | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.373 | yes |
| 2 CA-disabled | 1.000 | 0.990 | 1.000 | 0.276 | 1.000 | 0.000 | 0.413 | yes |
| 3 MIMO-reduced | 1.000 | 0.000 | 1.000 | 0.400 | 1.000 | 0.000 | 0.453 | yes |
| 4 VoNR-denied | 1.000 | 0.402 | 1.000 | 0.000 | 1.000 | 0.000 | 0.453 | yes |
| 5 Combined | 1.000 | 0.990 | 1.000 | 0.704 | 1.000 | 0.250 | 0.278 | yes |
| 6 Partial/noise | 0.091 | 0.020 | 0.673 | 0.000 | 0.402 | 0.000 | 0.255 | yes |
|---|---|---|---|---|---|---|---|---|
| **macro-F1 (held-out profile)** | **0.821** | **0.486** | **0.810** | **0.340** | **0.830** | **0.036** |  |  |
