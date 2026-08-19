#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_ca_disabled() (label 2) edge
cases not covered by test_ngap_decode_stage2.py's test_apply_ca_disabled,
which only checks that the base supportedBandCombinationList key is removed
from the synthetic sw-ext profile - which never sets the two 3GPP-release
extension variants apply_ca_disabled() also clears:
supportedBandCombinationList-v1540 and -v1560.

Real capture inspection (both the RRC-side JSON dump and, more importantly,
a real N2 PER wire decode via decode_ue_radio_capability_container - not
just the RRC path) confirms every real device on file populates all three
keys simultaneously, with identical lengths (the -v1540/-v1560 variants
appear to redeclare the same combinations under later 3GPP release
extensions, not carry additional ones on top). apply_ca_disabled()'s own
3-key clear had never been tested against this real shape before.

Cross-validated against a *second*, genuinely different real device
(spike_verify_label0.pcap - the Nokia-CPE-like device from the project's internal build log's Build
0d notes, distinct from the Samsung A56 in spike_verify_label1.pcap) at a
direct request, so the "every real device populates all three keys" claim
doesn't rest on a single data point: this second device also carries all
three keys simultaneously (3 combinations each, vs. the A56's 2), confirming
the pattern isn't specific to one handset vendor/model.

Also surfaces a genuine asymmetry worth documenting (not a live bug given
what's been observed - every real capture on file always populates the base
list whenever CA is supported): summarize_capability()/
_capability_record_from_bytes()'s ca_supported/ca_band_count detection reads
*only* the base supportedBandCombinationList key, never the -v1540/-v1560
variants. apply_ca_disabled() itself is more thorough (clears all three). If
a real device ever reported CA support *only* via one of the extension
variants with an empty/absent base list, the feature extraction would
report ca_supported=False even on an unattacked capability - a blind spot in
detection, not in the attack itself (which would still correctly strip
whatever combination lists exist).

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

RRC_DIR = Path(__file__).resolve().parent.parent / "data/raw/rrc"
REAL_A56_PCAP = RRC_DIR / "spike_verify_label1.pcap"
REAL_NOKIA_CPE_PCAP = RRC_DIR / "spike_verify_label0.pcap"

CA_COMBO_KEYS = (
    "supportedBandCombinationList",
    "supportedBandCombinationList-v1540",
    "supportedBandCombinationList-v1560",
)


def _real_native_pdu(pcap_path: Path) -> bytes:
    cap = pyshark.FileCapture(
        str(pcap_path),
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
    raise AssertionError(f"no capability frame found in {pcap_path}")


def _real_a56_native_pdu() -> bytes:
    return _real_native_pdu(REAL_A56_PCAP)


def _decode_native_capability(pdu: bytes) -> dict:
    pdu_val = ngap_decode.decode_ngap_pdu(pdu)
    assert pdu_val is not None
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    assert decoded is not None
    return decoded["capability"]


def _summarize_pipeline_output(rewritten: bytes) -> dict:
    return ngap_decode.summarize_capability(_decode_native_capability(rewritten))


def test_real_a56_native_capability_has_all_three_ca_keys() -> None:
    """Precondition check, not itself the point of the test: confirms this
    real device's N2 wire capability (not just its RRC-side JSON dump)
    genuinely populates all three CA-related keys, so the test below isn't
    accidentally exercising an empty/no-op case."""
    native = _decode_native_capability(_real_a56_native_pdu())
    rf = native["rf-Parameters"]
    for key in CA_COMBO_KEYS:
        assert key in rf, f"expected real A56 native capability to have {key!r}"
        assert len(rf[key]) > 0
    print("test_real_a56_native_capability_has_all_three_ca_keys: PASSED")


def test_apply_ca_disabled_clears_all_three_keys_on_real_device_through_full_pipeline() -> None:
    template = _real_a56_native_pdu()
    native_summary = _summarize_pipeline_output(template)
    assert native_summary["ca_supported"] is True, "precondition: real A56 native capability has CA on"

    rewritten = ngap_decode.apply_capability_pipeline(template, profile=None, label=2)
    assert rewritten is not None

    rf = _decode_native_capability(rewritten)["rf-Parameters"]
    for key in CA_COMBO_KEYS:
        assert key not in rf, f"{key!r} should have been cleared by label 2, but is still present"

    result_summary = ngap_decode.summarize_capability(_decode_native_capability(rewritten))
    assert result_summary["ca_supported"] is False
    assert result_summary["access_stratum_release"] == native_summary["access_stratum_release"]
    assert result_summary["vonr_supported"] == native_summary["vonr_supported"]
    print("test_apply_ca_disabled_clears_all_three_keys_on_real_device_through_full_pipeline: PASSED")


def test_second_real_device_also_has_all_three_ca_keys() -> None:
    """Nokia-CPE-like device (spike_verify_label0.pcap) - a genuinely
    different real device from the Samsung A56 above, cross-validated at a
    direct request so the "every real device populates all three keys"
    finding isn't resting on a single data point."""
    native = _decode_native_capability(_real_native_pdu(REAL_NOKIA_CPE_PCAP))
    rf = native["rf-Parameters"]
    for key in CA_COMBO_KEYS:
        assert key in rf, f"expected real Nokia-CPE-like native capability to have {key!r}"
        assert len(rf[key]) > 0
    print("test_second_real_device_also_has_all_three_ca_keys: PASSED")


def test_apply_ca_disabled_clears_all_three_keys_on_second_real_device_through_full_pipeline() -> None:
    template = _real_native_pdu(REAL_NOKIA_CPE_PCAP)
    native_summary = _summarize_pipeline_output(template)
    assert native_summary["ca_supported"] is True, "precondition: real Nokia-CPE-like native capability has CA on"

    rewritten = ngap_decode.apply_capability_pipeline(template, profile=None, label=2)
    assert rewritten is not None

    rf = _decode_native_capability(rewritten)["rf-Parameters"]
    for key in CA_COMBO_KEYS:
        assert key not in rf, f"{key!r} should have been cleared by label 2, but is still present"

    result_summary = ngap_decode.summarize_capability(_decode_native_capability(rewritten))
    assert result_summary["ca_supported"] is False
    assert result_summary["access_stratum_release"] == native_summary["access_stratum_release"]
    assert result_summary["vonr_supported"] == native_summary["vonr_supported"]
    print("test_apply_ca_disabled_clears_all_three_keys_on_second_real_device_through_full_pipeline: PASSED")


def test_ca_support_carried_only_in_extension_variant_is_invisible_to_summarize_capability() -> None:
    """Documented asymmetry, not a live bug given what's been observed (every
    real capture on file always populates the base list too): construct a
    capability with CA support declared *only* via the v1540 extension
    variant, no base supportedBandCombinationList key at all -
    summarize_capability() misses it entirely (reports ca_supported=False),
    but apply_ca_disabled() still correctly strips the v1540 list if
    present, whatever the detection blind spot."""
    combo = [{"bandList": [("nr", {"bandNR": 78})], "featureSetCombination": 0}]
    capability = {
        "accessStratumRelease": "rel15",
        "rf-Parameters": {
            "supportedBandListNR": [{"bandNR": 78}],
            "supportedBandCombinationList-v1540": combo,
        },
    }
    summary = ngap_decode.summarize_capability(capability)
    assert summary["ca_supported"] is False, (
        "this is the documented blind spot: real CA support exists (in the v1540 variant) "
        "but summarize_capability() only reads the base key, so it reports False"
    )

    result = ngap_decode.apply_ca_disabled(capability)
    assert "supportedBandCombinationList-v1540" not in result["rf-Parameters"], (
        "apply_ca_disabled() must still strip the v1540 list even though summarize_capability() "
        "never reported it as CA-supporting in the first place"
    )
    print("test_ca_support_carried_only_in_extension_variant_is_invisible_to_summarize_capability: PASSED")


def main() -> int:
    test_real_a56_native_capability_has_all_three_ca_keys()
    test_apply_ca_disabled_clears_all_three_keys_on_real_device_through_full_pipeline()
    test_second_real_device_also_has_all_three_ca_keys()
    test_apply_ca_disabled_clears_all_three_keys_on_second_real_device_through_full_pipeline()
    test_ca_support_carried_only_in_extension_variant_is_invisible_to_summarize_capability()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
