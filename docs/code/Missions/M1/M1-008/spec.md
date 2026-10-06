# Feature Specification: M1-008 - Local research intake and resource binding
**TASK**: [M1-008](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (documentation checkout only; no implementation branch or candidate selected)
**Input**: [PRD-Full.r2](../sources/PRD-Full.r2.txt), §3.1.1–§3.1.5 (lines 466–537); applicable §§1.3–1.6 and 2. Architecture: PENDING_SOURCE; no architecture nodes have been invented.
**Status**: Preparing — PRD-backed requirements populated; Architecture and named local decisions pending. This is not a runtime result.

## User Scenarios & Testing
### User Story 1 - Local research intake and resource binding (Priority: P1)
Capture local CLI/Web research requests, extract permitted reference text, bind supplied project assets and validation data, qualify intake and preserve provenance. The UI implementation belongs to M1-017.
**Independent Test**: Exercise the versioned fixtures and source-derived observable outcomes in the AC table through the bounded producer; actual upstream, shared governance and downstream wiring is covered separately by V90.
**Acceptance Scenarios**:
1. Given permitted local documents and a supplied repository/data directory, when intake runs, then text and separate run-bound resources are available to compilation.
2. Given an empty prompt or unreadable input directory, when qualification runs, then the run halts without releasing compilation.

### Edge Cases
Empty prompt, unreadable/missing specified directory, unsupported extraction format, size boundary, malformed document and cross-run binding are covered. Extraction-error detail and normalization policy await design; no retry loop or autonomous recovery is authorized.

## Requirements
### Functional Requirements
- **FR-001**: Accept the raw natural-language request from the local CLI argument and native local Web UI without treating raw text as a confirmed requirement. Source: PRD-Full.r2 §3.1.1 (lines 470–480).
- **FR-002**: Extract .txt/.md/.pdf reference text from explicitly supplied local resources; bind code directory and validation data separately to the active run, recording local path, allowed resource type and run_id. Source: PRD-Full.r2 §3.1.2 (lines 482–503).
- **FR-003**: Bind intake to the local single-user profile and current Swarmflow run identity without cross-session user-state persistence. Source: PRD-Full.r2 §3.1.3 (lines 505–514).
- **FR-004**: Apply programmatic file-size qualification and record local path, size and ingest timestamp; exclude semantic deduplication and intake-document hashing/signing. Source: PRD-Full.r2 §3.1.4 (lines 516–525).
- **FR-005**: Deterministically reject and halt on an empty user-prompt string or unreadable specified input directory; otherwise produce the combined prompt/reference-text dictionary for compilation. Source: PRD-Full.r2 §3.1.5 (lines 527–537).
- **FR-006**: Supply run-bound intake evidence and use the shared governed transition into requirement compilation within the fixed local research flow. Source: PRD-Full.r2 §1.3 Phase 1; §1.4; §2.2–§2.4, §2.6–§2.10; §6.5 (lines 2334–2352).

### Key Entities
Raw request; extracted reference buffer; resource binding (reference_document, project_asset, validation_data); local profile; active run; qualified intake package.
Canonical semantic boundary: [M1-IF-008@r0](TASK.md#4-embedded-cross-module-agreements). Named PRD payloads and fields are recorded as source obligations, not a finalized technical schema.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD-Full.r2 §3.1.1 (lines 470–480) / FR-001 / US1 | Each supported channel yields the supplied request for qualification; no external-channel or voice intake is introduced. | BLOCK, BOUNDARY |
| AC-002 | PRD-Full.r2 §3.1.2 (lines 482–503) / FR-002 / US1 | Reference text is available to compilation; code/data remain separately identified resources and are not automatically inserted into the reasoning buffer. No clone, scrape, dataset download, vectorization or Office extraction occurs. | BLOCK, BOUNDARY |
| AC-003 | PRD-Full.r2 §3.1.3 (lines 505–514) / FR-003 / US1 | Inputs from run A are attributable to A; a fresh run B does not inherit A's user session state or mislabel A's resources. | BLOCK, BOUNDARY |
| AC-004 | PRD-Full.r2 §3.1.4 (lines 516–525) / FR-004 / US1 | Files violating the adopted size limit are rejected; accepted resource provenance records the required metadata. The PRD's >50 MB example is not silently promoted to a fixed threshold. | BLOCK, BOUNDARY |
| AC-005 | PRD-Full.r2 §3.1.5 (lines 527–537) / FR-005 / US1 | Empty prompt and unreadable-directory cases produce no qualified success; valid readable intake produces a dictionary preserving prompt and extracted text. Intake does not invoke an LLM to decide logical validity. | BLOCK, BOUNDARY |
| AC-006 | PRD-Full.r2 §1.3 Phase 1; §1.4; §2.2–§2.4, §2.6–§2.10; §6.5 (lines 2334–2352) / FR-006 / US1 | Qualified artifacts are submitted through the registered evidence/Gate boundary; rejected, stale or non-advancing intake does not release compilation. Local resource ownership and permitted side effects remain intact. | BLOCK, BOUNDARY |

All allocated behavior and exclusions are covered above. Product examples remain examples; source-backed literal limits such as the stated one-path/bounded execution obligations remain requirements. No new performance, reliability or model-quality threshold is invented.

## Scope and Assumptions
- Included scope: Capture local CLI/Web research requests, extract permitted reference text, bind supplied project assets and validation data, qualify intake and preserve provenance. The UI implementation belongs to M1-017.
- Excluded scope: External chat channels, speech recognition, intake web scraping, repository cloning, autonomous dataset downloads, vectorization, Office extraction, semantic deduplication, intake-document cryptographic hashing/signing, enterprise SSO, cross-session user state and intake LLM validity judgments are excluded by §3.1. Global non-goals in §2.12 still apply. Dynamic Phase 2 behavior is isolated under [M1-019](../M1-019/TASK.md), not a prerequisite for this Phase 1 task.
- Consumed TASK agreements: [M1-IF-017@r0](../M1-017/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Intake qualification is deterministic (§3.1.5). Any semantic Gate verification consumes the static Codex CLI route through M1-004/M1-007; intake does not introduce its own model route.
- Source/architecture boundary: §1.6 and §6.13 reserve exact schemas, APIs, process topology, storage layout and detailed mechanisms to Architecture. All such bindings remain PENDING_DESIGN; the architecture source is PENDING_SOURCE.
- Assumptions and unresolved source inputs: Q-008-01: Architecture source is PENDING_SOURCE; bind the intake representation, profile/run resource interfaces, error representation, extraction library, size-limit configuration and code/test paths without changing §3.1 behavior. Q-008-02: §3.1.4 gives >50 MB as an example. Record the adopted product/configuration bound and exact boundary semantics before asserting numeric file-size acceptance; do not fabricate a threshold.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete journeys and integrated candidate acceptance. This spec owns only M1-008's ACs; it does not duplicate system ACs or shared Gate policy.
- Runtime failure handling and explicit human restart use canonical M1-006/007 behavior; no independent retry mechanism is assumed.

This spec is the AC authority. Provisional design/check procedures are in plan.md; work and evidence are in tasks.md.
