#!/usr/bin/env python3
"""12-feature extractor for N2 PCAPs (the project's testbed architecture notes §7.1/§7.2) plus the
11-feature cross-layer consistency comparator (§7.2, cross-layer subsection).

extract(pcap_path) finds every UERadioCapabilityInfoIndication (procedureCode=44)
NGAP PDU in the capture with pyshark, then hands the raw PDU bytes to
proxy/ngap_decode.py for the actual ASN.1 decode - that module's capability
parsing is already validated against live Wireshark ground truth (Step 2,
the project's testbed architecture notes §6.2), so this file does not re-implement field parsing,
only feature derivation on top of it.

xlayer(rrc_record, n2_record) takes two "capability record" dicts (same shape as
_capability_record_from_bytes() below - proxy/rrc_capture.py, Build 0d, produces
records in this same shape, confirmed live against a real-handset RRC/N2 pair on
2026-07-30) and returns the 11 cross-layer consistency features.
"""
import csv
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyshark
from pyshark.capture.capture import TSharkCrashException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "proxy"))
import ngap_decode  # noqa: E402

FEATURE_COLS = [
    "ue_category",
    "ca_supported",
    "ca_band_count",
    "mimo_layers_dl",
    "mimo_layers_ul",
    "vonr_supported",
    "volte_supported",
    "nr_band_count",
    "psm_supported",
    "total_capability_size_bytes",
    "ie_field_count",
    "session_timestamp_delta",
]

XLAYER_COLS = [
    "ue_category_delta",
    "ca_supported_match",
    "ca_band_count_delta",
    "mimo_dl_delta",
    "mimo_ul_delta",
    "vonr_supported_match",
    "nr_band_count_delta",
    "capability_size_delta",
    "ie_field_count_delta",
    "num_fields_mismatched",
    "container_hash_match",
]

CSV_METADATA_COLS = ["session_id", "ue_imsi", "timestamp", "ue_profile", "label"]

# 3GPP TS 38.331 UE-NR-Capability MIMO-LayersDL/-UL enums. DL has no 'oneLayer'
# value at all - 1-layer DL support is modelled by the field being absent, not a
# value (confirmed in ngap_decode.apply_mimo_reduced's docstring). We apply the
# same "absent means 1" convention here for both DL and UL.
_MIMO_LAYER_VALUES = {"oneLayer": 1, "twoLayers": 2, "fourLayers": 4, "eightLayers": 8}


def _mimo_layers_to_int(layers: Optional[list]) -> int:
    if not layers:
        return 1
    return max(_MIMO_LAYER_VALUES.get(v, 1) for v in layers)


def _encode_ue_category(access_stratum_release: Optional[str]) -> int:
    """NR RRC has no ue-Category IE (ngap_decode.summarize_capability docstring);
    the closest analogue is the numeric release embedded in accessStratumRelease
    (e.g. 'rel15' -> 15). Unparseable/missing -> -1."""
    if not access_stratum_release:
        return -1
    m = re.search(r"\d+", access_stratum_release)
    return int(m.group()) if m else -1


def _raw_hex(raw_field) -> str:
    """pyshark's include_raw=True sometimes wraps a raw hex field as a plain str
    and sometimes as [hexstr, length, ...] metadata, depending on whether the
    layer occurs once or is JSON-flattened - observed on real capture files, not
    documented pyshark behaviour. Handle both."""
    return raw_field[0] if isinstance(raw_field, list) else raw_field


def _pcap_timestamp_to_epoch(sniff_timestamp: str) -> float:
    """pyshark (use_json=True on this build) returns sniff_timestamp as an ISO8601
    string with nanosecond precision rather than a numeric epoch - truncate to
    microseconds (Python datetime's native resolution) before parsing.

    2026-07-31 fix: the fractional-seconds run must be split from the timezone
    suffix by matching digits (\\d+), not a hardcoded frac_and_tz[:9] - the
    original slice assumed exactly 9 fractional digits always precede the
    timezone marker (true for pyshark's own 9-digit nanosecond timestamps, the
    only input this function is actually called with today), but silently
    corrupted the timezone suffix and raised ValueError on any input with
    fewer digits - including Python's own standard 6-digit
    datetime.isoformat() output, caught by test_extract_features.py."""
    ts = sniff_timestamp.replace("Z", "+00:00")
    if "." in ts:
        head, frac_and_tz = ts.split(".", 1)
        m = re.match(r"(\d+)(.*)", frac_and_tz)
        frac, tz = (m.group(1), m.group(2)) if m else (frac_and_tz, "")
        ts = f"{head}.{frac[:6]}{tz}"
    return datetime.fromisoformat(ts).timestamp()


