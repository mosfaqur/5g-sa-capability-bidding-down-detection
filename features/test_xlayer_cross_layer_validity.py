#!/usr/bin/env python3
"""Standalone smoke test for extract_features.xlayer() against the
cross-layer consistency model (the project's testbed architecture notes §8.5), plus the
2026-07-31 fix this file's original finding led to.

§8.5 states the core Chapter 5 result depends on: "the cross-view SHAP points
at container_hash_match / num_fields_mismatched / the divergent field, showing
it detects the manipulation." Checking xlayer() against that goal with real
committed rrc_capture.py output found this expectation only held when the
RRC-side record is byte_exact=True (rrc_capture.py's "case (b)",
cached-capability reattach) - it broke for byte_exact=False ("case (a)",
fresh capability transfer, the common case per the project's internal build log's Build 0d notes:
"Only case (a) fires on a first-ever attach"). A real committed RRC capture
(byte_exact=False) paired with a hand-constructed PERFECT semantic match
(num_fields_mismatched=0 - zero real attack signal) originally showed
container_hash_match=False and a capability_size_delta in the tens of
thousands - indistinguishable from what an actual attack would produce,
because the RRC side's container_bytes is a JSON-text fallback
(rrc_capture.py's no-raw-PER-bytes case) while the N2 side is always real PER
bytes - two different byte representations of potentially the same content,
not a manipulation signal.

Fixed in xlayer() itself: it now checks rrc_record.get("byte_exact", True)
and returns capability_size_delta=None, container_hash_match=None instead of
a numerically-plausible-looking but meaningless value when False - a caller
that doesn't check for None before feeding these into training/SHAP gets a
loud, immediate error instead of silently learning noise. Defaults to True
(byte comparison valid) when the key is absent, matching every N2-side record
_capability_record_from_bytes() produces (always real PER bytes, never sets
this key), so the byte_exact=True path below is unaffected by this fix.

ie_field_count_delta is unaffected by any of this - it's computed from the
*decoded dict structure* (len(capability)), not raw bytes, so it stays
meaningful regardless of byte_exact (confirmed below) and was never part of
the original finding's scope.

2026-07-31 second real finding (cached-reattach case-b live validation
session): a genuine byte_exact=True case-(b) reattach cannot, on its own,
detect an attack applied at the ORIGINAL registration that populated the
AMF's cached capability - because that reattach's RRC "echo" is sourced from
the same (possibly already-attacked) N2 bytes the proxy's try_rewrite only
ever touches on the gnb->amf leg; the amf->gnb leg carrying the cached
capability back to the gNB during a reattach is only decode/reencode'd, never
re-attacked. So comparing a case-(b) reattach's own RRC record against its
OWN originating registration's N2 record always matches, attack or not - not
a bug in xlayer(), a real blind spot in what a single reattach event can see.
Fixed at the collection layer, not in xlayer() itself: rrc_capture.py's
update_reference()/write_record(reference_dir=...) persists the last known-
good case-a (byte_exact=False) capability per IMSI, so a LATER event's
N2-side capability - fresh or cached-reattach - can be checked against a
genuinely independent reference instead of only the same-event echo.
test_cached_reattach_alone_misses_attack_but_persisted_reference_catches_it
below proves both halves with real captured data (a real Realme/imsi-...0004
label-1 attack): the same-event comparison shows a false clean match, and the
persisted-reference comparison correctly flags ue_category diverging.

Run under proxy/venv (needs pycrate; no pyshark needed - uses committed RRC
JSON fixtures, not pcaps). Read-only.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "proxy"))
import ngap_decode  # noqa: E402
from rrc_capture import capability_record_from_rrc_json  # noqa: E402
from extract_features import _capability_record_from_bytes, xlayer  # noqa: E402

REAL_RRC_CAPTURE = (
    Path(__file__).resolve().parent.parent / "data/raw/rrc/rrc_0_a56_build-0d-verify2-20260730_0.json"
)

# 2026-07-31 cached-reattach live validation session (real Realme RMX3363,
# imsi-001010000000004, ngap_proxy.py --stage rewrite --label 1, no --profile
# i.e. real-handset mode - see the project's internal build log's "Cached-reattach (case b) live
# validation" section for the full narrative):
#   - REAL_CASEB_ATTACKED_RRC: the case-(b) reattach's own RRC echo
#     (byte_exact=True), sourced from the AMF's cached (already label-1
#     attacked) capability - ran_ue=7, NAS Service Request.
#   - REAL_N2_ATTACKED_HEX: the post-rewrite (port 38413) N2 capability
#     container from ran_ue=6, the ORIGINAL registration that populated that
#     same AMF cache - the same attacked bytes REAL_CASEB_ATTACKED_RRC echoes.
#   - REAL_CLEAN_CASEA_REFERENCE: a genuinely independent, untampered case-(a)
#     reference for the SAME imsi/device, captured much earlier in the same
#     session under label 0 (no attack) - ran_ue=22.
REAL_CASEB_ATTACKED_RRC = (
    Path(__file__).resolve().parent.parent / "data/raw/rrc/rrc_1_realme-ue4_build-caseb-label1-20260731_7.json"
)
REAL_CLEAN_CASEA_REFERENCE = (
    Path(__file__).resolve().parent.parent / "data/raw/rrc/rrc_0_realme-ue4_build-caseb-20260731_22.json"
)
REAL_N2_ATTACKED_HEX = (
    "0419808832de9aed380574d5a13160003c6a00002c1262c003387a1a004d9061cf9863ca160704c0a00c47032a0d89bac1184341"
    "020e90a8002cb64c550d0e7c471e819f604f8c73e618f28581c0e1e138002f800e000be0012100000d940001400001506c4cd608"
    "c21a08107485400165b262a86873e238f40cfb027c639f30c7942c0e070f09c0017c0070005f00090800006ca0000a00000a83e2"
    "0eb04610d04083c42a00092d931541238f21cf8c73e618f28581c0e1e04fec000003fb00000048200000c1741b0a303582308682"
    "041d215000596c98aa1a1cf88e3d033ec09f18e7cc31e50b0381c3c270005f001c0017c0024200001b280002800000a0d84fac118"
    "4341020e90a8002cb64c550d0e7c471e819f604f8c73e618f28581c0e1e138002f800e000be00141b097582308682041d21500059"
    "6c98aa1a1cf88e3d033ec09f18e7cc31e50b0381c3c2700058001c0016000283e0deb04610d04083c42a00092d931541238f21cf8"
    "c73e618f28581c0e1e04fe8000003fa000000507c13d608c21a08107885400125b262a82471e439f18e7cc31e50b0381c3c09fc00"
    "00007f0000000a0f80fac1184341020f10a80024b64c55048e3c873e31cf9863ca16070387813f8000000fe000000141f01b5823"
    "08682041e215000496c98aa091c790e7c639f30c7942c0e070f027ff000001ffc00000283e026b04610d04083c42a00092d93154"
    "1238f21cf8c73e618f28581c0e1e04fe0000003f8000000507c02d608c21a08107885400125b262a82471e439f18e7cc31e50b03"
    "81c3c09ff0000007fc000000a0f801ac1184341020f10a80024b64c55048e3c873e31cf9863ca16070387813fb800000fee00000"
    "00841c4d00000000202695a000001a01810b639f0c0a0233d0bc0001f00140e0a00e0601280380030120020301f01c01000000008"
    "000010040000100200000c01000008008000050040000300200001c07e54d6065652d64cd606d60ad650d60a5014100000965240"
    "4000065949010000296524040000e594901000049652404000165949005d2a8aa07154a62a93455058aa51146c0001700720300804"
    "06030080c000000040080112a12000102030406070b10111213191b2526272841410280"
)


def test_byte_exact_true_case_discriminates_correctly() -> None:
    """The scenario §8.5 assumes: both sides are real PER bytes. A clean match
    gives container_hash_match=True, capability_size_delta=0; an attack
    (label 4, VoNR denied, applied to the N2 side only) flips
    container_hash_match to False - exactly the discriminative signal the
    spec expects SHAP to find."""
    cap = ngap_decode.PROFILE_CAPABILITIES["sw-std"]
    clean_bytes = ngap_decode._build_ue_radio_capability_bytes(cap)
    clean_record = _capability_record_from_bytes(clean_bytes)

    clean_result = xlayer(clean_record, dict(clean_record))
    assert clean_result["num_fields_mismatched"] == 0
    assert clean_result["container_hash_match"] is True
    assert clean_result["capability_size_delta"] == 0

    attacked_cap = ngap_decode.apply_vonr_denied(cap)
    attacked_bytes = ngap_decode._build_ue_radio_capability_bytes(attacked_cap)
    attacked_record = _capability_record_from_bytes(attacked_bytes)
    attacked_result = xlayer(clean_record, attacked_record)
    assert attacked_result["num_fields_mismatched"] == 1
    assert attacked_result["container_hash_match"] is False, (
        "byte_exact=True case: container_hash_match must correctly flag the attack"
    )
    print("test_byte_exact_true_case_discriminates_correctly: PASSED")


def test_byte_exact_false_case_returns_none_instead_of_misleading_values() -> None:
    """The common real-world scenario (rrc_capture.py's case (a), fires on
    every first-ever attach): a real committed RRC capture (byte_exact=False)
    paired with a hypothetical PERFECT semantic match on the N2 side (every
    one of the 7 tracked semantic fields agrees - zero attack signal) must now
    get None for both fields, not a numerically-plausible-looking but
    meaningless value - the pre-fix behavior (container_hash_match=False,
    capability_size_delta in the tens of thousands) was indistinguishable
    from what an actual attack would produce, purely because the two sides
    use incompatible byte representations (JSON text vs. real PER bytes), not
    because anything was manipulated."""
    rrc_record = capability_record_from_rrc_json(json.loads(REAL_RRC_CAPTURE.read_text())["raw_rrc_capability"])
    assert rrc_record["byte_exact"] is False, "this fixture must be a case-(a) capture for this test to be meaningful"

    n2_record = dict(rrc_record)
    n2_record["container_bytes"] = b"\x01\x02\x03\x04"  # some real PER bytes, unrelated length/content
    n2_record["capability_size_bytes"] = len(n2_record["container_bytes"])

    result = xlayer(rrc_record, n2_record)
    assert result["num_fields_mismatched"] == 0, "constructed as a perfect semantic match - zero real attack signal"
    assert result["container_hash_match"] is None, (
        "byte_exact=False: container_hash_match must be None, not a misleading True/False"
    )
    assert result["capability_size_delta"] is None, (
        "byte_exact=False: capability_size_delta must be None, not a misleading numeric value"
    )
    print("test_byte_exact_false_case_returns_none_instead_of_misleading_values: PASSED")


def test_ie_field_count_delta_stays_meaningful_regardless_of_byte_exact() -> None:
    """Unlike capability_size_delta/container_hash_match, ie_field_count_delta
    is computed from the decoded dict structure (len(capability)), not raw
    bytes - confirms it stays 0 for a clean match even when byte_exact=False,
    i.e. it is NOT part of this finding's scope and remains a trustworthy
    cross-layer feature regardless."""
    rrc_record = capability_record_from_rrc_json(json.loads(REAL_RRC_CAPTURE.read_text())["raw_rrc_capability"])
    n2_record = dict(rrc_record)
    n2_record["container_bytes"] = b"\x01\x02\x03\x04"
    n2_record["capability_size_bytes"] = len(n2_record["container_bytes"])

    result = xlayer(rrc_record, n2_record)
    assert result["ie_field_count_delta"] == 0
    print("test_ie_field_count_delta_stays_meaningful_regardless_of_byte_exact: PASSED")


def test_cached_reattach_alone_misses_attack_but_persisted_reference_catches_it() -> None:
    """Real data, 2026-07-31 cached-reattach live validation session (real
    Realme RMX3363, imsi-...0004, label-1 Cat-downgrade attack, no --profile -
    real-handset mode). Two real xlayer() calls on the SAME attacked reattach:

    1. The reattach's own RRC echo (byte_exact=True) vs. the N2 record from its
       OWN originating registration (both are the identical attacked bytes,
       since try_rewrite only fires gnb->amf - the amf->gnb leg carrying the
       cached capability back during a reattach is only decode/reencode'd) -
       this MUST show a clean match, proving the same-event comparison is
       blind to an attack that was already applied at the original
       registration, not a fluke of this one capture.
    2. The SAME N2 record vs. a genuinely independent case-(a) reference for
       the same IMSI captured much earlier in the same session (before this
       label-1 attack was even active) - this MUST correctly show
       ue_category diverging, proving rrc_capture.py's persisted-reference
       fix (update_reference()/write_record(reference_dir=...)) closes the
       blind spot the same-event comparison has."""
    caseb_rrc = json.loads(REAL_CASEB_ATTACKED_RRC.read_text())
    assert caseb_rrc["record"]["byte_exact"] is True, "must be a real case-(b) capture"
    assert caseb_rrc["label"] == 1
    caseb_rrc_record = dict(caseb_rrc["record"])
    caseb_rrc_record["container_bytes"] = bytes.fromhex(caseb_rrc_record["container_bytes"])

    n2_attacked_record = _capability_record_from_bytes(bytes.fromhex(REAL_N2_ATTACKED_HEX))
    assert n2_attacked_record["ue_category"] == 1, "label-1 Cat-downgrade must have landed (spare1 -> ue_category 1)"

    same_event_result = xlayer(caseb_rrc_record, n2_attacked_record)
    assert same_event_result["num_fields_mismatched"] == 0, (
        "same-event comparison must show a FALSE clean match - both sides are the "
        "same already-attacked cached bytes, so this proves the blind spot is real"
    )
    assert same_event_result["container_hash_match"] is True
    assert same_event_result["ue_category_delta"] == 0

    clean_reference = json.loads(REAL_CLEAN_CASEA_REFERENCE.read_text())
    assert clean_reference["label"] == 0
    assert clean_reference["record"]["byte_exact"] is False, "the persisted reference must be a genuine case-(a) capture"
    assert clean_reference["record"]["ue_category"] == 15, "untampered baseline, captured before the label-1 attack was active"
    reference_record = dict(clean_reference["record"])
    reference_record["container_bytes"] = bytes.fromhex(reference_record["container_bytes"])

    persisted_reference_result = xlayer(reference_record, n2_attacked_record)
    assert persisted_reference_result["ue_category_delta"] == -14, (
        "persisted-reference comparison must correctly detect the attack the "
        "same-event comparison missed"
    )
    assert persisted_reference_result["num_fields_mismatched"] == 1
    # The reference is byte_exact=False, so per the first fix in this file,
    # these two must be None, not a misleading value - not re-testing that
    # fix here, just confirming it still holds for this real pair.
    assert persisted_reference_result["container_hash_match"] is None
    assert persisted_reference_result["capability_size_delta"] is None

    print("test_cached_reattach_alone_misses_attack_but_persisted_reference_catches_it: PASSED")


def main() -> int:
    test_byte_exact_true_case_discriminates_correctly()
    test_byte_exact_false_case_returns_none_instead_of_misleading_values()
    test_ie_field_count_delta_stays_meaningful_regardless_of_byte_exact()
    test_cached_reattach_alone_misses_attack_but_persisted_reference_catches_it()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
