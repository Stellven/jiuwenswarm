# TASK: M0-002 — TRIAL-1 local identity, session authority and frozen configuration

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-002 / r3 / 2026-10-06 |
| Parent | [M0 joint Phase 1 / TRIAL-1 register](../TASKS.md) |
| Executor | Codex; bounded current trial implementation, collaborators assigned with disjoint code ownership |
| Current outcome | Supply only the supporting identity, authentication and effective-configuration boundary required by immediate-plan.md for the connected original-text Intent compiler CC -> Intent Verifier CC trial. Maintain a stable protected local product-user identifier and minimal durable defaults separate from run/workspace lifetime; authenticate the authorized local execution context; freeze the two admitted implementation pins, static baseline model-role assignments, fidelity/check profile, mode and finite time/call limits before dispatch. Native Web and the minimal sequential headless driver consume this boundary through the integrated M0-TRIAL-1 application use case. Preserve requested versus effective configuration and model/seed/telemetry limitations without claiming a mock establishes real bridge readiness. |
| Excluded work | No full account-registration or profile-administration product, cloud identity/profile service, enterprise authentication, multi-user switching, shared projects, broader export/delete/retention/privacy product flow, document/assets intake, full Research Brief, installer/doctor product, operational shell, interactive CLI/TUI, tmux, campaign dashboard, advanced compiler, dialogue, planner, dynamic model routing, alternate experimental provider execution, distributed workers, RSI, scientific workflow or full-M1/stage acceptance. Do not add semantic requirements from profile history or silently import prior research. Original request and permitted trial evidence retrieval, local session isolation and secret minimization remain required under retained acceptance cases; deferring AC-003 does not authorize unrestricted access or secret disclosure. |
| Current source authorities | [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective / recorded source manifest |
| Product clause references / architecture interpretation | PRD 2.3, 4.5.2, 5.4.1, 5.4.2, 5.6, 5.6.1, 5.6.2, 5.6.3, 5.6.4, 5.6.5; immediate-plan.md, placement.md, principles.md, automation.md, failure-and-human.md, capsules.md, guard-design.md; exact Phase 1 allocation is in source-coverage.json; other delivery phases are not activated |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | `jiuwenswarm/ai4research/identity.py`; `jiuwenswarm/ai4research/configuration.py`; `jiuwenswarm/ai4research/http.py`; `jiuwenswarm/ai4research/application.py`; `tests/unit_tests/ai4research/test_m0_002.py`; `tests/integration_tests/ai4research/test_m0_002_boundary.py` |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-002 | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-002/evidence/ | Actual observed runs; preserve historical r1 separately |
| Support | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md) | Context only; no independent interface/acceptance authority |

## 3. Dependencies

| TASK / IF | Required contribution | Prerequisite scope | Work |
| --- | --- | --- | --- |
| [M0-001](../M0-001/TASK.md); [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2) | Audited Codex model bridge | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

### M0-IF-002 at r2

