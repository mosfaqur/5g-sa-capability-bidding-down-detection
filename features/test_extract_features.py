#!/usr/bin/env python3
"""Standalone smoke test for extract_features.py.

Unlike custody_append.py, rrc_capture.py, and window_builder.py before this
review pass, this module already had inline self-tests (_selftest_extract,
_selftest_xlayer, run via `python3 extract_features.py`) - but those only
exercise extract()/xlayer() end-to-end against one real pcap, not the smaller
helper functions (_raw_hex, _pcap_timestamp_to_epoch, _encode_ue_category,
_mimo_layers_to_int, write_csv_row) that carry the documented pyshark quirks
and edge-case handling. This file adds unit coverage for those, formalizes
the existing end-to-end checks as real assertions instead of print statements,
and is named test_*.py for consistency with the other three test files added
during this review.

Requires pyshark/tshark - run under proxy/venv, same as extract_features.py
itself: ../proxy/venv/bin/python3 test_extract_features.py

Never writes into data/raw/ or features/ - CSV tests use a temp file, and
extract() is only ever called against the read-only committed exhibit pcap.
"""
import io
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "proxy"))
import ngap_decode  # noqa: E402
from extract_features import (  # noqa: E402
    CSV_METADATA_COLS,
    FEATURE_COLS,
    _capability_record_from_bytes,
    _encode_ue_category,
    _mimo_layers_to_int,
    _pcap_timestamp_to_epoch,
    _raw_hex,
    _warn_if_ue_category_missing,
    extract,
    write_csv_row,
    xlayer,
)

EXHIBIT_PCAP = str(Path(__file__).resolve().parent.parent / "data/raw/exhibits/ngap_label0_full.pcap")


def test_raw_hex_handles_both_pyshark_shapes() -> None:
    """pyshark's include_raw=True field is sometimes a plain hex string,
    sometimes [hexstr, length, ...] metadata for the same field across
    different frames in the same file - found live, not documented pyshark
    behaviour (see extract_features.py's _raw_hex docstring)."""
    assert _raw_hex("deadbeef") == "deadbeef"
    assert _raw_hex(["deadbeef", 4, 0, 1]) == "deadbeef"
    print("test_raw_hex_handles_both_pyshark_shapes: PASSED")


def test_pcap_timestamp_to_epoch_truncates_nanoseconds() -> None:
    """pyshark returns sniff_timestamp as an ISO8601 string with nanosecond
    precision on this build, not a numeric epoch float - _pcap_timestamp_to_epoch
    must truncate to microsecond precision before datetime.fromisoformat(), not
    raise on the extra digits, and must not silently corrupt the value in doing
    so (compare against the same instant computed independently via
    datetime.fromisoformat on the already-6-digit form, not a hand-computed
    magic number)."""
    from datetime import datetime

    expected = datetime.fromisoformat("2026-07-30T10:58:51.215477+00:00").timestamp()

    epoch_from_9_digit_z_form = _pcap_timestamp_to_epoch("2026-07-30T10:58:51.215477123Z")
    assert abs(epoch_from_9_digit_z_form - expected) < 1e-3, (
        f"9-digit 'Z' form should truncate to the same instant: got {epoch_from_9_digit_z_form}, expected {expected}"
    )

    epoch_from_6_digit_offset_form = _pcap_timestamp_to_epoch("2026-07-30T10:58:51.215477+00:00")
    assert abs(epoch_from_6_digit_offset_form - expected) < 1e-6
    print("test_pcap_timestamp_to_epoch_truncates_nanoseconds: PASSED")


def test_encode_ue_category() -> None:
    assert _encode_ue_category("rel15") == 15
    assert _encode_ue_category("rel8") == 8
    assert _encode_ue_category("spare1") == 1
    assert _encode_ue_category(None) == -1
    assert _encode_ue_category("") == -1
    assert _encode_ue_category("no-digits-here") == -1
    print("test_encode_ue_category: PASSED")


