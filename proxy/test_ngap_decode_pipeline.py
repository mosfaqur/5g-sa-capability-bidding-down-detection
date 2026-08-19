#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_capability_pipeline() (Steps 4+5
combined: Stage 1 profile-baseline rewrite + Stage 2 attack modifier, applied
to a full NGAP PDU).

This is the one function in ngap_decode.py that had never been exercised by
any committed test with a real NGAP PDU - test_relay_smoke.py's "rewrite"
stage only ever sends dummy PING/PONG bytes (not valid NGAP), so
apply_capability_pipeline always hit its very first decode-failure branch
there and returned None. Every test below feeds it real, complete
UERadioCapabilityInfoIndication PDUs extracted from the committed exhibit
pcap (both the pre-rewrite/native-UERANSIM frame and the post-rewrite/SW-Std
frame), the same technique features/extract_features.py uses.

Requires pyshark/tshark - run under proxy/venv:
    ../proxy/venv/bin/python3 test_ngap_decode_pipeline.py  (if invoked from proxy/, just:
    ./venv/bin/python3 test_ngap_decode_pipeline.py)

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
    """Every UERadioCapabilityInfoIndication frame's raw NGAP PDU bytes, in
    capture order, from the committed label-0 exhibit pcap (both proxy legs -
    see the project's internal build log Bug 16): [0] is the pre-rewrite (gNB->proxy, native
    UERANSIM minimal capability), [1] is the post-rewrite (proxy->AMF, SW-Std
    Stage 1 baseline)."""
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


def _summarize_output(rewritten: bytes) -> dict:
    """Decode a full apply_capability_pipeline() output back down to a
    summarize_capability() dict, confirming the whole-PDU re-encode is valid
    NGAP, procedureCode is still 44, and IE 117 is still present - not just
    that the capability content looks right in isolation."""
    pdu_val = ngap_decode.decode_ngap_pdu(rewritten)
    assert pdu_val is not None, "rewritten PDU must still decode as valid NGAP"
    assert ngap_decode.get_procedure_code(pdu_val) == ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    assert cap_bytes is not None, "IE 117 must still be present after rewrite"
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    assert decoded is not None
    return ngap_decode.summarize_capability(decoded["capability"])


def test_profile_mode_rewrites_to_profile_baseline(pdus) -> None:
    """profile='sw-std', label=0: whatever the input PDU's own capability was,
    the output must be exactly the SW-Std Stage 1 baseline - profile mode
    discards the incoming capability entirely (the project's testbed architecture notes §6.2)."""
    for name, pdu in [("native/pre-rewrite", pdus[0]), ("already-SW-Std/post-rewrite", pdus[1])]:
        rewritten = ngap_decode.apply_capability_pipeline(pdu, profile="sw-std", label=0)
        assert rewritten is not None, f"rewrite failed for input {name}"
        summary = _summarize_output(rewritten)
        assert summary["access_stratum_release"] == "rel15"
        assert summary["ca_supported"] is True
        assert summary["mimo_dl_layers"] == ["twoLayers"]
        assert summary["mimo_ul_layers"] == ["oneLayer"]
        assert summary["vonr_supported"] is True
        assert summary["band_ids"] == [78]
    print("test_profile_mode_rewrites_to_profile_baseline: PASSED")


def test_profile_mode_with_label_applies_stage2_on_top(pdus) -> None:
    """profile='sw-std', label=4 (VoNR denied): output must be the SW-Std
    baseline with VoNR specifically stripped - CA/MIMO must remain the SW-Std
    values, confirming Stage 2 applies on top of the Stage 1 baseline, not
    instead of it."""
    rewritten = ngap_decode.apply_capability_pipeline(pdus[0], profile="sw-std", label=4)
    assert rewritten is not None
    summary = _summarize_output(rewritten)
    assert summary["ca_supported"] is True, "label 4 must not touch CA"
    assert summary["mimo_dl_layers"] == ["twoLayers"], "label 4 must not touch MIMO"
    assert summary["vonr_supported"] is False, "label 4 must strip VoNR"
    print("test_profile_mode_with_label_applies_stage2_on_top: PASSED")


def test_real_handset_mode_label_0_is_passthrough(pdus) -> None:
    """profile=None (real-handset path): label 0 must forward the UE's own
    native capability unchanged - confirmed against the actual native
    UERANSIM minimal capability captured in the pre-rewrite frame."""
    pdu_val = ngap_decode.decode_ngap_pdu(pdus[0])
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    native_before = ngap_decode.summarize_capability(
        ngap_decode.decode_ue_radio_capability_container(cap_bytes)["capability"]
    )

    rewritten = ngap_decode.apply_capability_pipeline(pdus[0], profile=None, label=0)
    assert rewritten is not None
    native_after = _summarize_output(rewritten)

    assert native_after["access_stratum_release"] == native_before["access_stratum_release"]
    assert native_after["ca_supported"] == native_before["ca_supported"]
    assert native_after["mimo_dl_layers"] == native_before["mimo_dl_layers"]
    assert native_after["vonr_supported"] == native_before["vonr_supported"]
    print("test_real_handset_mode_label_0_is_passthrough: PASSED")


def test_real_handset_mode_applies_label_on_native_capability(pdus) -> None:
    """profile=None, label=1 (cat downgrade): must apply on top of the UE's
    own native capability, not silently substitute a profile template - the
    non-category fields must stay exactly what the native capability's own
    values were, whatever those happen to be, while accessStratumRelease
    becomes spare1."""
    pdu_val = ngap_decode.decode_ngap_pdu(pdus[0])
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    native_before = ngap_decode.summarize_capability(
        ngap_decode.decode_ue_radio_capability_container(cap_bytes)["capability"]
    )

    rewritten = ngap_decode.apply_capability_pipeline(pdus[0], profile=None, label=1)
    assert rewritten is not None
    result = _summarize_output(rewritten)

    assert result["access_stratum_release"] == "spare1"
    assert result["ca_supported"] == native_before["ca_supported"], "label 1 must not touch CA"
    assert result["vonr_supported"] == native_before["vonr_supported"], "label 1 must not touch VoNR"
    print("test_real_handset_mode_applies_label_on_native_capability: PASSED")


def test_returns_none_for_garbage_bytes() -> None:
    rewritten = ngap_decode.apply_capability_pipeline(b"not a valid ngap pdu at all", profile="sw-std", label=0)
    assert rewritten is None
    print("test_returns_none_for_garbage_bytes: PASSED")


def test_returns_none_for_unknown_profile(pdus) -> None:
    rewritten = ngap_decode.apply_capability_pipeline(pdus[0], profile="not-a-real-profile", label=0)
    assert rewritten is None
    print("test_returns_none_for_unknown_profile: PASSED")


def main() -> int:
    pdus = _extract_raw_capability_pdus()
    assert len(pdus) == 2, f"expected 2 UERadioCapabilityInfoIndication frames in the exhibit pcap, got {len(pdus)}"

    test_profile_mode_rewrites_to_profile_baseline(pdus)
    test_profile_mode_with_label_applies_stage2_on_top(pdus)
    test_real_handset_mode_label_0_is_passthrough(pdus)
    test_real_handset_mode_applies_label_on_native_capability(pdus)
    test_returns_none_for_garbage_bytes()
    test_returns_none_for_unknown_profile(pdus)
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
