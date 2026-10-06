# TASK: M0-001 — Audited Codex model bridge

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-001 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Verify and adapt the existing subscription bridge for bounded synchronous governed model invocations, with protected local IPC, owned context and attributable outcomes. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Verify and adapt the existing subscription bridge for bounded synchronous governed model invocations, with protected local IPC, owned context and attributable outcomes. Exclusions: No custom model proxy, broad conversational feature upgrade, provider tools, model training, inferred token billing or automatic model fallback; alternate routes belong to M0-019. |
| PRD clause and architecture node references | PRD 3.0 (../source/PRD - AI4Research.txt:L641-L644); PRD 3.0.1 (../source/PRD - AI4Research.txt:L645-L658); PRD 3.0.2 (../source/PRD - AI4Research.txt:L659-L670); PRD 4.3.2 (../source/PRD - AI4Research.txt:L1742-L1755); PRD 4.3.3 (../source/PRD - AI4Research.txt:L1756-L1778); PRD 4.3.4 (../source/PRD - AI4Research.txt:L1779-L1796); PRD 6.3 (../source/PRD - AI4Research.txt:L2553-L2571); architecture placement.md, contracts-and-native-reuse.md, immediate-plan.md, principles.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/server/runtime/codex_subscription/transport.py; jiuwenswarm/server/runtime/codex_subscription/service.py; jiuwenswarm/server/runtime/agent_adapter/interface_codex.py; jiuwenswarm/ai4research/model_bridge.py (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-001/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-001/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| None | Baseline source and current repository/tooling | Prepare independently; runtime provider readiness remains a separate check. | T001–T002 |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-001 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-001; consumers: M0-004, M0-007, M0-017, M0-018, M0-019, M0-SYSTEM, M0-TRIAL-1 |
| Purpose / source requirement | Verify and adapt the existing subscription bridge for bounded synchronous governed model invocations, with protected local IPC, owned context and attributable outcomes. Sources: 3.0, 3.0.1, 3.0.2, 4.3.2, 4.3.3, 4.3.4, 6.3 |
| Inputs: fields, types, units, required/optional, validation | ModelInvocation: messages: ordered role/content text; protected role: work/verifier; endpoint_profile: pinned reference; time_limit_s: positive seconds; call_limit: positive integer. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | CompletionObservation: completion_text: string on observed success; outcome: completed/auth_failed/timeout/delivery_unknown/cancelled; route/version/timestamps; usage: reliable per-call values or unavailable; account_allowance: separately labelled. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-001.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-001/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Exact fixtures and chosen enforcement/implementation require work items; no unresolved product scope choice is invented. |

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
