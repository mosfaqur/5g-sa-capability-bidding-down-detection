#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.apply_vonr_denied() / _clear_ims_parameters()
(label 4) edge cases not covered by test_ngap_decode_stage2.py's
test_apply_vonr_denied, which only exercises the sw-ext profile (ims-Parameters
exactly one hop down, a single occurrence).

Real capture inspection (data/raw/rrc/*.json) confirms the 1-hop-down shape
matches real devices when VoNR is supported (both real VoNR=True captures on
file have ims-Parameters at exactly depth 1, sibling interRAT-Parameters -
same shape build_profile_capability() constructs), and that a VoNR=False real
device's nonCriticalExtension chain is still present and 2 levels deep with
entirely different sibling keys (sdap-Parameters, inactiveState) - confirming
the recursive, field-name-driven design (not hardcoded to a specific depth)
is the right approach, not an accident.

Covers three angles never tested anywhere in this project:

1. apply_vonr_denied on a capability with no nonCriticalExtension key at all
   (sw-min: VoNR already off) - confirmed nowhere else, only
   apply_mimo_reduced's already-SISO no-op was tested for sw-min before.
2. ims-Parameters occurring at *multiple* depths in the same chain -
   _clear_ims_parameters recurses through the whole chain regardless of what
   it finds at each level (no early return), so it should strip every
   occurrence, not just the first. Not realistic 3GPP signaling, but
   confirms the function's actual behavior rather than assuming it.
3. A found inconsistency (documented, not fixed - no real capture comes
   anywhere near this depth): summarize_capability()'s own VoNR-detection
   walk caps at depth<10, but _clear_ims_parameters() has no depth cap at
   all. Constructs a chain with ims-Parameters at depth 11 and shows
   summarize_capability() misses it (reports vonr_supported=False, capped
   before reaching it) while _clear_ims_parameters() still finds and strips
   it if called - the two functions can disagree past depth 10.

Run under proxy/venv (needs pycrate; no pyshark needed).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngap_decode  # noqa: E402


def test_apply_vonr_denied_on_already_off_baseline() -> None:
    """sw-min: VoNR already off, no nonCriticalExtension key at all - must be
    a true no-op, not a crash on a missing key."""
    baseline = ngap_decode.PROFILE_CAPABILITIES["sw-min"]
    assert "nonCriticalExtension" not in baseline
    result = ngap_decode.apply_vonr_denied(baseline)
    assert result == baseline
    print("test_apply_vonr_denied_on_already_off_baseline: PASSED")


def test_clear_ims_parameters_strips_every_occurrence_at_multiple_depths() -> None:
    """Not realistic 3GPP signaling, but confirms the recursive walk's actual
    behavior: no early return means every level is processed regardless of
    what was found at a shallower level."""
    chain = {
        "siblingA": {},
        "ims-Parameters": {"depth": 0},
        "nonCriticalExtension": {
            "siblingB": {},
            "nonCriticalExtension": {
                "ims-Parameters": {"depth": 2},
                "siblingC": {},
            },
        },
    }
    cleared = ngap_decode._clear_ims_parameters(chain)
    assert "ims-Parameters" not in cleared, "depth-0 occurrence must be stripped"
    assert "ims-Parameters" not in cleared["nonCriticalExtension"]["nonCriticalExtension"], (
        "depth-2 occurrence must also be stripped, not just the first one found"
    )
    # siblings at every level must survive untouched
    assert cleared["siblingA"] == {}
    assert cleared["nonCriticalExtension"]["siblingB"] == {}
    assert cleared["nonCriticalExtension"]["nonCriticalExtension"]["siblingC"] == {}
    print("test_clear_ims_parameters_strips_every_occurrence_at_multiple_depths: PASSED")


def _chain_with_ims_parameters_at_depth(target_depth: int) -> dict:
    chain = {"ims-Parameters": {}}
    for _ in range(target_depth):
        chain = {"nonCriticalExtension": chain}
    return chain


def test_summarize_capability_and_clear_ims_parameters_disagree_past_depth_10() -> None:
    """Documented inconsistency, not a live bug (no real capture on file goes
    anywhere near this depth - the deepest real chain found is 2 levels):
    summarize_capability()'s VoNR walk stops at depth<10, so ims-Parameters
    at depth 11 is invisible to it (reports vonr_supported=False). But
    _clear_ims_parameters() has no depth cap and would still find and strip
    that same ims-Parameters if apply_vonr_denied() were called on this
    capability - the two functions can disagree about whether VoNR support
    is present, past depth 10."""
    deep_ext = _chain_with_ims_parameters_at_depth(11)
    capability = {"accessStratumRelease": "rel15", "nonCriticalExtension": deep_ext}

    summary = ngap_decode.summarize_capability(capability)
    assert summary["vonr_supported"] is False, "depth-11 ims-Parameters must be invisible to the capped VoNR walk"

    result = ngap_decode.apply_vonr_denied(capability)
    # confirm the deep ims-Parameters was actually found and removed despite
    # summarize_capability() never having seen it
    ext = result["nonCriticalExtension"]
    depth = 0
    while isinstance(ext, dict):
        assert "ims-Parameters" not in ext, f"ims-Parameters still present at depth {depth} after apply_vonr_denied"
        ext = ext.get("nonCriticalExtension")
        depth += 1
    print("test_summarize_capability_and_clear_ims_parameters_disagree_past_depth_10: PASSED")


def main() -> int:
    test_apply_vonr_denied_on_already_off_baseline()
    test_clear_ims_parameters_strips_every_occurrence_at_multiple_depths()
    test_summarize_capability_and_clear_ims_parameters_disagree_past_depth_10()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
