#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.build_profile_capability()'s CA
(carrier aggregation) combo-count edge cases.

Prompted by test_ngap_decode_summarize_real.py's finding (2026-07-31) that
real handset captures report 2-3 CA band combinations, while every one of
this project's synthetic profiles (SW-Std, SW-Ext, SW-Min) produces at most
1. That's not a bug relative to the docstring - build_profile_capability()'s
own docstring already says "ca_bands: list of band numbers used to build
*one* CA band combination", an honest architectural ceiling, not a stale
claim. This file:

1. Locks in that ceiling explicitly (no combination of arguments can ever
   produce more than 1 entry in supportedBandCombinationList) - a deliberate
   regression test, so if this is ever extended to support multiple
   combinations, this test needs updating rather than silently passing
   either way.
2. Tests edge-case inputs no current PROFILE_CAPABILITIES entry exercises,
   to see whether the function silently produces something semantically odd
   (but still checks whether it's at least still encodable, not a crash):
   a single-band "combination" - a follow-up review (2026-07-31, see
   test_real_ca_combo_structure_more_complex_than_synthetic in
   test_ngap_decode_summarize_real.py) found every real capture on file
   actually reports one of these routinely, alongside its 2-band combo(s), so
   this is NOT the "not real aggregation" footgun this comment originally
   called it - single-band entries represent a real, legitimate alternate
   bandwidth-class option, not a mistake. What build_profile_capability()
   still cannot represent is a *profile with more than one combo at once*
   (mixing a 1-band and a 2-band combo, as every real capture does) - and a
   CA band not present in the profile's own standalone supportedBandListNR
   (an "orphan" CA band, inconsistent with real 3GPP capability structure,
   where CA bands must be a subset of standalone-supported bands).
3. Confirms every existing real PROFILE_CAPABILITIES entry (SW-Std, SW-Ext)
   keeps its CA bands as a subset of its own standalone bands (the invariant
   the function itself does not enforce).

Run under proxy/venv (needs pycrate).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngap_decode  # noqa: E402


def _combo_count(cap: dict) -> int:
    return len(cap.get("rf-Parameters", {}).get("supportedBandCombinationList", []))


def _uper_round_trip(cap: dict) -> dict:
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
        ngap_decode._l4.from_uper(raw)
        return ngap_decode._l4.get_val()


def test_no_input_ever_produces_more_than_one_combination() -> None:
    """The architectural ceiling: regardless of how many bands are packed
    into ca_bands, or how they're structured, there is exactly one dict
    literal appended to supportedBandCombinationList in the function body -
    confirm this holds even for unusually large ca_bands lists."""
    for ca_bands in (None, [], [78], [78, 78], [1, 3, 28, 78], list(range(1, 21))):
        cap = ngap_decode.build_profile_capability([78], ca_bands=ca_bands, mimo_dl=None, mimo_ul=None, vonr=False)
        expected = 0 if not ca_bands else 1
        assert _combo_count(cap) == expected, f"ca_bands={ca_bands!r} produced {_combo_count(cap)} combos, expected {expected}"
    print("test_no_input_ever_produces_more_than_one_combination: PASSED")


def test_single_band_ca_combo_is_encodable_and_matches_a_real_pattern() -> None:
    """No current profile does this (SW-Std/SW-Ext both use 2+ bands in
    ca_bands), but nothing in build_profile_capability() stops a future
    caller from passing a single-element ca_bands list - confirm it encodes/
    decodes cleanly. Originally framed as "not real aggregation, a caller-
    level footgun" - corrected 2026-07-31 after checking every real capture
    on file: single-band "combinations" (a different bandwidth-class option
    for one carrier, not multi-CC aggregation) are routine in real handset
    capability signaling (see test_real_ca_combo_structure_more_complex_than_synthetic
    in test_ngap_decode_summarize_real.py), so this is a legitimate real
    pattern the function happens to support, not just a harmless oddity."""
    cap = ngap_decode.build_profile_capability([78], ca_bands=[78], mimo_dl=None, mimo_ul=None, vonr=False)
    assert _combo_count(cap) == 1
    decoded = _uper_round_trip(cap)
    combo = decoded["rf-Parameters"]["supportedBandCombinationList"][0]
    assert len(combo["bandList"]) == 1, "a single-band ca_bands list produces a 1-component 'combination'"
    summary = ngap_decode.summarize_capability(decoded)
    assert summary["ca_supported"] is True, "ca_supported is driven purely by combo-list presence"
    print("test_single_band_ca_combo_is_encodable_and_matches_a_real_pattern: PASSED")


def test_orphan_ca_band_not_in_standalone_list_is_encodable() -> None:
    """Real 3GPP capability requires every CA-combination band to also appear
    in the standalone supportedBandListNR - build_profile_capability() does
    not enforce this. Confirm it still encodes/decodes without error even
    when violated (semantically inconsistent with the 3GPP structure, but
    not a codec-level bug); flagged so a future profile addition doesn't
    introduce this by accident and only find out from a confusing Wireshark
    decode later."""
    cap = ngap_decode.build_profile_capability([78], ca_bands=[1, 3], mimo_dl=None, mimo_ul=None, vonr=False)
    standalone_bands = {b["bandNR"] for b in cap["rf-Parameters"]["supportedBandListNR"]}
    combo_bands = {b[1]["bandNR"] for b in cap["rf-Parameters"]["supportedBandCombinationList"][0]["bandList"]}
    assert not combo_bands.issubset(standalone_bands), (
        "this test's whole point is to construct the orphan-band scenario - if this assertion "
        "fails, the fixture itself needs revisiting, not the function"
    )
    decoded = _uper_round_trip(cap)  # must not raise
    assert decoded is not None
    print("test_orphan_ca_band_not_in_standalone_list_is_encodable: PASSED")


def test_real_profiles_keep_ca_bands_within_standalone_bands() -> None:
    """The invariant build_profile_capability() itself doesn't enforce, but
    every real PROFILE_CAPABILITIES entry must still respect it - confirms
    SW-Std and SW-Ext (SW-Min has no CA at all) haven't drifted into the
    orphan-band footgun the previous test exercises synthetically."""
    for profile in ("sw-std", "sw-ext"):
        cap = ngap_decode.PROFILE_CAPABILITIES[profile]
        rf = cap["rf-Parameters"]
        standalone_bands = {b["bandNR"] for b in rf["supportedBandListNR"]}
        combo_bands = {b[1]["bandNR"] for b in rf["supportedBandCombinationList"][0]["bandList"]}
        assert combo_bands.issubset(standalone_bands), (
            f"{profile}: CA combination references band(s) {combo_bands - standalone_bands} "
            f"not in its own standalone band list {standalone_bands}"
        )
    print("test_real_profiles_keep_ca_bands_within_standalone_bands: PASSED")


def main() -> int:
    test_no_input_ever_produces_more_than_one_combination()
    test_single_band_ca_combo_is_encodable_and_matches_a_real_pattern()
    test_orphan_ca_band_not_in_standalone_list_is_encodable()
    test_real_profiles_keep_ca_bands_within_standalone_bands()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
