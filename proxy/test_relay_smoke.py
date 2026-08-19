#!/usr/bin/env python3
"""Standalone smoke test for ngap_proxy.py Step 1 (transparent relay).

Spins up a dummy 'AMF' SCTP echo-like server, starts the proxy pointed at it,
connects a dummy 'gNB' SCTP client through the proxy, and confirms bytes
survive both directions unmodified. Does not touch the live 5G stack.
"""
import socket
import subprocess
import sys
import time

import sctp

PROXY_LISTEN = ("127.0.0.1", 28412)
DUMMY_AMF = ("127.0.0.1", 28413)


def run_dummy_amf():
    srv = sctp.sctpsocket_tcp(socket.AF_INET)
    srv.events.data_io = True
    srv.bind(DUMMY_AMF)
    srv.listen(1)
    conn, _ = srv.accept()
    conn.events.data_io = True
    _, flags, msg, _ = conn.sctp_recv(4096)
    assert msg == b"PING-FROM-GNB", f"dummy AMF got unexpected bytes: {msg!r}"
    conn.sctp_send(b"PONG-FROM-AMF", ppid=60, stream=0)
    conn.close()
    srv.close()


def main() -> int:
    proxy = subprocess.Popen(
        [
            sys.executable,
            "ngap_proxy.py",
            "--listen-addr", PROXY_LISTEN[0],
            "--listen-port", str(PROXY_LISTEN[1]),
            "--amf-addr", DUMMY_AMF[0],
            "--amf-port", str(DUMMY_AMF[1]),
            "--event-log", "/tmp/ngap_proxy_smoke_events.log",
            "--stage", sys.argv[1] if len(sys.argv) > 1 else "relay",
        ] + (["--profile", sys.argv[2]] if len(sys.argv) > 2 else []),
    )
    time.sleep(0.5)

    import threading
    amf_thread = threading.Thread(target=run_dummy_amf, daemon=True)
    amf_thread.start()
    time.sleep(0.3)

    try:
        gnb = sctp.sctpsocket_tcp(socket.AF_INET)
        gnb.events.data_io = True
        gnb.connect(PROXY_LISTEN)
        gnb.sctp_send(b"PING-FROM-GNB", ppid=60, stream=0)
        _, flags, msg, _ = gnb.sctp_recv(4096)
        assert msg == b"PONG-FROM-AMF", f"gNB got unexpected bytes back: {msg!r}"
        gnb.close()
        amf_thread.join(timeout=2)
        print("SMOKE TEST PASSED: bytes relayed unmodified in both directions")
        return 0
    finally:
        proxy.terminate()
        proxy.wait(timeout=2)


if __name__ == "__main__":
    sys.exit(main())
