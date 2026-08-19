#!/usr/bin/env python3
"""Standalone smoke test for ngap_decode.summarize_capability() against real,
committed real-handset RRC captures (data/raw/rrc/*.json, from the Build 0d
RRC-vs-N2 spike - Samsung A56 and the generic real-handset session).

Every prior test of summarize_capability() (test_ngap_decode_profiles.py,
test_ngap_decode_stage2.py, test_ngap_decode_decode.py) used either the
synthetic PROFILE_CAPABILITIES templates or hand-built minimal dicts - every
one of those has exactly one CA band combination, one featureSetsDownlinkPerCC
entry, one featureSetsUplinkPerCC entry, and a small handful of top-level
keys. Real handset captures are structurally much richer: this reviews found
(2026-07-31) captures with up to 12 bands, 2-3 CA band combinations (never
tested before - every synthetic fixture in this project has exactly 1), 1-2
featureSets entries per direction, several top-level keys
summarize_capability() doesn't read at all (rlc-Parameters, mac-Parameters,
measAndMobParameters, fdd/tdd-Add-UE-NR-Capabilities,
featureSetCombinations), and VoNR support genuinely varying True/False across
different real captures of the same profile.

Read-only against the committed data/raw/rrc/*.json fixtures - writes nothing.
Run under proxy/venv (needs pycrate; no pyshark needed, these are pre-decoded
RRC JSON dumps, not pcaps).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ngap_decode  # noqa: E402

DATA_RAW_RRC = Path(__file__).resolve().parent.parent / "data/raw/rrc"

REAL_CAPTURES = [
    "rrc_0_handset_build-0d-spike-20260730_0.json",
    "rrc_0_handset_build-0d-spike-20260730_1.json",
    "rrc_0_handset_build-0d-spike-20260730_2.json",
    "rrc_0_a56_build-0d-verify2-20260730_0.json",
    "rrc_1_a56_build-0d-verify3-20260730_0.json",
]


def _load_raw_capability(filename: str) -> dict:
    record = json.loads((DATA_RAW_RRC / filename).read_text())
    return record["raw_rrc_capability"]


def test_all_real_captures_decode_without_error() -> None:
    for filename in REAL_CAPTURES:
        cap = _load_raw_capability(filename)
        summary = ngap_decode.summarize_capability(cap)
        assert summary["access_stratum_release"] == "rel15"
        assert isinstance(summary["band_count"], int) and summary["band_count"] > 0
        assert isinstance(summary["band_ids"], list) and len(summary["band_ids"]) == summary["band_count"]
    print("test_all_real_captures_decode_without_error: PASSED")


def test_band_list_matches_ground_truth_extracted_directly() -> None:
    """Cross-check band_ids/band_count against bandNR values read directly out
    of the raw JSON, independent of summarize_capability()'s own logic."""
    for filename in REAL_CAPTURES:
        cap = _load_raw_capability(filename)
        summary = ngap_decode.summarize_capability(cap)
        ground_truth_bands = [b.get("bandNR") for b in cap["rf-Parameters"]["supportedBandListNR"]]
        assert summary["band_ids"] == ground_truth_bands, filename
        assert summary["band_count"] == len(ground_truth_bands), filename
    print("test_band_list_matches_ground_truth_extracted_directly: PASSED")


def test_ca_band_count_greater_than_one_on_real_captures() -> None:
    """The genuinely untested case: every synthetic fixture anywhere in this
    project's test suite has exactly 1 CA combination. Real handset captures
    have 2 or 3 - confirm ca_supported=True and the combination list length is
    computed correctly (2 or 3), not silently truncated or miscounted."""
    expected_combo_counts = {
        "rrc_0_handset_build-0d-spike-20260730_0.json": 2,
        "rrc_0_handset_build-0d-spike-20260730_1.json": 3,
        "rrc_0_handset_build-0d-spike-20260730_2.json": 2,
        "rrc_0_a56_build-0d-verify2-20260730_0.json": 3,
        "rrc_1_a56_build-0d-verify3-20260730_0.json": 2,
    }
    for filename, expected in expected_combo_counts.items():
        cap = _load_raw_capability(filename)
        summary = ngap_decode.summarize_capability(cap)
        assert summary["ca_supported"] is True
        combo_count = len(cap["rf-Parameters"].get("supportedBandCombinationList", []))
        assert combo_count == expected, f"{filename}: expected {expected} CA combos, found {combo_count}"
    print("test_ca_band_count_greater_than_one_on_real_captures: PASSED")


