# Planner CC (`research.planner`)

`Tier 3 · Part of: [Reference](../README.md)`

Part of the [capsule build references](README.md).

**Summary for reviewers**

- The Planner reads the accepted Research Brief, a frozen list of admitted CC versions, a list of available resources and the policy limits. It returns one JSON graph (`plan_proposal`).
- Each graph node names exactly one CC version, its typed inputs and outputs, its budget and which Brief requirements or deliverables it covers.
- The Planner proposes only. A protected binder checks the graph, copies the mandatory check bundle of each CC into the frozen run plan and freezes it. The Planner cannot add, drop or weaken a mandatory check.
- An infeasible or rejected plan halts the planned run and records a `plan_infeasible` outcome. The host then starts a new, linked Intention Compiler attempt that carries the Brief ref and the reasons (PRD 4.8.3, decisions D4 and [D30](../../method/decisions.md#d30)). A request gets at most two plan attempts: the original and one linked new attempt (depth 1 and 2). Nothing is repaired inside the same run.
- The semantic verifier sees only this declaration and the proposal. It checks that the graph is consistent with itself. The host does every check that needs the Brief, the library or the policy.
- The plan source, a static template or the Planner, is the `plan_source` run setting chosen before the run ([D39](../../method/decisions.md#d39)). A hand-authored static template reaches the same [run plan](../run-plan.md) through the same binder.

## Purpose and place in the run

The Planner takes an accepted `research_brief` and turns it into a bounded graph of downstream research CCs. The binder then validates, binds and freezes the graph into a [run plan](../run-plan.md). A failed or rejected proposal halts the planned run and records a [`plan_infeasible` outcome](../run-plan.md#plan-outcome). There is no silent repair of the proposal inside the same run and no silent switch to the static template (decision D4).

## Declaration

[planner_capsule.json](../examples/planner_capsule.json) validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name and kind | `research.planner`, kind `agent` |
| Effect class | `read_only`. It writes no file except its own output and uses the model bridge |
| Network | none |
| Budget per call | 120 s wall time, 1 invocation, 0 tool calls |
| Model needs | text only, no tool calling |
| Output checks | the twelve host checks named in the check bundle table below |

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
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.-]{0,63}$` | Immutable ID of this proposal. Chosen by the Planner. A label only. It grants nothing. |
| `brief_ref` | `Ref` | yes | the accepted Brief given to the Planner | Accepted governing Research Brief. The Planner copies the Ref of its `brief` input. Check `plan_proposal_schema` rejects any other Ref. |
| `library_snapshot_ref` | `Ref` | yes | the snapshot given to the Planner | Pinned list of eligible CC versions the nodes were chosen from. Copied from the `library_snapshot` input. Check `plan_proposal_schema` rejects any other Ref. |
| `resource_inventory_ref` | `Ref` | yes | the snapshot given to the Planner | Pinned list of supplied and observed resources. Copied from the `resource_inventory` input. Check `plan_proposal_schema` rejects any other Ref. |
| `policy_ref` | `Ref` | yes | the plan policy given to the Planner | Protected policy limits the plan was made under. Copied from the `plan_policy` input. The Planner cannot change a policy value. |
| `plan_source` | `string` | yes | exactly `planned` | Marks a Planner-made plan. A static template carries `static` instead. The user chooses the plan source before the run ([D39](../../method/decisions.md#d39)). The Planner does not choose it. |
| `nodes` | `PlanNode[]` | yes | 1 to 12 nodes (M1 ceiling, also limited by policy `max_nodes`) | The finite graph of nodes. Edges come from `predecessors` and future inputs. The Planner proposes it. The protected binder checks and freezes it. |
| `coverage` | `CoverageEntry[]` | yes | 1 to 60 entries, one entry per mandatory requirement and per deliverable of the Brief | Self-review map from each Brief item to the nodes that cover it. It is the exact inverse of the node tags. The Planner writes it. Check `brief_coverage` compares it with the node tags. |
| `topic_hints` | `string[]` | yes | 0 to 5 items, each 3 to 100 characters, no duplicates. The empty list is allowed | Optional topic phrases for the Search scope. The binder copies them into `search_scope.topic_hints`. Search may use or ignore them. They grant nothing. |
| `limits` | `Limits` | yes | time and calls at least the sum of node limits, memory at least the largest node limit, all at most the policy aggregate limits | Aggregate ceiling for the whole plan, in the units of the shared [Limits](../field-catalog.md#limits) type. Proposed by the Planner. The binder checks it against the node limits and the plan policy aggregate limits. |
| `notes` | `string` | yes | 0 to 1000 characters, the empty string is allowed only here | Short planner remark for human review. It is not an instruction and grants nothing. The verifier checks that it makes no authority claim (`no_authority_claims`). |



### Node fields

`PlanNode`, `PlanInput`, `FutureInput`, `PlanOutput` and `CoverageEntry` replace the old types of the same names. `PlannedSubnode` is retired. M1 runs one CC per node. The scheduler creates the verifier subnodes at dispatch, so a plan never lists them.

**PlanNode**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `node_id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, unique in the plan | Name of this node in the graph, for example `screening`. Never reused. The Planner chooses it. `predecessors`, `future.producer_node` and `coverage` refer to it by this exact string. |
| `cc` | `CcPin` | yes | must match one library entry with `selectable_by_planner` true | The one CC version this node runs. M1 binds one CC per node. The Planner copies name, version and digest from a library entry and invents none. |
| `objective` | `string` | yes | 1 to 300 characters | One plain sentence on what this node does for the run. Text for people. It grants nothing. |
| `requirement_ids` | `string[]` | yes | each an ID in the Brief `mandatory_requirements`, at most 40. A static template node may instead hold the one value `all_mandatory_requirements` ([selectors](../run-plan.md#selectors)) | Mandatory Brief requirements this node helps satisfy. These are tags. `coverage` must mirror them exactly. |
| `deliverable_ids` | `string[]` | yes | each an ID in the Brief `deliverables`, at most 20, `requirement_ids` and `deliverable_ids` together hold at least 1 item. A static template node may instead hold the one value `all_deliverables` | Brief deliverables this node produces or helps produce. These are tags. `coverage` must mirror them exactly. |
| `predecessors` | `string[]` | yes | node IDs, at most 11, includes every `future.producer_node` of this node, no self reference | Nodes that must be accepted before this node starts. Extra entries are ordering-only dependencies. |
| `inputs` | `PlanInput[]` | yes | at most 16 items, covers every required library input port | Typed bindings for the node inputs. The Planner names what each input binds to. It never writes a Ref. |
| `outputs` | `PlanOutput[]` | yes | 1 to 16 items, covers every required library output port | Typed outputs the node will produce. |
| `limits` | `Limits` | yes | each value at most the library `max_limits` | Time, model-call and memory ceiling for one attempt of this node, in the units of the shared [Limits](../field-catalog.md#limits) type. The Planner proposes it. The library `max_limits` of the chosen CC cap it. |
| `suggested_checks` | `string[]` | yes | at most 8 check IDs, each matching `^[a-z][a-z0-9_]{0,63}$` | Extra deterministic checks the Planner wants. The binder may adopt them. They never replace the mandatory bundle. An unknown ID is dropped and logged and does not fail the plan alone (`suggested_checks_known`). |

**PlanInput**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, unique in the node, an input port of the CC in the library entry | Consumer input port name. Copied from the library entry. Not a free label. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, equals the library input port type | Artifact type of the port. |
| `required` | `boolean` | yes | must be true when the library port is required | Whether the node needs this input. Copied from the library port. The Planner cannot mark a required library port optional. |
| `source_kind` | `string` | yes | enum `accepted_ref`, `future_output`, `host_record` | `accepted_ref` means an input that already exists when the run starts: the Brief, the bound `search_scope` or a supplied resource. `future_output` means the accepted output of an earlier node. `host_record` means a record the host supplies without a producing node: a pinned body file or a record built from the run's own accepted records. |
| `run_input_key` | `nullable-string` | yes | non-null exactly when `source_kind` is `accepted_ref` or `host_record`. For `accepted_ref`: `brief`, `search_scope` or a `resource_key` of the resource inventory. For `host_record`: `screening_rubric`, `build_receipt`, `gate_decision_index`, `screening_result`, `execution_receipt`, `provisioning_receipt`, `environment_lock` or `run_configuration` | Which run input or host record to bind. The Planner names the key and never writes a ref. Null for `future_output`. |
| `accepted_ref` | `nullable-Ref` | yes | null in every plan proposal and static template. In a run plan non-null when `source_kind` is `accepted_ref`, null otherwise | Exact bytes of the run input. Only the binder fills this field. The Planner must leave it null, and `plan_proposal_schema` rejects a proposal that sets it. A host record is bound at dispatch from the run's accepted records. |
| `future` | `nullable-FutureInput` | yes | non-null exactly when `source_kind` is `future_output` | Producer node, port and type of the future value. It binds to the gate-accepted output only, at dispatch. Null for the other two source kinds. |

**FutureInput**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `producer_node` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, an existing node ID other than the consumer | Node that will produce the value. It must also be in this node's `predecessors`, so the edge is explicit. |
| `port` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, a name in the producer node `outputs` | Output port of that node. It must be listed in that node's `outputs`. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, must equal the producer output `artifact_type` | Artifact type the consumer expects. A mismatch is an incompatible binding. |

**PlanOutput**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, unique in the node, an output port of the CC in the library entry | Producer output port name. Copied from the library entry. Not a free label. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, equals the library output port type | Artifact type of the port. |
| `required` | `boolean` | yes | must be true when the library port is required | Whether the node must produce this output. |

**CoverageEntry**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `item_id` | `string` | no | an ID in the Brief `mandatory_requirements`, `deliverables` or `evidence_obligations`. Set exactly when `item_kind` is set, and never together with `selector` | Brief item being covered. Copied from the Brief. The Planner invents no ID. Absent for a selector entry. |
| `item_kind` | `string` | no | enum `requirement`, `deliverable`, `evidence_obligation` | Whether the item is a mandatory requirement, a deliverable or an evidence obligation. An `evidence_obligation` entry names the nodes that produce the evidence. No node tag mirrors it, so it is outside the inverse rule. |
| `selector` | `string` | no | enum `all_mandatory_requirements`, `all_deliverables`, `all_evidence_obligations`. Valid only in a static template. Never set together with `item_id` | A rule that stands for every Brief item of one kind ([D47](../../method/decisions.md#d47)). The binder expands it into one concrete entry per Brief item before `brief_coverage` runs. A plan proposal never uses it. |
| `node_ids` | `string[]` | yes | 1 to 12 node IDs, each node must tag this item | Nodes that cover the item, or every item the selector stands for. The list is the exact inverse of the node tags. A node missing or extra here fails `brief_coverage`. |



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
7. Run an internal self-review before output. Re-read the Brief constraints and confirm that every mandatory requirement and every deliverable maps to at least one node. Confirm that the graph has no cycle, that it ends in exactly one Delivery leaf, that no required port is unbound and that no node lacks a coverage tag. Fix the graph or stop. Do not submit a known gap.
8. Fill `coverage` as the exact inverse of the node tags.
9. Never name a CC that is missing from the snapshot. If no listed CC can cover a requirement, output no graph. Reply with one text line that starts `INFEASIBLE:` and states what no CC can cover (at most 300 characters). The host records it as a `plan_infeasible` reason. Never invent a CC.
10. Never include code, commands, permissions, file paths or model choices. Model routing is not a planning matter.
11. Put at most five short topic phrases in `topic_hints`, or leave it empty. Never write search queries there.

The worker must not execute anything, read the live library or change a policy value.

## Deterministic check bundle

The host binder runs these checks on the exact output and on the pinned inputs. They may read the Brief, the library snapshot, the resource inventory and the policy. All twelve run. A failing check blocks the plan before dispatch.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `plan_proposal_schema` | Matches `plan-proposal:field-contract:3`: field types, enums, patterns, lengths, unique node IDs, node count at most `max_nodes`, `plan_source` is `planned`, no `accepted_ref` is set, `brief_ref`, `library_snapshot_ref`, `resource_inventory_ref` and `policy_ref` equal the refs given to the Planner. | reject |
| `brief_coverage` | Run after the binder has expanded the selectors of a static template ([D47](../../method/decisions.md#d47)). Every mandatory requirement and deliverable of the Brief has a `coverage` entry. Every node has at least one tag. `coverage` is the exact inverse of the node tags. Every tag is an ID in the Brief. A selector appears only in a static template. A plan proposal and a run plan never hold one. An `evidence_obligation` entry names an obligation of the Brief and existing nodes. | reject |
| `library_membership` | Every node `cc` matches exactly one library entry by name, version and `declaration_sha256`, and the entry has `selectable_by_planner` true. Unknown versions fail. | reject |
| `port_type_compatibility` | Every input and output name and type equals a port of the library entry. Required ports are present and not marked optional. Every future binding has the same `artifact_type` and `schema_ref` at the producer output and the consumer input. A host record key equals the port `artifact_type` of its input. | reject |
| `dependency_closure` | Every future binding names an existing other node that is in `predecessors` and lists that port in `outputs`. Every accepted-ref `run_input_key` is `brief`, `search_scope` or a key in the resource inventory. Every host-record key is one of the eight keys listed for `run_input_key`. Every required input is bound. | reject |
| `acyclicity` | The `predecessors` graph has a topological order. | reject |
| `delivery_leaf_coverage` | A leaf is a node that no other node lists in `predecessors`. The plan has exactly one leaf in M1. The leaf runs `research.delivery`. Its `deliverable_ids` hold every Brief deliverable. Exactly one of its ancestors runs `research.evaluation`. Every CC in the policy `required_stages` runs in exactly one node. Reason: M1 follows one opportunity, one hypothesis and one report template (PRD 3.4, 3.5, 3.9), and every DAG leaf is a Delivery node ([D28](../../method/decisions.md#d28)). | reject |
| `mandatory_check_bundle_present` | The library entry of every node has non-null `check_pins`, and the pinned bundle and profile exist in the protected registry. | reject |
| `effects_within_policy` | Each node `effect_class` is in `allowed_effect_classes`. A CC with a `network_mode` other than `none` is allowed only when `allow_network` is true. | reject |
| `resource_feasibility` | Every `resource_needs` entry of every chosen CC exists in the resource inventory, is available and meets `min_quantity`. | reject |
| `budget_ceilings` | Each node limit is at most the library `max_limits`. Plan time and calls are at least the node sums. Plan memory is at least the largest node value. The plan limits are at most the policy aggregate limits. | reject |
| `suggested_checks_known` | Every suggested check ID exists in the check registry. Unknown IDs are dropped from adoption and logged. They never fail the plan alone. | warn |

## Verifier criteria

The verifier receives the pinned Planner declaration and the exact `plan_proposal` bytes only. Every question below is answered from those two. It sees no Brief, library, policy or resource data, so it cannot tell whether the plan is the right plan. Under D20 this is reduced assurance. The host checks above carry the coverage and feasibility checks. This is the PRD §4.2 Tier 2 check of the Planner's output. It is not the autonomous peer review of the plan that PRD §4.8 excludes from M1.

| Criterion ID | Question | Blocking |
|---|---|---|
| `graph_self_consistent` | Does every node ID in a `predecessors` list or a future binding name a node in the `nodes` list, and does the listed `predecessors` graph have no cycle? | yes |
| `output_ports_named` | Does every future binding name a port that is listed in the `outputs` of its producer node, with the same `artifact_type`? | yes |
| `coverage_tags_present` | Does every node carry at least one requirement or deliverable ID? | yes |
| `coverage_map_consistent` | Is each `coverage` entry equal to the set of nodes whose tags include that item, with no node missing and none extra? | yes |
| `no_authority_claims` | Do `notes`, `objective` and `suggested_checks` avoid any statement that grants permission, waives or weakens a check, or gives a command or code? | yes |

## Gate rule

The gate accepts when all twelve host checks pass (`suggested_checks_known` may warn) and every criterion passes. It rejects on any failed check or criterion and records the failure. A rejection halts the planned run with a `plan_infeasible` outcome, because there is no automatic repair and no silent switch to the static template. The outcome starts a new linked Intention Compiler attempt (see [plan outcome](../run-plan.md#plan-outcome)). Acceptance of the proposal does not freeze the plan. The plan gate (the Planner node gate plus the binder checks) accepts the bound plan, its record is stored as `acceptance_ref`, and the binder then freezes the plan. See [run plan](../run-plan.md#run-plan).

## Failure outcomes

| Condition | Outcome | What is kept |
|---|---|---|
| Output is not valid JSON or fails `plan_proposal_schema` | reject, `plan_infeasible`, run halts before dispatch | raw output and check result |
| Any other host check fails | reject, `plan_infeasible`, run halts | proposal, check result, failing check ID |
| A verifier criterion fails | reject, `plan_infeasible`, run halts | proposal, assessment |
| No listed CC covers a mandatory requirement | the Planner replies `INFEASIBLE:`, `plan_infeasible`, run halts | report, no graph |
| Model or runtime failure | `failed`, run halts | partial evidence |
| Budget exhausted | `budget_exhausted`, run halts | partial evidence |

Every `plan_infeasible` outcome ends the run. The host records it and starts a new Intention Compiler attempt that carries the Brief ref and the reasons. The new attempt is new work with its own run. It is not a repair of the failed one. A request gets at most two plan attempts: the original and one linked new attempt (depth 1 and 2). After the second `plan_infeasible` outcome the host halts and writes an escalation record ([D30](../../method/decisions.md#d30)). A human may instead start a new run with `plan_source` `static` or with a changed Brief. Model or runtime failure and budget exhaustion are not plan infeasibility. They halt the run with their own outcome and start no new attempt.

## Examples

| File | Role | Rejected by |
|---|---|---|
| [planner_capsule.json](../examples/planner_capsule.json) | declaration | none |







Library, resource, policy, template and run plan examples are on the [run plan page](../run-plan.md#examples). The CC digests in the examples are synthetic. Digests for CCs other than the Planner follow whichever declaration files exist when the examples were made.

## Future seams

- Better planners (MCTS, search over candidate plans, learned planners) change only how a proposal is produced. The `plan_proposal` type, the binder and the run plan stay the same. A search-based planner may write several proposals and submit the best one. Every one is still checked by the same bundle.
- Automatic CC admission feeds the library snapshot. The Planner needs no change, because it only reads the snapshot.
- Composition later lets a node name a composite CC. The `cc` pin already carries name, version and declaration digest. A composite entry would appear in the library with its own ports and check pins. Nodes would not change shape.
- The RSI workbench may improve the Planner as a normal CC. It gets a new version in the library. Existing frozen runs keep their pins.
- Parallel nodes and replanning stay outside M1. The graph already allows branches, because edges come from `predecessors`.

## M1 placement

The CC page above does not depend on where the Planner runs. In M1 the rules below apply.

- The Planner runs after the Intention Compiler node has released the accepted Brief. In M1 the fixed static template is the default and the Planner is the second build step. The user chooses `plan_source` before the run ([D39](../../method/decisions.md#d39)).
- The Planner is not selectable by itself or by another Planner. `selectable_by_planner` is false in its own library entry, and the binder check `library_membership` rejects it.
- After a `plan_infeasible` outcome the host starts a new Intention Compiler attempt, linked to that outcome, which carries the Brief ref and the reasons (PRD 4.8.3).
- The protected binder, not the Planner, validates, binds and freezes the plan ([D42](../../method/decisions.md#d42)).
