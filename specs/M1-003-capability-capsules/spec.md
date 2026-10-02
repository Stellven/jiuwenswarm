# Feature Specification: M1-003 - Capability capsules and admission
**TASK**: [M1-003](../../docs/tasks/M1/M1-003/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)
**Input**: [PRD r2](../../docs/tasks/M1/sources/PRD-Full.r2.txt), §4.1, §4.1.1, §4.1.2, §4.1.3 Phase 1, §4.1.4, §4.1.5; shared §4.4.5, §4.4.8–§4.4.10; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.
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
- AC-003: Two admitted versions before/after human activation, a better-scoring but inactive RSI child, an explicit older-version pin and manual standing/rollback transitions.
- AC-004: Named default binding and an admissible explicit historical pin; each admission/standing/hash/type-compatibility failure.
- AC-005: Successful bounded call, timeout, prohibited source and real protected execution boundary.
- AC-006: Explicitly authorized implementation mutation; forbidden schema/effect/referee mutation; independently established protected fixtures; a run-derived fixture lacking separation/custody/freezing; an admitted-but-inactive child.
- AC-007: Registry/contract/runner inspection and prohibited operation attempts.
- AC-008: Attempted permission expansion, hidden-fixture access, security/referee/check/promotion tampering and unauthorized activation; retain required violation evidence and limitations without inventing isolation mechanisms.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.1.1): Machine-checked capsule.json types I/O, tools and mutable implementation fields and generates consistent make_capsule.md; support code tools, Markdown skills and shared prompts; changed-after-testing code refuses to load.
- **FR-002** (§4.1.2): Hand-written and RSI candidate versions undergo contract/rule checks, self-tests and a written admission decision; only provisional trust in M1. History is append-only and older admitted versions are never automatically deleted.
- **FR-003** (§4.1.2 Default Active / Pinned Execution; §4.1 introduction): New runs default to the latest human-activated admitted version. A better-scoring or newly admitted RSI candidate remains inactive until explicit human activation. An operator may explicitly pin an older admitted version; record the exact version/hash used at every node. Suspend/deprecate/rollback/default changes remain manual.
- **FR-004** (§4.1.2; §4.1.3 Phase 1): The fixed DAG names the capsule without registry search/ranking. Pre-run eligibility validates the resolved human-active default or explicitly pinned admitted version, applicable standing, unchanged code and neighbor type compatibility. Historical age alone must not invalidate a source-authorized explicit pin.
- **FR-005** (§4.1.4): One CC runner records every output and call observation, enforces configured time budgets and sends evidence to the Gate; generated-code execution uses required unprivileged boundary plus prompt restrictions and Tier-1 AST checks.
- **FR-006** (§4.1.5; §4.1.2 Hidden RSI Evaluation Fixtures; §4.4.5, §4.4.8, §4.4.9): RSI requires explicit target eligibility and may mutate only authorized implementation fields. Required I/O, interface/effect class and downstream compatibility stay invariant. Candidate evaluation first preserves mandatory parent behavior/tests. Hidden evaluation fixtures are established independently of the candidate, frozen before the session and inaccessible to proposer/candidate; governed run-derived cases require separation, custody and freezing. The child passes standard admission and remains inactive until human activation.
- **FR-007** (§4.1.1 blacklist; §4.1.2 blacklist; §4.1.3 Phase 2/blacklist; §4.1.4 blacklist; §4.1.5 blacklist): Phase 1 excludes the registry/discovery/model-selection/installation/budget/evolution features listed in scope; isolated catalogue/jiuwenbox work cannot change the release path.
- **FR-008** (§4.1.5; §2.11; §4.4.5, §4.4.9, §4.4.10): Enforce the system-level always-frozen security/referee set independently of capsule-local mutation permission. Permission controls, Evaluator/Verifier/check logic, hidden-evaluation controls, security/resource boundaries, interface/effect permissions and promotion controls cannot evolve through RSI. A child cannot grant itself broader mutation, tool, network, resource, evaluation or promotion authority. Consume M1-018's required adversarial validation/evidence and human rollback semantics; no concrete confinement mechanism is chosen here.

