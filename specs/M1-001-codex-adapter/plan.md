# Implementation Plan: M1-001 - Codex CLI adapter
**TASK**: [M1-001](../../docs/tasks/M1/M1-001/TASK.md) | **Spec**: [r2](spec.md)
**Revision / date**: r2 / 2026-10-02 | **Branch**: ai4r_xiaoyang, existing checkout
**Input sources**: PRD r2, §3.0, §3.0.1, §3.0.2; sequencing §6.3; architecture PENDING_SOURCE; IF revisions in TASK.

## Summary
Prepare source-derived behavior and checks. The blocks below partition observable responsibilities; they do not designate final modules/classes/processes. Bind technical realization after architecture and inspection of existing code/callers/tests. Requirements and thresholds remain in spec.md.

## Technical Context

All seven technical categories are reserved for [Architecture minimum inputs](../../docs/tasks/M1/ARCHITECTURE_MINIMUM_INPUTS.txt):
- Ownership, modules, processes and implementation paths: **PENDING_DESIGN** (1).
- Typed handoffs, validation, errors, timeout, cancellation and duplicates: **PENDING_DESIGN** (2).
- Runtime sequencing, durable gate coordination and explicit-restart realization: **PENDING_DESIGN** (3).
- Storage, write ownership, lineage and freezing mechanics: **PENDING_DESIGN** (4).
- Execution confinement and security enforcement mechanisms: **PENDING_DESIGN** (5).
- OS/runtime versions, dependencies, configuration precedence/application: **PENDING_DESIGN** (6).
- Invocation, verification entry points and fault-injection seams: **PENDING_DESIGN** (7).

Source-mandated technologies, artifact names, permissions and observable constraints remain in spec.md and the registered PRD; these placeholders do not erase them. Phase 1 uses the static Codex CLI route. Actual account/model/environment availability is untested. Product limits and adopted fixture/profile inputs remain explicit source inputs; no numerical defaults are invented.

## Constitution Check
One TASK/feature; TASK owns IF, spec ACs, plan blocks/procedures, tasks work/evidence. Every AC maps to a source check and real connected-boundary check. No parallel approval/review/checklist cards. Architecture/fixture/candidate binding unresolved; runtime NOT_RUN. Documentation is not execution evidence.

## Project Structure

Confirmed document paths: docs/tasks/M1/M1-001/TASK.md and specs/M1-001-codex-adapter/spec.md, plan.md, tasks.md. Future specs/M1-001-codex-adapter/evidence/ is only for actual verification records. Application, configuration, test and fixture locations are **PENDING_DESIGN** (minimum inputs 1, 4, 6 and 7); no application directory or schema is invented.

## Blocks and Dependencies

| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Existing adapter and native completion compatibility; AC-001, AC-004 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B02 | Secured local invocation context; AC-002 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B03 | Provider abstraction and failure telemetry; AC-003 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B04 | Audited invocation boundary; AC-005 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |

Stable B IDs are provisional acceptance-responsibility groups, not modules, classes or processes. Define the affected agreements before their implementation; connect available real participants before boundary checks. Reciprocal document references do not require fully completed peer TASKs. All technical sequencing and durable coordination remain Architecture-owned.

## Interfaces and Technical Decisions

