# TASK: M1-019 - Isolated Phase 3 experiment registration and integration

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.


PRD-derived preparation, r3 / 2026-10-06. Current authorization: populate code documentation, not implement or execute the product.

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-019 / r3 / 2026-10-06 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED; drafting assistance does not assign the future implementation executor. |
| Requested outcome and instruction/source | Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, access-gated heterogeneous routing and alternate-Verifier and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. User requested update of existing TASK/Spec Kit records from the latest attached PRD with the current architecture supplied. |
| Included scope / exclusions | Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, access-gated heterogeneous routing and alternate-Verifier and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. Exclusions: No experiment becomes an M1 release prerequisite or production behavior by default; no arbitrary expansion of globally blacklisted features. Unspecified experimental success targets remain pending source. |
| PRD clause and architecture node references | [current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) §1.3, §3.2.7, §4.3.1, §4.3.2, §4.7, §4.8, §4.9.1, §4.9.2, §6.12; applicable §§1–2 and §6. [Architecture entry and views](../../../../architecture/build-package/README.md), October 6 baseline. Also §4.3.4 and §5.6.1 govern alternate Verifier and access-gated configuration. |
| Working checkout / branch / base | Documentation prepared in existing ai4r_xiaoyang checkout at d9fe483ea64c273ef831886bfa83819f6d5bb21c; implementation NOT_STARTED, candidate NOT_BUILT. |
| Affected code/document paths | docs/code/Missions/M1/M1-019/TASK.md; docs/code/Missions/M1/M1-019/{spec.md,plan.md,tasks.md}. Product and executable test paths PENDING_DESIGN. |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-019/ | One directory owned by M1-019 |
| spec.md | [spec](spec.md) | Requirements, ACs and threshold sources |
| plan.md | [plan](plan.md) | Behavioral decomposition and verification design; technical realization pending |
| tasks.md | [tasks](tasks.md) | Work/progress and AC-to-evidence mapping |
| evidence/ | docs/code/Missions/M1/M1-019/evidence/ | Reserved for actual verification runs; none produced |
| Supporting artifacts | [PRD baseline](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) | Registered source snapshot; no separate approval/review cards |

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

[M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements) supplies approved evaluation profiles and access-gated configuration; actual wiring remains PENDING_DESIGN.

Definition-time dependencies are not a demand to finish every provider/consumer TASK first. Exact architecture edges remain pending. Full connected checks require actual relevant implementations; stubs only support independent block preparation.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for task-level coding design. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.


### M1-IF-019 at r0

**Status: PRD semantic draft; not an implementation-ready interface.** Architecture must supply the exact realization before consumers implement against it.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-019; consumers . Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | §1.3, §3.2.7, §4.3.1, §4.3.2, §4.7, §4.8, §4.9.1, §4.9.2, §6.12; Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, access-gated heterogeneous routing and alternate-Verifier and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. Also §4.3.4 alternate-Verifier, §5.6.1 endpoint configuration and §1.3 access gate. |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — The coding agent defines payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — The coding agent defines concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — The coding agent defines runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — The coding agent defines error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — The coding agent defines effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — The coding agent defines compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — The coding agent defines actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | SOURCE-019: Further imported compiler behavior beyond the supplied source, additional Code Mode evaluation criteria, candidate model identifiers and experiment-specific quality thresholds require the relevant future inputs; do not infer them from old week3 model studies. ARCH-019: Experiment branch/checkouts, technical isolation and interfaces await Architecture; independent registration can proceed now. SCOPE-019: This is a preliminary non-release-blocking coordination TASK. Split into separate bounded experiment TASKs when their source detail arrives, maintaining source/AC ownership and retiring no IDs silently. |

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this current PRD update.

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-019-OPEN-01 / 2026-10-01 | SOURCE-019: Further imported compiler behavior beyond the supplied source, additional Code Mode evaluation criteria, candidate model identifiers and experiment-specific quality thresholds require the relevant future inputs; do not infer them from old week3 model studies. | Corresponding ACs and plan blocks; T001/T002; M1-IF-019@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-019-OPEN-02 / 2026-10-01 | ARCH-019: Experiment branch/checkouts, technical isolation and interfaces await Architecture; independent registration can proceed now. | Corresponding ACs and plan blocks; T001/T002; M1-IF-019@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-019-OPEN-03 / 2026-10-01 | SCOPE-019: This is a preliminary non-release-blocking coordination TASK. Split into separate bounded experiment TASKs when their source detail arrives, maintaining source/AC ownership and retiring no IDs silently. | Corresponding ACs and plan blocks; T001/T002; M1-IF-019@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| PRD-R2 / 2026-10-02 | §1.3, §4.3.1/§4.3.2/§4.3.4, §5.6.1, §6.12. Adds approved real routing/one alternate-Verifier experiment; removes old lightweight-LLM prescription. | AC-001, AC-003, AC-006; native plan/tasks correspondence; M1-IF-019@r0 | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Implementation-dependent definitions before affected implementation. |

Progress belongs only in native tasks.md. No approval stage or additional task card is introduced.
