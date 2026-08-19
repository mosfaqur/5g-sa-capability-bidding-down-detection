#!/usr/bin/env python3
"""COMP997 Q2 ML pipeline: single-event RF, sliding-window RF, SHAP,
leave-one-profile-out generalisation, end-to-end latency replay, cross-layer
consistency RF, and open-set held-out-mode test. See the project's internal build log ML section for
the frozen spec (RandomForestClassifier(n_estimators=200, random_state=42),
StratifiedKFold(n_splits=5, shuffle=True, random_state=42))."""
import json
import sys
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold, cross_val_predict

ROOT = Path("/root/comp997")
FEATURES = ROOT / "features"
ML_MODELS = ROOT / "ml" / "models"
ML_RESULTS = ROOT / "ml" / "results"
ML_MODELS.mkdir(parents=True, exist_ok=True)
ML_RESULTS.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "proxy"))
sys.path.insert(0, str(FEATURES))

LABEL_NAMES = {
    0: "Normal", 1: "Cat-downgrade", 2: "CA-disabled", 3: "MIMO-reduced",
    4: "VoNR-denied", 5: "Combined", 6: "Partial/noise",
}
ACTIVE_PROFILES = ["nothing3a", "pixel8", "realme", "sw-std", "sw-ext", "sw-min"]

SINGLE_FEATURES = [
    "ue_category", "ca_supported", "ca_band_count", "mimo_layers_dl",
    "mimo_layers_ul", "vonr_supported", "volte_supported", "nr_band_count",
    "psm_supported", "total_capability_size_bytes", "ie_field_count",
    "session_timestamp_delta",
]
XLAYER_FEATURES = [
    "ue_category_delta", "ca_supported_match", "ca_band_count_delta",
    "mimo_dl_delta", "mimo_ul_delta", "vonr_supported_match",
    "nr_band_count_delta", "ie_field_count_delta", "num_fields_mismatched",
]
RF_KW = dict(n_estimators=200, random_state=42)
metrics = {}


def bool_to_int(df, cols):
    for c in cols:
        if df[c].dtype == bool or df[c].dtype == object:
            df[c] = df[c].map({True: 1, False: 0, "True": 1, "False": 0}).astype(float)
    return df


def per_class_report(y_true, y_pred, labels):
    p, r, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    macro_f1 = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    report = {
        str(lbl): {
            "label_name": LABEL_NAMES.get(lbl, str(lbl)),
            "precision": float(p[i]), "recall": float(r[i]),
            "f1": float(f1[i]), "support": int(support[i]),
        }
        for i, lbl in enumerate(labels)
    }
    return report, float(macro_f1), cm.tolist()


# ── Step 1: single-event RF ──────────────────────────────────────────────
print("[1/7] Single-event RF (raw_12f.csv, a56 filtered)...")
raw = pd.read_csv(FEATURES / "raw_12f.csv")
raw = raw[raw["ue_profile"] != "a56"].reset_index(drop=True)
raw = bool_to_int(raw, SINGLE_FEATURES)
X1 = raw[SINGLE_FEATURES].values
y1 = raw["label"].values
labels_all = sorted(raw["label"].unique().tolist())

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
y1_pred = cross_val_predict(RandomForestClassifier(**RF_KW), X1, y1, cv=skf)
report1, macro_f1_1, cm1 = per_class_report(y1, y1_pred, labels_all)
acc1 = float((y1_pred == y1).mean())
print(f"  accuracy={acc1:.4f} macro_f1={macro_f1_1:.4f}")

rf_single = RandomForestClassifier(**RF_KW)
rf_single.fit(X1, y1)
joblib.dump(rf_single, ML_MODELS / "rf_single_event.pkl")
metrics["single_event"] = {
    "accuracy": acc1, "macro_f1": macro_f1_1,
    "per_class": report1, "confusion_matrix": cm1, "labels": labels_all,
    "n_samples": len(y1),
}

