#!/usr/bin/env python3
"""Append a tamper-evident custody record for a PCAP (or other evidence file).

the project's testbed architecture notes §7.4: each record hashes the file and chains the
previous record's chain hash, so editing any earlier line breaks every record
after it. A bare `sha256sum` per file is not sufficient - it produces no chain
and only two fields. Used for N2 PCAPs, RRC reference captures, archived
per-campaign system logs (amf.log/gnb.log/proxy log), and per-session terminal
transcripts (Project_Setup_Plan.md Part 3.4 §0c / output-capture note).

Usage:
    custody_append.py <evidence_path> <attack_mode> <session_id>

Record format (six space-separated fields, appended to chain_of_custody.log):
    <sha256_file_hash>  <path>  <iso8601_timestamp>  <attack_mode>  <session_id>  <chain_hash>

The <path> field is project-root-relative (falls back to an absolute path for
evidence stored outside the project root), not a bare filename - two files
with the same basename in different directories (e.g. logs/transcripts/INDEX.md
vs analysis/exhibits/INDEX.md) must remain distinguishable in the log. The
chain hash itself never includes this field (only file_hash+ts+mode+sid), so
this only affects how new records are displayed - it does not touch, and
cannot invalidate, any record already appended.
"""
import hashlib
import datetime
import os
import pathlib
import sys

DEFAULT_LOG = pathlib.Path("/root/comp997/chain_of_custody.log")
PROJECT_ROOT = pathlib.Path("/root/comp997")
GENESIS_HASH = "0" * 64


def _record_path(evidence_path: str) -> str:
    """Project-root-relative path where possible, else the resolved absolute path."""
    resolved = pathlib.Path(evidence_path).resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def append_record(evidence_path: str, mode: str, sid: str, log: pathlib.Path = DEFAULT_LOG) -> str:
    """Append one custody record for evidence_path to log. Returns the new chain hash."""
    file_hash = hashlib.sha256(pathlib.Path(evidence_path).read_bytes()).hexdigest()
    prev = log.read_text().splitlines()[-1].split()[-1] if (log.exists() and log.read_text().strip()) else GENESIS_HASH
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    chain = hashlib.sha256((prev + file_hash + ts + mode + sid).encode()).hexdigest()
    with log.open("a") as f:
        f.write(f"{file_hash}  {_record_path(evidence_path)}  {ts}  {mode}  {sid}  {chain}\n")
    return chain


def main() -> None:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <evidence_path> <attack_mode> <session_id>", file=sys.stderr)
        sys.exit(1)

    evidence_path, mode, sid = sys.argv[1], sys.argv[2], sys.argv[3]
    log = pathlib.Path(os.environ.get("CUSTODY_LOG", str(DEFAULT_LOG)))
    log.parent.mkdir(parents=True, exist_ok=True)

    chain = append_record(evidence_path, mode, sid, log)
    print(f"appended custody record for {evidence_path} -> chain={chain}")


if __name__ == "__main__":
    main()