def test_warn_if_ue_category_missing() -> None:
    """2026-07-31 finding: ue_category=-1 means accessStratumRelease was
    missing/unparseable - a decode anomaly, not label 1's real downgrade
    signal (which produces a valid codepoint, spare1, encoded as 1). Nothing
    else in the pipeline flagged this before now - a -1 row under any label
    other than 1 would sit even further from baseline (15) than label 1's
    legitimate 1, indistinguishable from it at the feature level, risking
    exactly the SHAP validation the project's testbed architecture notes §8.3 describes
    ("SHAP attributes highest weight to ue_category for label 1")."""
    buf = io.StringIO()
    with redirect_stderr(buf):
        _warn_if_ue_category_missing("dummy.pcap", 1.0, -1)
    assert "WARNING" in buf.getvalue() and "ue_category=-1" in buf.getvalue()

    buf2 = io.StringIO()
    with redirect_stderr(buf2):
        _warn_if_ue_category_missing("dummy.pcap", 1.0, 15)
    assert buf2.getvalue() == "", "a valid ue_category must not trigger any warning"
    print("test_warn_if_ue_category_missing: PASSED")


def test_mimo_layers_to_int() -> None:
    assert _mimo_layers_to_int(None) == 1
    assert _mimo_layers_to_int([]) == 1
    assert _mimo_layers_to_int(["oneLayer"]) == 1
    assert _mimo_layers_to_int(["twoLayers"]) == 2
    assert _mimo_layers_to_int(["fourLayers"]) == 4
    assert _mimo_layers_to_int(["eightLayers"]) == 8
    # Multiple distinct values across component-carrier feature sets - the
    # aggregate feature is the best (max) supported layer count.
    assert _mimo_layers_to_int(["oneLayer", "fourLayers"]) == 4
    print("test_mimo_layers_to_int: PASSED")


def test_capability_record_from_bytes_matches_profile_fingerprint() -> None:
    """Round-trip a real UE-NR-Capability (the SW-Ext profile template from
    ngap_decode.py) through _capability_record_from_bytes and confirm every
    field matches the documented SW-Ext fingerprint (bands n1/n3/n28/n78, CA
    on, 4x4 DL/2x2 UL MIMO, VoNR on)."""
    cap = ngap_decode.PROFILE_CAPABILITIES["sw-ext"]
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()

    # _capability_record_from_bytes takes the NGAP IE 117 OCTET STRING content,
    # which is layers 2/3 wrapping layer 4 - build that wrapper the same way
    # ngap_decode._build_ue_radio_capability_bytes does.
    container_bytes = ngap_decode._build_ue_radio_capability_bytes(cap)
    record = _capability_record_from_bytes(container_bytes)

    assert record is not None
    assert record["ue_category"] == 15
    assert record["ca_supported"] is True
    assert record["ca_band_count"] == 1
    assert record["mimo_layers_dl"] == 4
    assert record["mimo_layers_ul"] == 2
    assert record["vonr_supported"] is True
    assert record["nr_band_count"] == 4
    # 2026-07-31 fix: capability_size_bytes/container_bytes are the inner
    # ue-CapabilityRAT-Container octets (raw, the layer-4 UE-NR-Capability bytes
    # this test built), not the outer NGAP IE 117 wrapper (container_bytes,
    # which additionally wraps a UE-CapabilityRAT-ContainerList + rat-Type tag -
    # a fixed few bytes larger even for identical content). See
    # ngap_decode.decode_ue_radio_capability_container()'s docstring.
    assert record["capability_size_bytes"] == len(raw)
    assert record["container_bytes"] == raw
    assert len(container_bytes) > len(raw), (
        "sanity check: the outer NGAP wrapper must be larger than the inner "
        "container it wraps, confirming this test still exercises the real "
        "two-layer structure rather than accidentally comparing equal-length data"
    )
    print("test_capability_record_from_bytes_matches_profile_fingerprint: PASSED")


