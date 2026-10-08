# Named shared field contracts

**AI reference.** [Machine inventory](field-contracts.json) and this generated view define field spelling, types and requiredness. [Other contracts](other-contracts.md) define behavior. Selected exact schemas take precedence for their types. All interface fields below are required unless marked optional; empty arrays mean explicitly none, not success. Version is `1.0.0`. Closed core plus optional namespaced `ext` prevents silent inventions. Shared implementations must realize one version; private internal records remain unconstrained.

`Ref` identifies exact immutable bytes through a protected manifest. `nullable-*` requires a present null with an explained absence where relevant. Numbers must be finite; timestamps are UTC; hashes are lowercase SHA-256. Arrays preserve typed items. Referenced records must satisfy expected catalog type, audience and scope, not merely exist. Bodies are human-readable; runtime envelopes and acceptance records are trusted infrastructure outputs.

## Planning and node contracts

### qualified-intake

`qualified-intake:field-contract:1` · protected intake → Intent CC, Requirements CC.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `request_ref` | `Ref` | Exact original text |
| `source_refs` | `Ref[]` | Permitted extracted text |
| `offset_basis` | `string` | Unicode code points |
| `resource_refs` | `Ref[]` | Qualified supplied assets |
| `rejected_inputs` | `string[]` | Rejected/skipped items and reasons |

**Invalid/missing behavior:** Reject missing required source or undecodable text; do not silently treat a rejected resource as available.

### resource-snapshot

`resource-snapshot:field-contract:1` · protected resolver → Hypothesis, Builder, Benchmark.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `kind` | `string` | Resource kind |
| `origin` | `string` | Original locator |
| `revision` | `string` | Captured immutable revision |
| `files` | `NamedFile[]` | Captured contents |
| `access` | `string` | Permitted use |
| `license` | `string` | Known license or explicit unknown |
| `availability` | `string` | available or unavailable |
| `environment_ref` | `nullable-Ref` | Prepared compatible environment lock |

**Invalid/missing behavior:** Unavailable mandatory data blocks; mutable locator alone is not a reproducible identity.

### environment-lock

`environment-lock:field-contract:1` · protected environment preparation → Hypothesis, Builder, provisioner.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `platform` | `string` | Exact supported environment |
| `requirements_ref` | `Ref` | Complete direct/transitive pinned declaration |
| `package_refs` | `Ref[]` | Reviewed immutable package bytes |
| `approval_ref` | `Ref` | Protected preparation decision |

**Invalid/missing behavior:** Reject unpinned/unavailable packages, incompatible platform or altered lock; no dynamic resolution.

### plan-proposal

`plan-proposal:field-contract:1` · static template or bounded planner → binder, plan checking.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `brief_ref` | `Ref` | Accepted governing Brief |
| `library_snapshot_ref` | `Ref` | Eligible version snapshot |
| `mode` | `string` | static or bounded planning |
| `nodes` | `PlanNode[]` | Proposed bounded graph |
| `limits` | `Limits` | Aggregate proposed bounds |
| `additional_checks` | `string[]` | Extra checks, never waiver |

**Invalid/missing behavior:** Reject cycles, missing Brief coverage, incompatible ports or denied effects; proposal grants no authority.

### frozen-graph

`frozen-graph:field-contract:1` · protected freeze → scheduler, binder.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `proposal_ref` | `Ref` | Checked plan |
| `decision_ref` | `Ref` | Committed acceptance |
| `node_template_refs` | `Ref[]` | Pinned node templates |
| `policy_ref` | `Ref` | Effective policy |
| `configuration_ref` | `Ref` | Frozen run configuration |
| `library_snapshot_ref` | `Ref` | Pinned eligible versions |
| `limits` | `Limits` | Aggregate limits |

**Invalid/missing behavior:** Missing commit/pins/compatibility blocks dispatch; template future values are not observed artifacts.

### bound-check-plan

`bound-check-plan:field-contract:1` · protected guard resolver → checks, review builder, gate.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `contract_ref` | `Ref` | Final concrete node contract |
| `input_refs` | `Ref[]` | Exact bound inputs |
| `profile_ref` | `Ref` | Independently owned guard profile |
| `policy_ref` | `Ref` | Frozen policy |
| `mandatory_deterministic` | `string[]` | Unique mandatory check IDs |
| `mandatory_semantic` | `string[]` | Unique mandatory criterion IDs |
| `runner_refs` | `Ref[]` | Pinned check and verifier implementations |

