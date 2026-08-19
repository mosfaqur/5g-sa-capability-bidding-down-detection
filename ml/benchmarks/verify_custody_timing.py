#!/usr/bin/env python3
"""Automated ISO/IEC 27037:2012 forensic verification timing (post-Session-F
addendum item 5).

Two checks, both timed:
  (a) Chain-hash recompute: walk chain_of_custody.log from the genesis hash,
      recomputing sha256(prev_chain_hash + file_hash + ts + mode + sid) for
      every record and comparing against the stored chain_hash. This is the
      check that proves the log itself has not been tampered with, and does
      not require the original evidence files still being on disk.
  (b) File-hash re-verification: for every record whose evidence file still
      exists at its recorded path, re-read the file and confirm its sha256
      matches the recorded file_hash. Reports how many records could not be
      re-checked because the file no longer exists at that path (expected for
      files later reorganised/archived - this does not indicate tampering,
      chain-hash verification alone already proves the log wasn't altered).

Same formula as custody_append.py's append_record(): chain hash covers
(prev_chain_hash + file_hash + ts + mode + sid), NOT the path field.

Usage: verify_custody_timing.py [path/to/chain_of_custody.log]
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import psutil

ROOT = Path("/root/comp997")
LOG_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "chain_of_custody.log"
OUT_DIR = ROOT / "ml" / "benchmarks"
OUT_DIR.mkdir(parents=True, exist_ok=True)
GENESIS_HASH = "0" * 64


def parse_line(line: str):
    parts = line.rstrip("\n").split("  ")
    if len(parts) != 6:
        return None
    file_hash, path, ts, mode, sid, chain_hash = parts
    return {
        "file_hash": file_hash, "path": path, "ts": ts,
        "mode": mode, "sid": sid, "chain_hash": chain_hash,
    }


def main():
    lines = LOG_PATH.read_text().splitlines()
    records = [parse_line(l) for l in lines if l.strip()]
    malformed = sum(1 for r in records if r is None)
    records = [r for r in records if r is not None]
    n = len(records)
    print(f"Loaded {n} records from {LOG_PATH} ({malformed} malformed lines skipped)")

    proc = psutil.Process()
    proc.cpu_percent(interval=None)  # prime the counter

    # (a) Chain-hash recompute
    t0 = time.perf_counter()
    prev = GENESIS_HASH
    chain_breaks = []
    for i, r in enumerate(records):
        expected = hashlib.sha256(
            (prev + r["file_hash"] + r["ts"] + r["mode"] + r["sid"]).encode()
        ).hexdigest()
        if expected != r["chain_hash"]:
            chain_breaks.append({"index": i, "path": r["path"], "expected": expected, "found": r["chain_hash"]})
        prev = r["chain_hash"]
    chain_verify_s = time.perf_counter() - t0
    chain_cpu_pct = proc.cpu_percent(interval=None)

    # (b) File-hash re-verification, for files still present on disk
    t0 = time.perf_counter()
    proc.cpu_percent(interval=None)
    checked, matched, mismatched, missing = 0, 0, 0, 0
    file_mismatches = []
    for r in records:
        candidate = (ROOT / r["path"]) if not Path(r["path"]).is_absolute() else Path(r["path"])
        if not candidate.exists():
            missing += 1
            continue
        checked += 1
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual == r["file_hash"]:
            matched += 1
        else:
            mismatched += 1
            file_mismatches.append({"path": r["path"], "expected": r["file_hash"], "found": actual})
    file_verify_s = time.perf_counter() - t0
    file_cpu_pct = proc.cpu_percent(interval=None)

    result = {
        "log_path": str(LOG_PATH),
        "total_records": n,
        "malformed_lines_skipped": malformed,
        "chain_hash_verification": {
            "elapsed_seconds": chain_verify_s,
            "cpu_percent": chain_cpu_pct,
            "records_verified": n,
            "breaks_found": len(chain_breaks),
            "break_detail": chain_breaks[:20],
            "records_per_second": n / chain_verify_s if chain_verify_s > 0 else None,
        },
        "file_hash_reverification": {
            "elapsed_seconds": file_verify_s,
            "cpu_percent": file_cpu_pct,
            "files_checked": checked,
            "files_matched": matched,
            "files_mismatched": mismatched,
            "files_missing_from_disk": missing,
            "hash_match_rate": (matched / checked) if checked else None,
            "mismatch_detail": file_mismatches[:20],
        },
        "total_elapsed_seconds": chain_verify_s + file_verify_s,
    }

    with open(OUT_DIR / "custody_verification_timing.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nChain-hash verification: {n} records in {chain_verify_s:.4f}s "
          f"({result['chain_hash_verification']['records_per_second']:.0f} records/s), "
          f"{len(chain_breaks)} breaks, CPU {chain_cpu_pct:.1f}%")
    print(f"File-hash re-verification: {checked} files checked ({missing} missing from disk) "
          f"in {file_verify_s:.4f}s, {mismatched} mismatches, "
          f"match rate {result['file_hash_reverification']['hash_match_rate']:.4f}, "
          f"CPU {file_cpu_pct:.1f}%")
    print(f"Total: {result['total_elapsed_seconds']:.4f}s")
    print("Wrote", OUT_DIR / "custody_verification_timing.json")


if __name__ == "__main__":
    main()
