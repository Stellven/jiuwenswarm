# Feature Specification: M1-009 - Fixed-flow requirement and intention compilation

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

**TASK**: [M1-009](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r3 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang (documentation checkout only; no implementation branch or candidate selected)
**Input**: [Current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt), §3.2.1–§3.2.7 Phase 1; §4.7 introduction and §4.7.1–§4.7.5 Phase 1/common M1; applicable §§1.3–1.6 and 2. Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; use the linked architecture responsibilities and diagrams.
**Status**: Preparing — PRD-backed requirements populated; Architecture supplied; detailed realization pending. This is not a runtime result.

## User Scenarios & Testing
### User Story 1 - Fixed-flow requirement and intention compilation (Priority: P1)
Two bounded, separately checked intent and requirement compiler invocations, normalized scope/constraints, fixed conservative defaults, target metrics and versioned Research Brief. Preserve the fixed-flow route as an available fallback when Phase 3 is introduced.
**Independent Test**: Exercise the versioned fixtures and source-derived observable outcomes in the AC table through the bounded producer; actual upstream, shared governance and downstream wiring is covered separately by V90.
**Acceptance Scenarios**:
1. Given qualified research intake with explicit scope and metric targets, when the bounded compiler pipeline runs, then it produces the fixed Research Brief and submits it for governed handoff.
2. Given missing optional parameters, when compilation runs, then the adopted fixed defaults apply without dialogue; given empty objective/path, readiness fails.
3. Given no advanced intention-compiler integration, when the static route is selected, then the Phase 1 compiler remains available with its configured model endpoint.

### Edge Cases
Explicit versus missing constraints, empty readiness inputs, conflicting intake, invalid JSON/semantic omissions, absent reliable token telemetry, model failure, non-advancing Gate and post-start mutation are covered. Exact contradictory-input/default decisions await local elaboration; no dynamic replanning or human approval loop is added.

## Requirements
### Functional Requirements
- **FR-001**: Under D5, use two bounded compiler invocations in one non-interactive entry, with a combined frozen budget, to extract the core objective and select only the Scientific Research lane; do not ideate or select a solution. Source: Current PRD §3.2.1; §4.7 introduction, §4.7.1 Phase 1.
- **FR-002**: Extract explicit in_scope/out_of_scope and parameters strictly from supplied intake; bind the ingested local reference buffer without searching for missing context. Source: Current PRD §3.2.2; §4.7.2 Phase 1.
- **FR-003**: Apply fixed conservative defaults for missing parameters without interactive clarification; assert nonempty core objective and input-directory paths before readiness. Source: Current PRD §3.2.3; §4.7.3 Phase 1.
- **FR-004**: Extract declared token/runtime/hardware/resource boundaries into the Brief; preserve the distinction between enforceable execution-time/invocation limits and declarative token limits when usage telemetry is unavailable. Source: Current PRD §3.2.4; §4.7.4.
- **FR-005**: Separate mandatory_requirements from optional_preferences in the compiled JSON. Source: Current PRD §3.2.5.
- **FR-006**: Compile concrete target evaluation metrics and decision conditions for downstream hypothesis/benchmarking, based on the input and adopted fixed policy. Source: Current PRD §3.2.6.
- **FR-007**: Package the final schema-bound, versioned Brief and submit it to Gate for the deterministic Swarmflow handoff; do not await asynchronous human confirmation or modify the contract after DAG execution begins. Source: Current PRD §3.2.7 Phase 1 and blacklist; §4.7.5 Phase 1/blacklist.
- **FR-008**: Keep the fixed bounded compiler pipeline self-contained and available as the stable fallback, using the configured model endpoint; Phase 3 availability must not be a Phase 1 dependency. Source: Current PRD §3.2 external dependency flag; §4.7 introduction; §1.3–§1.4; §2.2, §2.6–§2.8, §2.10; §6.5.

### Key Entities
Research Brief; explicit objective; in_scope/out_of_scope; mandatory_requirements/optional_preferences; declared execution/token constraints; target metrics; fixed default policy.
Canonical semantic boundary: [M1-IF-009@r0](TASK.md#4-embedded-cross-module-agreements). Named PRD payloads and fields are recorded as source obligations, not a finalized technical schema.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | Current PRD §3.2.1; §4.7 introduction, §4.7.1 Phase 1 / FR-001 / US1 | A supplied research objective becomes the Brief objective through the static route; no multi-lane selection or autonomous solution generation is performed. | BLOCK, BOUNDARY |
| AC-002 | Current PRD §3.2.2; §4.7.2 Phase 1 / FR-002 / US1 | Scope and context are traceable to supplied text; absent context is not filled by web search, autonomous repository/history mining or invented intent. | BLOCK, BOUNDARY |
| AC-003 | Current PRD §3.2.3; §4.7.3 Phase 1 / FR-003 / US1 | Missing values follow the registered default policy with zero clarification turns; empty objective/path fails readiness. The single_gpu example does not authorize an invented complete defaults table. | BLOCK, BOUNDARY |
| AC-004 | Current PRD §3.2.4; §4.7.4 / FR-004 / US1 | User-stated bounds survive compilation with their meaning; no local resource scan or permission negotiation occurs. Missing reliable token telemetry does not become a false zero-usage or enforced-token-budget claim. | BLOCK, BOUNDARY |
| AC-005 | Current PRD §3.2.5 / FR-005 / US1 | Explicit mandatory metrics remain mandatory and preferences remain optional; compilation does not silently promote preferences or drop mandatory constraints. | BLOCK, BOUNDARY |
| AC-006 | Current PRD §3.2.6 / FR-006 / US1 | Each required target metric is stated with an observable direction/bound when defined by source; example 20% latency/16 GB values are not universal thresholds. Unresolved product inputs are not fabricated. | BLOCK, BOUNDARY |
| AC-007 | Current PRD §3.2.7 Phase 1 and blacklist; §4.7.5 Phase 1/blacklist / FR-007 / US1 | Intent, scope, constraints and metrics reach the next fixed node only after an advancing persisted Gate verdict; an inadmissible Brief cannot trigger that node. No happy-path approval wait is inserted. | BLOCK, BOUNDARY |
| AC-008 | Current PRD §3.2 external dependency flag; §4.7 introduction; §1.3–§1.4; §2.2, §2.6–§2.8, §2.10; §6.5 / FR-008 / US1 | With advanced compiler/Leader integration absent, the static Brief path still executes through admitted CC/model/evidence/Gate services; fallback is not falsely presented as model-free or offline inference. | BLOCK, BOUNDARY |

All allocated behavior and exclusions are covered above. Product examples remain examples; source-backed literal limits such as the stated one-path/bounded execution obligations remain requirements. No new performance, reliability or model-quality threshold is invented.

## Scope and Assumptions
- Included scope: Two bounded, separately checked intent and requirement compiler invocations, normalized scope/constraints, fixed conservative defaults, target metrics and versioned Research Brief. Preserve the fixed-flow route as an available fallback when Phase 3 is introduced.
- Excluded scope: Dynamic/interactive compiler integration, Leader/Cluster routing and dynamic classification are owned by M1-019. Phase 1 excludes solution generation, context web search, interactive clarification, host profiling, asynchronous confirmation waits, autonomous permission negotiation and post-hoc contract changes. Global non-goals in §2.12 still apply. Dynamic Phase 3 behavior is isolated under [M1-019](../M1-019/TASK.md), not a prerequisite for this Phase 1 task.
- Consumed TASK agreements: [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the single configured Codex CLI route (§3.0, §4.3). Exact deployment model/version: PENDING_CONFIGURATION, to be recorded by M1-004. The compiler budget does not include the separate Gate verifier invocation; no heterogeneous router is introduced.
- Source/architecture boundary: §1.6 and §6.13 reserve exact schemas, APIs, process topology, storage layout and detailed mechanisms to Architecture. All such bindings remain PENDING_DESIGN; the architecture source is [the current design](../../../../architecture/build-package/README.md).
- Assumptions and unresolved source inputs: Q-009-01: Architecture is supplied in [the current design](../../../../architecture/build-package/README.md); bind final Brief schema/versioning, readiness errors and handoff mechanics while retaining §3.2/§4.7 semantics. Phase 3 remains isolated. Q-009-02: Register the actual fixed prompt/default and acceptance policy during specification/design elaboration; PRD examples do not define every missing parameter, conflicting-input choice or fallback threshold. Independent source-backed cases can proceed. Q-009-03: Actual configured Codex model/version/telemetry must be recorded at execution; no exact model identifier is supplied by this PRD.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete journeys and integrated candidate acceptance. This spec owns only M1-009's ACs; it does not duplicate system ACs or shared Gate policy.
- Runtime failure handling and explicit human restart use canonical M1-006/007 behavior; no independent retry mechanism is assumed.

This spec is the AC authority. Provisional design/check procedures are in plan.md; work and evidence are in tasks.md.

D5 reconciliation: the accepted intent is an intermediate artifact; only the later accepted Research_Brief.json satisfies the full compiler exit. Both compiler outputs receive independent checking. No dialogue, solution selection or unsupported requirements are added. Existing compiler ACs apply to the complete pipeline; TRIAL-1 does not satisfy this task alone.
