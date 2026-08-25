# Results

These files are **empty templates** — every number must be backfilled from a
real evaluation run before being reported. Nothing here is fabricated.

How to backfill:

1. Run a batch with `./scripts/evaluate_act.sh --execute --max-steps <budget>`
   (or the async `./scripts/run_act.sh` stack) on the real robot.
2. Fill `trial_results.csv` from the run log; aggregate the columns into
   `evaluation_summary.json`.
3. Fill `latency_results.csv` from the gRPC server/client timing logs
   (policy inference, chunk encode, transport round-trip).
4. For the video-backed claim, film one unedited continuous take, then fill
   `consecutive_10_trials.csv` trial-by-trial from the footage. Only claim
   what the video shows — if a trial needed a manual reset, mark it.

Reporting rule of thumb: prefer "10/10 consecutive trials" to a percentage.
A single continuous take is far more credible than an aggregated success
rate.
