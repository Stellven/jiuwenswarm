---
id: system.model-bridge
type: module-spec
status: draft
version: 1
sources: [environment.md, model-auth.md, ../capsule/runner-broker.md]
provides: [system.model_bridge]
consumes: [system.secure_ipc, system.config, system.model_auth]
depends_on: [environment.md, model-auth.md, records.md, ../capsule/runner-broker.md, ../contracts/principles.md]
tags: [system, m1, model, ipc, security]
level: detail
prd: [3.0.1, 3.0.2, 4.3.3, 5.4.3]
---

# Model bridge

PRD: 3.0.1, 3.0.2, 4.3.3, 5.4.3

> Answers: How does one authorized model turn travel from the runner to the Codex app-server and back, and what happens when it fails?

## Purpose

The model bridge (block B11) is the only code that holds model credentials and talks to the Codex app-server. The [CC runner](../capsule/runner.md#term-runner) and, in the experiment track only, the planner call it. Capsule code never does. The bridge turns one authorized, scoped request into one model turn, captures the raw prompt and reply, and returns a text result. It serializes CC turns: one blocking exchange per turn. It picks no [capsule](../capsule/capsule.md#term-capability-capsule), gives the model no tools, shell or web, and never resubmits a turn silently. [Model authentication](model-auth.md) is the home of profile custody and the replaceable AuthProvider; [environment](environment.md) is the home of configuration keys, model-call scope and reservations; the runner side of the call is the [model client contract](../capsule/runner-broker.md#the-model-client-contract-m05).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-model-bridge"></a>**Model bridge** (also: bridge, model bridge) | The only code that holds model credentials and talks to the Codex app-server. It turns one authorized, scoped request into one captured model turn and returns text. |
| <a id="term-model-turn"></a>**Model turn** (also: turn, model turns) | One blocking prompt-and-reply exchange through the bridge. Each turn is reserved first, captured before success and counted against the call budget. |

## Interface

Messages of the bridge.

- **Who a model call belongs to** (call, supervisor -> bridge). Schema: [`services-v1.schema.json#model_call_scope`](../contracts/services-v1.schema.json).
- **A captured prompt or reply, by namespace and ref** (record, bridge -> authorized capture writer). Schema: [`services-v1.schema.json#scoped_capture_ref`](../contracts/services-v1.schema.json).
- **One model turn, cancel or status request** (call, runner broker -> bridge, or planner in the experiment track -> bridge). Schema: [`services-v1.schema.json#model_bridge_request`](../contracts/services-v1.schema.json).
- **The model turn result** (call, bridge -> runner broker). Schema: [`services-v1.schema.json#model_bridge_result`](../contracts/services-v1.schema.json).
- **Capture kept by the oracle or [RSI](../rsi.md#term-rsi) controller** (record, bridge). Schema: [`services-v1.schema.json#private_model_capture`](../contracts/services-v1.schema.json).
- **Time and turn limits for one call** (helper, supervisor -> bridge). Schema: [`services-v1.schema.json#model_call_limits`](../contracts/services-v1.schema.json).
- **Reservation made before a model call** (record, supervisor -> store). Schema: [`services-v1.schema.json#model_call_reservation`](../contracts/services-v1.schema.json).

The operations of `model_bridge_request` are `turn`, `cancel` and `status`. A `turn` carries a scoped prompt capture ref. `cancel` and `status` carry their own request id and the `target_request_id` of an existing turn in the same scope, with a null prompt ref. The states of `model_bridge_result` are `complete`, `cancelled`, `unavailable`, `timed_out` and `denied` for a turn, plus `queued` and `running`, which appear only in the answer to a `status` operation. Frames are length-prefixed: a 4-byte big-endian length, then UTF-8 JSON, at most `cc.ipc.max_frame_bytes` (default 1 MiB); prompts and replies travel by capture ref, never inline ([message principles](../contracts/principles.md#5-frames)).

## Behavior: one turn

1. **Channel.** The bridge listens on a protected Unix domain socket (UDS) between the supervisor/runner and itself: socket parent mode 0700, socket mode 0600, file user checked before connect, no symlink in the path, no TCP listener. The existing app-server transport uses inherited stdio (`jiuwenswarm/server/runtime/codex_subscription/transport.py:97` at `6cc05c36b`); it stays inside the bridge.
2. **Capability token in the first frame.** The supervisor opens the connection before it drops the runner's identity and passes only the connected descriptor to the runner. The first frame on a connection carries a random capability token bound to the scope, the permitted model and the capture root. Tool children do not inherit the descriptor. Peer credentials plus the capability token, the request id and the pinned scope and model context authorize each call. A frame without a valid token closes the connection.
3. **Reservation first.** Before forwarding any turn the broker commits `model_call_reserved` (see [records](records.md#public-model-call-reservation-semantics)); a failed reservation write means zero model turns.
4. **One blocking exchange per turn.** The broker sends one `turn` request (the prompt already stored as scoped capture) and waits for the result. The bridge [runs](lifecycle.md#term-run) one turn at a time. A fresh native session id is derived from the canonical scope hash, request id, obs id and turn, so every turn is a new conversation and the full exchange is re-sent each time.
5. **Capture before success.** The bridge sends raw prompt and reply bytes only to the authenticated scope writer and waits for its committed reference before it returns `complete`. A `complete` result carries `reply_content_ref` and `reply_content_sha256`, which the caller [checks](../capsule/fields.md#term-check) against the committed record and against the payload bytes.
6. **Status.** `status` for a target request returns `queued`, `running` or the terminal state. These two states are not returned to a `turn`: a turn that cannot finish ends in one of the terminal states.
7. **Duplicates.** Identity is scope plus `request_id`. Identical bytes reuse the existing status or result; changed bytes are a conflict. No timeout resubmits a paid turn.
8. **Cancel.** Cancel abandons the requester, drains remaining events for `cc.model.cancel_grace_s` (default 5 seconds), then kills and reaps only the bridge's own app-server child if the stream has not completed. It never touches the shared user-chat transport and never resubmits.
9. **Replies to the runner.** A `complete` result becomes the model client reply text. `timed_out` is `TIMEOUT`. `unavailable`, `denied` and `cancelled` are `RUNTIME_UNAVAILABLE`. A `status` answer of `queued` or `running` after the capsule's own deadline is mapped by the broker to `BUDGET_EXCEEDED` and the broker cancels the request. The mapping table is on [runner broker](../capsule/runner-broker.md#the-model-client-contract-m05).

A request that names a research `run_id` is not required for private calls: the scope identifies the caller (planning in the experiment track, run, admission, RSI controller or oracle). Planning, admission, RSI and oracle calls use fixed pinned models; only the run scope may use a routing selector.

## Custody and limits

- The release mounts one dedicated writable persistent `CODEX_HOME` directory used only by the bridge. Separate login and exclusive locking replace per-run credential injection; managed refresh stays with Codex. Auth management returns status and device challenges only to local setup, never tokens to research or benchmark callers ([model auth](model-auth.md)).
- The bridge holds a dedicated app-server transport instance and child, separate from the native user-chat transport. No credentials or child-control descriptor cross into tools.
- chmod alone does not isolate same-UID malicious processes, and the design does not claim it does: trusted local [ordinary module](../capabilities/README.md#term-ordinary-module) code remains part of the threat boundary.
- Each audit retains the requested and the effective seed and the unavailable reason; an unsupported seed is not reported as applied.
- Serialization, cancel grace and reaping are adapter requirements, not a claim that the existing shared service already has these semantics.

## Failure

| Situation | Outcome | Recovery |
|---|---|---|
| Authentication lost during a turn (`AUTH_RELOGIN_REQUIRED`) | result `unavailable`; the call [blocks](modules.md#term-block), capture is kept; the run [halts](lifecycle.md#term-halt) as `ENVIRONMENT_BLOCKED`; the possibly paid turn is never resubmitted | login, then a human `cc resume <run_id>` (action `resume_after_fix`) starts a new attempt of that step under the same pins |
| Duplicate request id with identical bytes | the existing status or result is returned; no second turn | none needed |
| Duplicate request id with changed bytes | `REQUEST_CONFLICT` | submit under a new request id |
| Cancel and the stream has not completed after `cc.model.cancel_grace_s` | the bridge kills and reaps only its own child; capture is kept | explicit startup or recovery; a new transport is never started by an automatic retry |
| Deadline passes | before submission: `RUNTIME_UNAVAILABLE`; after submission inside the capsule deadline: `TIMEOUT` for an upstream timeout; past the capsule deadline: `BUDGET_EXCEEDED` | explicit human review |
| Provider error (usage limit, failed turn, unsupported model hint) | result `unavailable` with a safe reason; no retry | fix the account or model setting, then `cc resume` |
| Required capture cannot be committed | no `complete` result; the call halts with preserved evidence | repair storage, then `cc resume` |
| Frame over `cc.ipc.max_frame_bytes`, missing or wrong capability token | the connection closes; request denied | send the prompt by capture ref with a valid token |

The same rules apply when the model is unavailable for another reason: the run halts as `ENVIRONMENT_BLOCKED` and only a human `resume` starts a new attempt.

**Open item.** The capability token has no field in a schema def yet. Until a def carries it, the first-frame token is part of connection setup and is checked by the bridge before any `model_bridge_request` is read.

## Tests

Fixtures and fakes: a fake app-server replaying recorded replies with delayed, auth-failed and duplicate cases; one bounded real call through the bridge. Rows in [test surfaces](test-surfaces.md#verification-table): [V01](test-surfaces.md#verification-table) (token refused, timeout, auth lost), [V02](test-surfaces.md#verification-table) (one live turn), [V37](test-surfaces.md#verification-table) (auth loss halts the run and no second paid turn is submitted at the supervisor). Observable outcomes: exactly one turn reaches the fake app-server per request id; captured bytes equal the sent prompt and the returned reply; `queued` and `running` appear only in `status` answers.
