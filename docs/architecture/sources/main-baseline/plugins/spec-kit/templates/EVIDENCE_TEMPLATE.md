# Verification run: [RUN-ID]
Store in the selected feature's evidence/RUN-ID.md. This is observed evidence, not an implementation checklist. One run may cover several checks.

## 1. Execution identity
| Field | Actual value |
| --- | --- |
| TASK ID / run ID / UTC time | [Fill] |
| Level and V IDs | [BLOCK / BOUNDARY / SYSTEM; qualified IDs] |
| Candidate identity | [Commit; for dirty work add diff digest and relevant changed/untracked file hashes or immutable snapshot] |
| Baseline / component revisions | [Fill] |
| PRD, spec, plan and IF versions | [Fill] |
| Working directory / platform / runtime / dependency versions | [Fill] |
| Input/fixture/dataset/model/prompt/configuration versions | [Fill or reasoned N/A] |
| Dependency mode and actual services | [Stub / local real / external real; details] |
| Command or reproducible manual procedure | [Exact invocation/steps; no secret values] |

## 2. Per-check observations
| V ID / AC references | Expected outcome / threshold source | Actual outcome | Exit code / counts including skips | Result | Raw artifact location |
| --- | --- | --- | --- | --- | --- |
| [Fill] | [Fill] | [Actual observation; never planned result] | [Fill or N/A for manual check] | [PASS / FAIL / BLOCKED / NOT_RUN / STALE / N/A] | [Exact path/digest] |

A check is PASS only if all its required assertions actually passed. Empty collection, required skips, missing real dependencies or suppressed errors do not qualify.

## 3. Scope and validity
- Behavior established: [Fill].
- Behavior not established / failures / blockers: [Fill or None].
- Reproducibility details for model/evaluation runs: [Sample count, repetitions, randomness, rubric, variability, cost/latency boundaries or N/A].
- Reused earlier evidence and comparison basis: [Fill or None].
- Superseded run IDs / reason: [Fill or None].
- Follow-up V/work-item references: [Fill or None].
- Candidate/input changes after this run: [None known or impact and STALE references].

Update the native tasks.md matrix to point to this run. Retain earlier runs; do not rewrite their observed outcomes.
