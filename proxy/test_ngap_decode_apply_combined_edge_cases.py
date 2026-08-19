#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_combined() (label 5) edge
cases not covered by test_ngap_decode_stage2.py's test_apply_combined, which
only exercises the function directly on the synthetic sw-ext profile dict.

Covers three angles never tested anywhere in this project:

1. Through the *full* apply_capability_pipeline(), on a REAL captured
   device's native capability (Samsung A56, from
   data/raw/rrc/spike_verify_label1.pcap's pre-rewrite frame), not the
   synthetic sw-ext profile dict. Confirms all three degradations
   (CA/MIMO/VoNR) land together on real N2 wire bytes, while the untouched
   fields (accessStratumRelease, band list) stay exactly the real device's
   own native values - label 5 doesn't touch category or bands.
2. Idempotency: apply_combined(apply_combined(x)) must equal
   apply_combined(x) - none of the three composed modifiers should behave
   differently on an already-degraded input than on a fresh one. Never
   checked for any Stage 2 modifier in this project before now.
3. Applied to an already-minimal baseline (sw-min: CA already off, already
   SISO, VoNR already off) - confirms the composition doesn't crash or
   produce something unexpected when there's nothing left to degrade in any
   of the three dimensions simultaneously (each modifier's own
   already-minimal case is tested individually elsewhere, but never all
   three at once via apply_combined specifically).

Run under proxy/venv (needs pyshark+pycrate). Read-only against the
committed pcap.
"""
import sys
from pathlib import Path

import pyshark

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
from extract_features import _raw_hex  # noqa: E402

REAL_A56_PCAP = Path(__file__).resolve().parent.parent / "data/raw/rrc/spike_verify_label1.pcap"

REAL_A56_BAND_IDS = [1, 3, 5, 7, 8, 28, 38, 40, 41, 66, 77, 78]


def _real_a56_native_pdu() -> bytes:
    """The pre-rewrite (gNB->proxy) frame - the real Samsung A56's own
    capability, before any Stage 2 modifier is applied."""
    cap = pyshark.FileCapture(
        str(REAL_A56_PCAP),
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
    raise AssertionError("no capability frame found")


def _summarize_pipeline_output(rewritten: bytes) -> dict:
    pdu_val = ngap_decode.decode_ngap_pdu(rewritten)
    assert pdu_val is not None
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    assert decoded is not None
    return ngap_decode.summarize_capability(decoded["capability"])


def test_apply_combined_through_full_pipeline_on_real_device() -> None:
    template = _real_a56_native_pdu()
    native_summary = _summarize_pipeline_output(template)
    assert native_summary["ca_supported"] is True, "precondition: real A56 native capability has CA on"
    assert native_summary["vonr_supported"] is True, "precondition: real A56 native capability has VoNR on"

    rewritten = ngap_decode.apply_capability_pipeline(template, profile=None, label=5)
    assert rewritten is not None
    result = _summarize_pipeline_output(rewritten)

    assert result["ca_supported"] is False
    assert result["mimo_dl_layers"] is None
    # UL's ASN.1 enum has an explicit 'oneLayer' codepoint (unlike DL, which
    # has none and models 1-layer via field absence) - apply_mimo_reduced
    # forces the field to 'oneLayer' explicitly, so it stays *present* with
    # that value, not absent. summarize_capability correctly reports
    # ['oneLayer'], not None, here - confirmed against the real A56 native
    # capability's own UL feature set, which already carried an explicit
    # mimo-CB-PUSCH field before this modifier even ran.
    assert result["mimo_ul_layers"] == ["oneLayer"]
    assert result["vonr_supported"] is False
    # label 5 doesn't touch category or the standalone band list
    assert result["access_stratum_release"] == "rel15"
    assert result["band_ids"] == REAL_A56_BAND_IDS
    assert result["band_count"] == len(REAL_A56_BAND_IDS)
    print("test_apply_combined_through_full_pipeline_on_real_device: PASSED")


def test_apply_combined_is_idempotent() -> None:
    baseline = ngap_decode.PROFILE_CAPABILITIES["sw-ext"]
    once = ngap_decode.apply_combined(baseline)
    twice = ngap_decode.apply_combined(once)
    assert once == twice, "apply_combined must be idempotent - re-applying to an already-degraded capability must not change it further"
    print("test_apply_combined_is_idempotent: PASSED")


def test_apply_combined_on_already_minimal_baseline() -> None:
    """sw-min: CA already off, already SISO (no featureSets at all), VoNR
    already off - apply_combined must not crash and must leave it exactly
    as minimal as it already was."""
    baseline = ngap_decode.PROFILE_CAPABILITIES["sw-min"]
    result = ngap_decode.apply_combined(baseline)
    assert result == baseline, "applying combined to an already-fully-minimal capability must be a true no-op"

    with ngap_decode._lock:
        ngap_decode._l4.set_val(result)
        raw = ngap_decode._l4.to_uper()
        ngap_decode._l4.from_uper(raw)
        decoded = ngap_decode._l4.get_val()
    summary = ngap_decode.summarize_capability(decoded)
    assert summary["ca_supported"] is False
    assert summary["mimo_dl_layers"] is None
    assert summary["mimo_ul_layers"] is None
    assert summary["vonr_supported"] is False
    print("test_apply_combined_on_already_minimal_baseline: PASSED")


def main() -> int:
    test_apply_combined_through_full_pipeline_on_real_device()
    test_apply_combined_is_idempotent()
    test_apply_combined_on_already_minimal_baseline()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
