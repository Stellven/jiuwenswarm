# Native workflow integration validation

Date: 2026-11-16. Integration branch: `integration/native-cc-workflows`.

## Verified

- Spark Linux broad regression: **1572 passed, 13 skipped, 1 deselected**, plus
  32 passing subtests. Includes incoming source-generation tests against real
  STRATA revision `13eedf552417a6a791a7d13c6597e24300ee3a09`, existing factory
  policy/evidence tests and CC v2 tests. Log:
  `/tmp/native-workflow-integration-tests-final.log` on Spark.
- After adding native standard-benchmark cancellation and wrapped-output
  lifecycle support: **105 targeted tests passed**, including source workbench,
  benchmark policy, construction comparison and factory API. Log:
  `/tmp/native-workflow-targeted-final.log` on Spark.
- Real native workflow test writes and commits a task-owned source file through
  the existing source-workbench CC, with append-only decision/evidence lineage.
  Real CC tests verify nested composition, internal selection, sealed release
  stability, lost-acknowledgement recovery and HTTP request authority.
- Fault-injected tests cover uncertain calls, cancellation continuing after a
  sibling error, cross-task refusal, exact-owned benchmark cleanup, rejected
  candidates and incomplete cleanup. These are explicitly transport fault tests,
  not hardware execution evidence.
- Frontend production build passed. Incoming frontend runtime unit tests:
  **18 passed**. A browser test against a real native CC process returned the
  expected output, displayed graph/evidence, and replayed recorded state without
  another invocation. Desktop and narrow views were inspected; detailed receipts
  are collapsed separately from the result.

## Fixes found by validation

The incoming C++ source generator imported `std::expf`, which failed with the
Spark toolchain. It now uses the C float math names in the global namespace while
preserving the generated arithmetic. The production-source tests passed after
this fix. Duplicate `test_api.py` basenames across the branches were separated.
The incoming optional model assessment uses the current platform Model interface,
without importing the removed M1 provider. The test environment was corrected to
the repository's existing `mcp>=1.28.1,<2` requirement.

## Not established by these checks

- The excluded Docker demo requires its old pinned compute-service image, which
  is absent on Spark. This is not an inference-engine qualification result.
- The incoming historical replay projection suite depends on eight external run
  directories that are not part of the source checkout. Native replay was tested
  with a fresh real CC run instead; historical fixtures were not fabricated.
- No new full-model GPU build/comparison, benchmark speedup, or live CUDA vector
  capture is claimed. These require a fresh admitted campaign, pinned model and
  image identities, and independent lab evaluation. Prior source/CPU/replay
  evidence is not a substitute.
- Source-comparison preparation still enforces its existing admitted source/build
  lineage. Do not bypass those checks when composing a new workflow or silently
  treat an arbitrary image as an admitted candidate.

The integration checkout on Spark is
`/home/user2/software-factory-spark-20261113/sources/native-workflow-integration-20261116`.
The original `sources/cc-dgx-spark` checkout and its live stores were not migrated.