**Invalid/missing behavior:** Reject missing assignments, mutable runner identities or hash cycles. Producer suggestions cannot replace mandatory criteria.

## Research artifacts

### candidate-set

`candidate-set:field-contract:1` · Search and Ideation CC → Screening, checking.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `brief_ref` | `Ref` | Governing accepted requirements |
| `queries` | `string[]` | Fixed retrieval queries |
| `citations` | `Citation[]` | Captured source evidence |
| `ideas` | `Idea[]` | One to three grounded candidates |

**Invalid/missing behavior:** Missing grounding, unresolved citation or unsupported claims block; bounded retrieval cannot repair itself.

### screening-result

`screening-result:field-contract:1` · Screening CC and deterministic helper → selection, checking, RSI.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `candidate_ref` | `Ref` | Exact candidate set |
| `brief_ref` | `Ref` | Accepted requirements |
| `rubric_ref` | `Ref` | Frozen work scoring policy |
| `scores` | `IdeaScore[]` | One assessment per idea |
| `ranking` | `Ranking[]` | Eligible sum order with stable ID ties |
| `selected_idea_id` | `string` | Exactly one Top-1 |

**Invalid/missing behavior:** Missing/duplicate/out-of-range scores or no eligible idea block; do not impute or invent an alternative.

### opportunity-card

`opportunity-card:field-contract:1` · Screening CC → Hypothesis, checking.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `candidate_ref` | `Ref` | Grounded set |
| `screening_ref` | `Ref` | Checked scoring/ranking |
| `brief_ref` | `Ref` | User obligations |
| `idea_id` | `string` | Existing selected ID |
| `title` | `string` | Readable title |
| `opportunity_statement` | `string` | Bottleneck and mechanism |
| `citation_ids` | `string[]` | Supporting citations |
| `constraints` | `string[]` | Applicable requirements |
| `assumptions` | `string[]` | Unproven premises |
| `risks` | `string[]` | Known concerns |

**Invalid/missing behavior:** Selected ID must equal ranking Top-1 and exist in candidates; unsupported mechanism or lost constraints blocks.

### hypothesis-blueprint

`hypothesis-blueprint:field-contract:1` · Hypothesis CC → Builder, Benchmark, Evaluation, checking.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `brief_ref` | `Ref` | Accepted requirements |
| `opportunity_ref` | `Ref` | Accepted opportunity |
| `claim` | `string` | One testable claim |
| `mechanism` | `string` | Proposed causal mechanism |
| `independent_variable` | `string` | Treatment intervention |
| `dependent_variables` | `string[]` | Registered measurements |
| `resource_refs` | `Ref[]` | Captured baseline/data |
| `environment_ref` | `Ref` | Selected prepared lock |
| `metrics` | `MetricRule[]` | Success/negative/middle rules fixed before results |
| `repeat_count` | `integer` | Positive repetitions |
| `seed` | `integer` | Registered seed |
| `implementation_scope` | `string` | Bounded allowed change |
| `constraints` | `string[]` | Preserved requirements |
| `verification_plan` | `string[]` | Required evidence checks |

**Invalid/missing behavior:** Missing resources, lock, measurable rules or full classification blocks Builder. Protocol cannot change after measurements.

### poc-manifest

`poc-manifest:field-contract:1` · Builder CC with trusted capture → Benchmark, checking, Delivery.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `blueprint_ref` | `Ref` | Frozen protocol |
| `environment_ref` | `Ref` | Exact unchanged prepared lock |
| `archive_ref` | `Ref` | Separate executable bundle |
| `files` | `NamedFile[]` | Required scripts/declaration |
| `mechanical_evidence_refs` | `Ref[]` | Syntax/forbidden-module/package checks |

**Invalid/missing behavior:** No scientific trial/install in Builder. Missing script, traversal, lock mutation or undeclared dependency blocks.

### benchmark-payload

`benchmark-payload:field-contract:1` · Benchmark with protected provisioner/executor → Evaluation, checking, Delivery.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `blueprint_ref` | `Ref` | Frozen criteria |
| `poc_ref` | `Ref` | Checked package |
| `resource_refs` | `Ref[]` | Exact baseline/data |
| `configuration_ref` | `Ref` | Observed fixed hardware/runtime |
| `baseline_execution_ref` | `Ref` | Unmodified baseline first |
| `treatment_execution_ref` | `Ref` | Matched treatment second |
| `metrics` | `MetricObservation[]` | All registered raw and aggregate values |
| `raw_evidence_refs` | `Ref[]` | Empirical repeats/stdout/stderr |
| `provisioning_ref` | `Ref` | Exact lock installation and limits |
| `missing_evidence` | `MissingEvidence[]` | Unmeasured/error reasons |