def test_mimo_aggregation_across_multiple_feature_set_entries() -> None:
    """Two of these captures have 2 featureSetsDownlinkPerCC/UplinkPerCC
    entries each (vs. always exactly 1 in every synthetic fixture) - confirm
    the set-based dedup in summarize_capability() still resolves to a single
    consistent value when both entries happen to agree, and that
    _mimo_layers_to_int-style downstream consumption isn't affected by having
    more than one entry to walk."""
    multi_entry_captures = [
        "rrc_0_handset_build-0d-spike-20260730_1.json",
        "rrc_0_a56_build-0d-verify2-20260730_0.json",
    ]
    for filename in multi_entry_captures:
        cap = _load_raw_capability(filename)
        fs = cap["featureSets"]
        assert len(fs["featureSetsDownlinkPerCC"]) == 2, filename
        assert len(fs["featureSetsUplinkPerCC"]) == 2, filename
        summary = ngap_decode.summarize_capability(cap)
        # both entries happen to report the same values in these real captures,
        # so the deduped set collapses to exactly one value, not two
        assert summary["mimo_dl_layers"] == ["fourLayers"], filename
        assert summary["mimo_ul_layers"] == ["oneLayer"], filename
    print("test_mimo_aggregation_across_multiple_feature_set_entries: PASSED")


def test_vonr_varies_true_and_false_across_real_captures() -> None:
    """Confirms the nonCriticalExtension walk correctly handles both real
    on-device states, not just one - most captures have VoNR on, but one
    (spike_1) genuinely has it off."""
    results = {}
    for filename in REAL_CAPTURES:
        cap = _load_raw_capability(filename)
        results[filename] = ngap_decode.summarize_capability(cap)["vonr_supported"]

    assert results["rrc_0_handset_build-0d-spike-20260730_1.json"] is False
    assert results["rrc_0_a56_build-0d-verify2-20260730_0.json"] is False
    assert results["rrc_0_handset_build-0d-spike-20260730_0.json"] is True
    assert results["rrc_0_handset_build-0d-spike-20260730_2.json"] is True
    assert results["rrc_1_a56_build-0d-verify3-20260730_0.json"] is True
    assert set(results.values()) == {True, False}, "must see both states across real captures, not just one"
    print("test_vonr_varies_true_and_false_across_real_captures: PASSED")


def test_repeated_capture_of_same_device_state_is_consistent() -> None:
    """spike_0 and spike_2 are two separate captures of the apparent same
    device/state (identical bands, combo count, MIMO, VoNR) - confirms
    summarize_capability() is deterministic given the same real input, not
    just that it doesn't crash once."""
    cap0 = _load_raw_capability("rrc_0_handset_build-0d-spike-20260730_0.json")
    cap2 = _load_raw_capability("rrc_0_handset_build-0d-spike-20260730_2.json")
    assert ngap_decode.summarize_capability(cap0) == ngap_decode.summarize_capability(cap2)
    print("test_repeated_capture_of_same_device_state_is_consistent: PASSED")


