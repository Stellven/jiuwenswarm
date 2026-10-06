# TASK: M0-003 — Capability declarations and admitted library

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-003 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Define the current versioned capsule serialization/profile, implementation closure, admission, immutable lineage and human standing controls, preserving every architecture declaration field meaning. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Define the current versioned capsule serialization/profile, implementation closure, admission, immutable lineage and human standing controls, preserving every architecture declaration field meaning. Exclusions: No live capability installation, autonomous capability creation/promotion, remote importing, fusion, mid-run replacement, third-party certification or machine-schema-only claims of confinement. |
| PRD clause and architecture node references | PRD 4.1 (../source/PRD - AI4Research.txt:L1190-L1206); PRD 4.1.1 (../source/PRD - AI4Research.txt:L1207-L1224); PRD 4.1.2 (../source/PRD - AI4Research.txt:L1225-L1243); PRD 4.1.5 (../source/PRD - AI4Research.txt:L1284-L1304); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture capsule/declaration.md, capsule/authoring.md, capsules.md, sources/capsule.schema.json, sources/capsule-semantic-v2.10b.md, sources/policy-m1.json, principles.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/symphony/adapter.py; jiuwenswarm/symphony/build.py; jiuwenswarm/ai4research/capsules.py (proposed); jiuwenswarm/ai4research/schemas/capsule-current.schema.json (proposed); jiuwenswarm/resources/ai4research/capsules/primary-registry.json (proposed); jiuwenswarm/resources/ai4research/capsules/<primary-role>/capsule.json and pinned prompt/alias resources (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-003/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-003/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-002](../M0-002/TASK.md) / [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1) | Durable identity, profiles and effective configuration | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-003 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-003; consumers: M0-004, M0-006, M0-007, M0-009, M0-010, M0-011, M0-012, M0-013, M0-014, M0-015, M0-016, M0-017, M0-018, M0-019, M0-SYSTEM, M0-TRIAL-1 |
| Purpose / source requirement | Define the current versioned capsule serialization/profile, implementation closure, admission, immutable lineage and human standing controls, preserving every architecture declaration field meaning. Sources: 4.1, 4.1.1, 4.1.2, 4.1.5, 5.2.1 |
| Inputs: fields, types, units, required/optional, validation | CapsuleCandidate: capsule.json: current versioned declaration; implementation/dependency closure: references/hashes; provenance/lineage; admission evidence; human standing command: explicit authorized action. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | AdmittedCapsuleSnapshot: immutable declaration/implementation identity; provisional admission record; active/suspended/deprecated standing; history; eligible read-only catalogue; full declaration field inventory preserved. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-003.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-003/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | SRC-SCHEMA: Machine schema and semantic inventory disagree on shapes/requiredness; old M1 policy defers product-required fields. |

### Primary capability registry and seeding

This table is the canonical responsibility mapping within M0-IF-003@r1. PRD Markdown names are preserved aliases/prompt resources of their current capsule.json declarations, not independent contracts. The proposed registry `jiuwenswarm/resources/ai4research/capsules/primary-registry.json` records each role, declaration revision/hash, prompt/alias hash, executable closure hash, owning IF revision, admission evidence and selected standing. Implementation modules and resource bodies below are proposed and NOT_BUILT; no admitted revision or source body is invented.

| PRD responsibility | Primary alias / proposed declaration location | Implementation owner / proposed realization | Required bind and seed identity |
| --- | --- | --- | --- |
| 3.3 | search_capsule.md; jiuwenswarm/resources/ai4research/capsules/search/capsule.json | [M0-010](../M0-010/TASK.md); jiuwenswarm/ai4research/search_ideation.py | Exact declaration/prompt/implementation closure, M0-IF-010@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 3.4 | screening_capsule.md; jiuwenswarm/resources/ai4research/capsules/screening/capsule.json | [M0-011](../M0-011/TASK.md); jiuwenswarm/ai4research/screening.py | Exact declaration/prompt/implementation closure, M0-IF-011@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 3.5 | hypothesis_capsule.md; jiuwenswarm/resources/ai4research/capsules/hypothesis/capsule.json | [M0-012](../M0-012/TASK.md); jiuwenswarm/ai4research/hypothesis.py | Exact declaration/prompt/implementation closure, M0-IF-012@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 3.6 | poc_capsule.md; jiuwenswarm/resources/ai4research/capsules/poc/capsule.json | [M0-013](../M0-013/TASK.md); jiuwenswarm/ai4research/builder.py | Exact declaration/prompt/implementation closure, M0-IF-013@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 3.7 | benchmark_capsule.md; jiuwenswarm/resources/ai4research/capsules/benchmark/capsule.json | [M0-014](../M0-014/TASK.md); jiuwenswarm/ai4research/benchmark.py | Exact declaration/prompt/implementation closure, M0-IF-014@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 3.8 | scientific_evaluator_capsule.md; jiuwenswarm/resources/ai4research/capsules/scientific_evaluator/capsule.json | [M0-015](../M0-015/TASK.md); jiuwenswarm/ai4research/scientific_evaluation.py | Exact declaration/prompt/implementation closure, M0-IF-015@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 3.9 | report_capsule.md; jiuwenswarm/resources/ai4research/capsules/report/capsule.json | [M0-016](../M0-016/TASK.md); jiuwenswarm/ai4research/delivery.py | Exact declaration/prompt/implementation closure, M0-IF-016@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |
| 4.2 | verifier_capsule.md; jiuwenswarm/resources/ai4research/capsules/verifier/capsule.json | [M0-007](../M0-007/TASK.md); jiuwenswarm/ai4research/guards.py | Exact declaration/prompt/implementation closure, M0-IF-007@r1, admission and permitted standing; Stage 3.8 scientific evaluator is distinct from infrastructure verifier |

M0-017 initialization consumes this mapping and seeds version-locked resources under PRD 5.2.1. M0-006 binding and each stage owner reject missing, stale, swapped or ineligible primary identities before dispatch/release; support capabilities need their own explicit admitted contract bindings. M0-007 owns verifier-rubric adaptation and read-only profiles. Detailed profile prompts/resources are implementation work in those owners. Changes follow the existing r1 migration and evidence-invalidation rules.

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-002@r1](../M0-002/TASK.md#m0-if-002-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| SRC-SCHEMA / 2026-10-06 | Machine schema and semantic inventory disagree on shapes/requiredness; old M1 policy defers product-required fields. | AC-001, capsule readers, runtime limits and RSI | Affected linked AC/B/V; no prior runtime evidence to reuse. | Create and document a current versioned profile retaining original sources; independently validate migration and activate product-required enforcement. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
