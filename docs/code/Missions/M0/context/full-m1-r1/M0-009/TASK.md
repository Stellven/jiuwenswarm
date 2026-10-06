# TASK: M0-009 — Research Brief compilation from independently accepted intent

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-009 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Produce the standard Research_Brief.json from accepted TRIAL-1 Intent plus original permitted context, explicit requirements and marked conservative defaults within one bounded non-interactive product entry. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Produce the standard Research_Brief.json from accepted TRIAL-1 Intent plus original permitted context, explicit requirements and marked conservative defaults within one bounded non-interactive product entry. Exclusions: No solution/idea generation, external context retrieval, host-resource inference, interactive Phase 1 clarification, asynchronous approval wait, post-start contract editing or dynamic routing/planning in the baseline. |
| PRD clause and architecture node references | PRD 3.2 (../source/PRD - AI4Research.txt:L746-L751); PRD 3.2.1 (../source/PRD - AI4Research.txt:L752-L760); PRD 3.2.2 (../source/PRD - AI4Research.txt:L761-L769); PRD 3.2.3 (../source/PRD - AI4Research.txt:L770-L776); PRD 3.2.4 (../source/PRD - AI4Research.txt:L777-L783); PRD 3.2.5 (../source/PRD - AI4Research.txt:L784-L788); PRD 3.2.6 (../source/PRD - AI4Research.txt:L789-L796); PRD 3.2.7 (../source/PRD - AI4Research.txt:L797-L809); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.7 (../source/PRD - AI4Research.txt:L2098-L2107); PRD 4.7.1 (../source/PRD - AI4Research.txt:L2108-L2117); PRD 4.7.2 (../source/PRD - AI4Research.txt:L2118-L2127); PRD 4.7.3 (../source/PRD - AI4Research.txt:L2128-L2137); PRD 4.7.4 (../source/PRD - AI4Research.txt:L2138-L2147); PRD 4.7.5 (../source/PRD - AI4Research.txt:L2148-L2160); PRD 6.5 (../source/PRD - AI4Research.txt:L2607-L2626); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md, principles.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/agents/harness/common/prompt/user_prompt_builder.py; jiuwenswarm/server/runtime/agent_adapter/interface_codex.py; jiuwenswarm/common/config.py; jiuwenswarm/ai4research/research_brief.py (proposed); tests/unit_tests/ai4research/test_research_brief.py (proposed); tests/integration_tests/ai4research/test_research_brief_boundary.py (proposed); tests/fixtures/ai4research/research_brief/calibration_manifest.json (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-009/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-009/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-TRIAL-1](../M0-TRIAL-1/TASK.md) / [M0-IF-020@r1](../M0-TRIAL-1/TASK.md#m0-if-020-at-r1) | Connected intermediate Intent compiler and protected Verifier slice | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-008](../M0-008/TASK.md) / [M0-IF-008@r1](../M0-008/TASK.md#m0-if-008-at-r1) | Qualified intake and attributable local resource binding | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-002](../M0-002/TASK.md) / [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1) | Durable identity, profiles and effective configuration | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-004](../M0-004/TASK.md) / [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1) | Governed capsule runner and enforced effects | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-006](../M0-006/TASK.md) / [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1) | Protected contracts, static graph and gate-locked scheduling | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-007](../M0-007/TASK.md) / [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1) | Protected guard profiles, Verifier and durable release | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-009 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-009; consumers: M0-006, M0-010, M0-011, M0-012, M0-013, M0-015, M0-016, M0-019, M0-SYSTEM |
| Purpose / source requirement | Produce the standard Research_Brief.json from accepted TRIAL-1 Intent plus original permitted context, explicit requirements and marked conservative defaults within one bounded non-interactive product entry. Sources: 3.2, 3.2.1, 3.2.2, 3.2.3, 3.2.4, 3.2.5, 3.2.6, 3.2.7, 4.2.1, 4.2.6, 4.7, 4.7.1, 4.7.2, 4.7.3, 4.7.4, 4.7.5, 6.5 |
| Inputs: fields, types, units, required/optional, validation | AcceptedIntentAndIntake: accepted IntermediateIntent and qualified intake/asset references; protected schema/default profile; user-stated scope/targets; frozen compiler limits. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | Research_Brief.json: objective/scope; mandatory requirements and optional preferences; constraints/time/hardware and recorded tokens; user metrics; deliverables; defaults/assumptions distinctly attributed; unresolved_items; evidence expectations; accepted contract reference. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-009.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-009/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | SRC-D5: Architecture D5 explicitly uses two bounded compiler calls whereas PRD 3.2/4.7 literally use one generation.; Q-BRIEF-SCHEMA: Architecture supplies semantic port examples rather than a final wire Research Brief schema. |

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1); [M0-IF-008@r1](../M0-008/TASK.md#m0-if-008-at-r1); [M0-IF-020@r1](../M0-TRIAL-1/TASK.md#m0-if-020-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| SRC-D5 / 2026-10-06 | Architecture D5 explicitly uses two bounded compiler calls whereas PRD 3.2/4.7 literally use one generation. | Baseline compiler invocation count and budgets | Affected linked AC/B/V; no prior runtime evidence to reuse. | Retain recorded D5 amendment and shared entry limits; independently accepted TRIAL-1 Intent precedes requirements. Preserve conflict/authority decision explicitly, never silently reinterpret one call. |
| Q-BRIEF-SCHEMA / 2026-10-06 | Architecture supplies semantic port examples rather than a final wire Research Brief schema. | Serialization/default readiness details | Affected linked AC/B/V; no prior runtime evidence to reuse. | Own and version the smallest exact schema through the TASK interface agreement, retaining every PRD semantic obligation and visibly marked defaults; no arbitrary numeric thresholds. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
