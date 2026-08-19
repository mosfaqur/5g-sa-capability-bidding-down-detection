# Multi-Model Benchmark Comparison

This benchmark runs 5-fold stratified cross-validation (`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`) on `features/raw_12f.csv` (a56 filtered, 4,225 rows, 12 features, 7 classes), under the same protocol and the same 12-feature vector as the frozen single-event RF result in `ml/results/metrics.json`. The RandomForest row below, at macro-F1 0.8475, reproduces that result as a consistency check.

Native XGBoost is included here, installed on the 12th of August 2026 once outbound internet access was restored on this machine. `GradientBoostingClassifier` was the original same-day substitute before XGBoost became available, and it has been retained as its own row, a legitimate independent result rather than a placeholder, even now that XGBoost runs.

| Model | Macro-F1 | Macro-Precision | Macro-Recall | Full-fit train time (s) | Per-event inference latency (ms, mean) | Per-event inference latency (ms, p95) |
|---|---|---|---|---|---|---|
| RandomForest | 0.8475 | 0.8492 | 0.8476 | 0.305 | 5.3919 | 5.5033 |
| ExtraTrees | 0.8482 | 0.8496 | 0.8483 | 0.219 | 5.4168 | 5.5383 |
| GradientBoosting | 0.8514 | 0.8544 | 0.8511 | 1.212 | 0.3513 | 0.3702 |
| XGBoost | 0.8553 | 0.8584 | 0.8549 | 3.097 | 0.2554 | 0.2732 |
| MLP | 0.8267 | 0.8682 | 0.8182 | 0.924 | 0.0739 | 0.0775 |
| SVM_RBF | 0.7805 | 0.8296 | 0.7848 | 0.088 | 0.0853 | 0.0876 |
| LogisticRegression | 0.8103 | 0.8464 | 0.8060 | 0.043 | 0.0291 | 0.0305 |

## Per-class recall (mean across 5 folds)

| Model | 0 Normal | 1 Cat-downgrade | 2 CA-disabled | 3 MIMO-reduced | 4 VoNR-denied | 5 Combined | 6 Partial/noise |
|---|---|---|---|---|---|---|---|
| RandomForest | 0.714 | 1.000 | 0.878 | 0.866 | 0.853 | 0.872 | 0.751 |
| ExtraTrees | 0.720 | 1.000 | 0.879 | 0.866 | 0.853 | 0.874 | 0.746 |
| GradientBoosting | 0.781 | 1.000 | 0.869 | 0.861 | 0.863 | 0.859 | 0.725 |
| XGBoost | 0.755 | 1.000 | 0.874 | 0.859 | 0.861 | 0.865 | 0.770 |
| MLP | 0.682 | 1.000 | 0.858 | 0.834 | 0.846 | 0.864 | 0.643 |
| SVM_RBF | 0.636 | 1.000 | 0.835 | 0.834 | 0.820 | 1.000 | 0.370 |
| LogisticRegression | 0.543 | 1.000 | 0.835 | 0.834 | 0.763 | 0.990 | 0.677 |

All models trained/evaluated under the identical CV protocol used for the frozen single-event RF result; inference latency measured as the mean/p95 of 200 single-row `predict()` calls on the fully-fitted model. Feature-scale-sensitive models (MLP, SVM-RBF, LogisticRegression) were standardised per fold; tree ensembles were not.
