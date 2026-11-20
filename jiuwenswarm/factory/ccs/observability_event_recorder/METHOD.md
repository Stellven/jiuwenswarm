# Recorder verification

Keep the base revision, proposed diff, contract, exact commands, raw outputs and stage with each result. See [VALIDATION.md](VALIDATION.md) for the native call.

| Stage | Evidence to retain |
| --- | --- |
| fixture | Run the capsule unit tests. The synthetic diffs exercise apply, scope, gate and marker checks. The helper tests use synthetic captures. For the actual recorder, exercise repeated graphs, mixed row remapping if supported, unavailable observations, a full ring, and a writer error with controlled inputs. |
| native CC execution | Invoke `verify` on the authored diff in the owned checkout. Review the verdict and inspect permitted hunks for unchanged routing, sampling, scheduler decisions and callback semantics. Check path authority against the work order as well as the verifier. |
| compile | Record standalone syntax results for illustrative samples and any new units with their provenance. In the owned target build, compile affected sources and dependents of changed headers, then link the intended server and retain its identity. |
| runtime acceptance | Run stock, candidate gate unset and candidate gate set with one frozen configuration. Compare greedy token IDs and output bytes, retain logs at `-lv 4`, and require exactly one active marker and one exit stats marker on success. Exercise an invalid gate and an output failure, require an inactive reason and unchanged output, and verify that the gate-unset run is silent. Inspect the effective load mode in all arms. |
| runtime acceptance | Construct a dispatch manifest from successful eligible microbatches and their routed layers. Require unique JSONL keys and exact coverage with zero loss in the normal run. Check caller tags, top-k IDs against an independent route probe, bytes against actual copy submissions, and timestamps against the chosen host boundary. Exercise prefill, one-token prefill, decode and accounted drop-newest overflow. Verify that the writer runs outside dispatch and drains on normal exit. |
| hardware measurement | Run comparable untraced paired recorder-on and recorder-off trials on the admitted hardware. Verify engagement. Measure external phase and end-to-end overhead and report internal hook and flush timing separately. Compare the external overhead with the contract. |

For a fixed layer set the expected event count is layers × successful eligible microbatches. For varying layer sets, sum the eligible routed layer count for each microbatch. Reconcile `expected = written + lost` for the same eligibility set. Report failed dispatches outside that set separately. Reconcile the independent manifest with the JSONL and the INFO counters. Submitted bytes measure scheduler requests. The readiness field measures the chosen host observation point.

A skipped syntax check supplies no compile evidence. A native verdict and compile check alone supply no runtime evidence. Server activation, parity, JSONL flush and hardware measurements require the authorized real shell described in [GUIDE.md](GUIDE.md).

## Gate-unset silence check

Inspect `verify` result `gate_unset_silence` and trace any inconclusive call
through the local code and its callers. Review first use, fallback and teardown for an early
stock return with no component work beyond one cached `getenv` check. In the
gate-unset arm at `-lv 4`, require the saved server log to pass:

```sh
python helpers/check_markers.py candidate-unset.server.log --name runtime_event_recorder --expect-silent
```

Require all component marker lines to come from gate-set arms.

Review informational `high_churn_signatures` findings against the additive
alternatives in [SOURCE-MAP.md](SOURCE-MAP.md).

## Graph-projected route rows

Follow [PROJECTED-ROWS.md](PROJECTED-ROWS.md) when the selected route tensor represents a verified subset of microbatch rows. Keep the normal zero-loss acceptance threshold.