def test_write_csv_row_header_written_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "raw_12f.csv"
        features = {c: 0 for c in FEATURE_COLS}
        features["ue_category"] = 15

        write_csv_row(str(csv_path), "sess-1", "0006", "2026-07-30T00:00:00Z", "SW-Std", 0, features)
        write_csv_row(str(csv_path), "sess-1", "0006", "2026-07-30T00:00:01Z", "SW-Std", 0, features)

        lines = csv_path.read_text().splitlines()
        assert len(lines) == 3, f"expected 1 header + 2 data rows, got {len(lines)} lines"
        assert lines[0].split(",") == CSV_METADATA_COLS + FEATURE_COLS
    print("test_write_csv_row_header_written_once: PASSED")


def test_extract_against_real_exhibit_pcap() -> None:
    """Formalizes the existing _selftest_extract as real assertions. Matches
    the documented pre-rewrite (native UERANSIM minimal) and post-rewrite
    (SW-Std baseline) events in data/raw/exhibits/ngap_label0_full.pcap."""
    rows = extract(EXHIBIT_PCAP)
    assert len(rows) == 2, f"expected 2 capability events, got {len(rows)}"
    for row in rows:
        assert list(row.keys()) == FEATURE_COLS

    pre_rewrite, post_rewrite = rows[0], rows[1]
    assert pre_rewrite["ca_supported"] is False
    assert pre_rewrite["ca_band_count"] == 0
    assert pre_rewrite["mimo_layers_dl"] == 1
    assert pre_rewrite["vonr_supported"] is False

    assert post_rewrite["ue_category"] == 15
    assert post_rewrite["ca_supported"] is True
    assert post_rewrite["ca_band_count"] == 1
    assert post_rewrite["mimo_layers_dl"] == 2
    assert post_rewrite["mimo_layers_ul"] == 1
    assert post_rewrite["vonr_supported"] is True
    assert post_rewrite["nr_band_count"] == 1
    assert post_rewrite["session_timestamp_delta"] > 0
    print("test_extract_against_real_exhibit_pcap: PASSED")


def test_xlayer_isolates_single_divergent_field() -> None:
    """Formalizes the existing _selftest_xlayer as real assertions."""
    base = {
        "ue_category": 15, "ca_supported": True, "ca_band_count": 2,
        "mimo_layers_dl": 2, "mimo_layers_ul": 1, "vonr_supported": True,
        "nr_band_count": 1, "capability_size_bytes": 34, "ie_field_count": 4,
        "container_bytes": b"\x01\x02\x03\x04",
    }
    rrc = dict(base)
    n2 = dict(base)
    n2["vonr_supported"] = False
    n2["container_bytes"] = b"\x01\x02\x03\x99"

    result = xlayer(rrc, n2)
    assert result["vonr_supported_match"] is False
    assert result["num_fields_mismatched"] == 1
    assert result["container_hash_match"] is False
    for field in (
        "ue_category_delta", "ca_supported_match", "ca_band_count_delta",
        "mimo_dl_delta", "mimo_ul_delta", "nr_band_count_delta",
        "capability_size_delta", "ie_field_count_delta",
    ):
        assert result[field] in (0, True), f"unexpected divergence flagged in unmodified field {field}"
    print("test_xlayer_isolates_single_divergent_field: PASSED")


def main() -> int:
    test_raw_hex_handles_both_pyshark_shapes()
    test_pcap_timestamp_to_epoch_truncates_nanoseconds()
    test_encode_ue_category()
    test_warn_if_ue_category_missing()
    test_mimo_layers_to_int()
    test_capability_record_from_bytes_matches_profile_fingerprint()
    test_write_csv_row_header_written_once()
    test_extract_against_real_exhibit_pcap()
    test_xlayer_isolates_single_divergent_field()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
