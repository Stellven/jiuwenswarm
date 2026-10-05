# An experimental plan is accepted or rejected

## Starting item

A developer selects a pinned isolated_experiment feature profile allowing Leader capability planning. Its task is a validated research_brief; its library snapshot exposes admitted capabilities, exact ports, versions, effects and bounds. Production keeps the fixed plan and never invokes this model planner.

`cc/experiments/entry.py` validates track/profile/access first. `cc/planning/service.py` uses `cc/adapters/leader.py` for native Leader identity and the protected model bridge for a single gpt-6.1-sol proposal. The planner is an orchestration service with no execution or activation authority. Entry allocates the real experimental run identity and supervisor commits planning_reserved with task/library/config/policy pins before granting a planning-scope bridge descriptor; a frozen Binding is not fabricated. Each turn reserves durable quota before forwarding.

## A concrete bad wire

The proposal connects `search.idea_set` to Hypothesis's `opportunity_card` input. Both are JSON-shaped payloads, but their canonical types differ. Merely generating syntactically valid JSON does not make this plan executable.

| Order | Connection | Expected result |
|---|---|---|
| 1 | Experimental entry → propose(task_ref, library_snapshot_ref, experiment_config_ref, request_id) | Raw turn and typed PlanProposal committed |
| 2 | Entry → `cc/planning/validate.py` validate | Resolve plan_ref to the complete planner_proposal Artifact, cross-check its task/library/config pins, selections, requirement-to-output criteria and budget, then compare source/output types |
| 3 | Validator → supervisor store | INVALID with TYPE_MISMATCH findings and exact input refs; no validated_plan_ref |
| 4 | Entry → local clarification/review | Return findings; zero runner dispatches and no live plan |
| 5 | Human explicitly requests a new proposal | Fresh request identity, prior rejected evidence preserved; no autonomous repair loop |

Cycle, missing launcher input, unreachable objective, unadmitted version, missing Gate, permission or budget excess gives the same no-dispatch boundary with its applicable finding. A failed validation save also cannot authorize freeze.

## A workable plan and immutable dispatch

A structurally valid proposal can use the [fixed plan](../m1/pipeline.md) as its fixture: Search's idea_set and Brief enter Screening; Screening's card plus Brief/intake enter Hypothesis. Validator also checks objective-to-final-output criteria, catalogue closure and bounds. It proves structural workability, not research success.

Only a committed VALID result matching all exact inputs allows `cc/freeze.py` to publish Bindings. If an active alias changes after validation, freeze uses the reviewed snapshot's exact version or denies a revocation; it never substitutes the new alias. Governed dispatch uses the normal runner/Gate/store contracts. A failed step halts; the planner cannot rewire the running graph.

## Gate ablation follows a different recorded authority

In a separately preregistered approved component-ablation profile, an omitted Gate produces NOT_RUN experimental_gate_evidence with null Verification. Partial checks carry the real partial Verification and skipped IDs. `cc/experiments/entry.py` commits experimental_advance only after exact work Observation/study/profile/evidence checks. Failed evidence/advance writes leave the successor stopped.

This is not a production release or a synthetic PASS. Export retains the deviation, absent release and actual evidence. Disabling a required producer such as Screening while retaining Hypothesis is rejected; no card is invented to bridge the gap. Schema/capture/auth/confinement/store-integrity controls cannot be ablated.

The [planner](../system/planner.md), [track owner](../system/experiments.md) and [service schemas](../contracts/services-v1.schema.json) define these interfaces. Dynamic compiler, routing and native Code Mode remain separately allowlisted adapters; unavailable permission/capture integration stops that experiment.