# ── Step 2: sliding-window RF ────────────────────────────────────────────
print("[2/7] Sliding-window RF (windowed_36f.csv)...")
win = pd.read_csv(FEATURES / "windowed_36f.csv")
window_feature_cols = [c for c in win.columns if c != "label"]
win = bool_to_int(win, window_feature_cols)
X2 = win[window_feature_cols].values
y2 = win["label"].values
labels2 = sorted(win["label"].unique().tolist())

skf2 = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
y2_pred = cross_val_predict(RandomForestClassifier(**RF_KW), X2, y2, cv=skf2)
report2, macro_f1_2, cm2 = per_class_report(y2, y2_pred, labels2)
acc2 = float((y2_pred == y2).mean())
print(f"  accuracy={acc2:.4f} macro_f1={macro_f1_2:.4f}")

rf_window = RandomForestClassifier(**RF_KW)
rf_window.fit(X2, y2)
joblib.dump(rf_window, ML_MODELS / "rf_sliding_window.pkl")
metrics["sliding_window"] = {
    "accuracy": acc2, "macro_f1": macro_f1_2,
    "per_class": report2, "confusion_matrix": cm2, "labels": labels2,
    "n_samples": len(y2),
}

# ── Step 3: SHAP on single-view models ───────────────────────────────────
print("[3/7] SHAP TreeExplainer, single-event model...")
explainer1 = shap.TreeExplainer(rf_single)
sv1 = explainer1.shap_values(X1)
sv1_arr = np.array(sv1)  # (n_classes, n_samples, n_features) or (n_samples,n_features,n_classes)
np.save(ML_RESULTS / "shap_single_values.npy", sv1_arr)

if sv1_arr.ndim == 3 and sv1_arr.shape[0] == len(labels_all):
    mean_abs1 = np.mean(np.abs(sv1_arr), axis=(0, 1))
elif sv1_arr.ndim == 3:
    mean_abs1 = np.mean(np.abs(sv1_arr), axis=(0, 2))
else:
    mean_abs1 = np.mean(np.abs(sv1_arr), axis=0)

order1 = np.argsort(mean_abs1)[::-1]
plt.figure(figsize=(8, 5))
plt.barh([SINGLE_FEATURES[i] for i in order1][::-1], mean_abs1[order1][::-1], color="#4C78A8")
plt.xlabel("mean |SHAP value|")
plt.title("Single-event model: feature importance (SHAP)")
plt.tight_layout()
plt.savefig(ML_RESULTS / "shap_single_summary.png", dpi=150)
plt.close()

try:
    class_idx = min(5, sv1_arr.shape[0] - 1) if sv1_arr.ndim == 3 and sv1_arr.shape[0] == len(labels_all) else None
    plt.figure()
    if class_idx is not None:
        shap.summary_plot(sv1_arr[class_idx], X1, feature_names=SINGLE_FEATURES, show=False)
    else:
        shap.summary_plot(sv1, X1, feature_names=SINGLE_FEATURES, show=False)
    plt.tight_layout()
    plt.savefig(ML_RESULTS / "shap_single_beeswarm.png", dpi=150)
    plt.close()
except Exception as exc:
    print(f"  beeswarm plot failed ({exc}), writing bar fallback")
    plt.figure(figsize=(8, 5))
    plt.barh([SINGLE_FEATURES[i] for i in order1][::-1], mean_abs1[order1][::-1], color="#4C78A8")
    plt.title("Single-event model: feature importance (SHAP, fallback)")
    plt.tight_layout()
    plt.savefig(ML_RESULTS / "shap_single_beeswarm.png", dpi=150)
    plt.close()

metrics["shap_single_event_top_features"] = [
    {"feature": SINGLE_FEATURES[i], "mean_abs_shap": float(mean_abs1[i])} for i in order1
]
print("  top feature:", SINGLE_FEATURES[order1[0]])

print("[3/7] SHAP TreeExplainer, sliding-window model...")
explainer2 = shap.TreeExplainer(rf_window)
sv2 = explainer2.shap_values(X2)
sv2_arr = np.array(sv2)
np.save(ML_RESULTS / "shap_window_values.npy", sv2_arr)

if sv2_arr.ndim == 3 and sv2_arr.shape[0] == len(labels2):
    mean_abs2 = np.mean(np.abs(sv2_arr), axis=(0, 1))
