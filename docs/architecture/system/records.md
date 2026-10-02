---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [system.record_api, system.dispatch_identity]
consumes: [cc.binding, cc.observation, cc.verification]
depends_on: [storage.md, lifecycle.md, ../capsule/rsi-engine.md]
tags: [system, persistence, contract]
---

# Durable system records and reserved identities

This page owns internal control records, implemented in `cc/records.py`. It supplies durability for lifecycle, recovery and quota without creating alternative CC Observations or Verifications.

## Closed envelope and store API

`put_system(record: SystemRecord) -> SystemRef` and `get_system(ref: SystemRef) -> SystemRecord` use [storage](storage.md)'s publication, hashes, conflicts and recovery. SystemRef is closed `{id:id, sha256:sha256}`. SystemRecord is closed `{schema_version:1, kind:enum(run_started,dispatch_reserved,lifecycle,release,human_review,rsi_session,oracle_quota,rsi_attempt), id:id, run_id:id?, session_id:id?, at:time, previous_ref:SystemRef?, payload:object}`. Schema_version/kind/id/at/payload are required; absent optional correlation keys are omitted. Each variant has the closed required payload below. Unknown fields and wrong scopes fail before publication.

The separate `DATA/cc/system/<id>/` commit namespace accepts only these kinds and authorized writers. Use the same temp-directory/fsync/rename protocol as CC records, never JSONL append as atomic authority. JSONL lifecycle/attempt logs are rebuildable projections. Oracle quota has its own protected root and cannot be read through the ordinary store or exported. SystemRef cannot substitute for a CC record Ref. One supervisor serializes writes; the private oracle serializes its own reservations.

| Kind / writer / scope | Exact payload fields | Identity / conditions |
|---|---|---|
| run_started / supervisor / run_id | plan_ref:Ref(artifact), intake_ref:Ref(artifact), config_sha256:sha256, binding_refs:list<Ref(binding)> | run-start-<run_id>; references committed first |
| dispatch_reserved / supervisor / run_id or admission session_id | caller:enum(dispatch,nested,gate,admission), step_id:id?, attempt:integer, obs_id:id, dispatch_id:sha256, request_sha256:sha256, binding_ref:Ref(binding)?, input_refs:map<string,Ref(artifact)>, parent_obs_id:id?, ordinal:integer? | dispatch-<dispatch_id>; reserve before effects; dispatch requires run/step/binding; nested/gate require parent/ordinal; admission requires session |
| lifecycle / supervisor / run_id | step_id:id?, attempt:integer?, state:enum(pending,running,evaluating,halted,completed,aborted), dispatch_ref:SystemRef?, observation_ref:Ref(observation)?, verification_ref:Ref(verification)?, release_ref:SystemRef?, reason:Reason? | append-only sequence linked by previous_ref; completed step requires release_ref; halted requires reason |
| release / supervisor / run_id | step_id:id, attempt:integer, dispatch_ref:SystemRef, observation_ref:Ref(observation), verification_ref:Ref(verification) | release-<dispatch_id>; only after authorize_advance verifies exact committed evidence |
| human_review / terminal adapter / run_id | step_id:id, attempt:integer, action:enum(abort,resume_after_fix,new_run), reviewed_refs:list<SystemRef>, response_text:text | fresh ID; authenticated reply; CC refs reached through the reviewed system records |
| rsi_session / offline controller / session_id | target_decl_hash:sha256, parent_decl_hash:sha256, export_id:id, model_id:string, config_sha256:sha256, policy_epoch:id, state:enum(preparing,running,stopped,blocked,finished), oracle_session_id:id?, reason:Reason? | sequence linked by previous_ref; parent/model/config/policy immutable per session |
| oracle_quota / private oracle / session_id | request_id:id, candidate_ref:Ref(candidate), request_sha256:sha256, ordinal:integer, state:enum(reserved,complete,interrupted), passed:integer?, failed:integer?, reason:Reason? | reserve ordinal 1–30 before child launch; complete counts nonnegative; transitions have separate immutable IDs; uncertain queries are never refunded |
| rsi_attempt / offline controller / session_id | Exact closed Attempt entry owned by [RSI engine](../capsule/rsi-engine.md#attempt-record) | attempt_id is the record id; previous_entry_sha256 links entries; no hidden cases |

## Reservation and replay

`reserve_dispatch(run_id, step_id, binding_ref, input_refs, human_review_ref?) -> dispatch_reserved` allocates attempt 1 or the next number after all existing reservations, including interrupted ones without Observations. A duplicate identity returns that reservation; a new attempt requires human review. Supervisor chooses obs_id once, hashes the canonical dispatch tuple and request bytes, commits, then sends obs_id/attempt/dispatch_id/reservation_ref to the runner. Runner cannot mint another dispatch Observation ID.

`reserve_call(caller,parent_obs_id,ordinal,request_sha256,scope)` handles nested/gate/admission calls. Broker durably reserves ordinals; the call identity is derived from parent/ordinal/request and uses attempt 1. Duplicate frames attach to that reservation. Gate repair uses the same work Observation and returns the existing Verification or completes missing decision storage; it never repeats work. Artifact IDs derive from reserved obs_id and port name.

Changed bytes under an existing identity return REQUEST_CONFLICT. No Observation means interruption, not proof of no effects. Inspect reservations, capture and published outputs before human-approved recovery. With every store sink unavailable, return truthful diagnostics without claiming a durable halt/review/release.
