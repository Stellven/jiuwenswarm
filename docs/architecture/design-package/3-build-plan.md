# 3. Build plan

`Tier 1 · Part of: README · Serves: Standard`

What to build first, what must never block it, and how M1 is accepted. Ownership and scope limits are in [build scope](method/build-scope.md).

## Build order: hot path first

| Step | Build | Done when |
|---|---|---|
| 0 | Docker Compose on the server host; the Codex CLI behind the model bridge (PRD 3.0) | A LAN user reaches the app with a token; the Codex route answers over secured IPC; POC code runs under the restricted identity |
| 1 | Reconcile the existing Intention Compiler with the current contracts | A request ends in an accepted `research_brief.json` or a visible halt, with every decision stored |
| 2 | Shared runtime: declaration loader, binder, freeze, scheduler, CC runner, check runner, verifier call, gate host, run store | Node A, gate, node B runs headless, every CC through the same path |
| 3 | Static template over the six research nodes and Delivery | One request runs from Brief to report, or halts with a recorded reason |
| 4 | Planner CC and its checks | A planned run reaches Delivery, and bad plans are rejected before dispatch |
| 5 | Sidecar container: test runner, then the platform benchmark pilot | The test runner's matrix rows pass, and the pilot scores are stored as the baseline |

Every step ends with its stage validation record, and each PRD phase with its completion report (PRD 6.2.1). After step 4, the Phase 3 exit test runs one Brief with `plan_source` static and planned (PRD 1.3). M1 needs correct, checked artifacts, not the best plans or scores.

## Side systems: built in M1, never blocking

The model router, the RSI workbench and the platform benchmark runner are built in M1. Owners build them in parallel; steps 0 to 4 never wait for them. Each connects to the hot path only through:
- `RouterPort`;
- the record export;
- the admission inbox;
- the control API.

**Non-blocking test.** With Codex available, run the same static template in each condition:
- router switched off, or its process not installed or not started;
- router that raises an error, times out, returns an unapproved model, or whose process is killed or hung;
- RSI workbench absent; admission inbox empty or holding a corrupt package;
- sidecar container down.

Every run must finish with the same frozen plan and CC versions. An [import linter](reference/import-boundary.md) must show that no hot-path module imports router, RSI workbench, sidecar or record-builder code. The router is a separate process, reached only through `RouterPort` over IPC.

## Testing

Each build criterion in the tier 2 pages says what correct looks like, and each tier 3 check states the exact condition it enforces. Builders write their own tests from these. The team verifies after the build.

## October 30 acceptance

**October 30 acceptance** covers the hot path only ([D40](method/decisions.md#d40)). The PRD's core M1 gate is Phase 1, Stages 0 to 7. RSI and routing must be implemented but never block it.
- two different research requests, each run from intake to report, one static and one planned (the Planner is Phase 3 work built early, [D19](method/decisions.md#d19));
- one of them repeated three times with the same frozen plan, all successful;
- rejection before dispatch of an incompatible connection, a cycle and a missing check bundle;
- a scientific positive and a valid scientific negative, both delivered, from fixture tasks with known outcomes;
- a storage failure that halts;
- the non-blocking test and the import check, with router stubs.

**Benchmark pilot**, a separate item: the platform benchmark runner scores the benchmark's first end-to-end cases (E1) from the sidecar and stores the baseline. A pilot failure is reported, but it never holds the October 30 acceptance.

Passing checks alone does not prove a run works: inspect its artifacts and report.