def _capability_record_from_bytes(cap_container_bytes: bytes) -> Optional[dict]:
    """Decode one UERadioCapability container (the NGAP IE 117 OCTET STRING) into
    the shared record shape used by both extract() and xlayer().

    2026-07-31 fix: capability_size_bytes/container_bytes now come from
    decoded["container_bytes"] - the inner ue-CapabilityRAT-Container octets - not
    the outer cap_container_bytes passed in (the raw NGAP IE 117 OCTET STRING,
    which wraps a UE-CapabilityRAT-ContainerList plus a rat-Type tag even for a
    single nr entry). Confirmed live against a real registration: the two differ
    by a fixed ~6 bytes despite identical content, which made container_hash_match
    always False and capability_size_delta always +6 in xlayer() for every real
    byte_exact=True (case-b) RRC/N2 pair - rrc_capture.py's case-(b) path already
    extracts at this same inner scope (srsRAN's RRC-layer log gives the inner
    container directly), so aligning here is what makes the two sides comparable.
    See ngap_decode.decode_ue_radio_capability_container()'s docstring."""
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_container_bytes)
    if decoded is None:
        return None
    capability = decoded["capability"]
    container_bytes = decoded["container_bytes"]
    summary = ngap_decode.summarize_capability(capability)

    rf_params = capability.get("rf-Parameters", {}) or {}
    ca_band_count = len(rf_params.get("supportedBandCombinationList", []) or [])

    return {
        "ue_category": _encode_ue_category(summary["access_stratum_release"]),
        "ca_supported": bool(summary["ca_supported"]),
        "ca_band_count": ca_band_count,
        "mimo_layers_dl": _mimo_layers_to_int(summary["mimo_dl_layers"]),
        "mimo_layers_ul": _mimo_layers_to_int(summary["mimo_ul_layers"]),
        "vonr_supported": bool(summary["vonr_supported"]),
        "nr_band_count": summary["band_count"],
        "capability_size_bytes": len(container_bytes),
        "ie_field_count": len(capability),
        "container_bytes": container_bytes,
    }


def extract(pcap_path: str) -> list:
    """Parse every UERadioCapabilityInfoIndication event in pcap_path and return
    a list of 12-feature dicts (keys = FEATURE_COLS), one per event, in capture
    order. session_timestamp_delta is computed against the previous event in this
    same call (one pcap == one profile/run, per the Session B capture convention -
    the project's testbed architecture notes §7.3)."""
    cap = pyshark.FileCapture(
        pcap_path,
        display_filter=f"ngap.procedureCode=={ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION}",
        include_raw=True,
        use_json=True,
    )
    events = []
    try:
        try:
            for pkt in cap:
                raw = bytes.fromhex(_raw_hex(pkt.ngap_raw.value))
                pdu_val = ngap_decode.decode_ngap_pdu(raw)
                if pdu_val is None:
                    continue
                cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
                if not cap_bytes:
                    continue
                record = _capability_record_from_bytes(cap_bytes)
                if record is None:
                    continue
                events.append((_pcap_timestamp_to_epoch(pkt.sniff_timestamp), record))
        except TSharkCrashException as exc:
            # Several validation-session pcaps in this project were cut short by a
            # killed proxy/nr-gnb process mid-capture (Bug 13/17) - tshark treats a
            # truncated final packet as fatal even though every earlier packet,
            # including any capability events, decoded fine. Keep what was already
            # parsed instead of discarding it.
            print(f"extract({pcap_path}): tshark reported a trailing error after {len(events)} event(s) parsed - {exc}", file=sys.stderr)
    finally:
        try:
            cap.close()
        except TSharkCrashException:
            # _cleanup_subprocess() raised before it could clear _running_processes,
            # so Capture.__del__ would otherwise retry close() later against an
            # event loop that's no longer safe to reuse - clear it ourselves.
            cap._running_processes.clear()

    events.sort(key=lambda e: e[0])

    rows = []
    prev_ts = None
    for ts, record in events:
        rows.append(
            {
                "ue_category": record["ue_category"],
                "ca_supported": record["ca_supported"],
                "ca_band_count": record["ca_band_count"],
                "mimo_layers_dl": record["mimo_layers_dl"],
                "mimo_layers_ul": record["mimo_layers_ul"],
                "vonr_supported": record["vonr_supported"],
                # 5G SA has no VoLTE (LTE-only concept) and the RRC UE-NR-Capability
                # container carries no PSM (NAS/MM concept) field - both are kept
                # fixed False for schema completeness, per the project's testbed architecture notes
                # §7.2's note that zero-variance features are retained and dropped
                # later during analysis if confirmed.
                "volte_supported": False,
                "nr_band_count": record["nr_band_count"],
                "psm_supported": False,
                "total_capability_size_bytes": record["capability_size_bytes"],
                "ie_field_count": record["ie_field_count"],
                "session_timestamp_delta": 0.0 if prev_ts is None else ts - prev_ts,
            }
        )
        _warn_if_ue_category_missing(pcap_path, ts, record["ue_category"])
        prev_ts = ts

    return rows


