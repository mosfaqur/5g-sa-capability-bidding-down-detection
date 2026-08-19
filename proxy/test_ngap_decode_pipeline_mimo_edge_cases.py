#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_capability_pipeline() against
the SISO/absent-DL MIMO edge case (label 3, Cat MIMO-reduced), through the
*full* pipeline (real NGAP PDU in, decode/apply/re-encode, real NGAP PDU out)
rather than testing apply_mimo_reduced() in isolation.

test_ngap_decode_stage2.py's test_apply_mimo_reduced_already_siso_is_noop
already confirms apply_mimo_reduced() itself is a no-op on SW-Min's baseline
(no featureSets key at all) - but that calls the modifier function directly
on a plain dict, never through apply_capability_pipeline() with a real NGAP
PDU wrapper, so the whole-PDU decode/re-encode path around it had never been
exercised for this specific case. And a second, more specific edge case had
never been tested anywhere in this project: apply_mimo_reduced()'s DL/UL
branches are independent (`if fs_dl:` / `if fs_ul:`) - none of
PROFILE_CAPABILITIES's three profiles, and none of the real committed
captures, has a capability with `featureSets` present but only *one* of
`featureSetsDownlinkPerCC`/`featureSetsUplinkPerCC` populated (real 3GPP
capabilities can report only one direction's feature sets). Constructs that
mixed shape by hand, embeds it as a real device's native capability inside a
real captured NGAP PDU (by swapping IE 117's content), and runs it through
apply_capability_pipeline() in real-handset mode (profile=None) with label=3.

Run under proxy/venv (needs pyshark+pycrate). Read-only against the
committed exhibit pcap.
"""
import sys
from pathlib import Path

import pyshark

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
from extract_features import _raw_hex  # noqa: E402

EXHIBIT_PCAP = str(Path(__file__).resolve().parent.parent / "data/raw/exhibits/ngap_label0_full.pcap")


def _first_capability_pdu() -> bytes:
    cap = pyshark.FileCapture(
        EXHIBIT_PCAP,
        display_filter=f"ngap.procedureCode=={ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION}",
        include_raw=True,
        use_json=True,
    )
    try:
        for pkt in cap:
            return bytes.fromhex(_raw_hex(pkt.ngap_raw.value))
    finally:
        try:
            cap.close()
        except Exception:
            pass
    raise AssertionError("no capability frame found in exhibit pcap")


def _pdu_with_custom_native_capability(template_pdu: bytes, capability: dict) -> bytes:
    """Take a real captured NGAP PDU and swap its IE 117 content for a custom
    capability dict, re-encoding the whole PDU - so the result is a genuinely
    valid NGAP PDU a real handset could have sent, carrying whatever
    capability shape the test needs, rather than a hand-built PDU skeleton
    that might not match real structure in some other respect."""
    with ngap_decode._lock:
        pdu_val = ngap_decode.decode_ngap_pdu(template_pdu)
        assert pdu_val is not None
        choice_name, body = pdu_val
        ies = body["value"][1]["protocolIEs"]
        ie_117 = next(ie for ie in ies if ie.get("id") == ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
        ie_117["value"] = ("UERadioCapability", ngap_decode._build_ue_radio_capability_bytes(capability))
        ngap_decode._ngap_pdu.set_val(pdu_val)
        return ngap_decode._ngap_pdu.to_aper()


def _summarize_pipeline_output(rewritten: bytes) -> dict:
    pdu_val = ngap_decode.decode_ngap_pdu(rewritten)
    assert pdu_val is not None
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    assert decoded is not None
    return ngap_decode.summarize_capability(decoded["capability"])


def test_sw_min_label3_through_full_pipeline_stays_siso() -> None:
    """profile='sw-min' (baseline already SISO by omission - no featureSets
    key at all) + label=3: through the *full* pipeline (real PDU decode,
    Stage 1 substitution, Stage 2 modifier, whole-PDU re-encode), not just
    apply_mimo_reduced() called directly - confirms the no-op holds end to
    end, not just at the dict level."""
    template = _first_capability_pdu()
    rewritten = ngap_decode.apply_capability_pipeline(template, profile="sw-min", label=3)
    assert rewritten is not None
    summary = _summarize_pipeline_output(rewritten)
    assert summary["mimo_dl_layers"] is None
    assert summary["mimo_ul_layers"] is None
    assert summary["ca_supported"] is False
    assert summary["vonr_supported"] is False
    print("test_sw_min_label3_through_full_pipeline_stays_siso: PASSED")


def _feature_sets_ul_only_capability() -> dict:
    """A real-shaped capability with featureSets present but only
    featureSetsUplinkPerCC populated - no featureSetsDownlinkPerCC key at
    all. No PROFILE_CAPABILITIES entry or committed real capture has this
    exact shape."""
    cap = dict(ngap_decode.PROFILE_CAPABILITIES["sw-ext"])
    cap["featureSets"] = {
        "featureSetsUplinkPerCC": [
            {
                "supportedSubcarrierSpacingUL": "kHz30",
                "supportedBandwidthUL": ("fr1", "mhz100"),
                "mimo-CB-PUSCH": {"maxNumberMIMO-LayersCB-PUSCH": "twoLayers", "maxNumberSRS-ResourcePerSet": 1},
                "supportedModulationOrderUL": "qam256",
            }
        ]
    }
    return cap


def _feature_sets_dl_only_capability() -> dict:
    """The mirror image: featureSets present but only featureSetsDownlinkPerCC
    populated - no featureSetsUplinkPerCC key at all."""
    cap = dict(ngap_decode.PROFILE_CAPABILITIES["sw-ext"])
    cap["featureSets"] = {
        "featureSetsDownlinkPerCC": [
            {
                "supportedSubcarrierSpacingDL": "kHz30",
                "supportedBandwidthDL": ("fr1", "mhz100"),
                "maxNumberMIMO-LayersPDSCH": "fourLayers",
                "supportedModulationOrderDL": "qam256",
            }
        ]
    }
    return cap


def test_dl_absent_ul_present_label3_through_full_pipeline() -> None:
    """Real-handset mode (profile=None): the native capability has UL MIMO
    features but no DL feature set at all - confirms apply_mimo_reduced's
    `if fs_dl:` branch correctly no-ops (DL stays absent, not a crash on a
    missing key) while `if fs_ul:` still forces UL to oneLayer, through the
    full real-PDU pipeline."""
    template = _first_capability_pdu()
    custom_capability = _feature_sets_ul_only_capability()
    input_pdu = _pdu_with_custom_native_capability(template, custom_capability)

    # sanity: confirm the constructed input really has the intended shape
    input_summary = _summarize_pipeline_output(input_pdu)
    assert input_summary["mimo_dl_layers"] is None, "constructed fixture must have no DL feature set"
    assert input_summary["mimo_ul_layers"] == ["twoLayers"]

    rewritten = ngap_decode.apply_capability_pipeline(input_pdu, profile=None, label=3)
    assert rewritten is not None
    result = _summarize_pipeline_output(rewritten)
    assert result["mimo_dl_layers"] is None, "DL was already absent - must stay absent, not error"
    assert result["mimo_ul_layers"] == ["oneLayer"], "UL must still be forced down to oneLayer"
    print("test_dl_absent_ul_present_label3_through_full_pipeline: PASSED")


def test_ul_absent_dl_present_label3_through_full_pipeline() -> None:
    """The mirror case: native capability has DL MIMO features but no UL
    feature set at all - confirms `if fs_ul:` correctly no-ops on the
    missing key while DL is still stripped down to absent (1-layer)."""
    template = _first_capability_pdu()
    custom_capability = _feature_sets_dl_only_capability()
    input_pdu = _pdu_with_custom_native_capability(template, custom_capability)

    input_summary = _summarize_pipeline_output(input_pdu)
    assert input_summary["mimo_dl_layers"] == ["fourLayers"]
    assert input_summary["mimo_ul_layers"] is None, "constructed fixture must have no UL feature set"

    rewritten = ngap_decode.apply_capability_pipeline(input_pdu, profile=None, label=3)
    assert rewritten is not None
    result = _summarize_pipeline_output(rewritten)
    assert result["mimo_dl_layers"] is None, "DL must be stripped down to absent (1-layer)"
    assert result["mimo_ul_layers"] is None, "UL was already absent - must stay absent, not error"
    print("test_ul_absent_dl_present_label3_through_full_pipeline: PASSED")


def main() -> int:
    test_sw_min_label3_through_full_pipeline_stays_siso()
    test_dl_absent_ul_present_label3_through_full_pipeline()
    test_ul_absent_dl_present_label3_through_full_pipeline()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
