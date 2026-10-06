# TASK: M0-007 — Protected guard profiles, Verifier and durable release

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-007 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Own mandatory check profiles and immutable full-context assignments, minimize verifier disclosure, enforce deterministic then semantic assessment, validate exact subject and durably decide release. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Own mandatory check profiles and immutable full-context assignments, minimize verifier disclosure, enforce deterministic then semantic assessment, validate exact subject and durably decide release. Exclusions: No recursive verifier chain, reviewer-authored repairs, parallel voting, producer-approved policy, RSI referee mutation, live fact-check crawling or semantic PASS-as-scientific-truth. |
| PRD clause and architecture node references | PRD 2.8 (../source/PRD - AI4Research.txt:L551-L566); PRD 4.2 (../source/PRD - AI4Research.txt:L1305-L1313); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.2 (../source/PRD - AI4Research.txt:L1355-L1383); PRD 4.2.3 (../source/PRD - AI4Research.txt:L1384-L1414); PRD 4.2.4 (../source/PRD - AI4Research.txt:L1415-L1447); PRD 4.2.5 (../source/PRD - AI4Research.txt:L1448-L1482); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.2.7 (../source/PRD - AI4Research.txt:L1514-L1541); PRD 4.2.8 (../source/PRD - AI4Research.txt:L1542-L1627); PRD 4.2.9 (../source/PRD - AI4Research.txt:L1628-L1698); PRD 4.2.10 (../source/PRD - AI4Research.txt:L1699-L1722); PRD 4.3.4 (../source/PRD - AI4Research.txt:L1779-L1796); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture guard-design.md, capsules.md, failure-and-human.md, principles.md, capsule/declaration.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | sciencediscovery/result-evaluator and sciencediscovery/citation-reviewer upstream inputs (PENDING_SOURCE; not present in current checkout); jiuwenswarm/ai4research/guards.py (proposed); jiuwenswarm/ai4research/gate.py (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-007/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-007/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-001](../M0-001/TASK.md) / [M0-IF-001@r1](../M0-001/TASK.md#m0-if-001-at-r1) | Audited Codex model bridge | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-007 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-007; consumers: M0-001, M0-002, M0-003, M0-004, M0-005, M0-006, M0-008, M0-009, M0-010, M0-011, M0-012, M0-013, M0-014, M0-015, M0-016, M0-017, M0-018, M0-019, M0-SYSTEM, M0-TRIAL-1 |
| Purpose / source requirement | Own mandatory check profiles and immutable full-context assignments, minimize verifier disclosure, enforce deterministic then semantic assessment, validate exact subject and durably decide release. Sources: 2.8, 4.2, 4.2.1, 4.2.2, 4.2.3, 4.2.4, 4.2.5, 4.2.6, 4.2.7, 4.2.8, 4.2.9, 4.2.10, 4.3.4, 5.2.1 |
| Inputs: fields, types, units, required/optional, validation | BoundVerificationSubject: exact contract/output/input/evidence/CC and invocation references; immutable guard/profile/rubric/check/source pins; observed runtime facts; protected permitted disclosure context. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | VerificationVerdictAndGateDecision: tier_1 checks; tier_2 structured assessment with reasons/evidence_refs; exact subject binding; final gate_verdict PASS/PASS_WITH_KNOWN_LIMITATIONS/FAIL/ENVIRONMENT_BLOCKED/INCONCLUSIVE; normalized verdict; ADVANCE/HALT/ESCALATE_TO_HUMAN action; immutable durable decision receipt. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-007.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-007/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | SRC-GATE: Legacy semantic quality refusal rule and fallback/retry defaults conflict with current mandatory gate and D4.; Q-CALIBRATION: Real semantic calibration corpus and quantitative reliability threshold are not supplied.; Q-UPSTREAM-RUBRICS: Required result-evaluator and citation-reviewer source bodies and exact upstream revision are absent from this checkout. |

Primary capsule identity and initialization consume [the canonical M0-003 responsibility/seeding mapping](../M0-003/TASK.md#primary-capability-registry-and-seeding); this TASK retains its owned node/function/interface rather than redefining the library registry.

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-001@r1](../M0-001/TASK.md#m0-if-001-at-r1); [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| SRC-GATE / 2026-10-06 | Legacy semantic quality refusal rule and fallback/retry defaults conflict with current mandatory gate and D4. | All check assignments and release behavior | Affected linked AC/B/V; no prior runtime evidence to reuse. | Current PRD 1.4/4.2 and D2/D4/D15 govern; old schema epochs are compatibility context and never runtime permission. |
| Q-CALIBRATION / 2026-10-06 | Real semantic calibration corpus and quantitative reliability threshold are not supplied. | Semantic characterization, profile admission and real semantic acceptance claims; deterministic lock assertions can proceed independently. | Affected linked AC/B/V; no prior runtime evidence to reuse. | Freeze independent labelled dataset/rubric and justified development acceptance criterion before candidate measurement; preserve false acceptance/refusal, counts and provider correlation; deterministic lock assertions remain executable independently. |
| Q-UPSTREAM-RUBRICS / 2026-10-06 | Required result-evaluator and citation-reviewer source bodies and exact upstream revision are absent from this checkout. | AC-010, adaptation/calibration/admission and all dependent live Tier-2 profile acceptance | Affected linked AC/B/V; no prior runtime evidence to reuse. | Obtain the authorized exact upstream snapshots, pin revision/content identity, map applicable checks and justified exclusions in the owning native plan/profile support record, then execute the declared adaptation cases before acceptance. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
