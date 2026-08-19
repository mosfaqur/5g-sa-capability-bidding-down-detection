#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.py's Stage 2 attack modifiers
(labels 1-6, the project's testbed architecture notes §6.3).

Covers each of the 6 modifier functions individually, apply_combined's
composition, the label-6 seeded-RNG determinism, STAGE2_MODIFIERS' mapping,
and - the invariant most worth locking in - that every modifier returns a
fresh copy rather than mutating its input in place. That matters because
PROFILE_CAPABILITIES's three dicts are module-level singletons reused across
every registration for that profile (ngap_proxy.py calls
apply_capability_pipeline() once per UERadioCapabilityInfoIndication); an
in-place mutation bug in any modifier would corrupt the shared baseline for
every subsequent registration of that profile, not just the one being
attacked - a class of bug that would be very hard to notice live (the first
attacked registration would look right, later ones silently wrong) and is
exactly the kind of thing worth a permanent regression test for.

Run under proxy/venv (needs pycrate_asn1dir), same as ngap_decode.py itself.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngap_decode  # noqa: E402


def _fresh_baseline() -> dict:
    """A full baseline with CA, DL+UL MIMO, and VoNR all present - the SW-Ext
    profile template exercises every substructure the modifiers touch."""
    return copy.deepcopy(ngap_decode.PROFILE_CAPABILITIES["sw-ext"])


def _uper_round_trip(cap: dict) -> dict:
    """Confirms cap is actually encodable (not just a plausible-looking dict) -
    catches the exact class of bug the Build 0b fix found (rel8 not being a
    valid AccessStratumRelease codepoint)."""
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
        ngap_decode._l4.from_uper(raw)
        return ngap_decode._l4.get_val()


def test_apply_cat_downgrade() -> None:
    baseline = _fresh_baseline()
    result = ngap_decode.apply_cat_downgrade(baseline)
    assert result["accessStratumRelease"] == "spare1"
    decoded = _uper_round_trip(result)
    assert decoded["accessStratumRelease"] == "spare1", "spare1 must be a real encodable ASN.1 codepoint"
    # everything else untouched
    assert result["rf-Parameters"] == baseline["rf-Parameters"]
    assert result.get("featureSets") == baseline.get("featureSets")
    assert result.get("nonCriticalExtension") == baseline.get("nonCriticalExtension")
    print("test_apply_cat_downgrade: PASSED")


def test_apply_ca_disabled() -> None:
    baseline = _fresh_baseline()
    assert "supportedBandCombinationList" in baseline["rf-Parameters"]  # precondition
    result = ngap_decode.apply_ca_disabled(baseline)
    assert "supportedBandCombinationList" not in result["rf-Parameters"]
    assert "supportedBandListNR" in result["rf-Parameters"], "standalone band list must be untouched"
    assert result["accessStratumRelease"] == baseline["accessStratumRelease"]
    assert result.get("featureSets") == baseline.get("featureSets")
    assert result.get("nonCriticalExtension") == baseline.get("nonCriticalExtension")
    _uper_round_trip(result)
    print("test_apply_ca_disabled: PASSED")


def test_apply_mimo_reduced() -> None:
    baseline = _fresh_baseline()
    result = ngap_decode.apply_mimo_reduced(baseline)
    for fs in result["featureSets"]["featureSetsDownlinkPerCC"]:
        assert "maxNumberMIMO-LayersPDSCH" not in fs, "DL MIMO must be removed (absent = 1 layer)"
    for fs in result["featureSets"]["featureSetsUplinkPerCC"]:
        assert fs["mimo-CB-PUSCH"]["maxNumberMIMO-LayersCB-PUSCH"] == "oneLayer"
    # CA and VoNR must be untouched
    assert result["rf-Parameters"] == baseline["rf-Parameters"]
    assert result.get("nonCriticalExtension") == baseline.get("nonCriticalExtension")
    _uper_round_trip(result)
    print("test_apply_mimo_reduced: PASSED")


def test_apply_mimo_reduced_already_siso_is_noop() -> None:
    """sw-min has no featureSets at all (already SISO by omission) - must be
    returned unchanged, not raise on a missing key."""
    siso = ngap_decode.PROFILE_CAPABILITIES["sw-min"]
    assert "featureSets" not in siso
    result = ngap_decode.apply_mimo_reduced(siso)
    assert "featureSets" not in result
    assert result == siso
    print("test_apply_mimo_reduced_already_siso_is_noop: PASSED")


def test_apply_vonr_denied() -> None:
    baseline = _fresh_baseline()
    ext = baseline["nonCriticalExtension"]
    assert "ims-Parameters" in ext.get("nonCriticalExtension", {}), "precondition: ims-Parameters present one hop down"
    result = ngap_decode.apply_vonr_denied(baseline)
    result_ext = result["nonCriticalExtension"]
    assert "ims-Parameters" not in result_ext
    assert "ims-Parameters" not in result_ext.get("nonCriticalExtension", {})
    assert "interRAT-Parameters" in result_ext, "sibling field at the same level must survive"
    assert result["rf-Parameters"] == baseline["rf-Parameters"]
    assert result.get("featureSets") == baseline.get("featureSets")
    _uper_round_trip(result)
    print("test_apply_vonr_denied: PASSED")


def test_apply_combined() -> None:
    """Label 5: all three of CA-disabled + MIMO-reduced + VoNR-denied together."""
    baseline = _fresh_baseline()
    result = ngap_decode.apply_combined(baseline)
    assert "supportedBandCombinationList" not in result["rf-Parameters"]
    for fs in result["featureSets"]["featureSetsDownlinkPerCC"]:
        assert "maxNumberMIMO-LayersPDSCH" not in fs
    for fs in result["featureSets"]["featureSetsUplinkPerCC"]:
        assert fs["mimo-CB-PUSCH"]["maxNumberMIMO-LayersCB-PUSCH"] == "oneLayer"
    assert "ims-Parameters" not in result["nonCriticalExtension"].get("nonCriticalExtension", {})
    assert result["accessStratumRelease"] == baseline["accessStratumRelease"], "label 5 doesn't touch category"
    _uper_round_trip(result)
    print("test_apply_combined: PASSED")


def test_apply_partial_noise_deterministic_sequence() -> None:
    """_STAGE2_RNG is module-level, seeded random_state=42, consumed
    sequentially across the whole process - the first draw (~0.639) is >=0.5
    (no flip), the second (~0.025) is <0.5 (flip), matching the project's internal build log's
    documented label-6 sequence exactly. Only valid when this test runs as
    its own fresh process (true for python3 test_ngap_decode_stage2.py) -
    _STAGE2_RNG is a singleton, so running this after other code in the same
    process already drew from it would desync the sequence."""
    baseline = _fresh_baseline()
    baseline_profiles = dict(baseline["pdcp-Parameters"]["supportedROHC-Profiles"])

    first = ngap_decode.apply_partial_noise(baseline)
    assert first["pdcp-Parameters"]["supportedROHC-Profiles"] == baseline_profiles, (
        "first draw (~0.639) should land on the no-flip branch"
    )

    second = ngap_decode.apply_partial_noise(baseline)
    second_profiles = second["pdcp-Parameters"]["supportedROHC-Profiles"]
    diffs = [k for k in baseline_profiles if baseline_profiles[k] != second_profiles[k]]
    assert len(diffs) == 1, f"second draw (~0.025) should flip exactly one profile bit, flipped: {diffs}"

    # everything outside pdcp-Parameters.supportedROHC-Profiles must be untouched by either call
    for result in (first, second):
        assert result["rf-Parameters"] == baseline["rf-Parameters"]
        assert result.get("featureSets") == baseline.get("featureSets")
        assert result.get("nonCriticalExtension") == baseline.get("nonCriticalExtension")

    _uper_round_trip(second)
    print("test_apply_partial_noise_deterministic_sequence: PASSED")


def test_stage2_modifiers_mapping() -> None:
    assert set(ngap_decode.STAGE2_MODIFIERS.keys()) == {1, 2, 3, 4, 5, 6}
    assert 0 not in ngap_decode.STAGE2_MODIFIERS, "label 0 (Normal) is pass-through, not a modifier function"
    assert ngap_decode.STAGE2_MODIFIERS[1] is ngap_decode.apply_cat_downgrade
    assert ngap_decode.STAGE2_MODIFIERS[2] is ngap_decode.apply_ca_disabled
    assert ngap_decode.STAGE2_MODIFIERS[3] is ngap_decode.apply_mimo_reduced
    assert ngap_decode.STAGE2_MODIFIERS[4] is ngap_decode.apply_vonr_denied
    assert ngap_decode.STAGE2_MODIFIERS[5] is ngap_decode.apply_combined
    assert ngap_decode.STAGE2_MODIFIERS[6] is ngap_decode.apply_partial_noise
    print("test_stage2_modifiers_mapping: PASSED")


def test_modifiers_do_not_mutate_shared_profile_singleton() -> None:
    """The critical invariant: PROFILE_CAPABILITIES's dicts are module-level
    singletons reused across every registration for that profile - a modifier
    that mutated its input in place would silently corrupt the baseline for
    every later registration, not just the attacked one. Snapshot each real
    PROFILE_CAPABILITIES entry, run every modifier against it, and confirm
    the live singleton is byte-for-byte unchanged afterward."""
    for profile_name, cap in ngap_decode.PROFILE_CAPABILITIES.items():
        snapshot = copy.deepcopy(cap)
        for label, modifier in ngap_decode.STAGE2_MODIFIERS.items():
            modifier(cap)
            assert cap == snapshot, (
                f"modifier for label {label} mutated PROFILE_CAPABILITIES[{profile_name!r}] in place"
            )
    print("test_modifiers_do_not_mutate_shared_profile_singleton: PASSED")


def main() -> int:
    test_apply_cat_downgrade()
    test_apply_ca_disabled()
    test_apply_mimo_reduced()
    test_apply_mimo_reduced_already_siso_is_noop()
    test_apply_vonr_denied()
    test_apply_combined()
    test_apply_partial_noise_deterministic_sequence()
    test_stage2_modifiers_mapping()
    test_modifiers_do_not_mutate_shared_profile_singleton()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