- Canonical owned/consumed agreement references: [TASK section 4](../../docs/tasks/M1/M1-001/TASK.md#4-embedded-cross-module-agreements). Provisional references: M1-IF-001@r0, M1-IF-002@r0, M1-IF-004@r0, M1-IF-005@r0. They are document allocations, not frozen runtime contracts.
- Data models, storage, APIs/process boundaries, errors/recovery, security mechanisms, configuration precedence/application and executable check hooks are **PENDING_DESIGN**, as enumerated in Technical Context.
- Source constraints remain in spec.md, including any named artifact, local platform/IPC boundary, dependency declaration/install restriction, model-call minimization and explicit user action. Architecture realizes those constraints without silently changing acceptance.
- No new schema, runtime topology, technical alternative selection or implementation mechanism is supplied. Refine and version the canonical TASK agreements when Architecture arrives.

## Verification Design

| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BOUNDARY | M1-001/B01; M1-001/AC-001; M1-IF-001@r0 | Existing code/caller inventory and one real bounded native request/response; external real Codex CLI/account plus local real native caller Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-001](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Existing code/caller inventory and one real bounded native request/response. Compare source-normal and expected-failure outcomes against every assertion in the AC. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V02 | BLOCK | M1-001/B02; M1-001/AC-002; M1-IF-001@r0 | Authorized caller, missing/wrong credential, inappropriate local context and listener/permission inspection; local real implementation; stubs only isolate dependencies Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-002](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Authorized caller, missing/wrong credential, inappropriate local context and listener/permission inspection. Compare source-normal and expected-failure outcomes against every assertion in the AC. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V03 | BLOCK | M1-001/B03; M1-001/AC-003; M1-IF-001@r0 | Provider consumer request, controlled timeout and missing/expired authentication; local real implementation; stubs only isolate dependencies Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-003](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Provider consumer request, controlled timeout and missing/expired authentication. Compare source-normal and expected-failure outcomes against every assertion in the AC. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V04 | BLOCK | M1-001/B01; M1-001/AC-004; M1-IF-001@r0 | Implementation/configuration inspection and out-of-scope streaming/dynamic-route requests; local real implementation; stubs only isolate dependencies Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-004](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Implementation/configuration inspection and out-of-scope streaming/dynamic-route requests. Compare source-normal and expected-failure outcomes against every assertion in the AC. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V05 | BLOCK | M1-001/B04; M1-001/AC-005; M1-IF-001@r0 | Source-relevant positive, boundary and prohibited-action fixtures prepared independently and versioned before execution. Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-005](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Compare local call-attribution records with the actual provider-bound request. Attempt a bypass through a supported invocation route; require audited participation. Confirm benchmark-only stage/role/capsule labels stay local while required task content is preserved. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V90 | BOUNDARY | M1-IF-001@r0; AC-001, AC-002, AC-003, AC-004, AC-005 | Real connected participating producers/consumers and their applicable per-AC normal/failure cases; fixture IDs frozen before execution. | All listed source AC assertions cross the boundary unchanged; no stale success, forbidden effect or unauthorized downstream release. | Observe actual connected results, local evidence and downstream admission/effects. Exact entry, fault injection and commands PENDING_DESIGN (7). Actual working directory: PENDING_DESIGN (7). | Implemented relevant blocks and effective agreements, real connection traces, candidate/profile identities and retained results. Stub-only evidence cannot pass. |

These are behavioral verification cases, not executable procedures or completed results. Architecture supplies invocation/fault hooks, and the native foundation work binds independent versioned fixtures and any adopted product limits before dependent checks. Required skipped/missing cases cannot pass. Model checks retain exposed model/route/runtime identity, prompts/configuration, dataset/split/fixture IDs, preregistered repetitions/scoring, effective seeds where supported, latency boundaries and reliable available usage. No benchmark-only labels are inserted into provider requests solely for attribution. Current preparation performs no inference, install or runtime verification.

## System Candidate and Journeys

[M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete candidate journeys and cross-cutting acceptance. Supply current evidence for AC-001, AC-002, AC-003, AC-004, AC-005, actual component/profile/IF identity and relevant source constraints. The candidate is NOT_BUILT and all current checks are NOT_RUN. Partial A/Gate/B, a single model response or a report does not establish complete M1 acceptance. Phase 2 evidence and mandatory-control ablations cannot substitute for the live Phase 1 baseline.

## Unresolved Decisions and Impact

- Architecture source is **PENDING_SOURCE**. All seven technical categories are **PENDING_DESIGN** and affect only dependent implementation/real checks, not independent source/fixture preparation. See TASK section 5 for local questions.
- Exact fixture versions, permitted environment/account availability, adopted budgets/caps and preregistered measurement repetitions must be bound before the affected verification; examples do not become universal thresholds.
- Latest PRD r2 controls active acceptance. Stable existing B/V/T IDs are retained; appended IDs cover new source behavior. Old r1-only numeric/mechanical RSI prescriptions are not active requirements. No runtime evidence exists to reuse or invalidate.
- Material source/IF/code/configuration/fixture changes require impact assessment, affected rows marked STALE if evidence later exists, retained raw history and matching downstream system revalidation.
