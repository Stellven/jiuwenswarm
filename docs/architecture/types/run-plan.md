---
type: payload-type
id: cc.type.run_plan
version: 1
status: draft
tags: [types, m1, control]
prd: [4.8.2, 4.6.2]
level: detail
---

# `run_plan`: which nodes run, in what order, fed by what · version 1

PRD: 4.8.2, 4.6.2

The control flow of one run, as data. A run has two plans: a **[fixed prep plan](../system/lifecycle.md#term-prep-plan)** (intent CC, then requirement CC, each with its gate) [frozen](../system/lifecycle.md#term-freeze) at launch, and a **planned DAG** proposed by the planner after requirements are accepted, then validated, bound and frozen in the same run ([planner](../system/planner.md), [lifecycle](../system/lifecycle.md)). Both use this type. It lists the [steps](../system/nodes.md#term-step) in order. For each step it names the [work capsule](../capabilities/README.md#term-work-capsule), the gate [capsule](../capsule/capsule.md#term-capability-capsule) that [checks](../capsule/fields.md#term-check) it, and where each input comes from. Control flow lives here and nowhere else: not in a script, a prompt or a host ([nodes](../system/nodes.md)).

**Made by** intake/launch for the fixed prep plan, and by the planner service (an ordinary service, not a capsule) for the planned DAG; the first planner emits the fixed research chain template ([capabilities](../capabilities/README.md)). Each plan is validated and frozen before its [nodes](../system/nodes.md#term-node) dispatch; no live replanning after a failure occurs in M1. A plan carries `phase` (`prep` or `planned`); a planned plan declares the prep outputs it reads in `prep_inputs`. **Read by** freeze and the generic [Swarmflow](../system/integration.md#term-swarmflow) script. Exact type-version bindings follow [Kubeflow component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-run-plan"></a>**run_plan** (also: run plan) | The control flow of one run as data: the steps in order, each naming its work capsule, its gate capsule and where each input comes from. A run has two plans, and control flow lives in the plan and nowhere else. |
| <a id="term-phase"></a>**phase** | Which of a run's two plans a `run_plan` is: `prep` or `planned`. Each plan is validated and frozen before its steps dispatch. |
| <a id="term-prep-plan"></a>**prep plan** (also: fixed prep plan) | The fixed first plan, frozen at launch: the intent step, then the requirement step, each with its Gate. Its accepted outputs feed the planned plan. |
| <a id="term-planned-plan"></a>**planned plan** (also: planned DAG) | The second plan, proposed by the planner after requirements are accepted, then validated, bound and frozen in the same run. It declares the prep outputs it reads in `prep_inputs`; M1 allows no live replanning after a failure. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `phase` | `enum(prep, planned)` | req | checked |  | `prep`: the fixed prep plan (intent step, then requirement step), frozen at launch. `planned`: the planner's DAG, frozen after the requirement [Gate](../verification.md#term-gate) verdict |
| `prep_inputs` | `map<string, reg(port_type)>` | opt | checked |  | [Planned plan](../system/lifecycle.md#term-planned-plan) only: every `prep.<step_id>.<port>` source with its port type, so freeze can check each wire. Absent in a prep plan. Example: `{"requirement.research_brief": "research_brief"}` |
| `steps` | `list<object>` | req | checked |  | At least one. The steps in the order they run. M1 [runs](../system/lifecycle.md#term-run) them one after another |
| `steps[].step_id` | `id` | req | checked |  | Unique within the plan. It becomes the [Binding](../schemas/binding.md#term-binding)'s `step_id` and the Swarmflow `label`. Example: `intent` |
| `steps[].capsule_name` | `string` | req | checked |  | The work capsule's `identity.name`. Freeze resolves the exact admitted version in the pinned [library snapshot](../capsule/library.md#term-library-snapshot), checks current revocation, and never substitutes a changed [active alias](../capsule/library.md#term-alias). Example: `research.compile_brief` |
| `steps[].gate_capsule_name` | `string` | req | checked |  | Shared independent verifier capability `research.verifier`; freeze pins its exact declaration hash |
| `steps[].gate_profile_ref` | `object` | req | checked |  | Closed [ProfileRef](../schemas/profiles.md#term-profileref) `{kind: gate, id, sha256}` selecting this stage's independently authored checks and rubrics |
| `steps[].gate_profile_ref.kind` | `enum(gate)` | req | checked |  | Profile discriminator |
| `steps[].gate_profile_ref.id` | `id` | req | checked |  | Policy-local stage profile name |
| `steps[].gate_profile_ref.sha256` | `sha256` | req | checked |  | Complete immutable profile hash |
| `library_snapshot_sha256` | `sha256` | req | checked |  | Complete immutable admitted library snapshot used to resolve all capabilities and dependencies |
| `track` | `enum(production, offline_rsi, isolated_experiment)` | req | checked |  | Production uses the fixed approved plan; offline [RSI](../rsi.md#term-rsi) remains a separate bounded controller; experiments never count as production acceptance |
| `steps[].inputs` | `map<string, string>` | req | checked |  | Input port name to its source: `launcher.<name>` for a value the launcher recorded, or `<step_id>.<output port>` for an earlier step's output in the same plan, or (planned plan only) `prep.<step_id>.<output port>` for an output already [released](../system/lifecycle.md#term-release) by the prep plan. An optional port may be left out. Example: `{"intake": "launcher.intake"}` |
| `steps[].step_checks` | `list<Check>` | opt | checked |  | Criteria this workflow adds for this step, each a full [Check](../capsule/fields.md#checks-one-runnable-test-each). Freeze copies them into the Binding's `step_checks`. Deterministic and reference ones run in [Tier 1](../verification.md#term-tier-1); judged ones go to the gate capsule in [Tier 2](../verification.md#term-tier-2). Policy `every_step_gated` requires at least one judged check per step, here or among the work capsule's own checks |
| `steps[].judge_inputs` | `list<string>` | opt | checked |  | What the gate's judge is shown of the step's inputs, for its `inputs_and_outputs` criteria: each entry a port name, or `<port>.<field>` for one field of it. Absent: every input in full. Example: `["intake.prompt"]` |
| `launcher_inputs` | `map<string, reg(port_type)>` | req | checked |  | Every `launcher.<name>` source, with its port type, so freeze can check each wire's type. Example: `{"intake": "intake"}` |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |
| `check.run_plan_wiring_resolves.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/run_plan.py:run_plan_wiring_resolves` | cc-team | step ids are unique; every source is `launcher.<name>` with `<name>` in `launcher_inputs`, or `prep.<step_id>.<port>` with that key in `prep_inputs` (planned plans only), or `<step_id>.<port>` naming a step that comes **earlier** in `steps`. So the plan is acyclic by construction |

Whether each wire joins two [ports](../capsule/fields.md#term-port) of the same type needs the [Declarations](../capsule/fields.md#term-declaration), so freeze checks it ([toolchain](../capsule/toolchain.md#m03-freeze-the-binding-writer)).

## Examples

The intent step of the fixed prep plan. Full plans: [prep.plan.json](../capabilities/prep.plan.json) (intent and requirement steps, frozen at launch) and [research-template.plan.json](../capabilities/research-template.plan.json) (planned DAG, frozen after requirements). See [capabilities](../capabilities/README.md).

```json
{
  "phase": "prep",
  "track": "production",
  "library_snapshot_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "launcher_inputs": {
    "intake": "intake",
    "source_text": "source_text"
  },
  "steps": [
    {
      "step_id": "intent",
      "capsule_name": "research.compile_intent",
      "gate_capsule_name": "research.verifier",
      "gate_profile_ref": {
        "kind": "gate",
        "id": "research.accept_intent.v1",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      },
      "inputs": {
        "source_text": "launcher.source_text"
      },
      "judge_inputs": [
        "source_text"
      ]
    }
  ]
}
```
