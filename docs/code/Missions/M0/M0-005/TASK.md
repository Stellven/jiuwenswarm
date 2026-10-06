# TASK: M0-005 — TRIAL-1 durable state, exact evidence custody and minimal observations

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-005 / r3 / 2026-10-06 |
| Parent | [M0 joint Phase 1 / TRIAL-1 register](../TASKS.md) |
| Executor | Codex; bounded current trial implementation, collaborators assigned with disjoint code ownership |
| Current outcome | Provide only the run-state, immutable artifact/evidence files, portable trial records/bundles and minimal attributable observations required by the connected text-only Intent compiler and protected Verifier slice. Persist the original request, fixed intent-node contract, separately assigned verifier context, two CC closure pins, frozen requested/effective configuration, attempts, checks, candidate, raw assessment, gate decision and exact accepted reference or halt. Preserve restart, cancellation and request reconciliation without replay. PRD Phase 1 and TRIAL-1 jointly govern the program; this responsibility is the implemented Intent contribution, with remaining Phase 1 data obligations owned by SYSTEM AC-019/AC-025/AC-027. |
| Excluded work | No Research Brief or research graph, later research stages, agent-memory integration, resource profiling, continuous utilization capture, broad capsule scorecards, general trace-search service, RSI sample exports, synthetic run generation, hidden-fixture handling, distributed graph subsystem or complete-M1 acceptance. Native UI/headless business behavior belongs to M0-TRIAL-1; this task supplies authoritative state and inspectable evidence without creating another application. |
| Current source authorities | [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective / recorded source manifest |
| Product clause references / architecture interpretation | PRD 2.10, 4.5.2, 4.5.3, 4.6.1, 4.6.2, 4.6.3, 4.6.4, 5.1.1, 5.1.2; immediate-plan.md, placement.md, guard-design.md, failure-and-human.md, automation.md; exact Phase 1 allocation is in source-coverage.json; other delivery phases are not activated |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | `jiuwenswarm/ai4research/state.py`; `jiuwenswarm/ai4research/evidence.py`; `tests/unit_tests/ai4research/test_m0_005.py`; `tests/integration_tests/ai4research/test_m0_005_boundary.py` |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-005 | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-005/evidence/ | Actual observed runs; preserve historical r1 separately |
| Support | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md) | Context only; no independent interface/acceptance authority |

## 3. Dependencies

| TASK / IF | Required contribution | Prerequisite scope | Work |
| --- | --- | --- | --- |
| [M0-002](../M0-002/TASK.md); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2) | TRIAL-1 local identity, session authority and frozen configuration | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

### M0-IF-005 at r2

| Property | Definition |
| --- | --- |
| Provider and consumers | M0-005; consumers: M0-001, M0-002, M0-003, M0-004, M0-006, M0-007, M0-SYSTEM, M0-TRIAL-1 |
| Purpose | Provide only the run-state, immutable artifact/evidence files, portable trial records/bundles and minimal attributable observations required by the connected text-only Intent compiler and protected Verifier slice. Persist the original request, fixed intent-node contract, separately assigned verifier context, two CC closure pins, frozen requested/effective configuration, attempts, checks, candidate, raw assessment, gate decision and exact accepted reference or halt. Preserve restart, cancellation and request reconciliation without replay. PRD Phase 1 and TRIAL-1 jointly govern the program; this responsibility is the implemented Intent contribution, with remaining Phase 1 data obligations owned by SYSTEM AC-019/AC-025/AC-027. |
| Inputs | TrialEvidenceCommit: original/candidate/assessment/decision bytes and type; run/node/attempt/invocation; SHA256/schema/profile/CC identity, audience and idempotency key. References validate exact SHA256, type/schema and run/subject attribution. Counts are integers, durations seconds, timestamps UTC. |
| Outputs | StoredTrialEvidence: immutable refs {artifact_id,run_id,type,schema_revision,sha256,locator}; durable receipt; accepted reference only after exact decision commit; trace and permitted bundle. Required identities are nonempty strings; optional unavailable telemetry has an explicit reason, never assumed zero. |
| States/invariants | Candidate differs from accepted. Two immutable CC pins; producer/verifier context separation; authority derives from host, not candidate fields. Required durable decision precedes exposure. |
| Errors/timeout/retry/cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable. Zero automatic compiler repair/replay; verifier malformed/uncertain cannot release. Cancellation differs from restart interruption. |
| Effects/idempotency | Only declared bounded model access and protected infrastructure writes. Client request reconciliation never re-executes uncertain work; changed payload under same identity is rejected. No tools/browsing/shell/POC/RSI effects. |
| Compatibility | Retained IF identity, scoped r2 implemented representation; required live evidence remains pending. Historical full-M1 r1 is context, not a live API. Required additional Phase 1 mechanisms need owned versioned contracts and affected verification; their product scope is already active. Separately phased mechanisms remain contextual. |
| Implementation schema | state.py defines RunStore and exact refs {interface_revision,artifact_id,run_id,type,schema_revision,sha256,locator}; evidence.py derives attributable bundles. Gate authority is nonserialized object identity. Paths are relative to jiuwenswarm/ai4research unless fully qualified. The owning r2 IF remains canonical; no parallel schemas/*.schema.json is generated. |
| Boundary verification | Provider odd V IDs, connected even V IDs in this plan; current SYSTEM candidate covers integration |
| Unresolved inputs | Q-TRIAL-CUSTODY-INTEGRATION: Which exact protected gate authority, artifact wire representation and caller/audience context implement the registered trial interfaces on the candidate?; Q-TRIAL-REAL-OBSERVATIONS: Is the approved authenticated actual bridge and its protected local/container execution boundary ready to supply real trial call evidence? |

Consumed agreements: [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2). Runtime connections do not add broad implementation dependencies.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-05 | Joint PRD Phase 1 / TRIAL-1 scope confirmation | Program allocation and component interpretation | r3 restores active product obligations under SYSTEM; implemented r2 IF and unchanged trial predicates are retained. USR-04 sole-authority interpretation is superseded. |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| Q-TRIAL-CUSTODY-INTEGRATION | The protected gate capability, immutable artifact representation and attributable store integration are implemented; final candidate-linked observations are pending. | AC-001/002/003/007 boundary checks | Resolved implementation: RunStore receives a host-only object capability; ArtifactRef binds revision, artifact/run/type/schema, exact SHA256 and immutable locator. Authenticated user/workspace context scopes inspect/bundle/cancel. Runner captures prompts/observations/output attempts; host gate commits decision and accepted exact candidate in one SQLite transaction before projection. Local real SQLite/files/process failures and scripted connected tests exist; their final frozen evidence is NOT_RUN and required native provider/container observations remain BLOCKED. |
| Q-TRIAL-REAL-OBSERVATIONS | Is the approved authenticated actual bridge and its protected local/container execution boundary ready to supply real trial call evidence? | Actual compiler/verifier evidence assertions in AC-003/007 and corresponding SYSTEM checks | Consume M0-001/M0-002 readiness for the same candidate; retain local custody tests as local evidence and leave unavailable real-model observations BLOCKED, never infer usage or claim model-backed acceptance from a stub. |

Historical criteria outside the active slice:

| Historical AC | Reason/disposition |
| --- | --- |
| AC-004 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-019, M0-SYSTEM/AC-025. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |
| AC-005 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-019, M0-SYSTEM/AC-025. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |
| AC-006 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-019. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |

The sole work/evidence state is tasks.md. Current coding is authorized; commits/pushes/deployment are not.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