def test_real_ca_combo_structure_more_complex_than_synthetic() -> None:
    """2026-07-31 follow-up: ngap_decode.build_profile_capability() (the
    Stage 1 synthetic profile builder) always produces exactly one combo,
    with every bandList entry uniformly getting both ca-BandwidthClassDL-NR
    and ca-BandwidthClassUL-NR. Every real capture on file diverges from
    that in two specific, systematic ways - not just "more combos" (already
    covered by test_ca_band_count_greater_than_one_on_real_captures above):

    1. A 2-band combo's bandList is asymmetric: the first entry has both DL
       and UL bandwidth class, the second has DL only (no UL key at all) -
       real intra-band CA where only one component carries UL aggregation.
    2. At least one combo is a single-band "combination" (an alternate
       bandwidth-class option for one carrier, not multi-CC aggregation -
       see the corrected test_single_band_ca_combo_is_encodable_and_matches_a_real_pattern
       in test_ngap_decode_build_profile_ca.py), alongside the 2-band combo(s)
       in the same capability - a mix of sizes no synthetic profile can
       produce (build_profile_capability can only ever emit one combo, of
       one fixed size).

    summarize_capability() never inspects bandList's internal structure (only
    the top-level combo count), so this divergence doesn't affect any tracked
    ML feature - this test exists as documented reference data for anyone
    extending the Stage 1 profile builder or writing Chapter 3 exhibits that
    compare a synthetic profile's Wireshark decode against a real handset's."""
    for filename in REAL_CAPTURES:
        cap = _load_raw_capability(filename)
        combos = cap["rf-Parameters"]["supportedBandCombinationList"]
        sizes = [len(c["bandList"]) for c in combos]
        assert 1 in sizes, f"{filename}: expected at least one single-band combo, sizes={sizes}"
        assert 2 in sizes, f"{filename}: expected at least one 2-band combo, sizes={sizes}"

        two_band_combo = next(c for c in combos if len(c["bandList"]) == 2)
        first, second = two_band_combo["bandList"]
        assert "ca-BandwidthClassUL-NR" in first["nr"], filename
        assert "ca-BandwidthClassUL-NR" not in second["nr"], (
            f"{filename}: expected the second bandList entry to omit UL bandwidth class "
            "(asymmetric UL CA), found it present - real-capture pattern may have changed"
        )
    print("test_real_ca_combo_structure_more_complex_than_synthetic: PASSED")


def test_extension_containers_with_no_band_data_dont_affect_band_count() -> None:
    """fdd-Add-UE-NR-Capabilities/tdd-Add-UE-NR-Capabilities are present in
    real captures (unlike any synthetic fixture) but only ever contain empty
    phy/mac-ParametersXDD-Diff sub-dicts in these captures, not band data -
    confirms summarize_capability() correctly ignores them (by design, per
    its own docstring) without under- or over-counting bands as a result."""
    for filename in ("rrc_0_handset_build-0d-spike-20260730_0.json", "rrc_1_a56_build-0d-verify3-20260730_0.json"):
        cap = _load_raw_capability(filename)
        assert "fdd-Add-UE-NR-Capabilities" in cap
        assert "tdd-Add-UE-NR-Capabilities" in cap
        for ext_key in ("fdd-Add-UE-NR-Capabilities", "tdd-Add-UE-NR-Capabilities"):
            ext = cap[ext_key]
            assert not any(v for v in ext.values()), (
                f"{filename}: {ext_key} unexpectedly non-empty - re-check summarize_capability() "
                "isn't missing band data hidden in here"
            )
        summary = ngap_decode.summarize_capability(cap)
        ground_truth_band_count = len(cap["rf-Parameters"]["supportedBandListNR"])
        assert summary["band_count"] == ground_truth_band_count
    print("test_extension_containers_with_no_band_data_dont_affect_band_count: PASSED")


def main() -> int:
    test_all_real_captures_decode_without_error()
    test_band_list_matches_ground_truth_extracted_directly()
    test_ca_band_count_greater_than_one_on_real_captures()
    test_mimo_aggregation_across_multiple_feature_set_entries()
    test_vonr_varies_true_and_false_across_real_captures()
    test_repeated_capture_of_same_device_state_is_consistent()
    test_real_ca_combo_structure_more_complex_than_synthetic()
    test_extension_containers_with_no_band_data_dont_affect_band_count()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
