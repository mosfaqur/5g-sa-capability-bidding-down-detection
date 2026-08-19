#!/usr/bin/env python3
"""Build features/xlayer.csv: cross-layer consistency features for real-handset
N2 events, each paired against that UE's persisted per-IMSI case-a RRC
reference (data/raw/rrc/reference/<imsi>.json), not against any RRC record
sharing its own registration/reattach cycle - "Cached-reattach
(case b) live validation" and SS6.1/SS7.1 of the project's testbed architecture notes for why pairing
against a same-cycle RRC record silently misses attacks already baked into the
AMF's cache before a reattach. UERANSIM rows are excluded (no valid RRC
reference - real-handset only).

Usage:
    build_xlayer.py [--input features/raw_12f.csv] [--reference-dir data/raw/rrc/reference]
                     [--output features/xlayer.csv]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from extract_features import xlayer

REAL_HANDSET_PROFILES = {
    "pixel8": "001010000000002",
    "nothing3a": "001010000000003",
}


def load_reference(reference_dir: Path, imsi: str) -> dict:
    data = json.loads((reference_dir / f"{imsi}.json").read_text())
    record = dict(data["record"])
    record["container_bytes"] = bytes.fromhex(record["container_bytes"])
    return record


def n2_record_from_row(row: pd.Series) -> dict:
    return {
        "ue_category": int(row["ue_category"]),
        "ca_supported": bool(row["ca_supported"]),
        "ca_band_count": int(row["ca_band_count"]),
        "mimo_layers_dl": int(row["mimo_layers_dl"]),
        "mimo_layers_ul": int(row["mimo_layers_ul"]),
        "vonr_supported": bool(row["vonr_supported"]),
        "nr_band_count": int(row["nr_band_count"]),
        "capability_size_bytes": int(row["total_capability_size_bytes"]),
        "ie_field_count": int(row["ie_field_count"]),
        # Unused by xlayer() whenever the paired rrc_record is byte_exact=False
        # (the case-a reference this script always uses) - not a real container.
        "container_bytes": b"",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="features/raw_12f.csv")
    p.add_argument("--reference-dir", default="data/raw/rrc/reference")
    p.add_argument("--output", default="features/xlayer.csv")
    args = p.parse_args()

    df = pd.read_csv(args.input, dtype={"ue_imsi": str})
    reference_dir = Path(args.reference_dir)

    references = {
        profile: load_reference(reference_dir, imsi)
        for profile, imsi in REAL_HANDSET_PROFILES.items()
    }

    rows = []
    for _, row in df.iterrows():
        profile = row["ue_profile"]
        if profile not in REAL_HANDSET_PROFILES:
            continue
        rrc_record = references[profile]
        n2_record = n2_record_from_row(row)
        result = xlayer(rrc_record, n2_record)
        rows.append({"session_id": row["session_id"], "ue_profile": profile, "label": int(row["label"]), **result})

    out = pd.DataFrame(rows)
    out.to_csv(args.output, index=False)
    print(f"wrote {len(out)} cross-layer rows to {args.output}")
    print(out["ue_profile"].value_counts())


if __name__ == "__main__":
    main()
