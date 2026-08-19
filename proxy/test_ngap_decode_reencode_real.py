#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.decode_and_reencode_ngap_pdu()
(Step 3, identity re-encode) against real handset NGAP traffic covering many
message types, not just the capability indication.

test_ngap_decode_decode.py's test_decode_and_reencode_ngap_pdu only exercises
this function against a single UERadioCapabilityInfoIndication frame from the
UERANSIM exhibit pcap. ngap_proxy.py's Step 3 (--stage reencode) re-encodes
*every* NGAP message in *both* directions, of *every* type the gNB and AMF
exchange during a real registration - NGSetupRequest/Response,
InitialUEMessage, uplink/downlink NAS transport, InitialContextSetupRequest/
Response, PDUSessionResourceSetupRequest/Response, and more - not just the
one capability message type. That broader real-world traffic mix had never
been exercised.

data/raw/rrc/spike_verify_label0.pcap and spike_verify_label1.pcap (Build 0d
verification session, real RF + full core, both proxy legs) each capture a
full real registration sequence with 7 distinct NGAP procedure codes. This
file decodes+re-encodes every NGAP frame in both pcaps and confirms every
single one round-trips byte-for-byte identical - not just same length, not
just same procedure code after re-decoding, but bit-for-bit the same bytes
pycrate produced from a genuinely different (real, not synthetic) capture
than every other test in this project uses.

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

# The 7 procedure codes actually observed in these real captures (not
# guessed - found by decoding every frame and recording what showed up).
EXPECTED_PROCEDURE_CODES = {4, 14, 15, 21, 29, 44, 46}


def _all_ngap_raw_frames(pcap_name: str) -> list:
    pcap_path = str(DATA_RAW_RRC / pcap_name)
    cap = pyshark.FileCapture(pcap_path, display_filter="ngap", include_raw=True, use_json=True)
    frames = []
    try:
        for pkt in cap:
            try:
                raw_field = pkt.ngap_raw.value
            except AttributeError:
                continue  # an SCTP frame matched by "ngap" display filter but with no ngap layer of its own
            frames.append(bytes.fromhex(_raw_hex(raw_field)))
    finally:
        try:
            cap.close()
        except Exception:
            pass
    return frames


def _check_pcap_round_trips_every_frame(pcap_name: str) -> dict:
    """Returns {procedure_code: frame_count} for reporting/assertions."""
    frames = _all_ngap_raw_frames(pcap_name)
    assert frames, f"{pcap_name}: expected at least one real NGAP frame"

    procedure_code_counts = {}
    for raw in frames:
        pdu_val = ngap_decode.decode_ngap_pdu(raw)
        assert pdu_val is not None, f"{pcap_name}: a real NGAP frame failed to decode"
        proc_code = ngap_decode.get_procedure_code(pdu_val)
        assert proc_code is not None

        reencoded = ngap_decode.decode_and_reencode_ngap_pdu(raw)
        assert reencoded is not None, f"{pcap_name}: procedureCode={proc_code} frame failed to re-encode"
        assert reencoded == raw, (
            f"{pcap_name}: procedureCode={proc_code} frame did not round-trip byte-for-byte "
            f"(original {len(raw)} bytes, re-encoded {len(reencoded)} bytes)"
        )

        redecoded = ngap_decode.decode_ngap_pdu(reencoded)
        assert redecoded is not None
        assert ngap_decode.get_procedure_code(redecoded) == proc_code

        procedure_code_counts[proc_code] = procedure_code_counts.get(proc_code, 0) + 1

    return procedure_code_counts


def test_label1_capture_every_frame_round_trips_byte_identical() -> None:
    counts = _check_pcap_round_trips_every_frame("spike_verify_label1.pcap")
    assert set(counts.keys()) == EXPECTED_PROCEDURE_CODES, (
        f"expected procedure codes {EXPECTED_PROCEDURE_CODES}, got {set(counts.keys())} - "
        "real traffic mix may have changed, worth re-checking this test's assumptions"
    )
    assert sum(counts.values()) == 32, f"expected 32 total NGAP frames, got {sum(counts.values())}"
    print(f"test_label1_capture_every_frame_round_trips_byte_identical: PASSED ({counts})")


def test_label0_capture_every_frame_round_trips_byte_identical() -> None:
    counts = _check_pcap_round_trips_every_frame("spike_verify_label0.pcap")
    assert set(counts.keys()) == EXPECTED_PROCEDURE_CODES
    print(f"test_label0_capture_every_frame_round_trips_byte_identical: PASSED ({counts})")


def main() -> int:
    test_label1_capture_every_frame_round_trips_byte_identical()
    test_label0_capture_every_frame_round_trips_byte_identical()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