**Invalid/missing behavior:** Incomplete mandatory metric, changed baseline or unmatched settings blocks scientific evaluation; no fabricated values.

### evaluation-verdict

`evaluation-verdict:field-contract:1` · Scientific Evaluation CC → Delivery, checking.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `brief_ref` | `Ref` | Preserved objective |
| `blueprint_ref` | `Ref` | Predeclared rules |
| `benchmark_ref` | `Ref` | Exact measurements |
| `classification` | `string` | PASS/FAIL/INCONCLUSIVE/CONDITIONALLY_ACCEPTABLE |
| `findings` | `MetricFinding[]` | Every registered metric rationale |
| `limitations` | `string[]` | Interpretive limits |
| `blockers` | `string[]` | Missing scientific basis |
| `followups` | `string[]` | Recommendations, not reruns |

**Invalid/missing behavior:** Apply registered rules; scientific FAIL is valid when supported. Conditional acceptance requires preregistration. No control-flow action field.

### delivery-manifest

`delivery-manifest:field-contract:1` · Delivery CC with trusted export → user, checking, client.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `brief_ref` | `Ref` | Objective |
| `verdict_ref` | `Ref` | Accepted scientific classification |
| `report_ref` | `Ref` | Readable narrative report |
| `artifact_refs` | `Ref[]` | Reproducible lifecycle records |
| `files` | `NamedFile[]` | Exact exported content and audience |
| `missing_evidence` | `MissingEvidence[]` | Omissions/redactions |

**Invalid/missing behavior:** Contradiction with verdict, missing mandatory content or unauthorized disclosure blocks release/export.

## Manifest and runtime records

### artifact-envelope

`artifact-envelope:field-contract:1` · trusted capture → checking, export, runner.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `contract_id` | `string` | Catalog payload contract |
| `payload_ref` | `Ref` | Exact body |
| `media_type` | `string` | Readable descriptive format |
| `run_id` | `string` | Trusted run scope |
| `node_id` | `string` | Trusted node scope |
| `attempt_id` | `string` | Trusted attempt |
| `invocation_ref` | `Ref` | Observed producer |
| `source_refs` | `Ref[]` | Original/accepted source chain |
| `audience` | `string` | Allowed readers |

**Invalid/missing behavior:** CC-authored metadata is untrusted; mismatched type/hash/scope blocks. Envelope does not establish acceptance.

### invocation-observation

`invocation-observation:field-contract:1` · protected runner → gate, review, Run Bundle.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `contract_ref` | `Ref` | Concrete node |
| `binding_id` | `string` | Participating binding |
| `input_refs` | `Ref[]` | Exact supplied inputs |
| `output_refs` | `Ref[]` | Captured candidates |
| `model_identity` | `ModelIdentity` | Requested/effective routing |
| `started_at` | `nullable-string` | Observed timestamp |
| `ended_at` | `nullable-string` | Observed timestamp |
| `outcome` | `string` | Observed completion/failure, or synthetic illustration |
| `effects` | `string[]` | Observed effects/tools |
| `duration_s` | `nullable-number` | Actual time or unavailable |
| `model_calls` | `nullable-integer` | Actual calls or unavailable |
| `usage` | `Usage` | Available token/cost telemetry; explicit nulls and reasons |
| `trace_refs` | `Ref[]` | Raw evidence |
| `unavailable_reasons` | `string[]` | Unsupported telemetry |
| `observed_runtime` | `boolean` | False only in synthetic teaching examples |

**Invalid/missing behavior:** Missing mandatory observations block release; optional telemetry stays unavailable. Synthetic illustrations cannot certify runtime work.

### review-context

`review-context:field-contract:1` · protected context builder → read-only verifier.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `subject_ref` | `Ref` | Exact candidate |
| `contract_ref` | `Ref` | Work obligations |
| `check_plan_ref` | `Ref` | Bound independent assignment |
| `input_refs` | `Ref[]` | Accepted/original evidence |
| `deterministic_result_ref` | `Ref` | Passed structural checks |
| `criteria` | `string[]` | Mandatory semantic obligations |
| `observations` | `Ref[]` | Runner evidence |
| `evidence_classes` | `string[]` | Protected policy/accepted input/observed evidence/untrusted producer |

