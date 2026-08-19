# data/raw_sample/

What follows is a stratified sample of the full labelled N2 capture dataset, not the
dataset itself. The full collection runs to approximately 5,251 raw PCAPs (406MB),
underpinning a 4,225-event single-view feature matrix, and is available on request, or
regenerable from the testbed procedure that this project's internal documentation
describes in detail, although that documentation is not distributed with this
repository. What is included here is instead sufficient to illustrate the raw capture
format without substantially bloating the repository.

## Sampling method

`build_raw_sample.py`, at the repository root, reads `logs/collection_manifest.csv`, groups rows by `(ue_profile, label)` and copies, for each group, the first 3 event(s)' `pcap_path` (and `rrc_path`, where present), preserving the manifest's original relative subpaths under this directory. The target budget was set at under 60MB total, and the per-group count was kept here at 3, the full target, since the budget was comfortably met.

`data/raw_validation_live/` (the Session F live-validation captures, already small) is copied in full alongside this sample rather than being sub-sampled in turn.

## Final per-(profile, label) counts

| Profile | Label | Events sampled |
|---|---|---|
| a56 | 0 | 3 |
| nothing3a | 0 | 3 |
| nothing3a | 1 | 3 |
| nothing3a | 2 | 3 |
| nothing3a | 3 | 3 |
| nothing3a | 4 | 3 |
| nothing3a | 5 | 3 |
| nothing3a | 6 | 3 |
| pixel8 | 0 | 3 |
| pixel8 | 1 | 3 |
| pixel8 | 2 | 3 |
| pixel8 | 3 | 3 |
| pixel8 | 4 | 3 |
| pixel8 | 5 | 3 |
| pixel8 | 6 | 3 |
| realme | 0 | 3 |
| realme | 1 | 3 |
| realme | 2 | 3 |
| realme | 3 | 3 |
| realme | 4 | 3 |
| realme | 5 | 3 |
| realme | 6 | 3 |
| sw-ext | 0 | 3 |
| sw-ext | 1 | 3 |
| sw-ext | 2 | 3 |
| sw-ext | 3 | 3 |
| sw-ext | 4 | 3 |
| sw-ext | 5 | 3 |
| sw-ext | 6 | 3 |
| sw-min | 0 | 3 |
| sw-min | 1 | 3 |
| sw-min | 2 | 3 |
| sw-min | 3 | 3 |
| sw-min | 4 | 3 |
| sw-min | 5 | 3 |
| sw-min | 6 | 3 |
| sw-std | 0 | 3 |
| sw-std | 1 | 3 |
| sw-std | 2 | 3 |
| sw-std | 3 | 3 |
| sw-std | 4 | 3 |
| sw-std | 5 | 3 |
| sw-std | 6 | 3 |

This gives a total of 194 files, 10.48 MB, plus a further 1.07 MB from `data/raw_validation_live/`.
