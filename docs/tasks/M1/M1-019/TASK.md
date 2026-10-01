# TASK: M1-019 - Isolated Phase 2 experiment registration and integration

PRD-derived preparation, r1 / 2026-10-01. Current authorization: populate code documentation, not implement or execute the product.

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-019 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED; drafting assistance does not assign the future implementation executor. |
| Requested outcome and instruction/source | Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, mocked heterogeneous routing and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. User requested initial TASK/Spec Kit breakdown from the full PRD while Architecture remains forthcoming. |
| Included scope / exclusions | Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, mocked heterogeneous routing and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. Exclusions: No experiment becomes a Phase 1 prerequisite or production behavior by default; no arbitrary expansion of globally blacklisted features. Unspecified experimental success targets remain pending source. |
| PRD clause and architecture node references | [PRD r1](../sources/PRD-Full.r1.txt) §1.3, §3.2.7, §4.3.1, §4.3.2, §4.7, §4.8, §4.9.1, §4.9.2, §6.12; applicable §§1–2 and §6. Architecture nodes/revision PENDING_SOURCE. |
| Working checkout / branch / base | Documentation prepared in existing ai4r_xiaoyang checkout at a8f36245a83358a606bf00f83a64b3353a41c4cd; implementation NOT_STARTED, candidate NOT_BUILT. |
| Affected code/document paths | docs/tasks/M1/M1-019/TASK.md; specs/M1-019-experimental-tracks/{spec.md,plan.md,tasks.md}. Product and executable test paths PENDING_DESIGN. |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-019-experimental-tracks/ | One directory owned by M1-019 |
| spec.md | [spec](../../../../specs/M1-019-experimental-tracks/spec.md) | Requirements, ACs and threshold sources |
| plan.md | [plan](../../../../specs/M1-019-experimental-tracks/plan.md) | Behavioral decomposition and verification design; technical realization pending |
| tasks.md | [tasks](../../../../specs/M1-019-experimental-tracks/tasks.md) | Work/progress and AC-to-evidence mapping |
| evidence/ | specs/M1-019-experimental-tracks/evidence/ | Reserved for actual verification runs; none produced |
| Supporting artifacts | [PRD baseline](../sources/PRD-Full.r1.txt) | Registered source snapshot; no separate approval/review cards |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-001 / M1-IF-001@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-003 / M1-IF-003@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-004 / M1-IF-004@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-005 / M1-IF-005@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-006 / M1-IF-006@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-007 / M1-IF-007@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-009 / M1-IF-009@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-SYSTEM / relevant baseline journey | Source-required operational baseline evidence | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |

- [M1-001 canonical TASK](../M1-001/TASK.md#4-embedded-cross-module-agreements)
- [M1-003 canonical TASK](../M1-003/TASK.md#4-embedded-cross-module-agreements)
- [M1-004 canonical TASK](../M1-004/TASK.md#4-embedded-cross-module-agreements)
- [M1-005 canonical TASK](../M1-005/TASK.md#4-embedded-cross-module-agreements)
- [M1-006 canonical TASK](../M1-006/TASK.md#4-embedded-cross-module-agreements)
- [M1-007 canonical TASK](../M1-007/TASK.md#4-embedded-cross-module-agreements)
- [M1-009 canonical TASK](../M1-009/TASK.md#4-embedded-cross-module-agreements)
- [M1-SYSTEM canonical TASK](../M1-SYSTEM/TASK.md)

Definition-time dependencies are not a demand to finish every provider/consumer TASK first. Exact architecture edges remain pending. Full connected checks require actual relevant implementations; stubs only support independent block preparation.

## 4. Embedded cross-module agreements

### M1-IF-019 at r0

**Status: PRD semantic draft; not an implementation-ready interface.** Architecture must supply the exact realization before consumers implement against it.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M1-019 within isolated experimental tracks only; no mandatory live Phase 1 consumer. Participating experimental routing/compiler/planner/build components are PENDING_DESIGN; baseline TASKs supply reference behavior, not experiment completion dependencies. |
| Purpose / source requirement | §1.3, §3.2.7, §4.3.1, §4.3.2, §4.7, §4.8, §4.9.1, §4.9.2, §6.12; Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, mocked heterogeneous routing and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. |
| Inputs: fields, types, units, required/optional, validation | An operational comparable Phase 1 baseline, source-designated experimental feature descriptions and later registered experiment-specific architecture/product inputs. Exact field types/units/validation PENDING_DESIGN except source-stated semantics. |
| Outputs: fields, types, units, semantics, guarantees | Isolated experimental execution and attributable comparison evidence; no automatic production promotion. Experimental payload/API design is PENDING_DESIGN. |
| States and invariants | Respect §§1–2, the source-defined phase boundary and owning spec ACs. Never infer technical states not yet designed. |
| Errors, timeout, retry, cancellation | Source-required failures and fixed budget behavior are retained in spec.md. Error representation, cancellation propagation and transport behavior PENDING_DESIGN; no new automatic retry/repair policy. |
| Side effects and idempotency | Only source-permitted local effects. Repeated-call/side-effect identity semantics PENDING_DESIGN; no blanket idempotency claim. |
| Compatibility and migration | r0 initial semantic baseline. Architecture revision produces a versioned agreement change, consumer updates and impacted evidence invalidation; no silent schema compatibility assumption. |
| Machine-readable schema / source path | PENDING_DESIGN; no schema generated or implementation path invented. |
| Provider/consumer verification responsibilities | M1-019/V01 onward in plan.md check local behavior; applicable V90 checks actual connected handoff. M1-SYSTEM owns integrated journeys; optional Phase 2 evidence is not a Phase 1 completion dependency. |
| Open agreement questions | SOURCE-019: Further imported compiler behavior beyond the supplied source, additional Code Mode evaluation criteria, candidate model identifiers and experiment-specific quality thresholds require the relevant future inputs; do not infer them from old week3 model studies. ARCH-019: Experiment branch/checkouts, technical isolation and interfaces await Architecture; independent registration can proceed now. SCOPE-019: This is a preliminary non-release-blocking coordination TASK. Split into separate bounded experiment TASKs when their source detail arrives, maintaining source/AC ownership and retiring no IDs silently. |

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-019-OPEN-01 / 2026-10-01 | SOURCE-019: Further imported compiler behavior beyond the supplied source, additional Code Mode evaluation criteria, candidate model identifiers and experiment-specific quality thresholds require the relevant future inputs; do not infer them from old week3 model studies. | Corresponding ACs and plan blocks; T001/T002; M1-IF-019@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-019-OPEN-02 / 2026-10-01 | ARCH-019: Experiment branch/checkouts, technical isolation and interfaces await Architecture; independent registration can proceed now. | Corresponding ACs and plan blocks; T001/T002; M1-IF-019@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-019-OPEN-03 / 2026-10-01 | SCOPE-019: This is a preliminary non-release-blocking coordination TASK. Split into separate bounded experiment TASKs when their source detail arrives, maintaining source/AC ownership and retiring no IDs silently. | Corresponding ACs and plan blocks; T001/T002; M1-IF-019@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |

Progress belongs only in native tasks.md. No approval stage or additional task card is introduced.

