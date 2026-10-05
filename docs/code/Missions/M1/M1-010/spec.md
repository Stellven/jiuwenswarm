# Feature Specification: M1-010 - Bounded literature search and evidence-grounded ideation
**TASK**: [M1-010](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (documentation checkout only; no implementation branch or candidate selected)
**Input**: [PRD-Full.r2](../sources/PRD-Full.r2.txt), §3.3.1–§3.3.6 (lines 604–658); applicable §§1.3–1.6 and 2. Architecture: PENDING_SOURCE; no architecture nodes have been invented.
**Status**: Preparing — PRD-backed requirements populated; Architecture and named local decisions pending. This is not a runtime result.

## User Scenarios & Testing
### User Story 1 - Bounded literature search and evidence-grounded ideation (Priority: P1)
Admitted search_capsule generates a static query list, retrieves local and bounded academic evidence via allowlisted deepsearch, extracts verbatim query-linked text and produces 1–3 cited candidate ideas.
**Independent Test**: Exercise the versioned fixtures and source-derived observable outcomes in the AC table through the bounded producer; actual upstream, shared governance and downstream wiring is covered separately by V90.
**Acceptance Scenarios**:
1. Given an accepted Research Brief and permitted sources, when search executes, then fixed queries retrieve bounded evidence and produce 1–3 cited ideas.
2. Given unsupported citations or unapproved tool use, when evidence is checked, then screening is not released and the failure evidence remains available.

### Edge Cases
Sparse/empty evidence, over-limit connector results, unavailable/rate-limited connector, query mismatch, non-verbatim quote, unsupported citation, malformed output and prohibited tool access are included. No retries/requery loops are assumed; connector-specific errors await design.

## Requirements
### Functional Requirements
- **FR-001**: Use one LLM prompt under search_capsule.md to generate a static keyword-query list from the Research Brief. Source: PRD-Full.r2 §3.3.1 (lines 608–615).
- **FR-002**: Use allowlisted deepsearch for local buffer search and bounded structured queries to designated academic APIs, enforcing a programmatic Top-K external-paper limit per query in a single linear process. Source: PRD-Full.r2 §3.3.2 (lines 617–627).
- **FR-003**: Extract exact verbatim text chunks matching queries from retrieved local and external documents. Source: PRD-Full.r2 §3.3.3 (lines 629–634).
- **FR-004**: Group raw evidence chunks by their triggering query in a standardized JSON array. Source: PRD-Full.r2 §3.3.4 (lines 636–641).
- **FR-005**: Use a single-turn synthesis to produce 1–3 concrete ideas, each explicitly cited to retrieved material. Source: PRD-Full.r2 §3.3.5 (lines 643–649).
- **FR-006**: Package ideas and mapped citations into Candidate_Set.json and submit it to the independent Evaluator Gate without recursive coverage-review loops. Source: PRD-Full.r2 §3.3.6 (lines 651–658).
- **FR-007**: Keep search within the admitted capsule and Brief bounds, preserving run-bound source evidence and stopping through shared failure handling on prohibited or inadmissible outcomes. Source: PRD-Full.r2 §1.3–§1.4; §2.2, §2.4, §2.6–§2.10; §6.6 (lines 2354–2374).

### Key Entities
Static keyword query; allowlisted academic connector; bounded retrieval result; verbatim source chunk; query group; cited candidate idea; Candidate_Set.json.
Canonical semantic boundary: [M1-IF-010@r0](TASK.md#4-embedded-cross-module-agreements). Named PRD payloads and fields are recorded as source obligations, not a finalized technical schema.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD-Full.r2 §3.3.1 (lines 608–615) / FR-001 / US1 | Queries are derived from Brief scope and stay fixed during that search invocation; poor initial results do not trigger autonomous query reformulation. | BLOCK, BOUNDARY |
| AC-002 | PRD-Full.r2 §3.3.2 (lines 617–627) / FR-002 / US1 | Both permitted source modes are exercised; retrieval never exceeds the adopted per-query limit or calls unapproved crawling/browser/multi-agent search tools. arXiv/Semantic Scholar and K=5 are examples, not a fabricated mandatory connector inventory or threshold. | BLOCK, BOUNDARY |
| AC-003 | PRD-Full.r2 §3.3.3 (lines 629–634) / FR-003 / US1 | Every extracted chunk is traceable to actual retrieved text and matches it verbatim; no author-authority, publisher-bias or geographic credibility scoring is introduced. | BLOCK, BOUNDARY |
| AC-004 | PRD-Full.r2 §3.3.4 (lines 636–641) / FR-004 / US1 | Every retained chunk has the correct query grouping without invented trend or cross-domain analyses. | BLOCK, BOUNDARY |
| AC-005 | PRD-Full.r2 §3.3.5 (lines 643–649) / FR-005 / US1 | Output candidate count is between 1 and 3 inclusive; each idea has document-title, author or local-filename citations traceable to retrieved chunks; unsupported speculative proposals are not admissible. | BLOCK, BOUNDARY |
| AC-006 | PRD-Full.r2 §3.3.6 (lines 651–658) / FR-006 / US1 | A schema-conforming evidence-backed Candidate_Set reaches screening only through shared advancing Gate behavior; malformed output cannot advance. Resource limits follow endpoint telemetry policy, not unsupported exact token accounting. | BLOCK, BOUNDARY |
| AC-007 | PRD-Full.r2 §1.3–§1.4; §2.2, §2.4, §2.6–§2.10; §6.6 (lines 2354–2374) / FR-007 / US1 | No manufactured evidence, undeclared connector access, silent retry loop or gate bypass occurs; blocked external dependencies do not become fabricated research success. | BLOCK, BOUNDARY |

All allocated behavior and exclusions are covered above. Product examples remain examples; source-backed literal limits such as 1–3 candidate ideas remain requirements. No new performance, reliability or model-quality threshold is invented.

## Scope and Assumptions
- Included scope: Admitted search_capsule generates a static query list, retrieves local and bounded academic evidence via allowlisted deepsearch, extracts verbatim query-linked text and produces 1–3 cited candidate ideas.
- Excluded scope: Dynamic query reformulation, unconstrained web/browser scraping, parallel multi-agent search, authority/bias/geographic source evaluation, historical trend/cross-domain mapping, unsupported speculation and recursive search-coverage self-reflection are outside Phase 1. Global non-goals in §2.12 still apply. Dynamic Phase 2 behavior is isolated under [M1-019](../M1-019/TASK.md), not a prerequisite for this Phase 1 task.
- Consumed TASK agreements: [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Static configured Codex CLI endpoint via M1-004. Search has one query-generation prompt and one candidate-synthesis turn (§3.3); verifier uses a separate context. No model IDs, alternative providers or search swarm are invented.
- Source/architecture boundary: §1.6 and §6.13 reserve exact schemas, APIs, process topology, storage layout and detailed mechanisms to Architecture. All such bindings remain PENDING_DESIGN; the architecture source is PENDING_SOURCE.
- Assumptions and unresolved source inputs: Q-010-01: Architecture PENDING_SOURCE: bind search/output/citation schemas, source-text normalization, connector interface/error policy and code/test paths. No connector availability has been verified by documentation work. Q-010-02: Record the designated academic connectors, permitted query bounds and adopted Top-K value before numeric/real-service checks; PRD's connector list and maximum 5 are examples. Q-010-03: Zero usable evidence/zero supportable ideas is not permission to invent one; exact stage outcome/diagnostic needs local specification using the shared fail-fast Gate policy.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete journeys and integrated candidate acceptance. This spec owns only M1-010's ACs; it does not duplicate system ACs or shared Gate policy.
- Runtime failure handling and explicit human restart use canonical M1-006/007 behavior; no independent retry mechanism is assumed.

This spec is the AC authority. Provisional design/check procedures are in plan.md; work and evidence are in tasks.md.
