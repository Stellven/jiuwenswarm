---
id: capsule.runner-broker
type: module-spec
status: draft
version: 1
tags: [capsule, draft, runner, m1, broker]
level: detail
prd: [4.1.4, 4.2.1]
provides: [cc.runner_broker, cc.model_client]
depends_on: [runner.md, runner-handlers.md, gate-host.md, ../system/model-bridge.md, ../system/lifecycle.md]
---

# Runner model client, broker and Swarmflow backend

PRD: 4.1.4, 4.2.1

> Answers: How do model calls, nested calls, the engine backend, permissions and records work around the runner pipeline?

## Purpose

This page is the third part of the [CC runner](runner.md). The **broker** (R7) is the one place the runner enforces `needs.external`: every call a [capsule](capsule.md#term-capability-capsule) makes to another capsule, and every model call, goes through it. This page also holds the model client (M05) contract, the four callers of the pipeline, the [Swarmflow](../system/integration.md#term-swarmflow) backend `CcBackend` that sits on the supervisor side and calls the runner and then the [Gate host](gate-host.md#term-gate-host), the permission table, the records the runner returns for commit, and its observability hooks.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-broker"></a>**broker** | The one place inside the runner where `needs.external` is enforced: every nested call to another capsule and every model call goes through it. It also counts and limits model turns. |
| <a id="term-ccbackend"></a>**CcBackend** | The supervisor-side Swarmflow backend that sends each node to the runner, then calls the Gate host, and only then lets the engine release the node. One backend serves each run. |
| <a id="term-dispatch"></a>**dispatch** | The caller kind for a workflow node's call (the others are `gate`, `admission` and `nested`). Every dispatch call is followed by the Gate host before the node is released. |

## Interface

Messages of the broker and the backend.

- **Args to start the generic SwarmFlow script for one phase** (call, supervisor -> workflow script). Schema: [`execution-v1.schema.json#workflow_start_args`](../contracts/execution-v1.schema.json).
- **Prompt of the SwarmFlow agent() call: [decl_hash](fields.md#term-decl-hash), input refs, [step_id](../system/records.md#term-step-id)** (call, script -> CcBackend). Schema: [`execution-v1.schema.json#call_descriptor`](../contracts/execution-v1.schema.json).
- **Per-step envelope returned by agent()** (call, CcBackend -> engine -> script). Schema: [`execution-v1.schema.json#step_envelope`](../contracts/execution-v1.schema.json).
- **[Gate](../verification.md#term-gate) call and result** (call, CcBackend -> Gate host). Schema: [`execution-v1.schema.json#gate_request`](../contracts/execution-v1.schema.json), [`execution-v1.schema.json#gate_result`](../contracts/execution-v1.schema.json).
- **M05 complete() call context and its mapping to model_bridge_request** (call, runner broker -> model client (M05)). Schema: [`execution-v1.schema.json#model_client_call`](../contracts/execution-v1.schema.json).
- **M05 reply or error and its mapping from model_bridge_result** (call, model client (M05) -> runner broker). Schema: [`execution-v1.schema.json#model_client_reply`](../contracts/execution-v1.schema.json).
- **Event relay to the supervisor bus** (frame, runner -> supervisor). Schema: [`execution-v1.schema.json#event_envelope`](../contracts/execution-v1.schema.json), [`execution-v1.schema.json#runner_event`](../contracts/execution-v1.schema.json).

## Behavior: who calls whom around one call

| Step | Caller | Callee | What |
|---|---|---|---|
| 1 | Swarmflow script | engine, then CcBackend | one `agent()` call per node, prompt is the call descriptor |
| 2 | CcBackend (supervisor) | runner | `runner_request` call; the supervisor committed the reservation first |
| 3 | handler code | broker | a nested call or a model call, only through the broker |
| 4 | broker | M05, then the [model bridge](../system/model-bridge.md) | one blocking model [turn](../system/model-bridge.md#term-model-turn) |
| 5 | runner | supervisor | `commit_request`; the supervisor commits and the runner answers `runner_response` complete |
| 6 | CcBackend (supervisor) | Gate host | `gate(obs_ref)`; the supervisor then [releases](../system/lifecycle.md#term-release) the node |

## The model client contract (M05)

The trusted broker additionally exposes the read-only [StageContext](../capabilities/write-report.md#term-stagecontext) API defined in [Write report](../capabilities/write-report.md#template-and-complete-inputs). It binds run/through-step scope to the current reserved call, captures the exact referenced record hashes in [Observation](../schemas/observation.md#term-observation).ext.runner.context_refs, and supplies bounded summaries/refs to the report skill. The model cannot request another run, arbitrary paths or hidden records. Reading prior evidence is recorded behavior, not permission to change it. The shared type and API stay on the report capability; no second StageContext schema is defined here.

The runner depends on M05 through one call. M05 is designed with Model Routing; this is what the runner needs from it. The wire to the [Codex adapter](../system/integration.md#term-codex-adapter) is on [model bridge](../system/model-bridge.md).

```python
@dataclass(frozen=True)
class ModelCallContext:       # which capsule call a model turn belongs to; for M05's records and an endpoint that routes itself
    scope: ModelCallScope     # canonical discriminated scope, defined in services-v1 and environment
    obs_id: str
    turn: int                 # 1, 2, ... within that call
    capsule_name: str | None  # null for non-capsule planner/controller calls
    decl_hash: str | None
    step_id: str | None
    role: str | None          # the Binding's role (unchecked at M1)

@dataclass
class ModelReply:
    text: str
    request_id: str               # the model bridge request_id this reply answers
    model_id: str | None          # None when the runtime does not report it
    elapsed_s: float
    tokens: dict | None           # {input, output, cache_hit}, when reported
    route_record_id: str | None   # set only by an endpoint that routes itself (a gateway); a capsule's own routing comes through cc.model's route_id

async def complete(prompt: str, *, model_hint: str | None, session_id: str, deadline: float,
                   context: ModelCallContext) -> ModelReply: ...
# raises ModelError(reason) where reason is a reason_code registry value
```

This page is the home of ModelCallContext, ModelReply, complete and ModelError. Schema: `execution-v1.schema.json#model_client_call` for the call and its context, `execution-v1.schema.json#model_client_reply` for ModelReply or ModelError. M05 sends the reserved request to the protected [model bridge](../system/model-bridge.md); only that [bridge](../system/model-bridge.md#term-model-bridge) calls the native stream adapter. Router integration is on [placement](../placement.md#model-routing-in-one-view). Each native session is used for one turn, and the bridge retains one request/result identity across transport retries without resubmitting the model call.

**Mapping to the model bridge.** The bridge wire shapes are `services-v1.schema.json#model_bridge_request` and `services-v1.schema.json#model_bridge_result`. M05 maps one `complete()` call to one bridge request, and the bridge result back to one reply:

| `complete()` / ModelCallContext | model_bridge_request |
|---|---|
| `context.scope` | `scope` (same ModelCallScope) |
| `context.obs_id`, `context.turn` | `obs_id`, `turn` |
| (always) | `operation: turn`, `target_request_id: null` |
| `session_id` | `session_id` |
| `model_hint`, else the model of the reserved model_call_reservation | `model_id` |
| `deadline` (monotonic) | `deadline_at` (absolute time) |
| `prompt` stored first as scoped capture | `prompt_content_ref` (namespace public_artifact for run, planning and admission scopes) |
| broker allocates from the reservation | `request_id` |
| `capsule_name`, `decl_hash`, `step_id`, `role` | not sent; local audit metadata only |

| model_bridge_result | ModelReply or ModelError |
|---|---|
| `state: complete`, reply bytes read from `reply_content_ref` and checked against `reply_content_sha256` | `ModelReply.text` |
| `request_id` | recorded in the turn entry and in `ModelReply` (`request_id`) |
| `state: timed_out` | ModelError `TIMEOUT` |
| `state: unavailable`, `denied`, `cancelled` | ModelError `RUNTIME_UNAVAILABLE` (`AUTH_RELOGIN_REQUIRED` is a case of `unavailable`: the run [halts](../system/lifecycle.md#term-halt) as `ENVIRONMENT_BLOCKED`, see [model auth](../system/model-auth.md)) |
| `queued` or `running` at the deadline | ModelError `RUNTIME_UNAVAILABLE`: the broker stops waiting and cancels the reserved bridge request (`queued` and `running` appear only in answers to a `status` operation). The runner then ends the call by its own capsule-deadline rule |
| a reservation or budget ceiling reached (`BUDGET_EXCEEDED` from the bridge) | ModelError `BUDGET_EXCEEDED` |
| an empty prompt (`INVALID_INPUT`) | ModelError `CAPSULE_ERROR` |
| not in the result | `model_id`, `tokens`, `route_record_id` come from the model audit record and are null when not reported |

**Replay at admission.** When a [test case](../schemas/checks.md#term-test-case) carries model_replies, M05 returns them in turn order instead of calling Codex. There is one sequence across the complete call tree, including nested capabilities and the routing adapter's bounded judge if enabled in that fixture. A missing reply is RUNTIME_UNAVAILABLE.

**Model transport cancellation.** M05 calls the authenticated [model bridge](../system/model-bridge.md), which is the home of the native subscription stream and raw capture. Cancellation means stop waiting and cancel the reserved bridge request; it never resubmits a turn. `model_client_reply` therefore carries one of the reasons `TIMEOUT`, `RUNTIME_UNAVAILABLE` or `BUDGET_EXCEEDED`; the handler ends the call `error` with that reason. The bridge drains an abandoned stream for at most the configured grace period, then terminates its dedicated CC app-server process if necessary. It never terminates a shared user-chat transport. Missing response or forced transport exit halts the call with preserved evidence. A new transport is established only by a subsequent explicit startup/recovery, not an automatic model retry.

**Deadlines.** A timeout before acquiring the serialized model-turn slot is RUNTIME_UNAVAILABLE; after submission an upstream runtime timeout is TIMEOUT, a bridge answer still queued or running at the deadline is RUNTIME_UNAVAILABLE, and a reached reservation or budget ceiling is BUDGET_EXCEEDED. [Lifecycle](../system/lifecycle.md) identifies the clock authority. No successful result is returned before required request/reply capture is committed.

**Error mapping**, from the `CodexError` codes the service and its transport raise (`service.py:131-194`, `transport.py:60-163`):

| `CodexError` | `ModelError` reason | Responsible party |
|---|---|---|
| `RUNTIME_TIMEOUT` | `TIMEOUT` | runtime |
| `SIGN_IN_REQUIRED`, `SUBSCRIPTION_REQUIRED`, `ACCOUNT_IDENTITY_UNAVAILABLE`, `RUNTIME_DISCONNECTED`, `NEW_SESSION_REQUIRED`, `BUSY` | `RUNTIME_UNAVAILABLE` | runtime |
| `TURN_FAILED` (the turn ended in a failed state, such as a usage limit) | `RUNTIME_UNAVAILABLE` | runtime |
| `RUNTIME_ERROR` (any JSON-RPC error, including a model hint the runtime rejects at `thread/start` or `turn/start`), `DELIVERY_UNKNOWN`, `PROFILE_IN_USE`, `PROFILE_CONFIG_CONFLICT`, `PROFILE_STATE_INVALID`, `RUNTIME_VERSION_MISMATCH`, `RUNTIME_UNAVAILABLE`, any other `CodexError` or unexpected exception | `RUNTIME_UNAVAILABLE` | runtime |
| a `chat.final` with `cancelled: true` (the turn was interrupted) | `RUNTIME_UNAVAILABLE`, never a success | runtime |
| `INVALID_INPUT` (an empty prompt) | `CAPSULE_ERROR` | capsule |

**Every turn is recorded.** For each model turn the runner stores the prompt as sent and the reply text as content (`cc/content/<sha256>`), and appends one entry to the Observation's `ext.runner.turns`: `{turn, session_id, prompt_sha256, reply_sha256, elapsed_s, model_hint, model_id, tokens, route_record_id}`. Schema: `execution-v1.schema.json#runner_turn_entry`. `model_hint` is the model this turn asked for; `route_record_id` is the `route_id` the capsule passed to `cc.model`, else `ModelReply.route_record_id`. So the exact exchange can be rebuilt from records ([seams](../system/seams.md#data-foundation)). When any turn reports `tokens`, the Observation's `cost.tokens` is their sum.

**The model field.** `stream()` reports no model id or version. So a model enters the Observation's `models` only when a turn's `model_id` is not `None`; with Codex at M1, `models` is absent. `models` lists each distinct reported model once, in order of first use; `ext.runner.turns` says which turn used which, and what each turn asked for. The runner never records a model it was not told served the call.

**The thread's own settings.** The service starts Codex threads read-only, with `approvalPolicy: untrusted` and fixed developer instructions that say tools are unavailable (`service.py:148`). The skill prompt tells the model not to run commands. If Codex still sends a tool or approval request, the transport refuses it at once with error -32601 (`transport.py:148`). The turn then goes on, or ends `TURN_FAILED`.

## Nested calls and the broker

Every call a capsule makes to another capsule, and every model call, goes through the **broker** (R7). The broker is the one place the runner enforces `needs.external`.

**A nested call, exactly:**

1. Look up `ref` among the caller's `needs.external[].ref`. Not found: no call and no Observation. A tool gets `cc.NestedRefused`; a skill's reply fails its parse rule. If uncaught, either ends the caller with `CAPSULE_ERROR`. (The [reason code](../schemas/policy.md#term-reason-code) `OPERATOR_NOT_ADMITTED` is meant for this case, but the policy says it is never the reason of a call; see [asks](runner.md#what-this-design-asks-of-other-pages) 2.)
2. Write each input value as an Artifact: `origin: control`, the caller's scope. `causation_id` is the caller's `obs_id`, so the record shows which call produced the value.
3. Run the pipeline with `caller: nested`, `decl_hash` from `needs.external[].decl_hash`, and the caller's [Binding](../schemas/binding.md#term-binding) as `binding_ref`. Step 3 computes the expected `code_sha256` from the callee's [Declaration](fields.md#term-declaration).
4. The budget is the earlier of the caller's deadline and the callee's own `needs.resources.timeout_s` (or the policy default), measured from now.
5. The nested Observation's `causation_id` is the caller's `obs_id`, so the call tree can be rebuilt from records.
6. Return `{port: {"ref": Ref, "value": value}}` and the outputs' `issues` on `ok`; otherwise `{obs_id, outcome, reason}`. An input given as `cc.input_ref(port)` is bound to the caller's own input Artifact, and step 2 stores nothing for it.

**Gate scope.** Every dispatch call has a Gate. A nested operator call (`op.*`) gets a mechanical [Verification](../schemas/verification-record.md#term-verification), persisted before it returns, and is covered by the parent node's Gate. Before returning a nested operator's output to the parent, the Gate host persists its Verification using the parent's [frozen](../system/lifecycle.md#term-freeze) dependency [GateProfile](../schemas/profiles.md#term-gateprofile). Pure mechanical [operators](../capabilities/README.md#term-operator) have deterministic [checks](fields.md#term-check) and [Tier 2](../verification.md#term-tier-2) status [NOT_RUN](../decisions.md#term-not-run) with a reason explaining the empty semantic-criteria set; the parent stage's independent semantic Gate includes nested evidence before downstream release. A nonadvancing or unsaved nested Verification fails the parent call. This grants no workflow release authority. The parent's cost.time_s includes nested execution/check time. Gate/referee calls are not recursively gated. The nested verifier review inside `research.compile_intent` is validated by the calling capsule and is not itself Gated.

**A model call:** the broker calls M05 `complete` with the caller's deadline and a session id `cc:<scope id>:<obs_id>:<n>`, where `n` counts the caller's model turns from 1.

**Effects nest; network does not.** A nested call is checked against its own Declaration at step 6. A `pure` caller that pins an `irreversible` dependency would hide that effect, so admission refuses it (proposed rule `effects_cover_dependencies`, in the [policy](../schemas/policy.md)). `needs.network` is different: a capsule declares only the network access its own code uses. A capsule that reaches a service only through an operator declares `network: none`, and the operator declares `egress`. `op.scholarly_search` declares `egress`, but its child process has no network: the egress itself is brokered.

## The four callers

One pipeline serves four callers. Only the [steps](../system/nodes.md#term-step) around it change. A gate, nested or admission call carries no `caller` in its `runner_request`: the caller [kind](capsule.md#term-capsule-kind), the parent observation and the ordinal come from the Reservation that `reservation_ref` names.

| Caller | Who calls | Binding (step 1) | Expected `code_sha256` (step 3) | Budget | After the call |
|---|---|---|---|---|---|
| `dispatch` | R1 (CcBackend), for a workflow node | looked up by `(run_id, step_id)` | the Binding's | `budget.time_s` | R1 calls the gate, after the supervisor committed the Observation |
| `gate` | the gate host (M10), for the step's judged checks | the node's Binding; [runs](../system/lifecycle.md#term-run) its `verifier` (the gate capsule) | `verifier.code_sha256` | `verifier.budget.time_s` | the gate host reads the output |
| `admission` | M14, for each test case | none; `binding_ref` is null, `test_ref` is the test case | computed from the Candidate's Declaration | `timeout_s`, else policy default 600, never over the cap 1800 | M14 runs the checks |
| `nested` | R7 | the caller's | computed from the callee's Declaration | the [nested rule](#nested-calls-and-the-broker) | returned to the caller |

**An admission call** has its own entry, `call_admission(decl_bytes: bytes, test_case_ref: Ref, workspace: Path, *, vocabulary_ref: dict, policy_ref: dict) -> (Ref, str)`, returning the Observation ref and outcome. It needs a workspace and a Declaration that admission has not stored yet. M14 passes both: the Declaration bytes (step 2 checks their hash against the computed `decl_hash`) and a fresh empty workspace folder. Before the call, the runner copies each of the test case's `fixtures` into that folder, at its `content_ref.name`. M14 deletes the folder afterwards. At step 6 an admission call is unattended.

## Swarmflow backend: talking to the engine

The engine calls `AgentBackend.run(prompt, opts, schema_json, *, call_key)` and expects an `AgentResult` (agent-core `openjiuwen/agent_teams/workflow/engine/backends/base.py:118`). `CcBackend` is that backend.

**One backend per run.** The [fixed prep plan](../system/lifecycle.md#term-prep-plan) and, after requirements, the planned DAG both run through it from the same [library snapshot](library.md#term-library-snapshot) ([toolchain](toolchain.md#m03-freeze-the-binding-writer)). The supervisor starts the generic script once per phase: the second start, for the planned phase, passes `plan_ref` and `pins_ref` of the [planned plan](../types/run-plan.md#term-planned-plan) (decision D-a). The backend contract is the same for both. The launcher builds `CcBackend(run_id=..., workspace=..., store=..., runner=<runner client>, gate=<Gate host>)` in the supervisor and passes the same `run_id` to freeze and to `run_workflow(path, args=..., backend=..., run_id=..., journal_path=..., resume=..., abort_event=...)` (`engine/runner.py:294`). The launcher always passes `CcBackend` (with no backend the engine silently uses a mock, `runner.py:358`) and always passes `run_id` (a `None` id lets the journal cache match on the call signature alone). `args` are references only: never secrets, never `None`, because the engine journals them. `run()` does not receive a run id, so the backend holds it, with the run's workspace folder. Policy and vocabulary are loaded per call from the Binding's pins.

**What the script gets.** The supervisor passes `args` (schema `execution-v1.schema.json#workflow_start_args`). Phase `prep`:

```json
{"version": 1, "run_id": "run-...", "phase": "prep",
 "plan_ref": {"id": "plan-prep", "sha256": "..."}, "pins_ref": {"id": "batch-prep", "sha256": "..."},
 "inputs": {"intake": {"id": "art-...", "sha256": "..."}, "source_text": {"id": "art-source", "sha256": "..."}}}
```

Phase `planned` adds `prep_release_refs` (the committed release records of the prep steps), so a `prep.<step_id>.<port>` source resolves only to a released prep output.

`plan_ref` names the phase's [`run_plan`](../types/run-plan.md) control Artifact. `pins_ref` names the commit [batch](../system/storage.md#term-commit-batch) manifest (`execution-v1.schema.json#commit_batch_manifest`) that maps each `step_id` to its committed Binding Ref from freeze. The backend resolves and verifies that exact Binding before reading its decl_hash or constructing a descriptor; it never resolves a current alias. `inputs` holds the intake and [source_text](../types/source-text.md#term-source-text) refs from the supervisor-side `record_input`. The examples abbreviate hashes and are not validation [fixtures](../system/test-surfaces.md#term-fixture). The launcher's order is on [toolchain M01](toolchain.md#m01-launcher). `record_input` writes `inputs` in the supervisor.

**What the script sends.** The prompt is a **call descriptor** (schema `execution-v1.schema.json#call_descriptor`): RFC 8785 canonical JSON of what decides the result.

```json
{"cc":1,"decl_hash":"5d41...","inputs":{"intake":{"id":"art-...","sha256":"..."},"source_text":{"id":"art-source","sha256":"..."}},"step_id":"requirement"}
```

The engine's cache key uses prompt, label, phase, model and schema (call_signature, engine/journal.py:61). The label is step_id. This is only a cache key: the supervisor's dispatch identity and committed Observation/Verification authorize reuse. Every cache hit must pass authorize_advance. Changed inputs/pins start a new run, not an automatic re-execution in the frozen run ([lifecycle](../system/lifecycle.md)).

**The envelope schema** (`execution-v1.schema.json#step_envelope` carries the same shape), passed as `schema` to every `agent()` call, and published as the constant `cc.adapters.swarmflow.ENVELOPE_SCHEMA`:

```json
{"type": "object", "additionalProperties": false,
 "required": ["step_id", "obs_id", "outcome", "reason", "decision", "verdict", "outputs"],
 "properties": {
   "step_id":  {"type": "string"},
   "obs_id":   {"type": "string"},
   "outcome":  {"enum": ["ok", "error", "refused"]},
   "reason":   {"type": ["string", "null"]},
   "decision": {"enum": ["pass", "fail", "blocked"]},
   "verdict":  {"enum": ["PASS", "PASS_WITH_KNOWN_LIMITATIONS", "FAIL", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE"]},
   "outputs":  {"type": "object", "additionalProperties": {
       "type": "object", "required": ["id", "sha256"], "additionalProperties": false,
       "properties": {"id": {"type": "string"}, "sha256": {"type": "string"}}}}}}
```

**What `run()` does:**

1. Parse the descriptor before reserving or invoking a capsule. Malformed (not JSON with exactly the keys `cc`, `decl_hash`, `inputs` and `step_id`) is an entry protocol rejection: retain sanitized descriptor/hash evidence in a supervisor incident, invoke no runner/Gate, mint no unreserved dispatch Observation, and return `AgentResult(skipped=True)` so the generic script halts. A script bug is never journalled as successful work. Well-formed calls reserve identity before executing the pipeline.
2. Run the pipeline as `dispatch`.
3. Call the gate: `gate(obs_ref) -> GateResult(verification_ref, decision, verdict, normalized_verdict, routing_action)` (schemas `execution-v1.schema.json#gate_request` and `execution-v1.schema.json#gate_result`). The order is fixed: the runner commits (the supervisor commits the Observation), then CcBackend calls the Gate host, then the supervisor releases. The Gate host is called by CcBackend on the supervisor side, never by the runner process. The gate writes Verification for governed dispatch/nested Observations, including validly reserved refusals, subject to cancellation and approved isolated ablation authority. A non-ok call follows the policy's source-sensitive fold: demonstrated capsule/conformance/permission/budget faults fail; unavailable runtime/dependency/capture [blocks](../system/modules.md#term-block); other insufficient evidence is inconclusive. A null Binding is diagnosed from the run's frozen policy and reserved call identity; it cannot authorize advancement.
4. Return the result:
   - `AgentResult(skipped=True)` when the call should run again on resume: `outcome: refused` with `PRECONDITION_DEFERRED`, or a `runtime`-owned reason (`RUNTIME_UNAVAILABLE`, `TIMEOUT`, `EXTERNAL_UNAVAILABLE`), or a [gate verdict](gate-host.md#term-gate-verdict) of `ENVIRONMENT_BLOCKED` (the gate call hit the runtime). A skipped result is a non-success with no retry (`engine/primitives.py:757-759`), so `agent()` returns `None` before the journal write (`:616-627`, write at `:631`), and a resume re-runs the step.
   - Otherwise `AgentResult(structured=envelope)`. The engine journals it, so a resume replays it.

If the gate raises or any required record/capture write fails, run returns AgentResult(skipped=True) and the supervisor halts. A response with no committed Verification never advances. On `cc resume`, a completed Observation without a decision is gated again without re-executing work.

**Cancellation.** Native pause/stop cancels the workflow task. The pipeline terminates/reaps child trees and cancels its reserved model-bridge request under the bounded grace policy. It seals retained capture and commits an error Observation under a bounded shield, marked [ext](../schemas/common.md#term-ext).runner.cancelled=true, without claiming success if capture/store fails. It calls no Gate and re-raises. Nested requests are cancelled innermost first; no operation is replayed automatically.

Apart from re-raising a cancellation, `run()` never raises and never lets the engine time it out. `Runtime.retries` is 2 (`engine/runtime.py:62`) and `run_workflow` has no switch for it: `_attempt_calls` (`primitives.py:692`) retries a call when the backend raises or times out (`:726`) or the result fails schema coercion (`:767`). M1's zero retries holds only because `run()` never raises and always returns a valid envelope that carries the typed failure. So the script must never pass `options={"timeout": ...}` for a CC node, and the envelope always passes the engine's schema check. **Required test:** inject a backend exception (and a schema-invalid reply) and prove the capsule and the model run at most once and the run halts. Do not rely on a nonexistent retries argument.

**Halts must not be swallowed.** `CcHalt` derives from `BaseException` and also sets the engine's `abort_event`. The native `parallel()`, `pipeline()` and `map_parallel()` wrap each branch in `except Exception: return None` (`primitives.py:1463` and `:1514` at the pin), so an `Exception`-based halt would become `None` and the script would continue after a failed Gate. `BaseException` passes through those wrappers; `abort_event` stops sibling branches at the next engine abort checkpoint. The engine checks abort before every new agent call and human turn (`primitives.py:585`, `:1153`), so the script opens the human triage session first and sets `abort_event` after the review is stored or at once in headless mode (order to verify by a probe). See [integration](../system/integration.md#swarmflow-run-a-plan-be-the-backend).

**The script.** There is one generic Swarmflow script, which walks the frozen plan and calls `cc_node(args, step_id, **refs)` once per step ([nodes](../system/nodes.md#generic-workflow-adapter)). `cc_node`, `CcHalt`, `CcBackend` and the script live in `cc.adapters.swarmflow` ([integration](../system/integration.md#swarmflow-run-a-plan-be-the-backend)). No step is wired by hand.

Before returning any advancing envelope, cc_node calls supervisor authorize_advance on the exact attempt's Observation and Verification, including journal replays. Otherwise it raises [CcHalt](../system/lifecycle.md#term-cchalt). A skipped result reads that attempt's committed evidence; absent Verification yields ENVIRONMENT_BLOCKED and cannot borrow an older PASS. The launcher invokes the native human-session halt/recovery adapter. ESCALATE_TO_HUMAN is a routing action, not a verdict. The script passes refs only.

**Pause or response loss does not authorize repeated effects.** The engine can drop a completed response while paused (primitives.py:629): an abort leaves the in-flight call unjournaled, and the engine journal is flushed but not fsynced (`journal.py:272`), so a native resume would run that call again. Reservation reuse is therefore mandatory: the supervisor consults the durable dispatch state before invoking work again. Completed work reuses its Observation; incomplete effects require explicit human review. A reviewed retry gets a new attempt; transport duplicates share the original id and result. A crash or kill never resumes by itself: on restart the supervisor writes a `halt_report` with reason `INTERRUPTED` and waits. `cc resume <run_id>`, run by a human, writes the `human_review_record` (action `resume_after_fix`) and starts a new attempt of the interrupted step under unchanged pins ([lifecycle](../system/lifecycle.md#failure-human-review-and-recovery)).

## Permissions and human interaction at M1

Step 6 decides from policy `mappings` and `needs.human_interaction`. **Every M1 call is unattended.** The Codex runtime has no reply path: `handle_swarmflow_reply` is `handle_user_answer`, which always returns `MILESTONE_TEXT_ONLY` (`jiuwenswarm/server/runtime/agent_adapter/interface_codex.py:67-70`). Admission calls are unattended too.

| Declared | Decision |
|---|---|
| `effect_class: pure` or `read_only` | allow |
| `effect_class: idempotent` or `compensable`, and every `effects[].resource_key` starts with `fs:workspace/` | allow |
| `effect_class: idempotent` or `compensable`, any other effect | ASK, which is DENY when unattended: `PERMISSION_DENIED` |
| `effect_class: nonrepeatable_effect` | allow only the pinned-policy bounded empirical operation through the validated process service, with the exact reserved Binding/attempt; otherwise `PERMISSION_DENIED` |
| `effect_class: irreversible` | ASK, so DENY: `PERMISSION_DENIED` |
| `needs.human_interaction: blocking` | `PERMISSION_DENIED`: nothing can answer |
| `needs.human_interaction: optional` | allowed; `cc_sdk` offers no way to reach a person, so the capsule finishes without an answer |

At M1 an `irreversible` capsule never runs. Stage 3.7 declares `nonrepeatable_effect`: its frozen plan, policy, gated bundle and exact durable [dispatch reservation](../system/records.md#term-reservation) authorize the first bounded empirical execution automatically after predecessor release. The process-service pre-check must pass. Duplicate requests attach to the original running/committed result and cannot execute again; interrupted uncertainty halts. An authenticated human review authorizes a new reserved attempt for explicit restart. This class grants no broader filesystem, network or irreversible authority. Generated program confinement remains the separate validated process boundary.

**Runtime coverage is an execution prerequisite.** [Restricted child](../isolation.md#term-restricted-child) mount/network/identity profiles and broker capabilities are defined by environment. If the profile cannot prevent host-file/socket bypass, doctor blocks that backend; cwd alone is insufficient. POC execution uses its own fixed profile. [Deployment](../system/deployment.md) is the home of one Linux image using nested unprivileged Bubblewrap; macOS Docker Desktop executes that same profile. Actual negative [probes](../system/environment.md#term-probe) must pass before enabling it. General [jiuwenbox](../isolation.md#term-jiuwenbox) orchestration remains deferred. No runtime safety result is claimed here.

## Records the runner returns for commit

| When | Record | Fields the runner sets (supervisor commits) |
|---|---|---|
| `record_input` (supervisor side) | Artifact, `origin: human` or `control` | `content_sha256`, `type`, `value` or `content_ref`; `scope.run_id` |
| a nested call's inputs | Artifact, `origin: control` | as above, plus `causation_id` = the caller's `obs_id` |
| step 8 | one Artifact per output, `origin: capsule` | `type` from the port, `produced_by {obs_id, port}`, `issues` from the handler |
| step 9 | one Observation per call, refusals included | `caller`, `started_at`, `binding_ref`, `test_ref` (admission), `decl_hash` (null only for `BINDING_MISSING`), `attempt`, `inputs` (the refs it was given), `outputs`, `predicates`, `outcome`, `reason`, `seen_code_sha256`, `models` (only when reported), `cost.time_s`, `causation_id` (nested calls), `ext.runner` |

`ext.runner` holds what is useful for debugging and for [Data Foundation](../system/storage.md#term-data-foundation), but not part of the record's meaning: `failure_code`, `turns` (each with its own `model_hint`), `stderr`, `reply`, `error_detail`, `engine_call_key`.

[Artifacts](../schemas/artifact.md#term-artifact) are committed before the Observation that names them, in the same batch; an Artifact names its call by `obs_id` only ([Artifact](../schemas/artifact.md)). The runner never writes: it sends `commit_request`, and the supervisor writes every record once through M12, with `producer.component: runner`.

## Hooks for observability

The runner announces each call on the CC event bus: `cc.call.started`, `cc.call.resolved`, `cc.call.refused`, `cc.call.nested`, `cc.model.turn` and `cc.call.finished`. Each event is emitted after the record it describes is committed; schema `execution-v1.schema.json#event_envelope`, relayed to the supervisor bus by the proposed `execution-v1.schema.json#runner_event` frame. Their payloads, the bus API and every subscriber are defined once, on [system observability](../system/observability.md#interface-the-events). Adding a subscriber never changes the runner, which is why this page can stay fixed while observability is designed.

## Three worked calls

**`op.local_search` (tool, pure; [local search](../capabilities/op-local-search.md)).** The frozen dependency closure pins its declaration and code/check hashes. The broker binds intake, query and bounded top_k inputs, validates them, and invokes the restricted tool host. It returns canonical [search_hits](../types/search-hits.md#term-search-hits), stored as an Artifact linked to its Observation. The Gate host persists a mechanical Verification before the parent consumes that output; the parent node's Gate covers it. Input/schema/capture failure returns the documented refusal/error and no successful hit result.

**`research.compile_brief` (skill; [requirement capsule](../capabilities/requirement-capsule.md)).** This is the one requirement call. Inputs are intake, source_text and the accepted `intent_ir` (port wiring `PENDING_SOURCE`, [decisions](../decisions.md#pending-source-do-not-invent)). Requirements are one model pass. The handler builds its prompt from pinned SKILL.md/reference files, these inputs and the canonical [research_brief](../types/research-brief.md#term-research-brief) output contract. M05 uses the fixed configured Codex route, preserving raw prompt/reply capture. Parsing and deterministic output checks precede the independent semantic Gate; a committed Verification and release are required before the planner or any successor runs.

**A skill that pins an operator** (Hypothesis with op.codesearch). The first reply requests a permitted pinned capability. The broker verifies needs.external, reserves the nested call identity and asks the supervisor to commit inputs. Nested execution publishes its Observation/output and mechanical Verification before the exchange is returned to the skill. The second reply supplies the parent outputs. Parent and operator Observations are linked through causation_id and the scoped call capture; the parent Gate also checks the nested evidence.

## Required observed-operation capture

The trusted broker/process collector supplies Observation.effects_observed for every call, including nested and admission calls, as resource_key/op entries backed by committed raw capture. Compare operations against the exact pinned Declaration/Binding and process profile before an ok result. Empty lists denote no observed operations, including refusal before launch; missing mandatory capture is an evidence failure, not proof no effects occurred. An undeclared/denied operation fails with attributable security evidence. An operation whose enforcement or capture cannot be verified remains unsupported. Automated librarian drift analysis and Standing changes are deferred.

## Failure: model, broker and backend

| Situation | Outcome | Recovery |
|---|---|---|
| Model bridge `unavailable`, `denied` or `cancelled` | `error`, `RUNTIME_UNAVAILABLE`; auth loss (`AUTH_RELOGIN_REQUIRED`) halts the run as `ENVIRONMENT_BLOCKED` | login, then a human `cc resume` starts a new attempt of the step; the possibly paid turn is never resubmitted without that command |
| Capsule deadline passes while the bridge request is queued or running | `error`, `BUDGET_EXCEEDED`; the broker cancels the bridge request | explicit human review |
| A nested `ref` that is not pinned | no call, no Observation; the caller ends `CAPSULE_ERROR` | fix the capsule |
| The Gate host raises or a required write fails | `AgentResult(skipped=True)`; the supervisor halts | `cc resume` gates the committed Observation again without re-executing work |
| The runner or the supervisor dies mid-call | no automatic resume; `halt_report` reason `INTERRUPTED` | `cc resume <run_id>` by a human |

**Open items.**

1. **Retries.** No autonomous execution retry at M1. Transport deduplication and human-approved recovery use supervisor identities ([lifecycle](../system/lifecycle.md)); they do not depend on the unchecked generic retry fields.
2. **Structured output.** When the Codex App Server's `outputSchema` is usable (AI4R-001), M05 can take the reply contract as a schema. The parse rules stay as a second line of defence.

## Tests

Rows in [test surfaces](../system/test-surfaces.md#verification-table): [V01](../system/test-surfaces.md#verification-table), [V02](../system/test-surfaces.md#verification-table) (model bridge), [V10](../system/test-surfaces.md#verification-table), [V37](../system/test-surfaces.md#verification-table) (model auth loss halts, no second paid turn), [V41](../system/test-surfaces.md#verification-table) (crash then resume).

| Module | Checked by |
|---|---|
| R1 Swarmflow backend | a descriptor reaches the pipeline as `dispatch`; a malformed descriptor is rejected before reservation with sanitized protocol diagnostics and no fabricated Observation; a cancelled call kills its tool host and still commits an Observation; a runtime failure returns `skipped`; a repeated descriptor replays from the journal; `run` never raises; inject a backend exception and a schema-invalid reply and prove the capsule and the model run at most once; the Gate is called only after `runner_response` complete |
| R5 permission check | every row of the permission table |
| R7 broker | an unpinned ref writes no Observation; a nested deadline never exceeds its caller's; nested Observations carry `causation_id`; a model reply after the capsule deadline is `BUDGET_EXCEEDED` |
| R8 event emission | events fire in order, after their records; a raising subscriber never fails a call |
| R9 generated-code process boundary | see [process boundary](process-boundary.md#interface-provisional-api) |