**Invalid/missing behavior:** Incomplete/stale context blocks assessment/release; artifact instructions remain untrusted data.

### accepted-output

`accepted-output:field-contract:1` · protected durable state → scheduler, client.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `run_id` | `string` | Run scope |
| `node_id` | `string` | Node scope |
| `attempt_id` | `string` | Attempt scope |
| `gate_ref` | `Ref` | Committed protected decision |
| `contract_ref` | `Ref` | Same concrete contract |
| `output_refs` | `Ref[]` | Exact accepted bytes |
| `commit_id` | `string` | Durable transaction identity |

**Invalid/missing behavior:** Created only after artifact/decision persistence. File presence or verifier PASS cannot create acceptance.

### run-bundle

`run-bundle:field-contract:1` · protected evidence builder → inspection, authorized export.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `run_id` | `string` | Run scope |
| `status` | `string` | In-progress/completed/halted/paused |
| `configuration_ref` | `Ref` | Requested/effective pins |
| `artifact_refs` | `Ref[]` | Candidate/accepted records |
| `decision_refs` | `Ref[]` | Protected decisions |
| `observation_refs` | `Ref[]` | Actual execution evidence |
| `missing_evidence` | `MissingEvidence[]` | Not-produced or unavailable items |
| `redactions` | `string[]` | Audience omissions |

**Invalid/missing behavior:** Incomplete export cannot claim completion. Derived bundle never replaces durable state.

### scorecard

`scorecard:field-contract:1` · derived observation builder → analysis, planner.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `capsule_ref` | `Ref` | Exact admitted version |
| `observation_refs` | `Ref[]` | Source samples |
| `sample_count` | `integer` | Observed sample size |
| `window` | `string` | Sample time/scope |
| `outcomes` | `string[]` | Measured outcomes/failure counts |
| `unavailable_reasons` | `string[]` | Unmeasured quality/cost |

**Invalid/missing behavior:** No samples means unavailable quality. Regeneration does not change gate history.

## Client and model boundaries

### client-readiness

`client-readiness:field-contract:1` · application → browser, CLI, benchmarker, sidecar.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `client_contract_version` | `string` | Negotiated interface |
| `instance_id` | `string` | Target instance |
| `build_id` | `string` | Application build |
| `operations` | `string[]` | Supported actions |
| `prerequisites` | `Prerequisite[]` | Storage/auth/model/isolation state with reason |
| `ready` | `boolean` | Required prerequisites available |

**Invalid/missing behavior:** Wrong target/version or mandatory unavailable prerequisite blocks submission; liveness alone is insufficient.

### client-submission

`client-submission:field-contract:1` · scoped client → control plane.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `client_request_id` | `string` | Idempotent submission identity |
| `workspace_id` | `string` | Authorized scope |
| `account_id` | `string` | Authenticated actor |
| `intake_ref` | `Ref` | Qualified request/resources |
| `configuration_ref` | `Ref` | Approved profile/mode/seed |

**Invalid/missing behavior:** Reconcile uncertain delivery by request identity before resubmission. Do not replay capsule work.

### client-status

`client-status:field-contract:1` · control plane → clients.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `client_request_id` | `string` | Reconciliation identity |
| `run_id` | `nullable-string` | Allocated run or unavailable |
| `revision` | `integer` | Monotonic state revision |
| `stage` | `string` | Current phase/stage |
| `status` | `string` | Completion/halt/cancel/pause/in-progress |
| `candidate_refs` | `Ref[]` | Unaccepted outputs |
| `accepted_refs` | `Ref[]` | Committed accepted outputs |
| `decision_ref` | `nullable-Ref` | Last decision |
| `reasons` | `string[]` | Visible explanation |
| `bundle_ref` | `nullable-Ref` | Available export |

**Invalid/missing behavior:** Disconnection does not cancel; malformed or stale status is unavailable, not accepted completion.

### client-retrieval

`client-retrieval:field-contract:1` · scoped client and application → inspection, export.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `run_id` | `string` | Authorized run |
| `artifact_refs` | `Ref[]` | Requested/returned identities |
| `audience` | `string` | Authorized intended readers |
| `files` | `NamedFile[]` | Returned descriptive content |
| `redactions` | `string[]` | Withheld evidence |

**Invalid/missing behavior:** No direct database/volume access; path escape or forbidden audience is rejected.

### client-cancellation

