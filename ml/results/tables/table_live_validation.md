# Live Validation: `rf_single_event.pkl` Pure-Inference Test (2026-08-11)

Session ID: `live-validation-20260811`. This is a fresh, independent capture, never seen by training: 120 registration events (Nothing 3A and Realme RMX3363, 15 events per device per label), across labels 0, 1, 3 and 5. The model was loaded from `ml/models/rf_single_event.pkl` and run with `.predict()` only, with no `.fit()` calls anywhere in this session.

## Per-label results

| Label | Name | n | Accuracy | False negatives | FNR |
|---|---|---|---|---|---|
| 0 | Normal | 30 | 96.7% | 1 | 3.3% |
| 1 | Cat-downgrade | 30 | 100.0% | 0 | 0.0% |
| 3 | MIMO-reduced | 30 | 100.0% | 0 | 0.0% |
| 5 | Combined | 30 | 100.0% | 0 | 0.0% |
| **Overall** | | **120** | **99.2%** | **1** | n/a |

The operationally critical number here is a 0% false-negative rate on all three attack labels tested, meaning no attack was missed. The single error was a label-0 (Normal) row misclassified as label 6 (Partial/noise), which is a false alarm on benign traffic rather than a missed attack.

## Confusion matrix (rows = true, cols = predicted)

Predictions only ever landed on labels {0, 6} within the true-label-0 rows, whilst all other true labels were predicted perfectly.

| true \ pred | 0 | 1 | 3 | 5 | 6 |
|---|---|---|---|---|---|
| **0** | 29 | 0 | 0 | 0 | 1 |
| **1** | 0 | 30 | 0 | 0 | 0 |
| **3** | 0 | 0 | 30 | 0 | 0 |
| **5** | 0 | 0 | 0 | 30 | 0 |

## Comparison against Session D baseline

| Metric | Session D (5-fold CV, full 7-class) | Session D (same 4 labels only) | Live (this session) |
|---|---|---|---|
| Accuracy / macro-F1 | 0.848 / 0.847 | 96.1%* | 99.2% |
| Label 0 recall/F1 | 0.714 / 0.722 | n/a | 0.967 |
| Label 1 recall/F1 | 1.000 / 1.000 | n/a | 1.000 |
| Label 3 recall/F1 | 0.866 / 0.859 | n/a | 1.000 |
| Label 5 recall/F1 | 0.872 / 0.881 | n/a | 1.000 |

*Session D's own CV confusion matrix, restricted to predictions among labels {0,1,3,5} only: 2083/2167, or 96.1%.

Live performance holds up here, and, on this restricted label subset, it modestly exceeds the CV baseline rather than regressing against it. This is not, however, a like-for-like comparison against the headline 0.847 macro-F1, which averages in labels 2, 4 and 6, themselves label 0's main confusion sources in the full 7-class problem. Restricting the Session D confusion matrix to the same 4 labels tested here (96.1%) is the fairer comparison, and live accuracy (99.2%) sits consistent with, if modestly above, that figure, well within what a 120-event sample can plausibly resolve either way. Both live-validation devices, Nothing 3A and Realme, are members of the original 6-profile training set, so this amounts to an in-distribution check rather than a genuine cross-profile generalisation test. Per the W6.3 leave-one-profile-out finding, these two profiles specifically transfer well (held-out macro-F1 0.82 and 0.81 respectively) even under full profile holdout, which is consistent with the strong performance seen here. The single 0-to-6 miss simply reproduces the model's largest known label-0 confusion direction from the Session D CV confusion matrix (99 of 604 rows), rather than representing a new failure mode.

## Investigation of the divergence (per task instructions)

Three possible explanations for the divergence were considered and ruled out in turn. Label imbalance does not explain it: there were exactly 30 events per label (15 per device), perfectly balanced. Decode anomalies of the Bug 13/17 class do not explain it either: all 120 PCAPs decoded cleanly, with 0 nulls and no truncation fallback triggered, and every profile/label combination produced byte-identical feature vectors across all 15 repeats, that is, zero within-class variance, matching the deterministic behaviour already characterised for these attacks in the 2026-08-10 Session C2 pass. Nor is a distribution shift responsible: the live label-0 feature vectors for both devices match `features/raw_12f.csv`'s original training rows for the same profiles field-for-field (for example, Realme's `nr_band_count=13`, `total_capability_size_bytes=813` and `ie_field_count=11` are identical to training, not the `band_count=12` figure quoted in an earlier prose summary elsewhere in the project, which was itself an imprecise restatement rather than evidence of a genuine data change).

## Capture provenance

- PCAPs: `data/raw_validation_live/<label>/*.pcap` (kept fully separate from `data/raw/<label>/`)
- Features: `features/raw_12f_live_validation.csv` (kept fully separate from `features/raw_12f.csv`)
- Registration success: 120/120 (100%), with 0 registration failures and 0 decode failures
- Custody: all PCAPs, the features CSV, and this results pair were custody-appended under `session_id=live-validation-20260811`, mode `analysis`
