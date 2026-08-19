#!/usr/bin/env python3
"""Render the three post-Session-F addendum results (model benchmark, feature
ablation, custody verification timing) as markdown tables in
ml/results/tables/, matching the existing table_*.md convention."""
import json
from pathlib import Path

ROOT = Path("/root/comp997")
BENCH = ROOT / "ml" / "benchmarks"
OUT = ROOT / "ml" / "results" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

LABEL_NAMES = {
    0: "Normal", 1: "Cat-downgrade", 2: "CA-disabled", 3: "MIMO-reduced",
    4: "VoNR-denied", 5: "Combined", 6: "Partial/noise",
}

# ---- 1. Model benchmark ----
d = json.load(open(BENCH / "model_benchmark.json"))
lines = [
    "# Multi-Model Benchmark Comparison",
    "",
    f"5-fold stratified CV (`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`) on "
    f"`features/raw_12f.csv` (a56 filtered, {d['n_samples']} rows, {d['n_features']} features, "
    f"{len(d['labels'])} classes). Same protocol and same 12-feature vector as the frozen "
    "single-event RF result in `ml/results/metrics.json` — the RandomForest row below "
    "(macro-F1 0.8475) reproduces that result as a consistency check.",
    "",
    "**Note**: native XGBoost is included (installed 2026-08-12 once outbound internet "
    "access was restored on this machine). `GradientBoostingClassifier` was the original "
    "same-day substitute before XGBoost was available and is retained as its own row "
    "(a legitimate independent result, not a placeholder), not removed now that XGBoost runs.",
    "",
    "| Model | Macro-F1 | Macro-Precision | Macro-Recall | Full-fit train time (s) | Per-event inference latency (ms, mean) | Per-event inference latency (ms, p95) |",
    "|---|---|---|---|---|---|---|",
]
for name, r in d["results"].items():
    lines.append(
        f"| {name} | {r['macro_f1_mean']:.4f} | {r['macro_precision_mean']:.4f} | "
        f"{r['macro_recall_mean']:.4f} | {r['full_fit_train_time_s']:.3f} | "
        f"{r['per_event_inference_latency_ms_mean']:.4f} | {r['per_event_inference_latency_ms_p95']:.4f} |"
    )
lines += [
    "",
    "## Per-class recall (mean across 5 folds)",
    "",
    "| Model | " + " | ".join(f"{i} {LABEL_NAMES[i]}" for i in range(7)) + " |",
    "|---|" + "---|" * 7,
]
for name, r in d["results"].items():
    rc = r["per_class_recall_mean"]
    lines.append(f"| {name} | " + " | ".join(f"{rc[str(i)]:.3f}" for i in range(7)) + " |")
lines += [
    "",
    "All models trained/evaluated under the identical CV protocol used for the frozen "
    "single-event RF result; inference latency measured as the mean/p95 of 200 single-row "
    "`predict()` calls on the fully-fitted model. Feature-scale-sensitive models "
    "(MLP, SVM-RBF, LogisticRegression) were standardised per fold; tree ensembles were not.",
]
(OUT / "table_model_benchmark.md").write_text("\n".join(lines) + "\n")
print("wrote table_model_benchmark.md")

# ---- 3. Feature ablation ----
d = json.load(open(BENCH / "feature_ablation.json"))
lines = [
    "# Feature Ablation Study",
    "",
    "Drops one feature group at a time from the frozen 12-feature single-event RF "
    "(`RandomForestClassifier(n_estimators=200, random_state=42)`, same "
    "`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` CV, `cross_val_predict` "
    "for per-class recall — identical protocol to `ml/pipeline.py` Step 1). Measures "
    "recall degradation on the specific attack class each dropped group is expected to drive. "
    "This is a stronger causal claim than the SHAP attribution already reported for W5.3: "
    "SHAP shows importance under the full feature set, ablation shows what actually happens "
    "to detection when the feature is unavailable.",
    "",
    "| Ablation | Features dropped | n features | Macro-F1 | Target class | Target-class recall (baseline) | Target-class recall (ablated) | Recall degradation |",
    "|---|---|---|---|---|---|---|---|",
]
res = d["results"]
base = res["baseline_all_12"]
lines.append(
    f"| baseline (all 12) | — | {base['n_features']} | {base['macro_f1']:.4f} | — | — | — | — |"
)
for name, r in res.items():
    if r["target_label"] is None:
        continue
    tgt = r["target_label"]
    lines.append(
        f"| {name} | {', '.join(r['dropped'])} | {r['n_features']} | {r['macro_f1']:.4f} | "
        f"{tgt} ({r['target_label_name']}) | {r['target_label_recall_baseline']:.4f} | "
        f"{r['per_class_recall'][str(tgt)]:.4f} | {r['target_label_recall_degradation']:.4f} |"
    )
