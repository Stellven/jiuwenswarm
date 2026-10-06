# TASK: M0-004 — Governed capsule runner and enforced effects

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-004 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Execute admitted pinned capabilities under the intersection of per-CC, node and run authority, capture per-invocation observations and enforce resource/effect limits. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Execute admitted pinned capabilities under the intersection of per-CC, node and run authority, capture per-invocation observations and enforce resource/effect limits. Exclusions: No capability-created permission union, arbitrary installation, uncontrolled agent loops, automatic retries, host-wide effects or container-as-proof shortcut. |
| PRD clause and architecture node references | PRD 2.6 (../source/PRD - AI4Research.txt:L516-L533); PRD 2.9 (../source/PRD - AI4Research.txt:L567-L582); PRD 4.1.4 (../source/PRD - AI4Research.txt:L1266-L1283); PRD 4.6.3 (../source/PRD - AI4Research.txt:L2070-L2078); PRD 5.4.3 (../source/PRD - AI4Research.txt:L2410-L2418); architecture capsules.md, placement.md, guard-design.md, workflow.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/agents/harness/common/rails/permissions/openjiuwen_contract.py; jiuwenswarm/server/sandbox/jiuwenbox_runner.py; jiuwenswarm/ai4research/runner.py (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-004/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-004/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-001](../M0-001/TASK.md) / [M0-IF-001@r1](../M0-001/TASK.md#m0-if-001-at-r1) | Audited Codex model bridge | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-002](../M0-002/TASK.md) / [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1) | Durable identity, profiles and effective configuration | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-004 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-004; consumers: M0-006, M0-007, M0-008, M0-009, M0-010, M0-011, M0-012, M0-013, M0-014, M0-015, M0-016, M0-017, M0-018, M0-019, M0-SYSTEM, M0-TRIAL-1 |
| Purpose / source requirement | Execute admitted pinned capabilities under the intersection of per-CC, node and run authority, capture per-invocation observations and enforce resource/effect limits. Sources: 2.6, 2.9, 4.1.4, 4.6.3, 5.4.3 |
| Inputs: fields, types, units, required/optional, validation | GovernedInvocation: Node Execution Contract reference; exact CC/dependency pins; accepted typed bindings; invocation/role identity; guard assignment; finite permissions and time/call limits. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | InvocationObservation: candidate artifact references; actual stdout/stderr/tool/effect observations; outcome and duration seconds; exact implementation/model identities; observed counts and unavailable telemetry; no acceptance self-claim. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-004.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-004/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Exact fixtures and chosen enforcement/implementation require work items; no unresolved product scope choice is invented. |

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-001@r1](../M0-001/TASK.md#m0-if-001-at-r1); [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
