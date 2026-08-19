#!/usr/bin/env python3
"""Standalone smoke test for ngap_proxy.py itself.

proxy/test_relay_smoke.py (pre-existing) already covers the transparent-relay
SCTP path end-to-end, but only ever sends dummy "PING-FROM-GNB"/"PONG-FROM-AMF"
bytes - not valid NGAP, so try_decode_capability()/try_rewrite() always hit
their first decode-failure branch there, and none of the log_event()/
log_capability_event() profile/label fields added during the 2026-07-31 review
(nor the removed dead NotImplementedError branch) were ever exercised by a
committed test. This file covers the unit-level pieces directly, plus one
end-to-end SCTP-level test using a real captured NGAP capability PDU (from the
committed exhibit pcap, same technique as test_ngap_decode_pipeline.py) so the
rewrite path is exercised with input it can actually act on.

Requires pyshark/tshark + sctp - run under proxy/venv:
    ./venv/bin/python3 test_ngap_proxy.py

Never writes to the real /root/comp997/logs/ngap_proxy_events.log - the
end-to-end test uses its own --event-log path in a temp directory (as a
subprocess, same pattern as test_relay_smoke.py); the unit tests attach an
in-memory logging handler directly, no file at all.
"""
import logging
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pyshark
import sctp

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "features"))
import ngap_decode  # noqa: E402
import ngap_proxy  # noqa: E402
from extract_features import _raw_hex  # noqa: E402

EXHIBIT_PCAP = str(Path(__file__).resolve().parent.parent / "data/raw/exhibits/ngap_label0_full.pcap")


def _extract_raw_capability_pdus() -> list:
    cap = pyshark.FileCapture(
        EXHIBIT_PCAP,
        display_filter=f"ngap.procedureCode=={ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION}",
        include_raw=True,
        use_json=True,
    )
    pdus = []
    try:
        for pkt in cap:
            pdus.append(bytes.fromhex(_raw_hex(pkt.ngap_raw.value)))
    finally:
        try:
            cap.close()
        except Exception:
            pass
    return pdus


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _capture_log(fn, *args, **kwargs):
    """Run fn with a temporary handler attached to ngap_proxy.LOG, return
    (result, [formatted messages])."""
    handler = _ListHandler()
    prev_level = ngap_proxy.LOG.level
    ngap_proxy.LOG.setLevel(logging.INFO)
    ngap_proxy.LOG.addHandler(handler)
    try:
        result = fn(*args, **kwargs)
    finally:
        ngap_proxy.LOG.removeHandler(handler)
        ngap_proxy.LOG.setLevel(prev_level)
    return result, [r.getMessage() for r in handler.records]


def test_log_event_always_includes_profile_and_label() -> None:
    """2026-07-31 fix: log_event()'s own comment had promised this since before
    the rewrite path existed; the fields were never actually added until now."""
    _, messages = _capture_log(ngap_proxy.log_event, "gnb->amf", 42, 0, 1.5, "sw-std", 3)
    assert any("event=relay" in m and "profile=sw-std" in m and "label=3" in m for m in messages), messages

    _, messages_default = _capture_log(ngap_proxy.log_event, "gnb->amf", 42, 0, 1.5)
    assert any("profile=None" in m and "label=0" in m for m in messages_default), (
        "relay/decode/reencode stages must still log profile=None label=0, not omit the fields"
    )
    print("test_log_event_always_includes_profile_and_label: PASSED")


def test_log_capability_event_includes_profile_and_label() -> None:
    summary = {
        "access_stratum_release": "rel15", "band_count": 1, "band_ids": [78],
        "ca_supported": True, "mimo_dl_layers": ["twoLayers"], "mimo_ul_layers": ["oneLayer"],
        "vonr_supported": True,
    }
    _, messages = _capture_log(ngap_proxy.log_capability_event, summary, "sw-ext", 5)
    assert any("event=capability" in m and "profile=sw-ext" in m and "label=5" in m for m in messages), messages
    print("test_log_capability_event_includes_profile_and_label: PASSED")


def test_try_decode_capability_never_raises_on_garbage() -> None:
    ngap_proxy.try_decode_capability(b"not valid ngap at all", "sw-std", 0)
    ngap_proxy.try_decode_capability(b"", "sw-std", 0)
    print("test_try_decode_capability_never_raises_on_garbage: PASSED")


def test_try_decode_capability_logs_summary_for_real_pdu(pdus) -> None:
    _, messages = _capture_log(ngap_proxy.try_decode_capability, pdus[0], "sw-std", 2)
    assert any("decoded UERadioCapabilityInfoIndication" in m for m in messages)
    assert any("capability summary" in m for m in messages)
    assert any("event=capability" in m and "profile=sw-std" in m and "label=2" in m for m in messages)
    print("test_try_decode_capability_logs_summary_for_real_pdu: PASSED")


def test_try_reencode_real_pdu_round_trips(pdus) -> None:
    out = ngap_proxy.try_reencode(pdus[0], "gnb->amf")
    pdu_val = ngap_decode.decode_ngap_pdu(out)
    assert pdu_val is not None, "re-encoded bytes must still be valid NGAP"
    assert ngap_decode.get_procedure_code(pdu_val) == ngap_decode.NGAP_PROC_UE_RADIO_CAPABILITY_INFO_INDICATION
    print("test_try_reencode_real_pdu_round_trips: PASSED")


def test_try_reencode_garbage_falls_back_unchanged() -> None:
    garbage = b"definitely not ngap"
    out, messages = _capture_log(ngap_proxy.try_reencode, garbage, "gnb->amf")
    assert out == garbage
    assert any("decode/re-encode failed, forwarding original" in m for m in messages)
    print("test_try_reencode_garbage_falls_back_unchanged: PASSED")


