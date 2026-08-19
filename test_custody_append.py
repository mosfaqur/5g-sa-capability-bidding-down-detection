#!/usr/bin/env python3
"""Standalone smoke test for custody_append.py.

Never touches the real chain_of_custody.log - every test runs against an
isolated scratch log in a temp directory (via the CUSTODY_LOG env var
override custody_append.py already supports), same convention the project's internal build log
describes for prior ad hoc verification of this script.

Covers:
1. Chain dependency - the second record's chain hash depends on the first's
   (the project's testbed architecture notes Sec7.4): tampering the first record's chain hash
   breaks the second's.
2. The 2026-07-31 basename-collision fix - two same-named files in different
   directories must produce distinguishable, path-qualified records, not two
   identical-looking "INDEX.md" rows.
3. The outside-project-root fallback - evidence stored outside PROJECT_ROOT
   is recorded by its resolved absolute path, not silently mis-rooted.

Was previously only exercised by hand, inline, once per session - never
committed as a re-runnable script (see the project's internal build log's custody_append.py entry).
"""
import hashlib
import pathlib
import subprocess
import sys
import tempfile

CUSTODY_APPEND = pathlib.Path(__file__).resolve().parent / "custody_append.py"
GENESIS_HASH = "0" * 64


def run_append(evidence_path: str, mode: str, sid: str, log: pathlib.Path) -> str:
    result = subprocess.run(
        [sys.executable, str(CUSTODY_APPEND), evidence_path, mode, sid],
        env={"CUSTODY_LOG": str(log), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def verify_chain(log: pathlib.Path) -> bool:
    """Recompute every chain hash from the genesis hash forward. Same check
    used throughout this project's custody-chain re-verifications."""
    prev = GENESIS_HASH
    for line in log.read_text().splitlines():
        file_hash, _path, ts, mode, sid, chain = line.split()
        expect = hashlib.sha256((prev + file_hash + ts + mode + sid).encode()).hexdigest()
        if expect != chain:
            return False
        prev = chain
    return True


def test_chain_dependency(tmp: pathlib.Path) -> None:
    log = tmp / "chain_dependency.log"
    a = tmp / "a.pcap"
    b = tmp / "b.pcap"
    a.write_bytes(b"dummy evidence file A")
    b.write_bytes(b"dummy evidence file B")

    run_append(str(a), "normal", "test-session", log)
    run_append(str(b), "normal", "test-session", log)

    assert verify_chain(log), "two-record chain should verify cleanly"

    lines = log.read_text().splitlines()
    assert len(lines) == 2, f"expected 2 records, got {len(lines)}"

    # Tamper the first record's chain hash - the second record's link must break.
    first_fields = lines[0].split()
    first_fields[-1] = "f" * 64
    tampered = "  ".join(first_fields)
    log.write_text(tampered + "\n" + lines[1] + "\n")
    assert not verify_chain(log), "tampering record 1's chain hash must break record 2's link"

    print("test_chain_dependency: PASSED")


def test_basename_collision_fixed(tmp: pathlib.Path) -> None:
    log = tmp / "collision.log"
    (tmp / "dirA").mkdir()
    (tmp / "dirB").mkdir()
    file_a = tmp / "dirA" / "INDEX.md"
    file_b = tmp / "dirB" / "INDEX.md"
    file_a.write_text("content A")
    file_b.write_text("content B")

    run_append(str(file_a), "transcript", "index", log)
    run_append(str(file_b), "transcript", "index", log)

    lines = log.read_text().splitlines()
    assert len(lines) == 2
    path_a = lines[0].split()[1]
    path_b = lines[1].split()[1]
    assert path_a != path_b, f"same-basename files must not collide: {path_a!r} == {path_b!r}"
    assert path_a.endswith("dirA/INDEX.md"), f"expected a directory-qualified path, got {path_a!r}"
    assert path_b.endswith("dirB/INDEX.md"), f"expected a directory-qualified path, got {path_b!r}"
    assert verify_chain(log)

    print("test_basename_collision_fixed: PASSED")


def test_project_relative_path(tmp: pathlib.Path) -> None:
    """The other two tests run under /tmp, which is outside PROJECT_ROOT and
    always takes the absolute-path fallback branch of _record_path - neither
    exercises the project-relative branch. PROJECT_ROOT is hardcoded to
    /root/comp997 in custody_append.py (not env-overridable), so this test
    uses a scratch subdirectory inside the real project root instead, and
    removes it afterward."""
    project_root = pathlib.Path("/root/comp997")
    scratch = project_root / ".test_custody_append_scratch"
    scratch.mkdir(exist_ok=True)
    try:
        evidence = scratch / "evidence.pcap"
        evidence.write_bytes(b"in-project-root evidence")
        log = tmp / "project_relative.log"

        run_append(str(evidence), "meta", "test-session", log)

        recorded_path = log.read_text().splitlines()[0].split()[1]
        assert recorded_path == ".test_custody_append_scratch/evidence.pcap", (
            f"expected a project-root-relative path, got {recorded_path!r}"
        )
        assert not recorded_path.startswith("/"), "should be relative, not absolute, when inside PROJECT_ROOT"
        assert verify_chain(log)
    finally:
        for f in scratch.iterdir():
            f.unlink()
        scratch.rmdir()

    print("test_project_relative_path: PASSED")


def test_outside_project_root_fallback(tmp: pathlib.Path) -> None:
    log = tmp / "outside.log"
    outside_dir = tmp / "not_the_project_root"
    outside_dir.mkdir()
    outside_file = outside_dir / "evidence.pcap"
    outside_file.write_bytes(b"outside-root evidence")

    run_append(str(outside_file), "meta", "test-session", log)

    recorded_path = log.read_text().splitlines()[0].split()[1]
    assert recorded_path == str(outside_file.resolve()), (
        f"expected the resolved absolute path for out-of-root evidence, got {recorded_path!r}"
    )
    assert verify_chain(log)

    print("test_outside_project_root_fallback: PASSED")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="custody_append_smoke_") as tmpdir:
        tmp = pathlib.Path(tmpdir)
        for name, fn in [
            ("chain_dependency", test_chain_dependency),
            ("basename_collision_fixed", test_basename_collision_fixed),
            ("project_relative_path", test_project_relative_path),
            ("outside_project_root_fallback", test_outside_project_root_fallback),
        ]:
            sub = tmp / name
            sub.mkdir()
            fn(sub)
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
