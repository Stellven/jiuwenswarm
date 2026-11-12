# Authorized engine-factory design change — 2026-11-12

Status: authorized by the operator for the engine-factory workflow under
[AMENDMENT.md](AMENDMENT.md). This records the policy change and its boundaries;
it does not restore M1. See [RESPONSIBILITIES.md](RESPONSIBILITIES.md) for ownership.

## Decision

Replace M1's freeze-then-execute policy with a contract-driven revisable loop:

**task contract → justified next actions → resource-aware execution →
evidence/assessment → revised actions**, until the contract is satisfied,
further action is unjustified, or the budget is exhausted.

M1 sources here refer to read-only history at `141c1c4`.
`docs/architecture/design-package/reference/run-plan.md` forbids replanning,
substitution and pin changes after freeze. In
`jiuwenswarm/research/scheduler.py:Scheduler.execute_plan`, dispatch requires
`plan['frozen']`; `jiuwenswarm/research/binding.py:Binder.freeze` captures the
graph, pins and one-attempt limit before execution.

Main does support bounded linked continuation: in
`jiuwenswarm/research/planning.py:PlanOutcomeController.record`, a planned
proposal rejection or infeasibility can allocate one linked compiler attempt,
for two plan attempts total. `planning.py:research_continuation` validates that
allocation. A rejected static template escalates immediately. Main therefore
has bounded replanning across runs; the authorized departure is **in-run
revision** after evidence, without repeating compiler/planner admission.

The agent chooses and justifies actions. The host checks authority, identity,
contracts and lifecycle. Revising work never changes the scored comparison's
contract or expands grants; a changed contract requires a new revision and
comparable run set. The task graph records work and does not dispatch it.

## What was relaxed

- Mandatory verifier agents for intermediate outputs.
- Fixed output-port chains as the compulsory workflow.
- Semantic review for every tool call.
- Repeated approvals within authority already granted by the operator.
- Serial Intention Compiler → planner → binder/freeze ceremony before execution.

## What remains enforced in code

Factory references below are relative to `jiuwenswarm/factory/`. These are host
API guarantees within the trusted local execution model described below.

| Boundary | Enforcement and source (`file:symbol`) |
|---|---|
| Decision revisions | `store.py:Store.advance_decision` uses transactional compare-and-swap (CAS) on `expected_rev`, assigns parent/revision identity and validates cited evidence. Stale writes fail. |
| Append-only evidence, attempts and plan patches | `store.py:Store.__init__` protects observations, artifacts, decisions and evaluations against update/delete; `Store._event` appends evidence snapshots. `Store.create_attempt` retains separate attempts; `Store.transition_attempt` appends lifecycle history while updating the current snapshot. `taskgraph.py:plan_patch` appends immutable observations with graph CAS and decision lineage; `apply_decision_patch` can commit a decision and patch atomically. |
| Frozen contract reference and immutable task contract ID | `controller.py:Controller.init_task` and `store.py:Store.create_task` persist the pinned task inputs; `api.py:dispatch` exposes no task-update operation. `ab.py:submit` requires the task's contract ID and a frozen stdout reference, and snapshots the contract per attempt. `contract.py:freeze` rejects refreezing; ordinary unscored lab runs remain distinguishable via `contract.py:evaluate`. |
| Exact image admission | `manager.py:Manager.admit` requires a successful build and equality of the requested immutable image ID, local inspected ID and build receipt; it also checks the target architecture/profile. |
| Module-appropriate acceptance pinned per attempt | `ab.py:submit` captures `component_material` with the contract in the durable request; `ab.py:analyse` and `ab.py:acceptance` evaluate verified evidence under those captured rules (performance, observability or prerequisite). `controller.py:validate_keep_evidence`, called by `api.py:dispatch`, requires `keep_component` to cite matching component evidence with `acceptance.verdict == accept`. |
| Idempotent durable jobs and reconciliation | `jobs.py:Jobs.submit` fingerprints inputs, persists attempt identity before launch and rejects key conflicts. `Jobs._recover` recovers lost acknowledgements; `Jobs.status` reconciles the recorded queue, and `Jobs.retry` requires a terminal attempt and new key. `controller.py:Controller._reconcile` runs before model work on restart. |
| Queue GPU/build exclusivity | `jobs.py:Jobs.__init__` selects the shared jobq and `Jobs.submit` records the class/queue. The siminfeng `bin/jobq:compatible` rule excludes concurrent GPU/build jobs in that queue. |
| Budget, turn limits and cancellation | `controller.py:Controller._remaining` and `Controller.run` enforce persisted turn/wall-clock limits and return partial evidence on exhaustion. `Controller.cancel`, `jobs.py:Jobs.cancel` and `manager.py:Manager.cancel` record cancellation intent and reconcile the actual lifecycle. Budget exhaustion alone does not cancel running jobs. |
| Task-scoped store reads | `store.py:ScopedStore._check` restricts reads to the current task and explicitly authorized prior tasks, and forbids cross-task writes. `controller.py:read_tasks` / `configure_agent` derive that read scope from operator constraints; `api.py:main` installs it for native calls. |
| Operator authority | `controller.py:configure_agent` intersects task `allowed_effects` with operator grants; decisions and graph patches cannot widen them. |

## What relies on the trusted local operator/agent

- Native capsule tools run as the local user (`trusted_local`). The factory adds
  no execution sandbox beyond Codex `workspace-write`; native tools are trusted
  code, and store/API checks are not an OS isolation boundary.
- The agent can edit its owned checkout within the operator's granted scope.
  It must preserve reference checkouts, credentials and evaluation inputs.
- Queue exclusivity covers jobs submitted to that shared jobq. Host-level
  contention outside jobq still needs operator coordination; a host contention
  guard is being added and is not claimed as an existing guarantee here.
- The operator freezes references through `manager.py:freeze_reference` and
  preserves contract files. The agent does not freeze or rewrite references;
  direct local-user file edits remain outside the host API guarantees.

## Evidence and the reliability illustration

`0.9^10 ≈ 34.9%` assumes ten independent mandatory steps, each with success
probability 0.9, and no retry. This is conditional arithmetic, not a measured
rate. **We claim no reliability number.**

The execution evidence is the actual recovery recorded in Run 5. The operator
fills these identifiers from the run records; placeholders are not run results:

- Task: `<run5:task_id>`; original failure evidence: `<run5:failure_evidence_id>`.
- Revised decision: `<run5:decision_rev>`; revised plan: `<run5:graph_rev>`.
- Recovery attempt: `<run5:recovery_attempt_id>`; assessment: `<run5:evaluation_id>`.
- Tool receipt/transcript: `<run5:receipt_id>` / `<run5:transcript_ref>`.