elif sv2_arr.ndim == 3:
    mean_abs2 = np.mean(np.abs(sv2_arr), axis=(0, 2))
else:
    mean_abs2 = np.mean(np.abs(sv2_arr), axis=0)

# Aggregate t0/t1/t2 copies of each base feature.
base_feat_order = SINGLE_FEATURES  # base feature order matches t0/t1/t2 blocks
agg = {f: 0.0 for f in base_feat_order}
per_timestep = {f: {"t0": 0.0, "t1": 0.0, "t2": 0.0} for f in base_feat_order}
for i, col in enumerate(window_feature_cols):
    base, _, step = col.rpartition("_")
    if base in agg:
        agg[base] += mean_abs2[i]
        per_timestep[base][step] = float(mean_abs2[i])

order_base = sorted(agg, key=lambda f: agg[f], reverse=True)
plt.figure(figsize=(8, 5))
plt.barh(order_base[::-1], [agg[f] for f in order_base][::-1], color="#F58518")
plt.xlabel("summed mean |SHAP value| across t0/t1/t2")
plt.title("Sliding-window model: aggregated feature importance (SHAP)")
plt.tight_layout()
plt.savefig(ML_RESULTS / "shap_window_summary.png", dpi=150)
plt.close()

metrics["shap_window_aggregated"] = [
    {"feature": f, "summed_mean_abs_shap": agg[f], "per_timestep": per_timestep[f]}
    for f in order_base
]
print("  top aggregated feature:", order_base[0])

# ── Step 4: leave-one-profile-out cross-profile generalisation (W6.3) ───
print("[4/7] Leave-one-profile-out cross-profile generalisation...")
lopo = {}
sigma_flags = []
per_class_f1_by_profile = {lbl: [] for lbl in labels_all}
for held_out in ACTIVE_PROFILES:
    train_df = raw[raw["ue_profile"] != held_out]
    test_df = raw[raw["ue_profile"] == held_out]
    if test_df.empty or train_df.empty:
        continue
    Xtr, ytr = train_df[SINGLE_FEATURES].values, train_df["label"].values
    Xte, yte = test_df[SINGLE_FEATURES].values, test_df["label"].values
    clf = RandomForestClassifier(**RF_KW)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    present_labels = sorted(set(yte.tolist()))
    rep, macro, cm = per_class_report(yte, pred, present_labels)
    lopo[held_out] = {"per_class": rep, "macro_f1": macro, "n_test": len(yte)}
    for lbl in labels_all:
        f1_val = rep.get(str(lbl), {}).get("f1")
        if f1_val is not None:
            per_class_f1_by_profile[lbl].append(f1_val)
    print(f"  held out {held_out}: macro_f1={macro:.4f} n_test={len(yte)}")

sigma_by_class = {}
for lbl in labels_all:
    vals = per_class_f1_by_profile[lbl]
    if len(vals) >= 2:
        sigma = float(np.std(vals, ddof=0))
    else:
        sigma = 0.0
    sigma_by_class[str(lbl)] = {"sigma": sigma, "f1_values": vals, "flagged": sigma >= 0.05}
    if sigma >= 0.05:
        sigma_flags.append(lbl)

metrics["cross_profile_lopo"] = {
    "per_profile": lopo, "sigma_by_class": sigma_by_class,
    "flagged_classes": sigma_flags,
}
print(f"  classes flagged (sigma>=0.05): {sigma_flags}")

# ── Step 5: end-to-end latency (W6.2) ────────────────────────────────────
print("[5/7] End-to-end latency replay (100 events, active profiles only)...")
import extract_features  # noqa: E402

manifest = pd.read_csv(ROOT / "logs" / "collection_manifest.csv")
manifest = manifest[manifest["ue_profile"].isin(ACTIVE_PROFILES)]
manifest = manifest[manifest["pcap_path"].notna()]
manifest["abs_pcap"] = manifest["pcap_path"].apply(lambda p: str(ROOT / p))
manifest = manifest[manifest["abs_pcap"].apply(lambda p: Path(p).exists())]

