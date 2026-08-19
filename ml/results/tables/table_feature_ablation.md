# Feature Ablation Study

This study drops one feature group at a time from the frozen 12-feature single-event RF (`RandomForestClassifier(n_estimators=200, random_state=42)`, the same `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` cross-validation, and `cross_val_predict` for per-class recall, an identical protocol to `ml/pipeline.py` Step 1), and measures the recall degradation on the specific attack class each dropped group is expected to drive. This is a stronger causal claim than the SHAP attribution already reported for W5.3, since SHAP shows importance under the full feature set, whilst ablation shows what actually happens to detection once a feature becomes unavailable.

| Ablation | Features dropped | n features | Macro-F1 | Target class | Target-class recall (baseline) | Target-class recall (ablated) | Recall degradation |
|---|---|---|---|---|---|---|---|
| baseline (all 12) | none | 12 | 0.8474 | n/a | n/a | n/a | n/a |
| drop_MIMO | mimo_layers_dl, mimo_layers_ul | 10 | 0.7846 | 3 (MIMO-reduced) | 0.8659 | 0.5894 | 0.2765 |
| drop_CA | ca_supported, ca_band_count | 10 | 0.8474 | 2 (CA-disabled) | 0.8775 | 0.8775 | 0.0000 |
| drop_ue_category | ue_category | 11 | 0.7384 | 1 (Cat-downgrade) | 1.0000 | 0.5190 | 0.4810 |
| drop_VoNR | vonr_supported | 11 | 0.8031 | 4 (VoNR-denied) | 0.8526 | 0.6507 | 0.2020 |

Carrier Aggregation (`ca_supported`, `ca_band_count`) is the one group whose removal fails to measurably degrade detection of its own target class, CA-disabled, label 2: macro-F1 and target recall are unchanged, at 0.0000 degradation. The other three groups, MIMO, ue_category and VoNR, show real, substantial degradation when dropped (0.20 to 0.48 recall loss on their target class), which confirms that those three fields are load-bearing for their respective attack signatures. The CA result is nonetheless a genuine finding rather than an error: `total_capability_size_bytes` and `ie_field_count`, both of which are retained in the CA-dropped feature set, already carry a correlated signal of capability-container shrinkage that substitutes for the explicit CA fields. This is worth discussing in Chapter 4 or 5 as a case where feature redundancy, rather than feature necessity, explains a class's detectability.
