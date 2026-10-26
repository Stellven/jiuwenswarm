# QA and Benchmark integration foundation

Build a small, reusable benchmark integration foundation alongside the
product. Deliver one executable integration test case for each of:
Capability Capsules, Evaluator/Verifier, Model Routing, and RSI.

The purpose is to demonstrate the actual execution and evidence paths,
then let the benchmark team extend them with independently owned fixtures,
oracles, and scoring. This work does not implement the full benchmark suite
or establish module performance or full-product acceptance.

## References and source authority

Resolve the following files relative to this prompt in the QA repository
or extracted package. Do not use workstation-specific paths from historical
links inside the reference documents as required execution locations.

- [BENCHMARK_REQUIREMENTS.md](./BENCHMARK_REQUIREMENTS.md)
  Approved v0.12: authority for benchmark obligations and applicability.
  Read Sections 1.2, 2, 3, 5, 6, 7, 9, and 11-12 as applicable to these
  four integration cases. Wider campaign requirements remain staged.
- [BENCHMARK_INTERFACE_CONTRACT.md](./BENCHMARK_INTERFACE_CONTRACT.md)
  Proposed architecture agreement v0.5: benchmark interface handoff.
  Read the shared conditions in Sections 3-10 and the module bindings in
  Sections 11.1 (CC), 11.3 (Evaluator/Verifier), 11.4 (Model Routing), and
  11.5 (RSI). Reuse existing product interfaces and reconcile proposed
  bindings with the adopted product design. Sections 12-13 provide
  interface disposition and evidence context; this prompt defines the
  limited four-case implementation scope.

External product-design input is required. The main Spec Kit kickoff prompt
must supply an accessible product repository or design package and its
pinned revision. Resolve its current authority index, product/module
contracts, and Docker execution instructions before planning dependent
implementation. Record the exact design paths and revision used. These
product designs are not included in this three-file QA package. If they
cannot be resolved, report the missing dependency explicitly rather than
invent interfaces or treat an older pinned architecture assessment as the
latest design.

Select representative scenarios and fixtures independently from the approved
benchmark requirements and adopted product contracts. Historical examples
and source links inside the reference documents do not prescribe the case
design or add required inputs to this workstream. Obtain any required
governing source from the pinned product package rather than assuming a
historical local path is available.

Use the adopted product/module design for implementation details and the
approved benchmark requirements for benchmark obligations and milestone
applicability. Record source conflicts and unresolved dependencies; do not
silently change benchmark requirements or product contracts.

## Docker execution environment

Implement and validate this foundation in the Docker environment defined
by the adopted product design. All four cases must exercise the
containerized product through its supported interfaces. Follow its images,
services, networking, volumes, resource limits, and process boundaries,
including separation of candidate execution and protected referee resources.

Provide reproducible Docker build, startup, test, evidence-export, and
cleanup commands with explicit prerequisites and configuration. Record the
effective image identity and runtime configuration. Distinguish actual host
hardware from container-visible resources and limits. Host-only or mock
checks may supplement integration evidence but cannot replace the required
Docker execution path.

The implementing agent must run the applicable checks in this environment
and provide commands, results, and evidence. Unexecuted scripts are
insufficient. Report required human actions and blocked dependencies
separately; do not fabricate approvals or mark blocked execution as passed.

## Scope

Create four representative integration cases. A case may contain small
controlled variants where needed to demonstrate the relevant boundary:

1. Capability Capsules
   Execute one admitted capsule on frozen, contract-valid research inputs
   through the real resolver, runner, required checks, and gate. Verify the
   exact capsule identity, required output, and persisted execution evidence.
   Make fixtures replaceable without changes to product execution code.

2. Evaluator/Verifier
   Assess a valid artifact and an intentionally invalid counterpart through
   the supported checking path. Verify expected verdicts and actual
   advance/block behavior, including persisted decisions and downstream
   locking. A verdict string alone is insufficient evidence.

3. Model Routing
   Exercise an actual supported routing decision using declared compatible
   routes. Record the selected route, effective model/endpoint/adapter,
   compatibility findings, execution outcome, and available usage.
   Demonstrate a controlled incompatible-route rejection or unavailable-route
   outcome. Static route logging or mocks must not be presented as evidence
   of dynamic routing quality or cost savings.

4. RSI
   Execute one bounded offline improvement session through the real
   controller and independent evaluation path. Preserve parent/candidate
   identities, authorized changes, evaluation actions, budgets/exposure
   accounting, qualification evidence, and terminal outcome. Verify that
   session completion does not bypass admission or activation policy.
   A correctly reported no-improvement or inconclusive outcome is valid
   integration evidence; it is not a successful-improvement claim.
   Enforce the declared policy where no qualifying candidate is produced.

## Implementation requirements

- Use existing supported product entry points and shared execution,
  checking, isolation, and evidence infrastructure. Do not create a parallel
  execution path that bypasses product controls.
- Provide reusable adapters and documented fixture/result interfaces.
  Additional cases must be addable without modifying the product core.
- Support bounded, headless execution with attributable terminal outcomes.
- Freeze each case's inputs, expected behavior, relevant versions,
  evaluation profile, and budgets before execution.
- Capture actual hardware/readiness before each test or repeat.
- Retain failed, timed-out, blocked, and cancelled attempts. Do not silently
  retry or replace them.
- Keep protected expected answers and scoring material outside the evaluated
  agent, capsule, and RSI proposal contexts.
- Clearly distinguish real execution, mock-only checks, and blocked
  dependencies. Missing mandatory real execution remains incomplete.
- Keep design-specific algorithms, thresholds, limits, and storage choices
  in versioned profiles or owning module contracts.

## Deliverables

- Four runnable case definitions with frozen example fixtures.
- Reusable launch, observation, reconciliation, and evidence-retrieval
  adapters as applicable to each module.
- Documented Docker build, startup, test, evidence-export, and cleanup
  commands, prerequisites, configuration, and expected outcomes.
- Machine-readable results linked to actual raw execution evidence.
- A coverage report mapping each case to relevant benchmark requirements,
  with unsupported capabilities and remaining gaps.
- Instructions showing how the benchmark team can add a new fixture,
  independent oracle, and case without changing product execution code.

## Acceptance and staging

Verify that the cases use the actual supported product paths, that their
observable outcomes match the frozen expectations, and that exported
evidence supports independent checking. Product self-reports alone do not
establish correctness.

These four cases establish integration readiness only. They do not replace
the complete Phase 1 workflow and verifier acceptance requirements.
Model Routing and RSI benchmark campaigns remain scheduled for M2/M3;
preparing their integration foundations does not make them M1 benchmark
acceptance gates.

Include this workstream explicitly in the specification, implementation
plan, task breakdown, and validation report.

