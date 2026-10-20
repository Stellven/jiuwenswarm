# Feature Specification: M1-007 - Isolated API model router
**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r3 / 2026-10-16
**Feature Branch**: ai4r_M1
**Input**: [Exact source baseline](../source-baseline.json); Registered M1-007/TASK.md §§1,3–5; TASKS.md §4 reserves M1-IF-008; consumes M1-IF-001 and protected selected-Capsule context from M1-002.; source/PRD/PRD_Oct_15.md §§4.3.1–4.3.4, 6.12 Heterogeneous Model Routing.; source/Architecture_Design/reference/model-routing-contract.md; side-systems/router-design.md; side-systems/model-catalog.md; side-systems/model-routing.md RTR-1–RTR-8; side-systems/owner-rulings.md Routing.. Architecture references mean only the assigned source/Architecture_Design snapshot.
**Status**: Specified; formal Clarify source resolutions and reviewed Plan/Tasks artifacts recorded; no runtime result implied

## User Scenarios & Testing

### User Story 1 - Obtain the supported outcome (Priority: P1)
An authorized Phase 3 evaluation run supplies one already selected and pinned Capsule plus protected context. The router filters approved runtime-qualified deployments, applies the frozen development selection policy, and returns one persisted immutable decision through RouterPort. The bridge audits and dispatches that model. Disabled, missing or failed routing preserves fixed Codex according to the adopted fallback rules.
**Independent Test**: Use frozen source-valid inputs through the actual supported provider/consumer boundary and independently reconcile effects, exact identities, accepted artifacts and persisted evidence. Source/schema fixtures alone cannot establish real external connections.
**Acceptance Scenarios**:
1. Given valid inputs, admitted authority and ready prerequisites, when the scoped operation executes, then The registry, bounded compatible selection, configuration, immutable request/decision lifecycle and observation code are implemented. Fixed Codex remains the mandatory verified Phase 1 route. Real integration, mock checks, unavailable access, implementation and verification statuses are reported separately; no statistical routing-quality or savings claim follows from an integration probe.

### User Story 2 - Understand a failed or blocked attempt (Priority: P1)
The researcher or consuming module receives an attributable outcome when required validity, authority, evidence or resources are unavailable.
**Independent Test**: Supply a frozen invalid/boundary counterpart and inspect actual effects, terminal outcome and retained evidence against an independent expectation.
**Acceptance Scenarios**:
1. Given a violated mandatory condition, when the operation is requested, then Invalid Capsule/context halts as a platform integrity fault. Router failures before dispatch yield attributed Codex fallback; bridge audit failure prevents new dispatch. A model failure after start halts the node without model switching or replay. Unavailable required enforcement blocks affected spending; optional missing measurements retain explicit unavailable reasons.
2. Given missing mandatory real service or required unexecuted checks, when status is reported, then it remains BLOCKED, NOT_RUN or INCOMPLETE rather than PASS.

### Edge Cases
The AC table defines source-specific invalid, boundary, failure, cancellation, compatibility and recovery outcomes. Preserve failed/interrupted attempts. Unknown values remain unavailable, never zero. Reused identities cannot replace prior content silently. Missing mandatory evidence is not waived by a generated checklist or summary. Resource blockers constrain affected execution while independent preparation continues.

## Requirements

