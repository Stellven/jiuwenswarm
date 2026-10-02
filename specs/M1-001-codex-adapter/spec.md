# Feature Specification: M1-001 - Codex CLI adapter
**TASK**: [M1-001](../../docs/tasks/M1/M1-001/TASK.md)  
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)  
**Revision / date**: r1 / 2026-10-01  
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)  
**Input**: [PRD r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §3.0, §3.0.1, §3.0.2; sequencing §6.3; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.  
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Codex CLI adapter observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.

### Edge Cases
- AC-001: Existing code/caller inventory and one real bounded native request/response.
- AC-002: Authorized caller, missing/wrong credential, inappropriate local context and listener/permission inspection.
- AC-003: Provider consumer request, controlled timeout and missing/expired authentication.
- AC-004: Implementation/configuration inspection and out-of-scope streaming/dynamic-route requests.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§3.0.1; §6.3): Inspect and reuse the existing adapter; a real bounded single-turn JiuwenSwarm request reaches active Codex CLI and returns a parsed native-format completion without requiring enterprise API keys.
- **FR-002** (§3.0.1; §2.9): The adapter exposes only the required secured local IPC with restrictive permissions and ephemeral execution-bound session credentials; no adapter TCP listener; unauthorized local context cannot invoke it.
- **FR-003** (§3.0.2): Provider abstraction is callable by native routing consumers; controlled timeout and authentication loss are attributable run-tree events rather than silent success.
- **FR-004** (§3.0.1 blacklist; §3.0.2 blacklist): Implementation reuses the existing adapter instead of building a replacement proxy; Phase 1 remains synchronous single-turn and does not integrate dynamic model routing or autonomous recovery.

### Key Entities
The input/output/state meanings are defined canonically in [M1-IF-001@r0](../../docs/tasks/M1/M1-001/TASK.md#4-embedded-cross-module-agreements). This spec does not invent a competing schema. PRD artifact/model names are retained; missing field-level design is reserved for architecture.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §3.0.1; §6.3 / FR-001 / US1 | Inspect and reuse the existing adapter; a real bounded single-turn JiuwenSwarm request reaches active Codex CLI and returns a parsed native-format completion without requiring enterprise API keys. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §3.0.1; §2.9 / FR-002 / US1 | The adapter exposes only the required secured local IPC with restrictive permissions and ephemeral execution-bound session credentials; no adapter TCP listener; unauthorized local context cannot invoke it. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | §3.0.2 / FR-003 / US1 | Provider abstraction is callable by native routing consumers; controlled timeout and authentication loss are attributable run-tree events rather than silent success. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | §3.0.1 blacklist; §3.0.2 blacklist / FR-004 / US1 | Implementation reuses the existing adapter instead of building a replacement proxy; Phase 1 remains synchronous single-turn and does not integrate dynamic model routing or autonomous recovery. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions
- Included: Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint.
- Excluded: No custom proxy from scratch, complex multi-turn conversational streaming, enterprise API-key prerequisite or dynamic-router integration on the Phase 1 path. Future endpoint-of-last-resort registration is an abstraction goal, not live heterogeneous routing.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Locate existing adapter/callers/tests before deciding changes; architecture must bind native payload conversion, local transport implementation, credential lifecycle, timeout/cancellation and telemetry hooks. Actual account availability is untested. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
