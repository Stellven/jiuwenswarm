# Checking and protected decision fields

`Tier 3 · Part of: [Reference](README.md)`

[Checking](../checking/README.md) owns the mechanism; [Intent detail](../pipeline/intention-compiler.md) explains its application. Runtime metadata comes from protected capture, not producer assertions.

## Deterministic result

Purpose: the outcome of every mandatory deterministic check of one bound check plan. The gate reads it before any verifier runs.

`deterministic-check-result` (exact [schema](schemas/deterministic-check-result.schema.json), version 1.0.0) · Producer: protected check runner. Consumers: review-context builder, gate host, run bundle.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `subject_ref` | `Ref` | yes | an output of the checked work subnode, or the protected failure receipt when no output exists, or the plan source at the plan gate | Exact subject the checks ran on. For a work subnode with k outputs, it names the output of the first declared output port. Each result's `evidence_refs` names every output that check read. |
| `subject_refs` | `Ref[]` | no; required when the work subnode writes more than one output | 1 or more, in output port order. The first item equals `subject_ref` | Every output the check bundle read in its one run. Each per-output gate decision reviews exactly one of them. Each result's `evidence_refs` still names the outputs that check read. |
| `check_plan_ref` | `Ref` | yes | the bound check plan the runner executed | Which checks were mandatory. |
| `results` | `CheckResult[]` | yes | 1 to 64 items. `check_id` values are unique and equal the plan's `mandatory_deterministic` set | One entry per mandatory check. |
| `ext` | `object` | no | keys match `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$` | Namespaced diagnostic data, written by the check runner. Consumers may ignore it. It never changes meaning, permission, acceptance, check outcomes or gate decisions. |

**CheckResult**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `check_id` | `string` | yes | an ID in the plan's `mandatory_deterministic` | Check that ran. |
| `outcome` | `string` | yes | enum below | Result of the check. |
| `reason` | `string` | yes | at least 1 character | Plain statement of what the check found, for people reading the record. The result is carried by `outcome`, not by this text. |
| `evidence_refs` | `Ref[]` | yes | may be empty only for a check that read no artifact | Exact bytes the check read. |

**Enum `outcome`**

| Value | Meaning |
|---|---|
| `PASS` | The check ran and its rule holds |
| `FAIL` | The check ran and its rule does not hold |
| `ENVIRONMENT_BLOCKED` | The check could not run because a resource, file or service was unavailable |
| `INCONCLUSIVE` | The check ran but could not decide |

**Invariants**

- One result per work subnode attempt. It covers all k outputs, because the check bundle runs once over them.
- Every mandatory ID appears exactly once. An absent check never counts as `PASS`.
- When any mandatory result is not `PASS`, no verifier runs. The gate writes one halting subnode-scope decision with `assessment_ref` null.

**Producer obligations (check runner)**

- Run exactly the checks the bound plan lists, from the pinned implementations in `runner_refs`.
- Record `ENVIRONMENT_BLOCKED` with the reason when a check cannot run. Never skip it.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `results_cover_plan` | The set of `check_id` values equals the plan's `mandatory_deterministic`, with no duplicate | the gate halts the subnode |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A mandatory check is not `PASS` | Halting gate decision. No verifier runs | The result, the candidate outputs and the evidence |
| A mandatory check is missing | Halting gate decision | The result and the plan |
| The runner crashes | The dispatch record outcome is `failed` | Everything stored so far |

**Examples:** [Intent checks](examples/intent_checks.json) · [science checks](examples/science_checks.json)

**Minimum quality bar.** A reviewer can see, for every mandatory check, what it read and why it passed or failed, without rerunning it.

## Verifier assessment

Semantic source: independently assigned read-only verifier CC. Assessment producer/consumer: trusted host gate. [Schema](schemas/verifier-assessment.schema.json) remains the persisted record; no schema change is implied.

The semantic model receives exactly two reviewed artifacts: the pinned subject CC declaration and the exact output bytes. It also receives fixed verifier instructions. It receives no worker input, request-specific context, conversation, review manifest, profile/criteria record, runtime observation, predecessor artifact or evidence-fetch capability. Its reply is untrusted finding/uncertainty/limitation content only; it does not supply trusted identity, evidence references or gate authority. The host validates the required criterion set and assembles this existing persisted record from that reply and protected records.

The unchanged persisted record requires `schema_version`, exact `subject_ref`, `review_context_ref`, `verdict`, nonempty `findings`, `uncertainties`, `limitations`, nullable `required_correction`. Each finding has `criterion_id`, `outcome`, `reason`, nonempty `evidence_refs`. Cover every required criterion exactly once. The host owns identity/context refs, evidence refs, and verdict; references attached by the host must not imply that hidden evidence was semantically reviewed. Findings identify the declaration/output basis and limitations, not replacement work. No new public reply schema is introduced.

