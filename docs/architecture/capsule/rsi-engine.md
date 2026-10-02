---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [cc.offline_rsi, cc.rsi_attempt_api]
consumes: [cc.candidate, cc.fixture_oracle_api]
depends_on: [fixture-oracle.md, toolchain.md, ../system/storage.md, ../system/environment.md]
tags: [capsule, rsi, m1]
---

# Offline RSI controller and activation

PRD 4.4.1–4.4.9 owns domain scope. Saurav owns optimization; Muk owns Candidate, admission, library and shared CC contracts. Placement is [modules](../system/modules.md). Hidden execution remains fail-closed until issue 40's boundary is validated; query scheduling is fixed below. The optimization algorithm remains an implementation choice.

## Public API

`start_rsi(target_decl_hash, export_id, request_id) -> RsiSessionResult`

`rsi_status(session_id) -> RsiSessionResult`

`stop_rsi(session_id, request_id) -> RsiSessionResult`

`submit_rsi(session_id, attempt_id, request_id) -> Ref(Candidate)`

`activate(candidate_ref, expected_parent_hash, request_id) -> Ref(Standing)` is a librarian action available only through explicit human CLI review after ordinary admission. A stale parent returns `STORE_CONFLICT`. It selects the admitted child for future runs, keeps the parent available and cannot change a frozen Binding or active run.

`RsiSessionResult` is a closed internal envelope: `session_id: id`, `state: enum(preparing,running,stopped,blocked,finished)`, `target_decl_hash: sha256`, `latest_attempt_id: id?`, `candidate_ref: Ref(Candidate)?`, `reason: Reason?`. Blocked requires a reason. These correlation fields belong to system envelopes, not reusable capsule payloads.

## Preparation and scope

1. Freeze target, parent, policy, vocabulary, visible suite, split manifest, permitted mutation paths, model ID and configuration. Copy the library into `.jiuwenswarm/rsi/tasks/<session_id>/`; preserve source hashes. The live library is read only.
2. Permit one declared implementation file or one target-owned prompt/rubric file. Interfaces, schemas, tests, referee rubrics, policy, datasets, dependency registry, deterministic ranking and splits remain frozen. For Screening, RSI may change only `research.select_opportunity`'s `SKILL.md` and owned assessment rubric. Reject other changes before evaluating them.
3. The oracle checks at least 20 hidden loop and 20 hidden final fixtures, disjoint hashes across dev/loop/final, and owner-authored labels. Hidden manifests and labels never reach the proposer.
4. Require baseline failures of at least 20% of the hidden loop set and at least five final cases. The oracle supplies only aggregate eligibility to the controller.
5. Bind one oracle-issued session to this controller and target. Enforce 30 durable query reservations: baseline 1; proposal evaluations at most 23; accepted-lineage revert ablations at most 5; final holdout 1. The final six reservations are unavailable to proposal generation, satisfying the 20% headroom target. Unused ablation reservations remain unused. Recovery reuses the handle and quota; it cannot mint a replacement to evade the cap.

## Attempt record

The controller alone writes append-only `attempts.jsonl`, with immutable entries committed through [storage](../system/storage.md). Each closed entry contains:

`attempt_id: id`, `session_id: id`, `parent_attempt_id: id?`, `target_decl_hash: sha256`, `parent_decl_hash: sha256`, `child_decl_hash: sha256?`, `changed_path: string`, `before_sha256: sha256`, `after_sha256: sha256`, `model_id: string`, `config_sha256: sha256`, `policy_epoch: id`, `export_id: id`, `oracle_request_id: id?`, `state: enum(proposed,rejected,evaluated,ablation,submitted)`, `passed: integer?`, `failed: integer?`, `reason: Reason?`, `candidate_ref: Ref(Candidate)?`, `previous_entry_sha256: sha256?`, `entry_sha256: sha256`, `at: datetime`.

Hash canonical UTF-8 JSON of all fields except `entry_sha256`. The first entry has a null previous hash; later entries reference the immediately preceding committed entry. Counts exist only for complete aggregate oracle results. Candidate references are appended only after Candidate publication. Prompt/reply and mutation bytes stay in the controller's private evidence bundle; hidden fixture evidence never enters it. The immutable entry objects are authoritative; the JSONL projection can be rebuilt after an interrupted append.

## Execution and failures

Run visible tests and CC checks before querying hidden fixtures. Schema changes, forbidden files and changed measurement rules reject the proposal without a query. The trusted controller labels oracle requests as `baseline`, `proposal`, `ablation` or `final`; the oracle enforces order and reserved counts, and the proposer never chooses a suite. Each hidden input executes in a fresh confined child; expected answers stay in the oracle parent. The final result is returned only once, after proposal evaluation is closed, and never re-enters optimization.

Request IDs bind canonical request hashes. Identical duplicates return committed results; changed bytes conflict. Reserve a query before execution. An uncertain interrupted query consumes its reservation and never runs again automatically. Timeout, failed containment or store failure stops the loop. Preserve attempts and failure evidence; never mutate the live DAG or automatically activate.

Submit through [Candidate](../schemas/candidate.md), including every pinned file, visible tests and builder evidence. Hidden counts are labels, not admission evidence. Admission runs independently through `tested_admission` or the developer-selected Puppet Gate; an RSI child remains `admitted_inactive` until a separate activation record. Never expose hidden cases in Candidate tests, test aids, extensions, exports or model prompts.

## Security and checks

The proposer reads target copies, approved dev exports and aggregate replies only. It cannot read hidden fixtures, credentials, store authority or another session. Concrete identity and IPC mechanisms are in [environment](../system/environment.md); issue 40 preserves the root-free source conflict. Directory separation alone is not verified confinement. [Verification](../system/verification.md) defines independent invocations and failure injection, including crashes after quota reservation, attempt publication and Candidate publication. No runtime validation is claimed.
