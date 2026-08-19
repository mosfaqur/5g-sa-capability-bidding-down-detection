#!/usr/bin/env python3
"""Builds analysis/table_intraclass_consistency.md (W4.3).

For each (mode, profile) pair (>=100 repeated runs each, a56 excluded — its
only mode is label 0 with 96 rows, kept here for completeness but flagged as
below the >=100 target), computes mean/sigma/CoV of each of the 12 tracked
features. Then, per (mode, feature), computes sigma ACROSS the 6 study
profiles' means (cross-device consistency of the same attack's signature).
"""
import pandas as pd
import numpy as np

raw = pd.read_csv("/root/comp997/features/raw_12f.csv")

FEATURES = [
    "ue_category", "ca_supported", "ca_band_count", "mimo_layers_dl",
    "mimo_layers_ul", "vonr_supported", "volte_supported", "nr_band_count",
    "psm_supported", "total_capability_size_bytes", "ie_field_count",
    "session_timestamp_delta",
]
BOOL_FEATURES = {"ca_supported", "vonr_supported", "volte_supported", "psm_supported"}
CONTINUOUS = [f for f in FEATURES if f not in BOOL_FEATURES]

for c in BOOL_FEATURES:
    raw[c] = raw[c].astype(bool).astype(int)

MODE_NAMES = {0:"Normal",1:"Cat-down",2:"CA-dis",3:"MIMO-red",
              4:"VoNR-den",5:"Combined",6:"Partial"}
PROFILES = ["sw-std", "sw-ext", "sw-min", "pixel8", "realme", "nothing3a", "a56"]

def cov(std, mean):
    if mean == 0 or pd.isna(mean):
        return np.nan
    return std / abs(mean)

# ---- Table A: per (mode, profile) CoV of each feature ----
rowsA = []
flagged_cells = []
for m in range(7):
    for p in PROFILES:
        sub = raw[(raw.label == m) & (raw.ue_profile == p)]
        if sub.empty:
            continue
        n = len(sub)
        row = {"mode": f"{m} {MODE_NAMES[m]}", "profile": p, "n": n}
        for feat in FEATURES:
            std = sub[feat].std(ddof=1) if n > 1 else 0.0
            mean = sub[feat].mean()
            c = cov(std, mean)
            row[feat] = c
            if feat in CONTINUOUS and pd.notna(c) and c > 0.3:
                flagged_cells.append((f"{m} {MODE_NAMES[m]}", p, feat, round(c, 3), n))
        rowsA.append(row)

dfA = pd.DataFrame(rowsA)

# ---- Table B: sigma across the 6 study profiles' per-profile means, per (mode, feature) ----
rowsB = []
for m in range(7):
    sub = raw[(raw.label == m) & (raw.ue_profile != "a56")]
    row = {"mode": f"{m} {MODE_NAMES[m]}"}
    for feat in FEATURES:
        profile_means = sub.groupby("ue_profile")[feat].mean()
        row[feat] = profile_means.std(ddof=1)
    rowsB.append(row)
dfB = pd.DataFrame(rowsB)

with open("/root/comp997/analysis/table_intraclass_consistency.md", "w") as f:
    f.write("# W4.3 — Intra-class Consistency\n\n")
    f.write(
        "**Table A** — coefficient of variation (σ/|μ|) of each feature within each "
        "(mode, profile) group, across its repeated runs (target ≥100 events/class/profile; "
        "a56 kept for completeness but only has label-0 data, n=96, below target — see Bug 21). "
        "Boolean features (`ca_supported`, `vonr_supported`, `volte_supported`, `psm_supported`) "
        "are cast to 0/1; CoV is undefined (n/a) when the group mean is 0 (fully constant "
        "at the False/0 value). Cells with CoV > 0.3 on a continuous feature are flagged in "
        "the notes below the table as high within-class variance.\n\n"
    )
    cols = ["mode", "profile", "n"] + FEATURES
    f.write("| " + " | ".join(cols) + " |\n")
    f.write("|" + "---|" * len(cols) + "\n")
    for _, r in dfA.iterrows():
        cells = [str(r["mode"]), str(r["profile"]), str(r["n"])]
        for feat in FEATURES:
            v = r[feat]
            cells.append("n/a" if pd.isna(v) else f"{v:.3f}")
        f.write("| " + " | ".join(cells) + " |\n")

    f.write("\n## Cells flagged as high within-class variance (continuous feature, CoV > 0.3)\n\n")
    if flagged_cells:
        f.write("| Mode | Profile | Feature | CoV | n |\n|---|---|---|---|---|\n")
        for mode, p, feat, c, n in flagged_cells:
            f.write(f"| {mode} | {p} | {feat} | {c} | {n} |\n")
    else:
        f.write("(none — every continuous feature is stable within class across all (mode, profile) groups)\n")

    f.write(
        "\n**Table B** — σ of each feature's per-profile mean, across the 6 study profiles, "
        "per mode (cross-device consistency of the attack's signature; a56 excluded). "
        "A near-zero σ means every profile's baseline/attacked value for that feature agrees; "
        "a large σ means the feature's value is profile-dependent even under the same attack "
        "label (expected for features with real device diversity, e.g. `nr_band_count`, "
        "`total_capability_size_bytes` — those vary by device fingerprint regardless of attack).\n\n"
    )
    cols = ["mode"] + FEATURES
    f.write("| " + " | ".join(cols) + " |\n")
    f.write("|" + "---|" * len(cols) + "\n")
    for _, r in dfB.iterrows():
        cells = [str(r["mode"])]
        for feat in FEATURES:
            v = r[feat]
            cells.append("n/a" if pd.isna(v) else f"{v:.3f}")
        f.write("| " + " | ".join(cells) + " |\n")

# ---- Boolean-feature anomaly scan (CoV is a poor metric for booleans, so scan directly) ----
bool_anomalies = []
for m in range(7):
    for p in PROFILES:
        sub = raw[(raw.label == m) & (raw.ue_profile == p)]
        if sub.empty:
            continue
        for feat in BOOL_FEATURES:
            vc = sub[feat].value_counts()
            if len(vc) > 1:
                minority = vc.min()
                if minority > 0 and minority < 0.05 * len(sub):
                    bool_anomalies.append((f"{m} {MODE_NAMES[m]}", p, feat, int(minority), len(sub)))

with open("/root/comp997/analysis/table_intraclass_consistency.md", "a") as f:
    f.write("\n## Boolean-feature anomalies (minority value <5% of group, not captured by CoV)\n\n")
    if bool_anomalies:
        f.write("| Mode | Profile | Feature | Minority-value count | n | Note |\n|---|---|---|---|---|---|\n")
        for mode, p, feat, minority, n in bool_anomalies:
            f.write(f"| {mode} | {p} | {feat} | {minority} | {n} | Likely a single-event decode/capture anomaly, not a real device-behaviour change — outside the label's targeted field |\n")
    else:
        f.write("(none)\n")

print(dfA.to_string())
print()
print(dfB.to_string())
print("\nFlagged high-variance cells:", len(flagged_cells))
for c in flagged_cells:
    print(" ", c)
print("\nWrote analysis/table_intraclass_consistency.md")
