# Feature Specification: M0-006 — Protected contracts, static graph and gate-locked scheduling

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0](../TASKS.md)
**Revision / date**: r1 / 2026-10-06
**Feature Branch**: ai4r_xiaoyang; directory identity is independent of branch
**Input**: PRD 1.4 (../source/PRD - AI4Research.txt:L211-L261); PRD 2.7 (../source/PRD - AI4Research.txt:L534-L550); PRD 4.1.3 (../source/PRD - AI4Research.txt:L1244-L1265); PRD 4.6 (../source/PRD - AI4Research.txt:L2048-L2051); PRD 4.6.1 (../source/PRD - AI4Research.txt:L2052-L2059); PRD 4.6.2 (../source/PRD - AI4Research.txt:L2060-L2069); PRD 4.6.4 (../source/PRD - AI4Research.txt:L2079-L2087); PRD 4.6.5 (../source/PRD - AI4Research.txt:L2088-L2097); PRD 6.4 (../source/PRD - AI4Research.txt:L2572-L2606); PRD 6.5 (../source/PRD - AI4Research.txt:L2607-L2626); architecture workflow.md, capsules.md, guard-design.md, m1-design.md, delivery-phases.md, principles.md; parent immutable source manifest
**Status**: Specified for preparation; runtime NOT_RUN

## User Scenarios & Testing

### User Story 1 — Complete the bounded declared outcome (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Complete fixture run plus missing node/cycle/unbound input topology., when the AC-001 operation is exercised, then Freeze and execute the declared static graph through real shared adapters.
2. Given One node with multiple CCs and future predecessor output references., when the AC-002 operation is exercised, then Instantiate concrete accepted artifact hashes under frozen templates.
3. Given Library activation/suspension after freeze and tampered contract., when the AC-003 operation is exercised, then Execute original admitted pin where still eligible.
4. Given Real work Node A, two-tier gate and bounded real work Node B with delayed/failed commit., when the AC-004 operation is exercised, then Node B starts once only after committed advancing decision; verifier is not Node B.
5. Given Failure at each state plus already in-flight task and lost submit response., when the AC-005 operation is exercised, then Preserve coherent halt reason and original failure history.
6. Given Browser disconnect, service kill/restart and interactive/headless fault profiles., when the AC-006 operation is exercised, then Submit request identity reconciles lost response without duplicate execution.

### User Story 2 — Reject invalid or inadmissible work without advancement (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Complete fixture run plus missing node/cycle/unbound input topology., when the AC-001 operation is exercised, then Reject missing obligations, unsupported CCs, cycle and attempted live parallel/dynamic insertion.
2. Given One node with multiple CCs and future predecessor output references., when the AC-002 operation is exercised, then Reject unknown governance fields, broadened permission and candidate rather than accepted input.
3. Given Library activation/suspension after freeze and tampered contract., when the AC-003 operation is exercised, then Reject mutation, substitution and stale eligibility.
4. Given Real work Node A, two-tier gate and bounded real work Node B with delayed/failed commit., when the AC-004 operation is exercised, then Producer done, native cache, missing decision or partial persistence never starts B.
5. Given Failure at each state plus already in-flight task and lost submit response., when the AC-005 operation is exercised, then Reject direct gate override and automatic retry even after native human reply.
6. Given Browser disconnect, service kill/restart and interactive/headless fault profiles., when the AC-006 operation is exercised, then Reject automatic resume, foreign callback, distributed worker lease and hidden replay.

### User Story 3 — Recover inspectability without silent replay or overwritten evidence (Priority: P1)

The authorized user or consuming module observes the source-defined outcome within the declared phase and authority.

**Independent Test**: Use fixed independent fixtures identified by each AC; inspect artifacts, actual effects and durable records. Mocks prove only the stated block behavior, not live service integration.

**Acceptance Scenarios**:

1. Given Complete fixture run plus missing node/cycle/unbound input topology., when the AC-001 operation is exercised, then Disabling an experimental path selects this baseline only for fresh attributable work.
2. Given One node with multiple CCs and future predecessor output references., when the AC-002 operation is exercised, then Future-valued inputs are bound before node start without changing policy/topology.
3. Given Library activation/suspension after freeze and tampered contract., when the AC-003 operation is exercised, then Human corrected run obtains new snapshot and lineage, not an overwritten old freeze.
4. Given Real work Node A, two-tier gate and bounded real work Node B with delayed/failed commit., when the AC-004 operation is exercised, then Rebuild readiness from durable state after restart without replaying unknown effects.
5. Given Failure at each state plus already in-flight task and lost submit response., when the AC-005 operation is exercised, then Explicit correction starts a linked new run with fresh gate checks.
6. Given Browser disconnect, service kill/restart and interactive/headless fault profiles., when the AC-006 operation is exercised, then Inspection/correction never converts old blocked decision into PASS.

### Edge Cases

