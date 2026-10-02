# Feature Specification: M1-004 - Static model routing and reviewer provisioning
**TASK**: [M1-004](../../docs/tasks/M1/M1-004/TASK.md)  
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)  
**Revision / date**: r1 / 2026-10-01  
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)  
**Input**: [PRD r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §4.3, §4.3.1 Phase 1, §4.3.2 Phase 1, §4.3.3, §4.3.4; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.  
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Static model routing and reviewer provisioning observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.

### Edge Cases
- AC-001: Two different designated capsule/role inputs and registry/wiring inspection.
- AC-002: Success/failure calls with unavailable and reliable usage metadata.
- AC-003: Real producer/reviewer context separation, artifact before/after identity and Gate result consumption.
- AC-004: Registry/configuration inspection and disallowed dynamic route/reviewer modification attempts.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.3.1 Phase 1; §4.3.2 Phase 1): Only Codex CLI is active; every route uses the DAG-supplied capsule/role and configured static endpoint. Router never selects the capsule.
- **FR-002** (§4.3.3): Every call records endpoint, capsule, task, role, timestamp, latency, call count, success/failure and fallback occurrence; absent unreliable token/cost data is permitted and not an execution failure.
- **FR-003** (§4.3.4; §4.2.1): Reviewer uses static Codex CLI and verifier_capsule.md with independent read-only context; structured result returns to Gate without changing implementation/artifacts.
- **FR-004** (§4.3.1 blacklist/Phase 2; §4.3.2 blacklist/Phase 2; §4.3.3 blacklist; §4.3.4 blacklist): Production bindings remain static and exclude listed registry/routing/accounting/reviewer features; mocked experiments remain isolated under M1-019.

### Key Entities
The input/output/state meanings are defined canonically in [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements). This spec does not invent a competing schema. PRD artifact/model names are retained; missing field-level design is reserved for architecture.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.3.1 Phase 1; §4.3.2 Phase 1 / FR-001 / US1 | Only Codex CLI is active; every route uses the DAG-supplied capsule/role and configured static endpoint. Router never selects the capsule. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §4.3.3 / FR-002 / US1 | Every call records endpoint, capsule, task, role, timestamp, latency, call count, success/failure and fallback occurrence; absent unreliable token/cost data is permitted and not an execution failure. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | §4.3.4; §4.2.1 / FR-003 / US1 | Reviewer uses static Codex CLI and verifier_capsule.md with independent read-only context; structured result returns to Gate without changing implementation/artifacts. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | §4.3.1 blacklist/Phase 2; §4.3.2 blacklist/Phase 2; §4.3.3 blacklist; §4.3.4 blacklist / FR-004 / US1 | Production bindings remain static and exclude listed registry/routing/accounting/reviewer features; mocked experiments remain isolated under M1-019. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions
- Included: Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review.
- Excluded: No heterogeneous/dynamic production selection, local weights, fine-tuned/poorly documented model-pool expansion, learned/vector/bandit routers, ensembles, mid-call switching, complex optimization, billing/quota infrastructure, reviewer edits or iterative coder-reviewer loops. Mocked isolated Phase 2 registry/routing is M1-019.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-001@r0](../../docs/tasks/M1/M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture binds registry/provider/review types and reliable-usage detection. Actual task-role metadata is required by this PRD even if older placeholder documentation omitted it. No missing model ID is invented. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
