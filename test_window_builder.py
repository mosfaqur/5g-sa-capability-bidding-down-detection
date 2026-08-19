#!/usr/bin/env python3
"""Standalone smoke test for window_builder.py.

Covers the original synthetic smoke-test scenario the project's internal build log describes for
build_windows() (4 rows sess-A, 3 rows sess-B, contiguous - 3 of 5 candidate
windows kept), plus the 2026-07-31 finding: build_windows() never actually
groups by session_id, it only checks that each raw n-row slice happens to
share one - interleaved (non-contiguous) session rows used to silently
produce zero windows with no error. _check_sessions_contiguous() now raises
ValueError instead; this file locks that behavior in and confirms the
original contiguous case still works unchanged.

Was previously only exercised by hand, inline, once per session - never
committed as a re-runnable script (see the project's internal build log's window_builder.py entry).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from window_builder import FEATURE_COLS, build_windows, windowed_column_names  # noqa: E402

BASE_FEATURES = dict(
    ue_category=1, ca_supported=1, ca_band_count=1, mimo_layers_dl=1, mimo_layers_ul=1,
    vonr_supported=1, volte_supported=0, nr_band_count=1, psm_supported=0,
    total_capability_size_bytes=100, ie_field_count=5, session_timestamp_delta=0,
)


def _rows(session_labels):
    """session_labels: list of (session_id, label) pairs, in row order."""
    return [dict(session_id=sid, label=label, **BASE_FEATURES) for sid, label in session_labels]


def test_contiguous_sessions_original_smoke_test() -> None:
    """Reproduces the project's internal build log's original 0c smoke test exactly: 4 rows sess-A
    then 3 rows sess-B, contiguous."""
    df = pd.DataFrame(_rows([("sess-A", i) for i in range(4)] + [("sess-B", i) for i in range(4, 7)]))
    X, y = build_windows(df, n=3)
    assert len(X) == 3, f"expected 3 of 5 candidate windows kept, got {len(X)}"
    assert X.shape[1] == 36, f"expected 36 features per window (3 * 12), got {X.shape[1]}"
    # Windows: [A0,A1,A2] label=A2's label(2), [A1,A2,A3] label=3, [B4,B5,B6] label=6.
    # The two straddling the boundary ([A2,A3,B4], [A3,B4,B5]) must be dropped.
    assert list(y) == [2, 3, 6], f"unexpected labels kept: {list(y)}"
    print("test_contiguous_sessions_original_smoke_test: PASSED")


def test_interleaved_sessions_raise_instead_of_silently_dropping() -> None:
    """2026-07-31 finding: before the fix, this silently returned zero windows
    for both sessions even though each individually had enough rows for one."""
    df = pd.DataFrame(_rows([("sess-A", i) if i % 2 == 0 else ("sess-B", i) for i in range(7)]))
    try:
        build_windows(df, n=3)
        raise AssertionError("expected ValueError for non-contiguous session rows, none raised")
    except ValueError as e:
        assert "sess-A" in str(e) and "sess-B" in str(e), f"error should name both offending sessions: {e}"
    print("test_interleaved_sessions_raise_instead_of_silently_dropping: PASSED")


def test_single_contiguous_block_still_works() -> None:
    """A single session with only 3 rows (contiguous, trivially) - baseline
    sanity check for the smallest input build_windows should accept."""
    df = pd.DataFrame(_rows([("sess-A", i) for i in range(3)]))
    X, y = build_windows(df, n=3)
    assert len(X) == 1
    assert list(y) == [2]
    print("test_single_contiguous_block_still_works: PASSED")


def test_fewer_rows_than_n_yields_no_windows() -> None:
    """Fewer rows than the window size must yield zero windows, not an error -
    this is a normal, expected outcome (not a contiguity violation)."""
    df = pd.DataFrame(_rows([("sess-A", 0), ("sess-A", 1)]))
    X, y = build_windows(df, n=3)
    assert len(X) == 0 and len(y) == 0
    print("test_fewer_rows_than_n_yields_no_windows: PASSED")


def test_none_value_silently_becomes_nan_not_an_error() -> None:
    """2026-07-31 finding, prompted by checking window_builder.py against
    extract_features.xlayer()'s byte_exact fix (which can now return None for
    2 of its 11 cross-layer features): window_builder.py is entirely out of
    scope for that - it is a standalone script never imported by any other
    code (confirmed by grep), hardcoded to the single-view 12-feature schema
    only, and the project's testbed architecture notes §8.2's own sliding-window spec is
    scoped to the single-view model only (the Week 8 timeline lists "sliding
    window (N=3) RF" and "cross-layer consistency RF" as two separate,
    non-overlapping line items) - so there is no live path for a None to ever
    reach build_windows() today, and no fix is warranted for a case that
    cannot currently happen.

    This test locks in the *observed* behavior anyway, as a guardrail: if
    build_windows() (or a copy of its logic) is ever repurposed for
    cross-layer data in the future, a None does NOT raise here - pandas
    silently converts it to NaN, which flows straight through into the output
    array with no error at window-building time. The failure only surfaces
    later, at RandomForestClassifier.fit() time ("Input contains NaN"),
    fully disconnected from where the None actually originated - the same
    class of delayed, confusing failure this project's Build Phase review
    kept finding and fixing elsewhere. Whoever eventually builds a
    cross-layer windowing/training pipeline should add an explicit NaN check
    before that point, rather than reuse build_windows() as-is."""
    df = pd.DataFrame(_rows([("sess-A", i) for i in range(3)]))
    df.loc[1, "total_capability_size_bytes"] = None
    X, y = build_windows(df, n=3)
    assert len(X) == 1
    import numpy as np
    assert np.isnan(X).any(), "expected the None to have become a NaN somewhere in the flattened window"
    print("test_none_value_silently_becomes_nan_not_an_error: PASSED")


def test_windowed_column_names_and_feature_cols_shape() -> None:
    cols = windowed_column_names(n=3)
    assert len(cols) == 36, f"expected 36 column names for n=3, got {len(cols)}"
    assert cols[:12] == [f"{c}_t0" for c in FEATURE_COLS]
    assert cols[12:24] == [f"{c}_t1" for c in FEATURE_COLS]
    assert cols[24:] == [f"{c}_t2" for c in FEATURE_COLS]
    assert len(FEATURE_COLS) == 12, f"expected 12 single-event features, got {len(FEATURE_COLS)}"
    print("test_windowed_column_names_and_feature_cols_shape: PASSED")


def test_feature_cols_matches_extract_features() -> None:
    """Cross-file guard: window_builder.py's FEATURE_COLS must stay identical
    (same names, same order) to extract_features.py's - a future edit to one
    without the other would silently misalign every windowed feature column.
    Reads extract_features.py's FEATURE_COLS list directly out of its source
    rather than importing the module, since that module requires pyshark
    (not installed in the base environment, only proxy/venv)."""
    import ast

    ef_path = Path(__file__).resolve().parent / "features" / "extract_features.py"
    tree = ast.parse(ef_path.read_text())
    ef_feature_cols = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FEATURE_COLS" for t in node.targets):
            ef_feature_cols = ast.literal_eval(node.value)
            break
    assert ef_feature_cols is not None, "could not find FEATURE_COLS in extract_features.py"
    assert ef_feature_cols == FEATURE_COLS, (
        f"FEATURE_COLS mismatch between window_builder.py and extract_features.py:\n"
        f"  window_builder.py:   {FEATURE_COLS}\n"
        f"  extract_features.py: {ef_feature_cols}"
    )
    print("test_feature_cols_matches_extract_features: PASSED")


def main() -> int:
    test_contiguous_sessions_original_smoke_test()
    test_interleaved_sessions_raise_instead_of_silently_dropping()
    test_single_contiguous_block_still_works()
    test_fewer_rows_than_n_yields_no_windows()
    test_none_value_silently_becomes_nan_not_an_error()
    test_windowed_column_names_and_feature_cols_shape()
    test_feature_cols_matches_extract_features()
    print("ALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