### Functional Requirements
- **FR-001**: Implement bounded registry, compatible-candidate selection, configuration and route observations while retaining fixed Codex as the sole active Phase 1 model endpoint. Report implementation, integration and verification separately. [PRD §§4.3 introduction,4.3.1–4.3.3,6.12 Heterogeneous Model Routing; model-routing.md RTR-1]
- **FR-002**: Receive exactly the protected selected Capsule and context. Never choose, replace, combine or generate Capsules, widen effects or accept outputs. Validate original-byte pins and protected binding/profile/context before dispatch. [model-routing-contract.md Pinning trust and readiness, selected-capsule-input, route-request; router-design.md Inputs and Replies; PRD §4.3.2]
- **FR-003**: Keep router decision separate from bridge execution: separate killable router process reached over local IPC; no provider calls, provider credentials or bridge route-record writes inside router. [model-routing-contract.md RouterPort; router-design.md Boundary rules; model-routing.md RTR-4]
- **FR-004**: Filter exact authorized runtime-qualified endpoint/adapter configurations using verified capabilities, method/task scope, context/output limits, disclosure/effects, host/dependencies and enforceable remaining budgets. Preserve exclusion reasons. [router-design.md Qualification and filtering; model-catalog.md Qualification states, Catalog entries and refresh, Registry and development evidence]
- **FR-005**: Use frozen development aggregates for exact measured category/Capsule/method/deployment/input-resource scope and the preregistered quality/uncertainty rule. Rank qualifying deployments by lowest expected complete execution cost, then supported latency preference and configured priority/ID. [router-design.md Selection policy; model-catalog.md Registry and development evidence; owner-rulings.md Routing row 5]
- **FR-006**: Enforce independent 30-second RouterPort deadline and 30-second unexecuted ready validity. Apply adopted pre-call fallback cases and prohibit post-start switching/replay. [model-routing-contract.md RouterPort, route-record, Provider errors; router-design.md Deadline and expiry; model-routing.md RTR-2,3,6; model-catalog.md API provider entry]
- **FR-007**: Atomically claim authenticated execution_id against immutable full request fingerprint. Preserve decision and outcome; allow one compatible profile-authorized alternate only before freeze within original eligible set. [router-design.md Claim freeze and lifecycle; model-routing-contract.md Identities budgets and execution]
- **FR-008**: Persist router decision/events before reply and bridge route/call-start evidence before dispatch. Capture local attribution, requested/effective model identity and basis, endpoint/adapter/settings, times, outcomes, fallback and available usage. [router-design.md Records and Accounting and evaluation; model-routing-contract.md route-record and model-call; model-routing.md RTR-7; PRD §4.3.3]
- **FR-009**: Protect verifier, routing and other required work reservations and recheck live protected limits/prerequisites before dispatch. Preserve all applicable budget dimensions and enforcement modes. [model-routing-contract.md Identities budgets and execution, RoutingBudgetSnapshot; router-design.md Qualification and filtering]
- **FR-010**: Enable API routing only under approved evaluation configuration. Keep verifier calls on fixed Codex unless the separately approved alternate-verifier study expressly applies. [model-routing-contract.md Phase and review compatibility; model-routing.md RTR-5,8; PRD §§4.3.4,6.12]

### Key Entities
- Protected SelectedCapsuleInput
- RouteRequest
- ModelSelectionProfile
- Runtime-qualified deployment/catalog snapshot
- RouteDecision/model-route 2.0.0
- route-record 1.0.0
- model-call 1.0.0
- Protected budget/readiness context
Exact interoperable fields and requiredness belong to the canonical owning TASK agreement; this spec does not create a second interface definition.

## Success Criteria

### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| M1-007/AC-001 | FR-001; PRD §§4.3 introduction,4.3.1–4.3.3,6.12 Heterogeneous Model Routing; model-routing.md RTR-1; Story 1/2 (normal and applicable failure scenario) | With cc.router.enabled=false, every model call uses the fixed Codex route and records decision_source=codex_router_disabled. Mock or unverified experimental routes never become accepted Phase 1 configuration. | BLOCK, BOUNDARY |
| M1-007/AC-002 | FR-002; model-routing-contract.md Pinning trust and readiness, selected-capsule-input, route-request; router-design.md Inputs and Replies; PRD §4.3.2; Story 1/2 (normal and applicable failure scenario) | Changed declaration/body/overlay/dependency bytes, forged authority, invalid binding, unsupported labels or wrong run/child cannot dispatch. An invalid Capsule pin/context produces a platform_integrity_fault halt, without Codex fallback. Domain is exactly cs_ml and task_category is one of the eight adopted C01–C08 values; role labels confer no executor authority. | BLOCK, BOUNDARY |
| M1-007/AC-003 | FR-003; model-routing-contract.md RouterPort; router-design.md Boundary rules; model-routing.md RTR-4; Story 1/2 (normal and applicable failure scenario) | Hot-path imports reach RouterPort only and do not import router implementation. The router communicates a choice/no-route/integrity fault only; bridge retains provider execution, credentials and call records. | BLOCK, BOUNDARY |
| M1-007/AC-004 | FR-004; router-design.md Qualification and filtering; model-catalog.md Qualification states, Catalog entries and refresh, Registry and development evidence; Story 1/2 (normal and applicable failure scenario) | Tools and selection configurations cannot enter executor candidates or serve as router alternate. Registration or HTTP 200 alone cannot enable a deployment. Stale or changed model/adapter/parser/schema/settings evidence remains visible and cannot masquerade as current qualification. JSON output alone does not demand provider-native JSON mode. | BLOCK, BOUNDARY |
| M1-007/AC-005 | FR-005; router-design.md Selection policy; model-catalog.md Registry and development evidence; owner-rulings.md Routing row 5; Story 1/2 (normal and applicable failure scenario) | Missing profile coverage, including singleton candidates, yields the permitted compatible baseline or PROFILE_COVERAGE_MISSING. Source-only/model-card claims, brand and size are not measured quality. Runtime sees frozen development aggregates rather than private per-item calibration or referee costs. | BLOCK, BOUNDARY |
| M1-007/AC-006 | FR-006; model-routing-contract.md RouterPort, route-record, Provider errors; router-design.md Deadline and expiry; model-routing.md RTR-2,3,6; model-catalog.md API provider entry; Story 1/2 (normal and applicable failure scenario) | missing,error,timeout,unapproved_model,invalid_decision each yields attributed Codex fallback; router halt/block yields no_route plus router_halt_code. Expired unexecuted decision cannot run; executing decision does not expire mid-call. Started model failure halts without resend. Provider failure maps to auth_failed,rate_limited,timeout,provider_error,invalid_request,network_error or invalid_output; SDK retry count is zero. Configured provider timeout is 1–600 s and the shorter call limit applies. | BLOCK, BOUNDARY |
| M1-007/AC-007 | FR-007; router-design.md Claim freeze and lifecycle; model-routing-contract.md Identities budgets and execution; Story 1/2 (normal and applicable failure scenario) | Matching duplicate requests return stored outcome or ROUTING_IN_PROGRESS without duplicate side effects; changed content conflicts and cross-user access is denied. Lost/uncertain execution retains outcome_unknown without replay. Shared-context integrity failures never permit alternate substitution. Explicit upstream retry uses a new linked identity. | BLOCK, BOUNDARY |
| M1-007/AC-008 | FR-008; router-design.md Records and Accounting and evaluation; model-routing-contract.md route-record and model-call; model-routing.md RTR-7; PRD §4.3.3; Story 1/2 (normal and applicable failure scenario) | Router audit failure yields AUDIT_UNAVAILABLE fallback; bridge route/call-record failure prevents a new call and halts. Already-started uncertainty is retained. Missing per-call usage or cost is unavailable rather than zero/inferred; account subscription allowance is not per-call cost. Monetary claims require reliable usage and pinned tariff; internal IDs are not added to provider prompts solely for telemetry. | BLOCK, BOUNDARY |
| M1-007/AC-009 | FR-009; model-routing-contract.md Identities budgets and execution, RoutingBudgetSnapshot; router-design.md Qualification and filtering; Story 1/2 (normal and applicable failure scenario) | No borrowing verifier allowance, mixing invocation/model-call/token/currency dimensions or treating memory as additive money. Unsupported mandatory hard enforcement blocks affected dispatch; optional missing telemetry is explicit. Deferred dispatch predicates must pass for actual chosen deployment. | BLOCK, BOUNDARY |
| M1-007/AC-010 | FR-010; model-routing-contract.md Phase and review compatibility; model-routing.md RTR-5,8; PRD §§4.3.4,6.12; Story 1/2 (normal and applicable failure scenario) | Normal verifier calls do not consult API router even when enabled: router_enabled=false and codex_router_disabled. Toggling router on/off preserves frozen plan and declaration hashes; disabling restores exact Codex baseline without replaying prior failed calls. | BLOCK, BOUNDARY |