Assessment verdicts use the PRD outcome vocabulary: `PASS`, `PASS_WITH_KNOWN_LIMITATIONS`, `FAIL`, `ENVIRONMENT_BLOCKED`, `INCONCLUSIVE`. They are checking data, not control actions. Mandatory failure or unresolved uncertainty cannot accompany an advancing assessment. Known limitations can advance only when no mandatory obligation is unsatisfied. Missing required evidence means unavailable/inconclusive, not inferred success.

The host-only, audit-only review manifest binds subject, original/accepted inputs, owning node and subject subnode contracts, CC/dependency pins, assigned criteria/profile, policy, deterministic results, observations and allowed evidence audience. It is retained for deterministic checking, provenance and gate assembly, but is not sent to the semantic model. The verifier cannot access any of those records beyond the two-artifact projection and cannot fetch evidence or mutate outputs. Fidelity and preservation are producer obligations backed by deterministic host checks. Tier 2 does not assess them. See the [Verifier page](capsules/verifier.md).

## Gate decision

Purpose: the protected decision that releases or halts work. There is one per output of a work subnode, and one node-scope decision per node attempt.

`gate-decision` (exact [schema](schemas/gate-decision.schema.json), version 2.0.0) · Producer: protected gate host. Consumers: durable run state, scheduler, dispatch record, run bundle, inspection and export.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version. Reject any other value. |
| `id` | `string` | yes | at least 1 character, unique in the run | Immutable decision ID. |
| `recorded_at` | `string` | yes | UTC date-time | When the gate host stored the decision. The gate host sets it from its own clock, in UTC. A CC or client value is never used. |
| `run_id` | `string` | yes | the run of the attempt | Run scope. |
| `node_id` | `string` | yes | a node of the run plan, or `intention_compiler` or `planner` | Node scope. |
| `attempt_id` | `string` | yes | `<node_id>-a<attempt>`, equal to the dispatch record | Attempt scope. |
| `scope_kind` | `string` | yes | enum, see below | Whether the decision reviews one output or the whole node. |
| `subnode_id` | `nullable-string` | yes | the work subnode ID when `scope_kind` is `subnode`. Null when `node` | Work subnode reviewed. |
| `output_port` | `nullable-string` | no. Required on an advancing subnode-scope decision | pattern `^[a-z][a-z0-9_]{0,63}$`. Null on a node-scope decision and on a halt with no output | Output port this decision reviews. One decision per output. |
| `contract_ref` | `Ref` | yes | the work Subnode Execution Contract (subnode scope), or the node contract equal to `node_contract_ref` (node scope) | Contract the decision checked. |
| `node_contract_ref` | `Ref` | yes | the Node Execution Contract of this attempt | Owning node contract. |
| `invocation_refs` | `Ref[]` | yes | at least 1 for `advance`. May be empty for a halt before dispatch | Observed invocations of the reviewed work. |
| `internal_decision_refs` | `Ref[]` | yes | the per-output decisions for node scope. Empty for subnode scope | Decisions the node-scope decision aggregates. |
| `policy_ref` | `Ref` | yes | the run policy | Fixed authority and obligations. |
| `check_plan_ref` | `Ref` | yes | the bound check plan of this scope | Which checks and criteria were mandatory. |
| `input_refs` | `Ref[]` | yes | may be empty | Exact accepted inputs. |
| `output_refs` | `Ref[]` | yes | at least 1 for `advance`. Exactly 1 on an advancing subnode-scope decision | Exact reviewed outputs. |
| `deterministic_result_ref` | `Ref` | yes | the deterministic result of `check_plan_ref` | Tier 1 result. |
| `assessment_ref` | `nullable-Ref` | yes | non-null for `advance`. Null when Tier 1 stopped review | Tier 2 verifier assessment. |
| `verdict` | `string` | yes | enum, see below. `PASS` or `PASS_WITH_KNOWN_LIMITATIONS` exactly for `advance` | Protected verdict, set by the gate host from the checking records. A CC or verifier cannot set it. It is a checking verdict, never a copy of the scientific `evaluation_verdict`. |
| `reasons` | `Reason[]` | yes | at least 1 | Why, with criterion IDs and evidence. The gate host writes it from protected records, for people and audit. The decision itself is carried by `verdict` and `action`. |
| `action` | `string` | yes | enum, see below | Control action, set by the gate host. It follows `verdict`: `advance` exactly when the verdict is `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`. |
| `accepted_refs` | `Ref[]` | yes | at least 1 and a subset of `output_refs` for `advance`. Empty for `halt` | Outputs released to the next nodes. |
| `ext` | `object` | no | keys match `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$` | Namespaced diagnostic data, written by the gate host. Consumers may ignore it. It never changes meaning, authority, the verdict, the action or any later gate decision. |

