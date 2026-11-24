# Node contracts

A node contract says what one step of building an inference engine takes, what it produces and how each output is checked. The task contract carries its node contracts, a planner orders them into a task graph, and the factory works them one node at a time. See [INTEGRATION.md](INTEGRATION.md) for where this sits.

- **Format:** `factory.node-contracts/1`, schema `jiuwenswarm/factory/schemas/node-contract-1.schema.json`.
- **Code:** `jiuwenswarm/factory/node_contract.py`.
- **Where it lives:** in a format-2 task contract under `extensions["factory.node-contracts"]`, so the contract format does not change.
- **Field names** follow the M1 Node Execution Contract (design package `reference/field-catalog.md`) wherever the meaning is the same.

## One node

```json
{"node_id": "integrate_cache", "kind": "integrate",
 "objective": "Add the expert weight cache to the owned checkout by following its builder capsule, off by default.",
 "requirement_ids": ["C3", "gate_unset_parity", "gate_set_activation"],
 "predecessors": ["inspect_engine"],
 "inputs": [{"name": "engine_map", "from": "inspect_engine.engine_map"}],
 "outputs": [{"name": "change", "kind": "diff", "criteria": [
   "With its switch unset, the engine behaves exactly like stock: no new work, no changed output.",
   "With its switch set, it prints the activation markers the method names."]}],
 "evidence_obligations": ["captured_input_and_output", "mandatory_checks", "semantic_assessment"],
 "node_limits": {"turns": 40, "build_attempts": 0},
 "authority_ceiling": {"effects": ["workspace.read", "workspace.write", "process.exec"], "workspace": "write"},
 "work": {"helpful_ccs": ["engine.build_expert_weight_cache", "factory.integration_skill", "factory.source_workbench"],
          "capability": "engine.build_expert_weight_cache.verify"},
 "verifiers": [{"output": "change", "verifier": "engine.build_expert_weight_cache.verify",
                "stage": "native CC execution", "review": true}],
 "hands_to": "combine"}
```

| Field | Meaning |
|---|---|
| `node_id`, `kind`, `objective` | The step, in plain words. `kind` is a task graph kind. `deliver` is the step that hands the engine to the lab manager |
| `requirement_ids` | Contract arms, checks and metrics this step serves |
| `predecessors` | Steps that must be done first. Every step an input comes from must be listed |
| `inputs[].from` | Where an input comes from: `<node>.<output>` of a predecessor, `contract:<input>`, or `task:source`, `task:objective` or `task:target` |
| `outputs[]` | What the step owes. `kind` is `diff`, `source_bundle`, `image`, `lab_request` or `evidence`. `criteria` are the sentences the reviewer judges against |
| `evidence_obligations` | The M1 evidence names the step's checks must cover |
| `node_limits` | `build_attempts` and `gpu_launches` are enforced: jobs that name the node are refused past them. `turns` and `time_s` are advice; the task budget enforces the totals |
| `authority_ceiling` | The most the step may use; the task's grants still apply |
| `work.helpful_ccs` | Capsules whose methods help, both for the worker and for the reviewer. They are advice, not orders |
| `verifiers[]` | One per output, like M1's verifier subnode per output. `verifier` is a capsule capability that checks a `diff` up to `stage`. `review` asks for an independent reviewer of a `diff` or `evidence` output |
| `hands_to` | The next step, or `lab_manager` for the deliver step |

## Rules `node_contract.problems()` enforces

- **Unique names:** node ids are unique, and within a node, input and output names are unique.
- **Order:** the graph is acyclic, and every predecessor exists.
- **Inputs:** every `<node>.<output>` input names an existing output of a predecessor, and every `contract:` input exists in the contract.
- **Verifiers:**
  - each required output has a verifier, at most one per output;
  - a verifier names a real output;
  - a `stage` needs a verifier capability;
  - capsule verifiers check only `diff` outputs;
  - reviews read only `diff` and `evidence` outputs.
- **Requirements:** requirement ids name contract arms, checks or metrics.
- **Hand-offs:** `hands_to` names a node that lists this one as a predecessor. There is exactly one leaf, the `deliver` node; it hands to `lab_manager` and owes a required `lab_request`.

## The Spark contract

`contracts/star-deepseek-v2.json` carries nine node contracts:

1. `inspect_engine`
2. five `integrate_<builder>` steps, one per builder capsule; each uses that builder's verifier with review
3. `combine`, a review-only step that needs no capsule
4. `build_candidate`, which owes source bundles for C1 to C5 and D, and optionally an image
5. `deliver_to_lab`, whose lab request must cover every arm, check and metric of the contract

## From an M1 run plan

`run_plan_adapter.from_run_plan()` maps an M1 frozen `run_plan` onto node contracts:

- **Carried over:** nodes, objectives, predecessors, ports, the CC as a helpful capsule, the time limit, and one reviewed verifier per output.
- **Not carried over:** check pins, model routing and authority do not fit this format.
- **The one change needed:** a research plan ends in a Delivery report, not a lab hand-off. Add a deliver node before the factory can run it.