Required checks need current actual evidence. Required real execution is not established by mocks, static inspection, empty/skipped tests or artifact existence. M1-SYSTEM owns complete-candidate journeys and their separate system ACs.

## Scope and Assumptions

- Canonical consumed agreements: [M1-IF-001](../M1-001/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK), [M1-IF-002](../M1-002/TASK.md#4-embedded-cross-module-agreements) (r2, source-bound in the owning TASK), [M1-IF-003](../M1-002/TASK.md#4-embedded-cross-module-agreements) (r1, source-bound in the owning TASK). These are explicit definition prerequisites for dependent planning, not assumed published contracts.
Phase 3 implementation is required and remains isolated from Phase 1. Approved real endpoint access and runtime qualification are prerequisites only for affected real integration. M1 builds development_profile and fixed_baseline; bounded_llm_ablation is refused at start, and development_profile makes zero routing-selection model calls. No learned/bandit/RL router, ensembles, locally hosted weights, exhaustive model inventory, mid-call switching, full billing, organization quota enforcement or autonomous model activation. S07 repeated tier calibration, eight-domain quality/cost/regret and statistical savings comparisons remain M2/M3; the separately requested four-case QA real-routing probe is not such a campaign. Alternate-verifier execution requires its own explicit approved isolated study.

- Permitted models/providers come from registered source and qualified protected configuration only. Access, model version, pricing and measurement availability are not assumed.
- Missing Linux Codex/app authentication, dedicated Builder credentials, Docker/native hardware, endpoint qualification or protected referee resources retain actual readiness status; these prerequisites apply only to operations that require them, and this spec grants no waiver.
- All registered source constraints remain binding. ACs group observable requirements without discarding source details; source-to-AC allocation is recorded in TASKS.
- TASKS owns source allocation; TASK owns interfaces; spec owns ACs; plan will own design/procedures; tasks will own work/evidence mapping. No plan, implementation task list or product code is generated by this Specify writer.

## Clarifications

### Session 2026-10-16
- Fixed Codex profile ambiguity: model-routing-contract.md:43,128 permits router-off profile_ref=null and says CodexRouter needs no profile, while model-call at line 234 requires a nonnullable model_selection_profile_ref. Resolve the actual protected call-authorization mapping without fabricating a selection profile.
- Standing timing ambiguity: model-routing-contract.md:112 reads standing once at library snapshot and retains pins after later suspension/revocation; BoundRoutingContext admission_ref at line 321 says current standing rechecked. Preserve explicit snapshot behavior pending recorded interpretation; endpoint access/authorization checks remain applicable.
- Adopt assigned Architecture_Design current contracts; proposed QA interface version lists are not replacement authority. Real provider endpoint/credential references and qualification evidence are unavailable unless actually supplied; do not invent scores, access or secrets.
- No new quality floor, uncertainty bound, freshness period or cost threshold is invented. The versioned protected development profile must supply applicable policy values before dependent scoring/selection claims.

User workflow steering: finish all M1 specifications, then formal Clarify, Checklist, Plan, Tasks, read-only Analyze/corrections, Implement/verify and Converge. No downstream phase completion is claimed here.

- Source-resolved M1-I001 (Fixed-call authorization): Consume M1-001 M1-I001 and M1-IF-001@r1: fixed Codex audit authorization is distinct from external router configuration. No external API profile/catalog is required for CodexRouter and no API RouteDecision is fabricated. Source: M1-001/TASK.md M1-I001; reference/model-routing-contract.md.

C008 consumer revision reconciliation: consume canonical M1-IF-002@r2 from the owning M1-002/TASK.md. Its existing aggregate work/check limits are not pooled worker allowances. This metadata correction changes no source requirement, FR/AC identity, route-selection authority, threshold or M1-IF-008@r1 field. Retain historical evidence under its original pins.
