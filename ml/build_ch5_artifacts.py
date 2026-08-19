"""Builds Chapter 5 (W5.1-W5.3, W6.2-W6.3) tables and confusion-matrix figures
from ml/results/{metrics,latency,openset}.json. Run under proxy/venv (needs
matplotlib/numpy). See the project's internal build log Key Files Reference for ml/pipeline.py context.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS = Path(__file__).parent / "results"
TABLES = RESULTS / "tables"
TABLES.mkdir(exist_ok=True)

metrics = json.loads((RESULTS / "metrics.json").read_text())
latency = json.loads((RESULTS / "latency.json").read_text())
openset = json.loads((RESULTS / "openset.json").read_text())

LABEL_ORDER = ["0", "1", "2", "3", "4", "5", "6"]
LABEL_NAMES = {k: v["label_name"] for k, v in metrics["single_event"]["per_class"].items()}


def fmt(x):
    return f"{x:.3f}"


# ── Table 1: per-class precision/recall/F1, single-event vs sliding-window vs cross-layer ──
se = metrics["single_event"]["per_class"]
sw = metrics["sliding_window"]["per_class"]
xl = metrics["cross_layer"]["per_class"]

lines = []
lines.append("# Table: Per-Class Classification Performance (W5.1/W5.2/W5.3)")
lines.append("")
lines.append(
    "Single-event RF (12-feature, N2-only baseline) and sliding-window RF (N=3, "
    "36-feature) are trained on the full 6-profile dataset (4,225 / 3,783 rows). "
    "The cross-layer consistency RF (9-of-11 features, real handsets only — Pixel 8 "
    "and Nothing 3A, capability_size_delta and container_hash_match excluded per "
    "the project's testbed architecture notes §7.2) is trained on 1,418 rows. The comparison column "
    "is single-event F1 minus cross-layer F1 (positive = single-view scores higher "
    "on that class)."
)
lines.append("")
lines.append(
    "| Label | Single-event P | Single-event R | Single-event F1 | "
    "Window P | Window R | Window F1 | "
    "Cross-layer P | Cross-layer R | Cross-layer F1 | "
    "Single-view − Cross-layer F1 |"
)
lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
for lbl in LABEL_ORDER:
    name = LABEL_NAMES[lbl]
    a, b, c = se[lbl], sw[lbl], xl[lbl]
    diff = a["f1"] - c["f1"]
    lines.append(
        f"| {lbl} {name} | {fmt(a['precision'])} | {fmt(a['recall'])} | {fmt(a['f1'])} | "
        f"{fmt(b['precision'])} | {fmt(b['recall'])} | {fmt(b['f1'])} | "
        f"{fmt(c['precision'])} | {fmt(c['recall'])} | {fmt(c['f1'])} | "
        f"{diff:+.3f} |"
    )
lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
lines.append(
    f"| **Overall** | | | **{fmt(metrics['single_event']['accuracy'])} acc / "
    f"{fmt(metrics['single_event']['macro_f1'])} macro-F1** | | | "
    f"**{fmt(metrics['sliding_window']['accuracy'])} acc / "
    f"{fmt(metrics['sliding_window']['macro_f1'])} macro-F1** | | | "
    f"**{fmt(metrics['cross_layer']['accuracy'])} acc / "
    f"{fmt(metrics['cross_layer']['macro_f1'])} macro-F1** | "
    f"{metrics['single_event']['macro_f1'] - metrics['cross_layer']['macro_f1']:+.3f} |"
)
(TABLES / "table_ml_performance.md").write_text("\n".join(lines) + "\n")

# ── Table 2: open-set held-out-mode result ──
lines = []
lines.append("# Table: Open-Set Held-Out-Mode Detection (Train Labels 0-4, Detect 5-6)")
lines.append("")
lines.append(
    "Tests generalisation to attack modes absent from training. Cross-layer did not "
    "transfer better than single-view here, contrary to the W5.3 prediction — see "
    "Chapter 5 discussion."
)
lines.append("")
lines.append("| Metric | Single-view | Cross-layer |")
lines.append("|---|---|---|")
sv, cl = openset["single_view"], openset["cross_layer"]
lines.append(f"| n_train | {sv['n_train']} | {cl['n_train']} |")
lines.append(f"| n_test | {sv['n_test']} | {cl['n_test']} |")
lines.append(
    f"| Overall detection rate | {fmt(sv['overall_detection_rate'])} | "
    f"{fmt(cl['overall_detection_rate'])} |"
)
lines.append(
    f"| Label 5 (Combined) detection rate | {fmt(sv['per_label_detection_rate']['5'])} | "
    f"{fmt(cl['per_label_detection_rate']['5'])} |"
)
lines.append(
    f"| Label 6 (Partial/noise) detection rate | {fmt(sv['per_label_detection_rate']['6'])} | "
    f"{fmt(cl['per_label_detection_rate']['6'])} |"
)
lines.append(
    f"| Cross-layer transfers better than single-view? | "
    f"{'Yes' if openset['cross_layer_transfers_better'] else 'No'} | |"
)
(TABLES / "table_openset.md").write_text("\n".join(lines) + "\n")

# ── Table 3: cross-profile (LOPO) generalisation ──
lopo = metrics["cross_profile_lopo"]
profiles = list(lopo["per_profile"].keys())

lines = []
lines.append("# Table: Cross-Profile (Leave-One-Profile-Out) Generalisation (W6.3)")
lines.append("")
lines.append(
    "Per-class F1 when each profile is held out entirely (trained on the "
    "remaining 5, tested on the held-out profile's own rows). sigma is the "
    "standard deviation of that class's F1 across the 6 held-out folds; sigma>0.05 "
    "is flagged per the project's threshold. All 7 classes are flagged — see "
    "the project's internal build log's 'CLI Session D' W6.3 finding for the causal breakdown (sw-min and "
    "pixel8 collapse due to device-fixed traits aliasing with attack target "
    "features)."
)
lines.append("")
header = "| Label | " + " | ".join(profiles) + " | sigma | flagged |"
lines.append(header)
lines.append("|---|" + "---|" * (len(profiles) + 2))
for lbl in LABEL_ORDER:
    name = LABEL_NAMES[lbl]
    row = [f"{lbl} {name}"]
    for p in profiles:
        row.append(fmt(lopo["per_profile"][p]["per_class"][lbl]["f1"]))
    sigma_entry = lopo["sigma_by_class"][lbl]
    row.append(fmt(sigma_entry["sigma"]))
    row.append("yes" if sigma_entry["flagged"] else "no")
    lines.append("| " + " | ".join(row) + " |")
lines.append("|---|" + "---|" * (len(profiles) + 2))
macro_row = ["**macro-F1 (held-out profile)**"]
for p in profiles:
    macro_row.append(f"**{fmt(lopo['per_profile'][p]['macro_f1'])}**")
macro_row.append("")
macro_row.append("")
lines.append("| " + " | ".join(macro_row) + " |")
(TABLES / "table_cross_profile.md").write_text("\n".join(lines) + "\n")

# ── Table 4: latency vs operational ceiling ──
d = latency["decode_to_classification_ms"]
f = latency["full_arrival_to_classification_ms"]
lines = []
lines.append("# Table: Pipeline Latency vs Operational Ceiling (W6.2)")
lines.append("")
lines.append(
    f"100-event replay (decode -> 12-feature extraction -> RF inference), plus "
    f"Session A's mean proxy-forward latency "
    f"({fmt(latency['session_a_mean_proxy_forward_latency_ms'])} ms) added for a "
    f"full arrival-to-classification figure. Operational ceiling is a study-defined "
    f"target ({latency['operational_ceiling_ms']} ms), not a 3GPP-defined N2 timer."
)
lines.append("")
lines.append("| Stage | Mean (ms) | P95 (ms) | Max (ms) | Under 1000 ms ceiling? |")
lines.append("|---|---|---|---|---|")
lines.append(
    f"| Decode -> classification | {d['mean']:.1f} | {d['p95']:.1f} | {d['max']:.1f} | "
    f"{'yes' if d['max'] < latency['operational_ceiling_ms'] else 'no'} |"
)
lines.append(
    f"| Full arrival -> classification (+ proxy forward) | {f['mean']:.1f} | "
    f"{f['p95']:.1f} | {f['max']:.1f} | "
    f"{'yes' if latency['under_ceiling'] else 'no'} |"
)
lines.append("")
lines.append(f"n_events_replayed = {latency['n_events_replayed']}")
(TABLES / "table_latency.md").write_text("\n".join(lines) + "\n")

print("Tables written:")
for f_ in sorted(TABLES.glob("*.md")):
    print(" ", f_)

# ── Confusion matrix figures ──
LABELS_SHORT = [f"{k}\n{LABEL_NAMES[k]}" for k in LABEL_ORDER]


def plot_confmat(cm, title, caption, out_path):
    cm = np.array(cm)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(LABEL_ORDER)))
    ax.set_yticks(range(len(LABEL_ORDER)))
    ax.set_xticklabels(LABELS_SHORT, fontsize=8)
    ax.set_yticklabels(LABELS_SHORT, fontsize=8)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(title, fontsize=11)
    for i in range(len(LABEL_ORDER)):
        for j in range(len(LABEL_ORDER)):
            val = cm[i, j]
            frac = cm_norm[i, j]
            color = "white" if frac > 0.5 else "black"
            ax.text(j, i, str(val), ha="center", va="center", color=color, fontsize=8)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Row-normalised fraction")
    fig.text(0.02, 0.01, caption, fontsize=7, wrap=True, va="bottom")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


plot_confmat(
    metrics["single_event"]["confusion_matrix"],
    "Single-Event RF Confusion Matrix (W5.1 baseline, 12 features)",
    "[Figure X.Y]: Confusion matrix for the single-event Random Forest classifier "
    "across seven attack classes.",
    RESULTS / "confusion_matrix_single.png",
)

plot_confmat(
    metrics["sliding_window"]["confusion_matrix"],
    "Sliding-Window RF Confusion Matrix (W5.2, N=3, 36 features)",
    "[Figure X.Y]: Confusion matrix for the sliding-window Random Forest "
    "classifier (N=3) across seven attack classes.",
    RESULTS / "confusion_matrix_window.png",
)

plot_confmat(
    metrics["cross_layer"]["confusion_matrix"],
    "Cross-Layer Consistency Model Confusion Matrix (real handsets, 9 features)",
    "[Figure X.Y]: Confusion matrix for the cross-layer consistency model (real "
    "handsets) across seven attack classes.",
    RESULTS / "confusion_matrix_xlayer.png",
)

print("Figures written:")
for f_ in [
    RESULTS / "confusion_matrix_single.png",
    RESULTS / "confusion_matrix_window.png",
    RESULTS / "confusion_matrix_xlayer.png",
]:
    print(" ", f_)

# ── Sliding-window SHAP: regenerate as a stacked per-time-step bar chart ──
# (the existing shap_window_summary.png only showed the t0+t1+t2 sum; the task
# requires the per-time-step contribution to be visible, which metrics.json's
# shap_window_aggregated[*].per_timestep already carries).
window_feats = metrics["shap_window_aggregated"]
window_feats_sorted = sorted(window_feats, key=lambda x: -x["summed_mean_abs_shap"])
names = [f["feature"] for f in window_feats_sorted]
t0 = [f["per_timestep"]["t0"] for f in window_feats_sorted]
t1 = [f["per_timestep"]["t1"] for f in window_feats_sorted]
t2 = [f["per_timestep"]["t2"] for f in window_feats_sorted]

fig, ax = plt.subplots(figsize=(9, 6))
y = np.arange(len(names))
ax.barh(y, t0, label="t0 (oldest)", color="#f4a261")
ax.barh(y, t1, left=np.array(t0), label="t1", color="#e76f51")
ax.barh(y, t2, left=np.array(t0) + np.array(t1), label="t2 (most recent)", color="#9d3b1a")
ax.set_yticks(y)
ax.set_yticklabels(names)
ax.invert_yaxis()
ax.set_xlabel("mean |SHAP value| (stacked across t0/t1/t2)")
ax.set_title("Sliding-window model: per-time-step feature contribution (SHAP)")
ax.legend()
fig.tight_layout()
fig.savefig(RESULTS / "shap_window_summary.png", dpi=150)
plt.close(fig)
print("Regenerated (per-time-step):", RESULTS / "shap_window_summary.png")

# ── Caption text file for Chapter 5 SHAP + confusion-matrix figures ──
captions = """# Chapter 5 figure captions (SHAP + confusion matrices)