`client-cancellation:field-contract:1` · client and protected controller → runner, client.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `request_id` | `string` | Cancellation identity |
| `run_id` | `string` | Target |
| `status` | `string` | requested/acknowledged/terminal |
| `preserved_effects` | `string[]` | Known effects that cannot be undone |

**Invalid/missing behavior:** Stop new dispatch, contain active work, preserve uncertainty/evidence; cancellation is not rollback.

### client-error

`client-error:field-contract:1` · application → clients.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `category` | `string` | Stable reason family |
| `message` | `string` | Actionable human explanation |
| `request_id` | `nullable-string` | Known request |
| `run_id` | `nullable-string` | Known run |
| `evidence_refs` | `Ref[]` | Authorized diagnosis |
| `correction` | `string` | Allowed user action |

**Invalid/missing behavior:** Never include credentials/hidden fixtures or suggest implicit work retry.

### model-route

`model-route:field-contract:1` · protected router → audited bridge, observations.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `invocation_id` | `string` | Attempt call |
| `role` | `string` | Approved CC role |
| `profile_ref` | `Ref` | Frozen selection policy |
| `eligible_endpoints` | `string[]` | Approved candidates |
| `excluded_reasons` | `string[]` | Capability/access failures |
| `selected_endpoint` | `nullable-string` | Eligible endpoint or unavailable |
| `identity` | `ModelIdentity` | Requested/effective identity |
| `limits` | `Limits` | Frozen call bounds |

**Invalid/missing behavior:** No eligible endpoint blocks. Router cannot replace CC or switch a started invocation.

## Offline rsi records

### rsi-target-profile

`rsi-target-profile:field-contract:1` · protected target owner → controller, guard, referee.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `parent_ref` | `Ref` | Eligible exact sandbox parent |
| `frozen_contract_ref` | `Ref` | Unchanged interface |
| `required_test_refs` | `Ref[]` | Mandatory parent tests |
| `mutable_paths` | `string[]` | Only allowed helper path |
| `protected_refs` | `Ref[]` | Immutable dependency/referee closure |
| `splits` | `SplitIdentities` | Disjoint partition identities |
| `scoring` | `RSIScore` | Passed-tests-first timing tie rule |
| `calibration_ref` | `Ref` | Good/bad children and measured headroom |
| `session_query_limit` | `integer` | 30 |
| `lifetime_query_limit` | `integer` | 90 |
| `limits` | `Limits` | Frozen session bounds |
| `scoring_adapter_ref` | `Ref` | Frozen independent scoring adapter |
| `improver_ref` | `Ref` | Fixed proposer policy/implementation |
| `configuration_ref` | `Ref` | Frozen model/host/runtime configuration |

**Invalid/missing behavior:** No calibrated headroom, overlap or mutable referee blocks session. Never edit profile in response to candidate results.

### rsi-attempt

`rsi-attempt:field-contract:1` · protected RSI controller → guard, referee, evidence.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `session_id` | `string` | Bounded session |
| `sequence` | `integer` | Ordered positive attempt |
| `previous_ref` | `nullable-Ref` | Previous exact attempt or null first |
| `target_ref` | `Ref` | Frozen profile |
| `parent_ref` | `Ref` | Same eligible parent |
| `child_ref` | `Ref` | Exact proposed child |
| `diff_ref` | `Ref` | Allowed implementation delta |
| `rationale` | `string` | Proposer explanation, not proof |
| `visible_evidence_refs` | `Ref[]` | Visible tests |
| `queries_used` | `integer` | Actual protected count |
| `violations` | `string[]` | Observed violations |
| `stop_reason` | `nullable-string` | Terminal reason or null |
| `configuration_ref` | `Ref` | Same frozen target context |
| `observation_refs` | `Ref[]` | Protected model/time/call traces |
| `time_s` | `nullable-number` | Observed session elapsed time or unavailable |
| `model_calls` | `nullable-integer` | Observed proposal calls or unavailable |
| `unavailable_reasons` | `string[]` | Explicit unobserved telemetry |
| `hash_profile_ref` | `Ref` | Pinned serialization/hash profile |
| `chain_root_ref` | `Ref` | Protected pre-attempt session genesis |

**Invalid/missing behavior:** Broken chain/lineage, unauthorized mutation or security violation halts and retains evidence; clearance needed before a new autonomous session.

### rsi-loop-feedback

`rsi-loop-feedback:field-contract:1` · custodian → proposer.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `passed` | `integer` | Aggregate hidden passed count |
| `total` | `integer` | Hidden case count |
| `queries_left` | `integer` | Remaining bounded allowance |

