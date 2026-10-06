---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-018 — Local-isolated RSI, protected fixture oracle, and bounded candidate evidence

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-018/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-018/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; Existing anchor: jiuwenswarm/agents/harness/common/rsi/worker.py; Existing anchor: jiuwenswarm/agents/harness/common/rsi/models.py; Existing anchor: jiuwenswarm/agents/harness/common/rsi/validation_dataset.py; Existing anchor: jiuwenswarm/agents/harness/common/rsi/task_store.py; Existing anchor: jiuwenswarm/agents/harness/common/rsi/event_journal.py; Existing anchor: jiuwenswarm/agents/harness/common/rsi/materializer.py; Existing anchor: jiuwenswarm/agents/harness/common/rsi/harness_activation.py; Existing anchor: jiuwenswarm/server/rsi/rsi_handlers.py; Proposed: jiuwenswarm/ai4research/rsi/; Proposed: tests/unit_tests/ai4research/test_rsi.py; Proposed: tests/integration_tests/ai4research/test_rsi_boundary.py.

### Block B01 — FR-001

- [ ] T003 [US1] Expose a target profile and shared loop core that copy an eligible immutable Screening parent into a separate sandbox and mutate only rank_opportunities for required Target 1. Profile owns fixtures, scoring adapter, mutation surface, and proposer settings; core does not branch on capsule name. B01, AC-001; `jiuwenswarm/ai4research/rsi/profiles.py (proposed)`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Enforce a server-side explicit mutation allowlist outside mutable child code, preserving required parent tests, incoming scoring dimensions, Top-1 behavior, Opportunity_Card interface, dependencies, effect boundary, and compatibility before hidden evaluation. B02, AC-002; `jiuwenswarm/ai4research/rsi/mutation_guard.py (proposed)`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Freeze referee, oracle, scoring/promotion policy, gates/verifiers/check runners, their rubrics, permission enforcement, evidence stores, hidden suites, and the transitive behavioral dependency closure before a session. B03, AC-003; `jiuwenswarm/ai4research/rsi/protected_manifest.py (proposed)`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Keep visible development, hidden-loop, hidden-final, and milestone/platform splits separate, frozen, provenance-bound, and overlap-checked. Manually seed meaningful hidden fixtures before live telemetry is sufficient, and calibrate the fixed referee using planted good/bad children. B04, AC-004; `jiuwenswarm/ai4research/rsi/fixture_catalog.py (proposed)`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Give hidden data and authoritative scoring only to a protected oracle/custodian; enforce the supplied channel limits and terminal-final policy outside proposer and child trust boundaries. B05, AC-005; `jiuwenswarm/ai4research/rsi/oracle.py (proposed)`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Compare exact parent and child on paired permitted fixtures with frozen scoring, the same relevant model route/runtime configuration, required parent-test preservation, and declared repeated-fixture aggregation. Execution time is only the tie-breaker when passed-test counts are equal. B06, AC-006; `jiuwenswarm/ai4research/rsi/scoring.py (proposed)`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Keep the M1 improver fixed and drive one bounded candidate change per iteration through the shared audited model/runner boundary with frozen policy and resource limits. B07, AC-007; `jiuwenswarm/ai4research/rsi/session.py (proposed)`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B08 — FR-008

- [ ] T017 [US1] Retain hash-chained attempts, parent/child and contract hashes, target/profile/diff/rationale, frozen improver/referee/scoring/split/configuration identities, limits/query counters, outcomes, violations, stop reason, and permitted run/export joins. B08, AC-008; `jiuwenswarm/ai4research/rsi/records.py (proposed)`.
- [ ] T018 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V15; AC-008, B08; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B09 — FR-009

- [ ] T019 [US1] Validate an eligible child with node-level offline replay on recorded inputs and a nonexecuting DAG wiring dry-run while workflow structure, roles, ports, gates and effects remain read-only. B09, AC-009; `jiuwenswarm/ai4research/rsi/replay.py (proposed)`.
- [ ] T020 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V17; AC-009, B09; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B10 — FR-010

- [ ] T021 [US1] Execute a fixed intentional adversarial violation suite that covers hidden access/leakage, referee/check/policy tampering, out-of-scope mutation, permission escalation, injection-driven scope escape, unauthorized filesystem/process/tool/network effects, resource abuse, evidence tampering, adaptive overfitting/premature final access, and promotion bypass. B10, AC-010; `tests/integration_tests/ai4research/test_rsi_boundary.py (proposed)`.
- [ ] T022 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V19; AC-010, B10; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B11 — FR-011

- [ ] T023 [US1] Publish the Target 1 child as sandbox evidence and inactive lineage; admission and explicit human activation are separate actions, with rollback affecting future runs only. B11, AC-011; `jiuwenswarm/ai4research/rsi/adoption.py (proposed)`.
- [ ] T024 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V21; AC-011, B11; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B12 — FR-012

