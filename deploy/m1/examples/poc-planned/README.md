# Planned POC case

One request for the POC objectives, run on the Planner path. The request names no stages
or template; the Planner chooses the capsules and the scheduler runs the plan.

- Source: the 10-26 product case `poc-product-public-feasible-05`. The task text and all
  seven inputs are byte-identical; the input hashes match its `input-packaging-revision.json`.
- Changed: `id` (`poc-planned`), `plan_source` (`static` to `planned`), and `deadline_s`
  (600 to 3600, the sidecar default; 600 s is only the compiler's own budget).
- The profile must capture the same `data.json` and `scoring-pins.json` as its external
  dataset, for example `scripts/live/deploy_live.py initialize --plan-source planned
  --fixture deploy/m1/examples/poc-planned`.
