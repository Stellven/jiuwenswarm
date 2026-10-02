# TASK: M1-002 - Local configuration, identity and execution boundaries

PRD-derived preparation, r1 / 2026-10-01. Current authorization: populate code documentation, not implement or execute the product.

## 1. Identity

| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-002 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED; drafting assistance does not assign the future implementation executor. |
| Requested outcome and instruction/source | Local single-user settings, source-defined configuration precedence, static endpoint aliases, local-session authentication, restricted execution requirements and budget configuration. User requested initial TASK/Spec Kit breakdown from the full PRD while Architecture remains forthcoming. |
| Included scope / exclusions | Local single-user settings, source-defined configuration precedence, static endpoint aliases, local-session authentication, restricted execution requirements and budget configuration. Exclusions: Enterprise identity, multi-user profiles, cloud configuration/secrets, remote cluster declarations, dynamic billing and heavy container/hypervisor orchestration are outside this M1 scope. |
| PRD clause and architecture node references | [PRD r1](../sources/PRD-Full.r1.txt) §5.4, §5.6; applicable §§1–2 and §6. Architecture nodes/revision PENDING_SOURCE. |
| Working checkout / branch / base | Documentation prepared in existing ai4r_xiaoyang checkout at a8f36245a83358a606bf00f83a64b3353a41c4cd; implementation NOT_STARTED, candidate NOT_BUILT. |
| Affected code/document paths | docs/tasks/M1/M1-002/TASK.md; specs/M1-002-local-runtime-config/{spec.md,plan.md,tasks.md}. Product and executable test paths PENDING_DESIGN. |

## 2. Spec Kit registry

| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-002-local-runtime-config/ | One directory owned by M1-002 |
| spec.md | [spec](../../../../specs/M1-002-local-runtime-config/spec.md) | Requirements, ACs and threshold sources |
| plan.md | [plan](../../../../specs/M1-002-local-runtime-config/plan.md) | Behavioral decomposition and verification design; technical realization pending |
| tasks.md | [tasks](../../../../specs/M1-002-local-runtime-config/tasks.md) | Work/progress and AC-to-evidence mapping |
| evidence/ | specs/M1-002-local-runtime-config/evidence/ | Reserved for actual verification runs; none produced |
| Supporting artifacts | [PRD baseline](../sources/PRD-Full.r1.txt) | Registered source snapshot; no separate approval/review cards |

## 3. Dependencies

| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-001 / M1-IF-001@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-003 / M1-IF-003@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-004 / M1-IF-004@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-005 / M1-IF-005@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-006 / M1-IF-006@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-017 / M1-IF-017@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |
| M1-018 / M1-IF-018@r0 | Source-required provider/consumer behavior; see canonical TASK | Definition: agree relevant semantics before coupled implementation. Runtime: working participating blocks before connection checks; whole TASK completion is not a prerequisite to independent preparation. | Dependent blocks/checks below; exact block-to-interface mapping PENDING_DESIGN. |

- [M1-001 canonical TASK](../M1-001/TASK.md#4-embedded-cross-module-agreements)
- [M1-003 canonical TASK](../M1-003/TASK.md#4-embedded-cross-module-agreements)
- [M1-004 canonical TASK](../M1-004/TASK.md#4-embedded-cross-module-agreements)
- [M1-005 canonical TASK](../M1-005/TASK.md#4-embedded-cross-module-agreements)
- [M1-006 canonical TASK](../M1-006/TASK.md#4-embedded-cross-module-agreements)
- [M1-017 canonical TASK](../M1-017/TASK.md#4-embedded-cross-module-agreements)
- [M1-018 canonical TASK](../M1-018/TASK.md#4-embedded-cross-module-agreements)

Definition-time dependencies are not a demand to finish every provider/consumer TASK first. Exact architecture edges remain pending. Full connected checks require actual relevant implementations; stubs only support independent block preparation.

## 4. Embedded cross-module agreements

### M1-IF-002 at r0

**Status: PRD semantic draft; not an implementation-ready interface.** Architecture must supply the exact realization before consumers implement against it.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M1-002; consumers M1-001, M1-003, M1-004, M1-005, M1-006, M1-008, M1-009, M1-013, M1-014, M1-017 and M1-018; M1-SYSTEM verifies connected outcomes. Semantic task allocation only; actual API/process edges remain PENDING_DESIGN. |
| Purpose / source requirement | §5.4, §5.6; Local single-user settings, source-defined configuration precedence, static endpoint aliases, local-session authentication, restricted execution requirements and budget configuration. |
| Inputs: fields, types, units, required/optional, validation | Project/global configuration, local OS identity, authenticated session requests, declared execution permissions and configured capsule limits. Exact field types/units/validation PENDING_DESIGN except source-stated semantics. |
| Outputs: fields, types, units, semantics, guarantees | Effective local configuration, authenticated local access and an execution boundary satisfying PRD permissions; schema, API, process and enforcement design PENDING_DESIGN. |
| States and invariants | Respect §§1–2, the source-defined phase boundary and owning spec ACs. Never infer technical states not yet designed. |
| Errors, timeout, retry, cancellation | Source-required failures and fixed budget behavior are retained in spec.md. Error representation, cancellation propagation and transport behavior PENDING_DESIGN; no new automatic retry/repair policy. |
| Side effects and idempotency | Only source-permitted local effects. Repeated-call/side-effect identity semantics PENDING_DESIGN; no blanket idempotency claim. |
| Compatibility and migration | r0 initial semantic baseline. Architecture revision produces a versioned agreement change, consumer updates and impacted evidence invalidation; no silent schema compatibility assumption. |
| Machine-readable schema / source path | PENDING_DESIGN; no schema generated or implementation path invented. |
| Provider/consumer verification responsibilities | M1-002/V01 onward in plan.md check local behavior; applicable V90 checks actual connected handoff. M1-SYSTEM owns integrated journeys; optional Phase 2 evidence is not a Phase 1 completion dependency. |
| Open agreement questions | ARCH-002: Architecture must define effective configuration schema, reload semantics, platform mapping, privilege boundaries and IPC/authentication mechanisms. Do not claim that a venv or privilege drop alone proves filesystem/network confinement. POLICY-002: Budget values and any unspecified defaults come from registered product/configuration inputs; no universal numeric thresholds are invented. IF-002: Fixture-isolation startup behavior must be connected with M1-018 provisioning and M1-017 startup; definition-time coordination is required before dependent checks, not completion of the entire RSI loop. |

## 5. Changes and unresolved decisions

| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-002-OPEN-01 / 2026-10-01 | ARCH-002: Architecture must define effective configuration schema, reload semantics, platform mapping, privilege boundaries and IPC/authentication mechanisms. Do not claim that a venv or privilege drop alone proves filesystem/network confinement. | Corresponding ACs and plan blocks; T001/T002; M1-IF-002@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-002-OPEN-02 / 2026-10-01 | POLICY-002: Budget values and any unspecified defaults come from registered product/configuration inputs; no universal numeric thresholds are invented. | Corresponding ACs and plan blocks; T001/T002; M1-IF-002@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |
| M1-002-OPEN-03 / 2026-10-01 | IF-002: Fixture-isolation startup behavior must be connected with M1-018 provisioning and M1-017 startup; definition-time coordination is required before dependent checks, not completion of the entire RSI loop. | Corresponding ACs and plan blocks; T001/T002; M1-IF-002@r0 | Only affected implementation/checks wait; all current runtime evidence NOT_RUN. | UNASSIGNED; register the missing source/design decision, update native records and parent allocation. |

Progress belongs only in native tasks.md. No approval stage or additional task card is introduced.

