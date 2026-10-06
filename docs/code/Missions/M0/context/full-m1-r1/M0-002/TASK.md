# TASK: M0-002 — Durable identity, profiles and effective configuration

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-002 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Separate stable product identity/profile storage from local research workspace lifetime; resolve reproducible configuration and enforce local session/disclosure/privacy controls. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Separate stable product identity/profile storage from local research workspace lifetime; resolve reproducible configuration and enforce local session/disclosure/privacy controls. Exclusions: No enterprise tenants, cloud vendor requirement, remote execution control, distributed quota/billing, or silent reuse of unrelated research. |
| PRD clause and architecture node references | PRD 2.3 (../source/PRD - AI4Research.txt:L442-L466); PRD 5.4 (../source/PRD - AI4Research.txt:L2381-L2387); PRD 5.4.1 (../source/PRD - AI4Research.txt:L2388-L2401); PRD 5.4.2 (../source/PRD - AI4Research.txt:L2402-L2409); PRD 5.4.4 (../source/PRD - AI4Research.txt:L2419-L2432); PRD 5.6 (../source/PRD - AI4Research.txt:L2458-L2464); PRD 5.6.1 (../source/PRD - AI4Research.txt:L2465-L2473); PRD 5.6.2 (../source/PRD - AI4Research.txt:L2474-L2481); PRD 5.6.3 (../source/PRD - AI4Research.txt:L2482-L2489); PRD 5.6.4 (../source/PRD - AI4Research.txt:L2490-L2497); PRD 5.6.5 (../source/PRD - AI4Research.txt:L2498-L2518); architecture placement.md, m1-design.md, principles.md, guard-design.md, automation.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/common/config.py; jiuwenswarm/common/model_config_validation.py; jiuwenswarm/ai4research/identity.py (proposed); jiuwenswarm/ai4research/configuration.py (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-002/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-002/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| None | Baseline source and current repository/tooling | Prepare independently; runtime provider readiness remains a separate check. | T001–T002 |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-002 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-002; consumers: M0-003, M0-004, M0-005, M0-008, M0-009, M0-014, M0-017, M0-018, M0-019, M0-SYSTEM, M0-TRIAL-1 |
| Purpose / source requirement | Separate stable product identity/profile storage from local research workspace lifetime; resolve reproducible configuration and enforce local session/disclosure/privacy controls. Sources: 2.3, 5.4, 5.4.1, 5.4.2, 5.4.4, 5.6, 5.6.1, 5.6.2, 5.6.3, 5.6.4, 5.6.5 |
| Inputs: fields, types, units, required/optional, validation | ExecutionProfileRequest: user_id/workspace_id: stable strings; requested_profile: reference; account/machine/project overrides: validated objects; requested_seed: optional integer. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | EffectiveExecutionProfile: effective settings and precedence; immutable profile_hash; requested/effective seed plus support status; role route aliases; positive time/call ceilings; authorization/disclosure audience; identity context. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-002.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-002/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | SRC-IDENTITY: PRD 3.1.3 local single-user wording conflicts with durable product account requirements. |

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| SRC-IDENTITY / 2026-10-06 | PRD 3.1.3 local single-user wording conflicts with durable product account requirements. | Account binding and intake compatibility | Affected linked AC/B/V; no prior runtime evidence to reuse. | Apply PRD 1.7 and architecture D12: durable product identity, local execution configuration; preserve source bytes and prohibit implicit prior-run intake reuse. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
