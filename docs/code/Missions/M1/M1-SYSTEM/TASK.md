# TASK: M1-SYSTEM - Integrated M1 governed research and workstation verification

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.


PRD-derived preparation, r3 / 2026-10-06. Current authorization: populate code documentation, not implement or execute the product.

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-SYSTEM / r3 / 2026-10-06 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED; drafting assistance does not assign the future implementation executor. |
| Requested outcome and instruction/source | Whole-system journeys and cross-cutting invariants for the complete required M1 scope: Phase 1 research/workstation and the separate required offline RSI validation track. Child feature requirements remain in their owning specs. User requested update of existing TASK/Spec Kit records from the latest attached PRD with the current architecture supplied. |
| Included scope / exclusions | Whole-system journeys and cross-cutting invariants for the complete required M1 scope: Phase 1 research/workstation and the separate required offline RSI validation track. Child feature requirements remain in their owning specs. Exclusions: Phase 3 experiments do not block M1 acceptance unless explicitly promoted. This task does not redefine child schemas, feature thresholds, component implementation or scientific hypotheses. |
| PRD clause and architecture node references | [current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) §1, §2, §6; applicable §§1–2 and §6. [Architecture entry and views](../../../../architecture/build-package/README.md), October 6 baseline. Also §3.5.4/§3.6.1/§3.7.1, §4.3.3/§4.4/§4.5.2/§4.6.4, §5.3.1 and §5.6.5 supply the changed cross-cutting acceptance requirements. |
| Working checkout / branch / base | Documentation prepared in existing ai4r_xiaoyang checkout at d9fe483ea64c273ef831886bfa83819f6d5bb21c; implementation NOT_STARTED, candidate NOT_BUILT. |
| Affected code/document paths | docs/code/Missions/M1/M1-SYSTEM/TASK.md; docs/code/Missions/M1/M1-SYSTEM/{spec.md,plan.md,tasks.md}. Product and executable test paths PENDING_DESIGN. |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-SYSTEM/ | One directory owned by M1-SYSTEM |
| spec.md | [spec](spec.md) | Requirements, ACs and threshold sources |
| plan.md | [plan](plan.md) | Behavioral decomposition and verification design; technical realization pending |
| tasks.md | [tasks](tasks.md) | Work/progress and AC-to-evidence mapping |
| evidence/ | docs/code/Missions/M1/M1-SYSTEM/evidence/ | Reserved for actual verification runs; none produced |
| Supporting artifacts | [PRD baseline](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) | Registered source snapshot; no separate approval/review cards |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-001 / M1-IF-001@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-002 / M1-IF-002@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-003 / M1-IF-003@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-004 / M1-IF-004@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-005 / M1-IF-005@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-006 / M1-IF-006@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-007 / M1-IF-007@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-008 / M1-IF-008@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-009 / M1-IF-009@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-010 / M1-IF-010@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-011 / M1-IF-011@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-012 / M1-IF-012@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-013 / M1-IF-013@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-014 / M1-IF-014@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-015 / M1-IF-015@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-016 / M1-IF-016@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-017 / M1-IF-017@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-018 / M1-IF-018@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |

- [M1-001 canonical TASK](../M1-001/TASK.md#4-embedded-cross-module-agreements)
- [M1-002 canonical TASK](../M1-002/TASK.md#4-embedded-cross-module-agreements)
- [M1-003 canonical TASK](../M1-003/TASK.md#4-embedded-cross-module-agreements)
- [M1-004 canonical TASK](../M1-004/TASK.md#4-embedded-cross-module-agreements)
- [M1-005 canonical TASK](../M1-005/TASK.md#4-embedded-cross-module-agreements)
- [M1-006 canonical TASK](../M1-006/TASK.md#4-embedded-cross-module-agreements)
- [M1-007 canonical TASK](../M1-007/TASK.md#4-embedded-cross-module-agreements)
- [M1-008 canonical TASK](../M1-008/TASK.md#4-embedded-cross-module-agreements)
- [M1-009 canonical TASK](../M1-009/TASK.md#4-embedded-cross-module-agreements)
- [M1-010 canonical TASK](../M1-010/TASK.md#4-embedded-cross-module-agreements)
- [M1-011 canonical TASK](../M1-011/TASK.md#4-embedded-cross-module-agreements)
- [M1-012 canonical TASK](../M1-012/TASK.md#4-embedded-cross-module-agreements)
- [M1-013 canonical TASK](../M1-013/TASK.md#4-embedded-cross-module-agreements)
- [M1-014 canonical TASK](../M1-014/TASK.md#4-embedded-cross-module-agreements)
- [M1-015 canonical TASK](../M1-015/TASK.md#4-embedded-cross-module-agreements)
- [M1-016 canonical TASK](../M1-016/TASK.md#4-embedded-cross-module-agreements)
- [M1-017 canonical TASK](../M1-017/TASK.md#4-embedded-cross-module-agreements)
- [M1-018 canonical TASK](../M1-018/TASK.md#4-embedded-cross-module-agreements)

Definition-time dependencies are not a demand to finish every provider/consumer TASK first. Exact architecture edges remain pending. Full connected checks require actual relevant implementations; stubs only support independent block preparation.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for task-level coding design. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.


Owned: None. This task owns system ACs and verification, not a new product interface. Consumed agreements: M1-IF-001 through M1-IF-018 @r0 at the linked owning TASKs above. A provisional agreement must be completed before dependent implementation; this system task does not copy its schema.

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this current PRD update.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-SYSTEM-OPEN-01 / 2026-10-01 | ARCH-SYSTEM: Candidate components, technical boundaries and exact supported deployment/test entry points await Architecture and implementation binding. | Corresponding ACs and plan blocks; T001/T002; consumed IFs | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-SYSTEM-OPEN-02 / 2026-10-01 | VERIFY-SYSTEM: Real service/account availability, permitted local research fixtures, dataset versions, execution budgets and any externally claimed quality/reliability thresholds must be registered before corresponding measurements. No new universal model score or budget is imposed by this scaffold. | Corresponding ACs and plan blocks; T001/T002; consumed IFs | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-SYSTEM-OPEN-03 / 2026-10-01 | COVERAGE-SYSTEM: Passing the first research journey does not discharge required workstation/RSI obligations or the parent full-source coverage requirement; Phase 3 stays separate. | Corresponding ACs and plan blocks; T001/T002; consumed IFs | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| PRD-R2 / 2026-10-02 | §1.3/§1.5/§2.11, §3.5.4/§3.6.1/§3.7.1, §4.3.3/§4.4/§4.5.2/§4.6.4, §5.3.1/new §5.6.5, §6.4/§6.11/§6.12. Updates three-track acceptance: required adversarial RSI, headless reproduction, clean local attribution and ablation validity. | AC-004, AC-006, AC-007, AC-009, AC-010, AC-012, AC-013; native plan/tasks correspondence; consumed IFs | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Implementation-dependent definitions before affected implementation. |

Progress belongs only in native tasks.md. No approval stage or additional task card is introduced.
