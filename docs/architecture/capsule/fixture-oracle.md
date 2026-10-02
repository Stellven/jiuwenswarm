---
type: design
status: blackbox
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [cc.rsi_fixture_oracle, cc.fixture_oracle_api]
consumes: [cc.candidate]
depends_on: [process-boundary.md, library.md, ../schemas/candidate.md, ../schemas/checks.md]
tags: [capsule, rsi, security, m1, blackbox]
---

> **Black box: RSI fixture oracle.** The full PRD requires hidden historical fixtures to remain outside the proposer’s reach. The provisional API below returns aggregate pass/fail counts only. Oracle identity, OS permissions, IPC authentication and the pre-check are open under issue 40; this service is not the Stage 3.7 benchmark process boundary.

# RSI fixture oracle

The fixture oracle is the only component that can read hidden RSI fixtures. It evaluates an RSI candidate in a fresh child process, one fixture input at a time, and returns only aggregate results. The RSI proposer submits a candidate reference under an oracle-issued session; it never chooses a suite and never reads hidden inputs, expected outputs, or raw child output.

**Source:** PRD 4.4.9 (hidden fixture sets, fresh subprocess, aggregate-only response, at most 30 queries per session) and 5.4.3 (oracle-only filesystem access, active Swarmflow runner pre-check). This page does not extend the oracle to user benchmarking or ordinary capsule admission.

## Provisional API

`evaluate(FixtureEvaluationRequest) -> FixtureEvaluationResult`

`begin_session() -> session_id`

`begin_session` is available only over the authenticated local channel to the RSI controller. The oracle mints the session id and binds it to that caller; an arbitrary client-supplied id is rejected. Exact IPC credentials and principal setup remain open under issue 40.

### `FixtureEvaluationRequest`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `request_id` | `id` | yes | Unique request/result join key. |
| `session_id` | `id` | yes | Oracle-issued session handle bound to the authenticated RSI controller; callers cannot mint or rebind it. |
| `candidate_ref` | `Ref(Candidate)` | yes | Submitted child candidate whose implementation is tested. |
| `purpose` | `enum(baseline, proposal, ablation, final)` | yes | Trusted-controller request class. The oracle validates the session state and chooses the corresponding private suite; the proposer cannot set it. |

The request carries no fixture input, expected output, suite selector, or arbitrary filesystem path. The trusted controller supplies `purpose` over an authenticated channel; the oracle state machine permits baseline once, proposals before close, at most five accepted-lineage ablations during close, and final once after close. It selects loop/final suites internally. The proposer cannot call the oracle or select a weaker suite.

### `FixtureEvaluationResult`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `request_id` | `id` | yes | Echo of the request. |
| `state` | `enum(complete, denied, unavailable, boundary_violation, query_limit)` | yes | Distinguishes an evaluation result from an unavailable or failed security boundary. |
| `passed` | `integer?` | no | Aggregate count only, present when `state` is `complete`. |
| `failed` | `integer?` | no | Aggregate count only, present when `state` is `complete`. |
| `reason` | `Reason?` | no | Required for a non-complete state. |

The service enforces: one baseline reservation, at most 23 proposal reservations, at most five ablation reservations and one final reservation. Proposal calls cannot consume the final six. A call outside the state machine or budget returns `query_limit` without reading a fixture. Persist reservations before launching children. Identical request IDs, candidate hashes and purpose return the existing result; changed bytes are denied. Interrupted reservations consume quota and are not replayed. Audit evidence stays oracle-only. Complete results expose no per-case outcome, input, expected answer, stdout, stderr or patch content.

## Security contract

1. Only the oracle identity can read the hidden fixture directory. The active Swarmflow runner and RSI proposer must fail an automated read-access pre-check before the RSI service starts if this boundary is degraded.
2. Candidate execution happens in a fresh subprocess with no direct path or credential to the hidden fixture store. Only the case input reaches the child. The expected answer stays in the oracle parent, which compares the result internally.
3. The response is aggregate-only. Raw cases, expected outputs and child output stay in restricted records; the proposer receives only pass/fail counts and a non-sensitive status/reason.
4. Any failed access pre-check or containment invariant returns `boundary_violation` and blocks RSI. It cannot become a candidate failure or a scientific result.
5. The concrete user/account and IPC design remains provisional under issue 40. Do not infer that a separate UID alone prevents network or other system effects.

## Waiting on

- Issue 40: settle the oracle and runner principals, POSIX permissions, and authenticated request channel against PRD 4.4.9 and 5.4.3.
- Issue 54: define backend-specific effect enforcement and infrastructure failure mapping.
- Implementation validation must prove the 30-query state machine, reserved headroom and final-set non-disclosure.

Until those inputs are settled and the canary passes, this is a provisional contract, not an implementation-ready security guarantee.
