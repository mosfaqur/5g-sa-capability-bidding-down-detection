#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_cat_downgrade() (label 1) edge
cases not covered by test_ngap_decode_stage2.py's test_apply_cat_downgrade
(sw-ext baseline, starting from rel15 only) or test_ngap_decode_pipeline.py's
real-handset test (profile=None, also starting from rel15 - the only value
any real capture or synthetic profile on file ever uses).

apply_cat_downgrade() is the simplest of the 6 Stage 2 modifiers - an
unconditional overwrite of accessStratumRelease to 'spare1', regardless of
whatever was there before. That simplicity means most of the "edge cases"
below are really just confirming the unconditional-overwrite behavior holds
for inputs no real capture has ever actually presented:

1. Idempotency - applying it twice must equal applying it once (matches the
   pattern already checked for apply_combined()).
2. Starting from every other valid AccessStratumRelease codepoint
   (rel16/rel17/rel18/spare2/spare3/spare4 - the ASN.1 enum has 8 values
   total, only rel15 has ever been observed in any real capture or synthetic
   profile) - confirms the overwrite converges to spare1 regardless of
   starting point, not just from the one value ever seen in practice.
3. A capability with no accessStratumRelease key at all (3GPP mandates it as
   a mandatory field, so no real capture is missing it, but the function
   itself has no presence check) - confirms it's still added correctly
   rather than silently doing nothing.
4. Through the full pipeline, combined with a Stage 1 profile substitution
   never paired with label 1 before: profile='sw-min' (CA/MIMO/VoNR all
   already at minimum) + label 1 - confirms the category downgrade lands
   correctly while SW-Min's own minimal baseline for the other three
   dimensions is preserved, not the "native real device" baseline every
   other label-1 pipeline test used (Samsung A56).

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

# 3GPP TS 38.331 AccessStratumRelease enum, confirmed against the generated
# pycrate schema (see the Build 0b fix note in ngap_decode.py) - 8 codepoints
# total, only rel15 ever observed in any real capture or synthetic profile.
OTHER_VALID_RELEASES = ["rel16", "rel17", "rel18", "spare2", "spare3", "spare4"]


def _uper_round_trip(cap: dict) -> dict:
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
        ngap_decode._l4.from_uper(raw)
        return ngap_decode._l4.get_val()


def test_apply_cat_downgrade_is_idempotent() -> None:
    baseline = ngap_decode.PROFILE_CAPABILITIES["sw-ext"]
    once = ngap_decode.apply_cat_downgrade(baseline)
    twice = ngap_decode.apply_cat_downgrade(once)
    assert once == twice
    print("test_apply_cat_downgrade_is_idempotent: PASSED")


def test_apply_cat_downgrade_converges_from_every_other_valid_release() -> None:
    baseline = ngap_decode.PROFILE_CAPABILITIES["sw-ext"]
    for release in OTHER_VALID_RELEASES:
        starting = dict(baseline)
        starting["accessStratumRelease"] = release
        result = ngap_decode.apply_cat_downgrade(starting)
        assert result["accessStratumRelease"] == "spare1", f"starting from {release!r}"
        decoded = _uper_round_trip(result)
        assert decoded["accessStratumRelease"] == "spare1", f"starting from {release!r} (post round-trip)"
    print("test_apply_cat_downgrade_converges_from_every_other_valid_release: PASSED")


def test_apply_cat_downgrade_adds_missing_access_stratum_release() -> None:
    """No real capture is missing this mandatory field, but the function has
    no presence check - confirm it still sets the key rather than silently
    no-op'ing when it isn't there to begin with."""
    capability = {"rf-Parameters": {"supportedBandListNR": [{"bandNR": 78}]}}
    assert "accessStratumRelease" not in capability
    result = ngap_decode.apply_cat_downgrade(capability)
    assert result["accessStratumRelease"] == "spare1"
    print("test_apply_cat_downgrade_adds_missing_access_stratum_release: PASSED")


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


def _summarize_pipeline_output(rewritten: bytes) -> dict:
    pdu_val = ngap_decode.decode_ngap_pdu(rewritten)
    assert pdu_val is not None
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    assert decoded is not None
    return ngap_decode.summarize_capability(decoded["capability"])


def test_sw_min_label1_through_full_pipeline() -> None:
    """profile='sw-min' + label=1: category downgrades while SW-Min's own
    minimal baseline (CA off, SISO, VoNR off) is otherwise preserved - not
    tested with any profile before now (only real-handset mode was tested
    for label 1 previously)."""
    template = _first_capability_pdu()
    rewritten = ngap_decode.apply_capability_pipeline(template, profile="sw-min", label=1)
    assert rewritten is not None
    result = _summarize_pipeline_output(rewritten)
    assert result["access_stratum_release"] == "spare1"
    assert result["ca_supported"] is False
    assert result["mimo_dl_layers"] is None
    assert result["mimo_ul_layers"] is None
    assert result["vonr_supported"] is False
    assert result["band_ids"] == [78]
    print("test_sw_min_label1_through_full_pipeline: PASSED")


def main() -> int:
    test_apply_cat_downgrade_is_idempotent()
    test_apply_cat_downgrade_converges_from_every_other_valid_release()
    test_apply_cat_downgrade_adds_missing_access_stratum_release()
    test_sw_min_label1_through_full_pipeline()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
