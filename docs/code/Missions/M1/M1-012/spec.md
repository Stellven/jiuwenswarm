# Feature Specification: M1-012 - Immutable hypothesis and experimental protocol
**TASK**: [M1-012](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (documentation checkout only; no implementation branch or candidate selected)
**Input**: [PRD-Full.r2](../sources/PRD-Full.r2.txt), §3.5.1–§3.5.5 (lines 732–777); applicable §§1.3–1.6 and 2. Architecture: PENDING_SOURCE; no architecture nodes have been invented.
**Status**: Preparing — PRD-backed requirements populated; Architecture and named local decisions pending. This is not a runtime result.

## User Scenarios & Testing
### User Story 1 - Immutable hypothesis and experimental protocol (Priority: P1)
Translate the selected opportunity into one falsifiable claim and a pre-registered Hypothesis_Blueprint.json: baseline, variables, validation data, measurements, concrete mechanism, immutable thresholds and verification procedure.
**Independent Test**: Exercise the versioned fixtures and source-derived observable outcomes in the AC table through the bounded producer; actual upstream, shared governance and downstream wiring is covered separately by V90.
**Acceptance Scenarios**:
1. Given an accepted opportunity, Brief and supplied baseline/dataset, when hypothesis generation runs, then one falsifiable experimental blueprint is frozen before Builder starts.
2. Given a later consumer attempts to change the validation data, measurement rule or threshold, when the governed boundary is exercised, then the original scientific protocol remains authoritative and the inadmissible artifact does not advance.
3. Given a non-falsifiable claim or missing required empirical resource, when validation runs, then no successful ready-for-POC contract is fabricated.
4. Given a required metric, when the Blueprint is accepted, then AC-004 freezes both outcome boundaries and permitted classification before code/results; later changes cannot become valid downstream protocol.

### Edge Cases
Multiple claims, missing/wrong baseline, unbound or substituted dataset, missing success/falsification boundaries or absent preregistered classification rules, unsupported mechanism, downstream protocol mutation, stale run and non-advancing Gate are included. No numerical result is required at hypothesis time; exact failure representation awaits Architecture.

## Requirements
### Functional Requirements
- **FR-001**: Form one direct one-sentence testable technical claim from the selected Opportunity Card, specifying expected effect and applicable research object/situation. Source: PRD-Full.r2 §3.5.1 (lines 736–743).
- **FR-002**: Define independent/dependent variables, exact baseline and measurement relationship; bind evaluation to a static/standard/user-supplied validation dataset already ingested in 3.1. Source: PRD-Full.r2 §3.5.2 (lines 745–752); §2.5.
- **FR-003**: Specify a concrete technical mechanism for testing the opportunity without counter-evidence probing or iterative parameter evolution. Source: PRD-Full.r2 §3.5.3 (lines 754–759).
- **FR-004** (§3.5.4 (lines 761-768); §1.4; §2.5): For each required metric, preregister explicit success and falsification thresholds and permitted classification rules in Hypothesis_Blueprint.json before POC generation or empirical observation. Between-boundary values default to INCONCLUSIVE unless another permitted classification is defined before execution. Downstream cannot change rules after results; no automatic p-value/power thresholds or universal example threshold.
- **FR-005**: Produce Hypothesis_Blueprint.json with methodology, constraints and step-by-step verification plan; downstream stages may build their harness but cannot change validation dataset path, measurement functions or acceptance thresholds; submit to Gate before Builder. Source: PRD-Full.r2 §3.5.5 (lines 769–777).
- **FR-006**: Preserve run/stage/capsule evidence for the single pre-registered protocol; reject inadmissible hypotheses without autonomous repair or reinterpretation of scientific results. Source: PRD-Full.r2 §1.3–§1.5; §2.2, §2.5–§2.8, §2.10; §6.6–§6.7.

### Key Entities
Single technical claim; independent/dependent variables; exact baseline; bound validation dataset; measurement definition; mechanism; pre-registered success/falsification boundaries and classification rules; Hypothesis_Blueprint.json.
Canonical semantic boundary: [M1-IF-012@r0](TASK.md#4-embedded-cross-module-agreements). Named PRD payloads and fields are recorded as source obligations, not a finalized technical schema.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD-Full.r2 §3.5.1 (lines 736–743) / FR-001 / US1 | The blueprint advances exactly one traceable claim on the deterministic path; no competing parallel claim pool is created. | BLOCK, BOUNDARY |
| AC-002 | PRD-Full.r2 §3.5.2 (lines 745–752); §2.5 / FR-002 / US1 | Claim variables and baseline are explicit, and the validation resource matches intake binding; no synthetic validation set, new scrape, substituted resource or manufactured measurement is introduced. | BLOCK, BOUNDARY |
| AC-003 | PRD-Full.r2 §3.5.3 (lines 754–759) / FR-003 / US1 | The intervention is specific enough to describe the intended POC change and remains within the selected opportunity; no autonomous experimental iteration occurs. | BLOCK, BOUNDARY |
| AC-004 | PRD r2 §3.5.4 (lines 761-768); §1.4; §2.5 / FR-004 / US1 | For each required metric, preregister explicit success and falsification thresholds and permitted classification rules in Hypothesis_Blueprint.json before POC generation or empirical observation. Between-boundary values default to INCONCLUSIVE unless another permitted classification is defined before execution. Downstream cannot change rules after results; no automatic p-value/power thresholds or universal example threshold. | BLOCK, BOUNDARY |
| AC-005 | PRD-Full.r2 §3.5.5 (lines 769–777) / FR-005 / US1 | Accepted blueprint contains the required semantic plan, remains authoritative downstream and is available only through governed handoff. This stage writes no executable POC/benchmark code. | BLOCK, BOUNDARY |
| AC-006 | PRD-Full.r2 §1.3–§1.5; §2.2, §2.5–§2.8, §2.10; §6.6–§6.7 / FR-006 / US1 | A missing/unsupported/stale protocol does not release Builder; valid accepted protocol advances with intact evidence. Hypothesis definition does not claim empirical success or take ownership of Stage 3.8 scientific verdict. | BLOCK, BOUNDARY |

All allocated behavior and exclusions are covered above. Product examples remain examples; source-backed literal limits such as the stated one-path/bounded execution obligations remain requirements. No new performance, reliability or model-quality threshold is invented.

## Scope and Assumptions

- Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7. Actual code/module/process boundaries, typed payloads/APIs/errors, coordination, storage/durability, security/settings mechanisms and executable test entry points remain PENDING_DESIGN; this spec states product outcomes only.
- Included scope: Translate the selected opportunity into one falsifiable claim and a pre-registered Hypothesis_Blueprint.json: baseline, variables, validation data, measurements, concrete mechanism, immutable thresholds and verification procedure.
- Excluded scope: Multiple competing claims/parallel tests, synthetic or newly scraped validation data, counter-evidence probing, iterative parameter evolution, dynamic statistical power/p-value threshold generation and execution-code writing are excluded. Global non-goals in §2.12 still apply. Dynamic Phase 2 behavior is isolated under [M1-019](../M1-019/TASK.md), not a prerequisite for this Phase 1 task.
- Consumed TASK agreements: [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-011@r0](../M1-011/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Configured static Codex CLI endpoint via M1-004; actual model/version/prompt recorded at execution. No parallel hypothesis agents, training, tuning or dynamic model route is authorized.
- Source/architecture boundary: §1.6 and §6.13 reserve exact schemas, APIs, process topology, storage layout and detailed mechanisms to Architecture. All such bindings remain PENDING_DESIGN; the architecture source is PENDING_SOURCE.
- Assumptions and unresolved source inputs: Q-012-01: Architecture PENDING_SOURCE: define exact Blueprint schema/version binding, immutable representation, downstream read/violation behavior and code/test paths. Do not select hashing/storage/IPC here. Q-012-02: Task-specific metric/baseline/dataset/threshold inputs must be supplied or derived under the adopted product policy before dependent implementation/verification; PRD numeric examples are not defaults.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete journeys and integrated candidate acceptance. This spec owns only M1-012's ACs; it does not duplicate system ACs or shared Gate policy.
- Runtime failure handling and explicit human restart use canonical M1-006/007 behavior; no independent retry mechanism is assumed.

This spec is the AC authority. Provisional design/check procedures are in plan.md; work and evidence are in tasks.md.
