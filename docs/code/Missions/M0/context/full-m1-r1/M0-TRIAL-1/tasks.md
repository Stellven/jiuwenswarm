---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-TRIAL-1 — Connected intermediate Intent compiler and protected Verifier slice

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-TRIAL-1/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-TRIAL-1/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; Existing: jiuwenswarm/server/runtime/codex_subscription/{transport.py,service.py}; jiuwenswarm/server/runtime/agent_adapter/interface_codex.py; text-only chat reuse anchors, not a functioning governed CC adapter.; Existing: jiuwenswarm/symphony/{adapter.py,service.py,llm.py}; exact dependency public CapabilityDescriptor/CapabilityProvider/SymphonyRuntime contracts are inspected leads, with runtime compatibility NOT_RUN in source/build-package/sources/native-reuse-evidence.json.; Existing: jiuwenswarm/channels/web/frontend/src/stores/sessionStore.ts; jiuwenswarm/channels/web/frontend/src/features/UserQuestionModal; jiuwenswarm/channels/process_cli/{machine_entry.py,machine_io.py,machine_result.py,protocol/model.py}; native transport/presentation leads only.; Existing: jiuwenswarm/observability/{config.py,store.py}; existing trajectory projections cannot substitute for M0-005's authoritative run/evidence state or protected gate commit.; Existing: tests/unit_tests/runtime/test_codex_subscription.py; tests/unit_tests/symphony/test_direct_service.py; tests/unit_tests/agentserver/test_symphony_orchestration_needs_input.py; tests/unit_tests/process_cli/; native fixtures are reuse/characterization leads, not trial acceptance evidence.; Proposed: jiuwenswarm/ai4research/intent/{compiler.py,models.py,application.py}; intermediate Intent interface and parser belong to this task; shared model/security/state/gate mechanisms stay with their owners.; Proposed: jiuwenswarm/resources/ai4research/capsules/intent_compiler/{capsule.json,SKILL.md,references/}; intent-verifier implementation assignment references M0-007's protected gate/verifier interface and admitted implementation rather than defining a second gate.; Proposed: tests/unit_tests/ai4research/test_intent_compiler.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/journeys/ai4research/test_intent_trial.py; tests/fixtures/ai4research/intent/{development,characterization}/ with fixed independent labels before measurements.; Proposed: minimal native web adapter and sequential headless driver consuming one shared application boundary; no bespoke web dashboard or separate trial run-state store..

### Block B01 — FR-001

- [ ] T003 [US1] Qualify original text input and bind it to the authorized stable product-user, workspace, originating session and new run before any compiler work; preserve the source text as data rather than instructions for the host. B01, AC-001; `jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] At run admission freeze the protected intent-node contract, original source reference, compiler and intent-verifier implementation/dependency closure, exact model-role route, fidelity/check profile, interaction mode and time/call limits. B02, AC-002; `jiuwenswarm/ai4research/intent/models.py and jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Perform one bounded compiler invocation that extracts the problem/objective, desired change/deliverable, explicit scope/constraints and source-attributed omissions/conflicts without choosing a solution or inventing requirements. B03, AC-003; `jiuwenswarm/ai4research/intent/compiler.py and jiuwenswarm/ai4research/intent/models.py (proposed); jiuwenswarm/resources/ai4research/capsules/intent_compiler/capsule.json and prompt resources (proposed)`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Execute compiler and verifier through the shared governed runner and audited model bridge, with distinct invocation context, implementation identity, outcomes and evidence correlation. B04, AC-004; `jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Apply mandatory deterministic validation to the exact captured compiler artifact, source attribution, schema, pins, budget/effect observations and subject binding before invoking the semantic verifier. B05, AC-005; `jiuwenswarm/ai4research/intent/models.py (proposed)`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Use a separate admitted intent-verifier invocation with protected output-led review context containing the original request, exact candidate, declared responsibility and independently owned fidelity rubric. B06, AC-006; `jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Release an accepted intermediate Intent reference only after the protected host commits the validated gate decision and exact candidate/evidence references to authoritative storage. B07, AC-007; `jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B08 — FR-008

- [ ] T017 [US1] Enforce frozen time/call limits, zero automatic repair/replay and halt on blocking execution/security/evidence faults; separate environment unavailability, demonstrated implementation failure and unresolved semantic uncertainty. B08, AC-008; `jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T018 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V15; AC-008, B08; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B09 — FR-009