**Invalid/missing behavior:** Counts only; no case IDs/content/timing/expected answers or final feedback enter proposal context.

### rsi-referee-evidence

`rsi-referee-evidence:field-contract:1` · protected independent referee → restricted admission, evidence builder.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `attempt_ref` | `Ref` | Exact assessed attempt |
| `target_ref` | `Ref` | Frozen scorer/splits |
| `parent_ref` | `Ref` | Same parent |
| `child_ref` | `Ref` | Same candidate |
| `pairs` | `RSIPair[]` | Comparable repeated aggregate loop/final results |
| `mandatory_parent_tests_passed` | `boolean` | Compatibility prerequisite |
| `integrity_passed` | `boolean` | Custody/mutation/effect checks |
| `final_evaluations` | `integer` | Exactly one terminal evaluation |
| `violations` | `string[]` | Protected security results |
| `configuration_ref` | `Ref` | Comparable exact parent/child evaluation context |

**Invalid/missing behavior:** Wrong parent, fewer mandatory passes, changed configuration, final reuse or tampering blocks certification.

### rsi-evidence-export

`rsi-evidence-export:field-contract:1` · trusted audience-filtered builder → authorized human, library.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `attempt_ref` | `Ref` | Terminal child attempt |
| `referee_ref` | `Ref` | Restricted evidence identity |
| `parent_ref` | `Ref` | Exact parent |
| `child_ref` | `Ref` | Exact child |
| `summary` | `string` | Allowed paired aggregate comparison |
| `redactions` | `string[]` | Hidden cases/scoring details withheld |
| `violations` | `string[]` | Allowed security outcomes |

**Invalid/missing behavior:** Final export never feeds the loop; withheld contents remain custodian-only. Hash identity does not grant read permission.

### library-admission

`library-admission:field-contract:1` · protected library admission → eligibility, human.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `candidate_ref` | `Ref` | Exact declaration/body package |
| `parent_ref` | `nullable-Ref` | Lineage |
| `evidence_refs` | `Ref[]` | Independent allowed-change/contract/test/effect checks |
| `status` | `string` | admitted/rejected/blocked |
| `standing` | `string` | inactive/active/suspended/revoked |
| `reasons` | `string[]` | Disposition rationale |

**Invalid/missing behavior:** Only protected admission authors standing. RSI score or producer declaration grants no eligibility.

### activation-record

`activation-record:field-contract:1` · authorized human through protected library → future selection, audit.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `actor` | `string` | Authenticated human |
| `recorded_at` | `string` | UTC timestamp |
| `from_ref` | `Ref` | Prior admitted version |
| `to_ref` | `Ref` | Selected admitted version |
| `admission_ref` | `Ref` | Eligibility basis |
| `reason` | `string` | Activation or rollback rationale |
| `effect_scope` | `string` | future sandbox selection only in Target 1 M1 |

**Invalid/missing behavior:** Cannot affect frozen runs or automatically adopt production child. Rollback records reverse selection without erasing history.

## Shared field types

These structures standardize consequential nested information. Arbitrary configuration remains pinned referenced data, not a replacement for mandatory fields.

### Ref

| Field | Type | Meaning |
|---|---|---|
| `id` | `string` | Immutable manifest identity |
| `sha256` | `sha256` | Exact-byte digest |

### Citation

| Field | Type | Meaning |
|---|---|---|
| `id` | `string` | Stable citation ID |
| `source_ref` | `Ref` | Captured readable source |
| `locator` | `string` | Original origin and exact location |
| `excerpt` | `string` | Relevant source quotation |

### Idea

| Field | Type | Meaning |
|---|---|---|
| `idea_id` | `string` | Unique immutable ID |
| `title` | `string` | Short title |
| `summary` | `string` | Grounded mechanism |
| `citation_ids` | `string[]` | Supporting citations |
| `assumptions` | `string[]` | Unproven premises |
| `risks` | `string[]` | Known concerns |

### IdeaScore

| Field | Type | Meaning |
|---|---|---|
| `idea_id` | `string` | Existing candidate |
| `novelty` | `integer` | 1–5 |
| `feasibility` | `integer` | 1–5 |
| `compute_alignment` | `integer` | 1–5 |
| `reasons` | `string[]` | Evidence-linked scoring rationale |
| `citation_ids` | `string[]` | Score support |
| `eligible` | `boolean` | Meets declared resource constraints |
| `disposition` | `string` | Exclusion or eligibility reason |

### Ranking

