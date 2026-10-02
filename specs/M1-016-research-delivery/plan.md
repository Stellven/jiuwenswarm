# Implementation Plan: M1-016 - Research report and local lifecycle delivery
**TASK**: [M1-016](../../docs/tasks/M1/M1-016/TASK.md) | **Spec**: [r2](spec.md)
**Revision / date**: r2 / 2026-10-02 | **Branch**: ai4r_xiaoyang (documents only)
**Input sources**: PRD-Full.r2, §3.9 (all); sequencing §6.9; shared §§1–2; architecture PENDING_SOURCE; consumed IFs r0.
This is a PRD-derived behavior/verification scaffold, **not completed architecture or permission to implement**.

## Summary
A researcher receives a local report and reproducible supporting artifacts, including a correctly executed experiment whose hypothesis failed. Decompose the source-required observable behavior into the blocks below; bind implementation decisions only when architecture is registered. Refer to spec.md for ACs rather than redefining thresholds.

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
One TASK/feature; parent owns allocation/dependencies; TASK owns preliminary IF; spec owns ACs; this plan owns behavior blocks/verification intent; tasks owns unchecked work and NOT_RUN evidence correspondence. All ACs have mapped blocks/checks. No separate checklist, reviewer gate, handoff or test report is created. Architecture/schema decisions remain pending rather than fabricated.

## Project Structure

Confirmed document paths: docs/tasks/M1/M1-016/TASK.md and specs/M1-016-research-delivery/spec.md, plan.md, tasks.md. Future specs/M1-016-research-delivery/evidence/ is only for actual verification records. Application, configuration, test and fixture locations are **PENDING_DESIGN** (minimum inputs 1, 4, 6 and 7); no application directory or schema is invented.

## Blocks and Dependencies

| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Bind admitted evidence and synthesize fixed-format report; AC-001, AC-002 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B02 | Package reusable local research artifacts; AC-003 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |
| B03 | Expose delivery and close lifecycle; AC-004 | PENDING_DESIGN (minimum inputs 1–5); observable obligations remain in the referenced ACs. | Provisional TASK section 3 document dependencies; actual runtime edges PENDING_DESIGN (1–3). | PENDING_DESIGN (1 and 7). |

Stable B IDs are provisional acceptance-responsibility groups, not modules, classes or processes. Define the affected agreements before their implementation; connect available real participants before boundary checks. Reciprocal document references do not require fully completed peer TASKs. All technical sequencing and durable coordination remain Architecture-owned.

## Interfaces and Technical Decisions

