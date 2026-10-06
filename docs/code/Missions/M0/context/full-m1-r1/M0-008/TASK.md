# TASK: M0-008 — Qualified intake and attributable local resource binding

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-008 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Capture the original scientific request through supported local CLI/Web surfaces, import permitted documents, bind supplied code/data separately and produce a verified qualified intake for fixed Intent preparation. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Capture the original scientific request through supported local CLI/Web surfaces, import permitted documents, bind supplied code/data separately and produce a verified qualified intake for fixed Intent preparation. Exclusions: No external channels, voice, ingestion web crawling, repository cloning, dataset download, Office extraction, vectorization, semantic deduplication or intake document signing. Account persistence is not an ingestion-owned feature. |
| PRD clause and architecture node references | PRD 2.3 (../source/PRD - AI4Research.txt:L442-L466); PRD 2.4 (../source/PRD - AI4Research.txt:L467-L485); PRD 3.1 (../source/PRD - AI4Research.txt:L671-L674); PRD 3.1.1 (../source/PRD - AI4Research.txt:L675-L686); PRD 3.1.2 (../source/PRD - AI4Research.txt:L687-L709); PRD 3.1.3 (../source/PRD - AI4Research.txt:L710-L720); PRD 3.1.4 (../source/PRD - AI4Research.txt:L721-L731); PRD 3.1.5 (../source/PRD - AI4Research.txt:L732-L745); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/channels/cli/main.py; jiuwenswarm/channels/web/file_picker.py; jiuwenswarm/channels/web/directory_picker.py; jiuwenswarm/agents/harness/common/tools/pdf_tools.py; jiuwenswarm/server/runtime/agent_adapter/session_input.py; jiuwenswarm/ai4research/intake.py (proposed); tests/unit_tests/ai4research/test_intake.py (proposed); tests/integration_tests/ai4research/test_intake_boundary.py (proposed); tests/fixtures/ai4research/intake/calibration_manifest.json (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-008/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-008/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-002](../M0-002/TASK.md) / [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1) | Durable identity, profiles and effective configuration | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-004](../M0-004/TASK.md) / [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1) | Governed capsule runner and enforced effects | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-006](../M0-006/TASK.md) / [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1) | Protected contracts, static graph and gate-locked scheduling | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-007](../M0-007/TASK.md) / [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1) | Protected guard profiles, Verifier and durable release | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-008 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-008; consumers: M0-009, M0-010, M0-012, M0-013, M0-014, M0-017, M0-SYSTEM |
| Purpose / source requirement | Capture the original scientific request through supported local CLI/Web surfaces, import permitted documents, bind supplied code/data separately and produce a verified qualified intake for fixed Intent preparation. Sources: 2.3, 2.4, 3.1, 3.1.1, 3.1.2, 3.1.3, 3.1.4, 3.1.5, 4.2.1, 4.2.6 |
| Inputs: fields, types, units, required/optional, validation | LocalResearchSubmission: request text; permitted txt/md/pdf document locators; supplied project/code/data references; user/workspace/request identity; configured size bound. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | QualifiedIntake: original text and extracted document dictionary; separate code/validation asset registry; origin path/type/size/timestamp; qualification result/reasons; no semantic intake verdict or automatic retrieval. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-008.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-008/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Q-INTAKE-LIMIT: The PRD example is not a supplied numeric maximum file size.; SRC-INTAKE-PERSISTENCE: PRD 3.1.3 excludes cross-session user state while 2.3/5.4 require durable product identity. |

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-INTAKE-LIMIT / 2026-10-06 | The PRD example is not a supplied numeric maximum file size. | Oversize acceptance boundary only | Affected linked AC/B/V; no prior runtime evidence to reuse. | Select and freeze a finite supported limit in M0-002 configuration before threshold testing; do not copy 50 MB as an authoritative requirement. |
| SRC-INTAKE-PERSISTENCE / 2026-10-06 | PRD 3.1.3 excludes cross-session user state while 2.3/5.4 require durable product identity. | Intake identity and context carryover | Affected linked AC/B/V; no prior runtime evidence to reuse. | Use m1-design.md/placement.md: preserve durable account/profile separately, prohibit implicit prior research/session context carryover, and bind each local run explicitly. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
