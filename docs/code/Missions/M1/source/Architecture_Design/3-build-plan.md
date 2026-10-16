# 3. Build plan

`Tier 1 · Part of: README · Serves: Standard`

What to build first, what must never block it, and how M1 is accepted. Ownership and scope limits are in [build scope](method/build-scope.md).

Start from the [JiuwenSwarm foundation](platform/native-reuse.md): extend the native application, workflow event transport, agent harness, web run view, configuration and diagnostics. Add the governed research binder, scheduler and gate authority around them. The existing Codex chat transport needs the documented bridge and Builder adaptations before research execution.

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

## M1 scope and acceptance boundary

The PRD core M1 gate is Phase 1, Stages 0–7 ([D40](method/decisions.md#d40)). Phase 2 and Phase 3 implementation coverage is reported separately and does not block that gate. Dynamic Agent Planning is the targeted Phase 3 item for full implementation, integration and verification. Its positive and negative paths must be reported. RSI and Model Routing are M1 implementation commitments; successful integration and verification are not core gate conditions. The [benchmark runner](side-systems/benchmark-runner.md) defines its own pilot and evidence.
