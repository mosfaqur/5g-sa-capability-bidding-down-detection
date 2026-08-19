#!/usr/bin/env python3
"""NGAP proxy for the N2 interface (gNodeB <-> Open5GS AMF).

Build order (the project's testbed architecture notes §6.2, Project_Setup_Plan.md Part 3.4 §0a):
    1. Transparent SCTP relay                       <- implemented, this file
    2. Decode-only (pycrate NGAP + RRC schemas)      <- implemented, this file (ngap_decode.py)
    3. Identity re-encode                            <- implemented, this file (ngap_decode.py)
    4. Stage 1 profile-baseline rewrite (UERANSIM)   <- implemented, this file (ngap_decode.py)
    5. Stage 2 attack modifiers (labels 1-6)         <- implemented, this file (ngap_decode.py)
    6. Instrumentation (latency + event log)         <- partially implemented (relay-level)

Step 2 (--stage decode) decodes every gNB->AMF message with pycrate to detect
UERadioCapabilityInfoIndication and unwraps the nested RRC-NR capability
container (see ngap_decode.py for the real 4-layer nesting, deeper than the
architecture doc's "second decode pass" phrasing). Decoding is diagnostic
only: the raw bytes are still forwarded completely unmodified regardless of
whether decode succeeds, so a decode bug cannot break the live session.

Step 3 (--stage reencode) decodes+re-encodes *every* NGAP message in *both*
directions before forwarding (not just UERadioCapabilityInfoIndication) -
this stresses the codec far harder than Step 2 and is the real test that
Stage 1/2 field modification (Steps 4-5) will be safe to build on. Per-message
fallback to the original raw bytes on any codec failure means a single bad
PDU degrades to Step-1 behaviour for that message instead of breaking the
association.

Step 4 (--stage rewrite --profile {sw-min,sw-std,sw-ext}) applies everywhere Step 3
does (decode+re-encode all traffic, same fallback safety), and additionally
substitutes the UERadioCapability IE content of any UERadioCapabilityInfoIndication
with the target profile's fixed fingerprint (the project's testbed architecture notes §6.2/§6.3).
UERANSIM's native capability (patched into UERANSIM to exist at all - see
ueransim/src/*/rrc/capability.cpp) is discarded entirely rather than field-patched,
since it lacks the CA/MIMO/VoNR substructures the target profiles need. Real
handsets are never run with --profile set; the rewrite only applies when a profile
is selected via CLI flag, per §6.2's "real handsets skip Stage 1 entirely."

Step 5 (--stage rewrite --label {1-6}, the project's testbed architecture notes §6.3) applies a
Stage 2 attack modifier on top of the Stage 1 baseline (--profile, UERANSIM) or
the UE's own native capability (--profile unset, real handsets - Stage 1 is
skipped but Stage 2 still applies). Label 0 (the default) is Normal: the
baseline forwards unchanged. Label 6 uses a module-level RNG seeded with
random_state=42 (ngap_decode.py) so the probabilistic bit-flip sequence is
reproducible across a whole data-collection run.

Each step must be validated against a live registration before the next is built
(see the project's internal build log / Project_Setup_Plan.md Part 3.4 §0a).

Topology:
    srsRAN/UERANSIM gNB --SCTP:38412--> [this proxy] --SCTP:38413--> Open5GS AMF

The AMF's ngap.server port was moved to 38413 in
/usr/local/etc/open5gs/amf.yaml so this proxy can bind the standard port
38412 that the gNB config (cu_cp.amf.port) already points at, with zero
gNB-side reconfiguration.

Fallback (the project's testbed architecture notes §6.2): if SCTP interception proves
unreliable (timing-sensitive association setup, kernel SCTP quirks, etc.),
the alternative is to modify srsRAN Project source directly at
lib/ngap/ or lib/cu_cp/ue_manager/ue_task_scheduler.cpp, where the
UERadioCapabilityInfoIndication encoder can be intercepted before it hits
the wire. That path avoids SCTP-in-the-middle entirely but requires
patching and rebuilding srsRAN for every change, so it is the fallback,
not the primary implementation.
"""
import argparse
import logging
import socket
import sys
import threading
import time
from pathlib import Path

import sctp

import ngap_decode

NGAP_PPID = 60  # 3GPP TS 38.412 payload protocol identifier for NGAP over SCTP
RECV_MAXLEN = 65536

