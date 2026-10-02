# Feature Specification: M1-003 - Capability capsules and admission
**TASK**: [M1-003](../../docs/tasks/M1/M1-003/TASK.md)  
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)  
**Revision / date**: r1 / 2026-10-01  
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)  
**Input**: [PRD r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §4.1, §4.1.1, §4.1.2, §4.1.3 Phase 1, §4.1.4, §4.1.5; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.  
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Capability capsules and admission observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Define, admit, retain and execute fixed-schema capabilities with explicit permissions, version pins, static selection, time limits and manually activated implementation lineage.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.

### Edge Cases
- AC-001: Valid code/skill/prompt definitions, invalid contract, changed hash and generated readable view.
- AC-002: Passing/failing self-tests, rejected candidate and historical version lookup.
- AC-003: Two admitted versions before/after manual activation, V1 pin and manual standing transitions.
- AC-004: Valid named binding and one fixture for each eligibility failure; incompatible adjacent ports.
- AC-005: Successful bounded call, timeout, prohibited source and real protected execution boundary.
- AC-006: Allowed prompt mutation, forbidden schema/verifier mutation, hidden-evaluation reference and admitted-but-inactive candidate.
- AC-007: Registry/contract/runner inspection and prohibited operation attempts.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.1.1): Machine-checked capsule.json types I/O, tools and mutable implementation fields and generates consistent make_capsule.md; support code tools, Markdown skills and shared prompts; changed-after-testing code refuses to load.
- **FR-002** (§4.1.2): Hand-written and RSI candidate versions undergo contract/rule checks, self-tests and a written admission decision; only provisional trust in M1. History is append-only and older admitted versions are never automatically deleted.
- **FR-003** (§4.1 introduction; §4.1.2): New runs bind the latest active manually activated version; explicit historical pin is supported and exact version/hash recorded. Suspend/deprecate/rollback/default changes use manual management.
- **FR-004** (§4.1.3 Phase 1): Pre-run eligibility rejects unadmitted/noncurrent/changed/type-incompatible named capsules; the fixed DAG names the capsule without registry search or ranking.
- **FR-005** (§4.1.4): One CC runner records every output and call observation, enforces configured time budgets and sends evidence to the Gate; generated-code execution uses required unprivileged boundary plus prompt restrictions and Tier-1 AST checks.
- **FR-006** (§4.1.5; §4.1.2 Hidden RSI Fixtures): Only contract-permitted implementation fields may evolve; required I/O/schema unchanged and verifier immutable. RSI candidates need standard admission, hidden-fixture evaluation supplied by M1-018 and manual activation; builder cannot see hidden fixtures.
- **FR-007** (§4.1.1 blacklist; §4.1.2 blacklist; §4.1.3 Phase 2/blacklist; §4.1.4 blacklist; §4.1.5 blacklist): Phase 1 excludes the registry/discovery/model-selection/installation/budget/evolution features listed in scope; isolated catalogue/jiuwenbox work cannot change the release path.

### Key Entities
The input/output/state meanings are defined canonically in [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements). This spec does not invent a competing schema. PRD artifact/model names are retained; missing field-level design is reserved for architecture.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.1.1 / FR-001 / US1 | Machine-checked capsule.json types I/O, tools and mutable implementation fields and generates consistent make_capsule.md; support code tools, Markdown skills and shared prompts; changed-after-testing code refuses to load. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §4.1.2 / FR-002 / US1 | Hand-written and RSI candidate versions undergo contract/rule checks, self-tests and a written admission decision; only provisional trust in M1. History is append-only and older admitted versions are never automatically deleted. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | §4.1 introduction; §4.1.2 / FR-003 / US1 | New runs bind the latest active manually activated version; explicit historical pin is supported and exact version/hash recorded. Suspend/deprecate/rollback/default changes use manual management. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | §4.1.3 Phase 1 / FR-004 / US1 | Pre-run eligibility rejects unadmitted/noncurrent/changed/type-incompatible named capsules; the fixed DAG names the capsule without registry search or ranking. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-005 | §4.1.4 / FR-005 / US1 | One CC runner records every output and call observation, enforces configured time budgets and sends evidence to the Gate; generated-code execution uses required unprivileged boundary plus prompt restrictions and Tier-1 AST checks. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-006 | §4.1.5; §4.1.2 Hidden RSI Fixtures / FR-006 / US1 | Only contract-permitted implementation fields may evolve; required I/O/schema unchanged and verifier immutable. RSI candidates need standard admission, hidden-fixture evaluation supplied by M1-018 and manual activation; builder cannot see hidden fixtures. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-007 | §4.1.1 blacklist; §4.1.2 blacklist; §4.1.3 Phase 2/blacklist; §4.1.4 blacklist; §4.1.5 blacklist / FR-007 / US1 | Phase 1 excludes the registry/discovery/model-selection/installation/budget/evolution features listed in scope; isolated catalogue/jiuwenbox work cannot change the release path. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions
- Included: Define, admit, retain and execute fixed-schema capabilities with explicit permissions, version pins, static selection, time limits and manually activated implementation lineage.
- Excluded: No autonomous capsule generation, remote A2A/MCP imports, per-capsule package installation or model selection by capsules; no deletion, automatic librarian, external publishing or third-party certified trust; no dynamic production discovery/ranking, token/money enforcement, mid-run installation, repair/promotion, horizontal evolution, live RSI or verifier evolution. Phase 2 read-only catalogue/jiuwenbox work belongs to M1-019; offline optimization loop belongs to M1-018.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../../docs/tasks/M1/M1-018/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture binds contract loader/schema, history/default storage, runner and Gate bootstrap. Latest optimized must preserve manual activation. Hidden-fixture evaluation is M1-018 and isolation policy M1-002; this task owns admission/manual activation semantics only. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
