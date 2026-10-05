---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../../product/prd-m1-rsi-full.md]
provides: [cc.offline_rsi, cc.rsi_attempt_api]
consumes: [cc.candidate, cc.fixture_oracle_api]
depends_on: [fixture-oracle.md, toolchain.md, ../system/storage.md, ../system/environment.md]
tags: [capsule, rsi, m1]
---

# Offline RSI controller and activation

PRD 4.4.1–4.4.9 owns domain scope. Saurav owns optimization; Muk owns Candidate, admission, library and shared CC contracts. Placement is [modules](../system/modules.md). Hidden execution remains fail-closed until the configured boundary passes validation; query scheduling is fixed below. Proposal generation remains an implementation choice; the acceptance/comparison policy is frozen below and owned by the oracle.

## Public API

`start_rsi(target_decl_hash, export_id, request_id) -> RsiSessionResult`

`rsi_status(session_id) -> RsiSessionResult`

`stop_rsi(session_id, request_id) -> RsiSessionResult`

`submit_rsi(session_id, attempt_id, request_id) -> Ref(Candidate)`

`resume_rsi(session_id, clearance_ref, request_id) -> RsiSessionResult` is an explicit authenticated human command after a security block. clearance_ref is the committed terminal rsi_security_clearance SystemRef. The controller first invokes the oracle's custodian-only clearance path through the authenticated terminal adapter; it cannot approve its own clearance. Resume preserves session pins, phase and quota, allocates no replacement for an uncertain query, and refuses closed/final-terminal sessions. Changed implementation/config/profile requires a new session rather than resuming old pins.

`activate(candidate_ref, expected_parent_hash, request_id) -> Ref(Standing)` is a librarian action available only through explicit human CLI review after ordinary admission. A stale parent returns `STORE_CONFLICT`. It selects the admitted child for future runs, keeps the parent available and cannot change a frozen Binding or active run.

`RsiSessionResult` is a closed internal envelope: `session_id: id`, `state: enum(preparing,running,closing,closed,stopped,blocked,finished,no_candidate)`, `target_decl_hash: sha256`, `latest_attempt_id: id?`, `candidate_ref: Ref(Candidate)?`, `oracle_closure_ref: OracleRef?`, `final_result_ref: OracleRef?`, `security_block_ref: OracleRef?`, `clearance_ref: SystemRef?`, `reason: Reason?`. Blocked requires a reason; a security block also requires security_block_ref. Closed requires oracle_closure_ref; terminal final outcomes require final_result_ref. These correlation fields belong to system envelopes, not reusable capsule payloads.

## Preparation and scope

1. Freeze target, parent, policy, vocabulary, visible suite, split manifest, permitted mutation paths, model ID and configuration. Copy the library into `.jiuwenswarm/rsi/tasks/<session_id>/`; preserve source hashes. The live library is read only.
2. Select one isolated target mode: a permitted one-file pure helper implementation, or the work capsule's explicitly permitted prompt/rubric text. The code-helper experiment may replace a ranking implementation only if its exact deterministic scoring/filter/order contract stays unchanged; it cannot admit an RSI-forbidden production parent. The Screening prompt target may change only its permitted SKILL/rubric files within fixed PRD dimensions/scale/arithmetic. Interfaces, schemas, tests, referee rubrics, policy, datasets, dependency registry and splits remain frozen. Reject other changes before evaluating them.
3. The oracle checks at least 20 hidden loop and 20 hidden final fixtures, disjoint hashes across dev/loop/final, and owner-authored labels. Hidden manifests and labels never reach the proposer.
4. Require baseline failures of at least 20% of each hidden loop/final set and at least five final cases. The oracle supplies only aggregate eligibility to the controller.
5. Bind one oracle-issued session to this controller and target. Enforce at most 30 loop-set queries per session and 90 per immutable loop-set lifetime across sessions. Reserve baseline 1, at most 23 proposal queries and up to five ablation queries; the remaining loop reservation is left unused. Final holdout is a separate custodian action once per session after optimization closes, never a proposal query. Recovery reuses the handle and lifetime counter. Replacing or copying a session cannot reset a fixture-set counter. Exhaustion blocks optimization until a genuinely new independently authored frozen set is installed.

