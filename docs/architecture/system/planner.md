---
id: system.planner
type: module-spec
status: draft
version: 4
sources: [../flow.md, integration.md]
provides: [system.planner, system.plan_validation, system.experimental_planner]
consumes: [m1.control_flow, cc.type.run_plan]
depends_on: [../flow.md, ../decisions.md, ../verification.md, ../types/run-plan.md, ../capsule/library.md, ../capabilities/research-template.plan.json, lifecycle.md, experiments.md]
tags: [system, planner, m1]
level: detail
prd: [4.8.2, 4.8.3, 4.6.2]
---

# Planner, validation and binding

PRD: 4.8.2, 4.8.3, 4.6.2

> Answers: How is a plan proposed, validated, bound and frozen?

## Purpose

Two separate things share the word "planner". Do not mix them.

| | Production planner (M1) | Experimental Leader-agent planner |
|---|---|---|
| Track | production | isolated_experiment only ([experiments](experiments.md)) |
| Runs | every run, after the accepted requirements | only inside an approved experiment profile |
| Model calls | none: zero model calls, no planning reservation | model-proposed DAG through the [model bridge](model-bridge.md#term-model-bridge), with a planning reservation |
| Output | the fixed template DAG, for the shared validator | candidate DAG for the same validator, plus experiment evidence |

Both are ordinary services, not [capsules](../capsule/capsule.md#term-capability-capsule), not RSI-able, and neither [releases](lifecycle.md#term-release) work. Everything after the candidate DAG (validate, bind, freeze, dispatch, delivery) is the same code, called by the supervisor. The planner-to-bridge edge, the planning scope, the planning reservation and model-proposed DAGs exist only in the isolated experiment track.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-planner"></a>**Planner** | An ordinary service that proposes the DAG of task nodes. In M1 it returns one fixed template with no model call; it is not a capsule, cannot be improved by RSI and releases nothing. |
| <a id="term-plan-validator"></a>**Plan validator** (also: validator) | A pure function that checks a whole proposed DAG for wrong ports, cycles, permissions, budgets, missing objective coverage and missing Gates. An invalid plan means zero dispatch, and the validator never repairs it. |
| <a id="term-binder"></a>**Binder** | The deterministic step that resolves each task node to an exact admitted capsule version in the run's library snapshot and attaches its Gate. It runs before freeze 2. |

## Position in the fixed flow

- Order: intake, intent call + [Gate](../verification.md#term-gate), requirement call + Gate, **planner**, validate / bind / freeze, dispatch, planned [nodes](nodes.md#term-node) each followed by its Gate, delivery ([flow](../flow.md)).
- The planner [runs](lifecycle.md#term-run) **after the requirement call is released**, inside the same run, from the **same [library snapshot](../capsule/library.md#term-library-snapshot)** pinned at launch (decision A26). It never sees a different snapshot.
- Prep nodes (intent, requirement) are not planned. They come from the [prep plan](../types/run-plan.md#term-prep-plan) [frozen](lifecycle.md#term-freeze) at launch (freeze 1). The planner adds only the task nodes (freeze 2). See [lifecycle](lifecycle.md#phases-and-the-two-freeze-points-decision-a26).
- The supervisor calls the planner, then the validator, then the binder. The planner does not call the validator.

## Interface: inputs, output and placement

Messages of this module. The sections below give their meaning.

- **Ask the planner for a DAG** (call, supervisor -> planner). Schema: [`services-v1.schema.json#planner_request`](../contracts/services-v1.schema.json).
- **The proposed DAG envelope** (record, planner -> supervisor, which commits it and passes it to the validator). Schema: [`services-v1.schema.json#planner_proposal`](../contracts/services-v1.schema.json).
- **Ask the validator to check a proposal** (call, supervisor -> validator). Schema: [`services-v1.schema.json#validation_request`](../contracts/services-v1.schema.json).
- **Validator verdict and normalized plan** (call, validator -> supervisor). Schema: [`services-v1.schema.json#plan_validation`](../contracts/services-v1.schema.json), findings coded by [`services-v1.schema.json#plan_finding_code`](../contracts/services-v1.schema.json).

- Inputs: the accepted immutable requirement output (`task_ref`, the same record as `accepted_requirements_ref`) with the accepted intent reference, the pinned library snapshot, effective policy and configuration, and run identity. The request is `services-v1.schema.json#planner_request`. The request fields are `version`, `run_id`, `accepted_requirements_ref`, `accepted_intent_ref`, `task_ref`, `library_snapshot_ref`, `config_ref`, `request_id`, `planning_reservation_ref` and `experiment_config_ref`. `planning_reservation_ref` and `experiment_config_ref` are nullable: both are null in M1 (the fixed-template planner makes no model call and writes no planning reservation) and are refs only in the isolated experiment track.
- Validator: the input is the committed `planner_proposal` (`validation_request.plan_ref`, never a bare [run plan](../types/run-plan.md#term-run-plan)) with the task, snapshot and policy refs; the output is `plan_validation`, whose `validated_plan_ref` (present only when `status` is `VALID`) is the normalized run plan that freeze accepts.
- Output: a captured candidate plan with capability selections, node dependencies, typed input/output bindings, required Gate profiles, resource budgets and objective-to-terminal-output coverage. For production, `proposal_source_ref` is the deterministic fixed-plan provenance, never fabricated model evidence.
- The planner chooses work structure only. It never chooses credentials, filesystem permissions, admission policy, active aliases or the library snapshot. Generated source code is never executable dispatch authority.
- **First version:** returns one fixed template DAG, [research-template.plan.json](../capabilities/research-template.plan.json), selected from the pinned snapshot. The template is a planned-only phase (`phase: planned`): it holds only the task nodes and reads released prep outputs through `prep.<step_id>.<port>`; the preparation [steps](nodes.md#term-step) live in the prep plan. It is a plain service output and passes the full validator like any proposal. A new capsule becomes a node through a hand-authored frozen plan or a new template. Selecting capsules from the catalogue is Phase 2.
- **Model-proposed DAGs** are not part of the M1 production path. They run only in the isolated experiment track ([experiments](experiments.md)), through the same validator. Promoting one to production needs a PRD decision.
- Placement: `cc/planning/service.py` and the pure validator `cc/planning/validate.py`. The experimental Leader adapter (`cc/adapters/leader.py`) belongs to block B27 and the [experiments](experiments.md) page, not to the production planner. [Reuse audit](reuse-audit.md) records pinned native symbols.

## Behavior: validation, binding and freeze 2

1. **Select the plan.** Production: the supervisor asks the planner for the fixed template from the pinned snapshot; no model is called and no planning reservation is written. Experiment track only: the supervisor first commits a planning reservation and captures the request under an authenticated bounded model scope; failed persistence prevents model work or dispatch, and duplicate identities reuse reserved state rather than issuing another paid call.
2. Preserve the proposal as an immutable Artifact. A proposal is not permission to execute.
3. **Validate** (supervisor calls the validator): exact type versions, available required inputs, unique nodes, acyclicity, dependency closure, admitted versions in the pinned snapshot, reachability, objective coverage, permissions, budgets and a Gate for every node. [Findings](../schemas/finding.md#term-finding) use the ten closed codes of `plan_finding_code`: `CYCLE`, `MISSING_PRODUCER`, `WRONG_VERSION`, `UNREACHABLE_OBJECTIVE`, `DENIED_EFFECT`, `MISSING_GATE`, `BUDGET_EXCEEDED`, `TYPE_MISMATCH`, `UNKNOWN_CAPABILITY` and `MISSING_INPUT`.
4. **Bind** (supervisor calls the binder) every task node to an exact admitted [work capsule](../capabilities/README.md#term-work-capsule) and its [GateProfile](../schemas/profiles.md#term-gateprofile) and verifier. The trusted builder derives each node's test from the producer's [Declaration](../capsule/fields.md#term-declaration); a Declaration obligation it cannot test fails freeze. Check current revocation without substituting aliases.
5. **Freeze 2:** publish the [planned plan](../types/run-plan.md#term-planned-plan)'s [Bindings](../schemas/binding.md#term-binding) in one [batch](storage.md#term-commit-batch), linked to the accepted requirements, prep plan and the same snapshot. Dispatch only from this committed state.
6. Inject accepted task data and resource references into declared DAG [ports](../capsule/fields.md#term-port). [SwarmFlow](integration.md#term-swarmflow) runs dependency-ready nodes (M1 may run them one at a time). Each node's output and capture are committed, then its Gate runs; only a committed advancing [Verification](../schemas/verification-record.md#term-verification) and release unlock successors. A failed Gate [halts](lifecycle.md#term-halt) the whole run, including sibling branches. Delivery is ordinary code over accepted terminal results.

## Failure: authority and failure

| Situation | Outcome | Recovery |
|---|---|---|
| Invalid proposal (cycle, missing producer, wrong version, denied effect, missing Gate, budget overrun, unreachable objective) | zero planned-node dispatch; findings recorded; run halts with preparation evidence kept | explicit human review; a changed task or input needs a new run ([lifecycle](lifecycle.md#failure-human-review-and-recovery)) |
| Production planner cannot select the template (absent from the pinned snapshot) | halt; zero dispatch; no model call exists to resubmit | fix the library, then a new run |
| Experiment track only: planner model call fails, times out or auth lost | halt; capture kept; no silent resubmission of a paid call | reuse the planning reservation; `cc resume` (human review) allows a new planning attempt under the same pins |
| Validation or freeze write fails | halt; nothing released | revalidate the committed proposal against the same snapshot and publish freeze 2; never re-plan |
| Planner tries to release, repair a running graph or activate a candidate | not possible: it has no such authority | none needed |
| Different task, policy or pins wanted | new run | start a new run |

- One `research.verifier` identity supplies semantic assessment through pinned profiles. Gate-role capsules have zero RSI-mutable components. [Gate host](../capsule/gate-host.md#term-gate-host) and store custody remain the durable authority.
- There is no replanning after a failure and no live restructuring.
- Structural validity does not prove semantic success of a capsule combination; interaction analysis is deferred (A21).
- Bounded plan [test cases](../schemas/checks.md#term-test-case) cover wrong versions, missing producers, cycles, unreachable objectives, denied effects, missing Gates, budget overrun, timeout and failed validation writes.

## Proposal envelope

The proposal is an immutable envelope, not a bare DAG. It preserves task, library and policy pins, selected capsules, objective mappings and budgets. Validation records the proposal reference and publishes the normalized run-plan reference separately; freeze accepts only that committed validated plan. The wire shape is `services-v1.schema.json#planner_proposal`; the plan inside it is the [run plan](../types/run-plan.md).

## Experimental Leader-agent planner (separate track)

- Enabled only by an approved feature profile in the isolated_experiment track; production rejects it with `TRACK_FEATURE_FORBIDDEN` ([experiments](experiments.md)).
- Uses the native Leader capability planning through `cc/adapters/leader.py` (block B27). Native approval is not CC authorization.
- Its candidate goes through the same deterministic validator, binder and freeze. Its manifest is experimental and carries [deviations](../decisions.md#term-deviation) from production.
- It cannot change the production planner, plan template, library aliases or production acceptance.

Related: [model authentication](model-auth.md), [model bridge](model-bridge.md), [environment](environment.md), [library](../capsule/library.md), [storage](storage.md), [lifecycle](lifecycle.md).

## Tests

Fixtures and fakes: planner proposals with a cycle, missing producer, wrong version, denied effect, over budget and forged scope; a fake model bridge (experiment track only); a freeze with a failure injected after one staged Binding. Expected result: zero unauthorized dispatch and recorded findings.

Rows in [test surfaces](test-surfaces.md#verification-table): [V16](test-surfaces.md#verification-table), [V17](test-surfaces.md#verification-table), [V18](test-surfaces.md#verification-table), [V34](test-surfaces.md#verification-table) (prep plan with the real capsules and Gates: zero planner work before the requirement release), [V36](test-surfaces.md#verification-table) (interrupted planner call, proposal committed without freeze 2, freeze 2 without dispatch).
