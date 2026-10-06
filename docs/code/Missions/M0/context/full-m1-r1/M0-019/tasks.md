---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-019 — All six bounded Phase 3 integration efforts and preserved deterministic fallback

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-019/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-019/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; Existing anchor: jiuwenswarm/symphony/adapter.py; Existing anchor: jiuwenswarm/symphony/build.py; Existing anchor: jiuwenswarm/symphony/service.py; Existing anchor: jiuwenswarm/agents/harness/team/handlers/workflow_state.py; Existing anchor: jiuwenswarm/server/runtime/agent_adapter/team_helpers.py; Existing anchor: jiuwenswarm/common/schema/swarmflow_reply.py; Existing anchor: jiuwenswarm/server/runtime/gateway_adapter/codex_adapter.py; Existing anchor: pyproject.toml; Proposed: jiuwenswarm/ai4research/integrations/; Proposed: tests/unit_tests/ai4research/test_dynamic_integrations.py; Proposed: tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py.

### Block B01 — FR-001

- [ ] T003 [US1] Treat all six Phase 3 capabilities as expected M1 work, prepare independent adapters once their relevant deterministic baseline boundary exists, and integrate/promote only after the declared operational/stability prerequisites. B01, AC-001; `jiuwenswarm/ai4research/integrations/status.py (proposed)`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Integrate an available advanced intention compiler through a versioned adapter that preserves accepted Brief semantics, original-source attribution, constraints/defaults and unresolved requirements; retain bounded baseline compilation. B02, AC-002; `jiuwenswarm/ai4research/integrations/intention_compiler.py (proposed)`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Evaluate native local Agent Team/Cluster Leader decomposition into bounded research objectives, roles, dependencies and candidate graph, optionally invoking a deterministic SwarmFlow subworkflow; keep proposal separate from authority and execution. B03, AC-003; `jiuwenswarm/ai4research/integrations/team_planner.py (proposed)`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Expose eligible admitted CCs through native Symphony catalogue/provider seams and dynamically bind exact compatible pins into explicit Node Execution Contracts without treating semantic metadata as payload validation or execution permission. B04, AC-004; `jiuwenswarm/ai4research/integrations/admitted_catalogue.py (proposed)`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Develop bounded heterogeneous role/profile routing over approved routes, first through labeled mock preparation where necessary and then through real approved endpoints when available, retaining static Codex selection as fallback. B05, AC-005; `jiuwenswarm/ai4research/integrations/model_routing.py (proposed)`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Evaluate an approved alternate Reviewer/Verifier model through the existing read-only assessment interface under the same independently pinned profiles, criteria, evidence custody and host release authority. B06, AC-006; `jiuwenswarm/ai4research/integrations/verifier_model.py (proposed)`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Investigate the actually installed/pinned OpenJiuwen Code Mode and integrate applicable available capabilities through the existing bounded Builder/runner adapter without weaker declarations, dependency/effect restrictions or evidence controls. B07, AC-007; `jiuwenswarm/ai4research/integrations/code_mode.py (proposed)`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B08 — FR-008

- [ ] T017 [US1] Keep experimental profiles isolated and preserve operational deterministic fallback while sharing protected compilation, admission, binding, runner, verifier, evidence and release protocols across static and dynamic modes. B08, AC-008; `jiuwenswarm/ai4research/integrations/profiles.py (proposed)`.
- [ ] T018 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V15; AC-008, B08; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B09 — FR-009

- [ ] T019 [US1] Maintain one explicit outcome per six Phase 3 efforts and provide exact evidence, unavailable prerequisites and limitations to the system-owned Phase_3_Completion_Report.md and M1_Implementation_Report.md. B09, AC-009; `jiuwenswarm/ai4research/integrations/status.py (proposed)`.
- [ ] T020 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V17; AC-009, B09; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B10 — FR-010

- [ ] T021 [US1] Characterize applicable advanced variants against frozen matched baseline inputs/configurations through the ordinary scoped client/export path, with independently fixed challenge criteria and honest uncertainty. B10, AC-010; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py (proposed)`.
- [ ] T022 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V19; AC-010, B10; `tests/unit_tests/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T023 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Start release-critical dynamic work without a stable relevant baseline or omit it solely as non-blocking; refuse promotion and retain incomplete status.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T024 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Attempt to edit accepted requirements through clarification, wait for headless input, omit a mandatory constraint or exceed the dialog budget; halt and preserve original evidence.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T025 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Attempt Leader self-certification, omitted gate, unsupported role, cycle or post-freeze graph edit; prevent work dispatch.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T026 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Use folder presence/fingerprint or cached catalogue as admission, union CC permissions, drop unsupported governance fields, or swap an implementation; reject dispatch/release.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T027 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Attempt unapproved endpoint access, interpret absent cost as zero, or silently fail over a started invocation; block and retain the attempted route/fault.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T028 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Alter gate criteria, author a replacement artifact, disclose forbidden evidence or treat a provider PASS as release authority; deny advancement.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T029 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `Call unsupported API, widen tools, execute unconstrained generated code, silently repair or claim source inspection as runtime compatibility; block/report precise status.` and check recovery; B07, AC-007; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T030 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V16; inject `Automatically switch graph/model mid-run or continue after a failed experimental gate; stop and preserve exact failure evidence.` and check recovery; B08, AC-008; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T031 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V18; inject `Label mocked endpoint success as PASS, omit an effort, conflate core completion with complete Phase 3 accounting, or record a blocker without dependency evidence; reject the report conclusion.` and check recovery; B09, AC-009; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T032 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V20; inject `Change expected labels after outcomes, compare incompatible configurations, infer optimality from one candidate, or omit failed cases; invalidate the affected comparison.` and check recovery; B10, AC-010; `tests/integration_tests/ai4research/test_dynamic_integrations_boundary.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T033 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-019@r1 | T001, T002, T003 | V01 / T004; V02 / T023 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-019@r1 | T001, T002, T005 | V03 / T006; V04 / T024 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-019@r1 | T001, T002, T007 | V05 / T008; V06 / T025 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-019@r1 | T001, T002, T009 | V07 / T010; V08 / T026 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-019@r1 | T001, T002, T011 | V09 / T012; V10 / T027 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-019@r1 | T001, T002, T013 | V11 / T014; V12 / T028 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; M0-IF-019@r1 | T001, T002, T015 | V13 / T016; V14 / T029 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-008](spec.md) | B08; M0-IF-019@r1 | T001, T002, T017 | V15 / T018; V16 / T030 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-009](spec.md) | B09; M0-IF-019@r1 | T001, T002, T019 | V17 / T020; V18 / T031 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-010](spec.md) | B10; M0-IF-019@r1 | T001, T002, T021 | V19 / T022; V20 / T032 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

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
