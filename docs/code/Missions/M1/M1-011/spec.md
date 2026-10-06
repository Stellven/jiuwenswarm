# Feature Specification: M1-011 - Fixed-rubric opportunity screening and selection

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

**TASK**: [M1-011](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r3 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang (documentation checkout only; no implementation branch or candidate selected)
**Input**: [Current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt), §3.4.1–§3.4.7; applicable §§1.3–1.6 and 2. Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; use the linked architecture responsibilities and diagrams.
**Status**: Preparing — PRD-backed requirements populated; Architecture supplied; detailed realization pending. This is not a runtime result.

## User Scenarios & Testing
### User Story 1 - Fixed-rubric opportunity screening and selection (Priority: P1)
Consolidate cited candidates, form structured Idea Cards, score novelty/feasibility/compute alignment with a fixed single-pass rubric, filter disallowed dependencies and deterministically select one opportunity.
**Independent Test**: Exercise the versioned fixtures and source-derived observable outcomes in the AC table through the bounded producer; actual upstream, shared governance and downstream wiring is covered separately by V90.
**Acceptance Scenarios**:
1. Given cited candidates and Brief constraints, when screening runs, then grounded cards receive justified fixed-rubric scores and one highest-scoring eligible opportunity is selected.
2. Given a high-scoring candidate requiring an unavailable dependency, when filtering runs, then it cannot displace an eligible candidate.
3. Given an invalid card or score, when Gate checks the output, then hypothesis generation does not start.

### Edge Cases
Near-duplicates versus distinct mechanisms, missing fields, out-of-range scores, ungrounded justifications, unavailable dependencies, ties, no eligible candidate, wrong run identity and rejected Gate are covered. Tie/empty-set policy remains local unresolved; no interactive selection or execution-based feasibility probing is added.

## Requirements
### Functional Requirements
- **FR-001**: Perform single-pass consolidation of near-identical proposals while preserving variants with different mechanisms or baseline papers. Source: Current PRD §3.4.1.
- **FR-002**: Map each consolidated candidate to a technical problem statement and proposed mechanism grounded in the input evidence. Source: Current PRD §3.4.2.
- **FR-003**: Emit schema-valid Idea Cards with idea_id, title, summary, linked_citations, core_assumptions and identified_risks. Source: Current PRD §3.4.3.
- **FR-004**: Record opportunity_statement explaining the literature bottleneck and why the proposed mechanism addresses it. Source: Current PRD §3.4.4.
- **FR-005**: Use one bounded single-turn fixed-rubric assessment with novelty, technical feasibility and compute alignment scores on 1–5 scales, each with an evidence-grounded one-sentence justification. Source: Current PRD §3.4.5.
- **FR-006**: Apply a deterministic dependency-conflict filter, including candidates requiring unreleased proprietary models or closed datasets. Source: Current PRD §3.4.6.
- **FR-007**: Compute Score = Novelty + Feasibility + ComputeAlignment, select the Top-1 eligible card, retain rejection/deferral rationale for all lower-ranked candidates and package Opportunity_Card.json for Gate. Source: Current PRD §3.4.7.
- **FR-008**: Use the single fixed research path and preserve constraint/citation/score evidence; schema/scoring/evidence must pass the shared Gate before hypothesis generation. Source: Current PRD §3.4 introduction; §1.3–§1.4; §2.2, §2.5–§2.8, §2.10; §6.6.

### Key Entities
Candidate set; consolidated candidate; Idea Card; opportunity_statement; novelty/technical-feasibility/compute-alignment scores; dependency exclusion; Opportunity_Card.json.
Canonical semantic boundary: [M1-IF-011@r0](TASK.md#4-embedded-cross-module-agreements). Named PRD payloads and fields are recorded as source obligations, not a finalized technical schema.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | Current PRD §3.4.1 / FR-001 / US1 | Duplicate proposals are consolidated; materially distinct mechanisms/baselines remain separate; no iterative clustering/reindexing is performed. | BLOCK, BOUNDARY |
| AC-002 | Current PRD §3.4.2 / FR-002 / US1 | Every card retains a traceable candidate problem/mechanism; no newly brainstormed candidate is introduced. | BLOCK, BOUNDARY |
| AC-003 | Current PRD §3.4.3 / FR-003 / US1 | Each required PRD-named semantic field is present and valid under the future approved schema; unsupported free-form-only cards are not accepted. | BLOCK, BOUNDARY |
| AC-004 | Current PRD §3.4.4 / FR-004 / US1 | Every card contains a grounded actionable opportunity statement; no commercial business-case, ROI or market-sizing work is added. | BLOCK, BOUNDARY |
| AC-005 | Current PRD §3.4.5 / FR-005 / US1 | All three scores remain within 1–5; feasibility concerns standard Python/PyTorch and compute alignment uses Brief hardware bounds. No reviewer debate, voting or pre-POC live code execution occurs. | BLOCK, BOUNDARY |
| AC-006 | Current PRD §3.4.6 / FR-006 / US1 | Candidates that violate the adopted dependency constraints cannot be selected; no patent search or formal legal audit is invoked. | BLOCK, BOUNDARY |
| AC-007 | Current PRD §3.4.7 / FR-007 / US1 | Arithmetic totals equal the three scores; exactly one eligible highest-scoring opportunity proceeds when a unique winner exists; losers retain rationales, with no human selection wait. | BLOCK, BOUNDARY |
| AC-008 | Current PRD §3.4 introduction; §1.3–§1.4; §2.2, §2.5–§2.8, §2.10; §6.6 / FR-008 / US1 | Screening performs convergent selection rather than new ideation or literature re-verification; a malformed/unjustified/stale decision cannot release the next node. | BLOCK, BOUNDARY |

All allocated behavior and exclusions are covered above. Product examples remain examples; source-backed literal limits such as the three 1–5 scores and Top-1 remain requirements. No new performance, reliability or model-quality threshold is invented.

## Scope and Assumptions
- Offline RSI allocation (§4.4.3): M1-018 owns a sandbox copy of the pure `rank_opportunities` helper associated with this screening capability. Its candidate mutation does not modify this live fixed baseline, Top-1 responsibility, Opportunity_Card interface or scoring-dimension set. Admission and explicit human activation are owned by M1-003/M1-018; actual code locations remain Architecture-owned.
- Included scope: Consolidate cited candidates, form structured Idea Cards, score novelty/feasibility/compute alignment with a fixed single-pass rubric, filter disallowed dependencies and deterministically select one opportunity.
- Excluded scope: New brainstorming, iterative clustering, cross-database indexing, unstructured cards, business/ROI analysis, reviewer debate/voting, feasibility code execution, patent/legal auditing and interactive human selection are excluded. Global non-goals in §2.12 still apply. Dynamic Phase 3 behavior is isolated under [M1-019](../M1-019/TASK.md), not a prerequisite for this Phase 1 task.
- Consumed TASK agreements: [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-010@r0](../M1-010/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Single configured Codex CLI route via M1-004; fixed bounded screening assessment, with separate independent Gate verification. Model/rubric versions must be recorded at execution; no reviewer swarm or model pool is introduced.
- Source/architecture boundary: §1.6 and §6.13 reserve exact schemas, APIs, process topology, storage layout and detailed mechanisms to Architecture. All such bindings remain PENDING_DESIGN; the architecture source is [the current design](../../../../architecture/build-package/README.md).
- Assumptions and unresolved source inputs: Q-011-01: Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent: formalize schemas, runtime boundaries, score validation and code/test paths; source-provided field names and 1–5 scales remain normative semantic requirements. Q-011-02: PRD names the ported assessment-screening rubric but does not supply its complete versioned text; bind actual permitted rubric/adaptations before semantic reproducibility claims. Q-011-03: Resolve deterministic tie behavior and empty eligible-candidate behavior before those boundary checks. Do not fabricate a winner or add an interactive human-selection step.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete journeys and integrated candidate acceptance. This spec owns only M1-011's ACs; it does not duplicate system ACs or shared Gate policy.
- Runtime failure handling and explicit human restart use canonical M1-006/007 behavior; no independent retry mechanism is assumed.

This spec is the AC authority. Provisional design/check procedures are in plan.md; work and evidence are in tasks.md.
