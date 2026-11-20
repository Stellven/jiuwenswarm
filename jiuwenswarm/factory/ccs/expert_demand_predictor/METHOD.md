# Expert demand predictor verification

| Order | Stage | Check and retained evidence |
| --- | --- | --- |
| 1 | fixture | Run the capsule unit tests. Retain results for synthetic apply, allowed and forbidden scope, gate default, marker checks, worktree input and helper cases. Synthetic replay and synthetic logs earn this stage. |
| 2 | native CC execution | Submit your finished diff to the CC v2 `verify` capability. Retain the receipt and candidate identity. Review phase identification, callback control flow and INFO logging, and manually inspect protected routing, sampling and model paths. [Exact invocation](VALIDATION.md) |
| 3 | compile | Build all touched and header-dependent units with the pinned configuration and retain the logs. The verifier's optional syntax pass and standalone sample checks cover the units and flags reported. |
| 4 | runtime acceptance | Use one configuration per comparison. Run matched stock, candidate gate-unset and candidate gate-on. Compare greedy output byte for byte and compare actual IDs and mixture weights where captured. At `-lv 4`, confirm effective mmap mode, one active line on the eligible run and one requested-run exit stats line. Exercise unmapped or unsupported mode, mixed slots, decode, final layer, terminal advice failure, teardown, duplicate aliases and exhaustion of both budgets. Verify demand never waits for hint completion. Require readiness and lead evidence for the corresponding stats. |
| 5 | runtime acceptance | Replay the frozen predictor on held-out captured traces. Preserve request, microbatch and layer order and issue each forecast before its label. Report hits, misses, coverage, target and forecast counts and simulated waste using the applicable byte inventory. |
| 6 | hardware measurement | With hardware authority, measure matched target runs under the frozen methodology and retain repetitions, configuration and performance results. |

Server checks involving a port, GPU parity and hardware measurement run in an authorized real shell. Retain the engagement log separately from parity evidence. The factory task's fixed activation and greedy-parity smoke check records that workload. The component's broader acceptance includes every applicable row above.

## Gate-unset silence check

Inspect `verify` result `gate_unset_silence` and trace any inconclusive call
through the local code and its callers. Review first use, fallback and teardown for an early
stock return with no component work beyond one cached `getenv` check. In the
gate-unset arm at `-lv 4`, require the saved server log to pass:

```sh
python helpers/check_markers.py candidate-unset.server.log --name expert_demand_predictor --expect-silent
```

Require all component marker lines to come from gate-set arms.

Review informational `high_churn_signatures` findings against the additive
alternatives in [SOURCE-MAP.md](SOURCE-MAP.md).
