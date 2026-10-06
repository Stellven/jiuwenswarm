# TASK: M0-016 — Faithful Markdown research delivery and verified artifact closure

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-016 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Synthesize gate-admitted scientific verdict, protocol, original Brief, citations, POC assets and empirical evidence into the fixed Markdown research report and user package; transfer accepted artifacts through the control plane and close the run. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Synthesize gate-admitted scientific verdict, protocol, original Brief, citations, POC assets and empirical evidence into the fixed Markdown research report and user package; transfer accepted artifacts through the control plane and close the run. Exclusions: No audience profiling/custom report structures, publication-ready LaTeX/slides/dashboard formats, external Git/registry publication, chat notifications or verdict/measurement reinterpretation. |
| PRD clause and architecture node references | PRD 3.9 (../source/PRD - AI4Research.txt:L1146-L1151); PRD 3.9.1 (../source/PRD - AI4Research.txt:L1152-L1159); PRD 3.9.2 (../source/PRD - AI4Research.txt:L1160-L1167); PRD 3.9.3 (../source/PRD - AI4Research.txt:L1168-L1174); PRD 3.9.4 (../source/PRD - AI4Research.txt:L1175-L1189); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.9.3 (../source/PRD - AI4Research.txt:L2223-L2236); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); PRD 6.9 (../source/PRD - AI4Research.txt:L2700-L2717); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/agents/harness/common/tools/send_file_to_user.py; jiuwenswarm/agents/harness/common/tools/file_delivery_policy.py; jiuwenswarm/server/runtime/agent_adapter/output_handoff.py; jiuwenswarm/channels/web/frontend/tests/markdownRenderer.test.mjs; jiuwenswarm/ai4research/delivery.py (proposed); tests/unit_tests/ai4research/test_delivery.py (proposed); tests/integration_tests/ai4research/test_delivery_boundary.py (proposed); tests/fixtures/ai4research/delivery/calibration_manifest.json (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-016/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-016/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-015](../M0-015/TASK.md) / [M0-IF-015@r1](../M0-015/TASK.md#m0-if-015-at-r1) | Read-only scientific evidence evaluation and pre-registered classification | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-014](../M0-014/TASK.md) / [M0-IF-014@r1](../M0-014/TASK.md#m0-if-014-at-r1) | Restricted baseline-treatment benchmarking and empirical evidence | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-013](../M0-013/TASK.md) / [M0-IF-013@r1](../M0-013/TASK.md#m0-if-013-at-r1) | Bounded Builder and mechanical POC artifact assembly | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-012](../M0-012/TASK.md) / [M0-IF-012@r1](../M0-012/TASK.md#m0-if-012-at-r1) | Immutable hypothesis and pre-registered experimental protocol | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-009](../M0-009/TASK.md) / [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1) | Research Brief compilation from independently accepted intent | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-004](../M0-004/TASK.md) / [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1) | Governed capsule runner and enforced effects | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-006](../M0-006/TASK.md) / [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1) | Protected contracts, static graph and gate-locked scheduling | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-007](../M0-007/TASK.md) / [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1) | Protected guard profiles, Verifier and durable release | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-016 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-016; consumers: M0-017, M0-SYSTEM |
| Purpose / source requirement | Synthesize gate-admitted scientific verdict, protocol, original Brief, citations, POC assets and empirical evidence into the fixed Markdown research report and user package; transfer accepted artifacts through the control plane and close the run. Sources: 3.9, 3.9.1, 3.9.2, 3.9.3, 3.9.4, 4.2.1, 4.2.6, 4.9.3, 5.2.1, 6.9 |
| Inputs: fields, types, units, required/optional, validation | AcceptedScientificVerdict: accepted verdict/benchmark/Brief/citations; pinned report-writer logic/template; authorized destination and audience. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | ResearchDeliveryBundle: Markdown report plus allowed POC/environment/raw evidence references; faithful negative/inconclusive result; exact bundle manifest and final gate acceptance; transfer only to authorized local output. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-016.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-016/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Q-REPORT-UPSTREAM: Required sciencediscovery report-writer/result-evaluator/citation-reviewer source implementations are not present at inspected repository paths. |

Primary capsule identity and initialization consume [the canonical M0-003 responsibility/seeding mapping](../M0-003/TASK.md#primary-capability-registry-and-seeding); this TASK retains its owned node/function/interface rather than redefining the library registry.

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-012@r1](../M0-012/TASK.md#m0-if-012-at-r1); [M0-IF-013@r1](../M0-013/TASK.md#m0-if-013-at-r1); [M0-IF-014@r1](../M0-014/TASK.md#m0-if-014-at-r1); [M0-IF-015@r1](../M0-015/TASK.md#m0-if-015-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-REPORT-UPSTREAM / 2026-10-06 | Required sciencediscovery report-writer/result-evaluator/citation-reviewer source implementations are not present at inspected repository paths. | Pinned template and domain verification adaptations | Affected linked AC/B/V; no prior runtime evidence to reuse. | Resolve exact authorized upstream/revision, import/adapt via governed library ownership and record node obligation mappings/N/A/tests before live acceptance; retain proposed paths as proposed until implemented. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
