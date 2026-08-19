# Table: Open-Set Held-Out-Mode Detection (Train Labels 0-4, Detect 5-6)

This table tests generalisation to attack modes absent from training. The cross-layer model did not transfer better than the single-view model here, contrary to the W5.3 prediction, and is discussed further in Chapter 5.

| Metric | Single-view | Cross-layer |
|---|---|---|
| n_train | 3021 | 1018 |
| n_test | 1204 | 400 |
| Overall detection rate | 0.593 | 0.502 |
| Label 5 (Combined) detection rate | 0.895 | 1.000 |
| Label 6 (Partial/noise) detection rate | 0.292 | 0.005 |
| Cross-layer transfers better than single-view? | No | |