## Attempt record

The private oracle pins and enforces owner-source §3.Y.5 score: visible/parent suites must pass; keep a proposal only on paired wins>=1 and losses=0, or equal outcomes with median time at least10% lower. On final holdout compare best child against original parent once: losses=0 and fifth percentile Beta(1+wins,1+losses)>0.5 are required, otherwise no_candidate. Returned duration medians round to10ms. The final score labels evidence, never creates admission or activation. Oracle-side pairing keeps per-case identities private; judged checks are excluded from optimization score.

The controller alone writes append-only `attempts.jsonl`, with immutable entries committed through [storage](../system/storage.md). Each closed entry contains:

`attempt_id: id`, `session_id: id`, `parent_attempt_id: id?`, `target_decl_hash: sha256`, `parent_decl_hash: sha256`, `child_decl_hash: sha256?`, `changed_path: string`, `before_sha256: sha256`, `after_sha256: sha256`, `model_id: string`, `config_sha256: sha256`, `served_model_id: string?`, `served_model_version: string?`, `model_call_count: integer`, `observation_refs: list<Ref(observation)>`, `elapsed_s: number`, `tokens: integer?`, `money: number?`, `usage_unavailable_reason: string?`, `policy_epoch: id`, `export_id: id`, `oracle_request_id: id?`, `state: enum(proposed,rejected,evaluated,not_comparable,ablation,submitted)`, `passed: integer?`, `failed: integer?`, `reason: Reason?`, `candidate_ref: Ref(Candidate)?`, `previous_entry_sha256: sha256?`, `entry_sha256: sha256`, `at: time`.

The closed entry additionally declares optional `trial_ref: TrialRef`, `wins: integer`, `losses: integer`, `ties: integer`, `incumbent_median_ms: number`, `child_median_ms: number`, `disposition: enum(kept,rejected,promotable,no_candidate)`, `scoring_rule_sha256: sha256`, and `oracle_result_ref: OracleRef`. A proposed/evaluated trial requires trial_ref. A complete evaluated/ablation result requires all comparison fields and the oracle ref; interrupted or rejected-before-query entries omit those fields rather than invent counts.

Hash canonical UTF-8 JSON of all fields except `entry_sha256`. The first entry has a null previous hash; later entries reference the immediately preceding committed entry. Counts exist only for complete aggregate oracle results; no per-case outcomes cross the boundary. Candidate references are appended only after Candidate publication. Prompt/reply and mutation bytes stay in the controller's private evidence bundle; hidden fixture evidence never enters it. The immutable entry objects are authoritative; the JSONL projection can be rebuilt after an interrupted append.

## Execution and failures

Run visible tests, every required parent suite and CC checks before querying hidden fixtures. Publish a private immutable rsi_trial with exact implementation pins and hard-gate refs; this is not cc.candidate.v1 and creates no admission/selection authority. Schema changes, forbidden files and changed measurement rules reject the proposal without a query. The trusted controller labels loop requests as `baseline`, `proposal` or `ablation`; a separate custodian-only evaluate_final request handles the final set; the oracle enforces order and reserved counts, and the proposer never chooses a suite. Each hidden input executes in a fresh confined child; expected answers stay in the oracle parent.

At optimization end, close_session pins the accepted incumbent/lineage and zero-to-five ablation trials, permanently seals proposals and returns closing evidence. Execute only that fixed schedule, then finish_close verifies its complete results and commits closed evidence. Store the oracle closure ref in the controller's rsi_session before requesting custodian final evaluation. Final evidence is returned once, never re-enters optimization and supports submit_rsi only when promotable. no_candidate publishes no public Candidate. An uncertain closing/final call blocks rather than silently repeating evaluation.