sample = manifest.sample(n=min(100, len(manifest)), random_state=42)
latencies_ms = []
n_ok = 0
for _, row in sample.iterrows():
    t0 = time.perf_counter()
    try:
        rows = extract_features.extract(row["abs_pcap"])
        if not rows:
            continue
        feat = rows[-1]
        x = np.array([[
            feat["ue_category"], int(feat["ca_supported"]), feat["ca_band_count"],
            feat["mimo_layers_dl"], feat["mimo_layers_ul"], int(feat["vonr_supported"]),
            int(feat["volte_supported"]), feat["nr_band_count"], int(feat["psm_supported"]),
            feat["total_capability_size_bytes"], feat["ie_field_count"],
            feat["session_timestamp_delta"],
        ]])
        _ = rf_single.predict(x)
        n_ok += 1
    except Exception as exc:
        print(f"  skip {row['abs_pcap']}: {exc}", file=sys.stderr)
        continue
    t1 = time.perf_counter()
    latencies_ms.append((t1 - t0) * 1000.0)

latencies_ms = np.array(latencies_ms)
session_a_proxy_latency_ms = float(manifest["proxy_latency_ms"].dropna().astype(float).mean()) if "proxy_latency_ms" in manifest.columns else None

latency_stats = {
    "n_events_replayed": int(n_ok),
    "decode_to_classification_ms": {
        "mean": float(latencies_ms.mean()) if len(latencies_ms) else None,
        "p95": float(np.percentile(latencies_ms, 95)) if len(latencies_ms) else None,
        "max": float(latencies_ms.max()) if len(latencies_ms) else None,
    },
    "session_a_mean_proxy_forward_latency_ms": session_a_proxy_latency_ms,
    "operational_ceiling_ms": 1000,
}
if len(latencies_ms) and session_a_proxy_latency_ms is not None:
    latency_stats["full_arrival_to_classification_ms"] = {
        "mean": latency_stats["decode_to_classification_ms"]["mean"] + session_a_proxy_latency_ms,
        "p95": latency_stats["decode_to_classification_ms"]["p95"] + session_a_proxy_latency_ms,
        "max": latency_stats["decode_to_classification_ms"]["max"] + session_a_proxy_latency_ms,
    }
    latency_stats["under_ceiling"] = latency_stats["full_arrival_to_classification_ms"]["max"] < 1000
print(f"  decode->classify mean={latency_stats['decode_to_classification_ms']['mean']:.3f}ms "
      f"p95={latency_stats['decode_to_classification_ms']['p95']:.3f}ms "
      f"max={latency_stats['decode_to_classification_ms']['max']:.3f}ms "
      f"(n={n_ok})")
with open(ML_RESULTS / "latency.json", "w") as f:
    json.dump(latency_stats, f, indent=2)
metrics["latency"] = latency_stats

# ── Step 6: cross-layer consistency RF (W5.1/W5.3) ───────────────────────
print("[6/7] Cross-layer consistency RF (xlayer.csv, 9-of-11 features)...")
xl = pd.read_csv(FEATURES / "xlayer.csv")
xl = bool_to_int(xl, ["ca_supported_match", "vonr_supported_match"])
X6 = xl[XLAYER_FEATURES].values
y6 = xl["label"].values
labels6 = sorted(xl["label"].unique().tolist())

n_splits6 = min(5, min(np.bincount(y6.astype(int))[np.bincount(y6.astype(int)) > 0]))
n_splits6 = max(2, n_splits6)
skf6 = StratifiedKFold(n_splits=n_splits6, shuffle=True, random_state=42)
y6_pred = cross_val_predict(RandomForestClassifier(**RF_KW), X6, y6, cv=skf6)
report6, macro_f1_6, cm6 = per_class_report(y6, y6_pred, labels6)
acc6 = float((y6_pred == y6).mean())
print(f"  accuracy={acc6:.4f} macro_f1={macro_f1_6:.4f} (n_splits={n_splits6})")

rf_xlayer = RandomForestClassifier(**RF_KW)
rf_xlayer.fit(X6, y6)
joblib.dump(rf_xlayer, ML_MODELS / "rf_xlayer.pkl")