def _warn_if_ue_category_missing(pcap_path: str, ts: float, ue_category: int) -> None:
    """-1 means accessStratumRelease was missing/unparseable - a decode
    anomaly, not a real network signal - not the label 1 attack, which
    produces a valid (if reserved) codepoint, spare1, encoded as 1.
    the project's testbed architecture notes §8.3's SHAP validation narrative ("SHAP attributes
    highest weight to ue_category for label 1") implicitly assumes
    ue_category's variance is driven only by real signal; a -1 row under any
    other label would sit even further from baseline (15) than label 1's
    legitimate 1, so it's indistinguishable from label 1 at the feature level
    and could contaminate whichever class's rows it lands in. Nothing else in
    this pipeline currently surfaces this, so it would otherwise silently
    reach raw_12f.csv - flag it here instead."""
    if ue_category == -1:
        print(
            f"extract({pcap_path}): WARNING - event at {ts} has ue_category=-1 "
            "(accessStratumRelease missing/unparseable) - likely a decode "
            "anomaly, not a real attack signal; review before including in "
            "training data",
            file=sys.stderr,
        )


def write_csv_row(csv_path: str, session_id: str, ue_imsi: str, timestamp: str, ue_profile: str, label: int, features: dict) -> None:
    """Append one full Session B schema row: metadata prefix (session_id, ue_imsi,
    timestamp, ue_profile, label) then the 12 FEATURE_COLS, in that order."""
    path = Path(csv_path)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_METADATA_COLS + FEATURE_COLS)
        writer.writerow([session_id, ue_imsi, timestamp, ue_profile, label] + [features[c] for c in FEATURE_COLS])


