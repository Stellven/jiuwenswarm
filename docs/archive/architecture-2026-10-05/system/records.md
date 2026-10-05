---
id: system.records
type: module-spec
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [system.record_api, system.dispatch_identity]
consumes: [cc.binding, cc.observation, cc.verification]
depends_on: [storage.md, lifecycle.md, ../capsule/rsi-engine.md]
tags: [system, persistence, contract]
level: detail
prd: [4.5.2, 4.6.4]
---

# Durable system records and reserved identities

PRD: 4.5.2, 4.6.4

> Answers: Which internal control records exist and how are identities reserved?

## Purpose

This page is the home of internal control records, implemented in `cc/records.py`. It supplies durability for lifecycle, recovery and quota without creating alternative CC [Observations](../schemas/observation.md#term-observation) or [Verifications](../schemas/verification-record.md#term-verification).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-systemrecord"></a>**SystemRecord** (also: SystemRecords, system record) | A durable control record the supervisor writes (run phase, dispatch reservation, release, human review, RSI and oracle records). It is a closed variant with a `kind`. |
| <a id="term-systemref"></a>**SystemRef** | A reference `{id, sha256}` to one SystemRecord. |
| <a id="term-dispatch"></a>**Dispatch** (also: dispatched, dispatching) | The supervisor sending one step to the runner after it has reserved the call. A duplicate dispatch with the same identity attaches to the existing call or returns its committed result. |
| <a id="term-reservation"></a>**Reservation** (also: dispatch reservation, dispatch_reserved) | The `dispatch_reserved` system record the supervisor commits before any effect. It fixes the `obs_id`, attempt and request hash, so a crash leaves proof that a call may have run. |
| <a id="term-dispatch-id"></a>**dispatch_id** | The id of one dispatch, derived deterministically from run, step, Binding hash, input hashes and attempt. It is an id, not a sha256, and the same tuple always gives the same id. |
| <a id="term-run-id"></a>**run_id** | The id of one run, created at launch. Every run-scoped record, event and path carries it. |
| <a id="term-step-id"></a>**step_id** | The id of one step within a run's plan. Together with `run_id` and the attempt it names a call site. |

## Interface: closed envelope and store API

`put_system(record: SystemRecord) -> SystemRef` and `get_system(ref: SystemRef) -> SystemRecord` use [storage](storage.md)'s publication, hashes, conflicts and recovery. SystemRef is closed `{id:id, sha256:sha256}`. SystemRecord is closed `{schema_version:1, kind:enum(planning_reserved,model_call_reserved,run_phase_started,dispatch_reserved,lifecycle,release,human_review,rsi_session,rsi_trial,rsi_security_clearance,oracle_session,oracle_closure,oracle_result,oracle_security_block,oracle_security_clearance,oracle_quota,rsi_attempt,activation), id:id, run_id:id?, session_id:id?, at:time, previous_ref:SystemRef?, payload:object}`. Schema_version/kind/id/at/payload are required; absent optional correlation keys are omitted. Each variant has the closed required payload below. Unknown fields and wrong scopes fail before publication.

Schema: `execution-v1.schema.json#system_record` is the oneOf of one closed definition per [kind](../capsule/capsule.md#term-capsule-kind): `execution-v1.schema.json#system_record_planning_reserved`, `execution-v1.schema.json#system_record_model_call_reserved`, `execution-v1.schema.json#run_phase_started`, `execution-v1.schema.json#dispatch_reservation`, `execution-v1.schema.json#system_record_lifecycle`, `execution-v1.schema.json#release_record`, `execution-v1.schema.json#human_review_record`, `execution-v1.schema.json#system_record_rsi_session`, `execution-v1.schema.json#system_record_rsi_trial`, `execution-v1.schema.json#system_record_rsi_security_clearance`, `execution-v1.schema.json#system_record_oracle_session`, `execution-v1.schema.json#system_record_oracle_closure`, `execution-v1.schema.json#system_record_oracle_result`, `execution-v1.schema.json#system_record_oracle_security_block`, `execution-v1.schema.json#system_record_oracle_security_clearance`, `execution-v1.schema.json#system_record_oracle_quota`, `execution-v1.schema.json#system_record_rsi_attempt`, `execution-v1.schema.json#system_record_activation`. The SystemRef returned by put_system is `execution-v1.schema.json#system_ref`. The schema encodes the payload conditions in the table below.

The separate `DATA/cc/system/<id>/` commit namespace accepts only these kinds and authorized writers. Use the same temp-directory/fsync/rename protocol as CC records, never JSONL append as atomic authority. JSONL lifecycle/attempt logs are rebuildable projections. Oracle quota has its own protected root and cannot be read through the ordinary store or exported. The oracle writes only its private namespace through its own writer; B14 remains the sole writer of the public store. SystemRef cannot substitute for a CC record Ref. One supervisor serializes writes; the [private oracle](../capsule/fixture-oracle.md#term-fixture-oracle) serializes its own reservations.

| Kind / writer / scope | Exact payload fields | Identity / conditions |
|---|---|---|
| planning_reserved / supervisor / run_id | [services-v1 planning_reservation](../contracts/services-v1.schema.json) is the home of the closed payload: planning_request_id, request_sha256, task_ref, library_snapshot_ref, experiment_config_ref (nullable ref), policy_ref, model_id, max_model_calls and deadline_at | isolated experiment track only: the M1 fixed-template planner makes no model call and writes no planning reservation. Reserved for the experiment planner call, after the requirement release and before freeze 2; immutable requirement/library/config/policy/model/deadline/call pins committed before [bridge](model-bridge.md#term-model-bridge) access; same identity/bytes reuse, changed bytes conflict; no planned-plan [Bindings](../schemas/binding.md#term-binding) exist yet |
| model_call_reserved / supervisor / run_id | [services-v1 model_call_reservation](../contracts/services-v1.schema.json) is the home of the closed payload | run requires exact declaration/dispatch linkage; planning (experiment track only) requires planning_ref; [obs_id](observability.md#term-obs-id)/turn permit direct-call quota reconstruction, ordinal counts aggregate calls; reserve before forwarding, uncertain calls never refunded |
| run_phase_started / supervisor / run_id | one record per freeze point; see [two freeze points](#behavior-two-freeze-points). run_id:id, phase:enum(prep,planned), plan_ref:Ref(artifact), batch_ref:Ref(commit [batch](storage.md#term-commit-batch) manifest), library_snapshot_sha256:sha256, prep_release_refs:list<SystemRef> (planned only), effective_config_ref:Ref(artifact); prep also intake_ref:Ref(artifact), source_manifest_sha256:sha256, track:enum(production,offline_rsi,isolated_experiment); planned also proposal_ref:Ref(artifact) | run-phase-<run_id>-<phase>; references committed first; [freezes](lifecycle.md#term-freeze) complete source/config/library context. Schema: `execution-v1.schema.json#run_phase_started` |
| dispatch_reserved / supervisor / run_id or admission session_id | caller:enum(dispatch,nested,gate,admission), step_id:id?, attempt:integer, obs_id:id, dispatch_id:id (derived from the dispatch tuple, not a hash), request_sha256:sha256, binding_ref:Ref(binding)?, input_refs:map<string,Ref(artifact)>, parent_obs_id:id?, ordinal:integer? | dispatch-<dispatch_id>; reserve before effects; dispatch requires run/step/binding; nested/gate require parent/ordinal; admission requires Candidate. A gate, nested or admission `runner_request` carries no `caller`: the caller kind, parent observation and ordinal are read from this reservation |
| lifecycle / supervisor / run_id | step_id:id?, attempt:integer?, state:enum(pending,running,evaluating,[halted](lifecycle.md#term-halt),completed,aborted), dispatch_ref:SystemRef?, observation_ref:Ref(observation)?, verification_ref:Ref(verification)?, release_ref:SystemRef?, reason:Reason? | append-only sequence linked by previous_ref; completed step requires release_ref; halted requires reason |
| release / supervisor / run_id | step_id:id, attempt:integer, dispatch_ref:SystemRef, observation_ref:Ref(observation), verification_ref:Ref(verification) | release-<dispatch_id>; only after authorize_advance verifies exact committed evidence |
| human_review / terminal adapter (written by `cc resume` or abort) / run_id | step_id:id, attempt:integer, action:enum(abort,resume_after_fix,new_run), reviewed_refs:list<SystemRef>, response_text:text | fresh ID; authenticated reply; CC refs reached through the reviewed system records |
| rsi_session / offline controller / session_id | target_decl_hash:sha256, parent_decl_hash:sha256, export_id:id, model_id:string, config_sha256:sha256, policy_epoch:id, evaluator_sha256:sha256, execution_profile_sha256:sha256, state:enum(preparing,running,closing,closed,stopped,blocked,finished,no_candidate), oracle_session_id:id?, incumbent_trial_ref:[TrialRef](../capsule/fixture-oracle.md#term-trialref)?, oracle_closure_ref:OracleRef?, final_result_ref:OracleRef?, security_block_ref:OracleRef?, clearance_ref:SystemRef?, reason:Reason? | sequence linked by previous_ref; parent/model/config/policy/evaluator/profile immutable; closing/closed require closure/incumbent refs; finished/no_candidate require final evidence; security blocked requires incident ref |
| rsi_trial / offline controller / session_id | target_decl_hash:sha256, parent_decl_hash:sha256, trial_decl_hash:sha256, declaration:json, files:list<TrialFile>, visible_suite_result_refs:list<Ref(observation)>, policy_ref:Ref(policy), permitted_paths_sha256:sha256, config_sha256:sha256, evaluator_sha256:sha256 | immutable implementation [snapshot](../capsule/library.md#term-library-snapshot) only; TrialFile is closed {path:string, sha256:sha256, content_ref:Ref(artifact)}; exact local file coverage, no hidden bytes; parent snapshot may precede oracle session creation and uses controller session_id |
| rsi_security_clearance / authenticated human terminal / session_id | [request_id](../contracts/principles.md#term-request-id):id, actor:string, target_decl_hash:sha256, execution_profile_sha256:sha256, security_block_ref:OracleRef, remediation_refs:list<SystemRef>, boundary_report_ref:Ref(artifact), reason:text | authenticated explicit clearance; nonempty remediation refs and current passing report required; label alone cannot clear oracle latch |
| oracle_quota / private oracle / session_id | request_id:id, trial_ref:TrialRef, request_sha256:sha256, loop_set_sha256:sha256, purpose:enum(baseline,proposal,ablation,final), ordinal:integer, lifetime_ordinal:integer?, state:enum(reserved,complete,interrupted), passed:integer?, failed:integer?, reason:Reason? | serialized private commit reserves session ordinal 1-30 and lifetime ordinal 1-90 for loop queries; final uses ordinal1, omits lifetime_ordinal and has separate once/session reservation after closed; uncertain queries never refunded |
| rsi_attempt / offline controller / session_id | Exact closed Attempt entry defined in [RSI engine](../capsule/rsi-engine.md#attempt-record) | attempt_id is the record id; previous_entry_sha256 links entries; no hidden cases |

### Public model-call reservation semantics

model_call_reserved is valid only for run scopes and, in the isolated experiment track, planning scopes. Its run linkage must agree with the envelope. Resolve dispatch_ref and its Binding for run calls, or (experiment track only) planning_ref to planning_reserved for the model-proposed planner call made between freeze 1 and freeze 2. The broker chooses obs_id/turn from the trusted call reservation; callers cannot select a fresh audit identity to reset the direct ceiling. Reconstruct direct calls grouped by exact obs_id/decl_hash and aggregate calls by run; both identities survive a crash. Missing or inconsistent authority [blocks](modules.md#term-block) forwarding.

budget_ref identifies the committed effective [ConfigSnapshot](environment.md#term-configsnapshot) before validation and the accepted complete proposal afterward. Cross-check config and policy; a model-created standalone quota object has no authority. ceiling is the minimum of policy/config and validated-plan limits, including already reserved planning calls. Reject ordinal above ceiling. The scope/request byte hash deduplicates exact replay; changed bytes conflict. In the experiment track planning uses its single authorized [turn](model-bridge.md#term-model-turn); run direct ceilings are pinned by [ExecutionProfile](../schemas/profiles.md#term-executionprofile). The proposal's budget never refunds spent calls or extends an elapsed deadline.

### Private RSI control records

TrialRef and OracleRef encode the same closed id/hash pair as SystemRef, with distinct namespace/kind authorization. A TrialRef resolves only to a controller-written rsi_trial in the private controller evidence root. OracleRefs resolve only through the oracle's authenticated API; ordinary get_system, manifests and benchmark exports cannot fetch private oracle records. Public Ref(Candidate) cannot be accepted in either position. For the parent trial, the controller allocates its session identity before begin_session; the oracle-issued identity is stored separately as oracle_session_id.

The following exact payloads use the SystemRecord envelope with session_id and no run_id, but are committed by the oracle in its protected namespace. All refs and counts are checked before publication; ? fields are optional and absent when not applicable. Private loop/final set hashes never cross into public controller records.

| Kind | Closed required payload; optional fields marked ? | Conditions |
|---|---|---|
| oracle_session | request_id:id, request_sha256:sha256, target_decl_hash:sha256, parent_trial_ref:TrialRef, model_id:string, model_version:string, config_sha256:sha256, policy_ref:Ref(policy), permitted_paths_sha256:sha256, evaluator_sha256:sha256, execution_profile_sha256:sha256, loop_set_sha256:sha256, final_set_sha256:sha256, state:enum(preparing,running,closing,closed,finished,no_candidate,blocked), incumbent_trial_ref:TrialRef, closure_ref:OracleRef?, final_result_ref:OracleRef?, security_block_ref:OracleRef?, clearance_ref:OracleRef?, reason:Reason? | pins immutable; chronological previous_ref chain; blocked requires reason; security block requires incident ref; closed/final states require their durable evidence |
| oracle_closure | request_id:id, request_sha256:sha256, state:enum(closing,closed), incumbent_trial_ref:TrialRef, accepted_lineage_refs:list<TrialRef>, ablation_trial_refs:list<TrialRef>, ablation_result_refs:list<OracleRef>, closing_record_ref:OracleRef? | closing fixes zero-to-five ablations and has empty result list; closed points to exact closing record and complete scheduled results; immutable publication precedes final reservation |
| oracle_result | request_id:id, trial_ref:TrialRef, incumbent_trial_ref:TrialRef, purpose:enum(baseline,proposal,ablation,final), state:enum(complete,denied,unavailable,boundary_violation,query_limit), scoring_rule_sha256:sha256, passed:integer?, failed:integer?, wins:integer?, losses:integer?, ties:integer?, incumbent_median_ms:number?, child_median_ms:number?, disposition:enum(kept,rejected,promotable,no_candidate)?, reason:Reason? | complete requires all counts/durations/disposition; other states omit them and require reason; contains no per-case vectors, cases, outputs or set hashes; this exact immutable redacted record supplies AggregateResult.result_ref |
| oracle_security_block | request_id:id, target_decl_hash:sha256, execution_profile_sha256:sha256, blocked_from_state:enum(preparing,running,closing,closed), reason:Reason, private_audit_sha256:sha256 | target-wide latch keyed by incident ref; private audit bytes remain oracle-only; append-only incident cannot be erased to resume |
| oracle_security_clearance | request_id:id, security_block_ref:OracleRef, terminal_clearance_ref:SystemRef, actor:string, target_decl_hash:sha256, execution_profile_sha256:sha256, boundary_report_ref:Ref(artifact), restored_state:enum(preparing,running,closing,closed) | commit only after human/custody/report validation; all uncleared target incidents must be cleared before new optimization; restores the interrupted phase only, never quota or an uncertain final reservation |

Pairing vectors and raw hidden child captures remain separately committed private content. They are reconciled with request identities inside oracle audit, but have no public retrieval refs. Oracle result projections are distinct from those private bytes, so their id/hash always identifies exactly the disclosed immutable record; redaction never changes bytes under an existing ref.

The terminal's rsi_security_clearance is attributable permission to request clearance, not the authoritative latch transition. Only the oracle writes oracle_security_clearance after validating it. Closing/closed records and security blocks are replayed before any recovered query. With storage unavailable the service stays stopped and claims no committed clearance. The API and phase transitions are owned by [fixture oracle](../capsule/fixture-oracle.md).

## Behavior: two freeze points

A run publishes two frozen plans (decision A26; sequencing in [lifecycle](lifecycle.md#phases-and-the-two-freeze-points-decision-a26)).

| Freeze | When | Covers | Record |
|---|---|---|---|
| 1. [Prep plan](lifecycle.md#term-prep-plan) | at launch | intent and requirement [steps](nodes.md#term-step), their Bindings and [Gate](../verification.md#term-gate) profiles, library snapshot, config, source manifest | `run_phase_started` with phase `prep` |
| 2. [Planned plan](lifecycle.md#term-planned-plan) | after the last requirement release, before the first task node | planned [nodes](nodes.md#term-node)' Bindings and Gates, accepted requirement refs, the planner proposal ref | `run_phase_started` with phase `planned`, carrying `prep_release_refs` and `proposal_ref` |

Rules that any shape must satisfy:
- Freeze 2 carries the same `library_snapshot_sha256` and `config_sha256` as freeze 1; a mismatch is a conflict and halts.
- Each freeze publishes its Binding set in one batch; both link to the proposal and requirement refs they depend on.
- A `dispatch_reserved` for a task node requires a committed freeze 2. A dispatch for a preparation step requires freeze 1.
- The kind enum above is closed. Adding a kind is a new records revision with affected [fixtures](test-surfaces.md#term-fixture) rechecked. `run_phase_started` replaces the earlier `run_started` kind.
- The supervisor starts the generic script a second time for the planned phase with `plan_ref` and `pins_ref` (the `batch_ref` batch of the planned record), see [lifecycle](lifecycle.md#phases-and-the-two-freeze-points-decision-a26).
- A planned plan may wire inputs from [released](lifecycle.md#term-release) prep outputs with source form `prep.<step_id>.<port>`; the planned record's `prep_release_refs` is how those sources resolve.

Schema: `execution-v1.schema.json#run_phase_started`.
- `read_manifest` must expose both plan refs (see below) and mark each step's phase.

## Failure

| Situation | Outcome | Recovery |
|---|---|---|
| Freeze 2 carries a different `library_snapshot_sha256` or `config_sha256` than freeze 1 | conflict; the run halts | new run |
| `dispatch_reserved` for a task node without a committed freeze 2 (or a preparation step without freeze 1) | not allowed | commit the freeze first |
| Same record identity with different bytes | `STORE_CONFLICT`; halt; both hashes kept in incident evidence ([storage](storage.md)) | explicit review |
| A record kind outside the closed enum | rejected | adding a kind is a new records revision with affected [seams](seams.md#term-seam) rechecked |
| Duplicate dispatch identity | the existing reservation or committed result is returned | none needed |

## Reservation and replay

`reserve_dispatch(run_id, step_id, binding_ref, input_refs, human_review_ref?) -> dispatch_reserved` allocates attempt 1 or the next number after all existing reservations, including interrupted ones without Observations. A duplicate identity returns that reservation; a new attempt requires human review. Supervisor chooses obs_id once, derives the dispatch id from the canonical dispatch tuple, hashes the request bytes, commits, then sends obs_id/attempt/dispatch_id/reservation_ref to the runner. Runner cannot mint another dispatch Observation ID.

`reserve_call(caller,parent_obs_id,ordinal,request_sha256,scope)` handles nested/gate/admission calls. Broker durably reserves ordinals; the call identity is derived from parent/ordinal/request and uses attempt 1. Duplicate frames attach to that reservation. Gate repair uses the same work Observation and returns the existing Verification or completes missing decision storage; it never repeats work. Artifact IDs derive from reserved obs_id and port name.

Changed bytes under an existing identity return REQUEST_CONFLICT. No Observation means interruption, not proof of no effects. After a crash the supervisor writes a `halt_report` with reason `INTERRUPTED` and waits; it never resumes by itself. Inspect reservations, capture and published outputs, then `cc resume <run_id>` by a human creates the `human_review` record (action `resume_after_fix`) and a new attempt under unchanged pins. With every store sink unavailable, return truthful diagnostics without claiming a durable halt/review/release.

## Run manifest and library activation

For isolated approved ablations, lifecycle payload and manifest step_records additionally permit `experimental_advance_ref:Ref(artifact)`; completed requires exactly one release_ref or experimental_advance_ref. Production forbids the latter. The supervisor validates the [experimental advance schema](../contracts/services-v1.schema.json) and exact study/profile/Observation before storing completed. Canonical release records retain their unconditional PASS-only rule. Derived exports preserve the difference, including absent Verification when a Gate was not run.

The supervisor is the only run-manifest writer. `read_manifest(run_id)` returns a rebuildable closed view `{schema_version:1, run_id, track, source_manifest_sha256, prep_plan_ref, planned_plan_ref?, library_snapshot_sha256, config_sha256, binding_refs, step_records:[{step_id, attempt, phase, dispatch_ref, observation_ref?, verification_ref?, release_ref?, state, reason?}], artifact_refs, model_audit_refs, started_at, finished_at?}` from committed records. `planned_plan_ref` is absent until freeze 2 (the `plan_ref` of the planned `run_phase_started`). An absent value is unavailable, never inferred success. Schema: `execution-v1.schema.json#run_manifest`. Export includes exact model/config/route and timing evidence and explicit unavailable usage fields. External benchmark [adapters](integration.md#term-adapter) consume this view and cannot write authoritative records. Interrupted manifest publication is rebuilt; release authority stays the committed release record. Content hashing and atomic publication follow [OCI's digest-addressed content model](https://github.com/opencontainers/image-spec/blob/main/descriptor.md).

The librarian writes an `activation` SystemRecord in library scope, closed payload `{capability_name, admitted_decl_hash, expected_current_hash, actor, reason, request_id, verdict_ref}`. This is separate from run-scoped release and from assurance. Extend the SystemRecord kind enum with `activation`; run_id/session_id are absent for this variant. Rollback is an `activation_request` that points at a historical admitted hash. The first activation is `cc bootstrap` (the installer), which admits and activates the seed [capsules](../capsule/capsule.md#term-capability-capsule) with `expected_current_hash` null and actor `installer`; toy capsules are bootstrapped at build step 1 and research capsules when each is ported. No run manifest mutates its library snapshot after activation.

## Tests

Fixtures and fakes: a temporary store root; a frozen two-node toy plan with a kill between nodes. Rows in [test surfaces](test-surfaces.md#verification-table): [V03](test-surfaces.md#verification-table), [V11](test-surfaces.md#verification-table), [V36](test-surfaces.md#verification-table) (planner and freeze lifecycle rows), [V38](test-surfaces.md#verification-table) (activate, rollback, `STORE_CONFLICT`), [V41](test-surfaces.md#verification-table) (crash then resume).
