# Feature Specification: M1-006 - Governed harness and fixed research DAG
**TASK**: [M1-006](../../docs/tasks/M1/M1-006/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)
**Input**: [PRD r2](../../docs/tasks/M1/sources/PRD-Full.r2.txt), §4.6, §4.6.1, §4.6.2 Phase 1, §4.6.3, §4.6.4; §4.6.5 excluded; §4.8, §4.8.1, §4.8.2, §4.8.3 Phase 1; sequencing §6.4–§6.5; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Governed harness and fixed research DAG observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.
4. Given the same blocking Node A/Gate condition in interactive/headless modes, when it occurs, then AC-004 invokes human_session only interactively and AC-008 durably terminates headlessly without releasing Node B; absence of prompts cannot permit continuation.

### Edge Cases
- AC-001: Successful and failed node with independently observed state transitions.
- AC-002: A/Gate/B under all five verdicts and delayed decision/persistence.
- AC-003: Success, hung capsule and malformed/missing-output variants with captured traces.
- AC-004: Crash/syntax/rejection/environment variants; human correction without restart; inspect preserved failure.
- AC-005: Two different valid briefs with identical graph shape and distinct parameter bindings.
- AC-006: Valid script, syntax error, absent named capsule and incompatible neighbor definition.
- AC-007: Runtime/graph/configuration inspection and failed-node trace with no retry/graph mutation.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.6.1): Native Swarmflow initializes/steps/terminates local runs; nodes follow deterministic Pending/Running/Evaluating/Completed-or-Failed transitions with state snapshots in local logs.
- **FR-002** (§4.6.2 Phase 1; §1.4): The fixed nine-stage DAG is sequential; downstream remains locked until durable Gate PASS/PASS_WITH_KNOWN_LIMITATIONS. Pending/blocking verdicts do not release it.
- **FR-003** (§4.6.3): Dispatch the CC runner as managed local subprocess, enforce declared time limits, log hangs/faults and package stdout/stderr/artifacts/runtime metrics for Gate before release.
- **FR-004** (§4.6.4 (lines 1818-1826); §4.2.8; §2.7): Crash, syntax faults and blocking Gate states stop autonomous work and preserve failures. Interactive execution invokes native human_session; explicit headless development/evaluation instead follows AC-008. Environment correction cannot silently pass or automatically replay failed work; restart remains explicit.
- **FR-005** (§4.8.1 Phase 1; §4.8.2 Phase 1): Autonomous decomposition is bypassed; hardcoded Swarmflow Python graph retains all 3.1–3.9 stages and injects brief objective/hardware/metric values without changing sequence.
- **FR-006** (§4.8.3 Phase 1; §4.1.3): Syntax checking and startup assertions reject malformed fixed-graph configuration or unavailable/incompatible declared bindings before dispatch; no autonomous replanning.
- **FR-007** (§4.6.1 blacklist; §4.6.2 blacklist/Phase 2; §4.6.3 blacklist; §4.6.4 blacklist; §4.6.5 excluded; §4.8.1 blacklist/Phase 2; §4.8.2 blacklist/Phase 2; §4.8.3 blacklist/Phase 2): Phase 1 excludes listed dynamic/parallel/distributed orchestration and autonomous repair; isolated Cluster/Leader experiments cannot alter the baseline.

- **FR-008** (§4.6.4 (lines 1818-1826); §6.4 (lines 2299-2333)): In explicit headless development/evaluation mode, every condition normally invoking human_session durably records blocking verdict, halt reason and available evidence, terminates autonomous execution and returns stable non-zero completion status without waiting for input. Headless mode changes post-halt interaction only; Gate policy, durable release and no-autonomous-repair rules remain intact.

### Key Entities
The input/output/state meanings are defined canonically in [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements). This spec does not invent a competing schema. PRD artifact/model names are retained; missing field-level design is reserved for architecture.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.6.1 / FR-001 / US1 | Native Swarmflow initializes/steps/terminates local runs; nodes follow deterministic Pending/Running/Evaluating/Completed-or-Failed transitions with state snapshots in local logs. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §4.6.2 Phase 1; §1.4 / FR-002 / US1 | The fixed nine-stage DAG is sequential; downstream remains locked until durable Gate PASS/PASS_WITH_KNOWN_LIMITATIONS. Pending/blocking verdicts do not release it. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | §4.6.3 / FR-003 / US1 | Dispatch the CC runner as managed local subprocess, enforce declared time limits, log hangs/faults and package stdout/stderr/artifacts/runtime metrics for Gate before release. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | PRD r2 §4.6.4 (lines 1818-1826); §4.2.8; §2.7 / FR-004 / US1 | Crash, syntax faults and blocking Gate states stop autonomous work and preserve failures. Interactive execution invokes native human_session; explicit headless development/evaluation instead follows AC-008. Environment correction cannot silently pass or automatically replay failed work; restart remains explicit. | BLOCK, BOUNDARY |
| AC-005 | §4.8.1 Phase 1; §4.8.2 Phase 1 / FR-005 / US1 | Autonomous decomposition is bypassed; hardcoded Swarmflow Python graph retains all 3.1–3.9 stages and injects brief objective/hardware/metric values without changing sequence. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-006 | §4.8.3 Phase 1; §4.1.3 / FR-006 / US1 | Syntax checking and startup assertions reject malformed fixed-graph configuration or unavailable/incompatible declared bindings before dispatch; no autonomous replanning. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-007 | §4.6.1 blacklist; §4.6.2 blacklist/Phase 2; §4.6.3 blacklist; §4.6.4 blacklist; §4.6.5 excluded; §4.8.1 blacklist/Phase 2; §4.8.2 blacklist/Phase 2; §4.8.3 blacklist/Phase 2 / FR-007 / US1 | Phase 1 excludes listed dynamic/parallel/distributed orchestration and autonomous repair; isolated Cluster/Leader experiments cannot alter the baseline. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-008 | PRD r2 §4.6.4 (lines 1818-1826); §6.4 (lines 2299-2333) / FR-008 / US1 | In explicit headless development/evaluation mode, every condition normally invoking human_session durably records blocking verdict, halt reason and available evidence, terminates autonomous execution and returns stable non-zero completion status without waiting for input. Headless mode changes post-halt interaction only; Gate policy, durable release and no-autonomous-repair rules remain intact. | BLOCK, BOUNDARY |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions

- Architecture reservation: [minimum inputs](../../docs/tasks/M1/ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7. Actual code/module/process boundaries, typed payloads/APIs/errors, coordination, storage/durability, security/settings mechanisms and executable test entry points remain PENDING_DESIGN; this spec states product outcomes only.
- Included: Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG.
- Excluded: No Auto Harness recursive sub-runs; autonomous decomposition, live graph restructuring, parallel hypotheses/batching, remote/cloud fleets or external container dispatch, message brokers/leases/quotas; no automatic repair/requeue or complex partial rewind. Isolated Cluster/Leader/dynamic-planning tracks belong to M1-019.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../../docs/tasks/M1/M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture must locate native Swarmflow integration and bind graph/runner/Gate bootstrap, state serialization, cancellation and human-session wiring. Graph definitions can use declared capsule contracts before all research stages are implemented; real integration cannot be claimed with placeholders. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
