# Feature Specification: M1-004 - Static model routing and reviewer provisioning
**TASK**: [M1-004](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)
**Input**: [PRD r2](../sources/PRD-Full.r2.txt), §4.3, §4.3.1 Phase 1, §4.3.2 Phase 1, §4.3.3, §4.3.4; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Static model routing and reviewer provisioning observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.
4. Given local correlation, when the audited boundary constructs a provider request, then AC-002 retains joinable evidence and AC-005 excludes attribution-only labels; a bypass cannot silently produce an un-attributable supported call.

### Edge Cases
- AC-001: Two different designated capsule/role inputs and registry/wiring inspection.
- AC-002: Success/failure calls with unavailable and reliable usage metadata.
- AC-003: Real producer/reviewer context separation, artifact before/after identity and Gate result consumption.
- AC-004: Registry/configuration inspection and disallowed dynamic route/reviewer modification attempts.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.3.1 Phase 1; §4.3.2 Phase 1): Only Codex CLI is active; every route uses the DAG-supplied capsule/role and configured static endpoint. Router never selects the capsule.
- **FR-002** (§4.3.3 (lines 1502-1521)): Every invocation is locally attributable to its run, Observation, stage/step, role and capsule/version through a stable local correlation identifier. Retain endpoint, route decision, timestamp, latency, outcome, fallback state and other available benchmark-relevant telemetry. Reliable tokens/estimated cost are best effort; absent usage must not fail execution.
- **FR-003** (§4.3.4; §4.2.1): Reviewer uses static Codex CLI and verifier_capsule.md with independent read-only context; structured result returns to Gate without changing implementation/artifacts.
- **FR-004** (§4.3.1 Phase 2/blacklist (lines 1475-1487); §4.3.2 Phase 2/blacklist (lines 1488-1501); §4.3.4 Phase 2/blacklist (lines 1522-1539)): Production remains static Codex and excludes source-listed routing/accounting/reviewer features. Isolated registry/routing/alternate-Verifier work belongs to M1-019: mocks/analysis before approved access and explicitly approved real-model integration afterward. No experiment silently replaces production.

- **FR-005** (§4.3.3 (lines 1502-1521)): All supported M1 model calls pass through the approved audited routing/bridge boundary; components cannot silently produce un-attributable calls. Local stage, role, capsule and other labels used solely for benchmarking/attribution are correlated locally, not inserted into prompts or forwarded to providers solely for benchmarking.

### Key Entities
The input/output/state meanings are defined canonically in [M1-IF-004@r0](TASK.md#4-embedded-cross-module-agreements). This spec does not invent a competing schema. PRD artifact/model names are retained; missing field-level design is reserved for architecture.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.3.1 Phase 1; §4.3.2 Phase 1 / FR-001 / US1 | Only Codex CLI is active; every route uses the DAG-supplied capsule/role and configured static endpoint. Router never selects the capsule. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | PRD r2 §4.3.3 (lines 1502-1521) / FR-002 / US1 | Every invocation is locally attributable to its run, Observation, stage/step, role and capsule/version through a stable local correlation identifier. Retain endpoint, route decision, timestamp, latency, outcome, fallback state and other available benchmark-relevant telemetry. Reliable tokens/estimated cost are best effort; absent usage must not fail execution. | BLOCK, BOUNDARY |
| AC-003 | §4.3.4; §4.2.1 / FR-003 / US1 | Reviewer uses static Codex CLI and verifier_capsule.md with independent read-only context; structured result returns to Gate without changing implementation/artifacts. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | PRD r2 §4.3.1 Phase 2/blacklist (lines 1475-1487); §4.3.2 Phase 2/blacklist (lines 1488-1501); §4.3.4 Phase 2/blacklist (lines 1522-1539) / FR-004 / US1 | Production remains static Codex and excludes source-listed routing/accounting/reviewer features. Isolated registry/routing/alternate-Verifier work belongs to M1-019: mocks/analysis before approved access and explicitly approved real-model integration afterward. No experiment silently replaces production. | BLOCK, BOUNDARY |
| AC-005 | PRD r2 §4.3.3 (lines 1502-1521) / FR-005 / US1 | All supported M1 model calls pass through the approved audited routing/bridge boundary; components cannot silently produce un-attributable calls. Local stage, role, capsule and other labels used solely for benchmarking/attribution are correlated locally, not inserted into prompts or forwarded to providers solely for benchmarking. | BLOCK, BOUNDARY |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions

- Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7. Actual code/module/process boundaries, typed payloads/APIs/errors, coordination, storage/durability, security/settings mechanisms and executable test entry points remain PENDING_DESIGN; this spec states product outcomes only.
- Included: Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review.
- Excluded: No heterogeneous/dynamic production selection, local weights, fine-tuned/poorly documented model-pool expansion, learned/vector/bandit routers, ensembles, mid-call switching, complex optimization, billing/quota infrastructure, reviewer edits or iterative coder-reviewer loops. Access-gated isolated Phase 2 registry/routing and alternate-Verifier experiments belong to M1-019.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-001@r0](../M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture binds registry/provider/review types and reliable-usage detection. Run/Observation/stage/role/capsule attribution is local; attribution-only labels must not reach providers. Correlation and clean-request construction remain PENDING_DESIGN. No missing model ID is invented. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