- [ ] T025 [US1] Account explicitly for conditional Target 2 implementation-text mutation through the same loop when a bounded headless model-execution path is available, preserving dimensions/interface/tests and all referee-owned rubric assets. B12, AC-012; `jiuwenswarm/ai4research/rsi/profiles.py (proposed)`.
- [ ] T026 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V23; AC-012, B12; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B13 — FR-013

- [ ] T027 [US1] Permit only approved bounded read-only public benchmark/repository retrieval needed by a declared target, retaining origin/license/provenance, immutable revision/content hash and local snapshot before session use. B13, AC-013; `jiuwenswarm/ai4research/rsi/reference_import.py (proposed)`.
- [ ] T028 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V25; AC-013, B13; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B14 — FR-014

- [ ] T029 [US1] Distinguish ordinary candidate rejection, resource/query exhaustion, security/referee/storage faults, human adoption/refusal, and terminal session completion; export enough protected evidence for the system-owned Phase 2 completion report. B14, AC-014; `jiuwenswarm/ai4research/rsi/session.py and jiuwenswarm/ai4research/rsi/records.py (proposed)`.
- [ ] T030 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V27; AC-014, B14; `tests/unit_tests/ai4research/test_rsi.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T031 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Submit a live-DAG target or a profile without an eligible immutable parent; deny before candidate execution.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T032 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Attempt every prohibited diff and assert zero hidden evaluations, unchanged protected hashes, and attributable refusals.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T033 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Replace a transitive check dependency or change scoring policy mid-session; stop without accepting a score or allowing another child evaluation.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T034 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Detect overlap, an insufficient hidden split, post-freeze fixture rewriting, or misleading planted-child scoring; block session acceptance and preserve diagnostics without exposing hidden case details.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T035 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Attempt direct reads/leaks, counter reset/replay, a 31st session query, a 91st lifetime query, premature final evaluation, or a second final call; deny and retain actual attribution.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T036 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Evaluate with mismatched settings or revise scoring after seeing results; reject comparison validity and prevent improvement claims.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T037 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `Attempt budget escalation, a new unaudited route, or weight modification; deny, terminate as required, and preserve evidence.` and check recovery; B07, AC-007; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T038 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V16; inject `Forge lineage/score or tamper with evaluation evidence; block acceptance and halt on security tampering.` and check recovery; B08, AC-008; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T039 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V18; inject `Supply an incompatible output or graph mutation; record failure and exclude the candidate from admission/improvement claims.` and check recovery; B09, AC-009; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T040 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V20; inject `Demonstrate a bypass or missing enforcement observation; mark the boundary failed/blocked and deny acceptance regardless of candidate score.` and check recovery; B10, AC-010; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T041 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V22; inject `Attempt automatic promotion or promotion without admission; deny and preserve production/default pointers.` and check recovery; B11, AC-011; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T042 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V24; inject `Treat verifier rubric as mutable or report mocked execution as real model-backed Target 2; refuse and retain honest status.` and check recovery; B12, AC-012; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T043 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V26; inject `Attempt an unauthorized network/write operation or use an unpinned mutable input; refuse and record the precise boundary.` and check recovery; B13, AC-013; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T044 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V28; inject `Resume after security failure without clearance, export hidden results, or declare acceptance with unrun required checks; deny and retain non-success status.` and check recovery; B14, AC-014; `tests/integration_tests/ai4research/test_rsi_boundary.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T045 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-018@r1 | T001, T002, T003 | V01 / T004; V02 / T031 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-018@r1 | T001, T002, T005 | V03 / T006; V04 / T032 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-018@r1 | T001, T002, T007 | V05 / T008; V06 / T033 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-018@r1 | T001, T002, T009 | V07 / T010; V08 / T034 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-018@r1 | T001, T002, T011 | V09 / T012; V10 / T035 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-018@r1 | T001, T002, T013 | V11 / T014; V12 / T036 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; M0-IF-018@r1 | T001, T002, T015 | V13 / T016; V14 / T037 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-008](spec.md) | B08; M0-IF-018@r1 | T001, T002, T017 | V15 / T018; V16 / T038 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-009](spec.md) | B09; M0-IF-018@r1 | T001, T002, T019 | V17 / T020; V18 / T039 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-010](spec.md) | B10; M0-IF-018@r1 | T001, T002, T021 | V19 / T022; V20 / T040 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-011](spec.md) | B11; M0-IF-018@r1 | T001, T002, T023 | V21 / T024; V22 / T041 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-012](spec.md) | B12; M0-IF-018@r1 | T001, T002, T025 | V23 / T026; V24 / T042 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-013](spec.md) | B13; M0-IF-018@r1 | T001, T002, T027 | V25 / T028; V26 / T043 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-014](spec.md) | B14; M0-IF-018@r1 | T001, T002, T029 | V27 / T030; V28 / T044 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

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
