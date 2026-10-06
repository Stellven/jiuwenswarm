# TASK: M0-010 — Bounded evidence retrieval and grounded candidate ideation

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-010 / r1 / 2026-10-06 |
| Parent TASKS | [M0 program register](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepared English records and source allocation |
| Requested outcome and instruction/source | Search permitted local context and designated academic connectors under a fixed query plan, retain exact source excerpts and produce one to three evidence-linked candidates for Screening. User requests a complete local English Spec Kit system and two architecture prose clarifications. |
| Included scope / exclusions | Search permitted local context and designated academic connectors under a fixed query plan, retain exact source excerpts and produce one to three evidence-linked candidates for Screening. Exclusions: No unrestricted web scraping, headless crawling, dynamic query reformulation, search swarms, authority/bias/geography assessment, historical trend mapping, unsupported speculation or recursive coverage repair. |
| PRD clause and architecture node references | PRD 2.4 (../source/PRD - AI4Research.txt:L467-L485); PRD 3.3 (../source/PRD - AI4Research.txt:L810-L813); PRD 3.3.1 (../source/PRD - AI4Research.txt:L814-L822); PRD 3.3.2 (../source/PRD - AI4Research.txt:L823-L834); PRD 3.3.3 (../source/PRD - AI4Research.txt:L835-L841); PRD 3.3.4 (../source/PRD - AI4Research.txt:L842-L848); PRD 3.3.5 (../source/PRD - AI4Research.txt:L849-L856); PRD 3.3.6 (../source/PRD - AI4Research.txt:L857-L867); PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354); PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513); PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327); architecture m1-design.md, workflow.md, contracts-and-native-reuse.md, guard-design.md, placement.md, failure-and-human.md, capsules.md; baselines in parent source-manifest.json |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861; uncommitted document preparation; product NOT_STARTED |
| Affected code/document paths | jiuwenswarm/agents/harness/common/tools/search_tools.py; jiuwenswarm/agents/harness/common/tools/trusted_search_tool_adapter.py; jiuwenswarm/server/runtime/agent_adapter/trusted_web_search.py; jiuwenswarm/ai4research/search_ideation.py (proposed); tests/unit_tests/ai4research/test_search_ideation.py (proposed); tests/integration_tests/ai4research/test_search_ideation_boundary.py (proposed); tests/fixtures/ai4research/search_ideation/calibration_manifest.json (proposed) |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M0/M0-010/ | One TASK, one colocated directory |
| spec.md | [specification](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Blocks, technical decisions and verification procedures |
| tasks.md | [work/evidence](tasks.md) | Sole implementation work/progress and evidence correspondence |
| evidence/ | docs/code/Missions/M0/M0-010/evidence/ | Actual observations; no runtime result yet |
| Supporting artifacts | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md), [diagnostic](checklists/requirements.md) | Subordinate context, not duplicated acceptance or interfaces |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M0-009](../M0-009/TASK.md) / [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1) | Research Brief compilation from independently accepted intent | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-008](../M0-008/TASK.md) / [M0-IF-008@r1](../M0-008/TASK.md#m0-if-008-at-r1) | Qualified intake and attributable local resource binding | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-003](../M0-003/TASK.md) / [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1) | Capability declarations and admitted library | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-004](../M0-004/TASK.md) / [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1) | Governed capsule runner and enforced effects | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-005](../M0-005/TASK.md) / [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1) | Durable run state, evidence and derived observability | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-006](../M0-006/TASK.md) / [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1) | Protected contracts, static graph and gate-locked scheduling | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |
| [M0-007](../M0-007/TASK.md) / [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1) | Protected guard profiles, Verifier and durable release | Definition r1 can be consumed for fixture/design preparation; actual acceptance requires valid real producer evidence for the same candidate. | Applicable B/V rows; T001–T002 and connected checks |

Definition-time prerequisites are the registered r1 semantic agreements, not completed teammate implementations. Runtime connections additionally need actual runner, custody, protected gate and applicable services. Their mutual calls do not create a definition-time DAG cycle. Independent fixture/source preparation can continue when a runtime dependency is unavailable. Runtime-only consumer/provider links are indexed separately below and do not create completion dependencies.

## 4. Embedded cross-module agreements

### M0-IF-010 at r1

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M0-010; consumers: M0-011, M0-SYSTEM |
| Purpose / source requirement | Search permitted local context and designated academic connectors under a fixed query plan, retain exact source excerpts and produce one to three evidence-linked candidates for Screening. Sources: 2.4, 3.3, 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5, 3.3.6, 4.2.1, 4.2.6, 5.2.1 |
| Inputs: fields, types, units, required/optional, validation | AcceptedResearchBrief: accepted Brief; permitted local buffer and approved academic connectors; static keyword/query plan; strict configured Top-K; immutable retrieved source refs. Required references validate type, schema revision, exact SHA256 and run scope; optional values are explicit null/unavailable with reason, never implicit success. |
| Outputs: fields, types, units, semantics, guarantees | Candidate_Set.json: one to three candidates with concrete mechanisms, exact citations/source chunks and query grouping; warnings/coverage; all source provenance; no fabricated facts or recursive search. Identity fields are required strings, counts integers, durations seconds, timestamps UTC ISO8601. Artifact references use M0-IF-005@r1. |
| States and invariants | Candidate and accepted are distinct; immutable pinned identity; all required inputs attributable; each CC authority intersects admitted/node/run scopes. Source-specific state behavior is verified by the linked spec; no producer self-certified release. |
| Errors, timeout, retry, cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable; runtime gate maps faults under M0-IF-007. Zero autonomous work retries/replay. Headless never waits. An unsupported failure class must be defined before boundary implementation. |
| Side effects and idempotency | Only explicitly permitted resource effects and protected owner writes; client request/commit identity is reconciled without re-executing uncertain work. Changed payload under same request identity is rejected. Cancellation never claims prior effects undone. |
| Compatibility and migration | r1 is the current proposed implementation agreement, not an existing implemented wire API. JSON UTF-8 boundary objects use explicit interface_revision and supported schema revision; reject unknown authority-bearing fields. Material change requires r2, updated consumers and invalidated checks. Historical sources/versions remain unchanged. |
| Machine-readable schema / source path | Proposed owning implementation schema under jiuwenswarm/ai4research/schemas/m0-010.schema.json; not generated/implemented by this documentation request. Source data models and capsule sources constrain meaning; TASK agreement is canonical. |
| Provider/consumer verification responsibilities | M0-010/plan.md odd V IDs verify provider blocks; even V IDs verify connected real boundaries with consuming owners; M0-SYSTEM verifies integrated stage exits. |
| Open agreement questions | Q-SEARCH-OPERATOR: The current repository has generic search helpers but no inspected deepsearch capsule implementation or academic connector contract.; Q-SEARCH-LIMIT: PRD maximum five papers is illustrative and exact query/Top-K limits are unsupplied. |

Primary capsule identity and initialization consume [the canonical M0-003 responsibility/seeding mapping](../M0-003/TASK.md#primary-capability-registry-and-seeding); this TASK retains its owned node/function/interface rather than redefining the library registry.

Consumed agreements (definition and runtime links; no copied definitions): [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-004@r1](../M0-004/TASK.md#m0-if-004-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1); [M0-IF-006@r1](../M0-006/TASK.md#m0-if-006-at-r1); [M0-IF-007@r1](../M0-007/TASK.md#m0-if-007-at-r1); [M0-IF-008@r1](../M0-008/TASK.md#m0-if-008-at-r1); [M0-IF-009@r1](../M0-009/TASK.md#m0-if-009-at-r1). Shared custody, check/gating and contract agreements apply according to the runtime boundary, independently of implementation-order prerequisites.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-SEARCH-OPERATOR / 2026-10-06 | The current repository has generic search helpers but no inspected deepsearch capsule implementation or academic connector contract. | Real operator/connector integration | Affected linked AC/B/V; no prior runtime evidence to reuse. | Inspect installed dependency and admitted operator source; freeze exact adapter/version/allowlist. Prepare mocked bounded connector tests independently, but do not claim real integration before evidence. |
| Q-SEARCH-LIMIT / 2026-10-06 | PRD maximum five papers is illustrative and exact query/Top-K limits are unsupplied. | Retrieval/count/time boundary tests | Affected linked AC/B/V; no prior runtime evidence to reuse. | Define finite approved profile bounds and freeze them before verification; record actual configured values rather than inventing PRD numbers. |
| USR-01/02 / 2026-10-06 | Architecture verification/gating and required upstream rubric adaptation prose clarifications | All consuming semantic profiles / M0-IF-007@r1 | No scope or identity change; ensure exact adopted logic mapping before live acceptance. | Preserve protected gate authority and frozen criteria; record source revision/disposition in M0-007. |

Progress and observations remain in tasks.md. This TASK does not authorize commits, pushes, live provider campaigns or deployment. Material scope/interface changes update parent allocation and affected native artifacts.
