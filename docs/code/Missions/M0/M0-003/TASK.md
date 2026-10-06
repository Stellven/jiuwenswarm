# TASK: M0-003 — Trial capsule declarations and admitted two-definition library

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-003 / r3 / 2026-10-06 |
| Parent | [M0 joint Phase 1 / TRIAL-1 register](../TASKS.md) |
| Executor | Codex; bounded current trial implementation, collaborators assigned with disjoint code ownership |
| Current outcome | Support only TRIAL-1 by packaging, admitting, human-activating and pinning the intent compiler and intent verifier as exactly two authored CCs. Preserve the declaration inventory through an explicit versioned trial profile and applicability/future disposition. Retain M0-003 and M0-IF-003 identities; broad r1 is historical future context. |
| Excluded work | No full research-stage registry/seeding, live creation/import/installation, composite execution, dynamic discovery, RSI generation/mutation/evolution execution, fusion, mid-run substitution, external publishing, third-party certification or general library-management UI. Preserved metadata does not enable a deferred mechanism. |
| Current source authorities | [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective / recorded source manifest |
| Product clause references / architecture interpretation | PRD 4.1.1, 4.1.2; immediate-plan.md, capsule/declaration.md, capsule/authoring.md, capsules.md, guard-design.md, sources/capsule.schema.json, sources/capsule-semantic-v2.10b.md, sources/policy-m1.json, principles.md; exact Phase 1 allocation is in source-coverage.json; other delivery phases are not activated |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | `jiuwenswarm/ai4research/capsules.py`; `jiuwenswarm/ai4research/service.py`; `jiuwenswarm/ai4research/declaration/library/intent_compiler.json`; `jiuwenswarm/ai4research/declaration/library/intent_verifier.json`; `jiuwenswarm/ai4research/declaration/library/README.md`; `tests/unit_tests/ai4research/test_m0_003.py`; `tests/integration_tests/ai4research/test_m0_003_boundary.py`; `jiuwenswarm/ai4research/admission.py`; `tests/unit_tests/ai4research/test_definition_admission.py` |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-003 | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-003/evidence/ | Actual observed runs; preserve historical r1 separately |
| Support | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md) | Context only; no independent interface/acceptance authority |

## 3. Dependencies

| TASK / IF | Required contribution | Prerequisite scope | Work |
| --- | --- | --- | --- |
| [M0-002](../M0-002/TASK.md); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2) | TRIAL-1 local identity, session authority and frozen configuration | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

### M0-IF-003 at r2

| Property | Definition |
| --- | --- |
| Provider and consumers | M0-003; consumers: M0-004, M0-006, M0-007, M0-SYSTEM, M0-TRIAL-1 |
| Purpose | Support only TRIAL-1 by packaging, admitting, human-activating and pinning the intent compiler and intent verifier as exactly two authored CCs. Preserve the declaration inventory through an explicit versioned trial profile and applicability/future disposition. Retain M0-003 and M0-IF-003 identities; broad r1 is historical future context. |
| Inputs | TrialCapsuleCandidate: exact declaration and prompt/code/profile/dependency closure for intent compiler or intent verifier; actual admission/development evidence; authenticated human standing action. References validate exact SHA256, type/schema and run/subject attribution. Counts are integers, durations seconds, timestamps UTC. |
| Outputs | PinnedTrialDefinitions: two eligible read-only pinned definitions; declaration/closure hashes and interface revision; admission/standing history; compatibility fields never grant execution. Required identities are nonempty strings; optional unavailable telemetry has an explicit reason, never assumed zero. |
| States/invariants | Candidate differs from accepted. Two immutable CC pins; producer/verifier context separation; authority derives from host, not candidate fields. Required durable decision precedes exposure. |
| Errors/timeout/retry/cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable. Zero automatic compiler repair/replay; verifier malformed/uncertain cannot release. Cancellation differs from restart interruption. |
| Effects/idempotency | Only declared bounded model access and protected infrastructure writes. Client request reconciliation never re-executes uncertain work; changed payload under same identity is rejected. No tools/browsing/shell/POC/RSI effects. |
| Compatibility | Retained IF identity, scoped r2 implemented representation; required live evidence remains pending. Historical full-M1 r1 is context, not a live API. Required additional Phase 1 mechanisms need owned versioned contracts and affected verification; their product scope is already active. Separately phased mechanisms remain contextual. |
| Implementation schema | capsules.py defines SCHEMA_REVISION 2.11, FIELD_DISPOSITION, validate_declaration and CapsulePin; admission.py validates the protected local definition-admission-r2 receipt with exact declaration pins, retained no-skip self-test JUnit and independent scoped definition-review-r2 evidence. The service --admission-receipt input has no HTTP setter and cannot certify semantic acceptance or authorize runtime release. Packaged declaration/library templates hydrate exact source hashes without admission. Paths are relative to jiuwenswarm/ai4research unless fully qualified. The owning r2 IF remains canonical; no parallel schemas/*.schema.json is generated. |
| Boundary verification | Provider odd V IDs, connected even V IDs in this plan; current SYSTEM candidate covers integration |
| Unresolved inputs | SRC-SCHEMA: The legacy machine schema and semantic inventory disagree on shapes/requiredness and policy epochs.; SCOPE-TWO-CCS: The broad r1 primary registry covers research-stage aliases not exercised by the trial. |

### Two trial definitions

Only `intent_compiler` and `intent_verifier` are authored, admitted, activated and seeded. Each has capsule.json, pinned prompt/code/check/profile/dependency resources, typed ports and its current IF revision. An unimplemented research-stage alias or composite is rejected by the current executable trial profile. Required Phase 1 research capabilities remain active SYSTEM work, with owned admission/contracts before execution. Detailed package resources are owned here; fidelity rubric is owned by M0-007.

Consumed agreements: [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2). Runtime connections do not add broad implementation dependencies.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-05 | Joint PRD Phase 1 / TRIAL-1 scope confirmation | Program allocation and component interpretation | r3 restores active product obligations under SYSTEM; implemented r2 IF and unchanged trial predicates are retained. USR-04 sole-authority interpretation is superseded. |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| SRC-SCHEMA | Legacy machine schema and semantic inventory disagree on shapes/requiredness and policy epochs; the supported trial representation is now selected. | AC-001 and the trial reader/closure | Resolved implementation: capsules.py SCHEMA_REVISION 2.11, FIELD_DISPOSITION and validate_declaration define canonical trial requiredness and explicit contextual/future field disposition. Exact two packaged declarations bind current source closures; ambiguous authority and future executable fields are refused. Source files remain unchanged; no migration is required by current trial inputs. |
| SCOPE-TWO-CCS | The archived r1 registry covers research-stage aliases outside immediate-plan; active seeding is now bounded. | AC-002 and startup seeding | Resolved implementation: CapsuleLibrary.seed_builtin loads only intent_compiler.json and intent_verifier.json. service.py consumes a protected local admission.py receipt bound to both exact declaration hashes, observed no-skip structural self-tests and independent scoped definition review; missing/stale receipt leaves definitions unadmitted. This provisional eligibility and initial authorized human standing are distinct from real connected trial acceptance. |

Historical criteria outside the active slice:

| Historical AC | Reason/disposition |
| --- | --- |
| AC-005 | Retired criterion concerns Phase 2 RSI or Phase 3 dynamic execution outside the selected Phase 1 target. Applicable frozen-referee/security prohibitions remain active under SYSTEM AC-027; no execution or PASS is allocated here. |
| AC-006 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-019, M0-SYSTEM/AC-027. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |

The sole work/evidence state is tasks.md. Current coding is authorized; commits/pushes/deployment are not.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
