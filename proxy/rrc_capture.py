#!/usr/bin/env python3
"""RRC UE capability capture at the gNodeB, real handsets only (the project's testbed architecture notes
§6.1/§7.1, Build 0d).

Feasibility (spike, 2026-07-30): srsRAN Project's rrc_ue_impl::store_ue_capabilities()
(lib/rrc/ue/rrc_ue_message_handlers.cpp) JSON-dumps the decoded UE-NR-Capability RRC
container per UE via `logger.log_debug(...)` whenever the RRC logger channel is at
debug level (`log.rrc_level: debug` in gnb.yml - not the default, which is
`all_level: info`). No srsRAN source patch is needed. Confirmed live: a real handset's
"UE Capabilities:" JSON block appears in gnb.log within ~150 microseconds of the
matching NGAP Tx `UERadioCapabilityInfoIndication` for the same `ue=` index, giving a
reliable join key. The JSON uses the same hyphenated ASN.1 field names
(`rf-Parameters`, `featureSets`, `ims-Parameters`, ...) as pycrate's get_val() output,
so `proxy/ngap_decode.summarize_capability()` and `features/extract_features.py`'s
encoding helpers are reused as-is rather than re-implemented here.

Caveat: this is a JSON dump, not the raw PER-encoded UE-NR-Capability octets (srsRAN
has no RRC pcap option). The resulting record's `capability_size_bytes`,
`ie_field_count` and `container_bytes` are therefore JSON-based, not byte-identical to
the PER-encoded N2-side record `extract_features._capability_record_from_bytes()`
produces - `capability_size_delta` and `container_hash_match` in
`extract_features.xlayer()` are not meaningful for RRC-vs-N2 comparisons built from
this capture path. The five semantic fields (ue_category, ca_supported,
ca_band_count, mimo_layers_dl/ul, vonr_supported, nr_band_count) and
`num_fields_mismatched` are meaningful - they come from the same
summarize_capability() logic on both sides.

Real handsets only: for UERANSIM UEs the Stage 1 proxy rewrite is itself an N2
change, so the RRC reference captured here would not be independent of the
attacker (the project's testbed architecture notes §6.1). Nothing in this script distinguishes
device type - that is an operator/session decision, same convention as
`ngap_proxy.py --profile` being left unset for real-handset sessions.

Usage:
    rrc_capture.py --label 0 --session-id <sid> [--profile a56] [--gnb-log /tmp/gnb.log]
                    [--amf-log /tmp/amf.log] [--output-dir data/raw/rrc] [--follow]
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
from extract_features import _encode_ue_category, _mimo_layers_to_int  # noqa: E402

RRC_HEADER_RE = re.compile(
    r"^(?P<ts>\S+) \[RRC\s*\] \[D\] ue=(?P<ue>\d+) c-rnti=(?P<crnti>0x[0-9a-fA-F]+): UE Capabilities:$"
)
NGAP_TX_RE = re.compile(
    r"^(?P<ts>\S+) \[NGAP\s*\] \[I\] Tx PDU ue=(?P<ue>\d+) ran_ue=(?P<ran_ue>\d+): UERadioCapabilityInfoIndication$"
)
# Fallback join anchor for case (b): a genuine cached-capability reattach (NAS
# Service Request reusing the AMF's stored UE radio capability) never triggers
# a fresh UERadioCapabilityInfoIndication - confirmed live 2026-07-31 (real
# Realme/imsi-...0004 reattach, ran_ue=15: RRC "UE Capabilities:" wrapper
# present, no UERadioCapabilityInfoIndication anywhere in that ue's NGAP
# transcript). InitialContextSetupResponse is sent by the gNB immediately
# after processing the (possibly cached) capability in both case (a) and (b),
# so it is used only when NGAP_TX_RE finds nothing for the same ue index.
ICS_RESPONSE_RE = re.compile(
    r"^(?P<ts>\S+) \[NGAP\s*\] \[I\] Tx PDU ue=(?P<ue>\d+) ran_ue=(?P<ran_ue>\d+) amf_ue=\d+: InitialContextSetupResponse$"
)
UE_CONTEXT_RE = re.compile(r"ue=(?P<ue>\d+) ran_ue=(?P<ran_ue>\d+) amf_ue=(?P<amf_ue>\d+)")
AMF_IMSI_RE = re.compile(r"imsi-(?P<imsi>\d{15})")
AMF_TS_RE = re.compile(r"^(?P<ts>\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d+):")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _capability_dict_and_bytes(capability_json: dict):
    """srsRAN's debug log prints UE Capabilities in one of two shapes, depending on
    which code path decoded them (found live, not documented by srsRAN):

    (a) rrc_ue_capability_transfer_procedure.cpp - fresh, over-the-air RRC
        UECapabilityEnquiry/UECapabilityInformation exchange. Logs the fully
        decoded UE-NR-Capability fields directly (accessStratumRelease, ...).
        No raw PER bytes available from the log in this case.
    (b) rrc_ue_message_handlers.cpp store_ue_capabilities() - a capability the
        AMF handed back to the gNB in InitialContextSetupRequest (its own
        earlier-cached copy, e.g. on a GUTI reattach where no fresh RRC
        enquiry is needed). Logs only the UE-CapabilityRAT-Container wrapper:
        {"rat-Type": "nr", "ue-CapabilityRAT-Container": "<hex PER bytes>"}.
        This *does* carry the raw PER-encoded UE-NR-Capability octets, which
        this function decodes with ngap_decode's own layer-4 codec
        (ngap_decode._l4) - the exact same codec extract_features.py uses on
        the N2 side - giving a byte-identical container_bytes/record, not an
        approximation.

    Returns (capability_dict, raw_bytes_or_None).
    """
    if "ue-CapabilityRAT-Container" in capability_json and "accessStratumRelease" not in capability_json:
        raw = bytes.fromhex(capability_json["ue-CapabilityRAT-Container"])
        with ngap_decode._lock:
            ngap_decode._l4.from_uper(raw)
            capability = ngap_decode._l4.get_val()
        return capability, raw
    return capability_json, None


def capability_record_from_rrc_json(capability_json: dict) -> dict:
    """Same record shape as extract_features._capability_record_from_bytes(), built
    from the gNB's RRC debug-log capture. byte_exact indicates whether
    container_bytes/capability_size_bytes are the real PER octets (case (b)
    above) or a JSON-based stand-in (case (a) - see module docstring caveat)."""
    capability, raw_bytes = _capability_dict_and_bytes(capability_json)
    summary = ngap_decode.summarize_capability(capability)
    rf_params = capability.get("rf-Parameters", {}) or {}
    ca_band_count = len(rf_params.get("supportedBandCombinationList", []) or [])
    byte_exact = raw_bytes is not None
    container_bytes = raw_bytes if byte_exact else json.dumps(capability, sort_keys=True).encode()

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
        "byte_exact": byte_exact,
    }


def _local_utc_offset():
    return datetime.now().astimezone().utcoffset()


def _gnb_ts_to_utc(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _amf_ts_to_utc(ts: str, today_utc: datetime, offset) -> Optional[datetime]:
    try:
        naive = datetime.strptime(f"{today_utc.year}/{ts}", "%Y/%m/%d %H:%M:%S.%f")
        return (naive - offset).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def find_imsi_near(amf_log_path: Path, target_utc: datetime, window_s: float = 30.0) -> Optional[str]:
    """Best-effort: nearest imsi-<...> line in amf.log within window_s of target_utc.
    amf.log timestamps are local (no year); gnb.log timestamps are naive UTC - the
    offset is resolved from the current system timezone (NZST/NZDT on this box)."""
    if not amf_log_path.exists():
        return None
    offset = _local_utc_offset()
    best = None
    best_delta = None
    try:
        text = amf_log_path.read_text(errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        line = ANSI_RE.sub("", line)
        m_imsi = AMF_IMSI_RE.search(line)
        m_ts = AMF_TS_RE.match(line)
        if not (m_imsi and m_ts):
            continue
        ts = _amf_ts_to_utc(m_ts.group("ts"), target_utc, offset)
        if ts is None:
            continue
        delta = abs((ts - target_utc).total_seconds())
        if delta <= window_s and (best_delta is None or delta < best_delta):
            best, best_delta = m_imsi.group("imsi"), delta
    return best


def parse_gnb_log(text: str) -> list:
    """Return a list of dicts, one per RRC 'UE Capabilities' block that has a
    matching NGAP Tx UERadioCapabilityInfoIndication for the same ue= index."""
    lines = text.splitlines()
    events = []
    i = 0
    n = len(lines)
    while i < n:
        m = RRC_HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        ue_idx = m.group("ue")
        rrc_ts = m.group("ts")
        crnti = m.group("crnti")

        # Collect the pretty-printed JSON block that follows. srslog gives the
        # "UE Capabilities:" header and the JSON dump as two separate log_debug()
        # calls (rrc_ue_message_handlers.cpp:524), so there is sometimes a blank
        # line between them, and the opening "{" line can itself carry its own
        # timestamp+channel prefix (store_ue_capabilities() path) rather than
        # being bare (rrc_ue_capability_transfer_procedure.cpp path) - handle
        # both by keeping only the trailing "{" of whichever line opens the block.
        j = i + 1
        while j < n and lines[j].strip() == "":
            j += 1
        if j >= n or not lines[j].rstrip().endswith("{"):
            i += 1
            continue
        depth = 0
        block_lines = ["{"]
        for ch in block_lines[0]:
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
        j += 1
        while j < n and depth != 0:
            line = lines[j]
            block_lines.append(line)
            for ch in line:
                if ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
            j += 1
        try:
            capability_json = json.loads("\n".join(block_lines))
        except json.JSONDecodeError:
            i = j
            continue

        # Find the matching NGAP Tx line for the same ue index, within the next
        # few hundred lines (InitialContextSetupResponse -> UERadioCapabilityInfoIndication
        # follow immediately after the RRC capability dump in the observed trace).
        # Case (b) never sends UERadioCapabilityInfoIndication (nothing new to
        # report to the AMF - confirmed live, see ICS_RESPONSE_RE), so fall back
        # to the InitialContextSetupResponse Tx line, present in both cases.
        ran_ue = None
        ngap_ts = None
        amf_ue = None
        join_source = None
        for k in range(j, min(j + 500, n)):
            mt = NGAP_TX_RE.match(lines[k])
            if mt and mt.group("ue") == ue_idx:
                ran_ue = mt.group("ran_ue")
                ngap_ts = mt.group("ts")
                join_source = "UERadioCapabilityInfoIndication"
                break
        if ran_ue is None:
            for k in range(j, min(j + 500, n)):
                mi = ICS_RESPONSE_RE.match(lines[k])
                if mi and mi.group("ue") == ue_idx:
                    ran_ue = mi.group("ran_ue")
                    ngap_ts = mi.group("ts")
                    join_source = "InitialContextSetupResponse"
                    break
        # amf_ue (for IMSI lookup) - search a wider window around the header for a
        # "ue=N ran_ue=M amf_ue=K" co-occurrence.
        for k in range(max(0, i - 200), min(i + 500, n)):
            mc = UE_CONTEXT_RE.search(lines[k])
            if mc and mc.group("ue") == ue_idx and (ran_ue is None or mc.group("ran_ue") == ran_ue):
                amf_ue = mc.group("amf_ue")
                break

        if ran_ue is not None:
            events.append(
                {
                    "gnb_ue_index": int(ue_idx),
                    "c_rnti": crnti,
                    "ran_ue_ngap_id": int(ran_ue),
                    "amf_ue_ngap_id": int(amf_ue) if amf_ue is not None else None,
                    "rrc_timestamp": rrc_ts,
                    "ngap_tx_timestamp": ngap_ts,
                    "join_source": join_source,
                    "capability_json": capability_json,
                }
            )
        i = j
    return events


def update_reference(reference_dir: Path, imsi: str, out: dict) -> Optional[Path]:
    """Persist the last known-good (case-a, byte_exact=False) RRC capability per
    IMSI, so a later reattach's N2-side capability can be checked against a
    genuinely independent, untampered reference even when that reattach is
    itself a cached case-(b) event with nothing fresh to compare against.

    2026-07-31 finding: a cached reattach's own RRC "echo" is sourced from the
    AMF's N2-delivered cache (try_rewrite only fires gnb->amf; the amf->gnb leg
    carrying a cached capability back to the gNB is only decode/reencode'd, never
    re-attacked) - so if the ORIGINAL registration that populated the cache was
    itself attacked, comparing that reattach's RRC echo against its own
    originating N2 record always matches (both are the same already-attacked
    bytes), silently missing the attack. Case (a) is the only point in the
    protocol where the RRC side is independently sourced from a live UE
    exchange, uncorrelated with whatever the AMF/proxy did on N2 - so only case
    (a) (byte_exact=False) is eligible to become this reference. Confirmed live:
    pairing a much-earlier clean case-a reference for imsi-...0004 against a
    label-1-attacked N2 record from a later registration correctly shows
    ue_category diverging, where pairing the same reattach's own case-b echo
    against its originating registration did not (see
    features/test_xlayer_cross_layer_validity.py)."""
    if imsi is None or out["record"].get("byte_exact") is not False:
        return None
    reference_dir.mkdir(parents=True, exist_ok=True)
    path = reference_dir / f"{imsi}.json"
    path.write_text(json.dumps(out, indent=2))
    return path


def write_record(
    output_dir: Path,
    label: int,
    profile: str,
    session_id: str,
    event_idx: int,
    event: dict,
    imsi: Optional[str],
    reference_dir: Optional[Path] = None,
) -> Path:
    record = capability_record_from_rrc_json(event["capability_json"])
    record["container_bytes"] = record["container_bytes"].hex()  # JSON-serialisable

    out = {
        "label": label,
        "profile": profile,
        "session_id": session_id,
        "event": event_idx,
        "ran_ue_ngap_id": event["ran_ue_ngap_id"],
        "amf_ue_ngap_id": event["amf_ue_ngap_id"],
        "gnb_ue_index": event["gnb_ue_index"],
        "c_rnti": event["c_rnti"],
        "rrc_timestamp_utc": event["rrc_timestamp"],
        "ngap_tx_timestamp_utc": event["ngap_tx_timestamp"],
        "join_source": event.get("join_source"),
        "imsi": imsi,
        "record": record,
        "raw_rrc_capability": event["capability_json"],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"rrc_{label}_{profile}_{session_id}_{event_idx}.json"
    path.write_text(json.dumps(out, indent=2))

    if reference_dir is not None:
        update_reference(reference_dir, imsi, out)

    return path


def run_once(
    gnb_log: Path,
    amf_log: Path,
    output_dir: Path,
    label: int,
    profile: str,
    session_id: str,
    start_event: int,
    seen: set,
    reference_dir: Optional[Path] = None,
) -> int:
    text = gnb_log.read_text(errors="replace")
    events = parse_gnb_log(text)
    event_idx = start_event
    written = 0
    for event in events:
        key = (event["ran_ue_ngap_id"], event["ngap_tx_timestamp"])
        if key in seen:
            continue
        seen.add(key)
        target_utc = _gnb_ts_to_utc(event["ngap_tx_timestamp"] or event["rrc_timestamp"])
        imsi = find_imsi_near(amf_log, target_utc) if target_utc else None
        path = write_record(output_dir, label, profile, session_id, event_idx, event, imsi, reference_dir)
        print(f"wrote {path} (ran_ue={event['ran_ue_ngap_id']} imsi={imsi})")
        event_idx += 1
        written += 1
    return event_idx


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", type=int, required=True, choices=range(0, 7), help="Attack label active on the proxy during this capture (0-6)")
    p.add_argument("--session-id", required=True, help="Collection-campaign session identifier")
    p.add_argument("--profile", default="handset", help="Real-handset identifier (e.g. a56, pixel8) - default 'handset'")
    p.add_argument("--gnb-log", default="/tmp/gnb.log")
    p.add_argument("--amf-log", default="/tmp/amf.log")
    p.add_argument("--output-dir", default=str(Path(__file__).resolve().parent.parent / "data/raw/rrc"))
    p.add_argument(
        "--reference-dir",
        default=str(Path(__file__).resolve().parent.parent / "data/raw/rrc/reference"),
        help=(
            "Per-IMSI last known-good (case-a, byte_exact=False) RRC capability, updated on every "
            "genuine fresh RRC exchange - lets a later cached reattach's N2-side capability be "
            "checked against a real untampered reference instead of only the same registration's "
            "own (possibly already-attacked) echo. Pass empty string to disable."
        ),
    )
    p.add_argument("--follow", action="store_true", help="Keep polling gnb.log for new events instead of processing once and exiting")
    p.add_argument("--poll-interval", type=float, default=2.0)
    args = p.parse_args()

    gnb_log = Path(args.gnb_log)
    amf_log = Path(args.amf_log)
    output_dir = Path(args.output_dir)
    reference_dir = Path(args.reference_dir) if args.reference_dir else None

    seen = set()
    event_idx = 0
    event_idx = run_once(gnb_log, amf_log, output_dir, args.label, args.profile, args.session_id, event_idx, seen, reference_dir)

    if args.follow:
        print("following gnb.log for new RRC capability events (Ctrl-C to stop)...", file=sys.stderr)
        try:
            while True:
                time.sleep(args.poll_interval)
                event_idx = run_once(gnb_log, amf_log, output_dir, args.label, args.profile, args.session_id, event_idx, seen, reference_dir)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