| Property | Definition |
| --- | --- |
| Provider and consumers | M0-002; consumers: M0-003, M0-004, M0-005, M0-SYSTEM, M0-TRIAL-1 |
| Purpose | Supply only the supporting identity, authentication and effective-configuration boundary required by immediate-plan.md for the connected original-text Intent compiler CC -> Intent Verifier CC trial. Maintain a stable protected local product-user identifier and minimal durable defaults separate from run/workspace lifetime; authenticate the authorized local execution context; freeze the two admitted implementation pins, static baseline model-role assignments, fidelity/check profile, mode and finite time/call limits before dispatch. Native Web and the minimal sequential headless driver consume this boundary through the integrated M0-TRIAL-1 application use case. Preserve requested versus effective configuration and model/seed/telemetry limitations without claiming a mock establishes real bridge readiness. |
| Inputs | AuthenticatedTrialContext: host-derived product user/workspace/session authority; approved profile ID; allowlisted per-run options and requested seed. References validate exact SHA256, type/schema and run/subject attribution. Counts are integers, durations seconds, timestamps UTC. |
| Outputs | FrozenTrialProfile: effective precedence/settings and fingerprint; actual requested/effective seed support; positive time/call limits; protected static roles and audience, no credentials. Required identities are nonempty strings; optional unavailable telemetry has an explicit reason, never assumed zero. |
| States/invariants | Candidate differs from accepted. Two immutable CC pins; producer/verifier context separation; authority derives from host, not candidate fields. Required durable decision precedes exposure. |
| Errors/timeout/retry/cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable. Zero automatic compiler repair/replay; verifier malformed/uncertain cannot release. Cancellation differs from restart interruption. |
| Effects/idempotency | Only declared bounded model access and protected infrastructure writes. Client request reconciliation never re-executes uncertain work; changed payload under same identity is rejected. No tools/browsing/shell/POC/RSI effects. |
| Compatibility | Retained IF identity, scoped r2 implemented representation; required live evidence remains pending. Historical full-M1 r1 is context, not a live API. Required additional Phase 1 mechanisms need owned versioned contracts and affected verification; their product scope is already active. Separately phased mechanisms remain contextual. |
| Implementation schema | identity.py defines host-derived AuthenticatedTrialContext and protected identity/session custody; configuration.py validates trial options and detached immutable FrozenTrialProfile. Paths are relative to jiuwenswarm/ai4research unless fully qualified. The owning r2 IF remains canonical; no parallel schemas/*.schema.json is generated. |
| Boundary verification | Provider odd V IDs, connected even V IDs in this plan; current SYSTEM candidate covers integration |
| Unresolved inputs | TRIAL-LOCAL-IDENTITY: Does the trial need to build a new remote account system or complete account registration/profile administration?; TRIAL-MODEL-SEED: Which model IDs and effective seed are established before real trial execution?; TRIAL-OWNING-INTEGRATION: Does M0-002 own the entire native Web/headless shell or direct model-runner entry points? |

Consumed agreements: [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2). Runtime connections do not add broad implementation dependencies.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-05 | Joint PRD Phase 1 / TRIAL-1 scope confirmation | Program allocation and component interpretation | r3 restores active product obligations under SYSTEM; implemented r2 IF and unchanged trial predicates are retained. USR-04 sole-authority interpretation is superseded. |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| TRIAL-LOCAL-IDENTITY | Does the trial need to build a new remote account system or complete account registration/profile administration? | AC-001, AC-002; exact portion of PRD 5.4.1 used by TRIAL-1 | No. immediate-plan requires stable product-user/workspace/run attribution; placement.md permits a protected local persistent baseline and requires no cloud vendor. Implement only host-provisioned stable local product identity/defaults and protected session binding. Preserve full verified-account product obligations as active SYSTEM AC-025 work outside this implemented trial component; do not present an OS identifier, generated session token or Codex model login as completed product account registration. |
| TRIAL-MODEL-SEED | Which model IDs and effective seed are established before real trial execution? | AC-004, AC-005, AC-006; model readiness and reproducibility evidence | Do not invent IDs or assume seed support. Resolve static role selections from the authenticated native bridge's supported-model discovery and retain observed/requested distinctions in the frozen manifest. Existing SubscriptionService.stream has no seed argument, so native effective seed is unavailable. Actual authenticated bridge/container readiness and connected call evidence remain NOT_RUN or BLOCKED until demonstrated; labeled mocks prove wiring only. |
| TRIAL-OWNING-INTEGRATION | Does M0-002 own the entire native Web/headless shell or direct model-runner entry points? | AC-001 through AC-006; authority and dependent integration | No. M0-002 owns only minimal identity/session/configuration authority. M0-TRIAL-1 owns original-text intake, one application boundary, native Web and minimal sequential headless use-case integration, submission reconciliation and connected two-CC lifecycle. Clients cannot directly invoke the runner or write gate state. No full shell, installer, TUI, tmux, RSI or advanced compiler is introduced. |

Historical criteria outside the active slice:

| Historical AC | Reason/disposition |
| --- | --- |
| AC-003 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-025, M0-SYSTEM/AC-027. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |

The sole work/evidence state is tasks.md. Current coding is authorized; commits/pushes/deployment are not.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
