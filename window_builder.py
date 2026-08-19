#!/usr/bin/env python3
"""Build N=3 sliding-window (36-feature) rows from the single-event 12-feature CSV.

the project's testbed architecture notes §8.2: for UEs with multiple consecutive registrations in
a session, construct a 36-feature window by concatenating N=3 consecutive
single-event feature vectors. A window is only emitted if all N rows share the
same session_id - windows never cross a session boundary.

Usage:
    window_builder.py [--input features/raw_12f.csv] [--output features/windowed_36f.csv] [--n 3]
"""
import argparse

import numpy as np
import pandas as pd

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


def _check_sessions_contiguous(df: pd.DataFrame) -> None:
    """Precondition for build_windows(): each session_id's rows must form one
    contiguous run in df. The sliding window below is a plain df.iloc[i:i+n]
    over row order - it never groups by session_id itself, it only checks
    that the n rows it happens to land on all share one. If a session's rows
    are scattered (e.g. events from concurrent UEs appended in wall-clock
    arrival order instead of grouped per session), that check silently keeps
    fewer windows than it should - including zero for a session whose rows
    never land in the same n-row block - with no error. Caught by inspection
    2026-07-31: interleaving two sessions' rows only 2-deep dropped every
    valid window for both, though each session individually had enough rows
    for one. Pre-sort by ["session_id", "session_timestamp_delta"] (or
    equivalent) before calling build_windows() if this raises.
    """
    block_id = (df["session_id"] != df["session_id"].shift()).cumsum()
    blocks_per_session = pd.Series(block_id.values, index=df.index).groupby(df["session_id"]).nunique()
    bad = blocks_per_session[blocks_per_session > 1]
    if not bad.empty:
        raise ValueError(
            "build_windows() requires each session_id's rows to be contiguous "
            f"(pre-sorted by session, then time within session): {list(bad.index)} "
            "each appear in more than one non-adjacent block of rows. Sort the "
            "input first, e.g. df.sort_values(['session_id', 'session_timestamp_delta'])."
        )


def build_windows(df: pd.DataFrame, n: int = 3):
    """the project's testbed architecture notes §8.2 build_windows(), verbatim logic plus a
    precondition check (see _check_sessions_contiguous) the spec's reference
    algorithm doesn't include.

    Window label is the LAST event's label in the window (the window is named
    after where it ends, matching how a detector would see it in real time -
    events accumulate before the labelled one is observed).
    """
    _check_sessions_contiguous(df)
    windows, labels = [], []
    for i in range(len(df) - n + 1):
        window = df.iloc[i : i + n]
        if window["session_id"].nunique() == 1:
            windows.append(window[FEATURE_COLS].values.flatten())
            labels.append(window["label"].iloc[-1])
    return np.array(windows), np.array(labels)


def windowed_column_names(n: int = 3):
    return [f"{col}_t{t}" for t in range(n) for col in FEATURE_COLS]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="features/raw_12f.csv", help="Single-event 12-feature CSV (default: features/raw_12f.csv)")
    p.add_argument("--output", default="features/windowed_36f.csv", help="Output windowed 36-feature CSV (default: features/windowed_36f.csv)")
    p.add_argument("--n", type=int, default=3, help="Window size (default: 3, per §8.2)")
    args = p.parse_args()

    df = pd.read_csv(args.input)
    X_win, y_win = build_windows(df, n=args.n)

    out = pd.DataFrame(X_win, columns=windowed_column_names(args.n))
    out["label"] = y_win
    out.to_csv(args.output, index=False)
    print(f"wrote {len(out)} windows ({args.n * len(FEATURE_COLS)} features each) to {args.output}")


if __name__ == "__main__":
    main()