def test_try_rewrite_wrong_direction_falls_through_to_reencode(pdus) -> None:
    """Capability messages only ever flow gNB->AMF - the amf->gnb direction
    must always fall through to the plain Step-3 re-encode path, never
    attempt a rewrite, regardless of profile/label."""
    rewritten = ngap_proxy.try_rewrite(pdus[0], "amf->gnb", "sw-std", 5)
    reencoded_only = ngap_proxy.try_reencode(pdus[0], "amf->gnb")
    assert rewritten == reencoded_only, "wrong-direction traffic must not be rewritten"
    print("test_try_rewrite_wrong_direction_falls_through_to_reencode: PASSED")


def test_try_rewrite_gnb_to_amf_rewrites_and_logs(pdus) -> None:
    rewritten, messages = _capture_log(ngap_proxy.try_rewrite, pdus[0], "gnb->amf", "sw-ext", 4)
    assert any("rewrote UERadioCapabilityInfoIndication profile=sw-ext label=4" in m for m in messages)
    assert any("event=capability" in m and "profile=sw-ext" in m and "label=4" in m for m in messages)

    pdu_val = ngap_decode.decode_ngap_pdu(rewritten)
    cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
    decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
    summary = ngap_decode.summarize_capability(decoded["capability"])
    assert summary["ca_supported"] is True, "sw-ext baseline: CA on"
    assert summary["mimo_dl_layers"] == ["fourLayers"], "sw-ext baseline: 4x4 DL"
    assert summary["vonr_supported"] is False, "label 4 must strip VoNR from the sw-ext baseline"
    print("test_try_rewrite_gnb_to_amf_rewrites_and_logs: PASSED")


NGAP_PPID = 60
PROXY_ADDR = ("127.0.0.1", 28512)
DUMMY_AMF_ADDR = ("127.0.0.1", 28513)


def _dummy_amf_capture(received: list):
    srv = sctp.sctpsocket_tcp(socket.AF_INET)
    srv.events.data_io = True
    srv.bind(DUMMY_AMF_ADDR)
    srv.listen(1)
    conn, _ = srv.accept()
    conn.events.data_io = True
    _, flags, msg, _ = conn.sctp_recv(65536)
    received.append(msg)
    conn.close()
    srv.close()


def test_end_to_end_relay_rewrites_real_capability_pdu(pdus) -> None:
    """Sends a real captured NGAP UERadioCapabilityInfoIndication PDU through
    the actual proxy process over real SCTP sockets (same pattern as
    test_relay_smoke.py), with --stage rewrite --profile sw-min --label 2,
    and confirms the AMF-side dummy receives a rewritten PDU matching the
    sw-min baseline with CA further forced off by label 2 (already off in
    sw-min, so this also confirms label 2 is a safe no-op on an
    already-CA-disabled baseline, not just that CA stays off)."""
    with tempfile.TemporaryDirectory() as tmp:
        event_log = str(Path(tmp) / "events.log")
        proxy = subprocess.Popen(
            [
                sys.executable, "ngap_proxy.py",
                "--listen-addr", PROXY_ADDR[0], "--listen-port", str(PROXY_ADDR[1]),
                "--amf-addr", DUMMY_AMF_ADDR[0], "--amf-port", str(DUMMY_AMF_ADDR[1]),
                "--event-log", event_log,
                "--stage", "rewrite", "--profile", "sw-min", "--label", "2",
            ],
            cwd=str(Path(__file__).resolve().parent),
        )
        time.sleep(0.5)
        try:
            received = []
            amf_thread = threading.Thread(target=_dummy_amf_capture, args=(received,), daemon=True)
            amf_thread.start()
            time.sleep(0.3)

            gnb = sctp.sctpsocket_tcp(socket.AF_INET)
            gnb.events.data_io = True
            gnb.connect(PROXY_ADDR)
            gnb.sctp_send(pdus[0], ppid=NGAP_PPID, stream=0)
            amf_thread.join(timeout=3)
            gnb.close()

            assert len(received) == 1, "AMF-side dummy must receive exactly one rewritten message"
            pdu_val = ngap_decode.decode_ngap_pdu(received[0])
            assert pdu_val is not None
            cap_bytes = ngap_decode.extract_protocol_ie(pdu_val, ngap_decode.NGAP_IE_ID_UE_RADIO_CAPABILITY)
            decoded = ngap_decode.decode_ue_radio_capability_container(cap_bytes)
            summary = ngap_decode.summarize_capability(decoded["capability"])
            assert summary["ca_supported"] is False
            assert summary["vonr_supported"] is False, "sw-min baseline has no VoNR"
            assert summary["band_ids"] == [78]
        finally:
            proxy.terminate()
            proxy.wait(timeout=3)

    print("test_end_to_end_relay_rewrites_real_capability_pdu: PASSED")


def main() -> int:
    pdus = _extract_raw_capability_pdus()
    assert len(pdus) == 2

    test_log_event_always_includes_profile_and_label()
    test_log_capability_event_includes_profile_and_label()
    test_try_decode_capability_never_raises_on_garbage()
    test_try_decode_capability_logs_summary_for_real_pdu(pdus)
    test_try_reencode_real_pdu_round_trips(pdus)
    test_try_reencode_garbage_falls_back_unchanged()
    test_try_rewrite_wrong_direction_falls_through_to_reencode(pdus)
    test_try_rewrite_gnb_to_amf_rewrites_and_logs(pdus)
    test_end_to_end_relay_rewrites_real_capability_pdu(pdus)
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