These figures belong in Chapter 5 (W5.1-W5.3 SHAP analysis / confusion matrices),
not Chapter 4. Renumber [Figure X.Y] placeholders to the actual Ch 5 sequence
before final submission.

## shap_single_summary.png
[Figure X.Y — assign number in Ch 5 sequence]: Mean |SHAP| values for the
single-event 12-feature Random Forest model. Feature names correspond to UE
radio capability IE fields defined in 3GPP TS 38.306 and carried in the NGAP
UERadioCapabilityInfoIndication PDU of 3GPP TS 38.413 (3GPP, 2024c, 2024e).
Confirmed: bar chart covers all 12 tracked features, labelled by IE field name.
Top feature: mimo_layers_dl.

## shap_window_summary.png
[Figure X.Y]: Mean |SHAP| values for the sliding-window (N=3) Random Forest
model, aggregated across the 12 tracked features and broken out by time-step
(t0 = oldest event in the window, t2 = most recent) to show each event's
relative contribution within the window. Secondary to the single-event SHAP
figure above. Top feature: mimo_layers_dl.

## shap_xlayer_summary.png
[Figure X.Y]: Mean |SHAP| values for the cross-layer consistency model (9
trained features; capability_size_delta and container_hash_match excluded,
the project's testbed architecture notes §7.2). Detection is driven by RRC-vs-N2 field
divergence (num_fields_mismatched and the specific semantic fields), not by
the raw capability value. Top feature: mimo_dl_delta.

## confusion_matrix_single.png
[Figure X.Y]: Confusion matrix for the single-event Random Forest classifier
across seven attack classes.

## confusion_matrix_window.png
[Figure X.Y]: Confusion matrix for the sliding-window Random Forest classifier
(N=3) across seven attack classes.

## confusion_matrix_xlayer.png
[Figure X.Y]: Confusion matrix for the cross-layer consistency model (real
handsets) across seven attack classes.
"""
(RESULTS / "figure_captions.md").write_text(captions)
print("Captions written:", RESULTS / "figure_captions.md")
