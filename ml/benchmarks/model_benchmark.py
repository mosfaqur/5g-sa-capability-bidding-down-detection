#!/usr/bin/env python3
"""Multi-model benchmark comparison (post-Session-F addendum item 1).

Runs identical 5-fold stratified CV on raw_12f.csv (a56 filtered, same protocol
as ml/pipeline.py Step 1) across 6 diverse classifier families, to empirically
justify the Random Forest choice argued in the project's testbed architecture notes Sec 3.4 /
Ch3 Sec 3.4. Same StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
and same 12-feature SINGLE_FEATURES vector as the frozen single-event RF result
in ml/results/metrics.json, so the RF row here should reproduce that result as
a consistency check.

Originally (2026-08-12) XGBoost was substituted with sklearn's
GradientBoostingClassifier because this research machine had no outbound
internet access to pip install xgboost. Internet access was restored the same
day and xgboost 3.4.0 was installed; native XGBoost was added as a seventh
model alongside the six already benchmarked (GradientBoosting is kept as its
own row rather than removed, since it is a legitimate independent result, not
a placeholder).
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import StandardScaler
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
import xgboost

ROOT = Path("/root/comp997")
FEATURES = ROOT / "features"
OUT_DIR = ROOT / "ml" / "benchmarks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SINGLE_FEATURES = [
    "ue_category", "ca_supported", "ca_band_count", "mimo_layers_dl",
    "mimo_layers_ul", "vonr_supported", "volte_supported", "nr_band_count",
    "psm_supported", "total_capability_size_bytes", "ie_field_count",
    "session_timestamp_delta",
]
LABEL_NAMES = {
    0: "Normal", 1: "Cat-downgrade", 2: "CA-disabled", 3: "MIMO-reduced",
    4: "VoNR-denied", 5: "Combined", 6: "Partial/noise",
}


def bool_to_int(df, cols):
    for c in cols:
        if df[c].dtype == bool or df[c].dtype == object:
            df[c] = df[c].map({True: 1, False: 0, "True": 1, "False": 0}).astype(float)
    return df


raw = pd.read_csv(FEATURES / "raw_12f.csv")
raw = raw[raw["ue_profile"] != "a56"].reset_index(drop=True)
raw = bool_to_int(raw, SINGLE_FEATURES)
X = raw[SINGLE_FEATURES].values.astype(float)
y = raw["label"].values
labels_all = sorted(raw["label"].unique().tolist())
n = len(y)
print(f"n_samples={n}, n_features={X.shape[1]}, n_classes={len(labels_all)}")

MODELS = {
    "RandomForest": lambda: RandomForestClassifier(n_estimators=200, random_state=42),
    "ExtraTrees": lambda: ExtraTreesClassifier(n_estimators=200, random_state=42),
    "GradientBoosting": lambda: GradientBoostingClassifier(random_state=42),
    "XGBoost": lambda: xgboost.XGBClassifier(
        n_estimators=200, random_state=42, eval_metric="mlogloss",
        use_label_encoder=False, verbosity=0,
    ),
    "MLP": lambda: MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42),
    "SVM_RBF": lambda: SVC(kernel="rbf", random_state=42),
    "LogisticRegression": lambda: LogisticRegression(max_iter=2000, random_state=42),
}
# Models sensitive to feature scale get a standardised copy; tree ensembles do not need it.
NEEDS_SCALING = {"MLP", "SVM_RBF", "LogisticRegression"}

results = {}
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

for name, make_model in MODELS.items():
    fold_f1, fold_prec, fold_rec = [], [], []
    fold_train_s = []
    per_class_recall_accum = {int(lbl): [] for lbl in labels_all}
    for fold_i, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        if name in NEEDS_SCALING:
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_train)
            X_test = scaler.transform(X_test)
        model = make_model()
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        fold_train_s.append(time.perf_counter() - t0)
        y_pred = model.predict(X_test)
        p, r, f1, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=labels_all, average="macro", zero_division=0
        )
        fold_f1.append(f1); fold_prec.append(p); fold_rec.append(r)
        p_c, r_c, f1_c, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=labels_all, average=None, zero_division=0
        )
        for i, lbl in enumerate(labels_all):
            per_class_recall_accum[int(lbl)].append(float(r_c[i]))

    # Per-event inference latency: fit once on the full dataset (scaled if needed),
    # then time 200 single-row predict() calls and take the mean.
    X_full = X.copy()
    if name in NEEDS_SCALING:
        scaler_full = StandardScaler()
        X_full = scaler_full.fit_transform(X_full)
    final_model = make_model()
    t0 = time.perf_counter()
    final_model.fit(X_full, y)
    full_train_s = time.perf_counter() - t0

    rng = np.random.default_rng(42)
    sample_idx = rng.integers(0, n, size=200)
    lat_samples = []
    for i in sample_idx:
        row = X_full[i:i + 1]
        t0 = time.perf_counter()
        final_model.predict(row)
        lat_samples.append((time.perf_counter() - t0) * 1000.0)

    results[name] = {
        "macro_f1_mean": float(np.mean(fold_f1)),
        "macro_f1_std": float(np.std(fold_f1)),
        "macro_precision_mean": float(np.mean(fold_prec)),
        "macro_recall_mean": float(np.mean(fold_rec)),
        "cv_fold_train_time_s_mean": float(np.mean(fold_train_s)),
        "full_fit_train_time_s": float(full_train_s),
        "per_event_inference_latency_ms_mean": float(np.mean(lat_samples)),
        "per_event_inference_latency_ms_p95": float(np.percentile(lat_samples, 95)),
        "per_class_recall_mean": {
            str(lbl): float(np.mean(vals)) for lbl, vals in per_class_recall_accum.items()
        },
    }
    print(f"{name:20s} macro_f1={results[name]['macro_f1_mean']:.4f} "
          f"train={results[name]['full_fit_train_time_s']:.3f}s "
          f"inf_latency={results[name]['per_event_inference_latency_ms_mean']:.4f}ms")

with open(OUT_DIR / "model_benchmark.json", "w") as f:
    json.dump({
        "n_samples": n, "n_features": X.shape[1], "labels": labels_all,
        "label_names": LABEL_NAMES, "cv": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "results": results,
    }, f, indent=2)
print("Wrote", OUT_DIR / "model_benchmark.json")