### Key Entities
The PRD names capsule contracts, readable views, admitted versions, exact version/hash evidence and human activation. Their observable obligations are specified above. [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements) reserves the future technical agreement; schemas, registry representation, loaders and process/security mechanisms remain PENDING_DESIGN.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.1.1 / FR-001 / US1 | Machine-checked capsule.json types I/O, tools and mutable implementation fields and generates consistent make_capsule.md; support code tools, Markdown skills and shared prompts; changed-after-testing code refuses to load. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §4.1.2 / FR-002 / US1 | Hand-written and RSI candidate versions undergo contract/rule checks, self-tests and a written admission decision; only provisional trust in M1. History is append-only and older admitted versions are never automatically deleted. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | §4.1.2 Default Active / Pinned Execution; §4.1 introduction / FR-003 / US1 | A new run uses the latest human-activated admitted version unless an operator explicitly pins an older admitted version. A better-scoring or newly admitted RSI child does not replace the active default. Every node records its exact used version/hash; activation, suspension, deprecation and rollback require manual action. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | §4.1.2; §4.1.3 Phase 1 / FR-004 / US1 | The fixed DAG names the capsule without search/ranking. Validate the resolved human-active default or explicitly pinned version against admission, applicable standing, unchanged hash and neighbor compatibility. Reject invalid bindings; accept a source-authorized historical pin when those checks pass. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-005 | §4.1.4 / FR-005 / US1 | One CC runner records every output and call observation, enforces configured time budgets and sends evidence to the Gate; generated-code execution uses required unprivileged boundary plus prompt restrictions and Tier-1 AST checks. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-006 | §4.1.5; §4.1.2 Hidden RSI Evaluation Fixtures; §4.4.5, §4.4.8, §4.4.9 / FR-006 / US1 | Only an explicitly eligible target's authorized implementation fields may change; required I/O, interface/effect class and compatibility remain fixed, with mandatory parent behavior/tests preserved before improvement evaluation. Protected fixtures are independently established/frozen and inaccessible to proposer/candidate. Run-derived cases require governed separation/custody/freezing. Required evaluation and admission do not activate the child without human action. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-007 | §4.1.1 blacklist; §4.1.2 blacklist; §4.1.3 Phase 2/blacklist; §4.1.4 blacklist; §4.1.5 blacklist / FR-007 / US1 | Phase 1 excludes the registry/discovery/model-selection/installation/budget/evolution features listed in scope; isolated catalogue/jiuwenbox work cannot change the release path. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-008 | §4.1.5; §2.11; §4.4.5, §4.4.9, §4.4.10 / FR-008 / US1; RSI suite owned by M1-018 | Capsule-local mutation permission cannot authorize changes to the always-frozen system security/referee set or expand a child's authority. Prohibited permission/security/referee/hidden-evaluation/promotion changes are blocked and produce attributable evidence under M1-018's required violation suite. The child remains inactive until human admission/activation, and an activated version supports explicit human rollback. Actual isolation/enforcement design remains architecture-owned. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions
- Included: Define, admit, retain and execute fixed-schema capabilities with explicit permissions, version pins, static selection, time limits and manually activated implementation lineage.
- Excluded: No autonomous capsule generation, remote A2A/MCP imports, per-capsule package installation or model selection by capsules; no deletion, automatic librarian, external publishing or third-party certified trust; no dynamic production discovery/ranking, token/money enforcement, mid-run installation, repair/promotion, horizontal evolution, live RSI or verifier evolution. Phase 2 read-only catalogue/jiuwenbox work belongs to M1-019; offline optimization loop belongs to M1-018.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../../docs/tasks/M1/M1-018/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture binds contract loader/schema, history/default storage, runner/Gate startup, independent fixture custody and always-frozen enforcement. The source's latest-optimized description is constrained by its explicit latest-human-activated/pinned rule. M1-018 owns offline evaluation/violation-suite behavior; M1-002 owns source-required local security outcomes. No OS accounts, physical custody layout or security mechanism is supplied here. Architecture PENDING_SOURCE constrains technical realization only.
- System task: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