LOG = logging.getLogger("ngap_proxy")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--listen-addr", default="127.0.0.5", help="Address the proxy binds for the gNB (default: 127.0.0.5)")
    p.add_argument("--listen-port", type=int, default=38412, help="Port the proxy binds for the gNB (default: 38412, the standard N2 port)")
    p.add_argument("--amf-addr", default="127.0.0.5", help="Real AMF address to forward to (default: 127.0.0.5)")
    p.add_argument("--amf-port", type=int, default=38413, help="Real AMF port to forward to (default: 38413, shifted off standard)")
    p.add_argument(
        "--stage",
        choices=["relay", "decode", "reencode", "rewrite"],
        default="relay",
        help="Pipeline stage to run. 'relay' (Step 1) forwards silently; "
        "'decode' (Step 2) additionally decodes and logs UERadioCapabilityInfoIndication "
        "contents but still forwards raw bytes unmodified; 'reencode' (Step 3) decodes and "
        "re-encodes every message in both directions before forwarding (falls back to the "
        "original raw bytes per-message if decode/encode fails); 'rewrite' (Step 4) additionally "
        "substitutes the capability content per --profile (UERANSIM sessions only).",
    )
    p.add_argument(
        "--profile",
        choices=["sw-min", "sw-std", "sw-ext"],
        default=None,
        help="UERANSIM profile fingerprint to rewrite UERadioCapabilityInfoIndication to when "
        "--stage rewrite is active. Leave unset for real-handset sessions (Stage 1 skipped "
        "entirely per the project's testbed architecture notes §6.2).",
    )
    p.add_argument(
        "--label",
        type=int,
        choices=range(0, 7),
        default=0,
        help="Stage 2 attack label (0-6, the project's testbed architecture notes §6.3) applied on top of the "
        "Stage 1 baseline (--profile) or the native handset capability (--profile unset). "
        "0 = Normal (baseline forwarded unchanged, the default).",
    )
    p.add_argument(
        "--event-log",
        default="/root/comp997/logs/ngap_proxy_events.log",
        help="Line-oriented event log for per-message latency/metadata (Step 6 instrumentation).",
    )
    return p


def setup_logging(event_log_path: str) -> logging.Logger:
    Path(event_log_path).parent.mkdir(parents=True, exist_ok=True)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    events = logging.FileHandler(event_log_path)
    events.setFormatter(logging.Formatter("%(message)s"))
    events.addFilter(lambda record: getattr(record, "is_event", False))

    logger = logging.getLogger("ngap_proxy")
    logger.setLevel(logging.INFO)
    logger.addHandler(console)
    logger.addHandler(events)
    return logger


def log_event(direction: str, nbytes: int, stream: int, latency_ms: float, profile: str = None, label: int = 0) -> None:
    """Step 6 instrumentation: one line per relayed SCTP message.

    Format is line-oriented (not CSV/JSON) so it can be tailed live during a
    data-collection session. profile/label are always included (None/0 for
    relay/decode/reencode stages, where they aren't meaningful) so a session's
    events log is self-describing without needing to cross-reference which CLI
    invocation was running at a given timestamp - fixed 2026-07-31, this
    function's own comment had promised these fields "once implemented" since
    before Steps 4-5 (Stage 1/2 rewrite) existed, and was never updated once
    they shipped.
    """
    LOG.info(
        "event=relay direction=%s bytes=%d stream=%d latency_ms=%.3f profile=%s label=%d",
        direction,
        nbytes,
        stream,
        latency_ms,
        profile,
        label,
        extra={"is_event": True},
    )


def log_capability_event(summary: dict, profile: str = None, label: int = 0) -> None:
    """Step 6 instrumentation line for a decoded UERadioCapabilityInfoIndication (Step 2).
    profile/label added 2026-07-31, same reasoning as log_event()."""
    LOG.info(
        "event=capability access_stratum_release=%s band_count=%d band_ids=%s "
        "ca_supported=%s mimo_dl_layers=%s mimo_ul_layers=%s vonr_supported=%s profile=%s label=%d",
        summary["access_stratum_release"],
        summary["band_count"],
        summary["band_ids"],
        summary["ca_supported"],
        summary["mimo_dl_layers"],
        summary["mimo_ul_layers"],
        summary["vonr_supported"],
        profile,
        label,
        extra={"is_event": True},
    )


