# Verification order

| Order | Stage | Check |
| --- | --- | --- |
| 1 | fixture | Exercise verifier fixtures for the good patch, missing marker, forbidden path and wrong preimage. Exercise the offline planner against synthetic inventories for exact cap, cap plus one byte, overlapping aliases, independent replicas, phase-boundary temporary overlap, safe and unsafe displacement, and deterministic ties. Reject duplicates, unknown assignments and invalid byte values. |
| 2 | fixture | Run the planner unit checks with real Qwen and Granite inventories from local GGUF metadata, identified by model, quantization and digest. Check stable unique rows, actual tensor sizes and physical-byte charges, including stock rows. Report missing inventories as skipped. |
| 3 | native CC execution | Call `verify` on the owned checkout and patch. Check the Git apply preimage, path allowlist, router and sampling file scope, recognized default-off `getenv` guard, and the required INFO marker literals in added code. With no patch path the preimage is HEAD and uncommitted changes include staged, unstaged and non-ignored untracked files. |
| 4 | compile | The verifier uses `g++ -std=c++17 -fsyntax-only` on candidate new C++ sources and headers in a temporary snapshot. It reports skipped if the compiler or an include is missing. Then compile every touched unit, with the intended backend flags and generated headers, and link the intended engine and tests. |
| 5 | runtime acceptance | Use `-lv 4` and fixed configuration. Compare gate-unset with stock and gate-on with stock configured through `-ot` for the same effective placement. Require byte-identical greedy stdout in both comparisons. The one-shot helper compares completion token arrays and reports markers as a server smoke check. Confirm effective load mode from `load_tensors`. Require active for a successful treatment, and check one active or inactive marker, one exit stats marker, class counts, and exact per-name readback against the plan. Exercise an invalid plan, a missing plan, an invalid gate value and a conflicting override. Require stock fallback and a recorded reason in each case. Audit that token order, routing, mixtures, quantization and sampling remain stock. |
| 6 | hardware measurement | If authorized, collect peak host residency and time for the fixed workload, with raw logs and configuration identity. Compare to the same assignment on stock. State which measurements were taken. |

Native results use named checks with `pass`, `fail` or `skipped` and their
stage. Any failure makes `done` false. A true `done` covers required static
checks and can coexist with a skipped best-effort syntax check. Assignments,
fallback and byte parity require runtime evidence. Syntax success covers the
listed units only. Claims about speed or hardware memory use require hardware
measurements. The phase ledger produces an admission calculation in bytes.

Syntax checks on the standalone samples carry the compile label for those
samples. Synthetic helper and verifier tests carry the fixture label. A
sealed host receipt on a synthetic input also demonstrates native CC
execution. Complete engine compilation and linking require the authorized
build environment. Server acceptance and hardware measurements need an
authorized real shell with the applicable GPU and port permissions.

## Gate-unset silence check

Inspect `verify` result `gate_unset_silence` and trace any inconclusive call
through the local code and its callers. Review first use, fallback and teardown for an early
stock return with no component work beyond one cached `getenv` check. In the
gate-unset arm at `-lv 4`, require the saved server log to pass:

```sh
python helpers/check_markers.py candidate-unset.server.log --name weight_placement_planner --expect-silent
```

Require all component marker lines to come from gate-set arms.

Review informational `high_churn_signatures` findings against the additive
alternatives in [SOURCE-MAP.md](SOURCE-MAP.md).

## Profile-driven Spark treatment

Follow [PROFILE-PLACEMENT.md](PROFILE-PLACEMENT.md) for a separately admitted residency comparison with reproducible controls. Retain the native verifier result and fixture acceptance before interpreting runtime timing.
