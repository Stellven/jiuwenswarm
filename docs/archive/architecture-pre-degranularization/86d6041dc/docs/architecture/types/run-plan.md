---
type: payload-type
id: cc.type.run_plan
version: 1
status: draft
tags: [types, m1, control]
---

> **Draft: reopened for the frozen October 2 scope and shared verifier.**

# `run_plan`: which nodes run, in what order, fed by what · version 1

The control flow of one run, as data. It lists the steps in order. For each step it names the work capsule, the gate capsule that checks it, and where each input comes from. Control flow lives here and nowhere else: not in a script, a prompt or a host ([nodes](../system/nodes.md)).

**Made by** the launcher for the fixed production plan, or the orchestration planner service for an isolated experimental plan. The planner is not a capsule. Both plans are validated and completely frozen before dispatch; no mid-run segment installation or live replanning occurs in M1. **Read by** freeze and the generic Swarmflow script. Exact type-version bindings follow [Kubeflow component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/).

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `steps` | `list<object>` | req | checked |  | At least one. The steps in the order they run. M1 runs them one after another |
| `steps[].step_id` | `id` | req | checked |  | Unique within the plan. It becomes the Binding's `step_id` and the Swarmflow `label`. Example: `intent` |
| `steps[].capsule_name` | `string` | req | checked |  | The work capsule's `identity.name`. Freeze resolves the exact admitted version in the pinned library snapshot, checks current revocation, and never substitutes a changed active alias. Example: `research.compile_brief` |
| `steps[].gate_capsule_name` | `string` | req | checked |  | Shared independent verifier capability `research.verifier`; freeze pins its exact declaration hash |
| `steps[].gate_profile_ref` | `object` | req | checked |  | Closed ProfileRef `{kind: gate, id, sha256}` selecting this stage's independently authored checks and rubrics |
| `steps[].gate_profile_ref.kind` | `enum(gate)` | req | checked |  | Profile discriminator |
| `steps[].gate_profile_ref.id` | `id` | req | checked |  | Policy-local stage profile name |
| `steps[].gate_profile_ref.sha256` | `sha256` | req | checked |  | Complete immutable profile hash |
| `library_snapshot_sha256` | `sha256` | req | checked |  | Complete immutable admitted library snapshot used to resolve all capabilities and dependencies |
| `track` | `enum(production, offline_rsi, isolated_experiment)` | req | checked |  | Production uses the fixed approved plan; offline RSI remains a separate bounded controller; experiments never count as production acceptance |
| `steps[].inputs` | `map<string, string>` | req | checked |  | Input port name to its source: `launcher.<name>` for a value the launcher recorded, or `<step_id>.<output port>` for an earlier step's output. An optional port may be left out. Example: `{"intake": "launcher.intake"}` |
| `steps[].step_checks` | `list<Check>` | opt | checked |  | Criteria this workflow adds for this step, each a full [Check](../capsule/fields.md#checks-one-runnable-test-each). Freeze copies them into the Binding's `step_checks`. Deterministic and reference ones run in Tier 1; judged ones go to the gate capsule in Tier 2. Policy `every_step_gated` requires at least one judged check per step, here or among the work capsule's own checks |
| `steps[].judge_inputs` | `list<string>` | opt | checked |  | What the gate's judge is shown of the step's inputs, for its `inputs_and_outputs` criteria: each entry a port name, or `<port>.<field>` for one field of it. Absent: every input in full. Example: `["intake.prompt"]` |
| `launcher_inputs` | `map<string, reg(port_type)>` | req | checked |  | Every `launcher.<name>` source, with its port type, so freeze can check each wire's type. Example: `{"intake": "intake"}` |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.run_plan_wiring_resolves.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/run_plan.py:run_plan_wiring_resolves` | muk | step ids are unique; every source is `launcher.<name>` with `<name>` in `launcher_inputs`, or `<step_id>.<port>` naming a step that comes **earlier** in `steps`. So the plan is acyclic by construction |

Whether each wire joins two ports of the same type needs the Declarations, so freeze checks it ([toolchain](../capsule/toolchain.md#m03-freeze-the-binding-writer)).

## Example

The first two M1 steps. The full M1 plan is on [the M1 pipeline](../m1/pipeline.md).

```json
{
  "steps": [
    {"step_id": "requirement", "capsule_name": "research.compile_brief", "gate_capsule_name": "research.verifier",
     "gate_profile_ref": {"kind": "gate", "id": "brief", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
     "inputs": {"intake": "launcher.intake", "source_text": "launcher.source_text"}}
  ],
  "launcher_inputs": {"intake": "intake", "source_text": "source_text"},
  "library_snapshot_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "track": "production"
}
```