def try_decode_capability(msg: bytes, profile: str = None, label: int = 0) -> None:
    """Best-effort decode for Step 2 diagnostics. Never raises - a decode bug must not
    affect the relay, since the raw bytes are forwarded regardless of this outcome."""
    try:
        pdu_val = ngap_decode.decode_ngap_pdu(msg)
        if pdu_val is None:
            return
        if ngap_decode.get_procedure_code(pdu_val) != ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION:
            return
        LOG.info("decoded UERadioCapabilityInfoIndication (procedureCode=44)")
        cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
        if cap_bytes is None:
            LOG.warning("UERadioCapabilityInfoIndication had no IE 117 (id-UERadioCapability)")
            return
        decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
        if decoded is None:
            LOG.warning("could not unwrap RRC-NR capability container (%d bytes)", len(cap_bytes))
            return
        summary = ngap_decode.summarize_capability(decoded["capability"])
        LOG.info("capability summary: %s", summary)
        log_capability_event(summary, profile, label)
    except Exception:
        LOG.exception("decode stage: unexpected error (raw bytes still forwarded unmodified)")


def try_reencode(msg: bytes, direction: str) -> bytes:
    """Step 3: decode+re-encode msg with pycrate; fall back to the original raw bytes
    unmodified if either step fails, so a codec bug degrades to Step-1 relay behaviour
    for that one message rather than corrupting or dropping it."""
    reencoded = ngap_decode.decode_and_reencode_ngap_pdu(msg)
    if reencoded is None:
        LOG.warning("%s: decode/re-encode failed, forwarding original %d raw bytes", direction, len(msg))
        return msg
    if reencoded != msg:
        LOG.info(
            "%s: re-encoded bytes differ from original (orig=%d bytes, reencoded=%d bytes) - "
            "not necessarily a bug (APER is not always canonical), forwarding re-encoded bytes",
            direction,
            len(msg),
            len(reencoded),
        )
    return reencoded


def try_rewrite(msg: bytes, direction: str, profile: str, label: int) -> bytes:
    """Steps 4+5: on gNB->AMF UERadioCapabilityInfoIndication messages, substitute
    the capability content with --profile's Stage 1 baseline (or the native
    handset capability if --profile is unset) and apply the --label Stage 2
    modifier on top (label 0 = no-op). Anything else (other message types, the
    AMF->gNB direction, or a rewrite failure) falls through to the Step-3 plain
    re-encode path - capability messages only ever flow gNB->AMF, so there is
    nothing to rewrite in the other direction."""
    if direction == "gnb->amf":
        rewritten = ngap_decode.apply_capability_pipeline(msg, profile, label)
        if rewritten is not None:
            LOG.info(
                "%s: rewrote UERadioCapabilityInfoIndication profile=%s label=%d (%d -> %d bytes)",
                direction,
                profile,
                label,
                len(msg),
                len(rewritten),
            )
            pdu_val = ngap_decode.decode_ngap_pdu(rewritten)
            cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
            decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
            if decoded is not None:
                log_capability_event(ngap_decode.summarize_capability(decoded["capability"]), profile, label)
            return rewritten
    return try_reencode(msg, direction)


MAX_OSTREAMS = 32  # offer generously on both legs to reduce (not eliminate) stream-count mismatch


def make_sctp_socket() -> sctp.sctpsocket_tcp:
    sk = sctp.sctpsocket_tcp(socket.AF_INET)
    sk.events.data_io = True  # populate sndrcvinfo (stream id) on recv
    sk.initparams.num_ostreams = MAX_OSTREAMS
    sk.initparams.max_instreams = MAX_OSTREAMS
    return sk


