# Feature Specification: M1-015 - Scientific evidence evaluation and verdict
**TASK**: [M1-015](../../docs/tasks/M1/M1-015/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r1 / 2026-10-01
**Feature Branch**: ai4r_xiaoyang (document-preparation checkout; no feature branch created)
**Input**: [PRD-Full.r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §3.8 (all); sequencing §6.8; shared §§1–2; architecture PENDING_SOURCE.
**Status**: Preparing — PRD-derived requirements populated; architecture binding pending, runtime NOT_RUN.
Local IDs are qualified by M1-015; this is the only AC authority for this task.

## User Scenarios & Testing
### User Story 1 - Scientific evidence evaluation and verdict (Priority: P1)
A researcher receives an evidence-grounded scientific conclusion, including a rejected hypothesis when execution was correct.
**Independent Test**: Given admitted benchmark evidence, frozen blueprint and original brief, when evaluation runs, then bind results to logs and preregistered criteria, classify the scientific outcome and record limitations. A scientific FAIL remains a valid deliverable when the independent infrastructure Gate admits the evaluation.
**Acceptance Scenarios**:
1. Given source-conforming inputs and ready declared dependencies, when this bounded capability executes, then its artifacts and observable effects satisfy the ACs below and remain attributable to the run/capsule.
2. Given a prohibited action, invalid contract/evidence or source-defined failure, when execution or verification detects it, then preserve the failure and follow the shared halt/non-admission behavior; do not silently report completion or repair autonomously.
3. Given a connected consumer, when the provider submits an artifact/candidate, then respect the owning interface, governance boundary and version identity rather than infer success from a model response.

### Edge Cases
- Supply matched run artifacts and inspect bound context and capsule identity; inspect tool traces to confirm no external retrieval. Cross-run or inadmissible input variants are handled by the shared evidence/gate contracts.
- Use complete, null/missing and log-disagreeing metric fixtures; inspect evidence references and visible completeness/provenance findings. No false claim of verified metrics on fabricated or unsupported input.
- Use a plausible fixture and independently specified anomaly fixtures; capture invocation count, findings and execution trace proving no secondary experiment. Numeric plausibility boundaries must come from the registered rubric, not be invented here.
- Supply protocol-defined boundary, passing and failing measurements; compare decisions to independently computed fixture expectations and verify thresholds/data/measurement definitions remain unchanged.
- Test scientific pass and fail with fixed evidence and criteria, then actual Gate-to-Delivery release for scientifically negative evidence. Exercise other labels once their rubric is defined; verify no consensus/debate path.
- Use evidence requiring a follow-up recommendation; inspect verdict and compare input/code/protocol state before/after; observe no additional workflow nodes or code-writing calls.
Architecture supplies representation, timeout/cancellation and recovery details; there is no assumed retry or resume mechanism. Source-specific numerical limits are listed in ACs only. No real-service claim is established by fixtures or stubs.

## Requirements
### Functional Requirements
- **FR-001** (§3.8 introduction; §3.8.1): Use scientific_evaluator_capsule.md as the unified scientific-evaluation node, separate from verifier_capsule.md. Bind admitted Benchmark Payload, frozen Blueprint and original Brief into evaluation context; do not fetch live leaderboard or web evidence.
- **FR-002** (§3.8.2): Audit metric values against raw stdout/stderr and require non-null empirical entries for every blueprint-declared dependent variable. Do not substitute LLM text for sandbox evidence; cryptographic provenance and multi-node cross-verification are outside this stage's scope.
- **FR-003** (§3.8.3): Perform one qualitative sanity-check turn of the observed delta and flag physically/computationally implausible results, such as negative memory measurements. Do not run perturbation or secondary counterfactual experiments.
- **FR-004** (§3.8.4; §2.5): Compare measured deltas deterministically with the preregistered falsifiability/acceptance thresholds and preserve those criteria unchanged after observing results.
- **FR-005** (§3.8.5; §§1.4,6.8): Emit one of PASS, FAIL, INCONCLUSIVE or CONDITIONALLY_ACCEPTABLE and catalog blockers, residual constraints and operational risks in a single classification pass without multi-agent voting. Scientific FAIL must reach Delivery when the independent infrastructure Gate admits the stage. Exact inconclusive/conditional criteria remain Q02 rather than invented policy.
- **FR-006** (§3.8.6; §§2.6,2.7): Record technical bottlenecks, algorithmic limitations and future research directions in Evaluation_Verdict.json without changing code or triggering patches, reruns, self-healing or iterative re-benchmarking.
### Key Entities
Benchmark_Payload.json; immutable Hypothesis_Blueprint.json; Research_Brief.json; Evaluation_Verdict.json; scientific verdict distinct from infrastructure gate verdict. See [M1-IF-015@r0](../../docs/tasks/M1/M1-015/TASK.md#4-embedded-cross-module-agreements) for canonical preliminary semantic handoff; exact schemas are PENDING_DESIGN.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD r1 §3.8 introduction; §3.8.1 / FR-001 / US1 | Use scientific_evaluator_capsule.md as the unified scientific-evaluation node, separate from verifier_capsule.md. Bind admitted Benchmark Payload, frozen Blueprint and original Brief into evaluation context; do not fetch live leaderboard or web evidence. | BLOCK |
| AC-002 | PRD r1 §3.8.2 / FR-002 / US1 | Audit metric values against raw stdout/stderr and require non-null empirical entries for every blueprint-declared dependent variable. Do not substitute LLM text for sandbox evidence; cryptographic provenance and multi-node cross-verification are outside this stage's scope. | BLOCK |
| AC-003 | PRD r1 §3.8.3 / FR-003 / US1 | Perform one qualitative sanity-check turn of the observed delta and flag physically/computationally implausible results, such as negative memory measurements. Do not run perturbation or secondary counterfactual experiments. | BLOCK |
| AC-004 | PRD r1 §3.8.4; §2.5 / FR-004 / US1 | Compare measured deltas deterministically with the preregistered falsifiability/acceptance thresholds and preserve those criteria unchanged after observing results. | BLOCK |
| AC-005 | PRD r1 §3.8.5; §§1.4,6.8 / FR-005 / US1 | Emit one of PASS, FAIL, INCONCLUSIVE or CONDITIONALLY_ACCEPTABLE and catalog blockers, residual constraints and operational risks in a single classification pass without multi-agent voting. Scientific FAIL must reach Delivery when the independent infrastructure Gate admits the stage. Exact inconclusive/conditional criteria remain Q02 rather than invented policy. | BLOCK, BOUNDARY |
| AC-006 | PRD r1 §3.8.6; §§2.6,2.7 / FR-006 / US1 | Record technical bottlenecks, algorithmic limitations and future research directions in Evaluation_Verdict.json without changing code or triggering patches, reruns, self-healing or iterative re-benchmarking. | BLOCK |
System-level end-to-end acceptance is owned by M1-SYSTEM, not copied into this task. Every row has block/check/work correspondence in plan.md and tasks.md; no runtime result is implied.

## Scope and Assumptions
- Included / excluded scope: Read-only scientific evaluation of admitted benchmark evidence against the frozen hypothesis; produce verdict, constraints and follow-ups. Distinct from the infrastructure verifier. Excludes live external evidence fetching, cryptographic provenance system, counterfactual runs, threshold changes, debate, repairs and reruns.
- Shared boundaries: local single-user scientific lane; fixed Phase 1 DAG and authorized tools/resources; frozen scientific protocol; separate scientific result and infrastructure release; authoritative system evidence; no automatic repair, live RSI, model training, external publication or distributed/cloud baseline execution (§§1–2). Shared enforcement ACs belong to their owning tasks; this task's observable compliance is covered above.
- Consumed TASK agreements: [M1-IF-014@r0](../../docs/tasks/M1/M1-014/TASK.md#4-embedded-cross-module-agreements); [M1-IF-012@r0](../../docs/tasks/M1/M1-012/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../../docs/tasks/M1/M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the single static Codex CLI route through M1-001/M1-004; role/consumer needs do not authorize a new model pool. Record actual provider/model/version when available; no guessed model identifier.
- Assumptions and unresolved source inputs: M1-015-Q01: Architecture is PENDING_SOURCE; exact schema, model-bound execution, source paths, provenance binding and classifier integration are PENDING_DESIGN. Resolution: Register architecture and bind implementation/fixture details; preserve source-defined artifact meanings. M1-015-Q02: §3.8.5 names INCONCLUSIVE and CONDITIONALLY_ACCEPTABLE without a complete decision rubric distinguishing them. Do not invent thresholds or silently map them to infrastructure verdicts. Resolution: Obtain source-backed rubric or explicit product clarification before verifying those label conditions; prepare PASS/FAIL and read-only checks independently.
- Architecture boundary: exact payload types, APIs, IPC, class/module design, process topology, storage paths and security realization remain PENDING_DESIGN pending the architecture source. Source-given names/constraints above are requirements, not proof of implementation.
- System tasks: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) consumes this task's current candidate, block/boundary evidence and source constraints for complete journeys; its acceptance remains separate.

This is the AC authority. Technical realization stays in plan.md; progress/results stay in tasks.md.