explainer6 = shap.TreeExplainer(rf_xlayer)
sv6 = explainer6.shap_values(X6)
sv6_arr = np.array(sv6)
if sv6_arr.ndim == 3 and sv6_arr.shape[0] == len(labels6):
    mean_abs6 = np.mean(np.abs(sv6_arr), axis=(0, 1))
elif sv6_arr.ndim == 3:
    mean_abs6 = np.mean(np.abs(sv6_arr), axis=(0, 2))
else:
    mean_abs6 = np.mean(np.abs(sv6_arr), axis=0)
order6 = np.argsort(mean_abs6)[::-1]
plt.figure(figsize=(8, 5))
plt.barh([XLAYER_FEATURES[i] for i in order6][::-1], mean_abs6[order6][::-1], color="#54A24B")
plt.xlabel("mean |SHAP value|")
plt.title("Cross-layer consistency model: feature importance (SHAP)")
plt.tight_layout()
plt.savefig(ML_RESULTS / "shap_xlayer_summary.png", dpi=150)
plt.close()

top_xlayer_feature = XLAYER_FEATURES[order6[0]]
top_is_num_mismatched_or_semantic = top_xlayer_feature == "num_fields_mismatched" or top_xlayer_feature in {
    "ue_category_delta", "ca_supported_match", "ca_band_count_delta",
    "mimo_dl_delta", "mimo_ul_delta", "vonr_supported_match",
}
print(f"  top xlayer feature: {top_xlayer_feature} "
      f"(expected num_fields_mismatched or semantic field: {top_is_num_mismatched_or_semantic})")

metrics["cross_layer"] = {
    "accuracy": acc6, "macro_f1": macro_f1_6,
    "per_class": report6, "confusion_matrix": cm6, "labels": labels6,
    "n_samples": len(y6), "n_splits_used": n_splits6,
    "features_used": XLAYER_FEATURES,
    "features_dropped": ["capability_size_delta", "container_hash_match"],
    "top_shap_feature": top_xlayer_feature,
    "shap_top_features": [
        {"feature": XLAYER_FEATURES[i], "mean_abs_shap": float(mean_abs6[i])} for i in order6
    ],
    "vs_single_view_macro_f1": {"single_view": macro_f1_1, "cross_layer": macro_f1_6},
}

# ── Step 7: open-set held-out-mode test (W5.3) ───────────────────────────
print("[7/7] Open-set held-out-mode test (train 0-4, detect 5/6)...")


def openset_eval(df, feature_cols, name):
    train = df[df["label"].isin([0, 1, 2, 3, 4])]
    test = df[df["label"].isin([5, 6])]
    Xtr, ytr = train[feature_cols].values, train["label"].values
    Xte, yte = test[feature_cols].values, test["label"].values
    clf = RandomForestClassifier(**RF_KW)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    detected = (pred != 0)
    detection_rate = float(detected.mean())
    per_label_rate = {}
    for lbl in (5, 6):
        mask = yte == lbl
        if mask.sum():
            per_label_rate[str(lbl)] = float((pred[mask] != 0).mean())
    return {
        "n_train": len(ytr), "n_test": len(yte),
        "overall_detection_rate": detection_rate,
        "per_label_detection_rate": per_label_rate,
    }


openset_single = openset_eval(raw, SINGLE_FEATURES, "single-view")
openset_xlayer = openset_eval(xl, XLAYER_FEATURES, "cross-layer")
print(f"  single-view detection_rate={openset_single['overall_detection_rate']:.4f}")
print(f"  cross-layer detection_rate={openset_xlayer['overall_detection_rate']:.4f}")

openset_result = {"single_view": openset_single, "cross_layer": openset_xlayer,
                   "cross_layer_transfers_better": openset_xlayer["overall_detection_rate"] >= openset_single["overall_detection_rate"]}
with open(ML_RESULTS / "openset.json", "w") as f:
    json.dump(openset_result, f, indent=2)
metrics["openset"] = openset_result

# ── Export ────────────────────────────────────────────────────────────────
with open(ML_RESULTS / "metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print("\nDone. Wrote metrics.json, latency.json, openset.json, models, SHAP artifacts.")