Each AC includes its normal, failure and recovery scenario above. Shared cases include missing/invalid inputs, foreign or stale artifact/contract/implementation identity, unavailable required service, budget exhaustion, permission/disclosure escape, malformed assessment, cancelled or uncertain delivery, persistence failure, duplicate request, restart and incompatible revisions as applicable. Omissions require a source-based explanation in the implementing plan; an all-skipped suite is not acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Bind and run the hardcoded Phase 1 research graph as the operational fallback. Source: PRD 4.1.3, PRD 4.6.2, PRD 6.5.
- **FR-002**: Assemble objective-instance contracts distinct from declarations and invocations. Source: PRD 1.4, PRD 4.1.3.
- **FR-003**: Freeze full binding snapshot and preserve current eligibility checks. Source: PRD 4.1.3, PRD 1.4.
- **FR-004**: Gate-lock readiness using durable authoritative decisions. Source: PRD 4.6.1, PRD 4.6.2, PRD 6.4.
- **FR-005**: Halt the whole run on blocking faults while retaining all attempts. Source: PRD 2.7, PRD 4.6.4.
- **FR-006**: Keep browser independence, pause-on-restart and mode-specific triage. Source: PRD 4.6.4, PRD 4.6.5.

### Key Entities

ContractAndGraphBinding, FrozenExecutionBinding, typed artifact reference, immutable input/implementation/profile pins, run/node/attempt/invocation identity and observable result. Exact semantics are owned by [TASK §4](TASK.md#m0-if-006-at-r1).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD 4.1.3, PRD 4.6.2, PRD 6.5; FR-001; US1/US2/US3 | All 3.1–3.9 responsibilities execute in immutable sequential order with one opportunity/hypothesis; Phase 1 does not semantically search/invent capabilities; preparation remains separate bounded governed work. Enforce one active sequential research run. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-002 | PRD 1.4, PRD 4.1.3; FR-002; US1/US2/US3 | Contract binds user/workspace/run/node, objective, accepted inputs, outputs/proof obligations, exact CC/dependency/check pins and limits before dispatch; permissions only narrow admitted authority. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-003 | PRD 4.1.3, PRD 1.4; FR-003; US1/US2/US3 | Topology/templates/library/check/profile/model/configuration pins are immutable; active selection changes do not alter run; current suspension still blocks start/release with no replacement. Planning and dispatch share the same predicate semantics; false rejects, unknown/stale/unavailable never silently passes, and value-dependent preconditions are explicit fresh dispatch obligations. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-004 | PRD 4.6.1, PRD 4.6.2, PRD 6.4; FR-004; US1/US2/US3 | Pending->Running->Evaluating->Completed/Failed projection is backed by authoritative run state; only PASS/PASS_WITH_KNOWN_LIMITATIONS with all obligations releases the exact successor inputs. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-005 | PRD 2.7, PRD 4.6.4; FR-005; US1/US2/US3 | No new dispatch after execution/security/budget/evidence/verification fault; no autonomous repair/requeue/replan; in-flight observations remain stored and cancellation is distinct. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |
| AC-006 | PRD 4.6.4, PRD 4.6.5; FR-006; US1/US2/US3 | Browser close does not cancel accepted work; service restart preserves results and pauses interrupted attempts; interactive native callback is projected once, headless halts nonzero without prompting. | BLOCK and BOUNDARY; contributing integrated SYSTEM checks in M0-SYSTEM |

Mandatory behavior/failure constraints use exact source requirements; finite independent fixture cases must all meet their stated assertions. Source examples do not become arbitrary thresholds. Scientific thresholds are supplied/frozen for the run, not coding-agent inventions. Missing numeric policies are PENDING_SOURCE only for affected checks.

## Scope and Assumptions

- Included: Assemble preparation and planned Node Execution Contracts; freeze the operational sequential Phase 1 graph, bind accepted artifacts and exact library/check pins, and dispatch only after durable gate acceptance.
- Excluded: No live graph restructuring, parallel hypotheses, distributed dispatch, active-version substitution, hidden retries or producer-written readiness.
- Consumed agreements: [M0-IF-003@r1](../M0-003/TASK.md#m0-if-003-at-r1); [M0-IF-005@r1](../M0-005/TASK.md#m0-if-005-at-r1).
- Permitted models: Phase 1 uses the PRD static subscription-authenticated Codex route; do not invent model IDs or providers. Phase 3 uses only explicitly approved pinned profiles/endpoints; before approval, mocks/analysis are labelled. Relevant provider model identifier/version is captured from actual runtime, never assumed.
- Architecture D1–D15 applies by responsibility; D5/D6 are explicit adopted amendments, not silent unchanged compliance. M0 is the coding-program folder, M1 the product.
- Verification checks outputs and evidence; gating applies advancement policy. M1 mandatory integration preserves distinct responsibilities and protected durable verdict/release. All Tier-2 profiles consume M0-007 required upstream adaptation; no profile skips PRD 4.2.6 by using an unrelated generic prompt.
- System contribution: [M0-SYSTEM](../M0-SYSTEM/spec.md); this spec owns block/boundary acceptance and does not duplicate complete-system criteria.

This is the acceptance authority. Technical realization belongs in plan.md; work and current evidence are in tasks.md. No runtime acceptance is claimed by specification generation.
