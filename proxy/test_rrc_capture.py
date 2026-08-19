#!/usr/bin/env python3
"""Standalone smoke test for rrc_capture.py.

2026-07-31: case (b) is now live-validated, not just internally consistent.
A genuine cached reattach was captured from a real handset (Realme RMX3363,
imsi-...0004, NAS Service Request reusing the AMF's cached capability) - see
the project's internal build log's "Cached-reattach (case b) live validation" section for the full
narrative. Two real findings came out of that session, both fixed:

1. parse_gnb_log() originally required a matching NGAP Tx
   UERadioCapabilityInfoIndication line to record ANY event - but real case
   (b) never sends one (nothing new to report to the AMF), so the tool
   silently dropped every genuine case-(b) event it ever saw. Fixed by
   falling back to the InitialContextSetupResponse Tx line (present in both
   cases) when no UERadioCapabilityInfoIndication follows - see
   ICS_RESPONSE_RE and the "join_source" field this test file now checks.
2. Even once captured, a real case-(b) reattach's own RRC echo cannot detect
   an attack applied at the ORIGINAL registration that populated the AMF's
   cache, because that echo is sourced from the same (possibly
   already-attacked) N2 bytes - try_rewrite only fires gnb->amf, never
   amf->gnb. update_reference()/write_record()'s reference_dir persists the
   last known-good case-a (byte_exact=False) capability per IMSI so a LATER
   reattach's N2-side capability can be checked against a genuinely
   independent reference instead - see features/test_xlayer_cross_layer_validity.py
   for the real-data before/after comparison.

The case-(b) synthetic fixture tests below (still kept, alongside the real
capture) predate that session and were themselves found to embed an
inaccurate assumption (a fake matching NGAP Tx line that real case (b) never
sends) - corrected to match the real shape once it was observed live.

Never touches /tmp/gnb.log, /tmp/amf.log, or data/raw/rrc/ - every test
builds its own synthetic log text and writes only to a temp directory.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
from rrc_capture import (  # noqa: E402
    _capability_dict_and_bytes,
    capability_record_from_rrc_json,
    find_imsi_near,
    parse_gnb_log,
    run_once,
    update_reference,
    write_record,
)

# A real, minimal, pretty-printed case-(a) capability dict, matching the shape
# actually observed in /tmp/gnb.log (accessStratumRelease at top level).
CASE_A_CAPABILITY = {
    "accessStratumRelease": "rel15",
    "pdcp-Parameters": {"supportedROHC-Profiles": {"profile0x0000": True}},
    "rf-Parameters": {"supportedBandListNR": [{"bandNR": 78}]},
}


def _pretty_json_lines(d: dict) -> list:
    return json.dumps(d, indent=2).splitlines()


def test_capability_dict_and_bytes_case_a() -> None:
    decoded, raw_bytes = _capability_dict_and_bytes(CASE_A_CAPABILITY)
    assert raw_bytes is None, "case (a) has no raw PER bytes available"
    assert decoded == CASE_A_CAPABILITY
    print("test_capability_dict_and_bytes_case_a: PASSED")


def test_capability_dict_and_bytes_case_b() -> None:
    cap = dict(ngap_decode.PROFILE_CAPABILITIES["sw-std"])
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
    case_b_json = {"rat-Type": "nr", "ue-CapabilityRAT-Container": raw.hex()}

    decoded, raw_bytes = _capability_dict_and_bytes(case_b_json)
    assert raw_bytes == raw, "case (b) must return the exact PER bytes it decoded"
    assert decoded.get("accessStratumRelease") == "rel15"
    print("test_capability_dict_and_bytes_case_b: PASSED")


def test_capability_record_byte_exact_flag() -> None:
    record_a = capability_record_from_rrc_json(CASE_A_CAPABILITY)
    assert record_a["byte_exact"] is False, "case (a) must be flagged non-byte-exact"

    cap = dict(ngap_decode.PROFILE_CAPABILITIES["sw-std"])
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
    case_b_json = {"rat-Type": "nr", "ue-CapabilityRAT-Container": raw.hex()}
    record_b = capability_record_from_rrc_json(case_b_json)
    assert record_b["byte_exact"] is True, "case (b) must be flagged byte-exact"
    assert record_b["capability_size_bytes"] == len(raw), "byte-exact size must equal the real PER length"
    assert record_b["ca_supported"] is True and record_b["ca_band_count"] == 1
    assert record_b["mimo_layers_dl"] == 2 and record_b["mimo_layers_ul"] == 1
    assert record_b["vonr_supported"] is True

    print("test_capability_record_byte_exact_flag: PASSED")


def _gnb_log_case_a(ue: str = "0", ran_ue: str = "0", amf_ue: str = "1") -> str:
    """Reproduces the exact block shape found live in /tmp/gnb.log: a bare
    "UE Capabilities:" header, a bare "{" opening the JSON on its own line,
    pretty-printed body, then a nearby NGAP Tx line and a ue/ran_ue/amf_ue
    context line, same relative ordering as the real log."""
    lines = [
        f"2026-07-30T10:58:51.100000 [NGAP    ] [I] Tx PDU ue={ue} ran_ue={ran_ue} amf_ue={amf_ue}: InitialContextSetupResponse",
        f"2026-07-30T10:58:51.215477 [RRC     ] [D] ue={ue} c-rnti=0x4601: UE Capabilities:",
        *_pretty_json_lines(CASE_A_CAPABILITY),
        f"2026-07-30T10:58:51.215604 [NGAP    ] [I] Tx PDU ue={ue} ran_ue={ran_ue}: UERadioCapabilityInfoIndication",
    ]
    return "\n".join(lines) + "\n"


def test_parse_gnb_log_case_a() -> None:
    text = _gnb_log_case_a()
    events = parse_gnb_log(text)
    assert len(events) == 1, f"expected 1 event, got {len(events)}"
    ev = events[0]
    assert ev["ran_ue_ngap_id"] == 0
    assert ev["amf_ue_ngap_id"] == 1
    assert ev["ngap_tx_timestamp"] == "2026-07-30T10:58:51.215604"
    assert ev["capability_json"] == CASE_A_CAPABILITY
    assert ev["join_source"] == "UERadioCapabilityInfoIndication"
    print("test_parse_gnb_log_case_a: PASSED")


def _gnb_log_case_b(ue: str = "0", ran_ue: str = "0", amf_ue: str = "1") -> str:
    """Synthetic case (b): RRC_HEADER_RE requires the "UE Capabilities:" line to
    end there ($) - no trailing content - so the "opening brace line" the
    parse_gnb_log docstring describes as carrying its own prefix must be a
    genuinely separate subsequent log line (e.g. its own "<ts> [RRC] [D] {"
    line), not appended to the header. Body otherwise pretty-printed the same
    as case (a).

    2026-07-31 correction: this fixture originally appended a fake matching
    UERadioCapabilityInfoIndication Tx line, which is NOT what a real case-(b)
    reattach does - confirmed live (Realme/imsi-...0004, NAS Service Request):
    no UERadioCapabilityInfoIndication anywhere in that ue's entire NGAP
    transcript. Real case (b) is joined via the InitialContextSetupResponse Tx
    line instead (present in both cases) - see ICS_RESPONSE_RE. Corrected to
    match the real observed shape rather than the original (wrong) assumption."""
    cap = dict(ngap_decode.PROFILE_CAPABILITIES["sw-min"])
    with ngap_decode._lock:
        ngap_decode._l4.set_val(cap)
        raw = ngap_decode._l4.to_uper()
    case_b_json = {"rat-Type": "nr", "ue-CapabilityRAT-Container": raw.hex()}
    body_lines = _pretty_json_lines(case_b_json)  # body_lines[0] == "{"

    lines = [
        f"2026-07-30T11:00:00.200000 [RRC     ] [D] ue={ue} c-rnti=0x4602: UE Capabilities:",
        f"2026-07-30T11:00:00.200005 [RRC     ] [D] {body_lines[0]}",
        *body_lines[1:],
        # Real order (confirmed live): InitialContextSetupResponse follows the RRC
        # capability block, not precedes it - no UERadioCapabilityInfoIndication
        # line at all, since real case (b) never sends one.
        f"2026-07-30T11:00:00.200130 [NGAP    ] [I] Tx PDU ue={ue} ran_ue={ran_ue} amf_ue={amf_ue}: InitialContextSetupResponse",
    ]
    return "\n".join(lines) + "\n", case_b_json


def test_parse_gnb_log_case_b() -> None:
    text, expected_json = _gnb_log_case_b()
    events = parse_gnb_log(text)
    assert len(events) == 1, f"expected 1 event, got {len(events)}"
    ev = events[0]
    assert ev["capability_json"] == expected_json, (
        "parse_gnb_log did not reconstruct the case-(b) JSON correctly when the "
        "opening line carries a log prefix before the '{'"
    )
    assert ev["join_source"] == "InitialContextSetupResponse", (
        "real case (b) has no UERadioCapabilityInfoIndication to join on - must "
        f"fall back to InitialContextSetupResponse, got {ev['join_source']!r}"
    )
    record = capability_record_from_rrc_json(ev["capability_json"])
    assert record["byte_exact"] is True
    assert record["ca_supported"] is False  # sw-min profile: no CA
    print("test_parse_gnb_log_case_b: PASSED")


def test_parse_gnb_log_no_match_dropped() -> None:
    """An RRC 'UE Capabilities:' block with no corresponding NGAP Tx line for
    the same ue index must not produce an event (nothing to join to)."""
    lines = [
        "2026-07-30T10:58:51.215477 [RRC     ] [D] ue=0 c-rnti=0x4601: UE Capabilities:",
        *_pretty_json_lines(CASE_A_CAPABILITY),
        # no matching "Tx PDU ue=0 ... UERadioCapabilityInfoIndication" line follows
    ]
    text = "\n".join(lines) + "\n"
    events = parse_gnb_log(text)
    assert events == [], f"expected no events without a matching NGAP Tx line, got {events}"
    print("test_parse_gnb_log_no_match_dropped: PASSED")


AMF_LOG_TEXT = (
    "\x1b[32m07/30 22:58:51.418\x1b[0m: \x1b[33mgmm\x1b[0m INFO: [imsi-001010000000001] Registration complete\n"
    "\x1b[32m07/30 22:59:30.000\x1b[0m: \x1b[33mgmm\x1b[0m INFO: [imsi-001010000000099] Registration complete\n"
)


def test_find_imsi_near() -> None:
    import datetime as dt

    with tempfile.TemporaryDirectory() as tmp:
        amf_log = Path(tmp) / "amf.log"
        amf_log.write_text(AMF_LOG_TEXT)

        # gnb.log is naive UTC; system timezone here is NZST (+12:00) per
        # /etc, confirmed live against /tmp/gnb.log + /tmp/amf.log during the
        # 2026-07-31 review - 22:58:51 local == 10:58:51 UTC.
        target_utc = dt.datetime(2026, 7, 30, 10, 58, 51, 300000, tzinfo=dt.timezone.utc)
        imsi = find_imsi_near(amf_log, target_utc, window_s=30.0)
        assert imsi == "001010000000001", f"expected the near-in-time IMSI, got {imsi!r}"

        far_target = dt.datetime(2026, 7, 30, 9, 0, 0, tzinfo=dt.timezone.utc)
        imsi_far = find_imsi_near(amf_log, far_target, window_s=30.0)
        assert imsi_far is None, f"expected no match outside window_s, got {imsi_far!r}"

    print("test_find_imsi_near: PASSED")


def test_run_once_writes_record_and_dedups() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gnb_log = tmp_path / "gnb.log"
        amf_log = tmp_path / "amf.log"
        output_dir = tmp_path / "rrc_out"

        gnb_log.write_text(_gnb_log_case_a())
        amf_log.write_text(AMF_LOG_TEXT)

        seen = set()
        next_idx = run_once(gnb_log, amf_log, output_dir, label=0, profile="test", session_id="smoke", start_event=0, seen=seen)
        assert next_idx == 1, f"expected 1 event written, got index {next_idx}"

        written = list(output_dir.glob("rrc_0_test_smoke_*.json"))
        assert len(written) == 1, f"expected exactly 1 output file, got {[f.name for f in written]}"
        out = json.loads(written[0].read_text())
        assert out["label"] == 0
        assert out["profile"] == "test"
        assert out["session_id"] == "smoke"
        assert out["ran_ue_ngap_id"] == 0
        assert out["amf_ue_ngap_id"] == 1
        assert out["record"]["byte_exact"] is False
        assert isinstance(out["record"]["container_bytes"], str)  # hex-encoded, JSON-serialisable
        bytes.fromhex(out["record"]["container_bytes"])  # must round-trip as valid hex

        # Re-running with the same seen set against the same log must not
        # produce a second file for the same event.
        next_idx_2 = run_once(gnb_log, amf_log, output_dir, label=0, profile="test", session_id="smoke", start_event=next_idx, seen=seen)
        assert next_idx_2 == next_idx, "re-processing the same log must not advance the event index"
        written_2 = list(output_dir.glob("rrc_0_test_smoke_*.json"))
        assert len(written_2) == 1, "re-processing the same log must not write a duplicate file"

    print("test_run_once_writes_record_and_dedups: PASSED")


def test_update_reference_only_persists_case_a() -> None:
    """update_reference() must persist a case-(a) (byte_exact=False) record per
    IMSI, and must skip a case-(b) (byte_exact=True) record - case (b)'s RRC
    echo is sourced from the AMF's cached N2 bytes, not an independent live UE
    exchange, so it cannot serve as a trustworthy reference (see module
    docstring)."""
    with tempfile.TemporaryDirectory() as tmp:
        reference_dir = Path(tmp) / "reference"

        event_a = {
            "gnb_ue_index": 0,
            "c_rnti": "0x4601",
            "ran_ue_ngap_id": 0,
            "amf_ue_ngap_id": 1,
            "rrc_timestamp": "2026-07-31T00:00:00.000000",
            "ngap_tx_timestamp": "2026-07-31T00:00:00.000100",
            "join_source": "UERadioCapabilityInfoIndication",
            "capability_json": CASE_A_CAPABILITY,
        }
        out_a = {
            "label": 0, "profile": "test", "session_id": "smoke", "event": 0,
            "ran_ue_ngap_id": 0, "amf_ue_ngap_id": 1, "gnb_ue_index": 0, "c_rnti": "0x4601",
            "rrc_timestamp_utc": event_a["rrc_timestamp"], "ngap_tx_timestamp_utc": event_a["ngap_tx_timestamp"],
            "join_source": event_a["join_source"], "imsi": "001010000000004",
            "record": capability_record_from_rrc_json(event_a["capability_json"]),
            "raw_rrc_capability": event_a["capability_json"],
        }
        out_a["record"]["container_bytes"] = out_a["record"]["container_bytes"].hex()
        assert out_a["record"]["byte_exact"] is False

        path_a = update_reference(reference_dir, "001010000000004", out_a)
        assert path_a is not None, "case-a record must be persisted"
        assert path_a == reference_dir / "001010000000004.json"
        assert path_a.exists()

        cap_b = dict(ngap_decode.PROFILE_CAPABILITIES["sw-min"])
        with ngap_decode._lock:
            ngap_decode._l4.set_val(cap_b)
            raw_b = ngap_decode._l4.to_uper()
        case_b_json = {"rat-Type": "nr", "ue-CapabilityRAT-Container": raw_b.hex()}
        out_b = dict(out_a)
        out_b["record"] = capability_record_from_rrc_json(case_b_json)
        out_b["record"]["container_bytes"] = out_b["record"]["container_bytes"].hex()
        assert out_b["record"]["byte_exact"] is True

        # A case-(b) record for the same IMSI must not overwrite the reference,
        # and must not create one on its own for a different IMSI either.
        path_b = update_reference(reference_dir, "001010000000004", out_b)
        assert path_b is None, "case-b record must not be persisted as a reference"
        assert json.loads(path_a.read_text())["record"]["byte_exact"] is False, (
            "case-a reference must be untouched by a later case-b record for the same IMSI"
        )

        path_none_imsi = update_reference(reference_dir, None, out_a)
        assert path_none_imsi is None, "a record with no resolved IMSI must not be persisted"

    print("test_update_reference_only_persists_case_a: PASSED")


def test_write_record_updates_reference_only_for_case_a() -> None:
    """write_record()'s reference_dir plumbing: a case-(a) event updates the
    per-IMSI reference file; a case-(b) event for the same IMSI does not."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        output_dir = tmp_path / "rrc_out"
        reference_dir = tmp_path / "reference"

        text_a = _gnb_log_case_a(ue="0", ran_ue="0", amf_ue="1")
        events_a = parse_gnb_log(text_a)
        write_record(output_dir, 0, "test", "smoke", 0, events_a[0], "001010000000004", reference_dir)
        ref_path = reference_dir / "001010000000004.json"
        assert ref_path.exists(), "case-a write_record() call must create the per-IMSI reference"
        first_ref = json.loads(ref_path.read_text())
        assert first_ref["record"]["byte_exact"] is False

        text_b, _ = _gnb_log_case_b(ue="1", ran_ue="1", amf_ue="2")
        events_b = parse_gnb_log(text_b)
        write_record(output_dir, 0, "test", "smoke", 1, events_b[0], "001010000000004", reference_dir)
        second_ref = json.loads(ref_path.read_text())
        assert second_ref == first_ref, "a case-b write_record() call must not touch the existing reference"

    print("test_write_record_updates_reference_only_for_case_a: PASSED")


def main() -> int:
    test_capability_dict_and_bytes_case_a()
    test_capability_dict_and_bytes_case_b()
    test_capability_record_byte_exact_flag()
    test_parse_gnb_log_case_a()
    test_parse_gnb_log_case_b()
    test_parse_gnb_log_no_match_dropped()
    test_find_imsi_near()
    test_run_once_writes_record_and_dedups()
    test_update_reference_only_persists_case_a()
    test_write_record_updates_reference_only_for_case_a()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
