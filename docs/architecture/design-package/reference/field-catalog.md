# Named shared field contracts

`Tier 3 · Part of: [Reference](README.md)`

These charts specify required information and why consumers need it. [Machine inventory](field-contracts.json) mirrors the charts for documentation checks; it is not a requirement to implement private datatypes verbatim. Exact critical schemas take precedence where linked. Versions are per interface; closed shared fields and namespaced extensions prevent competing representations.

`Ref` identifies protected immutable content; implementation agreements preserve identity, version, scope and audience. Nullable values and empty lists mean explicit absence, not success. Fields below are required unless marked optional. Use readable substantive records; binary technical evidence is separate.

**Find fields:** [contract index](README.md#contract-index) · [planning](#planning-and-node-contracts) · [research](#research-artifacts) · [runtime/evidence](#manifest-and-runtime-records) · [clients/models](#client-and-model-boundaries) · [library](#library-records) · [derived records](derived-records.md) · [RSI](rsi-contracts.md) · [shared types](#shared-field-types)

## Planning and node contracts

### qualified-intake

Purpose: the one protected record of what the user submitted and what the platform qualified for use. The Intention Compiler reads nothing else from the user.

`qualified-intake:field-contract:2` (version 2.0.0: adds `upload_refs`) · Producer: protected intake. Consumers: Intent CC, Requirements CC.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version 2.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this intake record. |
| `request_ref` | `Ref` | yes | resolves to stored bytes that decode as strict UTF-8 | Exact original request text. The Intent CC cites spans in these bytes. |
| `source_refs` | `Ref[]` | yes | at most 64 items, unique, each decodes as strict UTF-8 | Extracted text of uploaded documents. Each equals the `text_sha256` of one `upload_refs` record. Empty when the user uploaded no document. |
| `offset_basis` | `string` | yes | exactly `Unicode code points` | How every source span counts offsets. |
| `resource_refs` | `Ref[]` | yes | at most 64 items, unique | Qualified uploaded assets, such as baseline code or a dataset snapshot. Each equals the `content_sha256` of one `upload_refs` record. |
| `upload_refs` | `Ref[]` | yes | at most 64 items, unique, each a [client-upload](#client-upload) record with `status` `uploaded` | The uploads this intake used. Intake qualifies only uploaded files, so every entry of `source_refs` and `resource_refs` traces to one of them. Empty when the user uploaded nothing. |
| `rejected_inputs` | `string[]` | yes | at most 64 items, each names the item and the reason | Items the user offered that intake rejected or skipped. A rejected item never appears in `resource_refs` or `source_refs`. |
| `user_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Authenticated product account that submitted the request. |
| `profile_ref` | `Ref` | yes | the protected local execution profile | Profile the run executes under. |
| `workspace_ref` | `Ref` | yes | the authorized run workspace | Workspace the run may write to. |
| `input_directory_ref` | `Ref` | yes | the qualified input directory record | Configured input directory, including an empty authorized default directory. |
| `prior_plan_outcome_ref` | `nullable-Ref` | no | null, or a plan outcome with `outcome` `plan_infeasible` and `next_stage` `intention_compiler` | Set only on an Intention Compiler attempt started by a `plan_infeasible` [plan outcome](run-plan.md#plan-outcome). Absent or null on a first attempt. |

**Invariants**

- Every file the intake used came from an upload. The Intent CC and the Requirements CC never see a file that is not in `upload_refs`.
- `source_refs` and `resource_refs` hold no duplicate ref, and no ref appears in both lists.
- Every span in a later `intent_ir` counts code points in the bytes of `request_ref` or of one `source_refs` entry.
- When `prior_plan_outcome_ref` is set, the Intent CC and the Requirements CC read its `reasons`. Each reason is resolved or carried forward as an Intent uncertainty or a Brief unresolved item. Neither CC drops a reason. This is a producer obligation: no host check compares reasons in M1.

**Producer obligations (protected intake)**

- Store the request bytes before any extraction or normalization. Hash those bytes.
- Decode text as strict UTF-8. Record undecodable input in `rejected_inputs` with the reason. Never repair it silently.
- Read user files only from [client-upload](#client-upload) records with `status` `uploaded`. Never read a path the user typed.
- Copy only qualified items into `resource_refs`. An item that fails a size, type or permission rule goes to `rejected_inputs`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `request_text_decodable` | `request_ref` and every `source_refs` entry resolve and decode as strict UTF-8 | reject the intake, no Intention Compiler dispatch |
| `intake_refs_unique` | No duplicate ref inside `source_refs` or `resource_refs`, and no ref in both | reject the intake |
| `prior_outcome_is_plan_infeasible` | A non-null `prior_plan_outcome_ref` resolves to a plan outcome with `outcome` `plan_infeasible` and `next_stage` `intention_compiler` | reject the intake |
| `intake_files_are_uploads` | Every `upload_refs` entry resolves to a client-upload record with `status` `uploaded`. Every `source_refs` hash equals a `text_sha256` of those records, and every `resource_refs` hash equals a `content_sha256` | reject the intake |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Request missing or undecodable | Intake rejected. The user sees the reason. No run starts | The original bytes and the rejection reason |
| An offered file is not an upload, or its upload was deleted | Intake rejected | The rejection reason. No file reaches a CC |
| A supplied file fails qualification | The file is listed in `rejected_inputs`. The run continues without it | The rejection entry. The file is not passed to any CC |
| A required source cannot be stored | Intake rejected | The rejection reason |

**Examples:** [valid](examples/qualified_intake.json)

**Minimum quality bar.** Every byte the Intent CC cites can be traced to one stored original, and every offered item is either qualified or listed with a reason.

### resource-snapshot

`resource-snapshot:field-contract:1` · protected resolver → Hypothesis, Builder, Benchmark.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `kind` | `string` | Plain-text resource kind, for example `supplied baseline`. No fixed set of values. Display and audit only: no check branches on it. |
| `origin` | `string` | Original locator the resolver captured from. It is provenance only. A mutable locator alone is not a reproducible identity: use `revision` and the file hashes. |
| `revision` | `string` | Immutable revision the resolver captured. A Hypothesis `baseline_identity.revision` must equal it. |
| `files` | `NamedFile[]` | Captured file contents, each a `NamedFile` with an exact hash. Consumers read these bytes, not `origin`. |
| `access` | `string` | Permitted use of the resource, written as text, for example `read-only experiment`. A consumer must not use the resource outside it. |
| `license` | `string` | Known license name, or the explicit word unknown. Never left empty. |
| `availability` | `string` | `available` or `unavailable`. Unavailable mandatory data stops the node that needs it. |
| `environment_ref` | `nullable-Ref` | Prepared environment lock that is compatible with this resource ([environment-lock](#environment-lock)). Null means no environment was prepared for it. |

**Invalid/missing behavior:** Unavailable mandatory data blocks; mutable locator alone is not a reproducible identity.

### environment-lock

Purpose: the exact, reviewed software environment that Builder packages against and the provisioner installs. Nothing is resolved at run time.

`environment-lock:field-contract:1` (version 1.0.0) · Producer: protected environment preparation. Consumers: Hypothesis, Builder, provisioner.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this lock. |
| `platform` | `string` | yes | 1 to 200 characters | Exact supported environment, for example interpreter, version and operating system family. |
| `requirements_ref` | `Ref` | yes | resolves to UTF-8 text. Every non-empty line that is not a `#` comment has the form `name==version` | Complete pinned declaration of direct and transitive packages. A file with only comments means no third-party package. |
| `package_refs` | `Ref[]` | yes | at most 500 items, unique | Reviewed immutable package bytes the provisioner installs from. Empty when the requirements file pins nothing. |
| `approval_ref` | `Ref` | yes | the protected preparation decision | Record that a human or protected policy approved this lock. |

**Invariants**

- The lock is immutable. A changed requirement or package needs a new lock with a new `id`.
- Hypothesis `environment_ref`, Builder `environment_ref` and Benchmark `environment_lock_ref` name the same lock in one run.

**Producer obligations (environment preparation)**

- Pin every direct and transitive package with `==`. No ranges, no URLs, no editable installs.
- Store each package's bytes before approval and list them in `package_refs`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `requirements_pinned` | Every requirement line has the form `name==version` | reject the lock |
| `package_refs_unique` | No duplicate ref in `package_refs` | reject the lock |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Unpinned or unavailable package | Lock rejected. Hypothesis cannot reference it | The rejected lock and the reason |
| Platform differs from the host | Provisioning fails the Benchmark node and writes an escalation record | The provisioning receipt |
| Lock bytes changed after approval | Every consumer rejects the changed hash | The original lock |

**Examples:** [valid](examples/environment_lock.json)

**Minimum quality bar.** Two hosts that install from the same lock get byte-identical package sets, with no network resolution.

### plan-proposal

Moved. The current contract is `plan-proposal:field-contract:3`, defined on [capsules/planner.md](capsules/planner.md#output-field-contract). Do not restate its fields here.

### frozen-graph

Moved. The current contract is `run-plan:field-contract:1`, defined on [run-plan.md](run-plan.md#run-plan). Do not restate its fields here.

### bound-check-plan

Purpose: the per-attempt list of checks and criteria that must pass, resolved from the pinned check bundle and profile. The check runner runs exactly this list once per work subnode.

`bound-check-plan:field-contract:2` (version 2.0.0) · Producer: protected check runner at dispatch. Consumers: check runner, review-context builder, gate host.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version 2.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this plan. |
| `contract_ref` | `Ref` | yes | a Subnode Execution Contract (subnode scope), the Node Execution Contract (node scope), or the plan source before freeze (plan gate) | Exact contract the checks apply to. |
| `input_refs` | `Ref[]` | yes | equals the `input_refs` of the contract when the contract is a node or subnode contract | Exact bound inputs. |
| `profile_ref` | `Ref` | yes | the pinned checking profile or node finalization profile. At a static plan gate, which has no verifier, the static template | Independently owned profile the criteria come from. |
| `policy_ref` | `Ref` | yes | the frozen policy of the run or plan | Policy whose checks apply. |
| `mandatory_deterministic` | `string[]` | yes | 1 to 64 items, unique, each pattern `^[a-z][a-z0-9_]{0,63}$` | Check IDs that must each appear once in the deterministic result: every blocking check of the pinned bundle, plus contract, profile and policy checks, plus adopted `extra_check_ids`. |
| `mandatory_semantic` | `string[]` | yes | 0 to 32 items, unique, each pattern `^[a-z][a-z0-9_]{0,63}$` | Criterion IDs every verifier assessment must cover once. Empty for a static plan gate, where no verifier runs. |
| `runner_refs` | `Ref[]` | yes | 1 to 16 items | Pinned check implementations and the exact check bundle records they come from. |
| `node_contract_ref` | `Ref` | yes | equals `contract_ref` at node scope and at the plan gate. At subnode scope, the parent named by the subnode contract | Owning Node Execution Contract, or the plan source before freeze. |
| `subnode_id` | `nullable-string` | yes | null exactly when `contract_ref` equals `node_contract_ref`. Otherwise the subnode contract's `subnode_id` | Work subnode the plan checks. Null for node scope and the plan gate. |

**Scopes**

| Scope | `contract_ref` | `subnode_id` | Built from |
|---|---|---|---|
| Work subnode | The work Subnode Execution Contract | its `subnode_id` | The node `check_pins`, the exact inputs and adopted extra checks |
| Node | The Node Execution Contract | null | The fixed node checks `internal_acceptance`, `external_output`, `aggregate_limits` |
| Plan gate | The static template or plan proposal | null | The plan-gate checks of [run plan](run-plan.md#plan-gate) |

**Invariants**

- A work subnode has exactly one bound check plan per attempt. It covers all k outputs of that subnode. Verifier subnodes have none.
- The plan never drops a blocking check of the pinned bundle. Suggested checks add to the list and never replace an entry.

**Producer obligations (check runner)**

- Copy check IDs from the pinned bundle and profile by digest. Never accept a check list from a CC, a template or a proposal.
- Reject a pin whose bundle or profile digest does not resolve.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `check_ids_unique` | `mandatory_deterministic` and `mandatory_semantic` hold no duplicate | reject the plan, the attempt does not start |
| `check_plan_scope` | `subnode_id` is null exactly when `contract_ref` equals `node_contract_ref`. At subnode scope the contract's `subnode_id`, `node_contract_ref` and `input_refs` equal the plan's | reject the plan, the attempt does not start |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Missing bundle or profile association | The attempt does not start. The dispatch record outcome is `failed` | The dispatch record and the reason |
| Scope or input mismatch | The plan is rejected before any check runs | The rejected plan |

**Examples:** [Intent subnode](examples/check_plan.json) · [science node scope](examples/science_node_check_plan.json) · [static plan gate](examples/static_plan_check_plan.json)

**Minimum quality bar.** A reader can list every check that must pass for an attempt from this one record, and each ID traces to a pinned bundle, profile or policy.

### node-execution-contract

Purpose: the run-specific contract of one node attempt. The scheduler builds it at dispatch from the frozen run plan node and the node template stored at freeze. It chooses nothing.

`node-execution-contract:field-contract:2` (version 2.0.0) · Producer: scheduler at dispatch. Consumers: CC runner, check runner, node gate, inspection. Concrete subnodes use the [Subnode Execution Contract](node-execution.md#concrete-subnode) schema.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version 2.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Contract identity. Changed bindings need a new identity or revision. |
| `run_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$` | Run the attempt belongs to. Prevents cross-run substitution. |
| `node_id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`. A run plan node, or `intention_compiler` or `planner` | Node this contract governs. |
| `attempt_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$`. equal to `<node_id>-a<attempt>`, for example `intention_compiler-a1` | Attempt identity. A new attempt is a new contract. |
| `revision` | `integer` | yes | min 1 | Contract revision pinned before execution. |
| `objective` | `string` | yes | 1 to 300 characters, copied from the run plan node | Assigned product outcome, not a private CC task. |
| `requirement_ids` | `string[]` | yes | at most 40, each a Brief `mandatory_requirements` ID or a fixed profile ID | Obligations this node must cover. |
| `inputs` | `BoundNodeInput[]` | yes | at most 16, names unique | Named external input ports with exact accepted refs. |
| `outputs` | `BoundNodeOutput[]` | yes | 1 to 16, names unique | Named external output ports. The Intention Compiler's only external output is the Research Brief. |
| `input_refs` | `Ref[]` | yes | equals the concatenation of every `inputs[].artifact_refs`, in port order | Derived input inventory. |
| `required_outputs` | `string[]` | yes | the contract names of the `required` outputs, in port order | Derived required output inventory. |
| `evidence_obligations` | `string[]` | yes | 1 to 16, unique, each from the enum below | Evidence the node gate requires. Missing evidence blocks. |
| `checking_profile_ref` | `Ref` | yes | the checking profile pinned in the run plan node | Node checking profile. |
| `policy_ref` | `Ref` | yes | the frozen policy of the run | Governing policy. |
| `configuration_ref` | `Ref` | yes | the frozen run configuration | Effective configuration for reproducibility. |
| `template_ref` | `Ref` | yes | the node template stored at freeze | Template the contract was built from. It never depends on future child contracts. |
| `node_limits` | `Limits` | yes | each value at most the run plan node `limits` | Aggregate time, call and memory ceiling, including the verifier reservation. |
| `authority_ceiling` | `AuthorityCeiling` | yes | never wider than the declaration `needs` and the plan policy. `network` `none` needs an empty allowlist | Maximum read, write, tool and network authority. |
| `subnodes` | `NodeSubnodeAssignment[]` | yes | 2 to 16, `subnode_id` unique, `depends_on` acyclic. One work subnode per work CC and one verifier subnode per output | Pinned one-CC assignments and their order. |
| `gate_assignments` | `NodeGateAssignment[]` | yes | 1 to 17, each `subject_subnode_id` names a work subnode | Checking profiles for each work subnode and for final node release. |

**Enum `evidence_obligations`**

| Value | Meaning |
|---|---|
| `captured_input_and_output` | Inputs and outputs are stored by hash before checking |
| `invocation_observation` | One invocation observation per required subnode |
| `mandatory_checks` | A deterministic result for every bound check plan |
| `semantic_assessment` | A verifier assessment for every output |
| `independently_budgeted_check_observation` | The verifier ran inside its own reserved budget |
| `complete_check_and_invocation_records` | Node scope: every internal decision and observation is stored |
| `accepted_intent` | Intention Compiler: the Intent IR was accepted before Requirements ran |
| `accepted_requirements` | Intention Compiler: the Research Brief was accepted |

**Invariants**

- Every verifier subnode depends on the work subnode whose output it reviews. A verifier ID is `<node_id>.verifier` for one output and `<node_id>.verifier.<port>` for several.
- Each subnode `capsule_ref` equals the `capsule_ref` of its template.
- The node gate advances only when every per-output decision of every required work subnode advanced and was stored.

**Producer obligations (scheduler)**

- Copy or derive every value from the frozen node, the node template and the run. Never widen a limit or an authority.
- Bind each future input only to an output the producer node's gate accepted.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `internal_dependencies_acyclic` | `subnode_id` values are unique and `depends_on` names only known subnodes without a cycle | reject, the node is not dispatched |
| `input_inventory_matches_ports` | `input_refs` equals the concatenation of `inputs[].artifact_refs` | reject, the node is not dispatched |
| `gate_subjects_bound` | Every `gate_assignments[].subject_subnode_id` is a work subnode of this contract | reject, the node is not dispatched |
| `verifier_follows_work` | Every verifier subnode depends on at least one work subnode | reject, the node is not dispatched |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Unbound required input | The node is not dispatched. The dispatch record outcome is `failed` | The dispatch record and the reason |
| A host check above fails | The node is not dispatched | The rejected contract |
| Failed internal acceptance, missing evidence or a persistence failure | The node gate halts. No successor starts | The contract, every record of the attempt and the reasons |

**Examples:** [Intention Compiler](examples/intention_node_contract.json) · [science node](examples/science_node_contract.json)

**Minimum quality bar.** A runner can execute the node from this contract and its pinned templates alone, and every value traces to the frozen plan.

### default-policy

`default-policy:field-contract:1` · protected configuration owner → Requirements CC, Requirements verifier.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable policy identity |
| `hardware_profile` | `string` | Conservative default hardware class, currently `single_gpu`. The Requirements CC uses it only to fill an omitted hardware constraint, recorded as an assumption. It is never observed hardware and does not prove a GPU is available. |
| `automatic_retries` | `integer` | Number of automatic compiler repair or replay attempts allowed. Zero means the compiler is never retried automatically. |

**Invalid/missing behavior:** Unknown, unavailable or unsupported default authority blocks the affected requirement; policy cannot invent purpose or claim hardware availability.

## Research artifacts

### candidate-set

Moved. The current contract is `candidate-set:field-contract:2`, defined on [capsules/search.md](capsules/search.md#candidate_set). Do not restate its fields here.

### screening-result

Moved. The current contract is `screening-result:field-contract:2`, defined on [capsules/screening.md](capsules/screening.md#screening_result). Do not restate its fields here.

### opportunity-card

Moved. The current contract is `opportunity-card:field-contract:2`, defined on [capsules/screening.md](capsules/screening.md#opportunity_card). Do not restate its fields here.

### hypothesis-blueprint

Moved. The current contract is `hypothesis-blueprint:field-contract:2`, defined on [capsules/hypothesis.md](capsules/hypothesis.md#output-field-contract). Do not restate its fields here.

### poc-manifest

Moved. The current contract is `poc-manifest:field-contract:2`, defined on [capsules/builder.md](capsules/builder.md#poc_manifest). Do not restate its fields here.

### benchmark-payload

Moved. The current contract is `benchmark-payload:field-contract:2`, defined on [capsules/research-benchmark.md](capsules/research-benchmark.md#41-benchmark_payload-benchmark-payloadfield-contract2). Do not restate its fields here.

### evaluation-verdict

Moved. The current contract is `evaluation-verdict:field-contract:2`, defined on [capsules/scientific-evaluation.md](capsules/scientific-evaluation.md#41-evaluation_verdict-evaluation-verdictfield-contract2). Do not restate its fields here.

### delivery-manifest

Moved. The current contract is `delivery-manifest:field-contract:2`, defined on [capsules/delivery.md](capsules/delivery.md#delivery_manifest). Do not restate its fields here.

## Manifest and runtime records

### artifact-envelope

`artifact-envelope:field-contract:2` · trusted capture → checking, export, runner.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 2.0.0 |
| `id` | `string` | Immutable record identity |
| `contract_id` | `string` | ID of the catalog contract the payload body follows. The trusted runner sets it. CC-authored metadata is untrusted. |
| `payload_ref` | `Ref` | Exact body bytes. A hash that differs from the stored body blocks. |
| `media_type` | `string` | Readable descriptive format of the body, for example `text/plain`. It does not prove the body matches `contract_id`. |
| `run_id` | `string` | Trusted run scope. The trusted runner attaches it. A mismatch blocks. |
| `node_id` | `string` | Trusted node scope. The trusted runner attaches it. A mismatch blocks. |
| `attempt_id` | `string` | Trusted attempt scope. The trusted runner attaches it. A mismatch blocks. |
| `invocation_ref` | `Ref` | Invocation observation of the producer. It names the exact CC version that wrote the body. |
| `source_refs` | `Ref[]` | Chain of original and accepted sources the body derives from. Used for provenance. |
| `audience` | `string` | One of `researcher` (the requesting user) or `reviewer` (the requesting user plus authorized reviewers), the same values as the Delivery file audience. Export and retrieval filter by it. Never widen it. |
| `node_contract_ref` | `Ref` | Owning enclosing Node Execution Contract |
| `subnode_id` | `nullable-string` | Subject/producing subnode; null for node aggregate records |

**Invalid/missing behavior:** CC-authored metadata is untrusted; mismatched type/hash/scope blocks. Envelope does not establish acceptance.

### invocation-observation

Purpose: what the runner observed when one subnode ran one CC. It is the record that the RSI workbench and the platform benchmark runner read through the record export, so it names the exact CC version and the route. After the gate decision the gate host completes it, and the completed line in `records.jsonl` is the Capsule Run Record ([derived records](derived-records.md#capsule-run-record)).

`invocation-observation:field-contract:3` (version 3.0.0: adds `body_files_sha256`, `decision_source`, `failure_class`, `failure_reason_code`, `error_fingerprint`, `check_result_refs`, `verifier_assessment_ref` and `human_answer_ref`) · Producer: protected CC runner, and for the gate-side fields the gate host (hot path). The record builders do not write it. Consumers: gate host, review-context builder, run bundle, record export (RSI workbench, platform benchmark runner).

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `3.0.0` | Format version 3.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this observation. |
| `run_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$`, equals the contract's `run_id` | Run the invocation belongs to. |
| `attempt_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$`, equals the contract's `attempt_id` | Node attempt the invocation belongs to. |
| `node_id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, equals the contract's `node_id` | Node the invocation belongs to. |
| `subnode_id` | `nullable-string` | yes | equals the contract's `subnode_id`. Null only for a node aggregate record | Subnode that ran. |
| `cc_name` | `string` | yes | pattern `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$`, equals the bound declaration `identity.name` | CC that ran. |
| `cc_version` | `string` | yes | pattern `^[a-z0-9][a-z0-9._-]{0,31}$`, equals the bound declaration `identity.version_label` | Exact admitted version that ran. |
| `declaration_sha256` | `sha256` | yes | equals the digest of the bound `declaration_ref` | Exact declaration bytes. The RSI workbench and the benchmark runner join on the triple `cc_name`, `cc_version`, `declaration_sha256`. |
| `route_id` | `nullable-string` | yes | pattern `^[a-z0-9][a-z0-9_.-]{0,63}$`. Null when the CC does not inject the audited model bridge, or when it made no model call request | The [route record](model-routing-contract.md#route-record) of the invocation. Joins the observation to the model chosen. |
| `measurement_status` | `string` | yes | enum `observed`, `unavailable` | Whether the time, call and outcome values were measured. |
| `contract_ref` | `Ref` | yes | the Subnode Execution Contract the CC ran under | Exact contract. |
| `binding_id` | `string` | yes | equals the contract's binding `id` | Binding that ran. |
| `input_refs` | `Ref[]` | yes | equals the contract's `input_refs` | Exact supplied inputs. A verifier receives exactly the declaration and the one output. |
| `output_refs` | `Ref[]` | yes | at most 16 | Captured candidate outputs. Empty when nothing was written. |
| `model_identity` | `ModelIdentity` | yes | none | Requested and effective model, and how the effective one was known. |
| `started_at` | `nullable-string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ`. Non-null when `measurement_status` is `observed` | Observed start. |
| `ended_at` | `nullable-string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ`, not before `started_at`. Null while uncertain | Observed end. |
| `outcome` | `string` | yes | enum below | How the invocation ended. |
| `effects` | `string[]` | yes | at most 32 | Observed effects and tools used. Empty means none observed. |
| `duration_s` | `nullable-number` | yes | min 0. Non-null when `measurement_status` is `observed` | Observed elapsed time in seconds. Null when `measurement_status` is `unavailable`. |
| `model_calls` | `nullable-integer` | yes | min 0. Non-null when `measurement_status` is `observed` | Observed model calls of the CC. |
| `trace_refs` | `Ref[]` | yes | at most 64 | Raw evidence files of the per-call folder: prompt, capsule files, trace, model-call records, workspace copy, gate, verifier and human files ([layout](derived-records.md#records-folder-layout)). |
| `unavailable_reasons` | `string[]` | yes | non-empty when `measurement_status` is `unavailable` | Why a value is missing. |
| `observed_runtime` | `boolean` | yes | false only in synthetic teaching examples | Whether a real execution was observed. |
| `usage` | `Usage` | yes | null is never zero | Token and cost telemetry, with explicit nulls and reasons. |
| `node_contract_ref` | `Ref` | yes | equals the contract's `node_contract_ref` | Owning Node Execution Contract. |
| `body_files_sha256` | `sha256` | yes | SHA-256 of a UTF-8 text with one line per entry of the bound declaration `identity.body`, sorted by `path` in byte order: the path, a tab, the entry `sha256`, a line feed | Exact CC files that ran. With `declaration_sha256` it names the CC version without opening the library. |
| `decision_source` | `nullable-string` | yes | enum `router`, `codex_router_disabled`, `codex_router_failed`. Null exactly when `route_id` is null. Equals the `decision_source` of the route record | Who chose the model. Copied from the [route record](model-routing-contract.md#route-record), so a reader tells a router choice from the fixed Codex route without a join. |
| `failure_class` | `nullable-string` | yes | enum `capsule`, `input`, `infrastructure`, `scientific`, `none`. Null only in the runner's file, before the gate host sets it | Whose problem a failure was, by the [failure class rules](derived-records.md#failure-class-rules). A model never sets it. |
| `failure_reason_code` | `nullable-string` | yes | 1 to 64 characters. Null unless the CC ended without an output and reported a reason | The reason the CC reported at the stop. A declared `guarantees.failure_modes` code, or another string when the failure is undeclared. |
| `error_fingerprint` | `nullable-sha256` | yes | null when no error text exists | SHA-256 of the error text with volatile details removed, so the same error groups across runs. |
| `check_result_refs` | `Ref[]` | yes | at most 64. Empty in the runner's file | Deterministic check results of the gate for this invocation's outputs. |
| `verifier_assessment_ref` | `nullable-Ref` | yes | null in the runner's file, and when no verifier ran | Verifier assessment of this invocation's output. |
| `human_answer_ref` | `nullable-Ref` | yes | null unless a person was asked | The question shown, the answer given and any edit the person made. |

**Enum `measurement_status`**

| Value | Meaning |
|---|---|
| `observed` | The runner measured start, end, duration and model calls for this invocation |
| `unavailable` | At least one of those values was not measured. `unavailable_reasons` says why. A consumer must not compare its time or calls |

**Enum `outcome`**

| Value | Meaning |
|---|---|
| `success` | The CC returned and its outputs were captured |
| `failed` | The CC or its runtime raised an error. No output is accepted |
| `budget_exhausted` | A time, call or memory ceiling stopped the CC |
| `interrupted` | The process ended before the CC returned, for example a restart |
| `synthetic_example` | Documentation only. Never acceptance evidence |

**Invariants**

- `run_id`, `attempt_id`, `node_id`, `subnode_id`, `node_contract_ref` and `binding_id` equal the values of the contract in `contract_ref`.
- `cc_name`, `cc_version` and `declaration_sha256` equal the bound declaration. A record export never has to open the contract to know which CC version ran.
- `observed_runtime` false implies `measurement_status` `unavailable`.
- When `model_calls` is above 0, `route_id` is non-null and names a route record of the same run, node and subnode.
- `decision_source` is null exactly when `route_id` is null, and otherwise equals the `decision_source` of that route record.
- `failure_class` is not `none` when `outcome` is `failed`, `budget_exhausted` or `interrupted`. `error_fingerprint` and `failure_reason_code` are null when `failure_class` is `none`.
- `check_result_refs`, `verifier_assessment_ref` and `human_answer_ref` are empty or null while `failure_class` is null.
- The record is keyed by `run_id`, `node_id`, `attempt_id` and `subnode_id`, and its `id` is the invocation ID. A framework agent ID is never a key ([D37](../method/decisions.md#d37)).

**Producer obligations (CC runner)**

- Write the observation from runner measurements only. A CC cannot author any field.
- Copy the identity fields from the contract and the declaration at dispatch, before the CC starts.
- Mark a value `unavailable` with a reason rather than estimate it.
- Write `failure_class`, `check_result_refs`, `verifier_assessment_ref` as null or empty, and leave them to the gate host. The gate host (hot-path platform code, not a record builder) appends the completed record to `records.jsonl` right after the gate decision of the invocation is committed. It never changes the runner's file. A failed append is logged and never blocks the run.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `observation_identity_matches_contract` | The identity fields and the CC triple equal the contract and its bound declaration | the gate rejects the observation and halts |
| `measurement_status_consistent` | `observed` has non-null `started_at`, `duration_s` and `model_calls` and `observed_runtime` true. `unavailable` has a reason | the gate rejects the observation and halts |
| `route_id_matches_model_use` | `route_id` is null for a CC without the model bridge, and non-null when `model_calls` is above 0 | the gate rejects the observation and halts |
| `observation_body_matches_declaration` | `body_files_sha256` recomputes from the `identity.body` entries of the bound declaration | the gate rejects the observation and halts |
| `observation_decision_source_consistent` | `decision_source` is null exactly when `route_id` is null | the gate rejects the observation and halts |
| `failure_class_consistent` | The `failure_class` invariants above hold | the gate host does not append the completed record. The run is not affected |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A mandatory observation is missing | The gate halts the subnode | Every captured output and record |
| Optional telemetry is missing | The record is valid with `unavailable` and a reason | The record |
| Identity mismatch | The gate halts. The export marks the record unusable for comparison | The record and the mismatch reason |

**Examples:** [Intent work](examples/invocation_observation.json) · [science work](examples/science_observation.json) · [science verifier](examples/science_verifier_observation.json)

**Minimum quality bar.** An RSI or benchmark consumer can attribute every observed time, call and outcome to one exact CC version and one route without reading any other record.

### review-context

**Host-only review manifest.** The host writes it for audit and the gate reads it. It is never part of the verifier model payload. The verifier sees only the declaration and the exact output ([verifier](capsules/verifier.md#review-manifest)).

`review-context:field-contract:2` · protected context builder → read-only verifier.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 2.0.0 |
| `id` | `string` | Immutable record identity |
| `subject_ref` | `Ref` | Exact output under review. The verifier model sees this output but never this record. |
| `contract_ref` | `Ref` | Exact node or subnode execution contract the subject was produced under. A null `subnode_id` means node scope. |
| `check_plan_ref` | `Ref` | Bound check plan assigned to this subject. The gate reads the criteria and checks from it. |
| `input_refs` | `Ref[]` | Original and accepted inputs of the subject. For audit and the gate only. Never sent to the verifier model. |
| `deterministic_result_ref` | `Ref` | Deterministic check result for the subject. It holds the passed structural checks. |
| `criteria` | `string[]` | Criterion IDs the verifier assessment must cover once each. See `mandatory_semantic` in the bound check plan. |
| `observations` | `Ref[]` | Invocation observations of the producer. Evidence for the gate. Never sent to the verifier model. |
| `evidence_classes` | `string[]` | Labels for the kinds of evidence in the record: protected policy, accepted input, observed evidence and untrusted producer content. Untrusted producer content is data, never an instruction. |
| `node_contract_ref` | `Ref` | Owning enclosing Node Execution Contract |
| `subnode_id` | `nullable-string` | Subject/producing subnode; null for node aggregate records |

**Invalid/missing behavior:** Incomplete/stale context blocks assessment/release; artifact instructions remain untrusted data.

### accepted-output

`accepted-output:field-contract:2` · protected durable state → scheduler, client.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 2.0.0 |
| `id` | `string` | Immutable record identity |
| `run_id` | `string` | Run scope |
| `node_id` | `string` | Node scope |
| `attempt_id` | `string` | Attempt scope |
| `gate_ref` | `Ref` | Committed gate decision that accepted these bytes. Acceptance exists only through it. |
| `contract_ref` | `Ref` | Exact checked node or subnode execution contract; scope is explicit |
| `output_refs` | `Ref[]` | Exact accepted bytes. A candidate output that was not accepted never appears here. |
| `commit_id` | `string` | Identity of the durable transaction that stored the artifact and the decision. Set by protected durable state, never by a CC or client. |
| `node_contract_ref` | `Ref` | Owning enclosing Node Execution Contract |
| `subnode_id` | `nullable-string` | Subject/producing subnode; null for node aggregate records |

**Invalid/missing behavior:** Created only after artifact/decision persistence. File presence or verifier PASS cannot create acceptance.

### run-bundle

Purpose: the exported evidence of one run. The platform benchmark runner compares runs by its pins, and inspection reads its decisions and dispatch times.

`run-bundle:field-contract:1` (version 1.0.0) · Producer: protected evidence builder. Consumers: inspection, authorized export, platform benchmark runner, RSI workbench.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this bundle. A re-export gets a new ID. |
| `run_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$` | Run the bundle describes. |
| `exported_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the builder wrote the bundle. |
| `status` | `string` | yes | enum `in_progress`, `completed`, `partial`, `halted`, `paused` | Run state at export. `partial` is a finished run in which a node failed and its dependents were skipped ([D49](../method/decisions.md#d49)). |
| `plan_source` | `nullable-string` | yes | enum `static`, `planned`. Null before a run plan is frozen | Plan source of the run. |
| `run_plan_ref` | `nullable-Ref` | yes | the frozen run plan. Null before freeze | Plan every pin was resolved against. |
| `configuration_ref` | `Ref` | yes | the frozen run configuration | Requested and effective settings. |
| `evaluation_profile_id` | `nullable-string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$`. Null in a product profile | Approved [evaluation profile](#evaluation-profile) the app ran under. |
| `pins` | `RunPins` | yes | see the type below | Versions the benchmark runner compares with campaign pins. |
| `effective_seed` | `nullable-integer` | yes | min 0. Null when the system did not report one | Seed the run actually used. |
| `artifact_refs` | `Ref[]` | yes | at most 500 | Candidate and accepted artifacts. The files are the `inputs/` and `outputs/` files of the per-call folders and the `run-end/` files ([layout](derived-records.md#records-folder-layout)). |
| `decision_refs` | `Ref[]` | yes | at most 200, unique, equal to the set of `gate_decisions[].decision_ref` | Gate decisions of the run. |
| `gate_decisions` | `BundleGateDecision[]` | yes | at most 200. One entry per per-output decision and one per node-scope decision | Gate outcome summary, so the runner needs not open each decision. |
| `node_dispatches` | `NodeDispatchTime[]` | yes | at most 64. One entry per node attempt, in dispatch order | When each node attempt ran and how it ended. |
| `observation_refs` | `Ref[]` | yes | at most 500 | Invocation observations of the run. |
| `model_call_refs` | `Ref[]` | yes | at most 2000 | Model-call records of the run. |
| `route_record_refs` | `Ref[]` | yes | at most 2000 | Route records of the run, one per routed invocation. |
| `fault_ids` | `string[]` | yes | each pattern `^[a-z][a-z0-9_.:-]{0,63}$`. Empty when `evaluation_profile_id` is null | Faults the evaluation profile injected. |
| `missing_evidence` | `MissingEvidence[]` | yes | at most 100 | Items not produced or unavailable, with reasons. |
| `redactions` | `string[]` | yes | at most 100 | What this audience does not see, and why. |

**RunPins**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `app_build` | `string` | yes | 1 to 120 characters | Application build identity, equal to readiness `build_id`. |
| `client_contract_version` | `string` | yes | pattern `^[0-9]+\.[0-9]+\.[0-9]+$` | Client contract version the app served. |
| `library_snapshot_sha256` | `sha256` | yes | digest of the library snapshot bytes the run plan names | Which CC versions were eligible. |
| `plan_policy_ref` | `Ref` | yes | the plan policy the run plan names | Operator limits on nodes, effects, resources and budget. |
| `check_bundle_set_sha256` | `sha256` | yes | see the rule below | Which check bundles the library pinned. |
| `router_enabled` | `boolean` | yes | copied from `cc.router.enabled` | Whether the API router was on. |
| `router_version` | `nullable-string` | yes | null exactly when `router_enabled` is false | Version of the API router that served the run. |

`check_bundle_set_sha256` is the SHA-256 of a UTF-8 text built from the library snapshot. Take the `check_bundle_sha256` of every entry whose `check_pins` is not null. Remove duplicates, sort ascending, and write each value followed by one line feed.

**BundleGateDecision**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `node_id` | `string` | yes | equals the decision `node_id` | Node the decision belongs to. |
| `subnode_id` | `nullable-string` | yes | equals the decision `subnode_id`. Null for a node-scope decision | Work subnode of a per-output decision. |
| `scope_kind` | `string` | yes | enum `subnode`, `node` | Decision scope. |
| `output_port` | `nullable-string` | yes | equals the decision `output_port`. Null for a node-scope decision and for a halt with no output | Output the decision reviewed. |
| `verdict` | `string` | yes | enum `PASS`, `PASS_WITH_KNOWN_LIMITATIONS`, `FAIL`, `ENVIRONMENT_BLOCKED`, `INCONCLUSIVE` | Gate verdict, copied verbatim. |
| `action` | `string` | yes | enum `advance`, `halt` | Gate action, copied verbatim. |
| `recorded_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ`, equals the decision `recorded_at` | When the gate host stored the decision. |
| `decision_ref` | `Ref` | yes | an entry of `decision_refs` | The decision itself. |

**NodeDispatchTime**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `node_id` | `string` | yes | equals the dispatch record `node_id` | Node dispatched. |
| `attempt_id` | `string` | yes | equals the dispatch record `attempt_id` | Attempt dispatched. |
| `started_at` | `string` | yes | equals the dispatch record `started_at` | Dispatch start. |
| `ended_at` | `nullable-string` | yes | equals the dispatch record `ended_at` | Attempt end. Null for `interrupted`. |
| `outcome` | `string` | yes | the dispatch record outcome enum | How the attempt ended. |
| `dispatch_record_ref` | `Ref` | yes | the dispatch record | Source of these values. |

**Invariants**

- Every decision, dispatch record, observation, route record and model-call record in the bundle has the bundle's `run_id`.
- A completed bundle has a node-scope decision with action `advance` for every node in `node_dispatches`.
- `fault_ids` is empty unless `evaluation_profile_id` is set. A bundle with a non-empty `fault_ids` is never product output or RSI material.
- An `in_progress` bundle lists the outputs not yet produced in `missing_evidence`.

**Producer obligations (evidence builder)**

The evidence builder is hot-path platform code, not a record builder. It writes the manifest at run end, and the gate reads it.


- Copy pins from the frozen run plan, the library snapshot and the run configuration. Never from a client.
- Copy gate and dispatch values from the stored records. Never recompute a verdict.
- Name every record that is unavailable in `missing_evidence` instead of leaving it out.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `bundle_pins_match_run_plan` | `library_snapshot_sha256` and `plan_policy_ref` equal the run plan pins, and `check_bundle_set_sha256` recomputes from its library snapshot | the export is refused |
| `bundle_router_pin_consistent` | `router_version` is null exactly when `router_enabled` is false | the export is refused |
| `faults_only_in_evaluation` | `fault_ids` is empty when `evaluation_profile_id` is null | the export is refused |
| `bundle_gate_entries_match` | Each `gate_decisions` entry equals its decision, and `decision_refs` equals the set of entry refs | the export is refused |
| `bundle_dispatch_times_match` | Each `node_dispatches` entry equals its dispatch record, and all records share `run_id` | the export is refused |
| `dispatches_sequential` | No node dispatch starts before the previous one ended (one node at a time) | the export is refused |
| `dispatch_attempts_unique` | No `attempt_id` appears twice, so an interrupted attempt is never replayed | the export is refused |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No bundle is exported. The client sees a `client-error` | The durable run state |
| Evidence missing | The bundle is exported with a `missing_evidence` entry. A completed status is not claimed | The bundle |
| Export interrupted | The partial file is discarded. A later export gets a new ID | The durable run state |

**Examples:** [valid, science node](examples/run_bundle.json)

**Minimum quality bar.** Two bundles with equal pins differ only by the run's own nondeterminism, and every comparison the benchmark runner makes can be traced to a stored decision or dispatch record.

## Client and model boundaries

### control-api

Purpose: the one table of control API operations. The browser, the CLI, the platform benchmark runner and the test runner all call the app through these paths. No page repeats them.

**Authentication.** Every request carries `Authorization: Bearer <session token>`. A user's token comes from the one-time URL that `jiuwenswarm-start` prints inside the app container ([D35](../method/decisions.md#d35)). Each sidecar client uses its own scoped token in the same header ([D36](../method/decisions.md#d36)). A request without a valid token gets a `client-error` and no other effect. The app binds only the server's private address.

| Operation | Method and path | Request record | Reply record | Notes |
|---|---|---|---|---|
| Readiness | `GET /api/v1/readiness` | none | [client-readiness](#client-readiness) | Clients check target identity and contract version before any submit |
| Submit | `POST /api/v1/runs` | [client-submission](#client-submission) | [client-status](#client-status) | A repeated `client_request_id` returns the existing run |
| Reconcile | `GET /api/v1/runs?client_request_id=<id>` | none | [client-status](#client-status), or [client-error](#client-error) when no run exists | Resolves uncertain delivery before a resend |
| Status | `GET /api/v1/runs/<run_id>` | none | [client-status](#client-status) | |
| Retrieve | `GET /api/v1/runs/<run_id>/export` | none | [client-retrieval](#client-retrieval) | |
| Cancel | `POST /api/v1/runs/<run_id>/cancel` | [client-cancellation](#client-cancellation) | [client-cancellation](#client-cancellation) | Stops new dispatch. It cannot undo external effects |
| Upload | `POST /api/v1/inputs/<kind>` where `<kind>` is `docs`, `repo` or `datasets` | multipart form with `file` and `scope_id` (the run or project ID) | [client-upload](#client-upload) | User token. Stores the file in the app container volume under `workspace/input/<kind>/<scope_id>/`. Intake qualifies only uploaded files |
| List uploads | `GET /api/v1/inputs?scope_id=<id>` | none | [client-upload](#client-upload), one per stored file | User token. Returns only the caller's own uploads |
| Delete upload | `DELETE /api/v1/inputs/<upload_id>` | none | [client-upload](#client-upload) with `status` `deleted` | User token. Removes the stored bytes (PRD US20). Refused while a run that uses the file is not finished |

Status replies carry the PRD lifecycle name of each node in `node_statuses` ([node lifecycle](#node-lifecycle)).

A reply of `client-error` is a result, not an exception. The evaluation-profile entry points are not in this table. They exist only under an approved [evaluation profile](#evaluation-profile) and use a separate credential scope ([entry points](../side-systems/benchmark-runner.md#entry-points)).

### node-lifecycle

Purpose: the one mapping from the package's node and attempt states to the five lifecycle names of the PRD (PRD 4.2, 4.8, 4.10). The web UI and the status API show the PRD name. The records keep the package words.

| PRD name | Package state | Where it comes from |
|---|---|---|
| `Pending` | The node has no attempt in progress and no dispatch record yet. It waits for the node gates of its predecessors, or the run stopped before the node was dispatched (a halt, a cancel) | Run plan and dispatch records |
| `Running` | An attempt is in progress and a work subnode, or the Intention Compiler or Planner work CC, is executing | Run state of the attempt |
| `Evaluating` | The work subnodes have returned and a check bundle, a verifier subnode or a gate decision (per output or node) is in progress | Run state of the attempt |
| `Completed` | The dispatch record `outcome` is `accepted` | [Dispatch record](run-plan.md#dispatch-record) |
| `Failed` | The dispatch record `outcome` is `rejected`, `halted`, `failed`, `budget_exhausted` or `interrupted`. Also a node the scheduler marked `skipped` because a node it depends on failed: the PRD has no skipped name, so `Failed` is the closest, and `NodeStatus.skipped_because` names the cause ([D49](../method/decisions.md#d49)) | [Dispatch record](run-plan.md#dispatch-record) and run state |

The scheduler writes the dispatch record at the end of the attempt ([dispatch record](run-plan.md#dispatch-record)). So `Pending`, `Running` and `Evaluating` come from the run state while the attempt is open, and `Completed` and `Failed` come from the stored record. A mandatory check failure ends in `rejected`, so it shows as `Failed` and no verifier runs. An `interrupted` attempt shows as `Failed` for the node, and the run `status` is `paused` until a person decides. The run-level `status` of the [client status](#client-status) is separate from the node names.

### client-readiness

Purpose: what the running application says about itself before a client submits. A client compares it with what it expects and refuses to submit on any mismatch.

`client-readiness:field-contract:1` (version 1.0.0) · Producer: application. Consumers: browser, CLI, platform benchmark runner, sidecar.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this readiness report. |
| `client_contract_version` | `string` | yes | pattern `^[0-9]+\.[0-9]+\.[0-9]+$` | Client contract version the app serves. |
| `instance_id` | `string` | yes | 1 to 120 characters | Target instance identity. |
| `build_id` | `string` | yes | 1 to 120 characters | Application build identity. |
| `operations` | `string[]` | yes | 1 to 32 items, unique, each from the client operation names, for example `submit`, `status`, `retrieve`, `cancel` | Operations the app accepts now. |
| `prerequisites` | `Prerequisite[]` | yes | at most 32 | Storage, auth, model and isolation state, each with a reason. |
| `ready` | `boolean` | yes | true only when every mandatory prerequisite has status `ready` | Whether a submission can start. |
| `evaluation_profile` | `nullable-string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$`. Null in every product profile | `profile_id` of the evaluation profile the launcher started the app with. |
| `fault_injection` | `boolean` | yes | true only when `evaluation_profile` is not null and that profile allows E4 | Whether the app accepts a `fault_id` on submit. |
| `pins` | `RunPins` | yes | `app_build` equals `build_id`, `client_contract_version` equals the field above | Versions a run submitted now would use. The [RunPins](#run-bundle) type is shared with the run bundle. |

**Invariants**

- `pins.app_build` equals `build_id` and `pins.client_contract_version` equals `client_contract_version`.
- `pins.router_version` is null exactly when `pins.router_enabled` is false.
- `fault_injection` is false when `evaluation_profile` is null.

**Producer obligations (application)**

- Report observed state. Liveness alone is not readiness.
- Never list an evaluation entry point in `operations` unless the evaluation profile allows it.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `readiness_pins_match_identity` | The two pin copies equal `build_id` and `client_contract_version`, and the router pin rule holds | the client treats the app as not ready |
| `fault_injection_needs_profile` | `fault_injection` is false when `evaluation_profile` is null | the client treats the app as not ready |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Wrong target or contract version | The client does not submit | The readiness report |
| Mandatory prerequisite unavailable | `ready` is false. The client does not submit | The report with the reason |
| Pins differ from the campaign pins | The benchmark runner records `pins_match` false | The report and the run record |



**Minimum quality bar.** A client can decide whether to submit, and whether the run will be comparable, from this record alone.

### client-submission

Purpose: one idempotent request to start a run. An evaluation client also links the run to its campaign.

`client-submission:field-contract:1` (version 1.0.0) · Producer: scoped client. Consumers: control plane.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this submission record. |
| `client_request_id` | `string` | yes | pattern `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`, unique per submission attempt | Idempotent submission identity used to reconcile uncertain delivery. |
| `workspace_id` | `string` | yes | an authorized workspace | Scope of the run: the workspace whose uploaded inputs intake may read. The control plane checks that the session token is authorized for it, and rejects the submission otherwise. |
| `account_id` | `string` | yes | the authenticated actor | Who submits. The control plane sets it from the session token. A value sent by the client is ignored. |
| `intake_ref` | `Ref` | yes | a qualified intake | Qualified request and resources. |
| `configuration_ref` | `Ref` | yes | the operator's approved `config.yaml` snapshot | The approved settings, model route and requested seed. The operator approves the file, never the client. A client cannot set `cc.router.*` or any other operator setting. |
| `plan_source` | `string` | no | enum `static`, `planned`. Default `static`. Under an evaluation profile it equals that profile's `plan_source` | Chooses the plan before the run: `static` for the static template, `planned` for the Planner node ([D39](../method/decisions.md#d39)). The binder copies it into the run plan. Nothing else selects it. |
| `interaction_mode` | `string` | no | enum `interactive`, `headless`. A web UI submission defaults to `interactive`. A CLI or sidecar submission defaults to `headless` | Whether a person is present to answer intake clarification questions. The control plane freezes it in the run configuration. It changes nothing after intake: no run waits for a person ([D48](../method/decisions.md#d48), [D50](../method/decisions.md#d50)). |
| `evaluation` | `nullable-EvaluationLink` | no | absent or null for product use. Set only by the platform benchmark runner | Campaign identities the app copies into the run bundle. |
| `profile_id` | `nullable-string` | no | pattern `^[a-z][a-z0-9_.:-]{0,63}$`, equals readiness `evaluation_profile` | Evaluation profile the client expects. The app refuses a mismatch. |
| `fault_id` | `nullable-string` | no | pattern `^[a-z][a-z0-9_.:-]{0,63}$`. Non-null only when `profile_id` is set and readiness `fault_injection` is true | Fault from the campaign fault plan to inject in this run. |

**EvaluationLink**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `campaign_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$` | Benchmark campaign. |
| `run_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,127}$` | Benchmark run ID `<campaign_id>__<case_id>__<config_id>__r<nn>`. It is not the app's `run_id`. |
| `inventory_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$` | Hardware inventory taken before the run. |

**Invariants**

- `fault_id` needs `profile_id` and `evaluation`.
- `profile_id` needs `evaluation`. A product client sends none of the three.
- A submission carries no operator setting. A field outside this table, including any `cc.*` key, is refused by `submission_structure`.

**Producer obligations (client)**

- Reuse `client_request_id` when resending after uncertain delivery. Never create a second run for the same request.
- Take `profile_id` from the readiness report, not from configuration.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `submission_structure` | The submission matches `client-submission:field-contract:1`. A field outside the table, such as `cc.router.enabled`, is refused | the control plane rejects the submission with a `client-error` |
| `fault_requires_profile` | A non-null `fault_id` comes with a non-null `profile_id` and `evaluation`, and a non-null `profile_id` comes with `evaluation` | the control plane rejects the submission with a `client-error` |
| `profile_matches_readiness` | `profile_id` equals the app's readiness `evaluation_profile` | the control plane rejects the submission |
| `plan_source_matches_profile` | When `profile_id` is set, `plan_source` equals the evaluation profile's `plan_source` | the control plane rejects the submission |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Uncertain delivery | The client reconciles by `client_request_id` before resending | The first submission and its status |
| Profile or fault rejected | No run starts. The client receives a `client-error` | The rejected submission |



**Minimum quality bar.** A resent submission never starts a second run, and every evaluation run can be joined to its campaign row.

### evaluation-profile

Purpose: an approved app configuration for benchmarking. The launcher starts the app with it. It fixes what is compared and which evaluation entry points exist. A product profile has no evaluation profile.

`evaluation-profile:field-contract:1` (version 1.0.0) · Producer: protected configuration owner, approved by the benchmark owner. Consumers: launcher, application (readiness, binder, router switch, entry points), platform benchmark runner.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this record. |
| `profile_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Name clients see in readiness `evaluation_profile` and send as `profile_id`. |
| `plan_source` | `string` | yes | enum `static`, `planned` | The `plan_source` every run under this profile must request. A submission whose `plan_source` differs is rejected (`plan_source_matches_profile`). The profile mirrors the run setting and adds no other selector. |
| `router_enabled` | `boolean` | yes | equals operator config `cc.router.enabled` (`router_enabled_needs_profile`) | Whether the API router is on for runs under this profile. The launcher writes the same value into the operator config it starts the app with. |
| `router_version` | `nullable-string` | yes | null exactly when `router_enabled` is false | Router version the comparison pins. |
| `model_route` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.-]{0,63}$`. The fixed Codex route ID when `router_enabled` is false | Route kept apart from the model identifier. |
| `library_snapshot_sha256` | `sha256` | yes | digest of the library snapshot every run must capture | Library state under test. The binder refuses a run whose snapshot differs. |
| `candidate_pins` | `CcPin[]` | yes | at most 8, `cc_name` unique. Empty unless comparing an RSI child | CC versions that replace the active version of the same `cc_name` for this profile. Each must be an admitted entry of the pinned snapshot. |
| `verifier_cc_ref` | `Ref` | yes | the Verifier CC declaration bytes | Verifier version every verifier subnode must bind. |
| `invalid_for_product` | `boolean` | yes | true when `allowed_entry_points` holds E2, E3, E4 or E5, or `candidate_pins` is not empty | Marks every run and bundle of this profile as unusable as product output or RSI material. |
| `allowed_entry_points` | `string[]` | yes | 1 to 5 items, unique, each enum `E1`, `E2`, `E3`, `E4`, `E5` | Entry points the app exposes under this profile. E6 is runner-side and never listed. |

**Enum `allowed_entry_points`**

| Value | Meaning |
|---|---|
| `E1` | Ordinary client: submit, observe, retrieve, cancel |
| `E2` | Node replay |
| `E3` | Single-CC invocation with a supplied binding |
| `E4` | Fault injection hook. Readiness `fault_injection` becomes true |
| `E5` | Checkpoint observation |

**Invariants**

- `router_version` is null exactly when `router_enabled` is false.
- `invalid_for_product` is true whenever the profile allows E2 to E5 or pins a candidate.
- A profile is immutable. A changed value needs a new `id` and a new `profile_id`.

**Producer obligations (configuration owner)**

- Approve a profile before a campaign freezes. Never edit it during a campaign.
- Keep one intentional difference per paired comparison, for example `router_enabled`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `profile_router_pin_consistent` | `router_version` is null exactly when `router_enabled` is false | the launcher refuses to start the app |
| `evaluation_only_marked_invalid_for_product` | Any of E2 to E5, or a candidate pin, needs `invalid_for_product` true | the launcher refuses to start the app |
| `entry_points_unique` | `allowed_entry_points` holds no duplicate | the launcher refuses to start the app |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | The app does not start under the profile | The rejected profile |
| A run's library snapshot differs from `library_snapshot_sha256` | The run halts before dispatch | The run record with the reason |
| A candidate pin is not admitted | The run halts before dispatch | The run record with the reason |



**Minimum quality bar.** Two runs under the same profile differ only in what the campaign pair declares, and no run that used an evaluation-only hook can be mistaken for product output.

### client-status

`client-status:field-contract:1` · control plane → clients.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `client_request_id` | `string` | Echo of the submission `client_request_id`. A client uses it to reconcile uncertain delivery before it resends. |
| `run_id` | `nullable-string` | Allocated run ID. Null when no run was allocated yet. |
| `revision` | `integer` | Monotonic integer revision of the run state. Use it to tell a newer status from a stale one. |
| `stage` | `string` | The `node_id` of the node running now, or of the last node that finished; `intention_compiler` or `planner` before the plan exists. Display only. Per-node state is in `node_statuses`. |
| `status` | `string` | Run state, with the run bundle `status` values: `in_progress`, `completed`, `partial`, `halted`, `paused`. A cancelled run reports `halted` and its `reasons` say so. A client decides from this field, never from `reasons`. |
| `candidate_refs` | `Ref[]` | Candidate outputs that are not accepted. Show them as unaccepted. They are never a result. |
| `accepted_refs` | `Ref[]` | Outputs the gate accepted and durable state committed. |
| `decision_ref` | `nullable-Ref` | Latest gate decision. Null before any decision exists. |
| `reasons` | `string[]` | Plain-language explanation shown to the user. Display only: a client decides from `status`, not from these strings. |
| `bundle_ref` | `nullable-Ref` | Run bundle available for export. Null until an export exists. |
| `node_statuses` | `NodeStatus[]` | One entry per node of the plan, with its PRD lifecycle name ([node lifecycle](#node-lifecycle)) |

**Invalid/missing behavior:** Disconnection does not cancel; malformed or stale status is unavailable, not accepted completion.

### client-retrieval

`client-retrieval:field-contract:1` · scoped client and application → inspection, export.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `run_id` | `string` | Authorized run |
| `artifact_refs` | `Ref[]` | Identities of the artifacts requested and returned. |
| `audience` | `string` | One of `researcher` (the requesting user) or `reviewer` (the requesting user plus authorized reviewers), the same values as the Delivery file audience. Content outside it is withheld and listed in `redactions`. |
| `files` | `NamedFile[]` | Returned content as `NamedFile` entries, each with its own `audience`. |
| `redactions` | `string[]` | What was withheld from this audience, and why. Empty means nothing was withheld. |

**Invalid/missing behavior:** No direct database/volume access; path escape or forbidden audience is rejected.

### client-cancellation

`client-cancellation:field-contract:1` · client and protected controller → runner, client.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `request_id` | `string` | ID of this cancellation request, chosen by the client. A resend with the same ID is recognized and not applied twice. Not the submission `client_request_id`. |
| `run_id` | `string` | Target |
| `status` | `string` | Progress of the cancellation, set by the protected controller. `requested`: recorded, and no new node is dispatched from now on. `acknowledged`: the scheduler is containing the active work. `terminal`: no work is running and the run is `halted`. |
| `preserved_effects` | `string[]` | Known external effects that cancellation cannot undo. Cancellation is not rollback. Empty means none are known, not that none happened. |

**Invalid/missing behavior:** Stop new dispatch, contain active work, preserve uncertainty/evidence; cancellation is not rollback.

### client-upload

Purpose: the record of one file a user uploaded to the server, and of its later deletion. The control API stores uploads in the app container volume. Protected intake qualifies only uploaded files, so this record is the only way a user file reaches a run ([D35](../method/decisions.md#d35), PRD US03 and US20).

`client-upload:field-contract:1` (version 1.0.0) · Producer: control plane. Consumers: protected intake, browser, CLI.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable upload ID. The delete operation names it. |
| `user_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Authenticated user who uploaded the file. Only that user lists or deletes it. |
| `scope_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.-]{0,63}$` | The run or project the file belongs to. It names the folder under the kind folder. |
| `kind` | `string` | yes | enum `docs`, `repo`, `datasets` | Which input folder holds the file. |
| `resource_type` | `string` | yes | enum `reference_document`, `project_asset`, `validation_data`. Follows `kind` | The PRD resource type that intake registers. |
| `filename` | `string` | yes | pattern `^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$` | File name as stored. It holds no path separator. |
| `size_bytes` | `integer` | yes | min 0 | Size of the stored bytes. |
| `stored_path` | `string` | yes | equals `workspace/input/<kind>/<scope_id>/<filename>` | Where the file sits in the app container volume. |
| `content_sha256` | `sha256` | yes | SHA-256 of the stored bytes | Identity of the uploaded bytes. Kept after deletion. |
| `text_sha256` | `nullable-sha256` | yes | non-null exactly when `kind` is `docs` | SHA-256 of the UTF-8 text extracted from the document. |
| `status` | `string` | yes | enum `uploaded`, `deleted` | Whether the bytes are still stored. |
| `uploaded_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | Time the file was stored. |
| `deleted_at` | `nullable-string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ`. Non-null exactly when `status` is `deleted` | Time the bytes were removed. |

**Kinds**

| `kind` | `resource_type` | What the user uploads | Handling |
|---|---|---|---|
| `docs` | `reference_document` | A `.txt`, `.md` or `.pdf` reference document | The control API extracts the text and records `text_sha256`. Intake passes the text, never the file, to the Intent CC |
| `repo` | `project_asset` | A `.zip` archive of the project directory | Stored as the archive. Nothing clones, extracts or modifies it at upload. The executor binds a read-only captured copy at provisioning. An entry with an absolute path, `..` or a link is refused |
| `datasets` | `validation_data` | A validation data file or a baseline snapshot | Stored as is. Kept apart from the text buffer |

**Invariants**

- `kind` and `resource_type` agree as the table says. `stored_path` follows `kind`, `scope_id` and `filename`.
- `text_sha256` is non-null exactly for `docs`. `deleted_at` is non-null exactly when `status` is `deleted`.
- A deleted record keeps its hashes. Only the stored bytes and the extracted text are removed.

**Producer obligations (control plane)**

- Accept an upload only with a valid session token. Take `user_id` from the token, never from the request.
- Write the bytes under `workspace/input/<kind>/<scope_id>/` in the app container volume, then return the record. A failed write returns a `client-error` and stores nothing.
- On delete, remove the stored bytes and the extracted text, set `status` and `deleted_at`, and return the record. Refuse the delete with a `client-error` while a run that uses the upload is not finished. A run that finished keeps the copies its evidence captured. Removing run records is a separate run-data operation.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `upload_kind_matches_type` | `resource_type`, `stored_path` and `text_sha256` follow `kind` | the control plane refuses the upload with a `client-error` |
| `upload_deleted_consistent` | `deleted_at` is non-null exactly when `status` is `deleted` | the record is refused |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Wrong type, unreadable document or unsafe archive entry | The upload is refused with a `client-error`. Nothing is stored | The refusal |
| Delete of an upload that a running run uses | The delete is refused with a `client-error`. The file stays | The record |
| Delete of an unknown or foreign upload | A `client-error`. No other effect | Nothing |

[valid, dataset](examples/client_upload_validation.json)

**Minimum quality bar.** A user can upload, list and delete their own files through the browser or the CLI, and intake never reads a file that is not an upload record.

### client-error

`client-error:field-contract:1` · application → clients.

| Field | Type | Meaning / why needed |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `category` | `string` | Stable reason family that a client may branch on: one of `auth`, `validation`, `not_found`, `conflict`, `unavailable`, `internal`. It is not user text. |
| `message` | `string` | Actionable explanation for the user. Display only. Never holds credentials or hidden fixtures. |
| `request_id` | `nullable-string` | Request this error answers, when known. Null otherwise. |
| `run_id` | `nullable-string` | Run this error concerns, when known. Null otherwise. |
| `evidence_refs` | `Ref[]` | Records the caller is authorized to see that explain the error. Empty when there are none. |
| `correction` | `string` | Action the user may take. A client never retries implicitly because of it. |

**Invalid/missing behavior:** Never include credentials/hidden fixtures or suggest implicit work retry.

### operator-config

Purpose: the one operator configuration file, `config.yaml` (PRD 5.6). The operator mounts it read-only into the app container. The entrypoint reads it before it accepts work. It holds the `cc.*` settings and the role aliases. No other file or environment variable sets them. Each run copies the effective values into its frozen run configuration at run start, so a later edit never changes an active run.

`operator-config:field-contract:1` (version 1.0.0) · Producer: operator (protected configuration owner). Consumers: app container entrypoint, binder, model bridge, scheduler.

The file is YAML. A dotted name is a nested key: `cc.router.enabled` is `enabled` under `router` under `cc`. A key that is not in the table is refused.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `cc.plan_source` | `string` | yes | enum `static`, `planned`. Default `static` | Plan source of a run whose submission names none. A submission's `plan_source` wins ([D39](../method/decisions.md#d39)). |
| `cc.plan_policy_ref` | `Ref` | yes | the [plan policy](run-plan.md#plan-policy) | Operator limits the binder and the Planner stay inside. |
| `cc.static_template_ref` | `Ref` | yes | an admitted [static template](run-plan.md#static-template) | The one static template a `static` run binds. The binder loads exactly this file and checks its hash. It never picks a template by name or by newest version. To change the fixed path, the operator points this at a new template version and restarts. |
| `cc.evaluation_profile_ref` | `nullable-Ref` | yes | default null. When non-null, an approved [evaluation profile](#evaluation-profile) | The evaluation profile this app start runs under. Null for normal product use. The host launcher writes it when it starts the app for an evaluation; nothing else loads a profile. |
| `cc.router.enabled` | `boolean` | yes | default `false` | The one router switch. When `cc.evaluation_profile_ref` is set, it must equal that profile `router_enabled`. Its meaning and rules live in the [routing contract](model-routing-contract.md#routerport-the-hot-path-seam). |
| `cc.router.deadline_s` | `number` | yes | default `30` | Router deadline in seconds. Meaning in the [routing contract](model-routing-contract.md#routerport-the-hot-path-seam). |
| `cc.router.profile_ref` | `nullable-Ref` | yes | default null | The model selection profile. Meaning in the [routing contract](model-routing-contract.md#routerport-the-hot-path-seam). |
| `rsi.custodian_key_id` | `nullable-string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$`. Default null. Null means admission refuses every candidate package | ID of the RSI custodian key whose public half is pinned in this file. Admission checks the signatures of referee evidence and session results against it ([D46](../method/decisions.md#d46)). |
| `rsi.custodian_public_key` | `nullable-string` | yes | base64url public key. Default null. Non-null exactly when `rsi.custodian_key_id` is non-null | The public key the operator pins. The private key stays with `rsi_custodian` and `rsi_worker` cannot read it. |
| `codex.route_id` | `string` | yes | default `codex-cli-default` | ID of the fixed Codex route. The bridge writes it as `model_id` in every route record the Codex route answers. |
| `role_aliases` | `object` | yes | one entry per role label. Every value equals `codex.route_id` | Map from a role label (for example `searcher`, `builder`, `verifier`) to a route ID. In M1 every alias names the Codex route. |

**Invariants**

- Every `role_aliases` value equals `codex.route_id`. A role alias never names an API model in M1.
- `cc.router.enabled` is true only when `cc.evaluation_profile_ref` names an approved [evaluation profile](#evaluation-profile) whose `router_enabled` is true. Without a profile it is false. The profile never overrides the file: the two must agree, or startup refuses.
- Only the operator edits this file. A client submission cannot set any `cc.*` key, any `rsi.*` key or any other operator setting. The operator approves the file; each run freezes a snapshot of it ([client submission](#client-submission)).

**Producer obligations (operator)**

- Edit the file on the host and restart the app container. The app never writes the file.
- Keep credentials out of the file. Credentials come from the protected env file ([startup](../platform/README.md#container-startup-ipc-and-storage-obligations)).

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `config_keys_known` | The file holds only the keys above, with the right types | startup refuses with an explicit readiness failure. The app accepts no work |
| `role_aliases_all_codex` | Every `role_aliases` value equals `codex.route_id` | startup refuses with an explicit readiness failure |
| `router_enabled_needs_profile` | `cc.router.enabled` is true only when `cc.evaluation_profile_ref` is non-null, and when it is non-null `cc.router.enabled` equals the profile `router_enabled` | startup refuses with an explicit readiness failure |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| File missing, unreadable or invalid | The app serves readiness failures only and accepts no run | The refusal reason in the readiness report |
| File edited while runs are active | Active runs keep their frozen configuration. The edit applies to the next start | The frozen run configuration |

**Example (YAML, the shipped M1 defaults)**

```yaml
schema_version: "1.0.0"
cc:
  plan_source: static
  plan_policy_ref: {id: plan_policy.json, sha256: "<sha256 of the plan policy>"}
  evaluation_profile_ref: null
  static_template_ref: {id: static_template.json, sha256: "<sha256 of the static template>"}
  router:
    enabled: false
    deadline_s: 30
    profile_ref: null
rsi:
  custodian_key_id: null
  custodian_public_key: null
codex:
  route_id: codex-cli-default
role_aliases:
  searcher: codex-cli-default
  builder: codex-cli-default
  verifier: codex-cli-default
```

**Minimum quality bar.** An operator changes any `cc.*` setting in this one file, and a run records the values it used.

### model-route

`model-route:field-contract:2` is RouteDecision. Its authoritative fields and supporting types are in the [Capsule–routing integration contract](model-routing-contract.md#model-route). Version 1 is historical.

## Library records

These records give a CC version its standing. The RSI records (target profile, session, attempt, feedback, referee evidence, export, session result, candidate package, provenance and security clearance) are on [RSI contracts](rsi-contracts.md).

### library-admission

Purpose: the protected disposition of one candidate CC version. It is the only record that grants standing and pins the check bundle that every run must use with that version.

`library-admission:field-contract:1` (version 1.0.0) · Producer: protected library admission. Consumers: library snapshot, eligibility, human, RSI workbench.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this admission record. |
| `candidate_ref` | `Ref` | yes | the candidate package of an RSI child, or the declaration of a first version | Exact declaration and body package that was assessed. |
| `cc` | `CcPin` | yes | equals the name, version label and digest of the candidate's declaration | Exact CC version this record admits or rejects. |
| `parent_ref` | `nullable-Ref` | yes | null for a first version | Parent CC version this one derives from. Null for a first version. |
| `parent_admission_ref` | `nullable-Ref` | yes | null exactly when `parent_ref` is null. Otherwise a library-admission record with the same `cc.cc_name` | The library-admission record of the parent version. A child copies its check pins from it. |
| `evidence_refs` | `Ref[]` | yes | 1 to 32 items | Independent allowed-change, contract, test and effect checks. |
| `check_pins` | `nullable-CheckPins` | yes | non-null for a version a run plan may bind. For an RSI child, equal to the parent admission `check_pins` | Check bundle and checking profile pinned to this version. The library snapshot copies them. Null means no run plan can use the version. A child gets its parent's pins: its ports and guarantees cannot change ([D34](../method/decisions.md#d34)), so the same bundle and profile apply. |
| `memory_mb` | `nullable-integer` | yes | min 1. Non-null when `check_pins` is non-null | Memory ceiling in MiB for one node attempt of this CC version. The person who runs the admission command sets it, because a declaration carries no memory budget. It must not exceed the plan policy `aggregate_limits.memory_mb`. An RSI child copies its parent value. The library snapshot copies it into `max_limits.memory_mb`. |
| `status` | `string` | yes | enum `admitted`, `rejected`, `blocked` | Disposition. |
| `standing` | `string` | yes | enum `inactive`, `active`, `suspended`, `revoked`. Not `inactive` only when `status` is `admitted` | Current eligibility for future selection. |
| `reasons` | `string[]` | yes | 1 to 20 items | Why this disposition. |

**Enum `status`**

| Value | Meaning |
|---|---|
| `admitted` | The version passed admission and may receive standing |
| `rejected` | The version failed a check. It never gains standing |
| `blocked` | Evidence was missing or unavailable. A new admission record can follow |

**Enum `standing`**

| Value | Meaning |
|---|---|
| `inactive` | Admitted but not selected. RSI children start here |
| `active` | Selected by an activation record, within the `effect_scope` of that record |
| `suspended` | Temporarily not selectable. Running plans keep their pins |
| `revoked` | Permanently not selectable |

**Invariants**

- A `rejected` or `blocked` record has standing `inactive`.
- Standing changes only through an [activation record](#activation-record). The admission record is never edited.
- An RSI score or a producer declaration grants no standing.

**Producer obligations (library admission)**

- Run the independent checks before writing the record. List each one in `evidence_refs`.
- Pin a pre-approved, compatible check bundle before giving a version `check_pins`. M1 bootstrap entries use shared pinned bundles.
- For an RSI child, copy the check bundle and checking profile pins of the parent admission record. Never take pins from the candidate package.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `admission_cc_matches_candidate` | `cc` equals the identity and digest of the candidate's declaration | the record is refused |
| `standing_follows_status` | Standing other than `inactive` needs `status` `admitted` | the record is refused |
| `memory_with_check_pins` | `memory_mb` is non-null when `check_pins` is non-null | the record is refused |
| `child_inherits_parent_check_pins` | A record with a `parent_ref` names a `parent_admission_ref` of the same CC name, and its `check_pins` equal the parent's | the record is refused |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| Missing evidence | `status` `blocked`, standing `inactive` | The record and the reasons |
| A check fails | `status` `rejected`, standing `inactive` | The record, the evidence and the reasons |
| A host check fails | No record is written. The candidate stays in the inbox | The candidate package |

**Examples:** [admitted RSI child, inactive](examples/rsi_admission.json) · [admitted parent, active](examples/rsi_parent_admission.json) · rejected by `child_inherits_parent_check_pins`: [library_admission_invalid_child_pins](examples/library_admission_invalid_child_pins.json) (the child has no pins, its parent has them)

**Minimum quality bar.** A reader can tell from one record which exact CC version may be selected, under which check bundle, and why.

### activation-record

Purpose: the one record of a human change of standing. It moves one admitted CC version to `active`, `suspended` or `revoked`. It is the only way standing changes after admission.

`activation-record:field-contract:1` (version 1.0.0) · Producer: authorized human through the protected library. Consumers: library snapshot builder, RSI workbench sandbox selection, audit.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this activation record. |
| `actor` | `string` | yes | 1 to 120 characters | The authenticated human who moved the standing. |
| `recorded_at` | `string` | yes | UTC time, pattern `YYYY-MM-DDTHH:MM:SSZ` | When the change was made. |
| `cc` | `CcPin` | yes | equals the `cc` of the admission record | The CC version whose standing changes. |
| `admission_ref` | `Ref` | yes | a library-admission record with status `admitted` and non-null `check_pins` | The eligibility basis. |
| `from_standing` | `string` | yes | enum `inactive`, `active`, `suspended`, `revoked` | Standing before this change. |
| `to_standing` | `string` | yes | enum `active`, `suspended`, `revoked`. Never `inactive` | Standing after this change. |
| `reason` | `string` | yes | 1 to 300 characters | Why the human made the change. For a rollback it names the earlier version that is reactivated. |
| `effect_scope` | `string` | yes | enum `rsi_sandbox`, `live_plans`. An RSI child gets `live_plans` only by promotion (`activation_scope_matches_lineage`) | Where the new standing applies. The latest accepted record of a version sets both its standing and its scope. |

**Enum `effect_scope`**

| Value | Meaning |
|---|---|
| `rsi_sandbox` | The version is selectable only in the RSI workbench sandbox. Live plans never see it |
| `live_plans` | The version is eligible for library snapshots captured after this record. A non-RSI version is activated here directly. An RSI child reaches it only by promotion from `rsi_sandbox` |

**Invariants** ([D46](../method/decisions.md#d46))

- A human activation first makes an RSI child `active` for RSI-workbench sandbox selection only (`rsi_sandbox`).
- Activating a child never deactivates the parent. The parent stays `active` and eligible.
- Adopting a child into live runs is manual and takes two human steps. First a human records a promotion: an activation record that moves the active child from `rsi_sandbox` to `live_plans`. Then a human writes a new static template file that pins the child and points the operator config `cc.static_template_ref` at it. Runs frozen before that keep their pins. After promotion the child is in later live snapshots, so the Planner may also choose it.
- To undo an adoption, a human points `cc.static_template_ref` back at the earlier template and suspends the child or records it back at `rsi_sandbox`.
- A rollback is a standing move, not a new version ([D41](../method/decisions.md#d41)). Suspending or revoking a child, or reactivating an earlier version, builds nothing.
- A record never affects a frozen run plan.

**Allowed moves**

| From | To |
|---|---|
| `inactive` | `active`, `revoked` |
| `active` | `suspended`, `revoked`, or `active` only to promote an RSI child from `rsi_sandbox` to `live_plans`, or to move it back |
| `suspended` | `active`, `revoked` |
| `revoked` | none. A revoked version is permanent |

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `activation_target_admitted` | `admission_ref` is a library-admission record with status `admitted`, and its `cc` equals the record `cc` | the record is refused |
| `activation_target_has_check_pins` | That admission record has non-null `check_pins` | the record is refused |
| `activation_transition_allowed` | The pair `from_standing` and `to_standing` is in the table of allowed moves | the record is refused |
| `activation_scope_matches_lineage` | For a version whose admission has a `parent_ref`, a record with `to_standing` `active` and `effect_scope` `live_plans` has `from_standing` `active`: the child was active in the sandbox first. An `active` to `active` record is allowed only for an RSI child | the record is refused |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No standing change. The human sees the reason | The refused record |



**Minimum quality bar.** A reader can tell from one record who moved which version, from which standing to which, where it applies, and on what admitted basis.

## Shared field types

These meanings constrain shared interfaces. Private helper types and classes remain agent choices.

**Conventions for every field table in the package.** A row may say more; it never says less.
- An `id` is set by the record's producer (named on the contract line), is immutable, and is a label: it grants nothing. Consumers locate records by `Ref` (ID plus SHA-256), never by ID alone.
- Every timestamp is UTC in the form `YYYY-MM-DDTHH:MM:SSZ`, written by the component that observed the event.
- Null means unknown or not observed. Null is never zero, never empty and never success. An empty list means none.
- Free-text fields (reasons, messages, rationales, notes, `detail`) are for people and audit. No component parses them or branches on them unless a check row names the field. Text that came from a CC or a model is untrusted data, never instructions.
- `ext` objects carry optional diagnostics. Consumers may ignore them, and they never change a check, verdict or gate decision.
- Units: durations in seconds (`_s`), memory in MiB (`_mb`), sizes in bytes unless a row says otherwise.

Types used by one CC have one home, on that CC page:
- `Citation` and `Idea`: [Search](capsules/search.md#citation).
- `IdeaScore`, `Ranking` and `Disposition`: [Screening](capsules/screening.md#screening_result).
- `ComparisonRule`, `MetricDeclaration` and `OutcomeRule`: [Hypothesis](capsules/hypothesis.md#comparisonrule).
- `PlanNode`, `PlanInput`, `FutureInput` and `PlanOutput`: [Planner](capsules/planner.md#node-fields).

### Ref

| Field | Type | Meaning / why needed |
|---|---|---|
| `id` | `string` | ID of the stored record or file. A path alone does not prove identity. |
| `sha256` | `sha256` | SHA-256 of the exact stored bytes, 64 lowercase hex characters. Compared byte-exact. A mismatch rejects the ref. |

### NodeStatus

| Field | Type | Meaning / why needed |
|---|---|---|
| `node_id` | `string` | Node of the run plan, or `intention_compiler` or `planner` before the plan exists |
| `attempt_id` | `nullable-string` | Latest attempt, null while the node is `Pending` and never dispatched |
| `lifecycle_status` | `string` | Exactly one of `Pending`, `Running`, `Evaluating`, `Completed`, `Failed` ([mapping](#node-lifecycle)) |
| `skipped_because` | `nullable-string` | Node ID of the failed node that made the scheduler skip this node. Null unless the node was skipped ([D49](../method/decisions.md#d49)). A skipped node shows `Failed` |

### NamedFile

| Field | Type | Meaning / why needed |
|---|---|---|
| `path` | `string` | Descriptive relative path, confined to the returned file set. A path escape is rejected. |
| `artifact_ref` | `Ref` | Exact content identity of the file. Consumers fetch the bytes by this ref, not by path. |
| `media_type` | `string` | Format of the file, readable or binary, for example `text/plain`. |
| `audience` | `string` | One of `researcher` (the requesting user) or `reviewer` (the requesting user plus authorized reviewers), the same values as the Delivery file audience. Retrieval withholds the file from anyone outside it. |

### MissingEvidence

| Field | Type | Meaning / why needed |
|---|---|---|
| `obligation_id` | `string` | ID of what was expected and is absent: a Brief evidence obligation, deliverable or mandatory requirement ID, or else the contract name of the missing record, for example `delivery-manifest`. |
| `reason` | `string` | Why it is unavailable or not yet produced. |
| `blocking` | `boolean` | True when the absence prevents release. False when it is only reported. |

### Limits

| Field | Type | Meaning / why needed |
|---|---|---|
| `time_s` | `number` | Elapsed-time cap in seconds. Positive. |
| `model_calls` | `integer` | Cap on model calls. 0 or more. 0 allows no model call. |
| `memory_mb` | `integer` | Memory cap in mebibytes (1 MiB = 1,048,576 bytes), the unit Docker memory limits use. Positive. |

### ModelIdentity

| Field | Type | Meaning / why needed |
|---|---|---|
| `requested` | `string` | Model ID the call asked for. It equals the route record `model_id`. |
| `effective` | `nullable-string` | Model the provider reported using. Null when the actual identity is unavailable. |
| `basis` | `string` | Short statement of how `effective` was established, or why it is null. |

### RSIPair

| Field | Type | Meaning / why needed |
|---|---|---|
| `split` | `string` | Identity of the target `hidden_loop` or `hidden_final` split. A partition identity, not a case ID. Never shown to the proposer. |
| `parent_passed` | `integer` | Count of fixture units the parent passed in this split. Aggregate only. |
| `child_passed` | `integer` | Count of fixture units the child passed in this split. Aggregate only. |
| `total` | `integer` | Number of fixture units in the split. The same for parent and child. |
| `parent_time_s` | `number[]` | Paired batch durations of the parent, in seconds. Paired with `child_time_s`. |
| `child_time_s` | `number[]` | Paired batch durations of the child, in seconds. Paired with `parent_time_s`. |

### RSIScore

| Field | Type | Meaning / why needed |
|---|---|---|
| `primary` | `string` | Always `passed_test_count`. The count of passed tests decides first. |
| `secondary` | `string` | Always `paired_time_at_equal_counts`. Timing counts only when pass counts are equal. |
| `warmup_batches` | `integer` | Warm-up batches run before timing. Fixed at 5. |
| `paired_rounds` | `integer` | Paired timing rounds, run in alternating order. Fixed at 7. |
| `min_relative_gain` | `number` | Smallest relative timing gain, as a fraction, that can qualify a child on timing. Frozen. |
| `noise_multiplier` | `number` | The timing gain must exceed this multiple of `calibrated_relative_noise`. Frozen. |
| `batch_iterations` | `integer` | Iterations in each timed helper batch. The same for parent and child. |
| `calibrated_relative_noise` | `number` | Timing noise measured by calibration before the session, as a fraction. Not measured on the child. |

### SplitIdentities

| Field | Type | Meaning / why needed |
|---|---|---|
| `development` | `string` | Identity of the visible partition the proposer may see. |
| `hidden_loop` | `string` | Identity of the hidden loop partition. Known only to the custodian. Never shown to the proposer. |
| `hidden_final` | `string` | Identity of the hidden final partition. Known only to the custodian. Never shown to the proposer. Read once per session. |
| `platform` | `string` | Identity of the partition the platform uses for evaluation outside the RSI loop. All four identities differ. |

### Prerequisite

| Field | Type | Meaning / why needed |
|---|---|---|
| `name` | `string` | Which prerequisite this is: storage, auth, model or isolation. |
| `status` | `string` | `ready`, `unavailable` or `failed`. A mandatory prerequisite must be `ready` for the report `ready` to be true. |
| `reason` | `string` | Observed basis for the status, in actionable words. Never a secret value. |

### Usage

| Field | Type | Meaning / why needed |
|---|---|---|
| `input_tokens` | `nullable-integer` | Input tokens the provider reported. Null means not observed. Null is never zero. |
| `output_tokens` | `nullable-integer` | Output tokens the provider reported. Null means not observed. Null is never zero. |
| `cost_amount` | `nullable-number` | Cost the provider reported, in `currency`. Null when unavailable. Never an estimate. |
| `currency` | `nullable-string` | Unit of `cost_amount`, as reported. Null when unavailable. |
| `unavailable_reasons` | `string[]` | Names each null field above and why it is unavailable. |

### BoundNodeInput

| Field | Type | Meaning / why needed |
|---|---|---|
| `name` | `string` | Name of the external input port. Unique in the contract. |
| `contract_id` | `string` | Catalog contract |
| `version` | `string` | Supported contract version |
| `required` | `boolean` | True means the node is not dispatched without a bound ref for this port. |
| `artifact_refs` | `Ref[]` | Exact accepted refs bound to the port. A required port with none is an unbound input and the node is not dispatched. |

### BoundNodeOutput

| Field | Type | Meaning / why needed |
|---|---|---|
| `name` | `string` | Name of the external output port. Unique in the contract. |
| `contract_id` | `string` | Catalog contract |
| `version` | `string` | Supported contract version |
| `required` | `boolean` | True means the node gate does not release the node without this output. |

### NodeSubnodeAssignment

| Field | Type | Meaning / why needed |
|---|---|---|
| `subnode_id` | `string` | Unique child identity |
| `role` | `string` | `work` or `verifier`. The scheduler creates each verifier subnode at dispatch, one per output. |
| `template_ref` | `Ref` | Frozen internal port and checking template |
| `capsule_ref` | `Ref` | Pinned declaration of the one admitted CC version this subnode runs. Equals the `capsule_ref` of its template. |
| `depends_on` | `string[]` | Subnode IDs that must be accepted first, each through its gate. Acyclic. A verifier subnode lists the work subnode it reviews. |
| `required` | `boolean` | True means node completion needs this subnode. |

### NodeGateAssignment

| Field | Type | Meaning / why needed |
|---|---|---|
| `gate_id` | `string` | Protected gate identity |
| `subject_subnode_id` | `string` | Work subnode whose output this gate decision reviews. The final assignment for node release aggregates the node obligations. |
| `profile_ref` | `Ref` | Checking profile giving the criteria (the node finalization profile for node release). Owned independently of the CC. |

### AuthorityCeiling

| Field | Type | Meaning / why needed |
|---|---|---|
| `network` | `string` | `none` or `allowlist`. `none` needs an empty `network_allowlist`. |
| `network_allowlist` | `string[]` | Maximum endpoints the node may reach. Empty when `network` is `none`. |
| `resource_reads` | `Ref[]` | Maximum read scope, as refs. A ceiling, never a grant. |
| `write_roots` | `string[]` | Maximum paths the node may write under. A ceiling, never a grant. |
| `tools` | `string[]` | Maximum admitted tools. A ceiling, never a grant. |