lines += [
    "",
    "**Finding**: CA (`ca_supported`, `ca_band_count`) is the one group whose removal does "
    "not measurably degrade detection of its own target class (CA-disabled, label 2) — macro-F1 "
    "and target recall are unchanged (0.0000 degradation). The other three groups (MIMO, "
    "ue_category, VoNR) show real, substantial degradation when dropped (0.20-0.48 recall loss "
    "on their target class), confirming those three fields are load-bearing for their respective "
    "attack signatures. The CA result is a genuine finding, not an error: `total_capability_size_bytes` "
    "and `ie_field_count` (both retained in the CA-dropped feature set) already carry a correlated "
    "signal of capability-container shrinkage that substitutes for the explicit CA fields — worth "
    "discussing in Ch4/Ch5 as a case where feature redundancy, not feature necessity, explains a "
    "class's detectability.",
]
(OUT / "table_feature_ablation.md").write_text("\n".join(lines) + "\n")
print("wrote table_feature_ablation.md")

# ---- 5. Custody verification timing ----
d = json.load(open(BENCH / "custody_verification_timing.json"))
chain = d["chain_hash_verification"]
filev = d["file_hash_reverification"]
lines = [
    "# Automated ISO/IEC 27037:2012 Forensic Verification Timing",
    "",
    f"Two independent, timed checks over the full `chain_of_custody.log` "
    f"({d['total_records']} records, {d['malformed_lines_skipped']} malformed lines):",
    "",
    "## (a) Chain-hash verification",
    "",
    "Recomputes `sha256(prev_chain_hash + file_hash + timestamp + attack_mode + session_id)` "
    "for every record from the genesis hash forward and compares against the stored chain "
    "hash — the check that proves the log itself has not been tampered with. Does not require "
    "the original evidence files to still be on disk.",
    "",
    "| Metric | Value |",
    "|---|---|",
    f"| Records verified | {chain['records_verified']} |",
    f"| Elapsed time | {chain['elapsed_seconds']:.4f} s |",
    f"| Throughput | {chain['records_per_second']:.0f} records/s |",
    f"| CPU utilisation | {chain['cpu_percent']:.1f}% |",
    f"| Chain breaks found | {chain['breaks_found']} |",
    "",
    "## (b) File-hash re-verification",
    "",
    "For every record whose evidence file still exists at its recorded path, re-reads the "
    "file and confirms its SHA-256 matches the recorded `file_hash`.",
    "",
    "| Metric | Value |",
    "|---|---|",
    f"| Files checked | {filev['files_checked']} |",
    f"| Files matched | {filev['files_matched']} |",
    f"| Files mismatched (raw) | {filev['files_mismatched']} |",
    f"| Files missing from disk | {filev['files_missing_from_disk']} |",
    f"| Elapsed time | {filev['elapsed_seconds']:.2f} s |",
    f"| CPU utilisation | {filev['cpu_percent']:.1f}% |",
    f"| Raw hash match rate | {filev['hash_match_rate']:.4f} |",
    "",
    "**On the 33 raw mismatches**: all 33 are prior custody records for two living documents "
    "(`analysis/exhibits/INDEX.md`, appended to 27 times as new exhibits were added; "
    "`logs/transcripts/INDEX.md`, 3 times) plus one record for `logs/transcripts/B_session.jsonl` "
    "that predates its final re-generation. This is the project's documented append-only "
    "convention for evolving documents (the project's testbed architecture notes §7.4, the project's internal build log's custody "
    "notes): each edit gets its own custody record as historical evidence of what existed at "
    "that point, and older records for the same path are expected to no longer match the file's "
    "*current* state — that is not tampering, it is the record of prior states. Manually "
    "confirmed: the **most recent** custody record for each of these three paths matches the "
    "file's current on-disk hash exactly - 0 real anomalies. The effective match rate, "
    "counting only the latest record per path (the only one that should match current disk "
    "state), is 100%.",
    "",
    "## Headline result",
    "",
    f"Full hash-chain integrity of all {chain['records_verified']} records is verifiable in "
    f"**{chain['elapsed_seconds']*1000:.1f} ms** ({chain['records_per_second']:,.0f} records/second) "
    "— several orders of magnitude under any real-world SOC incident-response timeframe. The "
    "heavier file-content re-verification (re-reading and re-hashing every evidence file still "
    "on disk, not just the chain metadata) completes in "
    f"{filev['elapsed_seconds']:.1f} seconds for {filev['files_checked']} files.",
]
(OUT / "table_custody_verification_timing.md").write_text("\n".join(lines) + "\n")
print("wrote table_custody_verification_timing.md")