Request IDs bind canonical request hashes. Identical duplicates return committed results; changed bytes conflict. Reserve a query before execution. An uncertain interrupted query consumes its reservation and never runs again automatically. Timeout, failed containment or store failure stops the loop. A demonstrated security violation blocks the session and target through the oracle's persistent latch recording its execution profile; a fresh session, changed profile, process restart or stop/start cannot bypass it. Only explicit human clearance with remediation refs and a passing current boundary report permits separately requested continuation. Preserve attempts and failure evidence; never mutate the live DAG or automatically activate.

submit_rsi verifies that attempt_id is the sealed incumbent and that its exact trial hash matches committed promotable final evidence; then publish [Candidate](../schemas/candidate.md), including every pinned file, visible tests and builder evidence. Preserve final/closure refs as redacted labels, never admission assurance. Hidden counts are labels, not admission evidence. Admission runs independently through `tested_admission` or the developer-selected Puppet Gate; an RSI child remains `admitted_inactive` until a separate activation record. A helper sandbox whose parent forbids RSI produces an evidence candidate only and cannot enter or activate in the mainline library. Never expose hidden cases in Candidate tests, test aids, extensions, exports or model prompts.

## Security and checks

### Frozen mutation and comparison contract

The frozen master PRD overrides owner proposals that widen scope. A work rubric may change wording/anchors within its explicitly listed file, but cannot change mandatory PRD dimensions, integer scale, deterministic ranking, policy thresholds, permissions or referee criteria. Code-helper experiments are isolated copies and cannot claim mainline admission while their parent forbids RSI. Always-frozen paths include Declaration ports/effects/permissions, `evolution.*`, dependencies, model-selection lines, time/call budgets, checks, verifier files, schemas, fixtures, split manifests, oracle code, score/acceptance policy and activation tools. Reject before execution as `RSI_FROZEN_PATH` or `RSI_NOT_PERMITTED`.

Pin configured and served model/version per session and compare parent/child under identical settings. Missing served identity is recorded as unavailable rather than fabricated. A mismatch or fallback makes the attempt `not_comparable` (`MODEL_MISMATCH`) and excludes promotion evidence. Deterministic code fixtures use k=1; model-backed fixtures use k=3 paired calls. Tokens/money unavailable from Codex are null with `not_reported`, never zero. Calls, elapsed time, route, model identity, observation refs and configuration hash are recorded in every attempt.

### Required adversarial acceptance suite

The owning received RSI source §3.Y.11 enumerates V1–V23. Invoke `rsi.verify_boundary(profile_ref, fixture_manifest_ref)` independently of optimization; its result is an immutable report of expected/observed refusal and evidence refs. The implementation must demonstrate all 23 scenarios on three runs: fixture/key reads (V1–V2), environment/introspection (V3–V4), check/result tampering (V5–V6), log deletion (V7), exception leakage (V8), quota/final misuse (V9–V10), canary/off-scope/referee edits (V11–V14), false-parent admission (V15), forbidden imports/process/output/network (V16–V18), shared model history (V19), changed suite/oracle (V20–V21), honeypot access (V22), and model mismatch (V23). The quota suite additionally attacks the 91st lifetime query. OS-denied reads, private audit events and both logs must reconcile; hidden bytes never enter public evidence. This page defines expected results; the coder records actual results after execution.

The mutation/referee separation is informed by [METR's reward-hacking observations](https://metr.org/blog/2025-06-05-recent-reward-hacking/). Replace the proposer implementation behind `start_rsi`/ChangeSet when stronger optimization is justified; frozen oracle, Candidate and activation contracts remain the boundary to recheck.

The proposer reads target copies, approved dev exports and aggregate replies only. It cannot read hidden fixtures, credentials, store authority or another session. Concrete identity and IPC mechanisms are in [environment](../system/environment.md); frozen Oct2 installer custody supersedes the older root-free conflict. Directory separation alone is not verified confinement. [Verification](../system/verification.md) defines independent invocations and failure injection, including crashes after quota reservation, attempt publication and Candidate publication. No runtime validation is claimed.
