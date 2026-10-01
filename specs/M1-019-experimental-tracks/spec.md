# Feature Specification: M1-019 - Isolated Phase 2 experiment registration and integration

**TASK**: [TASK](../../docs/tasks/M1/M1-019/TASK.md)
**Parent TASKS**: [M1 TASKS](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r1 / 2026-10-01
**Feature Branch**: NOT_STARTED for implementation; documentation uses the existing checkout.
**Input**: [registered PRD r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §1.3, §3.2.7, §4.3.1, §4.3.2, §4.7, §4.8, §4.9.1, §4.9.2, §6.12; global §§1–2, §6. Architecture PENDING_SOURCE.
**Status**: Preparing; source-derived requirements populated, architecture-dependent contracts pending.

## User Scenarios & Testing

### User Story 1 - Isolated Phase 2 experiment registration and integration (Priority: P2; non-blocking experiment)

Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, mocked heterogeneous routing and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD.

**Independent Test**: Exercise the source-defined behavior with controlled inputs, then connect its real providers/consumers; procedures and retained observations are in plan.md.

**Acceptance Scenarios**:

1. Given the prerequisites for AC-001, when its planned action is exercised, then the observable result must satisfy AC-001. Procedure: Run the baseline without experimental components and compare its static routing/DAG/gate policies with an experiment-enabled isolated candidate; disabling a track must not remove Phase 1 functionality.
2. Given the prerequisites for AC-002, when its planned action is exercised, then the observable result must satisfy AC-002. Procedure: Prepare research/code/spec requests, irrelevant repository/history context and an ambiguous request. Verify the source-defined experimental classification, relevant context filtering, interactive clarification and Leader-consumable contract while the static fallback remains unchanged. Exact realization and additional unstated quality thresholds remain pending.
3. Given the prerequisites for AC-003, when its planned action is exercised, then the observable result must satisfy AC-003. Procedure: Supply mock metadata covering the source-defined candidate categories; run the actual routing logic against a DAG-provided capsule and verify compatibility filtering, lightweight LLM-based selection and unchanged Phase 1 routing. Record the selection judge service/configuration separately. Mock candidate APIs establish routing behavior only, never actual candidate availability or quality.
4. Given the prerequisites for AC-004, when its planned action is exercised, then the observable result must satisfy AC-004. Procedure: Inspect source allocation and experimental wiring; record each actual experiment's input source, isolation and comparison baseline. Functional acceptance beyond named scope waits for its own sourced criteria.
5. Given the prerequisites for AC-005, when its planned action is exercised, then the observable result must satisfy AC-005. Procedure: Compare source versions and enabled baseline features before/after an isolated experiment; verify no automatic promotion occurs and any requested promotion has traceable revised source coverage.

### Edge Cases

Applicable rejection, unavailable-dependency, security, governance and phase-isolation cases are included in the ACs below. Do not assert unsupported recovery, arbitrary retry, unprovided numeric defaults or product behavior. Pending cases are recorded in Scope and Assumptions; unrelated preparation continues.

## Requirements

### Functional Requirements

- **FR-001** (§1.3, §2.7, §2.12, §6.12): Phase 2 work remains isolated; the required Phase 1 baseline can operate and be accepted with every experimental feature disabled. Experiments begin against an operational relevant baseline.
- **FR-002** (§3.2.7, §4.7): Dynamic intention/Leader experiments preserve the fixed-flow fallback and Research Brief handoff while testing source-defined research/code/spec classification, relevant repository/history context filtering, interactive clarification and task semantics for Leader consumption; no dynamic behavior enters the default production path.
- **FR-003** (§4.3.1, §4.3.2): On the source-required separate mocked-API track, the registry represents mixed proprietary, open-weight and domain-specialist candidates; the router reads the DAG-provided capsule, filters compatible candidates and selects through lightweight LLM-based judgment. Phase 1 remains the Codex CLI baseline; no candidate model identifiers are invented.
- **FR-004** (§1.3, §4.8.1, §4.8.2, §4.8.3, §4.9.1, §4.9.2, §6.12): On isolated tracks, the Leader consumes Research_Brief.json, decomposes bounded research sub-tasks, constructs dependencies and checks disconnected nodes, missing data and capability mismatches; infeasible experimental graphs return to the Intention Compiler. Code Mode experiments exercise workspace provisioning/dependency discovery and AST-aware line-level diffs/multi-file refactoring. Dynamic discovery remains an explicitly named experiment whose detailed acceptance awaits its source. These behaviors are not mandatory live Phase 1 capabilities.
- **FR-005** (§1.3, §6.12, §6.13): Promotion into Phase 1 requires a recorded product/architecture revision and corresponding TASKS/spec changes; experimental results alone cannot modify live contracts, permissions or release scope.

### Key Entities

An operational comparable Phase 1 baseline, source-designated experimental feature descriptions and later registered experiment-specific architecture/product inputs. Isolated experimental execution and attributable comparison evidence; no automatic production promotion. Experimental payload/API design is PENDING_DESIGN. Exact cross-module semantics are owned by [M1-019 / M1-IF-019@r0](../../docs/tasks/M1/M1-019/TASK.md#4-embedded-cross-module-agreements).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §1.3, §2.7, §2.12, §6.12 / FR-001 / US1 | Phase 2 work remains isolated; the required Phase 1 baseline can operate and be accepted with every experimental feature disabled. Experiments begin against an operational relevant baseline. | BOUNDARY |
| AC-002 | §3.2.7, §4.7 / FR-002 / US1 | Dynamic intention/Leader experiments preserve the fixed-flow fallback and Research Brief handoff while testing source-defined research/code/spec classification, relevant repository/history context filtering, interactive clarification and task semantics for Leader consumption; no dynamic behavior enters the default production path. | BOUNDARY |
| AC-003 | §4.3.1, §4.3.2 / FR-003 / US1 | On the source-required separate mocked-API track, the registry represents mixed proprietary, open-weight and domain-specialist candidates; the router reads the DAG-provided capsule, filters compatible candidates and selects through lightweight LLM-based judgment. Phase 1 remains the Codex CLI baseline; no candidate model identifiers are invented. | BLOCK, BOUNDARY |
| AC-004 | §1.3, §4.8.1, §4.8.2, §4.8.3, §4.9.1, §4.9.2, §6.12 / FR-004 / US1 | On isolated tracks, the Leader consumes Research_Brief.json, decomposes bounded research sub-tasks, constructs dependencies and checks disconnected nodes, missing data and capability mismatches; infeasible experimental graphs return to the Intention Compiler. Code Mode experiments exercise workspace provisioning/dependency discovery and AST-aware line-level diffs/multi-file refactoring. Dynamic discovery remains an explicitly named experiment whose detailed acceptance awaits its source. These behaviors are not mandatory live Phase 1 capabilities. | BOUNDARY |
| AC-005 | §1.3, §6.12, §6.13 / FR-005 / US1 | Promotion into Phase 1 requires a recorded product/architecture revision and corresponding TASKS/spec changes; experimental results alone cannot modify live contracts, permissions or release scope. | BOUNDARY |

Thresholds are the source-defined rules or explicitly supplied run/configuration values; example numbers are not new release targets. A check's test settings are not global product requirements.

## Scope and Assumptions

- Included: Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, mocked heterogeneous routing and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD.
- Excluded: No experiment becomes a Phase 1 prerequisite or production behavior by default; no arbitrary expansion of globally blacklisted features. Unspecified experimental success targets remain pending source.
- Consumed TASK agreements: [M1-IF-001@r0](../../docs/tasks/M1/M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../../docs/tasks/M1/M1-009/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the registered Codex CLI endpoint; an exact underlying model/version is captured when available from the actual configured service. No model family or proprietary version is invented. Phase 2 model candidates, where applicable, remain separately sourced.
- Architecture-dependent fields/interfaces/runtime paths: PENDING_DESIGN until Architecture is registered; source technical examples are constraints/inputs, not validated feasibility claims.
- Unresolved: SOURCE-019: Further imported compiler behavior beyond the supplied source, additional Code Mode evaluation criteria, candidate model identifiers and experiment-specific quality thresholds require the relevant future inputs; do not infer them from old week3 model studies.
- Unresolved: ARCH-019: Experiment branch/checkouts, technical isolation and interfaces await Architecture; independent registration can proceed now.
- Unresolved: SCOPE-019: This is a preliminary non-release-blocking coordination TASK. Split into separate bounded experiment TASKs when their source detail arrives, maintaining source/AC ownership and retiring no IDs silently.
- System contribution: [M1-SYSTEM](../M1-SYSTEM-governed-research/spec.md) owns whole-system journeys. This spec retains its feature acceptance authority.

This file owns acceptance; plan.md owns implementation and verification methods, tasks.md owns progress and evidence.

