# Results

**Status: `consecutive_10_trials.csv` is REAL DATA** (backfilled from a
frame-by-frame review of one continuous recording, see
`consecutive_10_trials_review.md`). The other three files
(`evaluation_summary.json`, `trial_results.csv`, `latency_results.csv`)
remain **empty templates** — every number in them must be backfilled from a
real run before being reported. Nothing here is fabricated.

How to backfill the remaining templates:

1. Run a batch with `./scripts/evaluate_act.sh --execute --max-steps <budget>`
   (or the async `./scripts/run_act.sh` stack) on the real robot.
2. Fill `trial_results.csv` from the run log; aggregate the columns into
   `evaluation_summary.json`.
3. Fill `latency_results.csv` from the gRPC server/client timing logs
   (policy inference, chunk encode, transport round-trip).

`consecutive_10_trials.csv` already follows the 10/10 recording discipline:
- filled from a **single continuous take** (no internal cuts),
- `manual_reset_required` is true where an operator reset was visible,
- one incomplete 11th attempt (started ~320 s, unresolved at end of
  recording) is explicitly **not** counted.

Reporting rule of thumb: prefer "10/10 consecutive trials" to a percentage.
A single continuous take is far more credible than an aggregated success
rate.
