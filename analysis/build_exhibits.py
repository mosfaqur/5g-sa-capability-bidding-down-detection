#!/usr/bin/env python3
"""Builds analysis/exhibits/decoded_<mode>.txt (tshark -V dump, pre- and
post-rewrite legs of a representative registration per mode) and
analysis/exhibits/xlayer_<mode>.txt (paired RRC-vs-N2 decode for a real
handset event per mode, using the Nothing 3A profile — has valid data for
all 7 labels).
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/root/comp997/proxy")
import ngap_decode  # noqa: E402
sys.path.insert(0, "/root/comp997/features")
import extract_features  # noqa: E402

ROOT = Path("/root/comp997")
EXDIR = ROOT / "analysis/exhibits"
EXDIR.mkdir(parents=True, exist_ok=True)

MODE_NAMES = {0:"Normal",1:"Cat-downgrade",2:"CA-disabled",3:"MIMO-reduced",
              4:"VoNR-denied",5:"Combined",6:"Partial-noise"}

DECODE_PCAPS = {
    0: ROOT / "data/raw/exhibits/ngap_label0_full.pcap",
    1: ROOT / "data/raw/validation/ngap_swstd_label1_full.pcap",
    2: ROOT / "data/raw/validation/ngap_swstd_label2_full.pcap",
    3: ROOT / "data/raw/validation/ngap_swstd_label3_full.pcap",
    4: ROOT / "data/raw/validation/ngap_swstd_label4_full.pcap",
    5: ROOT / "data/raw/exhibits/ngap_label5_full.pcap",
    6: ROOT / "data/raw/exhibits/ngap_label6_full.pcap",
}

# ---------- Part 1: decoded_<mode>.txt ----------
def tshark_v(pcap, frame_number):
    out = subprocess.run(
        ["tshark", "-r", str(pcap), "-Y", f"frame.number=={frame_number}", "-V"],
        capture_output=True, text=True,
    )
    return out.stdout

for mode, pcap in DECODE_PCAPS.items():
    frames = subprocess.run(
        ["tshark", "-r", str(pcap), "-Y", "ngap.procedureCode==44",
         "-T", "fields", "-e", "frame.number", "-e", "sctp.dstport"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    out_path = EXDIR / f"decoded_{mode}.txt"
    with open(out_path, "w") as f:
        f.write(f"# Decoded UERadioCapabilityInfoIndication exhibit — mode {mode} ({MODE_NAMES[mode]})\n")
        f.write(f"# Source: {pcap.relative_to(ROOT)}\n")
        f.write(f"# Frames found (frame_number, dst_port): {frames}\n")
        f.write("# Port 38412 = gNB-facing leg (pre-rewrite); port 38413 = AMF-facing leg (post-rewrite, what the AMF actually cached)\n")
        f.write("#" + "=" * 78 + "\n\n")
        for line in frames:
            fn, port = line.split("\t")
            f.write(f"\n\n{'='*80}\nFRAME {fn} (dst_port={port}, {'PRE-REWRITE / gNB leg' if port=='38412' else 'POST-REWRITE / AMF leg (cached)' if port=='38413' else port})\n{'='*80}\n\n")
            f.write(tshark_v(pcap, fn))
    print(f"Wrote {out_path}")

# ---------- Part 2: xlayer_<mode>.txt (real handset RRC-vs-N2, Nothing 3A) ----------
XLAYER_PCAPS = {m: ROOT / f"data/raw/{m}/capture_{m}_nothing3a_nothing3a-{m}-run01-20260810T175015_10.pcap" for m in range(7)}
XLAYER_RRC = {m: ROOT / f"data/raw/rrc/rrc_{m}_nothing3a_nothing3a-{m}-run01-20260810T175015_10.json" for m in range(7)}
REFERENCE = ROOT / "data/raw/rrc/reference/001010000000003.json"

ref_record = json.loads(REFERENCE.read_text())["record"]

for mode in range(7):
    pcap = XLAYER_PCAPS[mode]
    rrc_path = XLAYER_RRC[mode]
    if not pcap.exists() or not rrc_path.exists():
        print(f"SKIP mode {mode}: missing {pcap if not pcap.exists() else rrc_path}")
        continue
    rrc_full = json.loads(rrc_path.read_text())
    rrc_record = rrc_full["record"]

    n2_rows = extract_features.extract(str(pcap))
    n2_record = n2_rows[-1] if n2_rows else None  # post-rewrite/AMF leg, per Bug 16 / rows[-1] convention

    xdiff = extract_features.xlayer(rrc_record, n2_record) if n2_record else None
    xdiff_vs_ref = extract_features.xlayer(ref_record, n2_record) if n2_record else None

    out_path = EXDIR / f"xlayer_{mode}.txt"
    with open(out_path, "w") as f:
        f.write(f"# Cross-layer (RRC-vs-N2) exhibit — mode {mode} ({MODE_NAMES[mode]})\n")
        f.write(f"# Profile: Nothing 3A (imsi-001010000000003)\n")
        f.write(f"# RRC source: {rrc_path.relative_to(ROOT)}\n")
        f.write(f"# N2 source: {pcap.relative_to(ROOT)} (post-rewrite/AMF-facing frame, last in capture order)\n\n")
        f.write("## RRC-side record (gNodeB-observed, untampered reference)\n")
        f.write(json.dumps(rrc_record, indent=2) + "\n\n")
        f.write("## N2-side record (AMF-facing, post-proxy-rewrite)\n")
        f.write(json.dumps(n2_record, indent=2, default=str) + "\n\n")
        f.write("## xlayer(rrc_this_event, n2) — same-registration pairing (documented as CIRCULAR for case-b reattach; shown for reference)\n")
        f.write(json.dumps(xdiff, indent=2, default=str) + "\n\n")
        f.write("## xlayer(persisted_case-a_reference, n2) — the actual project methodology (non-circular join, see the project's internal build log 'Cached-reattach (case b) live validation')\n")
        f.write(f"# reference source: {REFERENCE.relative_to(ROOT)}\n")
        f.write(json.dumps(xdiff_vs_ref, indent=2, default=str) + "\n")
    print(f"Wrote {out_path}")
