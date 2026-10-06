# Feature Specification: M1-007 - Evaluator Gate and independent Verifier
**TASK**: [M1-007](TASK.md)
**Parent TASKS**: [M1](../TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: ai4r_xiaoyang (existing checkout; no task branch created)
**Input**: [PRD r2](../sources/PRD-Full.r2.txt), §4.2, §4.2.1–§4.2.9; §4.2.10 explicitly excluded; consumed §4.3.3–§4.3.4; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12. Architecture PENDING_SOURCE.
**Status**: Preparing; product requirements populated, architecture-dependent design pending; not a runtime result.

## User Scenarios & Testing
### User Story 1 - Evaluator Gate and independent Verifier observable contract (Priority: P1)
A local scientific-workflow executor or connected component obtains attributable outputs/failure decisions from the supplied inputs, without expanding the fixed Phase 1 scope. Check node evidence with deterministic Tier 1 then independent read-only Tier 2, persist structured infrastructure verdicts and control advancement while preserving scientific conclusions.

**Independent Test**: Exercise the source-derived cases below against the specified behavior blocks, then connect the real peers. Expected outcomes are the ACs, not agent self-reported success. Stubs cannot establish actual provider availability, security isolation or whole-system readiness.

**Acceptance Scenarios**:
1. Given admissible inputs and required services, when the bounded behavior executes, then its output and evidence satisfy all normal-case ACs below.
2. Given each applicable invalid, stale, unavailable or over-budget fixture, when the behavior executes, then the stated failure/limitation occurs and forbidden downstream effects do not occur.
3. Given an excluded or isolated Phase 2 behavior, when inspecting Phase 1 bindings, then it does not silently expand production behavior.

### Edge Cases
- AC-001: Complete/missing evidence, reviewer call counter on failed Tier 1 and policy-mutation attempt.
- AC-002: Valid artifact and each type/field/artifact/proof/binding/trace mutation.
- AC-003: Supplied passing/failing tests, invalid Python, missing entry, prohibited import and scope-violating patch.
- AC-004: Within/over time, absent baseline/treatment/metric, changed protocol and missing usage data.
- AC-005: Benign code; each forbidden import; tool/scope violation; fake credential; missing runtime dependency.
- AC-006: Supported/unsupported citations, fabricated identifier, contradiction, omitted limitation and corrupt measurement under fixed rubric.
- AC-007: Claimed test without execution trace, out-of-order node, effect mismatch and human environment correction without restart.
- AC-008: All five verdicts, normalized mappings, delayed persistence and valid negative evaluation artifact.
- AC-009: Schema-valid artifact with complete observed runtime evidence.
- AC-010: Missing-field and invalid-type variants.
- AC-011: One swapped binding per otherwise valid artifact.
- AC-012: Citation absent from supplied evidence and fixed labelled rubric.
- AC-013: Capsule forced beyond its configured time allowance.
- AC-014: Forbidden import and independently observed undeclared-tool variants.
- AC-015: Controlled unavailable dependency or runtime.
- AC-016: Fixed acceptance profile identifying a genuinely non-blocking limitation.
- AC-017: Valid negative scientific artifact with complete process/benchmark evidence.
- AC-018: Instrumented A/Gate/B with controlled evaluation and persistence delays.
- AC-019: Policy/dependency/configuration inspection and disallowed mutation/repair attempts.
- AC-020: Tier-2 Verifier invocation with locally correlated evidence, a clean provider request and a planted unsupported bypass; stage/role/capsule audit labels remain local unless substantively required by the review task.

Cancellation, interrupted persistence and compatibility details not fixed by PRD remain design inputs; they must preserve fail-fast evidence and cannot introduce autonomous recovery. N/A: distributed/cloud/multi-tenant recovery is outside the local single-user scope. Existing implementation has not been assessed; neither absence nor correctness is claimed.

## Requirements
### Functional Requirements
- **FR-001** (§4.2.1): Applicable evidence obligations are present; mandatory deterministic failure halts before any semantic model call; passing Tier 1 enables independent read-only reviewer context. Policies/prompts/thresholds/aggregation remain frozen and outside RSI.
- **FR-002** (§4.2.2): Validate fields/types/bounds, declared artifact kinds/filenames and proof obligations; reject mismatched run/node/version/interface hash, undeclared tools/outputs and structurally incomplete evidence despite plausible prose.
- **FR-003** (§4.2.3): Run supplied mandatory tests and syntax/static checks; enforce entry points/import/write/implementation scope and Builder/Benchmark/Evaluator separation. Retain failing names/codes/compile traces/stderr; no repair. Type/lint checks apply when configured.
- **FR-004** (§4.2.4): Enforce configured time/operational limits and metric structure; benchmark evidence includes baseline/treatment, dependent variables, preregistered measurements and complete comparison metadata. Do not reinterpret science or enforce unreliable token/cost accounting.
- **FR-005** (§4.2.5): Detect prohibited os/sys/subprocess/requests/urllib/shutil imports, unauthorized tools/workspace escape, missing applicable unprivileged/network boundary evidence, obvious embedded secrets and missing attribution. Confirmed violation is FAIL; unavailable environment is ENVIRONMENT_BLOCKED.
- **FR-006** (§4.2.6): Reviewer adapts result-evaluator/citation-reviewer prompts; claims/citations must match supplied evidence. Contradictions, unsupported leaps, omitted uncertainty/limitations and corrupt empirical values yield structured reasons/references without rewriting scientific criteria/verdict.
- **FR-007** (§4.2.7): Verify actual execution/lifecycle/upstream gates/effects rather than agent success claims; next node stays locked. Preserve reviewer identity/time/reasons/evidence and route blocked/ambiguous/failed cases to human inspection without silent pass or automatic replay.
- **FR-008** (§4.2.8): Minimum result fields and deterministic tier order/normalization are preserved; final result is persisted before transition. Only PASS/PASS_WITH_KNOWN_LIMITATIONS advances with warnings; other verdicts halt. Valid scientific FAIL remains unchanged and admitted as infrastructure PASS.
- **FR-009** (§4.2.9 case 1): Complete valid artifact passes both tiers, emits PASS and starts the next Swarmflow node.
- **FR-010** (§4.2.9 case 2): Missing mandatory field or invalid field type gives Tier-1 FAIL, Tier-2 NOT_RUN, no reviewer invocation and no downstream start.
- **FR-011** (§4.2.9 case 3): Wrong run, node, capsule version or interface hash produces FAIL and downstream remains locked.
- **FR-012** (§4.2.9 case 4): Structurally valid unsupported citation/claim reaches Tier 2, yields FAIL or INCONCLUSIVE under the fixed rubric, and blocks downstream.
- **FR-013** (§4.2.9 case 5): Forced time overrun is detected by Tier 1, halts and preserves timeout evidence without requiring a semantic call.
- **FR-014** (§4.2.9 case 6): Forbidden import or undeclared tool produces infrastructure FAIL and halts for developer triage.
- **FR-015** (§4.2.9 case 7): Missing required dependency/runtime yields ENVIRONMENT_BLOCKED rather than asserted artifact defect, halts and invokes human review.
- **FR-016** (§4.2.9 case 8): Passing all mandatory requirements with a documented non-blocking limitation gives PASS_WITH_KNOWN_LIMITATIONS, persists warnings and advances.
- **FR-017** (§4.2.9 case 9): Valid scientific FAIL stays in Evaluation_Verdict.json; infrastructure PASS releases Stage 3.9 Delivery normally.
- **FR-018** (§4.2.9 case 10; §1.4): Delayed/blocked Gate decision cannot start downstream until an advancing verdict is durably recorded; producer success alone cannot release it.
- **FR-019** (§4.2.1 blacklist; §4.2.2 blacklist; §4.2.3 blacklist; §4.2.4 blacklist; §4.2.5 blacklist; §4.2.6 blacklist; §4.2.7 blacklist; §4.2.8 constraints; §4.2.10 excluded): Gate remains fixed two-tier, read-only and evidence-bound without excluded autonomous evaluation/repair, ensembles, web fact checking, legal certification or enterprise approval machinery.
- **FR-020** (§4.2.1; §4.3.3, §4.3.4, consumed from M1-004): Tier-2 Verifier calls use the approved audited model-routing/bridge boundary. Required artifact, contract, evidence and acceptance content remain available for semantic review, while internal labels used solely for attribution/benchmarking are not inserted into prompts or forwarded to the provider. Local invocation attribution consumes M1-004's canonical agreement without another audit schema.

### Key Entities
The PRD supplies evidence obligations, verdict vocabulary, tier order and release rules; their acceptance is specified above. [M1-IF-007@r0](TASK.md#4-embedded-cross-module-agreements) reserves detailed Gate contracts for Architecture. Tier-2 invocation consumes [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements) for local model-use attribution and provider-boundary minimization. No competing payload schema is defined.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §4.2.1 / FR-001 / US1 | Applicable evidence obligations are present; mandatory deterministic failure halts before any semantic model call; passing Tier 1 enables independent read-only reviewer context. Policies/prompts/thresholds/aggregation remain frozen and outside RSI. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-002 | §4.2.2 / FR-002 / US1 | Validate fields/types/bounds, declared artifact kinds/filenames and proof obligations; reject mismatched run/node/version/interface hash, undeclared tools/outputs and structurally incomplete evidence despite plausible prose. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-003 | §4.2.3 / FR-003 / US1 | Run supplied mandatory tests and syntax/static checks; enforce entry points/import/write/implementation scope and Builder/Benchmark/Evaluator separation. Retain failing names/codes/compile traces/stderr; no repair. Type/lint checks apply when configured. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-004 | §4.2.4 / FR-004 / US1 | Enforce configured time/operational limits and metric structure; benchmark evidence includes baseline/treatment, dependent variables, preregistered measurements and complete comparison metadata. Do not reinterpret science or enforce unreliable token/cost accounting. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-005 | §4.2.5 / FR-005 / US1 | Detect prohibited os/sys/subprocess/requests/urllib/shutil imports, unauthorized tools/workspace escape, missing applicable unprivileged/network boundary evidence, obvious embedded secrets and missing attribution. Confirmed violation is FAIL; unavailable environment is ENVIRONMENT_BLOCKED. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-006 | §4.2.6 / FR-006 / US1 | Reviewer adapts result-evaluator/citation-reviewer prompts; claims/citations must match supplied evidence. Contradictions, unsupported leaps, omitted uncertainty/limitations and corrupt empirical values yield structured reasons/references without rewriting scientific criteria/verdict. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-007 | §4.2.7 / FR-007 / US1 | Verify actual execution/lifecycle/upstream gates/effects rather than agent success claims; next node stays locked. Preserve reviewer identity/time/reasons/evidence and route blocked/ambiguous/failed cases to human inspection without silent pass or automatic replay. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-008 | §4.2.8 / FR-008 / US1 | Minimum result fields and deterministic tier order/normalization are preserved; final result is persisted before transition. Only PASS/PASS_WITH_KNOWN_LIMITATIONS advances with warnings; other verdicts halt. Valid scientific FAIL remains unchanged and admitted as infrastructure PASS. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-009 | §4.2.9 case 1 / FR-009 / US1 | Complete valid artifact passes both tiers, emits PASS and starts the next Swarmflow node. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-010 | §4.2.9 case 2 / FR-010 / US1 | Missing mandatory field or invalid field type gives Tier-1 FAIL, Tier-2 NOT_RUN, no reviewer invocation and no downstream start. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-011 | §4.2.9 case 3 / FR-011 / US1 | Wrong run, node, capsule version or interface hash produces FAIL and downstream remains locked. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-012 | §4.2.9 case 4 / FR-012 / US1 | Structurally valid unsupported citation/claim reaches Tier 2, yields FAIL or INCONCLUSIVE under the fixed rubric, and blocks downstream. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-013 | §4.2.9 case 5 / FR-013 / US1 | Forced time overrun is detected by Tier 1, halts and preserves timeout evidence without requiring a semantic call. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-014 | §4.2.9 case 6 / FR-014 / US1 | Forbidden import or undeclared tool produces infrastructure FAIL and halts for developer triage. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-015 | §4.2.9 case 7 / FR-015 / US1 | Missing required dependency/runtime yields ENVIRONMENT_BLOCKED rather than asserted artifact defect, halts and invokes human review. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-016 | §4.2.9 case 8 / FR-016 / US1 | Passing all mandatory requirements with a documented non-blocking limitation gives PASS_WITH_KNOWN_LIMITATIONS, persists warnings and advances. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-017 | §4.2.9 case 9 / FR-017 / US1 | Valid scientific FAIL stays in Evaluation_Verdict.json; infrastructure PASS releases Stage 3.9 Delivery normally. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-018 | §4.2.9 case 10; §1.4 / FR-018 / US1 | Delayed/blocked Gate decision cannot start downstream until an advancing verdict is durably recorded; producer success alone cannot release it. | BOUNDARY; full journey owned by M1-SYSTEM |
| AC-019 | §4.2.1 blacklist; §4.2.2 blacklist; §4.2.3 blacklist; §4.2.4 blacklist; §4.2.5 blacklist; §4.2.6 blacklist; §4.2.7 blacklist; §4.2.8 constraints; §4.2.10 excluded / FR-019 / US1 | Gate remains fixed two-tier, read-only and evidence-bound without excluded autonomous evaluation/repair, ensembles, web fact checking, legal certification or enterprise approval machinery. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |
| AC-020 | §4.2.1; §4.3.3, §4.3.4 / FR-020 / US1; canonical audit acceptance owned by M1-004 | The Verifier call crosses the consumed M1-004 approved/audited routing boundary and remains locally joinable to its originating execution. Internal stage/role/capsule labels used solely for benchmarking are omitted from the provider-facing request; substantively required review evidence remains supplied. Supported calls cannot silently bypass auditing, and unavailable reliable token/cost usage is not itself a Gate failure. No independent audit payload format is defined here. | BLOCK, BOUNDARY; full journey owned by M1-SYSTEM |

Numerical time/resource limits come from registered active capsule/task configuration; unspecified values remain PENDING_SOURCE until that source is supplied. No guessed time, token, cost or quality threshold is introduced. Runtime checks remain NOT_RUN.

## Scope and Assumptions
- Included: Check node evidence with deterministic Tier 1 then independent read-only Tier 2, persist structured infrastructure verdicts and control advancement while preserving scientific conclusions.
- Excluded: No reviewer swarms/voting, Auto Harness/live evaluator modification, schema repair/relaxation, autonomous engineering repair/refactoring, cheaper-model rerouting or learned thresholds; no legal/regulatory certification, per-gate web fact checking/replication panels, enterprise approval queues or automatic replay. All §4.2.10 autonomous multi-faceted evaluation is excluded.
- Global constraints: scientific lane; local single user; fixed sequential Phase 1; permitted evidence only; contract-bound tools/effects; frozen scientific protocol; independent read-only verification; durable gate before release; preserved failures and explicit human handling; native working memory distinct from system evidence; offline RSI with manual activation. Apply §2.1–§2.12 to owned behavior; peer TASKs own their mechanisms.
- Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-013@r0](../M1-013/TASK.md#4-embedded-cross-module-agreements); [M1-IF-014@r0](../M1-014/TASK.md#4-embedded-cross-module-agreements); [M1-IF-015@r0](../M1-015/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: sole active Codex CLI endpoint for Phase 1, including Reviewer. No underlying model ID is prescribed; observe actual identity/version during verification. No locally hosted weights or earlier design-document model pool is imported into this PRD allocation.
- Unresolved inputs: Architecture binds envelope/result types, aggregation and Gate bootstrap without changing supplied vocabulary. Exact time limits, per-node fixed reviewer rubrics and supplied test entries must come from registered configuration/capsule sources; no thresholds are invented. Architecture PENDING_SOURCE constrains technical realization only. Complete source clauses and exclusions remain authoritative.
- System task: [M1-SYSTEM](../M1-SYSTEM/TASK.md) owns complete research journeys/candidate acceptance; this task supplies source-level block/boundary evidence. A minimal A/Gate/B run is not full M1 completion.

This is the AC authority. TASK owns interfaces; plan.md owns design/check procedures; tasks.md owns work and evidence mapping.
