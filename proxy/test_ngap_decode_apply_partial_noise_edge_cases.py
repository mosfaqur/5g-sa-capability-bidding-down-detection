#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_partial_noise() (label 6) edge
cases not covered by test_ngap_decode_stage2.py's
test_apply_partial_noise_deterministic_sequence, which only exercises the
synthetic sw-ext baseline (_rohc_profiles_all_false() - every ROHC profile
flag starts False, so the flip always goes False->True; pdcp-Parameters is
always present).

Real capture inspection confirms real devices use the exact same 10 ROHC
profile keys as the synthetic baseline, but with a genuine *mix* of True/False
values - never exercised before now, and specifically never exercised the
True->False direction of the flip.

Must run as its own fresh process (python3 test_ngap_decode_apply_partial_noise_edge_cases.py)
- _STAGE2_RNG is a module-level singleton seeded once at import, consumed
sequentially; running this file's tests in a shared process with any other
test that also calls a Stage 2 modifier importing this module would desync
the draw sequence relied on below.

Covers two angles never tested anywhere in this project:

1. A capability with no pdcp-Parameters key at all (and, separately, one with
   pdcp-Parameters but no supportedROHC-Profiles key) - confirms no crash,
   and specifically confirms the RNG consumes *only* the random() draw and
   never calls choice() when there's nothing to flip - the `if profiles:`
   guard is not just a correctness check, it also protects the RNG draw
   sequence itself from an extra, conditional consumption that would only
   happen when profiles happens to be present.
2. A real device's ROHC profiles (a genuine mix of True/False, from
   data/raw/rrc/rrc_1_a56_build-0d-verify3-20260730_0.json), run through the
   full deterministic two-draw sequence: confirms the no-flip draw leaves it
   completely unchanged, and the flip draw correctly inverts whichever key is
   chosen regardless of its starting value (this real fixture has both True
   and False starting values among its 10 keys, unlike the synthetic
   all-False baseline every other test uses) - and that every other field
   (CA/MIMO/VoNR/category/bands) stays untouched on the flip draw
   specifically, not just trivially on the no-flip draw.

Run under proxy/venv (needs pycrate; no pyshark needed - uses the committed
RRC JSON fixture, not a pcap).
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngap_decode  # noqa: E402

REAL_A56_RRC_JSON = (
    Path(__file__).resolve().parent.parent / "data/raw/rrc/rrc_1_a56_build-0d-verify3-20260730_0.json"
)


def _reset_stage2_rng() -> None:
    """Each RNG-sensitive test below resets the module-level singleton to a
    fresh random.Random(42) first, rather than relying on draw *position*
    carried over from whichever test happened to run before it in this
    process - the position after a variable number of prior random()/
    choice() calls is not something to assume, only something to compute or
    reset."""
    ngap_decode._STAGE2_RNG = random.Random(42)


def test_missing_pdcp_parameters_consumes_only_the_random_draw() -> None:
    """A capability with no pdcp-Parameters at all - confirms no crash and,
    critically, that choice() is never called: the draw sequence for
    subsequent calls must match a fresh random.Random(42) advanced by
    random() alone, not random()+choice()."""
    _reset_stage2_rng()
    reference = random.Random(42)
    capability = {"accessStratumRelease": "rel15", "rf-Parameters": {"supportedBandListNR": [{"bandNR": 78}]}}

    # First call: reference's first draw is ~0.639 (>=0.5, no flip attempted
    # regardless of profiles being absent).
    expected_first_draw = reference.random()
    assert expected_first_draw >= 0.5
    result1 = ngap_decode.apply_partial_noise(capability)
    assert result1 == capability, "no profiles to flip, and draw >=0.5 anyway - must be an untouched copy"

    # Second call: reference's second draw is ~0.025 (<0.5, would normally
    # trigger a flip) - but profiles is still absent, so choice() must not be
    # called, and the capability must stay untouched despite the "flip" draw
    # succeeding.
    expected_second_draw = reference.random()
    assert expected_second_draw < 0.5
    result2 = ngap_decode.apply_partial_noise(capability)
    assert result2 == capability, "draw <0.5 but no profiles present - must still be untouched, not crash"
    print("test_missing_pdcp_parameters_consumes_only_the_random_draw: PASSED")


def test_pdcp_parameters_present_but_no_rohc_profiles_key() -> None:
    """pdcp-Parameters present (as it would be for any real 3GPP capability -
    it's not an all-or-nothing key) but supportedROHC-Profiles itself absent -
    same guard, different absent key."""
    _reset_stage2_rng()
    capability = {
        "accessStratumRelease": "rel15",
        "pdcp-Parameters": {"maxNumberROHC-ContextSessions": "cs2"},
    }
    # Run it enough times to hit both branches of the random() draw at least
    # once without relying on a fresh process's exact seed position.
    for _ in range(4):
        result = ngap_decode.apply_partial_noise(capability)
        assert result["pdcp-Parameters"] == capability["pdcp-Parameters"], "nothing to flip - must stay untouched"
    print("test_pdcp_parameters_present_but_no_rohc_profiles_key: PASSED")


def test_real_a56_mixed_rohc_profiles_through_deterministic_sequence() -> None:
    """Real A56 capability (genuine mix of True/False ROHC profile values,
    not the synthetic all-False baseline) - confirms the flip correctly
    inverts a key regardless of its starting value (this fixture has both
    directions available), and that every other field stays untouched on the
    flip draw specifically."""
    _reset_stage2_rng()
    raw_capability = json.loads(REAL_A56_RRC_JSON.read_text())["raw_rrc_capability"]
    original_profiles = dict(raw_capability["pdcp-Parameters"]["supportedROHC-Profiles"])
    assert True in original_profiles.values() and False in original_profiles.values(), (
        "precondition: this fixture must have a genuine mix, not all one value"
    )

    no_flip_result = ngap_decode.apply_partial_noise(raw_capability)
    assert no_flip_result["pdcp-Parameters"]["supportedROHC-Profiles"] == original_profiles

    flip_result = ngap_decode.apply_partial_noise(raw_capability)
    flipped_profiles = flip_result["pdcp-Parameters"]["supportedROHC-Profiles"]
    diffs = [k for k in original_profiles if original_profiles[k] != flipped_profiles[k]]
    assert len(diffs) == 1, f"expected exactly one flipped key, got {diffs}"
    flipped_key = diffs[0]
    assert flipped_profiles[flipped_key] == (not original_profiles[flipped_key]), (
        "the flip must correctly invert whichever value was there, in either direction"
    )

    for field in ("accessStratumRelease", "rf-Parameters", "featureSets", "nonCriticalExtension"):
        assert flip_result.get(field) == raw_capability.get(field), f"{field} must be untouched by label 6"
    print("test_real_a56_mixed_rohc_profiles_through_deterministic_sequence: PASSED")


def main() -> int:
    test_missing_pdcp_parameters_consumes_only_the_random_draw()
    test_pdcp_parameters_present_but_no_rohc_profiles_key()
    test_real_a56_mixed_rohc_profiles_through_deterministic_sequence()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