**Reason**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `code` | `string` | yes | at least 1 character | Stable reason code, for example a failing check ID. |
| `message` | `string` | yes | at least 1 character | Plain explanation for people, written by the gate host. Display and audit only: no component parses it or branches on it. The reason `code` is the stable key. |
| `criterion_ids` | `string[]` | yes | may be empty | Criteria the reason concerns. |
| `evidence_refs` | `Ref[]` | yes | may be empty | Evidence the reason rests on. |

**Enum `verdict`**

| Value | Meaning | Advances |
|---|---|---|
| `PASS` | Every mandatory check and criterion passed | yes |
| `PASS_WITH_KNOWN_LIMITATIONS` | Every mandatory obligation passed. Known limitations are recorded | yes |
| `FAIL` | A mandatory check or criterion failed. The node fails and an escalation record is written for later review ([D49](../method/decisions.md#d49), [D50](../method/decisions.md#d50)) | no |
| `ENVIRONMENT_BLOCKED` | A check or the verifier could not run. The node fails and an escalation record is written | no |
| `INCONCLUSIVE` | The evidence cannot decide. The node fails and an escalation record is written | no |

**Enum `action`**

| Value | Meaning |
|---|---|
| `advance` | Release `accepted_refs` after durable storage |
| `halt` | Release nothing. The node halts with reasons and evidence |

**Enum `scope_kind`**

| Value | Meaning |
|---|---|
| `subnode` | Reviews one output of one work subnode |
| `node` | Aggregates the per-output decisions of the node attempt |

**Scope rules**

| Field | Node scope | Subnode scope, per output |
|---|---|---|
| `subnode_id` | null | the work subnode ID |
| `output_port` | null | the reviewed port. Null only on a halt with no output |
| `contract_ref` | equals `node_contract_ref` | the work subnode contract |
| `output_refs`, `accepted_refs` | all outputs of the node | that one output |
| `assessment_ref` | the assessment of the first declared output | the assessment of that output |
| `internal_decision_refs` | the per-output decisions | empty |

The values each field takes at dispatch are in [from run plan node to execution contracts](run-plan.md#from-run-plan-node-to-execution-contracts).

**Invariants**

- `action` is `advance` exactly when `verdict` is `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`.
- An advancing decision has an assessment, at least one invocation and accepted refs that are reviewed outputs.
- A halt publishes no accepted refs.
- A node-scope decision advances only when every per-output decision in `internal_decision_refs` advances.

**Producer obligations (gate host)**

- Build the decision from protected records only: the bound check plan, the deterministic result, the assessment and the observations.
- Store the artifacts and the decision before the accepted-output commit. A decision file alone is not a commit.
- Never copy a scientific verdict into the gate verdict.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `gate_decision_schema` | The decision validates against the schema | the decision is not stored and the node halts |
| `verdict_action_consistent` | The invariants above hold, an advancing subnode-scope decision names one `output_port` and one output, and a node-scope decision has null `output_port` and `subnode_id` | the decision is not stored and the node halts |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No decision is stored. The node halts | The candidate outputs and the checking records |
| Storage of outputs or the decision fails | Readiness stays blocked, even after a passing assessment | The decision draft and the evidence |
| The verifier is missing on a mandatory branch | `halt` | The checking records |

**Examples:** [subnode advance](examples/gate_decision.json) · [node-scope advance](examples/gate_science_node_pass.json) · rejected by `verdict_action_consistent`: [gate_decision_invalid_advance_on_fail](examples/gate_decision_invalid_advance_on_fail.json) (action `advance` with verdict `FAIL`)

**Minimum quality bar.** A reader can tell from one decision what was reviewed, under which checks, and why it advanced or halted.

The host validates assessment structure, source/subject/context binding, criterion coverage and consistency with deterministic results. Every mandatory obligation must pass. Advancing verdicts are only `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`; all other outcomes halt. Producer/verifier readiness, instructions or a matching JSON shape grant no control authority.

Accepted references must be the exact reviewed output subset fulfilling required node outputs. Persist immutable artifacts and decision before the accepted-output commit becomes scheduler readiness. A proposed decision file is not a successful database commit. Persistence failure keeps readiness blocked, even if an assessment passed. New attempts/policy/subjects need new decisions.

Scientific `evaluation_verdict.json` has its own classification and measurement-to-criterion rationale. It is never copied into the gate verdict as an automatic halt. Valid scientific `FAIL` can be reviewed as conformant and yield infrastructure `PASS` for Delivery.

## One work subnode: checks once, then one decision per output

A work subnode runs one work CC that writes k outputs. Checking follows PRD §4.2 tier precedence:

1. The check runner runs the pinned check bundle once, over all k outputs together. That gives one bound check plan and one deterministic result per work subnode. A check that compares two outputs, such as Delivery's `ref_hash_match`, counts for every output it reads.
2. If any mandatory check does not `PASS`, no verifier runs for any output. The gate writes one halting subnode-scope decision with `assessment_ref` null.
3. If every mandatory check passes, one verifier subnode runs per output. Each sees only the declaration and that one output.
4. The gate writes one subnode-scope decision per output. `output_port` names the reviewed port, and `output_refs` holds exactly that output. Every per-output decision cites the same deterministic result.
5. The node-scope decision lists the per-output decisions in `internal_decision_refs`. It advances only when every one of them advances.

`output_port` is a field of gate decision 2.0.0. It is required on an advancing subnode-scope decision. It is null on a node-scope decision and on a halt that has no output.

## PRD minimum gate result

PRD §4.2 lists a minimum gate result. Each of its fields is filled from the gate decision and its checking records, so no second record is kept. The gate host builds this view for inspection and export.

| PRD field | Source |
|---|---|
| `run_id`, `stage_id` | `run_id`, `node_id` |
| `gate_verdict` | `verdict` |
| `normalized_verdict` | PRD mapping: `PASS` and `PASS_WITH_KNOWN_LIMITATIONS` → `PASS`. `FAIL` → `FAIL`. `ENVIRONMENT_BLOCKED` → `BLOCKED`. `INCONCLUSIVE` → `INCONCLUSIVE`. |
| `routing_action` | `advance` → `ADVANCE`. A halt with verdict `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE` → `ESCALATE_TO_HUMAN`: the gate host writes an escalation record (this gate decision and this view, listed for review in inspection). It never waits for a reply, and the scheduler continues with independent nodes ([D49](../method/decisions.md#d49), [D50](../method/decisions.md#d50)). Any other halt → `HALT`. Human corrections start linked new work. |
| `tier_1.status`, `tier_1.checks` | From the deterministic result. `PASS` when every mandatory check passes, `BLOCKED` when one is `ENVIRONMENT_BLOCKED`, otherwise `FAIL`. |
| `tier_2.status`, `reasons`, `evidence_refs` | From the verifier assessment. `NOT_RUN` when `assessment_ref` is null. |
| `failed_checks`, `warnings`, `known_limitations` | The failing mandatory check IDs; the non-blocking check results and findings that did not pass; the assessment `limitations` |
| `evidence_refs`, `timestamp` | All evidence refs of the decision, and `recorded_at` |

## Node finalization profile

Purpose: the checking profile of a whole node. It lists the node checks and says the node gate reuses an accepted assessment. Node finalization adds no semantic model call.

`node-finalization-profile:field-contract:2` (version 2.0.0) · Producer: protected configuration owner. Consumers: scheduler, node gate, check runner. The Node Execution Contract names it in `checking_profile_ref`.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version 2.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this profile. |
| `mandatory_deterministic` | `string[]` | yes | 1 to 8 items, unique, each pattern `^[a-z][a-z0-9_]{0,63}$` | Node check IDs that must each pass once before the node gate decision. M1 lists `internal_acceptance`, `external_output` and `aggregate_limits`. |
| `semantic_assessment_reuse` | `string` | yes | an ID from the node contract `evidence_obligations` | Evidence obligation whose accepted verifier assessment the node gate reuses instead of asking for a new one. |
| `additional_model_calls` | `integer` | yes | exactly 0 in M1 | Model calls node finalization may add. Node finalization makes no semantic call. |
| `synthetic` | `boolean` | no | absent in a real record | Marks an example record. A real record leaves it out. |

**Examples:** [valid](examples/node_finalization_profile.json)

## Subnode versus node release

Gate `2.0.0` explicitly names `scope_kind` (`subnode` or `node`), owning `node_contract_ref` and nullable `subnode_id`. Subnode gates review work under a concrete Subnode Execution Contract; final node release reviews the external Brief and required internal acceptance. `internal_decision_refs` connects the two scopes. No second interpretation or extra semantic call is required for final aggregation. Trusted records bind the producing/subject scope; schemas alone cannot establish authorship.

A halt may have empty output/invocation inventories when no output or dispatch occurred. Its deterministic subject is the protected failure receipt/checking manifest, with real reasons and evidence, not a fabricated candidate. Advancing decisions still need actual output, observations, complete checks/assessment and durable acceptance. A cancelled/missing verifier on a mandatory branch cannot release work.
