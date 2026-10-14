# Planner CC (`research.planner`)

**Reading level: AI reference.** Part of the [capsule build references](README.md).

**Summary for reviewers**

- The Planner reads the accepted Research Brief, a frozen list of admitted CC versions, a list of available resources and the policy limits. It returns one JSON graph (`plan_proposal`).
- Each graph node names exactly one CC version, its typed inputs and outputs, its budget and which Brief requirements or deliverables it covers.
- The Planner proposes only. A protected binder checks the graph, copies the mandatory check bundle of each CC into the frozen run plan and freezes it. The Planner cannot add, drop or weaken a mandatory check.
- An infeasible or rejected plan halts the planned run and records a `plan_infeasible` outcome. The host then starts a new, linked Intention Compiler attempt that carries the Brief ref and the reasons (PRD 4.8.3, decision D4). Nothing is repaired inside the same run.
- The semantic verifier sees only this declaration and the proposal. It checks that the graph is consistent with itself. The host does every check that needs the Brief, the library or the policy.
- The Planner is optional in M1. A hand-authored static template reaches the same [run plan](../run-plan.md) through the same binder.

## Purpose and place in the run

The Planner runs after the Intention Compiler node has released an accepted `research_brief`. It turns the Brief into a bounded graph of downstream research CCs. The binder then validates, binds and freezes the graph into a [run plan](../run-plan.md). In M1 the fixed static template is the default and the Planner is the second build step. The Planner is not selectable by itself or by another Planner (`selectable_by_planner` is false in its own library entry). A failed or rejected proposal halts the planned run and records a [`plan_infeasible` outcome](../run-plan.md#plan-outcome). The host then starts a new Intention Compiler attempt, linked to that outcome, which carries the Brief ref and the reasons (PRD 4.8.3). There is no silent repair of the proposal inside the same run and no silent fallback to the static template (decision D4). A user selects the static mode before a run.

## Declaration

[planner_capsule.json](../examples/planner_capsule.json) validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name and kind | `research.planner`, kind `agent` |
| Effect class | `read_only`. It writes no file except its own output and uses the model bridge |
| Network | none |
| Budget per call | 120 s wall time, 1 invocation, 0 tool calls |
| Model needs | text only, no tool calling |
| Output checks | the eleven host checks named in the check bundle table below |

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `brief` | `research_brief` | Intention Compiler node (accepted) | yes | Source of requirement IDs, deliverable IDs, constraints and scope. Defines what the graph must cover. |
| `library_snapshot` | `library_snapshot` | protected library | yes | The only CC versions the Planner may name. See [library snapshot](../run-plan.md#library-snapshot). |
| `resource_inventory` | `resource_inventory` | host intake | yes | Which resources exist. See [resource inventory](../run-plan.md#resource-inventory). |
| `plan_policy` | `plan_policy` | protected configuration | yes | Node ceiling, allowed effect classes, network rule and aggregate limits. See [plan policy](../run-plan.md#plan-policy). |

## Output field contract

The output artifact is `plan_proposal` (`plan-proposal:field-contract:3`, file `plan_proposal.json`). It supersedes version 2 of the plan proposal contract. The proposal is data only. It grants no authority, no permission and no check relief.

### plan_proposal

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `3.0.0` | Format version 3.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.-]{0,63}$` | Immutable ID of this proposal. |
| `brief_ref` | `Ref` | yes | the accepted Brief given to the Planner | Accepted governing Research Brief. |
| `library_snapshot_ref` | `Ref` | yes | the snapshot given to the Planner | Pinned list of eligible CC versions the nodes were chosen from. |
| `resource_inventory_ref` | `Ref` | yes | the snapshot given to the Planner | Pinned list of supplied and observed resources. |
| `policy_ref` | `Ref` | yes | the plan policy given to the Planner | Protected policy limits the plan was made under. |
| `mode` | `string` | yes | exactly `planned` | Marks a Planner-made plan. A static template carries `static` instead. |
| `nodes` | `PlanNode[]` | yes | 1 to 12 nodes (M1 ceiling, also limited by policy `max_nodes`) | The finite graph of nodes. Edges come from `predecessors` and future inputs. |
| `coverage` | `CoverageEntry[]` | yes | 1 to 60 entries, one entry per mandatory requirement and per deliverable of the Brief | Self-review map from each Brief item to the nodes that cover it. It is the exact inverse of the node tags. |
| `topic_hints` | `string[]` | yes | 0 to 5 items, each 3 to 100 characters, no duplicates. The empty list is allowed | Optional topic phrases for the Search scope. The binder copies them into `search_scope.topic_hints`. Search may use or ignore them. They grant nothing. |
| `limits` | `Limits` | yes | time and calls at least the sum of node limits, memory at least the largest node limit, all at most the policy aggregate limits | Aggregate ceiling for the whole plan. |
| `notes` | `string` | yes | 0 to 1000 characters, the empty string is allowed only here | Short planner remark for human review. It is not an instruction and grants nothing. |

Examples: [valid](../examples/plan_proposal.json) · rejected by `acyclicity`: [plan_proposal_invalid_cycle](../examples/plan_proposal_invalid_cycle.json) · rejected by `port_type_compatibility`: [plan_proposal_invalid_port_type](../examples/plan_proposal_invalid_port_type.json) · rejected by `mandatory_check_bundle_present`: [plan_proposal_invalid_missing_check_bundle](../examples/plan_proposal_invalid_missing_check_bundle.json) (it points at the helper snapshot [library_snapshot_unbundled](../examples/library_snapshot_unbundled.json), where the benchmark CC has no admitted bundle)

### Node fields

`PlanNode`, `PlanInput`, `FutureInput`, `PlanOutput` and `CoverageEntry` replace the old types of the same names. `PlannedSubnode` is retired. M1 runs one CC per node. The binder creates the verifier assignments from the pinned check bundle, so a plan never lists verifier subnodes.

**PlanNode**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `node_id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, unique in the plan | Name of this node in the graph, for example `screening`. Never reused. |
| `cc` | `CcPin` | yes | must match one library entry with `selectable_by_planner` true | The one CC version this node runs. M1 binds one CC per node. |
| `objective` | `string` | yes | 1 to 300 characters | One plain sentence on what this node does for the run. |
| `requirement_ids` | `string[]` | yes | each an ID in the Brief `mandatory_requirements`, at most 40 | Mandatory Brief requirements this node helps satisfy. |
| `deliverable_ids` | `string[]` | yes | each an ID in the Brief `deliverables`, at most 20, `requirement_ids` and `deliverable_ids` together hold at least 1 item | Brief deliverables this node produces or helps produce. |
| `predecessors` | `string[]` | yes | node IDs, at most 11, includes every `future.producer_node` of this node, no self reference | Nodes that must be accepted before this node starts. Extra entries are ordering-only dependencies. |
| `inputs` | `PlanInput[]` | yes | at most 16 items, covers every required library input port | Typed bindings for the node inputs. |
| `outputs` | `PlanOutput[]` | yes | 1 to 16 items, covers every required library output port | Typed outputs the node will produce. |
| `limits` | `Limits` | yes | each value at most the library `max_limits` | Time, model-call and memory ceiling for one attempt of this node. |
| `suggested_checks` | `string[]` | yes | at most 8 check IDs, each matching `^[a-z][a-z0-9_]{0,63}$` | Extra deterministic checks the Planner wants. The binder may adopt them. They never replace the mandatory bundle. |

**PlanInput**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, unique in the node, an input port of the CC in the library entry | Consumer input port name. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, equals the library input port type | Artifact type of the port. |
| `required` | `boolean` | yes | must be true when the library port is required | Whether the node needs this input. The Planner cannot mark a required library port optional. |
| `source_kind` | `string` | yes | enum `accepted_ref`, `future_output`, `host_record` | `accepted_ref` means an input that already exists when the run starts: the Brief, the bound `search_scope` or a supplied resource. `future_output` means the accepted output of an earlier node. `host_record` means a record the host supplies without a producing node: a pinned body file or a record built from the run's own accepted records. |
| `run_input_key` | `nullable-string` | yes | non-null exactly when `source_kind` is `accepted_ref` or `host_record`. For `accepted_ref`: `brief`, `search_scope` or a `resource_key` of the resource inventory. For `host_record`: `screening_rubric`, `build_receipt`, `gate_decision_index`, `screening_result`, `execution_receipt`, `provisioning_receipt`, `environment_lock` or `run_configuration` | Which run input or host record to bind. The Planner names the key and never writes a ref. |
| `accepted_ref` | `nullable-Ref` | yes | null in every plan proposal and static template. In a run plan non-null when `source_kind` is `accepted_ref`, null otherwise | Exact bytes of the run input. Only the binder fills this field. A host record is bound at dispatch from the run's accepted records. |
| `future` | `nullable-FutureInput` | yes | non-null exactly when `source_kind` is `future_output` | Producer node, port and type of the future value. It binds to the gate-accepted output only, at dispatch. |

**FutureInput**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `producer_node` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, an existing node ID other than the consumer | Node that will produce the value. |
| `port` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, a name in the producer node `outputs` | Output port of that node. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, must equal the producer output `artifact_type` | Artifact type the consumer expects. A mismatch is an incompatible binding. |

**PlanOutput**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, unique in the node, an output port of the CC in the library entry | Producer output port name. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, equals the library output port type | Artifact type of the port. |
| `required` | `boolean` | yes | must be true when the library port is required | Whether the node must produce this output. |

**CoverageEntry**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `item_id` | `string` | yes | an ID in the Brief `mandatory_requirements` or `deliverables` | Brief item being covered. |
| `item_kind` | `string` | yes | enum | Whether the item is a mandatory requirement or a deliverable. |
| `node_ids` | `string[]` | yes | 1 to 12 node IDs, each node must tag this item | Nodes that cover the item. The list is the exact inverse of the node tags. |

Examples: [valid proposal with all node types](../examples/plan_proposal.json) · rejected by `port_type_compatibility`: [plan_proposal_invalid_port_type](../examples/plan_proposal_invalid_port_type.json) (the `evaluation_verdict` input of `delivery` is bound to a `benchmark_payload` output)

Cross-field rules:

- Edges are exactly the `predecessors` lists. Every future input must name a node that is in the same node's `predecessors`. A `host_record` input draws no edge. The record `build_receipt` is the host-written receipt of the accepted Builder attempt. The record `gate_decision_index` lists the node-scope gate decisions of the accepted attempts before the node. The records `screening_result`, `execution_receipt` and `provisioning_receipt` are the accepted outputs of the Screening and Benchmark nodes. The records `environment_lock` and `run_configuration` are the run's prepared lock and frozen configuration. The node that takes `build_receipt`, `gate_decision_index`, `screening_result`, `execution_receipt` or `provisioning_receipt` must list the producing nodes in `predecessors`. The record `screening_rubric` is the rubric pinned in the CC body.
- A producer and a consumer are port-compatible when `artifact_type` is equal in the future binding, in the consumer input and in the producer output. The `schema_ref` of the two library ports must also be equal.
- The union of `requirement_ids` and `deliverable_ids` of a node has at least one item. Every mandatory Brief requirement and every Brief deliverable is covered by at least one node.
- Node IDs are not reused and are stable names, not numbers that change with order.

## Producer obligations

The worker must:

1. Choose CC versions only from the `library_snapshot` entries with `selectable_by_planner` true. Copy `cc_name`, `cc_version` and `declaration_sha256` exactly.
2. Declare every required input and output port of each chosen CC, using the library port names and types.
3. Bind every input to a run input key (`brief`, `search_scope` or a resource key), to the future output of an earlier node, or to a host record key. Never write an `accepted_ref`.
4. Keep every node limit at or under the library `max_limits` and the plan limit at or under the policy aggregate limits.
5. Keep the node count at or under the policy `max_nodes`.
6. Suggest extra checks only as names in `suggested_checks`. Never claim to add, drop, weaken or waive a check.
7. Run an internal self-review before output. Re-read the Brief constraints and confirm that every mandatory requirement and every deliverable maps to at least one node. Confirm that the graph has no cycle, that no required port is unbound and that no node lacks a coverage tag. Fix the graph or stop. Do not submit a known gap.
8. Fill `coverage` as the exact inverse of the node tags.
9. Never name a CC that is missing from the snapshot. If no listed CC can cover a requirement, output no graph. Reply with one text line that starts `INFEASIBLE:` and states what no CC can cover (at most 300 characters). The host records it as a `plan_infeasible` reason. Never invent a CC.
10. Never include code, commands, permissions, file paths or model choices. Model routing is not a planning matter.
11. Put at most five short topic phrases in `topic_hints`, or leave it empty. Never write search queries there.

The worker must not execute anything, read the live library or change a policy value.

## Deterministic check bundle

The host binder runs these checks on the exact output and on the pinned inputs. They may read the Brief, the library snapshot, the resource inventory and the policy. All eleven run. A failing check blocks the plan before dispatch.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `plan_proposal_schema` | Matches `plan-proposal:field-contract:3`: field types, enums, patterns, lengths, unique node IDs, node count at most `max_nodes`, `mode` is `planned`, no `accepted_ref` is set, `brief_ref`, `library_snapshot_ref`, `resource_inventory_ref` and `policy_ref` equal the refs given to the Planner. | reject |
| `brief_coverage` | Every mandatory requirement and deliverable of the Brief has a `coverage` entry. Every node has at least one tag. `coverage` is the exact inverse of the node tags. Every tag is an ID in the Brief. | reject |
| `library_membership` | Every node `cc` matches exactly one library entry by name, version and `declaration_sha256`, and the entry has `selectable_by_planner` true. Unknown versions fail. | reject |
| `port_type_compatibility` | Every input and output name and type equals a port of the library entry. Required ports are present and not marked optional. Every future binding has the same `artifact_type` and `schema_ref` at the producer output and the consumer input. A host record key equals the port `artifact_type` of its input. | reject |
| `dependency_closure` | Every future binding names an existing other node that is in `predecessors` and lists that port in `outputs`. Every accepted-ref `run_input_key` is `brief`, `search_scope` or a key in the resource inventory. Every host-record key is one of the eight keys listed for `run_input_key`. Every required input is bound. | reject |
| `acyclicity` | The `predecessors` graph has a topological order. | reject |
| `mandatory_check_bundle_present` | The library entry of every node has non-null `check_pins`, and the pinned bundle and profile exist in the protected registry. | reject |
| `effects_within_policy` | Each node `effect_class` is in `allowed_effect_classes`. A CC with a `network_mode` other than `none` is allowed only when `allow_network` is true. | reject |
| `resource_feasibility` | Every `resource_needs` entry of every chosen CC exists in the resource inventory, is available and meets `min_quantity`. | reject |
| `budget_ceilings` | Each node limit is at most the library `max_limits`. Plan time and calls are at least the node sums. Plan memory is at least the largest node value. The plan limits are at most the policy aggregate limits. | reject |
| `suggested_checks_known` | Every suggested check ID exists in the check registry. Unknown IDs are dropped from adoption and logged. They never fail the plan alone. | warn |

## Verifier criteria

The verifier receives the pinned Planner declaration and the exact `plan_proposal` bytes only. Every question below is answered from those two. It sees no Brief, library, policy or resource data, so it cannot tell whether the plan is the right plan. Under D20 this is reduced assurance. The host checks above carry the coverage and feasibility checks.

| Criterion ID | Question | Blocking |
|---|---|---|
| `graph_self_consistent` | Does every node ID in a `predecessors` list or a future binding name a node in the `nodes` list, and does the listed `predecessors` graph have no cycle? | yes |
| `output_ports_named` | Does every future binding name a port that is listed in the `outputs` of its producer node, with the same `artifact_type`? | yes |
| `coverage_tags_present` | Does every node carry at least one requirement or deliverable ID? | yes |
| `coverage_map_consistent` | Is each `coverage` entry equal to the set of nodes whose tags include that item, with no node missing and none extra? | yes |
| `no_authority_claims` | Do `notes`, `objective` and `suggested_checks` avoid any statement that grants permission, waives or weakens a check, or gives a command or code? | yes |

## Gate rule

The gate accepts when all eleven host checks pass (`suggested_checks_known` may warn) and every criterion passes. It rejects on any failed check or criterion and records the failure. A rejection halts the planned run with a `plan_infeasible` outcome, because there is no automatic repair and no silent switch to the static template. The outcome starts a new linked Intention Compiler attempt (see [plan outcome](../run-plan.md#plan-outcome)). Acceptance of the proposal does not freeze the plan. The binder builds the run plan, and a second protected acceptance of that run plan freezes it. See [run plan](../run-plan.md#run-plan).

## Failure outcomes

| Condition | Outcome | What is kept |
|---|---|---|
| Output is not valid JSON or fails `plan_proposal_schema` | reject, `plan_infeasible`, run halts before dispatch | raw output and check result |
| Any other host check fails | reject, `plan_infeasible`, run halts | proposal, check result, failing check ID |
| A verifier criterion fails | reject, `plan_infeasible`, run halts | proposal, assessment |
| No listed CC covers a mandatory requirement | the Planner replies `INFEASIBLE:`, `plan_infeasible`, run halts | report, no graph |
| Model or runtime failure | `failed`, run halts | partial evidence |
| Budget exhausted | `budget_exhausted`, run halts | partial evidence |

Every `plan_infeasible` outcome ends the run. The host records it and starts a new Intention Compiler attempt that carries the Brief ref and the reasons. The new attempt is new work with its own run. It is not a repair of the failed one. A human may instead start a new run in static mode or with a changed Brief. Model or runtime failure and budget exhaustion are not plan infeasibility. They halt the run with their own outcome and start no new attempt.

## Examples

| File | Role | Rejected by |
|---|---|---|
| [planner_capsule.json](../examples/planner_capsule.json) | declaration | none |
| [plan_proposal.json](../examples/plan_proposal.json) | valid output (seven nodes, Search to Delivery) | none |
| [plan_proposal_invalid_cycle.json](../examples/plan_proposal_invalid_cycle.json) | `search` lists `delivery` as predecessor | `acyclicity` |
| [plan_proposal_invalid_port_type.json](../examples/plan_proposal_invalid_port_type.json) | `delivery.evaluation_verdict` bound to a `benchmark_payload` output | `port_type_compatibility` |
| [plan_proposal_invalid_missing_check_bundle.json](../examples/plan_proposal_invalid_missing_check_bundle.json) | names a CC version whose library entry has no check bundle | `mandatory_check_bundle_present` |

Library, resource, policy, template and run plan examples are on the [run plan page](../run-plan.md#examples). The CC digests in the examples are synthetic. Digests for CCs other than the Planner follow whichever declaration files exist when the examples were made.

## Future seams

- Better planners (MCTS, search over candidate plans, learned planners) change only how a proposal is produced. The `plan_proposal` type, the binder and the run plan stay the same. A search-based planner may write several proposals and submit the best one. Every one is still checked by the same bundle.
- Automatic CC admission feeds the library snapshot. The Planner needs no change, because it only reads the snapshot.
- Composition later lets a node name a composite CC. The `cc` pin already carries name, version and declaration digest. A composite entry would appear in the library with its own ports and check pins. Nodes would not change shape.
- Offline RSI may improve the Planner as a normal CC. It gets a new version in the library. Existing frozen runs keep their pins.
- Parallel nodes and replanning stay outside M1. The graph already allows branches, because edges come from `predecessors`.
