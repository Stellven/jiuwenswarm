# Feature Specification: M1-009 - Fixed-flow requirement and intention compilation
**TASK**: [M1-009](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (documentation checkout only; no implementation branch or candidate selected)
**Input**: [PRD-Full.r2](../sources/PRD-Full.r2.txt), §3.2.1–§3.2.7 Phase 1 (lines 541–601); §4.7 introduction and §4.7.1–§4.7.5 Phase 1/common M1 (lines 1837–1895); applicable §§1.3–1.6 and 2. Architecture: PENDING_SOURCE; no architecture nodes have been invented.
**Status**: Preparing — PRD-backed requirements populated; Architecture and named local decisions pending. This is not a runtime result.

## User Scenarios & Testing
### User Story 1 - Fixed-flow requirement and intention compilation (Priority: P1)
One-shot Scientific Research compiler, normalized scope/constraints, fixed conservative defaults, target metrics and versioned Research Brief. Preserve the fixed-flow route as an available fallback when Phase 2 is introduced.
**Independent Test**: Exercise the versioned fixtures and source-derived observable outcomes in the AC table through the bounded producer; actual upstream, shared governance and downstream wiring is covered separately by V90.
**Acceptance Scenarios**:
1. Given qualified research intake with explicit scope and metric targets, when the one-shot compiler runs, then it produces the fixed Research Brief and submits it for governed handoff.
2. Given missing optional parameters, when compilation runs, then the adopted fixed defaults apply without dialogue; given empty objective/path, readiness fails.
3. Given no advanced intention-compiler integration, when the static route is selected, then the Phase 1 compiler remains available with its configured model endpoint.

### Edge Cases
Explicit versus missing constraints, empty readiness inputs, conflicting intake, invalid JSON/semantic omissions, absent reliable token telemetry, model failure, non-advancing Gate and post-start mutation are covered. Exact contradictory-input/default decisions await local elaboration; no dynamic replanning or human approval loop is added.

## Requirements
### Functional Requirements
- **FR-001**: Use one bounded single-turn compiler pass to extract the core objective and select only the Scientific Research lane; do not ideate or select a solution. Source: PRD-Full.r2 §3.2.1; §4.7 introduction, §4.7.1 Phase 1 (lines 547–554, 1837–1851).
- **FR-002**: Extract explicit in_scope/out_of_scope and parameters strictly from supplied intake; bind the ingested local reference buffer without searching for missing context. Source: PRD-Full.r2 §3.2.2; §4.7.2 Phase 1 (lines 556–563, 1857–1865).
- **FR-003**: Apply fixed conservative defaults for missing parameters without interactive clarification; assert nonempty core objective and input-directory paths before readiness. Source: PRD-Full.r2 §3.2.3; §4.7.3 Phase 1 (lines 565–570, 1867–1875).
- **FR-004**: Extract declared token/runtime/hardware/resource boundaries into the Brief; preserve the distinction between enforceable execution-time/invocation limits and declarative token limits when usage telemetry is unavailable. Source: PRD-Full.r2 §3.2.4; §4.7.4 (lines 572–577, 1877–1885).
- **FR-005**: Separate mandatory_requirements from optional_preferences in the compiled JSON. Source: PRD-Full.r2 §3.2.5 (lines 579–582).
- **FR-006**: Compile concrete target evaluation metrics and decision conditions for downstream hypothesis/benchmarking, based on the input and adopted fixed policy. Source: PRD-Full.r2 §3.2.6 (lines 584–589).
- **FR-007**: Package the final schema-bound, versioned Brief and submit it to Gate for the deterministic Swarmflow handoff; do not await asynchronous human confirmation or modify the contract after DAG execution begins. Source: PRD-Full.r2 §3.2.7 Phase 1 and blacklist; §4.7.5 Phase 1/blacklist (lines 591–601, 1887–1895).
- **FR-008**: Keep the fixed one-shot compiler self-contained and available as the stable fallback, using the configured model endpoint; Phase 2 availability must not be a Phase 1 dependency. Source: PRD-Full.r2 §3.2 external dependency flag; §4.7 introduction; §1.3–§1.4; §2.2, §2.6–§2.8, §2.10; §6.5.

### Key Entities
Research Brief; explicit objective; in_scope/out_of_scope; mandatory_requirements/optional_preferences; declared execution/token constraints; target metrics; fixed default policy.
Canonical semantic boundary: [M1-IF-009@r0](TASK.md#4-embedded-cross-module-agreements). Named PRD payloads and fields are recorded as source obligations, not a finalized technical schema.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD-Full.r2 §3.2.1; §4.7 introduction, §4.7.1 Phase 1 (lines 547–554, 1837–1851) / FR-001 / US1 | A supplied research objective becomes the Brief objective through the static route; no multi-lane selection or autonomous solution generation is performed. | BLOCK, BOUNDARY |
| AC-002 | PRD-Full.r2 §3.2.2; §4.7.2 Phase 1 (lines 556–563, 1857–1865) / FR-002 / US1 | Scope and context are traceable to supplied text; absent context is not filled by web search, autonomous repository/history mining or invented intent. | BLOCK, BOUNDARY |
| AC-003 | PRD-Full.r2 §3.2.3; §4.7.3 Phase 1 (lines 565–570, 1867–1875) / FR-003 / US1 | Missing values follow the registered default policy with zero clarification turns; empty objective/path fails readiness. The single_gpu example does not authorize an invented complete defaults table. | BLOCK, BOUNDARY |
| AC-004 | PRD-Full.r2 §3.2.4; §4.7.4 (lines 572–577, 1877–1885) / FR-004 / US1 | User-stated bounds survive compilation with their meaning; no local resource scan or permission negotiation occurs. Missing reliable token telemetry does not become a false zero-usage or enforced-token-budget claim. | BLOCK, BOUNDARY |
| AC-005 | PRD-Full.r2 §3.2.5 (lines 579–582) / FR-005 / US1 | Explicit mandatory metrics remain mandatory and preferences remain optional; compilation does not silently promote preferences or drop mandatory constraints. | BLOCK, BOUNDARY |
| AC-006 | PRD-Full.r2 §3.2.6 (lines 584–589) / FR-006 / US1 | Each required target metric is stated with an observable direction/bound when defined by source; example 20% latency/16 GB values are not universal thresholds. Unresolved product inputs are not fabricated. | BLOCK, BOUNDARY |
| AC-007 | PRD-Full.r2 §3.2.7 Phase 1 and blacklist; §4.7.5 Phase 1/blacklist (lines 591–601, 1887–1895) / FR-007 / US1 | Intent, scope, constraints and metrics reach the next fixed node only after an advancing persisted Gate verdict; an inadmissible Brief cannot trigger that node. No happy-path approval wait is inserted. | BLOCK, BOUNDARY |
| AC-008 | PRD-Full.r2 §3.2 external dependency flag; §4.7 introduction; §1.3–§1.4; §2.2, §2.6–§2.8, §2.10; §6.5 / FR-008 / US1 | With advanced compiler/Leader integration absent, the static Brief path still executes through admitted CC/model/evidence/Gate services; fallback is not falsely presented as model-free or offline inference. | BLOCK, BOUNDARY |

All allocated behavior and exclusions are covered above. Product examples remain examples; source-backed literal limits such as the stated one-path/bounded execution obligations remain requirements. No new performance, reliability or model-quality threshold is invented.

## Scope and Assumptions
- Included scope: One-shot Scientific Research compiler, normalized scope/constraints, fixed conservative defaults, target metrics and versioned Research Brief. Preserve the fixed-flow route as an available fallback when Phase 2 is introduced.
- Excluded scope: Dynamic/interactive compiler integration, Leader/Cluster routing and dynamic classification are owned by M1-019. Phase 1 excludes solution generation, context web search, interactive clarification, host profiling, asynchronous confirmation waits, autonomous permission negotiation and post-hoc contract changes. Global non-goals in §2.12 still apply. Dynamic Phase 2 behavior is isolated under [M1-019](../M1-019/TASK.md), not a prerequisite for this Phase 1 task.
- Consumed TASK agreements: [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the single configured Codex CLI route (§3.0, §4.3). Exact deployment model/version: PENDING_CONFIGURATION, to be recorded by M1-004. One compiler pass does not include the separate Gate verifier invocation; no heterogeneous router is introduced.
- Source/architecture boundary: §1.6 and §6.13 reserve exact schemas, APIs, process topology, storage layout and detailed mechanisms to Architecture. All such bindings remain PENDING_DESIGN; the architecture source is PENDING_SOURCE.
- Assumptions and unresolved source inputs: Q-009-01: Architecture is PENDING_SOURCE; bind final Brief schema/versioning, readiness errors and handoff mechanics while retaining §3.2/§4.7 semantics. Phase 2 remains isolated. Q-009-02: Register the actual fixed prompt/default and acceptance policy during specification/design elaboration; PRD examples do not define every missing parameter, conflicting-input choice or fallback threshold. Independent source-backed cases can proceed. Q-009-03: Actual configured Codex model/version/telemetry must be recorded at execution; no exact model identifier is supplied by this PRD.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete journeys and integrated candidate acceptance. This spec owns only M1-009's ACs; it does not duplicate system ACs or shared Gate policy.
- Runtime failure handling and explicit human restart use canonical M1-006/007 behavior; no independent retry mechanism is assumed.

This spec is the AC authority. Provisional design/check procedures are in plan.md; work and evidence are in tasks.md.
