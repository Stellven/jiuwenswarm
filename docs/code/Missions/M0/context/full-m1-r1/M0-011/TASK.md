# TASK: M0-011 — Fixed-rubric screening and deterministic Top-1 ranking

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-011 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Consolidate admitted candidates once, form evidence-linked opportunity cards, score fixed dimensions, filter unavailable dependencies and select the deterministic highest-scoring opportunity with rejection reasons and a pure rank_opportunities seam for isolated RSI. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Consolidate admitted candidates once, form evidence-linked opportunity cards, score fixed dimensions, filter unavailable dependencies and select the deterministic highest-scoring opportunity with rejection reasons and a pure rank_opportunities seam for isolated RSI. Exclusions: No new brainstorming, iterative clustering, commercial ROI/market/legal/patent analysis, live feasibility execution, multi-agent voting, human selection or production RSI mutation. |
| PRD clause and architecture node references | PRD 3.4 (../source/PRD - AI4Research.txt:L868-L873); PRD 3.4.1 (../source/PRD - AI4Research.txt:L874-L883); PRD 3.4.2 (../source/PRD - AI4Research.txt:L884-L890); PRD 3.4.3 (../source/PRD - AI4Research.txt:L891-L897); PRD 3.4.4 (../source/PRD - AI4Research.txt:L898-L904); PRD 3.4.5 (../source/PRD - AI4Research.txt:L905-L916); PRD 3.4.6 (../source/PRD - AI4Research.txt:L917-L923); PRD 3.4.7 (../source/PRD - AI4Research.txt:L924-L937); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 4.4.3 (../source/PRD - AI4Research.txt:L1837-L1858); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md, offline-rsi.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/agents/harness/common/tools/skill_toolkits.py; jiuwenswarm/agents/harness/common/prompt/prompt_builder.py; jiuwenswarm/ai4research/screening.py (proposed); tests/unit_tests/ai4research/test_screening.py (proposed); tests/integration_tests/ai4research/test_screening_boundary.py (proposed); tests/fixtures/ai4research/screening/calibration_manifest.json (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-011/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-011/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-010](../M0-010/TASK.md) / [M0-IF-010@r1](../M0-010/TASK.md#m0-if-010-at-r1) | Bounded evidence retrieval and grounded candidate ideation | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-009](../M0-009/TASK.md) / [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1) | Research Brief compilation from independently accepted intent | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-004](../M0-004/TASK.md) / [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1) | Governed capsule runner and enforced effects | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-006](../M0-006/TASK.md) / [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1) | Protected contracts, static graph and gate-locked scheduling | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-007](../M0-007/TASK.md) / [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1) | Protected guard profiles, Verifier and durable release | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-011 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-011; consumers: M0-012, M0-018, M0-SYSTEM |
| Purpose / source requirement | Consolidate admitted candidates once, form evidence-linked opportunity cards, score fixed dimensions, filter unavailable dependencies and select the deterministic highest-scoring opportunity with rejection reasons and a pure rank_opportunities seam for isolated RSI. Sources: 3.4, 3.4.1, 3.4.2, 3.4.3, 3.4.4, 3.4.5, 3.4.6, 3.4.7, 4.2.1, 4.2.6, 4.4.3, 5.2.1 |
| Inputs: fields, types, units, required/optional, validation | AcceptedCandidateSet: accepted 1-3 candidates; Brief hardware/dependency constraints; pinned single-turn work rubric. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | Opportunity_Card.json: one selected opportunity; three integer 1-5 dimensions Novelty/Feasibility/ComputeAlignment and per-score evidence justification; deterministic summed score/tie disposition; candidate/rejection/deferral provenance; pure rank helper input/output fixed. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-011.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-011/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Q-RANK-TIES: PRD specifies summed Top-1 but not tie, missing-score and no-eligible-card serialization.; SRC-RSI-RUBRIC: Optional work-rubric mutation can mention weights/scales while production screening fixes dimensions/sum. |

Primary capsule identity and initialization consume [the canonical M0-003 responsibility/seeding mapping](../M0-003/TASK.md#primary-capability-registry-and-seeding); this TASK retains its owned node/function/interface rather than redefining the library registry.

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1); [M0-IF-010@r1](../M0-010/TASK.md#m0-if-010-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-RANK-TIES / 2026-10-06 | PRD specifies summed Top-1 but not tie, missing-score and no-eligible-card serialization. | Deterministic helper boundary and RSI target contract | Affected linked AC/B/V; no prior runtime evidence to reuse. | Own a fixed transparent tie/error contract before implementation and fixtures. Highest-score Top-1 and fail-fast missing mandatory input remain invariant; no new numeric threshold. |
| SRC-RSI-RUBRIC / 2026-10-06 | Optional work-rubric mutation can mention weights/scales while production screening fixes dimensions/sum. | RSI target compatibility | Affected linked AC/B/V; no prior runtime evidence to reuse. | M0-018 target declaration must preserve incoming required dimensions, sum/Top-1 output/interface and referee; text target permission does not authorize production or gate-policy change. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