| Field | Type | Meaning |
|---|---|---|
| `idea_id` | `string` | Eligible candidate |
| `total` | `integer` | Sum of three scores |

### MetricRule

| Field | Type | Meaning |
|---|---|---|
| `metric_id` | `string` | Unique measurement ID |
| `unit` | `string` | Measurement unit |
| `measurement` | `string` | Deterministic extraction definition |
| `aggregation` | `string` | Frozen aggregation |
| `success` | `ComparisonRule` | Predeclared success rule |
| `falsification` | `ComparisonRule` | Predeclared negative rule |
| `middle` | `string` | Predeclared residual classification |

### MetricObservation

| Field | Type | Meaning |
|---|---|---|
| `metric_id` | `string` | Blueprint metric |
| `unit` | `string` | Same protocol unit |
| `baseline` | `number[]` | Raw baseline repeats |
| `treatment` | `number[]` | Raw treatment repeats |
| `baseline_value` | `number` | Registered aggregate |
| `treatment_value` | `number` | Registered aggregate |
| `delta` | `number` | Treatment minus baseline |

### MetricFinding

| Field | Type | Meaning |
|---|---|---|
| `metric_id` | `string` | Registered metric |
| `classification` | `string` | Scientific classification |
| `rationale` | `string` | Measurement-to-rule explanation |

### NamedFile

| Field | Type | Meaning |
|---|---|---|
| `path` | `string` | Confined descriptive relative path |
| `artifact_ref` | `Ref` | Exact content identity |
| `media_type` | `string` | Readable or binary format |
| `audience` | `string` | Authorized readership |

### MissingEvidence

| Field | Type | Meaning |
|---|---|---|
| `obligation_id` | `string` | Expected item |
| `reason` | `string` | Unavailable or not-yet-produced reason |
| `blocking` | `boolean` | Whether absence prevents release |

### FutureInput

| Field | Type | Meaning |
|---|---|---|
| `producer_node` | `string` | Predecessor node |
| `port` | `string` | Named output port |
| `contract_id` | `string` | Catalog contract |
| `version` | `string` | Exact version |

### PlanNode

| Field | Type | Meaning |
|---|---|---|
| `node_id` | `string` | Unique graph node |
| `objective` | `string` | Assigned purpose |
| `requirement_ids` | `string[]` | Brief coverage |
| `capsule_refs` | `Ref[]` | Exactly one proposed admitted work declaration for M1 |
| `predecessors` | `string[]` | Dependency IDs |
| `inputs` | `PlanInput[]` | Named concrete or future-bound inputs |
| `outputs` | `PlanOutput[]` | Named typed outputs |

### Limits

| Field | Type | Meaning |
|---|---|---|
| `time_s` | `number` | Positive elapsed cap |
| `model_calls` | `integer` | Nonnegative call cap |
| `memory_mb` | `integer` | Positive memory cap |

### ModelIdentity

| Field | Type | Meaning |
|---|---|---|
| `requested` | `string` | Configured identity |
| `effective` | `nullable-string` | Reported actual identity or unavailable |
| `basis` | `string` | How effective identity was established |

### RSIPair

| Field | Type | Meaning |
|---|---|---|
| `split` | `string` | loop or final partition identity, not case IDs |
| `parent_passed` | `integer` | Aggregate count |
| `child_passed` | `integer` | Aggregate count |
| `total` | `integer` | Same case count |
| `parent_time_s` | `number[]` | Paired batch durations |
| `child_time_s` | `number[]` | Paired batch durations |

### RSIScore

| Field | Type | Meaning |
|---|---|---|
| `primary` | `string` | passed_test_count |
| `secondary` | `string` | paired_time_at_equal_counts |
| `warmup_batches` | `integer` | Frozen warm-ups |
| `paired_rounds` | `integer` | Frozen round count |
| `min_relative_gain` | `number` | Frozen minimum gain |
| `noise_multiplier` | `number` | Frozen calibrated-noise multiple |
| `batch_iterations` | `integer` | Fixed equal helper batch workload |
| `calibrated_relative_noise` | `number` | Protected pre-session timing-noise estimate |


### SplitIdentities

| Field | Type | Meaning |
|---|---|---|
| `development` | `string` | Visible partition identity |
| `hidden_loop` | `string` | Custodian-only identity |
| `hidden_final` | `string` | Custodian-only identity |
| `platform` | `string` | Outside-loop evaluation identity |


### ComparisonRule

