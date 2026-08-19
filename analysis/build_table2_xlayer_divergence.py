#!/usr/bin/env python3
"""Builds analysis/table_xlayer_divergence.md (W4.4).

Uses features/xlayer.csv (real handsets only — Pixel 8 + Nothing 3A, per the
2026-08-10 build_xlayer.py session; a56/Realme/UERANSIM have no persisted
case-a RRC reference and are out of scope for this cross-layer comparison).

Of the 11 cross-layer consistency features, capability_size_delta and
container_hash_match are None on every row (2026-07-31 methodological fix:
the RRC-side reference is a case-a JSON-decoded capture, byte_exact=False,
so a byte-level size/hash comparison against the N2 PER bytes is meaningless.
They are reported as "n/a (excluded)" here, not treated as non-firing.
"""
import pandas as pd
import numpy as np

df = pd.read_csv("/root/comp997/features/xlayer.csv")

MATCH_COLS = ["ca_supported_match", "vonr_supported_match"]
DELTA_COLS = ["ue_category_delta", "ca_band_count_delta", "mimo_dl_delta",
              "mimo_ul_delta", "nr_band_count_delta", "ie_field_count_delta"]
COUNT_COL = "num_fields_mismatched"
EXCLUDED = ["capability_size_delta", "container_hash_match"]

MODE_NAMES = {0:"Normal",1:"Cat-downgrade",2:"CA-disabled",3:"MIMO-reduced",
              4:"VoNR-denied",5:"Combined",6:"Partial/noise"}

rows = []
for label in range(7):
    sub = df[df.label == label]
    n = len(sub)
    fires = []
    for c in MATCH_COLS:
        mismatch_rate = (~sub[c]).mean()
        if mismatch_rate > 0.01:
            fires.append(f"{c} (mismatch {mismatch_rate*100:.1f}%)")
    for c in DELTA_COLS:
        nonzero_rate = (sub[c] != 0).mean()
        mean_abs = sub[c].abs().mean()
        if nonzero_rate > 0.01:
            fires.append(f"{c} (nonzero {nonzero_rate*100:.1f}%, mean|Δ|={mean_abs:.2f})")
    mean_mismatch_count = sub[COUNT_COL].mean()
    no_trace = (len(fires) == 0)
    rows.append(dict(
        mode=f"{label} {MODE_NAMES[label]}",
        n=n,
        fired_features="; ".join(fires) if fires else "**NONE**",
        mean_num_fields_mismatched=round(mean_mismatch_count, 2),
        no_cross_layer_trace="**YES — flagged**" if no_trace else "No",
    ))

with open("/root/comp997/analysis/table_xlayer_divergence.md", "w") as f:
    f.write("# W4.4 — Cross-Layer (RRC-vs-N2) Divergence Catalogue\n\n")
    f.write(
        "Real handsets only (Pixel 8, Nothing 3A), `features/xlayer.csv`, "
        f"{len(df)} rows. Each N2 event is paired against its IMSI's persisted "
        "per-IMSI case-a RRC reference (non-circular join, see the project's internal build log's "
        "\"Cached-reattach (case b) live validation\" finding). "
        "`capability_size_delta`/`container_hash_match` are excluded from this "
        "table (None on every row by design — see module docstring); "
        "9-of-11 features are evaluated here, matching the Session D cross-layer "
        "model's own 9-feature training set.\n\n"
    )
    f.write("| Mode | n | Cross-layer features that fire | Mean num_fields_mismatched | No cross-layer trace? |\n")
    f.write("|---|---|---|---|---|\n")
    for r in rows:
        f.write(f"| {r['mode']} | {r['n']} | {r['fired_features']} | {r['mean_num_fields_mismatched']} | {r['no_cross_layer_trace']} |\n")
    f.write("\n## Per-feature fire rate by mode\n\n")
    f.write("| Mode | " + " | ".join(MATCH_COLS + DELTA_COLS) + " |\n")
    f.write("|---|" + "---|" * (len(MATCH_COLS) + len(DELTA_COLS)) + "\n")
    for label in range(7):
        sub = df[df.label == label]
        cells = []
        for c in MATCH_COLS:
            cells.append(f"{(~sub[c]).mean()*100:.0f}% mismatch")
        for c in DELTA_COLS:
            cells.append(f"{(sub[c]!=0).mean()*100:.0f}% nonzero (μ|Δ|={sub[c].abs().mean():.2f})")
        f.write(f"| {label} {MODE_NAMES[label]} | " + " | ".join(cells) + " |\n")

    vonr_by_profile = df[df.label == 4].groupby("ue_profile")["vonr_supported_match"].apply(lambda s: (~s).mean())
    f.write("\n## Notes\n\n")
    f.write(
        "- **Mode 4 (VoNR-denied) fires at only ~49% overall because it splits cleanly by profile**: "
        f"{dict((k, f'{v*100:.0f}% mismatch') for k, v in vonr_by_profile.items())}. "
        "Pixel 8 never advertises VoNR natively (`vonr_supported=False` on every baseline capture — "
        "confirmed elsewhere in this project), so stripping an already-absent VoNR bit is a true no-op "
        "for that device; Nothing 3A does support VoNR natively, so the attack is fully visible there. "
        "This is a genuine device-dependent finding, not noise or a decode defect.\n"
        "- **Modes 0 (Normal) and 6 (Partial/noise) leave no cross-layer trace**, as expected: mode 0 has "
        "no attack; mode 6's target field (`supportedROHC-Profiles`) is outside all 11 cross-layer "
        "features by design, matching the same finding already established for the single-view 12-feature "
        "vector in the W4.1 attack catalogue.\n"
    )

for r in rows:
    print(r)
print("\nWrote analysis/table_xlayer_divergence.md")
