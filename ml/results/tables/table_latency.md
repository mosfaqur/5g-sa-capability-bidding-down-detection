# Table: Pipeline Latency vs Operational Ceiling (W6.2)

These figures come from a 100-event replay of decode, 12-feature extraction and RF inference in sequence, to which Session A's mean proxy-forward latency (0.853 ms) has been added, giving a full arrival-to-classification figure. The 1000 ms operational ceiling is a study-defined target, not a 3GPP-defined N2 timer.

| Stage | Mean (ms) | P95 (ms) | Max (ms) | Under 1000 ms ceiling? |
|---|---|---|---|---|
| Decode -> classification | 250.8 | 397.8 | 422.8 | yes |
| Full arrival -> classification (+ proxy forward) | 251.6 | 398.6 | 423.6 | yes |

n_events_replayed = 100
