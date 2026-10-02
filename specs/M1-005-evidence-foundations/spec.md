# Feature Specification: M1-005 - Evidence foundations and run exports
**TASK**: [M1-005](../../docs/tasks/M1/M1-005/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)
**Input**: [PRD r2](../../docs/tasks/M1/sources/PRD-Full.r2.txt), §4.5, §4.5.1, §4.5.2, §4.5.3, §4.5.4; §4.5.5 explicitly excluded; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.   Also §4.3.3 (lines 1502-1521), §5.3.1 (lines 2089-2098) and §5.6.5 (lines 2228-2248) govern joinable observations and actual effective-state/seed evidence.
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Evidence foundations and run exports observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.
4. Given requested and effective settings that differ, when a run completes or halts, then AC-007 records actual components and requested/effective seed; AC-003 supports joined model-call observations without fabricated usage.

### Edge Cases
- AC-001: Working context and large log fixture; inspect memory and persisted destinations.
- AC-002: Two-node run, failure, delayed/failed persistence and end-of-run snapshot; independent event ordering.
- AC-003: Sequential success/failure records with missing usage metadata and before/after record comparison.
- AC-004: Known allowed/undeclared tool traces, unused declaration and independently counted pass/fail records.
- AC-005: Two preserved actual-run bundles, export hash/label check and post-export original change.
- AC-006: Implementation/dependency/configuration inspection and actual evidence/export destination observation.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.5.1; §2.10): Native Task Memory/Coding Memory retain working context; raw telemetry, benchmark stdout/stderr and large execution logs remain system evidence rather than agent context.
- **FR-002** (§4.5.2; §1.4; §4.2.8): Capture prompts, input/output, full traces and raw Gate/verifier evidence in attributable local bundles, with workspace snapshot at execution end and append-only records for each capsule. Persist advancing gate decision before release.
- **FR-003** (§4.5.2 (lines 1748-1757); §4.3.3 (lines 1502-1521)): Append-only records retain joinable local model-call/pipeline Observation references, run/stage/role/capsule/version, endpoint/route, timestamp, latency, outcome/fallback and reliable available usage/cost. Earlier entries remain intact. Missing unreliable usage is neither fabricated zero-cost evidence nor an execution failure; audited/provider boundary behavior is owned by M1-004.
- **FR-004** (§4.5.3): Compare declared ports/needs/effects against actual trace; flag undeclared tool use and unused declarations. Generate static Markdown/JSON scorecards with pass rates, available token use and failure reasons per version.
- **FR-005** (§4.5.4): Export frozen copies of real bundles/records with fixed labels/content hashes into a dedicated local directory for separate offline RSI consumption; no synthetic run manufacture or live workflow writeback.
- **FR-006** (§4.5.1 blacklist; §4.5.2 blacklist; §4.5.3 blacklist; §4.5.4 blacklist; §4.5.5 excluded): Data foundation remains within the local storage/context/export scope, without excluded dashboards, host monitors, enterprise graph/database structures, synthetic runs, redaction/deduplication or offline-to-live writeback.

- **FR-007** (§4.5.2 (lines 1748-1757); §5.3.1 (lines 2089-2098); §5.6.5 (lines 2228-2248)): Every Run Bundle preserves the configuration that actually executed: capsule-library snapshot/hash, stage capsule versions, routing configuration, evaluation profile, RSI participation where applicable, requested/effective seed where supported and other benchmark-relevant identifiers. Distinguish requested/effective state; do not claim deterministic model output without endpoint seed support.

### Key Entities
The input/output/state meanings are defined canonically in [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements). This spec does not invent a competing schema. PRD artifact/model names are retained; missing field-level design is reserved for architecture.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.5.1; §2.10 / FR-001 / US1 | Native Task Memory/Coding Memory retain working context; raw telemetry, benchmark stdout/stderr and large execution logs remain system evidence rather than agent context. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §4.5.2; §1.4; §4.2.8 / FR-002 / US1 | Capture prompts, input/output, full traces and raw Gate/verifier evidence in attributable local bundles, with workspace snapshot at execution end and append-only records for each capsule. Persist advancing gate decision before release. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | PRD r2 §4.5.2 (lines 1748-1757); §4.3.3 (lines 1502-1521) / FR-003 / US1 | Append-only records retain joinable local model-call/pipeline Observation references, run/stage/role/capsule/version, endpoint/route, timestamp, latency, outcome/fallback and reliable available usage/cost. Earlier entries remain intact. Missing unreliable usage is neither fabricated zero-cost evidence nor an execution failure; audited/provider boundary behavior is owned by M1-004. | BLOCK, BOUNDARY |
| AC-004 | §4.5.3 / FR-004 / US1 | Compare declared ports/needs/effects against actual trace; flag undeclared tool use and unused declarations. Generate static Markdown/JSON scorecards with pass rates, available token use and failure reasons per version. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-005 | §4.5.4 / FR-005 / US1 | Export frozen copies of real bundles/records with fixed labels/content hashes into a dedicated local directory for separate offline RSI consumption; no synthetic run manufacture or live workflow writeback. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-006 | §4.5.1 blacklist; §4.5.2 blacklist; §4.5.3 blacklist; §4.5.4 blacklist; §4.5.5 excluded / FR-006 / US1 | Data foundation remains within the local storage/context/export scope, without excluded dashboards, host monitors, enterprise graph/database structures, synthetic runs, redaction/deduplication or offline-to-live writeback. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-007 | PRD r2 §4.5.2 (lines 1748-1757); §5.3.1 (lines 2089-2098); §5.6.5 (lines 2228-2248) / FR-007 / US1 | Every Run Bundle preserves the configuration that actually executed: capsule-library snapshot/hash, stage capsule versions, routing configuration, evaluation profile, RSI participation where applicable, requested/effective seed where supported and other benchmark-relevant identifiers. Distinguish requested/effective state; do not claim deterministic model output without endpoint seed support. | BLOCK, BOUNDARY |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions

- Architecture reservation: [minimum inputs](../../docs/tasks/M1/ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7. Actual code/module/process boundaries, typed payloads/APIs/errors, coordination, storage/durability, security/settings mechanisms and executable test entry points remain PENDING_DESIGN; this spec states product outcomes only.
- Included: Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI.
- Excluded: No raw benchmark/telemetry logs in agent memory, external/vector/distributed stores, multi-user separation, trace redaction/deduplication, live telemetry dashboards or host CPU/GPU monitoring; no synthetic run generation or live writeback from offline experiments. All §4.5.5 extended graph management is deferred.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../../docs/tasks/M1/M1-018/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture binds concrete file schemas/layout, durability/snapshot boundaries, run identity and partial-write recovery. Scorecards must handle unavailable usage truthfully. Export labels come from actual registered runs, not invented outcomes. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