def xlayer(rrc_record: dict, n2_record: dict) -> dict:
    """the project's testbed architecture notes §7.2 cross-layer consistency features: RRC is the
    untampered reference (captured at the gNodeB), N2 is the observation (what
    reached the AMF). Both records must be the shape _capability_record_from_bytes()
    returns (ue_category, ca_supported, ca_band_count, mimo_layers_dl,
    mimo_layers_ul, vonr_supported, nr_band_count, capability_size_bytes,
    ie_field_count, container_bytes).

    2026-07-31 fix: capability_size_delta/container_hash_match compare raw
    container_bytes, which is only a meaningful comparison when both sides are
    the same kind of byte representation. rrc_capture.py's records carry a
    byte_exact flag (True for its case-(b) cached-capability path, which
    decodes real PER bytes; False for case (a), where container_bytes is a
    JSON-text fallback with no raw PER bytes available - the common case,
    per the project's internal build log's Build 0d notes: "Only case (a) fires on a first-ever
    attach"). Comparing a JSON-text byte string against the N2 side's real PER
    bytes is comparing two different encodings of potentially the same
    content, not detecting manipulation - proven empirically
    (features/test_xlayer_cross_layer_validity.py) to show
    container_hash_match=False and a capability_size_delta in the tens of
    thousands even for a byte-for-byte-irrelevant, semantically perfect
    match. When rrc_record.get("byte_exact", True) is False, both fields are
    now None instead of a numerically-plausible-looking but meaningless value -
    a caller that doesn't check for None before feeding these into a
    RandomForestClassifier/SHAP pipeline will get a loud, immediate error
    instead of silently training on noise. Defaults to True (byte comparison
    valid) when the key is absent, matching every N2-side record produced by
    _capability_record_from_bytes(), which is always real PER bytes and never
    sets this key at all."""
    compared_fields = [
        "ue_category",
        "ca_supported",
        "ca_band_count",
        "mimo_layers_dl",
        "mimo_layers_ul",
        "vonr_supported",
        "nr_band_count",
    ]
    num_fields_mismatched = sum(1 for f in compared_fields if rrc_record[f] != n2_record[f])

    byte_comparison_valid = rrc_record.get("byte_exact", True)
    if byte_comparison_valid:
        capability_size_delta = n2_record["capability_size_bytes"] - rrc_record["capability_size_bytes"]
        rrc_hash = hashlib.sha256(rrc_record["container_bytes"]).hexdigest()
        n2_hash = hashlib.sha256(n2_record["container_bytes"]).hexdigest()
        container_hash_match = rrc_hash == n2_hash
    else:
        capability_size_delta = None
        container_hash_match = None

    return {
        "ue_category_delta": n2_record["ue_category"] - rrc_record["ue_category"],
        "ca_supported_match": rrc_record["ca_supported"] == n2_record["ca_supported"],
        "ca_band_count_delta": n2_record["ca_band_count"] - rrc_record["ca_band_count"],
        "mimo_dl_delta": n2_record["mimo_layers_dl"] - rrc_record["mimo_layers_dl"],
        "mimo_ul_delta": n2_record["mimo_layers_ul"] - rrc_record["mimo_layers_ul"],
        "vonr_supported_match": rrc_record["vonr_supported"] == n2_record["vonr_supported"],
        "nr_band_count_delta": n2_record["nr_band_count"] - rrc_record["nr_band_count"],
        "capability_size_delta": capability_size_delta,
        "ie_field_count_delta": n2_record["ie_field_count"] - rrc_record["ie_field_count"],
        "num_fields_mismatched": num_fields_mismatched,
        "container_hash_match": container_hash_match,
    }


def _selftest_extract() -> None:
    pcap = str(Path(__file__).resolve().parent.parent / "data/raw/exhibits/ngap_label0_full.pcap")
    rows = extract(pcap)
    assert rows, f"no UERadioCapabilityInfoIndication events found in {pcap}"
    for i, row in enumerate(rows):
        assert list(row.keys()) == FEATURE_COLS
        write_csv_row(
            "/tmp/extract_features_selftest.csv",
            session_id="build0a-baseline",
            ue_imsi="0006",
            timestamp=f"2026-07-30T00:05:{30+i}Z",
            ue_profile="SW-Std",
            label=0,
            features=row,
        )
    print(f"extract() selftest: {len(rows)} event(s) parsed from {pcap}")
    for row in rows:
        print(row)


def _selftest_xlayer() -> None:
    base = {
        "ue_category": 15,
        "ca_supported": True,
        "ca_band_count": 2,
        "mimo_layers_dl": 2,
        "mimo_layers_ul": 1,
        "vonr_supported": True,
        "nr_band_count": 1,
        "capability_size_bytes": 34,
        "ie_field_count": 4,
        "container_bytes": b"\x01\x02\x03\x04",
    }
    rrc = dict(base)
    n2 = dict(base)
    n2["vonr_supported"] = False  # simulate label 4: VoNR-denied on the N2 leg
    n2["container_bytes"] = b"\x01\x02\x03\x99"

    result = xlayer(rrc, n2)
    assert result["vonr_supported_match"] is False
    assert result["num_fields_mismatched"] == 1
    assert result["container_hash_match"] is False
    for field in ("ue_category_delta", "ca_supported_match", "ca_band_count_delta", "mimo_dl_delta", "mimo_ul_delta", "nr_band_count_delta", "capability_size_delta", "ie_field_count_delta"):
        assert result[field] in (0, True), f"unexpected divergence flagged in unmodified field {field}: {result[field]}"

    print("xlayer() selftest: divergent field (vonr_supported) correctly isolated, all matching fields correctly zero/True")
    print(result)


if __name__ == "__main__":
    _selftest_extract()
    print()
    _selftest_xlayer()