- Canonical owned/consumed agreement references: [TASK section 4](../../docs/tasks/M1/M1-016/TASK.md#4-embedded-cross-module-agreements). Provisional references: M1-IF-003@r0, M1-IF-004@r0, M1-IF-005@r0, M1-IF-006@r0, M1-IF-007@r0, M1-IF-009@r0, M1-IF-013@r0, M1-IF-014@r0, M1-IF-015@r0, M1-IF-016@r0, M1-IF-017@r0. They are document allocations, not frozen runtime contracts.
- Data models, storage, APIs/process boundaries, errors/recovery, security mechanisms, configuration precedence/application and executable check hooks are **PENDING_DESIGN**, as enumerated in Technical Context.
- Source constraints remain in spec.md, including any named artifact, local platform/IPC boundary, dependency declaration/install restriction, model-call minimization and explicit user action. Architecture realizes those constraints without silently changing acceptance.
- No new schema, runtime topology, technical alternative selection or implementation mechanism is supplied. Refine and version the canonical TASK agreements when Architecture arrives.

## Verification Design

| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BLOCK | M1-016/B01; M1-016/AC-001; M1-IF-016@r0 | Versioned local report template port PENDING_DESIGN; real runner/Gate binding for admission claims; real model call for synthesis claim. Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-001](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Procedure: Provide admitted positive and negative scientific results; inspect capsule/template and input binding. Confirm inadmissible evaluation cannot be used for normal delivery and audience requests do not cause custom format invention. Exact executable command/entry point PENDING_DESIGN; working directory is repository root or the architecture-bound test workspace recorded in evidence. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V02 | BLOCK | M1-016/B01; M1-016/AC-002; M1-IF-016@r0 | Versioned evidence-backed report fixtures and admissibility expectations; real model route with captured prompts/results for output quality. Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-002](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Generate reports from admitted positive, valid negative and preregistered INCONCLUSIVE verdicts. Compare material claims, methods, limitations and citations with frozen input evidence; retain the admitted classification and produce no new experiment or excluded format. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V03 | BLOCK | M1-016/B02; M1-016/AC-003; M1-IF-016@r0 | Local-real output workspace and POC/evidence artifacts; independent inventory expectations; no external publication credentials needed. Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-003](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Procedure: Inspect output membership and references against source artifacts; verify that a missing required artifact remains a visible failure under shared governance and no external publication call occurs. Exact executable command/entry point PENDING_DESIGN; working directory is repository root or the architecture-bound test workspace recorded in evidence. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V04 | BLOCK | M1-016/B03; M1-016/AC-004; M1-IF-016@r0 | Local-real display/Harness/evidence connection, valid scientific PASS and FAIL reports; final source-backed failure encoding PENDING_DESIGN. Actual fixture locations and fault-injection seams PENDING_DESIGN (7). | Exactly [AC-004](spec.md#measurable-outcomes), including its registered PRD r2 locator and exclusions; no threshold is redefined here. | Procedure: Connect actual report/package, Harness, Data Foundations and one supported local display; observe readable artifacts and persisted completion. Exercise a delivery/persistence failure and verify no unsupported completed-success claim; inspect absence of external messages. Exact executable command/entry point PENDING_DESIGN; working directory is repository root or the architecture-bound test workspace recorded in evidence. Actual executable/manual entry, implementation bindings and command are PENDING_DESIGN (7); actual working directory is PENDING_DESIGN (7). | Effective source/Architecture/IF/profile and candidate; immutable fixture IDs/expected outcomes and actual raw run records. Real dependencies where an integrated/provider outcome is asserted; stubs cannot establish it. |
| V90 | BOUNDARY | M1-IF-016@r0; AC-004 | Real connected participating producers/consumers and their applicable per-AC normal/failure cases; fixture IDs frozen before execution. | All listed source AC assertions cross the boundary unchanged; no stale success, forbidden effect or unauthorized downstream release. | Observe actual connected results, local evidence and downstream admission/effects. Exact entry, fault injection and commands PENDING_DESIGN (7). Actual working directory: PENDING_DESIGN (7). | Implemented relevant blocks and effective agreements, real connection traces, candidate/profile identities and retained results. Stub-only evidence cannot pass. |

These are behavioral verification cases, not executable procedures or completed results. Architecture supplies invocation/fault hooks, and the native foundation work binds independent versioned fixtures and any adopted product limits before dependent checks. Required skipped/missing cases cannot pass. Model checks retain exposed model/route/runtime identity, prompts/configuration, dataset/split/fixture IDs, preregistered repetitions/scoring, effective seeds where supported, latency boundaries and reliable available usage. No benchmark-only labels are inserted into provider requests solely for attribution. Current preparation performs no inference, install or runtime verification.

## System Candidate and Journeys

[M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete candidate journeys and cross-cutting acceptance. Supply current evidence for AC-001, AC-002, AC-003, AC-004, actual component/profile/IF identity and relevant source constraints. The candidate is NOT_BUILT and all current checks are NOT_RUN. Partial A/Gate/B, a single model response or a report does not establish complete M1 acceptance. Phase 2 evidence and mandatory-control ablations cannot substitute for the live Phase 1 baseline.

## Unresolved Decisions and Impact

- Architecture source is **PENDING_SOURCE**. All seven technical categories are **PENDING_DESIGN** and affect only dependent implementation/real checks, not independent source/fixture preparation. See TASK section 5 for local questions.
- Exact fixture versions, permitted environment/account availability, adopted budgets/caps and preregistered measurement repetitions must be bound before the affected verification; examples do not become universal thresholds.
- Latest PRD r2 controls active acceptance. Stable existing B/V/T IDs are retained; appended IDs cover new source behavior. Old r1-only numeric/mechanical RSI prescriptions are not active requirements. No runtime evidence exists to reuse or invalidate.
- Material source/IF/code/configuration/fixture changes require impact assessment, affected rows marked STALE if evidence later exists, retained raw history and matching downstream system revalidation.
