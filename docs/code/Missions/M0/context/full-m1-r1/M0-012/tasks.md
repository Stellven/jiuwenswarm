---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-012 — Immutable hypothesis and pre-registered experimental protocol

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-012/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-012/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; jiuwenswarm/agents/harness/common/prompt/prompt_builder.py; jiuwenswarm/agents/harness/common/tools/memory_tools.py; jiuwenswarm/ai4research/hypothesis.py (proposed); tests/unit_tests/ai4research/test_hypothesis.py (proposed); tests/integration_tests/ai4research/test_hypothesis_boundary.py (proposed); tests/fixtures/ai4research/hypothesis/calibration_manifest.json (proposed).

### Block B01 — FR-001

- [ ] T003 [US1] State one testable scientific claim from the selected opportunity. B01, AC-001; `jiuwenswarm/ai4research/hypothesis.py`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_hypothesis.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Pre-register exact baseline, validation resource and measured variables. B02, AC-002; `jiuwenswarm/ai4research/hypothesis.py`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_hypothesis.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Define the bounded mechanism without performing implementation or evolution. B03, AC-003; `jiuwenswarm/ai4research/hypothesis.py`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_hypothesis.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Freeze success, falsification and permitted classification before code/results. B04, AC-004; `jiuwenswarm/ai4research/hypothesis.py`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_hypothesis.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Publish a complete typed verification-ready Blueprint with immutable downstream authority. B05, AC-005; `jiuwenswarm/ai4research/hypothesis.py`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_hypothesis.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Supply pre-registration calibration and evidence to independent checking. B06, AC-006; `jiuwenswarm/ai4research/hypothesis.py`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_hypothesis.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T015 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Multiple parallel claims, ungrounded mechanism or invented user target prevents acceptance. Missing, swapped, unadmitted or stale hypothesis_capsule.md identity prevents dispatch/release.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_hypothesis_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T016 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Unknown resource, favorable substitution, missing baseline or synthetic/undeclared downloaded data cannot satisfy the protocol.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_hypothesis_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T017 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Unbounded refactor, unsupported target or actual build code is rejected as role/scope mismatch.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_hypothesis_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T018 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Missing/ill-defined mandatory boundary, post-hoc condition, threshold change or outcome-driven adjustment blocks acceptance.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_hypothesis_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T019 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Candidate file or producer declaration cannot authorize execution; downstream write attempts to data/measurements/thresholds are denied.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_hypothesis_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T020 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Verifier must not invent missing scientific design or repair thresholds to pass the submitted artifact.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_hypothesis_boundary.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T021 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-012@r1 | T001, T002, T003 | V01 / T004; V02 / T015 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-012@r1 | T001, T002, T005 | V03 / T006; V04 / T016 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-012@r1 | T001, T002, T007 | V05 / T008; V06 / T017 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-012@r1 | T001, T002, T009 | V07 / T010; V08 / T018 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-012@r1 | T001, T002, T011 | V09 / T012; V10 / T019 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-012@r1 | T001, T002, T013 | V11 / T014; V12 / T020 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

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
