#!/usr/bin/env python3
"""Feature ablation study (post-Session-F addendum item 3).

Drops one feature group at a time from the frozen 12-feature single-event RF
(same protocol as ml/pipeline.py Step 1: RandomForestClassifier(n_estimators=200,
random_state=42), StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
cross_val_predict for per-class recall), and measures the degradation in
recall on the specific attack class each group is expected to drive:

  drop MIMO (mimo_layers_dl, mimo_layers_ul)  -> recall on label 3 (MIMO-reduced)
  drop CA   (ca_supported, ca_band_count)     -> recall on label 2 (CA-disabled)
  drop ue_category                            -> recall on label 1 (Cat-downgrade)
  drop VoNR (vonr_supported)                  -> recall on label 4 (VoNR-denied)

This is a stronger causal claim than the existing SHAP attribution (W5.3):
SHAP shows correlation/importance under the full feature set, ablation shows
what actually happens to detection when the feature is unavailable.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

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
RF_KW = dict(n_estimators=200, random_state=42)


def bool_to_int(df, cols):
    for c in cols:
        if df[c].dtype == bool or df[c].dtype == object:
            df[c] = df[c].map({True: 1, False: 0, "True": 1, "False": 0}).astype(float)
    return df


raw = pd.read_csv(FEATURES / "raw_12f.csv")
raw = raw[raw["ue_profile"] != "a56"].reset_index(drop=True)
raw = bool_to_int(raw, SINGLE_FEATURES)
y = raw["label"].values
labels_all = sorted(raw["label"].unique().tolist())
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

ABLATIONS = {
    "baseline_all_12": {"drop": [], "target_label": None},
    "drop_MIMO": {"drop": ["mimo_layers_dl", "mimo_layers_ul"], "target_label": 3},
    "drop_CA": {"drop": ["ca_supported", "ca_band_count"], "target_label": 2},
    "drop_ue_category": {"drop": ["ue_category"], "target_label": 1},
    "drop_VoNR": {"drop": ["vonr_supported"], "target_label": 4},
}

results = {}
for name, spec in ABLATIONS.items():
    cols = [c for c in SINGLE_FEATURES if c not in spec["drop"]]
    X = raw[cols].values.astype(float)
    y_pred = cross_val_predict(RandomForestClassifier(**RF_KW), X, y, cv=skf)
    macro_f1 = f1_score(y, y_pred, labels=labels_all, average="macro", zero_division=0)
    p, r, f1c, support = precision_recall_fscore_support(y, y_pred, labels=labels_all, zero_division=0)
    per_class_recall = {str(lbl): float(r[i]) for i, lbl in enumerate(labels_all)}
    results[name] = {
        "n_features": len(cols),
        "dropped": spec["drop"],
        "target_label": spec["target_label"],
        "target_label_name": LABEL_NAMES.get(spec["target_label"]) if spec["target_label"] is not None else None,
        "macro_f1": float(macro_f1),
        "per_class_recall": per_class_recall,
    }
    tgt = spec["target_label"]
    tgt_recall = per_class_recall[str(tgt)] if tgt is not None else None
    print(f"{name:20s} n_feat={len(cols):2d} macro_f1={macro_f1:.4f}"
          + (f"  target(label {tgt}, {LABEL_NAMES[tgt]}) recall={tgt_recall:.4f}" if tgt is not None else ""))

baseline_recall = results["baseline_all_12"]["per_class_recall"]
for name, spec in ABLATIONS.items():
    if spec["target_label"] is None:
        continue
    tgt = str(spec["target_label"])
    results[name]["target_label_recall_baseline"] = baseline_recall[tgt]
    results[name]["target_label_recall_degradation"] = baseline_recall[tgt] - results[name]["per_class_recall"][tgt]

with open(OUT_DIR / "feature_ablation.json", "w") as f:
    json.dump({
        "n_samples": len(y), "labels": labels_all, "label_names": LABEL_NAMES,
        "cv": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)",
        "results": results,
    }, f, indent=2)
print("Wrote", OUT_DIR / "feature_ablation.json")