def relay(
    src: sctp.sctpsocket_tcp,
    dst: sctp.sctpsocket_tcp,
    direction: str,
    stage: str = "relay",
    profile: str = None,
    label: int = 0,
) -> None:
    """Forward SCTP messages from src to dst, preserving stream id and NGAP PPID.

    stage == 'relay': forward raw bytes unmodified (Step 1).
    stage == 'decode': also decode+log UERadioCapabilityInfoIndication (gNB->AMF
        only, since that IE only ever flows that direction), still forward raw
        bytes unmodified (Step 2).
    stage == 'reencode': decode+log as above, then decode+re-encode every message
        in both directions before forwarding, falling back to the original raw
        bytes per-message on any codec failure (Step 3).
    stage == 'rewrite': decode+log as above, then substitute the capability content
        with --profile's Stage 1 baseline (or the native handset capability if
        --profile is unset) and apply the --label Stage 2 modifier on top, on
        UERadioCapabilityInfoIndication (gNB->AMF only); decode+re-encode
        everything else as in Step 3 (Steps 4+5).
    """
    try:
        while True:
            fromaddr, flags, msg, notif = src.sctp_recv(RECV_MAXLEN)
            t_arrival = time.monotonic()  # start the clock only once the message has actually arrived

            if not msg:
                if flags & sctp.FLAG_NOTIFICATION:
                    continue  # association-level event (e.g. peer address change) - nothing to relay
                LOG.info("%s: peer closed association", direction)
                break

            if stage in ("decode", "reencode", "rewrite") and direction == "gnb->amf":
                try_decode_capability(msg, profile, label)

            if stage == "rewrite":
                out_msg = try_rewrite(msg, direction, profile, label)
            elif stage == "reencode":
                out_msg = try_reencode(msg, direction)
            else:
                out_msg = msg

            stream = getattr(notif, "stream", 0) if notif is not None else 0
            # The two associations (gNB<->proxy, proxy<->AMF) negotiate their outbound
            # stream counts independently, so a stream id valid on src can be out of
            # range on dst (observed live: sctp_send raised EINVAL and dropped the
            # association). Clamp to what dst actually negotiated.
            max_stream = max(dst.get_status().outstrms - 1, 0)
            if stream > max_stream:
                LOG.warning("%s: clamping stream %d to dst max %d", direction, stream, max_stream)
                stream = max_stream
            dst.sctp_send(out_msg, ppid=NGAP_PPID, stream=stream)

            latency_ms = (time.monotonic() - t_arrival) * 1000.0
            log_event(direction, len(out_msg), stream, latency_ms, profile, label)
    except (OSError, ConnectionError) as exc:
        LOG.info("%s: relay stopped (%s)", direction, exc)
    finally:
        try:
            dst.close()
        except OSError:
            pass
        try:
            src.close()
        except OSError:
            pass


def handle_association(
    gnb_sock: sctp.sctpsocket_tcp, amf_addr: str, amf_port: int, stage: str, profile: str = None, label: int = 0
) -> None:
    LOG.info("accepted gNB association, connecting to AMF %s:%d", amf_addr, amf_port)
    amf_sock = make_sctp_socket()
    try:
        amf_sock.connect((amf_addr, amf_port))
    except OSError as exc:
        LOG.error("failed to connect to AMF %s:%d: %s", amf_addr, amf_port, exc)
        gnb_sock.close()
        return
    LOG.info("connected to AMF, relaying both directions")

    t_gnb_to_amf = threading.Thread(
        target=relay, args=(gnb_sock, amf_sock, "gnb->amf", stage, profile, label), daemon=True
    )
    t_amf_to_gnb = threading.Thread(
        target=relay, args=(amf_sock, gnb_sock, "amf->gnb", stage, profile, label), daemon=True
    )
    t_gnb_to_amf.start()
    t_amf_to_gnb.start()
    t_gnb_to_amf.join()
    t_amf_to_gnb.join()
    LOG.info("association closed")


def run_relay(
    listen_addr: str,
    listen_port: int,
    amf_addr: str,
    amf_port: int,
    stage: str = "relay",
    profile: str = None,
    label: int = 0,
) -> None:
    listener = make_sctp_socket()
    listener.bind((listen_addr, listen_port))
    listener.listen(5)
    LOG.info("listening on %s:%d, forwarding to AMF %s:%d", listen_addr, listen_port, amf_addr, amf_port)

    while True:
        gnb_sock, _ = listener.accept()
        gnb_sock.events.data_io = True
        threading.Thread(
            target=handle_association,
            args=(gnb_sock, amf_addr, amf_port, stage, profile, label),
            daemon=True,
        ).start()


def main() -> None:
    args = build_arg_parser().parse_args()
    global LOG
    LOG = setup_logging(args.event_log)

    try:
        run_relay(
            args.listen_addr,
            args.listen_port,
            args.amf_addr,
            args.amf_port,
            stage=args.stage,
            profile=args.profile,
            label=args.label,
        )
    except KeyboardInterrupt:
        LOG.info("shutting down")


if __name__ == "__main__":
    main()
