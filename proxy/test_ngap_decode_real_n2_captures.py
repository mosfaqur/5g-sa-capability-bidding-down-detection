#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.decode_ue_radio_capability_container()
against real handset N2 wire captures (not UERANSIM-synthetic).

Every prior test of this function (test_ngap_decode_decode.py,
test_ngap_decode_pipeline.py) used only the committed exhibit pcap
(data/raw/exhibits/ngap_label0_full.pcap) - a UERANSIM SW-Std capture, always
either the native minimal UERANSIM capability or a Stage 1 profile
substitution. It had never been run against a genuinely real handset's own
N2 capability bytes, as they actually appear on the wire before any Stage 1
substitution (real handsets skip Stage 1 entirely - the project's testbed architecture notes
§6.1).

data/raw/rrc/spike_verify_label0.pcap and spike_verify_label1.pcap (from the
Build 0d verification session, both proxy legs per Bug 16) are exactly this:
real RF, full core, a real Nokia-CPE-like device (label 0) and Samsung A56
(label 1) registering with --profile unset (real-handset mode). Both frames
in each pcap are decoded here directly with decode_ue_radio_capability_container,
independent of rrc_capture.py's RRC-side JSON decode path.

Cross-validation bonus: the Samsung A56's band list decoded here from real N2
wire bytes matches, band-for-band, what test_ngap_decode_summarize_real.py
independently found decoding the *RRC-side* JSON capture for the same device
(data/raw/rrc/rrc_1_a56_build-0d-verify3-20260730_0.json) - two independent
decode paths (N2 PER bytes vs. RRC JSON dump) agreeing on the same real
device's capability.

Run under proxy/venv (needs pyshark+pycrate). Read-only against the
committed pcaps.
"""
import sys
from pathlib import Path

import pyshark

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
from extract_features import _raw_hex  # noqa: E402

DATA_RAW_RRC = Path(__file__).resolve().parent.parent / "data/raw/rrc"

# Same band list independently found decoding the RRC-side JSON capture for
# this device in test_ngap_decode_summarize_real.py.
SAMSUNG_A56_BAND_IDS = [1, 3, 5, 7, 8, 28, 38, 40, 41, 66, 77, 78]


def _decode_all_capability_frames(pcap_name: str) -> list:
    pcap_path = str(DATA_RAW_RRC / pcap_name)
    cap = pyshark.FileCapture(
        pcap_path,
        display_filter=f"ngap.procedureCode=={ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION}",
        include_raw=True,
        use_json=True,
    )
    summaries = []
    try:
        for pkt in cap:
            raw = bytes.fromhex(_raw_hex(pkt.ngap_raw.value))
            pdu_val = ngap_decode.decode_ngap_pdu(raw)
            assert pdu_val is not None, f"{pcap_name}: a frame matched by the NGAP display filter failed to decode"
            cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
            assert cap_bytes is not None, f"{pcap_name}: UERadioCapabilityInfoIndication frame missing IE 117"
            decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
            assert decoded is not None, f"{pcap_name}: decode_ue_radio_capability_container failed on a real frame"
            assert decoded["ratType"] == "nr"
            summaries.append(ngap_decode.summarize_capability(decoded["capability"]))
    finally:
        try:
            cap.close()
        except Exception:
            pass
    return summaries


def test_real_label0_capture_decodes_both_frames_identically() -> None:
    """Label 0 (Normal): real-handset mode skips Stage 1, and label 0 is a
    Stage 2 no-op - both proxy-leg frames (pre- and post-rewrite) must be
    byte-for-byte the same capability content."""
    summaries = _decode_all_capability_frames("spike_verify_label0.pcap")
    assert len(summaries) == 2, f"expected 2 frames (both proxy legs), got {len(summaries)}"
    assert summaries[0] == summaries[1], "label 0 (no-op) must leave both frames identical"
    assert summaries[0]["access_stratum_release"] == "rel15"
    assert summaries[0]["ca_supported"] is True
    assert summaries[0]["band_count"] == 10
    print("test_real_label0_capture_decodes_both_frames_identically: PASSED")


def test_real_label1_capture_isolates_the_attacked_field() -> None:
    """Label 1 (Cat downgrade) on a real Samsung A56: the pre-rewrite frame
    must show the device's genuine accessStratumRelease (rel15); the
    post-rewrite frame must show spare1 (the label-1 downgrade target) with
    every other field - band list, CA, MIMO, VoNR - unchanged from the real
    device's own native capability."""
    summaries = _decode_all_capability_frames("spike_verify_label1.pcap")
    assert len(summaries) == 2, f"expected 2 frames (both proxy legs), got {len(summaries)}"
    pre_rewrite, post_rewrite = summaries

    assert pre_rewrite["access_stratum_release"] == "rel15"
    assert post_rewrite["access_stratum_release"] == "spare1"

    for field in ("band_count", "band_ids", "ca_supported", "mimo_dl_layers", "mimo_ul_layers", "vonr_supported"):
        assert pre_rewrite[field] == post_rewrite[field], (
            f"label 1 must isolate the attack to accessStratumRelease only - {field} differs "
            f"({pre_rewrite[field]!r} vs {post_rewrite[field]!r})"
        )
    print("test_real_label1_capture_isolates_the_attacked_field: PASSED")


def test_samsung_a56_band_list_matches_independent_rrc_side_decode() -> None:
    """Cross-validation: the same real device's band list, decoded here from
    real N2 PER wire bytes, must match what test_ngap_decode_summarize_real.py
    independently decoded from the RRC-side JSON capture for this device -
    two different decode paths (N2 vs. RRC), same real capability."""
    summaries = _decode_all_capability_frames("spike_verify_label1.pcap")
    assert summaries[0]["band_ids"] == SAMSUNG_A56_BAND_IDS
    assert summaries[0]["band_count"] == len(SAMSUNG_A56_BAND_IDS)
    print("test_samsung_a56_band_list_matches_independent_rrc_side_decode: PASSED")


def main() -> int:
    test_real_label0_capture_decodes_both_frames_identically()
    test_real_label1_capture_isolates_the_attacked_field()
    test_samsung_a56_band_list_matches_independent_rrc_side_decode()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