- [ ] T019 [US1] Expose native web submission, accepted intent or durable blocking reason/attention request, and an explicit sequential headless driver through one authenticated application boundary. B09, AC-009; `jiuwenswarm/channels/web/frontend/src/stores/sessionStore.ts; jiuwenswarm/channels/process_cli/machine_entry.py; jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T020 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V17; AC-009, B09; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B10 — FR-010

- [ ] T021 [US1] Keep server-owned lifecycle distinct from client transport; reconcile uncertain submit, continue after browser disconnect, record explicit cancellation and preserve restart interruption without replay. B10, AC-010; `jiuwenswarm/ai4research/intent/application.py (proposed)`.
- [ ] T022 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V19; AC-010, B10; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B11 — FR-011

- [ ] T023 [US1] Characterize verifier fidelity and instruction resistance on a fixed independently labeled challenge set before making any real connected slice-acceptance claim. B11, AC-011; `tests/fixtures/ai4research/intent/characterization and tests/journeys/ai4research/test_intent_trial.py (proposed); docs/code/Missions/M0/M0-TRIAL-1/evidence`.
- [ ] T024 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V21; AC-011, B11; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B12 — FR-012

- [ ] T025 [US1] Keep trial acceptance and product integration exits distinct and allocate its interface contribution without overclaiming complete requirement compilation or the governed downstream-worker demonstration. B12, AC-012; `jiuwenswarm/ai4research/intent/models.py (proposed); docs/code/Missions/M0/M0-TRIAL-1/TASK.md`.
- [ ] T026 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V23; AC-012, B12; `tests/unit_tests/ai4research/test_intent_compiler.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T027 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Mechanical qualification rejects invalid intake before semantic extraction; rejection reason remains attributable where persistence is available.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T028 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Admission/compatibility/authority failure yields non-advancing outcome with no substituted version or model fallback.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T029 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Unsupported addition, omitted material constraint, scope drift, conflict concealed as certainty or solution selection remains a candidate defect for independent checking.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T030 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Lost/ambiguous model delivery, wrong correlation or incomplete invocation evidence blocks acceptance without a duplicate call.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T031 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Tier-1 failure is durably recorded and prevents verifier dispatch and accepted artifact release.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T032 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Instruction injection, disclosure violation, invalid assessment or unresolved material judgment cannot create acceptance.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T033 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `No accepted artifact on blocking or undurable result; failed candidate remains inspectable as unaccepted evidence where storage permits.` and check recovery; B07, AC-007; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T034 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V16; inject `Each fault records precise causal outcome and stops dispatch rather than becoming a swallowed native warning/pass.` and check recovery; B08, AC-008; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T035 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V18; inject `Client/UI event, acknowledgment or user opinion cannot convert blocking state into acceptance.` and check recovery; B09, AC-009; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T036 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V20; inject `Ambiguous transport or restart does not produce implicit retry/resume or assign late evidence to a new run.` and check recovery; B10, AC-010; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T037 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V22; inject `Missing real account/security capability, zero cases, all skips or only stubs leave model-backed acceptance BLOCKED/NOT_RUN; poor fidelity remains measured failure rather than a rewritten threshold.` and check recovery; B11, AC-011; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.
- [ ] T038 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V24; inject `An artifact named Research_Brief or a verifier labeled Node B without real responsibilities fails documentation/interface consistency and cannot close the related exit.` and check recovery; B12, AC-012; `tests/integration_tests/ai4research/test_intent_trial.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T039 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-020@r1 | T001, T002, T003 | V01 / T004; V02 / T027 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-020@r1 | T001, T002, T005 | V03 / T006; V04 / T028 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-020@r1 | T001, T002, T007 | V05 / T008; V06 / T029 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-020@r1 | T001, T002, T009 | V07 / T010; V08 / T030 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-020@r1 | T001, T002, T011 | V09 / T012; V10 / T031 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-020@r1 | T001, T002, T013 | V11 / T014; V12 / T032 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; M0-IF-020@r1 | T001, T002, T015 | V13 / T016; V14 / T033 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-008](spec.md) | B08; M0-IF-020@r1 | T001, T002, T017 | V15 / T018; V16 / T034 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-009](spec.md) | B09; M0-IF-020@r1 | T001, T002, T019 | V17 / T020; V18 / T035 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-010](spec.md) | B10; M0-IF-020@r1 | T001, T002, T021 | V19 / T022; V20 / T036 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-011](spec.md) | B11; M0-IF-020@r1 | T001, T002, T023 | V21 / T024; V22 / T037 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-012](spec.md) | B12; M0-IF-020@r1 | T001, T002, T025 | V23 / T026; V24 / T038 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

## Dependency Order and Execution Notes

T001 → T002 → each implementation/block-verification pair → connected boundaries → system contribution. Definitions can proceed independently of missing runtime services; actual boundary acceptance cannot. No [P] is preassigned because shared native infrastructure and governing profiles require scoped ownership. Future disjoint work may be marked [P] after exact paths/dependencies are established.

Resume through parent TASKS → this TASK → spec/plan → first unresolved native work item. Select the exact feature directory explicitly; a feature pointer is not a task lock. Do not run simultaneous feature-generator sessions in a shared checkout. Scope for this request is preparation only. Live-provider tests, publication, pushes, deployment and installed-product changes are not automatically authorized by generated tasks.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT for runtime; authoring baseline 2cc0b8695d4000cc72af64eb781356697f7fd861.
- Required work complete: no product implementation work completed by preparation.
- Required AC/check coverage: all ACs mapped, all runtime required checks NOT_RUN.
- Conclusion: NOT_READY for product/runtime acceptance. Framework documentary acceptance is separately M0-SYSTEM/AC-001.
- Remaining limitations and next work IDs: T001–T002, then the ordered blocks; source/service-specific questions in TASK and plan constrain only dependent work.

## Evidence Invalidation

No prior runtime evidence exists for this generated revision. Any implementation/input/schema/interface/profile/model/test/configuration/dependency/acceptance change marks affected rows STALE and propagates through the parent dependency graph. Keep old observed runs, exact candidate identity and limitations. Do not turn missing mandatory service/check into PASS or N/A; exclusions require source basis.
