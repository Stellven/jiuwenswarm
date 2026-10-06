# TASK: M0-006 — Protected contracts, static graph and gate-locked scheduling

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-006 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Assemble preparation and planned Node Execution Contracts; freeze the operational sequential Phase 1 graph, bind accepted artifacts and exact library/check pins, and dispatch only after durable gate acceptance. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Assemble preparation and planned Node Execution Contracts; freeze the operational sequential Phase 1 graph, bind accepted artifacts and exact library/check pins, and dispatch only after durable gate acceptance. Exclusions: No live graph restructuring, parallel hypotheses, distributed dispatch, active-version substitution, hidden retries or producer-written readiness. |
| PRD clause and architecture node references | PRD 1.4 (../source/PRD - AI4Research.txt:L211-L261); PRD 2.7 (../source/PRD - AI4Research.txt:L534-L550); PRD 4.1.3 (../source/PRD - AI4Research.txt:L1244-L1265); PRD 4.6 (../source/PRD - AI4Research.txt:L2048-L2051); PRD 4.6.1 (../source/PRD - AI4Research.txt:L2052-L2059); PRD 4.6.2 (../source/PRD - AI4Research.txt:L2060-L2069); PRD 4.6.4 (../source/PRD - AI4Research.txt:L2079-L2087); PRD 4.6.5 (../source/PRD - AI4Research.txt:L2088-L2097); PRD 6.4 (../source/PRD - AI4Research.txt:L2572-L2606); PRD 6.5 (../source/PRD - AI4Research.txt:L2607-L2626); architecture workflow.md, capsules.md, guard-design.md, m1-design.md, delivery-phases.md, principles.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/agents/harness/team/handlers/workflow_state.py; jiuwenswarm/ai4research/contracts.py (proposed); jiuwenswarm/ai4research/scheduler.py (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-006/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-006/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-006 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-006; consumers: M0-001, M0-002, M0-003, M0-004, M0-005, M0-007, M0-008, M0-009, M0-010, M0-011, M0-012, M0-013, M0-014, M0-015, M0-016, M0-017, M0-018, M0-019, M0-SYSTEM, M0-TRIAL-1 |
| Purpose / source requirement | Assemble preparation and planned Node Execution Contracts; freeze the operational sequential Phase 1 graph, bind accepted artifacts and exact library/check pins, and dispatch only after durable gate acceptance. Sources: 1.4, 2.7, 4.1.3, 4.6, 4.6.1, 4.6.2, 4.6.4, 4.6.5, 6.4, 6.5 |
| Inputs: fields, types, units, required/optional, validation | ContractAndGraphBinding: accepted Brief or fixed preparation obligations; original input/accepted predecessor refs; eligible library snapshot; protected profile/policy pins; objectives/typed edges; limits. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | FrozenExecutionBinding: Node Execution Contract {run_id,node_id,contract_id,revision,sha256,objective,inputs,outputs,cc_pins,obligations,check_plan,limits,effects}; frozen graph snapshot; concrete accepted future inputs before dispatch; readiness from durable gate only. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-006.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-006/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Exact fixtures and chosen enforcement/implementation require work items; no unresolved product scope choice is invented. |

Primary capsule identity and initialization consume [the canonical M0-003 responsibility/seeding mapping](../M0-003/TASK.md#primary-capability-registry-and-seeding); this TASK retains its owned node/function/interface rather than redefining the library registry.

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-020@r1](../M0-TRIAL-1/TASK.md#m0-if-020-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