| Field | Type | Meaning |
|---|---|---|
| `operand` | `string` | Registered treatment aggregate |
| `comparator` | `string` | One of lt, le, eq, ge, gt |
| `reference` | `string` | baseline aggregate or constant |
| `factor` | `number` | Multiply baseline; zero for constant |
| `offset` | `number` | Add threshold in the registered unit |

### Prerequisite

| Field | Type | Meaning |
|---|---|---|
| `name` | `string` | Storage/auth/model/isolation prerequisite |
| `status` | `string` | ready, unavailable or failed |
| `reason` | `string` | Actionable observed basis; no secret values |

Comparison rules evaluate the treatment aggregate against `factor * baseline + offset`, or `offset` when reference is `constant` and factor is zero. Use the declared metric unit. Success/falsification regions must not overlap on admissible metric values; uncovered values receive the registered middle classification. Missing measurement is unavailable, never zero. Rule fields are fixed before results; a scientific evaluator cannot replace them with favorable prose. Supported M1 comparison operators are lt/le/eq/ge/gt. More complex measures require an independently pinned measurement adapter and explicit supported contract before execution, rather than an invented expression parser.

## Candidate provenance

`candidate-provenance:field-contract:1` · candidate builder with protected capture → library admission, human, RSI.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable candidate identity |
| `declaration_ref` | `Ref` | Exact unchanged interface declaration |
| `implementation_refs` | `Ref[]` | Complete exact body files |
| `parent_ref` | `nullable-Ref` | Exact prior implementation/version lineage |
| `builder_ref` | `Ref` | Attributable builder or protected RSI attempt |
| `evidence_refs` | `Ref[]` | Independent compatibility/security/provenance support |

Missing declaration/body closure, unknown lineage or mismatched evidence blocks admission. This package is candidate data, never standing or activation authority. Human from/to version refs resolve through admission to the exact candidate body and declaration closure; an implementation hash alone grants no eligibility.

### Usage

| Field | Type | Meaning |
|---|---|---|
| `input_tokens` | `nullable-integer` | Observed input tokens, or unavailable |
| `output_tokens` | `nullable-integer` | Observed output tokens, or unavailable |
| `cost_amount` | `nullable-number` | Reported attributable cost, or unavailable; no fabricated estimate |
| `currency` | `nullable-string` | Reported cost unit, or unavailable |
| `unavailable_reasons` | `string[]` | Unsupported or unobserved fields and basis |

Unavailable optional tokens/cost do not establish zero usage or waive mandatory model-call/time limits. Mandatory quota evidence is independently required by the bound profile. Reported values retain provider basis; arbitrary diagnostic estimates cannot certify a budget.

### PlanInput

| Field | Type | Meaning |
|---|---|---|
| `name` | `string` | Unique consumer input port |
| `contract_id` | `string` | Catalog contract |
| `version` | `string` | Exact contract version |
| `required` | `boolean` | Mandatory input |
| `artifact_refs` | `Ref[]` | Concrete accepted inputs; empty when future-bound |
| `future_bindings` | `FutureInput[]` | Named predecessor outputs; empty when concrete |

### PlanOutput

| Field | Type | Meaning |
|---|---|---|
| `name` | `string` | Unique producer output port |
| `contract_id` | `string` | Catalog contract |
| `version` | `string` | Exact contract version |
| `required` | `boolean` | Mandatory output |

Each PlanInput has exactly one nonempty source list: accepted `artifact_refs` or `future_bindings`. Future bindings must identify a declared predecessor and its named compatible output; concrete refs must have protected acceptance in the run scope. Names are unique per direction. Missing required input, unknown port/version or dependency cycles block freezing. Optional absent inputs are omitted, never represented by an ambiguous empty source.

### security-clearance

Producer: authorized security human through protected RSI controller. Consumers: new-session eligibility, audit.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Format version 1.0.0 |
| `id` | `string` | Immutable record identity |
| `actor_id` | `string` | Authorized security reviewer |
| `recorded_at` | `string` | UTC clearance time |
| `halted_session_id` | `string` | Exact violated session |
| `violation_refs` | `Ref[]` | Protected incident evidence |
| `remediation_ref` | `Ref` | Exact remediation |
| `guardrail_evidence_refs` | `Ref[]` | Independent validated guardrail evidence |
| `decision` | `string` | cleared or denied |
| `effect_scope` | `string` | new_rsi_session_only |

Missing incident, authorized actor or validated remediation blocks new-session eligibility. Clearance never resumes the halted session or activates a child.

