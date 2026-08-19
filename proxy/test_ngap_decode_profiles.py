#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.py's PROFILE_CAPABILITIES (Stage 1
profile-baseline fingerprints, the project's testbed architecture notes §6.2).

Round-trips each profile's UE-NR-Capability dict through the real UPER
codec (_l4.set_val/to_uper, then from_uper/get_val + summarize_capability -
the same layer test_rrc_capture.py and test_extract_features.py each
spot-check one profile against) and confirms every documented fingerprint
property, for all three profiles, not just the one or two profiles those
other two files happen to touch as part of testing something else.

Never modifies PROFILE_CAPABILITIES or any other module state - set_val()
mutates the shared pycrate singleton, so every test round-trips through it
under the module's own lock and reads back get_val() immediately, the same
pattern already used (and already proven safe) elsewhere in this project.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngap_decode  # noqa: E402


def _round_trip_fingerprint(profile: str) -> dict:
    """Encode profile's capability dict to real UPER bytes, decode it back,
    and summarize - confirms the fingerprint survives actual wire encoding,
    not just that the source dict looks right."""
    cap = ngap_decode.PROFILE_CAPABILITIES[profile]
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
        ngap_decode._l4.from_uper(raw)
        decoded = ngap_decode._l4.get_val()
    summary = ngap_decode.summarize_capability(decoded)
    rf_params = decoded.get("rf-Parameters", {}) or {}
    ca_band_count = len(rf_params.get("supportedBandCombinationList", []) or [])
    return {
        "access_stratum_release": summary["access_stratum_release"],
        "ca_supported": summary["ca_supported"],
        "ca_band_count": ca_band_count,
        "mimo_dl_layers": summary["mimo_dl_layers"],
        "mimo_ul_layers": summary["mimo_ul_layers"],
        "vonr_supported": summary["vonr_supported"],
        "band_count": summary["band_count"],
        "band_ids": summary["band_ids"],
    }


def test_profile_capabilities_has_exactly_three_profiles() -> None:
    assert set(ngap_decode.PROFILE_CAPABILITIES.keys()) == {"sw-min", "sw-std", "sw-ext"}
    print("test_profile_capabilities_has_exactly_three_profiles: PASSED")


def test_sw_std_fingerprint() -> None:
    """Documented (ngap_decode.py comment + the project's internal build log): n78, CA enabled, 2x2 MIMO, VoNR on."""
    fp = _round_trip_fingerprint("sw-std")
    assert fp["access_stratum_release"] == "rel15"
    assert fp["band_ids"] == [78]
    assert fp["band_count"] == 1
    assert fp["ca_supported"] is True
    assert fp["ca_band_count"] == 1
    assert fp["mimo_dl_layers"] == ["twoLayers"]
    assert fp["mimo_ul_layers"] == ["oneLayer"]
    assert fp["vonr_supported"] is True
    print("test_sw_std_fingerprint: PASSED")


def test_sw_ext_fingerprint() -> None:
    """Documented: n1/n3/n28/n78, CA multi-band, 4x4 MIMO, VoNR on."""
    fp = _round_trip_fingerprint("sw-ext")
    assert fp["access_stratum_release"] == "rel15"
    assert fp["band_ids"] == [1, 3, 28, 78]
    assert fp["band_count"] == 4
    assert fp["ca_supported"] is True
    assert fp["ca_band_count"] == 1
    assert fp["mimo_dl_layers"] == ["fourLayers"]
    assert fp["mimo_ul_layers"] == ["twoLayers"]
    assert fp["vonr_supported"] is True
    print("test_sw_ext_fingerprint: PASSED")


def test_sw_min_fingerprint() -> None:
    """Documented: n78 only, no CA, 1x1 SISO, VoNR off."""
    fp = _round_trip_fingerprint("sw-min")
    assert fp["access_stratum_release"] == "rel15"
    assert fp["band_ids"] == [78]
    assert fp["band_count"] == 1
    assert fp["ca_supported"] is False
    assert fp["ca_band_count"] == 0
    assert fp["mimo_dl_layers"] is None  # absent field = 1 layer, per _mimo_layers_to_int's convention
    assert fp["mimo_ul_layers"] is None
    assert fp["vonr_supported"] is False
    print("test_sw_min_fingerprint: PASSED")


def test_profiles_are_pairwise_distinct() -> None:
    """The whole point of Stage 1 is that each profile has a distinct N2
    fingerprint - confirm no two profiles' summaries collide."""
    fps = {p: _round_trip_fingerprint(p) for p in ngap_decode.PROFILE_CAPABILITIES}
    seen = list(fps.values())
    for i in range(len(seen)):
        for j in range(i + 1, len(seen)):
            assert seen[i] != seen[j], f"profiles produced identical fingerprints: {list(fps.keys())}"
    print("test_profiles_are_pairwise_distinct: PASSED")


def test_build_profile_capability_omits_ca_when_none() -> None:
    cap = ngap_decode.build_profile_capability([78], ca_bands=None, mimo_dl=None, mimo_ul=None, vonr=False)
    assert "supportedBandCombinationList" not in cap["rf-Parameters"]
    cap_empty_list = ngap_decode.build_profile_capability([78], ca_bands=[], mimo_dl=None, mimo_ul=None, vonr=False)
    assert "supportedBandCombinationList" not in cap_empty_list["rf-Parameters"]
    print("test_build_profile_capability_omits_ca_when_none: PASSED")


def test_build_profile_capability_omits_feature_sets_when_no_mimo() -> None:
    cap = ngap_decode.build_profile_capability([78], ca_bands=None, mimo_dl=None, mimo_ul=None, vonr=False)
    assert "featureSets" not in cap
    cap_dl_only = ngap_decode.build_profile_capability([78], ca_bands=None, mimo_dl="twoLayers", mimo_ul=None, vonr=False)
    assert "featureSetsDownlinkPerCC" in cap_dl_only["featureSets"]
    assert "featureSetsUplinkPerCC" not in cap_dl_only["featureSets"]
    print("test_build_profile_capability_omits_feature_sets_when_no_mimo: PASSED")


def test_build_profile_capability_omits_vonr_when_false() -> None:
    cap_off = ngap_decode.build_profile_capability([78], ca_bands=None, mimo_dl=None, mimo_ul=None, vonr=False)
    assert "nonCriticalExtension" not in cap_off
    cap_on = ngap_decode.build_profile_capability([78], ca_bands=None, mimo_dl=None, mimo_ul=None, vonr=True)
    assert "ims-Parameters" in cap_on["nonCriticalExtension"]["nonCriticalExtension"]
    print("test_build_profile_capability_omits_vonr_when_false: PASSED")


def main() -> int:
    test_profile_capabilities_has_exactly_three_profiles()
    test_sw_std_fingerprint()
    test_sw_ext_fingerprint()
    test_sw_min_fingerprint()
    test_profiles_are_pairwise_distinct()
    test_build_profile_capability_omits_ca_when_none()
    test_build_profile_capability_omits_feature_sets_when_no_mimo()
    test_build_profile_capability_omits_vonr_when_false()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
