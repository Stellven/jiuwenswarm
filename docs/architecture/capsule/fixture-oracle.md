---
id: capsule.fixture-oracle
type: module-spec
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt, ../../product/prd-m1-rsi-full.md]
provides: [cc.rsi_fixture_oracle, cc.fixture_oracle_api]
consumes: [cc.rsi_trial, cc.rsi_security_clearance]
depends_on: [rsi-engine.md, rsi-attacks.md, ../system/environment.md, ../system/records.md]
tags: [capsule, rsi, security, m1]
level: detail
prd: [4.1.2, 4.4.9, 4.4.10]
---

# Private RSI fixture oracle

PRD: 4.1.2, 4.4.9, 4.4.10

> Answers: How does the private oracle score RSI candidates on hidden fixtures without leaking them?

## Purpose

The oracle alone reads hidden loop/final [fixtures](../system/test-surfaces.md#term-fixture) and per-case results. It [runs](../system/lifecycle.md#term-run) parent/incumbent and child in fresh confined processes under the same pinned model/settings, retaining expected answers in the comparator. Only aggregate outcomes cross into the offline controller. The proposer cannot call this service. Private identities, mounts, socket authentication and doctor [probes](../system/environment.md#term-probe) are defined in environment; an unvalidated profile is unavailable, never degraded to ordinary-user execution.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-fixture-oracle"></a>**fixture oracle** (also: private oracle) | The private service that alone reads hidden RSI fixtures and per-case results, runs parent and child in fresh confined processes, and returns only aggregate outcomes. The proposer cannot call it. |
| <a id="term-hidden-loop-set"></a>**hidden loop set** (also: loop set) | The hidden fixtures used to score proposals during an RSI session, authored by someone other than the capsule builder. Queries against it are capped at 30 per session and 90 per set lifetime. |
| <a id="term-hidden-final-set"></a>**hidden final set** (also: final set) | The hidden fixtures held by the custodian and scored only once per session, after close, to decide whether the best child is promotable. |
| <a id="term-quota"></a>**quota** | The durable limit on loop queries, reserved before a query runs. An interrupted query consumes its reservation and never reruns automatically. |
| <a id="term-trial"></a>**trial** | One recorded candidate state (parent, proposal or ablation) evaluated by the oracle in an RSI session. The controller publishes it as a private `rsi_trial`. |
| <a id="term-trialref"></a>**TrialRef** | A private `{id, sha256}` reference to a trial. It has its own namespace and cannot stand in for a Candidate reference or an Artifact reference. |
| <a id="term-planted-child"></a>**planted child** (also: planted children) | A deliberately built known-bad or known-good child variant (10 bad, 3 good) that the comparator must reject or adopt as expected before optimization is enabled. |

## Interface: closed API envelopes

All requests have protocol_version=1 and stable [request_id](../contracts/principles.md#term-request-id); `SessionResult` (`oracle_session_result`) and `AggregateResult` (`oracle_aggregate_result`) also carry `protocol_version` 1 and echo the `request_id`. Same ID plus identical canonical bytes returns committed status/result; different bytes returns REQUEST_CONFLICT. No caller supplies fixture-pool IDs, filesystem paths, cases or expected answers.

Schema per envelope: BeginRequest `library-rsi-v1.schema.json#oracle_begin_request`; status request `library-rsi-v1.schema.json#oracle_status_request`; EvaluateRequest `library-rsi-v1.schema.json#oracle_evaluate_request`; CloseRequest `library-rsi-v1.schema.json#oracle_close_request`; FinishCloseRequest `library-rsi-v1.schema.json#oracle_finish_close_request`; FinalRequest `library-rsi-v1.schema.json#oracle_final_request`; ClearSecurityRequest `library-rsi-v1.schema.json#oracle_clear_security_request`; SessionResult `library-rsi-v1.schema.json#oracle_session_result`; AggregateResult `library-rsi-v1.schema.json#oracle_aggregate_result`; TrialRef `library-rsi-v1.schema.json#trial_ref`; OracleRef `library-rsi-v1.schema.json#oracle_ref`. The status request is the explicit form of `status(session_id, request_id)`.

- `begin_session(BeginRequest) -> SessionResult`: authenticated controller only. BeginRequest is closed `{protocol_version, request_id, target_decl_hash, parent_trial_ref, model_id, model_version, config_sha256, policy_ref, permitted_paths_sha256, evaluator_sha256, execution_profile_sha256}`. parent_trial_ref is a private TrialRef for the immutable parent [snapshot](library.md#term-library-snapshot), not a public Candidate. The private evaluator manifest resolves oracle-code/scoring-rule/split hashes and binds the target/model. Missing or inconsistent pins refuse start. The oracle selects the private loop/final sets and [checks](fields.md#term-check) disjointness, at least 20 fixtures each, parent failures >=20% of each set and >=5 final cases, plus a broken-copy probe. Parent headroom uses fixture-author preflight evidence pinned before optimization; it does not expose final results or consume the terminal child-versus-parent final reservation. It mints the session and cannot reset a set's lifetime counter. An uncleared security latch refuses creation before any evaluation.
- `status(session_id, request_id) -> SessionResult`: authenticated controller/custodian; no per-case detail.
- `evaluate(EvaluateRequest) -> AggregateResult`: controller only. Closed EvaluateRequest `{protocol_version, request_id, session_id, trial_ref, purpose: baseline|proposal|ablation}`. trial_ref is a private TrialRef; no public Candidate exists during proposal evaluation. The service chooses the set/incumbent; purpose and state are verified. Baseline/proposal require running; ablation requires closing and membership in the sealed ablation schedule. No final request is accepted here.
- `close_session(CloseRequest) -> SessionResult`: controller only. Closed CloseRequest `{protocol_version, request_id, session_id, incumbent_trial_ref, accepted_lineage_refs, ablation_trial_refs}`. All three reference fields use TrialRef; ablation_trial_refs is an ordered list of zero to five separately pinned trials reverting accepted lineage [steps](../system/nodes.md#term-step). Atomically seals proposal access and validates that the incumbent/lineage match private accepted history and the ablations revert only those steps. The committed oracle_closure record fixes this schedule and state becomes closing. Proposer gets no closing ablation or final feedback.
- `finish_close(FinishCloseRequest) -> SessionResult`: controller only. Closed FinishCloseRequest `{protocol_version, request_id, session_id, closing_record_ref, ablation_result_refs}`. The oracle verifies exactly one complete private result for every scheduled ablation in order, including zero results for an empty schedule. It atomically commits oracle_closure state=closed and its result refs. Missing, interrupted or extra results refuse closure; uncertainty [blocks](../system/modules.md#term-block) the session rather than repeating a query. Closed is permanent for proposal access. Identical duplicate finish requests return the same immutable closed_session_ref used by evaluate_final.
- `evaluate_final(FinalRequest) -> AggregateResult`: custodian-only authenticated channel. Closed FinalRequest `{protocol_version, request_id, session_id, closed_session_ref}`. Only closed sessions qualify; reserve once, evaluate best child against original parent, persist complete result before returning. No new candidate or suite selector is accepted. A failed/uncertain final reservation is terminal and cannot be repeated automatically.

SessionResult is closed `{request_id, session_id?, state: preparing|running|closing|closed|finished|no_candidate|blocked, session_record_ref?, reason?}`. A session ID exists only after durable creation; non-success requires reason. For closing/closed, session_record_ref identifies the committed oracle_closure; for other states it identifies oracle_session. Closed/finished refs identify immutable private control records, not public fixture material.

AggregateResult is closed `{request_id, state: complete|denied|unavailable|boundary_violation|query_limit, passed?, failed?, wins?, losses?, ties?, incumbent_median_ms?, child_median_ms?, disposition?: kept|rejected|promotable|no_candidate, scoring_rule_sha256?, result_ref?, reason?}`. Complete requires all count fields, rounded median durations (multiples of 10 ms), disposition, score hash and committed redacted result_ref. Other states expose no counts and require reason. Counts disclose no per-case ID, input, answer, exception text, stdout or stderr.

### Private trials and control references

TrialRef and OracleRef each encode `{id:id, sha256:sha256}` but have distinct authorized namespaces and cannot substitute for Ref(Candidate), Artifact Ref or one another. The controller publishes an immutable rsi_trial in its private evidence namespace before calling the oracle. The closed payload, file coverage and authorizations are defined in [system records](../system/records.md). Trial bytes contain only the parent/child implementation snapshot and visible hard-gate evidence, never hidden cases. The oracle fetches only exact pinned trial files through the authenticated broker, rehashes them and independently validates permitted changes and hard-gate evidence before reserving a hidden query. It never fetches arbitrary paths or URIs supplied by the proposer. Existing admitted parent bytes are projected into a parent trial with the original declaration hash; no new parent Candidate is fabricated.

Session/control refs and private result refs are OracleRefs. AggregateResult.result_ref resolves only to a redacted oracle_result projection authorized for the controller; private vectors and raw outputs have no exported references. accepted_lineage_refs/ablation_trial_refs are TrialRefs; closing_record_ref/closed_session_ref/ablation_result_refs are OracleRefs. Publishing a public Candidate is a later submit_rsi action, permitted only after promotable terminal evidence, preserving [frozen](../system/lifecycle.md#term-freeze) [RSI](../rsi.md#term-rsi) source §3.Y.5's gate-before-Candidate order.

## Behavior: frozen comparison and score

For a model-backed fixture, each arm makes exactly three independent paired calls with identical pinned settings. The fixture passes only if all three satisfy [Tier 1](../verification.md#term-tier-1) and Top-1 expected label (frozen RSI source line75). Count wins/losses/ties over fixtures, not individual calls: parent fails/child passes is one win; parent passes/child fails is one loss; equal binary outcomes are one tie. This fixes the statistical denominator. One failure out of three fails the fixture. The fixed planted-child corpus contains at least ten known-bad and three known-good variants (§3.Y.5); an implementation must demonstrate the comparator rejects/adopts them as expected before optimization is enabled.

The immutable manifest pins all score behavior before the first session. Visible tests and parent suites are a mandatory hard gate before a proposal query. On the private loop set, a fixture passes only if Tier 1 passes and Top-1 matches the known-good label; model-backed target uses k=3 paired calls, deterministic target k=1. The oracle retains per-case vectors privately. Keep a child when wins>=1 and losses=0; at equal results keep only if median duration is >=10% lower. Time cannot offset any loss. Durations returned to controller round to 10ms. Execution errors are fixture failures with details private.

At final close, compare best child and original parent once. A candidate is promotable only if losses=0 and the 5th percentile of Beta(1+wins,1+losses)>0.5; with zero losses this requires at least four wins. Otherwise finish no_candidate. Judged checks are excluded from RSI's score; runtime referee remains unchanged. These are fixed RSI-source §3.Y.5 requirements, not optimizer implementation choices. Returned optimization labels never become admission/Gate assurance.

## Fixture authoring

Hidden fixtures are authored outside the build and the proposer. The oracle only reads them.

| Item | Rule |
|---|---|
| Visible dev fixtures | written with the [capsule](capsule.md#term-capability-capsule) by its author; they may reach the proposer. For `research.compile_intent` they are the 25 AI4Research live prompts with their accepted outputs |
| Hidden loop and final fixtures | written by a fixture author who is not the capsule builder, each with a known good label; hidden sets for intent are authored separately from the visible prompts |
| Custody | final set held by the custodian; the loop account never holds a key. The proposer never sees a hidden label |
| Minimum counts | at least 20 loop and 20 final fixtures, disjoint hashes across dev, loop and final; parent failures at least 20 percent of each hidden set; at least 5 final cases that the parent fails |
| Planted children | a fixed corpus of 10 known-bad and 3 known-good child variants; the comparator must reject and adopt them as expected before optimization is enabled |
| Stub evaluator | `oracle.stub` is a fixed fake evaluator with the same API that the controller may use before real fixtures exist. It scores a small fixed fixture set, never counts against any real quota and is refused by the production profile for a real session |

Three manifests pin the above before the first session. All are oracle-side records and are never exported to the controller.

| Manifest | Schema | Pins |
|---|---|---|
| evaluator manifest | `library-rsi-v1.schema.json#evaluator_manifest` | `manifest_id`, `evaluator_sha256` (the hash pinned in the sessions), oracle code, launcher, write guard and scoring-rule hashes, the planted-child manifest ref, `split_hashes` (dev, loop, final), the loop and final fixture set refs, `model_pins` (one or more `{model_id, model_version}`), `minimums`, `hash_registry_sha256` and `frozen_at`. `minimums` are floors a manifest may raise but never lower: `min_loop_cases` and `min_final_cases` at least 20, `parent_failure_floor_percent` at least 20 and `min_final_failures` at least 5 |
| fixture set manifest | `library-rsi-v1.schema.json#fixture_set_manifest` | `set_id`, `role` (loop, final or dev), `case_count` (at least 20 for loop and final), `lineage_group_ids` (a group never spans two splits), `content_sha256` (equals the matching split hash), `case_sha256s` (one hash per case, hashes only), `created_at` (the creation time of the set, not a freeze time; the freeze time is `frozen_at` in the evaluator manifest) and `headroom_evidence_ref` (null for a dev set) |
| planted child manifest | `library-rsi-v1.schema.json#planted_child_manifest` | the 10 known-bad and 3 known-good children and their expected outcomes |

A set whose hash differs from its manifest, or whose manifest was registered after the session started, is refused (`HASH_MISMATCH`, `SUITE_NOT_SEALED`; see [RSI attacks](rsi-attacks.md)).

## Failure: durable budget and recovery

| Situation | Outcome | Recovery |
|---|---|---|
| Query limit reached (30 per session, 90 per immutable loop-set lifetime) | state `query_limit` | none within the session |
| Interrupted query | its reservation is consumed and it never runs again automatically | explicit review |
| Demonstrated security violation | private `oracle_security_block`; session blocked; optimization latched for the target | `clear_security` on the authenticated human custodian channel |
| Different bytes under an existing request id | `REQUEST_CONFLICT` | new request id |


The oracle enforces 30 loop queries per session and 90 per immutable loop-set lifetime. Baseline 1, proposal at most23 and ablation at most5 leave one loop query unused. Ablations are counted conservatively inside the loop budget; unused reservations stay unused. Final custody has a separate once/session reservation after close. Hash-identical copied sets retain the same lifetime budget.

One serialized private commit reserves both session and lifetime ordinals before launching child processes. Persist reservation, evaluation state and result under an append-only private namespace; JSONL is a rebuildable view. Crashes/interruption consume the reservation and expose uncertain status. Recovery reuses committed session pins/quota and cannot mint a reset session. Final uncertainty cannot reopen proposals or reserve a second final call. Failed record writes cannot return complete.

## Tests: security and acceptance

Rows in [test surfaces](../system/test-surfaces.md#verification-table): [V26](../system/test-surfaces.md#verification-table), [V27](../system/test-surfaces.md#verification-table).

Model-backed case calls use environment's oracle ModelCallScope, exact quota/Trial/case/arm/repeat reservations and oracle_private capture refs. Hidden prompt/reply bytes stay in the oracle private capture namespace; only comparator aggregates are returned. The proposer has rsi_controller scope for its own visible generation turns, not an oracle capability. Neither private scope creates a public Candidate/run/Observation to satisfy model transport.

Only oracle identity can read fixture/code/scoring material; runner/proposer must fail actual read-access probes. Tested children have no fixture directory, credential, oracle channel, store or expected answer. They receive one required case input and an empty secret environment. Raw errors/results remain private; canary/honeypot leakage blocks the session. Supervisor/runtime store exports cannot read private quota or cases.

Any demonstrated security violation atomically records a private oracle_security_block, marks the affected session blocked and latches further optimization for its target, recording the offending execution-profile hash. All evaluate/close/final calls and new sessions for that target, including changed profiles, are refused with RSI_SECURITY_CLEARANCE_REQUIRED while the latch is active; restarting or copying a session cannot clear it. If the durable block cannot be written, stop the service and refuse startup until reconciliation records the incident. Expected attack refusals in the isolated acceptance suite are attributed to their test sessions; they cannot clear an existing real-session latch.

`clear_security(ClearSecurityRequest) -> SessionResult` is available only on the authenticated human custodian channel. Closed request `{protocol_version, request_id, session_id, security_block_ref, clearance_ref}` uses an OracleRef for the exact incident and a [SystemRef](../system/records.md#term-systemref) to the terminal-written rsi_security_clearance. Validate authenticated actor, matching incident/target/profile, remediation evidence and a passing current boundary report before committing oracle_security_clearance and clearing the latch. The controller/proposer cannot write or invoke clearance. Clearance permits only a separately requested explicit continuation with unchanged pins and remaining quota; it never reopens closed proposals, repeats an uncertain query/final evaluation, resets counters or activates a version. A changed security profile or implementation requires a new session and attributable clearance covering the prior incident. Frozen master PRD4.4.10 requires this human clearance before autonomous optimization continues.

The required suite RSI-S01 to RSI-S24 ([RSI attacks](rsi-attacks.md), S24 being the 91st lifetime query) is run by `rsi.verify_boundary` ([RSI engine](rsi-engine.md#required-adversarial-acceptance-suite)). Test interrupted reservations, log-chain repair/refusal, early/duplicate final access, model mismatch, forged incumbent/lineage, score tampering and each forbidden path/network/credential access. No executed security or scoring result is claimed here. Referee isolation follows [METR's reward-hacking observations](https://metr.org/blog/2025-06-05-recent-reward-hacking/); replace the comparator implementation behind this API only through a new frozen manifest and validation, never by proposer mutation.
