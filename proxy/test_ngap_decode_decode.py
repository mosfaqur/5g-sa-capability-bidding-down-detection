#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.py's core decode functions:
decode_ngap_pdu, decode_and_reencode_ngap_pdu, get_procedure_code,
extract_protocol_ie, decode_ue_radio_capability_container, and
summarize_capability's own edge cases.

These are exercised indirectly, and only along their "everything works"
path, by test_ngap_decode_pipeline.py, test_ngap_decode_profiles.py,
test_rrc_capture.py, and test_extract_features.py - none of those hit the
failure/edge branches directly: garbage input to each function, a
malformed/absent pdu_val passed to get_procedure_code/extract_protocol_ie,
or - the one genuinely never-exercised branch across every test file so
far - decode_ue_radio_capability_container()'s "no nr RAT item found"
path (an LTE-only eutra capability container, decodable at every layer but
with no nr entry in the RAT container list).

Requires pyshark/tshark + pycrate - run under proxy/venv.
Never writes anything - read-only against the committed exhibit pcap.
"""
import sys
from pathlib import Path

import pyshark

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
from extract_features import _raw_hex  # noqa: E402

EXHIBIT_PCAP = str(Path(__file__).resolve().parent.parent / "data/raw/exhibits/ngap_label0_full.pcap")


def _extract_raw_capability_pdus() -> list:
    cap = pyshark.FileCapture(
        EXHIBIT_PCAP,
        display_filter=f"ngap.procedureCode=={ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION}",
        include_raw=True,
        use_json=True,
    )
    pdus = []
    try:
        for pkt in cap:
            pdus.append(bytes.fromhex(_raw_hex(pkt.ngap_raw.value)))
    finally:
        try:
            cap.close()
        except Exception:
            pass
    return pdus


def test_decode_ngap_pdu_valid_and_garbage(pdus) -> None:
    pdu_val = ngap_decode.decode_ngap_pdu(pdus[0])
    assert pdu_val is not None
    assert ngap_decode.get_procedure_code(pdu_val) == ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION

    assert ngap_decode.decode_ngap_pdu(b"not a valid ngap pdu") is None
    assert ngap_decode.decode_ngap_pdu(b"") is None
    print("test_decode_ngap_pdu_valid_and_garbage: PASSED")


def test_decode_and_reencode_ngap_pdu(pdus) -> None:
    reencoded = ngap_decode.decode_and_reencode_ngap_pdu(pdus[0])
    assert reencoded is not None
    pdu_val = ngap_decode.decode_ngap_pdu(reencoded)
    assert pdu_val is not None
    assert ngap_decode.get_procedure_code(pdu_val) == ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION

    assert ngap_decode.decode_and_reencode_ngap_pdu(b"garbage") is None
    print("test_decode_and_reencode_ngap_pdu: PASSED")


def test_get_procedure_code_edge_cases(pdus) -> None:
    pdu_val = ngap_decode.decode_ngap_pdu(pdus[0])
    assert ngap_decode.get_procedure_code(pdu_val) == 44
    assert ngap_decode.get_procedure_code(None) is None
    assert ngap_decode.get_procedure_code("not a tuple") is None
    assert ngap_decode.get_procedure_code(()) is None
    print("test_get_procedure_code_edge_cases: PASSED")


def test_extract_protocol_ie_edge_cases(pdus) -> None:
    pdu_val = ngap_decode.decode_ngap_pdu(pdus[0])
    ie = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    assert ie is not None and isinstance(ie, (bytes, bytearray))

    assert ngap_decode.extract_protocol_ie(pdu_val, 999999) is None, "an IE id not present must return None"
    assert ngap_decode.extract_protocol_ie(None, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY) is None
    assert ngap_decode.extract_protocol_ie("not a tuple", 1) is None
    print("test_extract_protocol_ie_edge_cases: PASSED")


def test_decode_ue_radio_capability_container_valid(pdus) -> None:
    pdu_val = ngap_decode.decode_ngap_pdu(pdus[0])
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    assert decoded is not None
    assert decoded["ratType"] == "nr"
    assert "accessStratumRelease" in decoded["capability"]
    print("test_decode_ue_radio_capability_container_valid: PASSED")


def test_decode_ue_radio_capability_container_garbage_returns_none() -> None:
    assert ngap_decode.decode_ue_radio_capability_container(b"not valid uper at all") is None
    assert ngap_decode.decode_ue_radio_capability_container(b"") is None
    print("test_decode_ue_radio_capability_container_garbage_returns_none: PASSED")


def test_decode_ue_radio_capability_container_no_nr_rat_item() -> None:
    """Genuinely never exercised elsewhere: an LTE-only (eutra) capability
    container, decodable at every layer, but with no 'nr' entry in the RAT
    container list - decode_ue_radio_capability_container must return None
    (the "no nr RAT present" branch, per its own docstring), not raise or
    return an eutra capability mislabeled as nr."""
    with ngap_decode._lock:
        ngap_decode._l3.set_val([{"rat-Type": "eutra", "ue-CapabilityRAT-Container": b"\x00\x01\x02\x03"}])
        l3_bytes = ngap_decode._l3.to_uper()
        ngap_decode._l2.set_val(
            {
                "criticalExtensions": (
                    "c1",
                    ("ueRadioAccessCapabilityInformation", {"ue-RadioAccessCapabilityInfo": l3_bytes}),
                )
            }
        )
        l2_bytes = ngap_decode._l2.to_uper()

    result = ngap_decode.decode_ue_radio_capability_container(l2_bytes)
    assert result is None, "an eutra-only RAT container list must decode to None, not a mislabeled nr capability"
    print("test_decode_ue_radio_capability_container_no_nr_rat_item: PASSED")


def test_summarize_capability_empty_dict() -> None:
    """The true "nothing present at all" edge case - no rf-Parameters,
    featureSets, or nonCriticalExtension keys at all."""
    summary = ngap_decode.summarize_capability({})
    assert summary["access_stratum_release"] is None
    assert summary["band_count"] == 0
    assert summary["band_ids"] == []
    assert summary["ca_supported"] is False
    assert summary["mimo_dl_layers"] is None
    assert summary["mimo_ul_layers"] is None
    assert summary["vonr_supported"] is False
    print("test_summarize_capability_empty_dict: PASSED")


def main() -> int:
    pdus = _extract_raw_capability_pdus()
    assert len(pdus) == 2

    test_decode_ngap_pdu_valid_and_garbage(pdus)
    test_decode_and_reencode_ngap_pdu(pdus)
    test_get_procedure_code_edge_cases(pdus)
    test_extract_protocol_ie_edge_cases(pdus)
    test_decode_ue_radio_capability_container_valid(pdus)
    test_decode_ue_radio_capability_container_garbage_returns_none()
    test_decode_ue_radio_capability_container_no_nr_rat_item()
    test_summarize_capability_empty_dict()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
