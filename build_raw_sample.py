#!/usr/bin/env python3
"""Build a stratified sample of data/raw/ PCAPs for the public release repo.

Reads logs/collection_manifest.csv, groups by (ue_profile, label), samples up
to N events per group (deterministic: first N by manifest row order), and
copies the referenced pcap_path (and rrc_path, if present) into
data/raw_sample/, preserving the original relative subpaths.
"""
import csv
import shutil
import sys
from pathlib import Path
from collections import defaultdict

SRC_ROOT = Path("/root/comp997")
DST_ROOT = Path("/root/comp997-release")
MANIFEST = DST_ROOT / "logs" / "collection_manifest.csv"
SAMPLE_DIR = DST_ROOT / "data" / "raw_sample"
MAX_TOTAL_BYTES = 60 * 1024 * 1024


def load_groups():
    groups = defaultdict(list)
    with open(MANIFEST, newline="") as f:
        for row in csv.DictReader(f):
            groups[(row["ue_profile"], row["label"])].append(row)
    return groups


def copy_for_row(row, copied_paths, total_bytes):
    added = 0
    for key in ("pcap_path", "rrc_path"):
        rel = row.get(key, "").strip()
        if not rel or rel in copied_paths:
            continue
        src = SRC_ROOT / rel
        if not src.is_file():
            continue
        dst = SAMPLE_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied_paths.add(rel)
        added += src.stat().st_size
    return added


def build_sample(per_group):
    groups = load_groups()
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    copied_paths = set()
    total_bytes = 0
    per_group_counts = {}
    for key in sorted(groups):
        rows = groups[key][:per_group]
        n = 0
        for row in rows:
            added = copy_for_row(row, copied_paths, total_bytes)
            if added:
                total_bytes += added
                n += 1
        per_group_counts[key] = n
    return per_group_counts, total_bytes, copied_paths


def copy_live_validation():
    src = SRC_ROOT / "data" / "raw_validation_live"
    if not src.is_dir():
        return 0
    dst = DST_ROOT / "data" / "raw_validation_live"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return sum(f.stat().st_size for f in dst.rglob("*") if f.is_file())


def main():
    for per_group in (3, 2):
        if SAMPLE_DIR.exists():
            shutil.rmtree(SAMPLE_DIR)
        counts, total_bytes, copied_paths = build_sample(per_group)
        if total_bytes <= MAX_TOTAL_BYTES:
            break
        print(f"per_group={per_group} exceeded budget "
              f"({total_bytes/1e6:.1f}MB) - reducing", file=sys.stderr)
    else:
        print(f"WARNING: even per_group=2 exceeds {MAX_TOTAL_BYTES/1e6:.0f}MB "
              f"budget ({total_bytes/1e6:.1f}MB) - reporting actual, not truncating further",
              file=sys.stderr)

    live_bytes = copy_live_validation()

    print(f"per_group used: {per_group}")
    print(f"raw_sample files copied: {len(copied_paths)}")
    print(f"raw_sample bytes: {total_bytes} ({total_bytes/1e6:.2f} MB)")
    print(f"raw_validation_live bytes copied: {live_bytes} ({live_bytes/1e6:.2f} MB)")
    print(f"total sample bytes: {total_bytes + live_bytes} ({(total_bytes+live_bytes)/1e6:.2f} MB)")
    print()
    print("Per (profile,label) counts:")
    for key in sorted(counts):
        print(f"  {key[0]:10s} label {key[1]}: {counts[key]}")

    per_group_note = (
        f"reduced here to {per_group} because the full sample of 3 per group would have "
        f"exceeded the 60MB budget"
        if per_group == 2
        else f"kept here at {per_group}, the full target, since the budget was comfortably met"
    )
    readme_lines = [
        "# data/raw_sample/",
        "",
        "What follows is a stratified sample of the full labelled N2 capture dataset, not the",
        "dataset itself. The full collection runs to approximately 5,251 raw PCAPs (406MB),",
        "underpinning a 4,225-event single-view feature matrix, and is available on request, or",
        "regenerable from the testbed procedure that this project's internal documentation",
        "describes in detail, although that documentation is not distributed with this",
        "repository. What is included here is instead sufficient to illustrate the raw capture",
        "format without substantially bloating the repository.",
        "",
        "## Sampling method",
        "",
        "`build_raw_sample.py`, at the repository root, reads `logs/collection_manifest.csv`, "
        "groups rows by `(ue_profile, label)` and copies, for each group, the first "
        f"{per_group} event(s)' `pcap_path` (and `rrc_path`, where present), preserving the "
        "manifest's original relative subpaths under this directory. The target budget was set "
        f"at under 60MB total, and the per-group count was {per_group_note}.",
        "",
        "`data/raw_validation_live/` (the Session F live-validation captures, already small) is "
        "copied in full alongside this sample rather than being sub-sampled in turn.",
        "",
        "## Final per-(profile, label) counts",
        "",
        "| Profile | Label | Events sampled |",
        "|---|---|---|",
    ]
    for key in sorted(counts):
        readme_lines.append(f"| {key[0]} | {key[1]} | {counts[key]} |")
    readme_lines += [
        "",
        f"This gives a total of {len(copied_paths)} files, {total_bytes/1e6:.2f} MB, plus a "
        f"further {live_bytes/1e6:.2f} MB from `data/raw_validation_live/`.",
        "",
    ]
    (SAMPLE_DIR / "README.md").write_text("\n".join(readme_lines))


if __name__ == "__main__":
    main()
