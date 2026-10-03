---
type: review
status: draft
tags: [review, draft, data-foundation, observability, m1]
---

# Data Foundation and the CC run record differences

On my side of the design, the capsule runner now writes two things for every capsule call: an **Observation** (a small record: which capsule version, inputs, output, outcome, cost) and a **capture** (the raw prompts, replies and process output, saved by hash).

Both carry one id, `obs_id`. I read your design as sitting on top of those. Four places where my reading and your doc may not match.

## Four places we may differ

**1. When capture fails.**
- *My assumption:* the capture for a call is required. If it is missing, the run cannot complete, because our gate has to check the evidence before it passes a step.
- *Your doc:* hooks append to files and a hook failure is logged and ignored, so a run is never blocked.
- *Question:* what is the right behavior when capture fails? If the runner saves model turns, tool frames and process output itself, your hooks could keep only the run-level items (host facts, configuration hash, workspace copies, journal). Does that cover what you need?

**2. The id.**
- *My assumption:* one id, `obs_id`, ties together the record, the capture, events, traces and the router's decision id.
- *Your doc:* records are keyed by the Swarmflow `agent_id`, or by an execution id from the router.
- *Question:* we can store `agent_id` on the Observation so you can still join to the Swarmflow run tree. Is that enough, or do you need `agent_id` as the primary key?

**3. The capsule version hash.**
- *My assumption:* a capsule version is named by two hashes we already compute at admission, one over the Declaration and one over the code.
- *Your doc:* one hash over every file that makes up the capsule, by path and SHA-256.
- *Question:* would you rather we extend ours to cover your file list, or keep yours as a separate value? I lean toward one definition so the two cannot drift. Is anything in your list missing from ours?

**4. Who wraps the capsule call.**
- *My assumption:* the capsule runner is the only way a capsule is called, so it can save the call details itself.
- *Your doc:* a wrapper around each Swarmflow `agent()` call saves them.
- *Question:* if the runner already records every call, what should your wrapper still do? Is the label rule (`capsule@hash8`, for the engine's cache) the main remaining need?

## Questions on ownership and intent

1. How much do you want to design Data Foundation yourself? I can fix only the seam with the runner and leave record fields, bundle layout and scorecard to you. Or I can propose the field mapping and you build to it. Which do you prefer?
2. Your doc says field names and formats are open, and lists three things you would keep: one record per capsule execution tied to the exact capsule version, results per individual check, and raw material kept so records can be rebuilt. Is that the full list of what must stay?
3. Why capture raw material with hooks rather than inside the runner? My guess is you wanted no risk to the run and no dependence on trace delivery. Is that right?
4. Who reads the scorecard first, and what do they decide with it? That tells me which fields must exist in the very first run.

## Appendix

**What I think we already agree on.**
Raw material is kept and records are rebuilt from it.
One record per execution, including runs that never reach the gate.
Scorecard and export only read.
Raw benchmark output is evidence, not Task Memory.
Observe only.

**A proposed split, open for you to change.**

| Item | Owner |
|---|---|
| Observation, capture, `obs_id`, runner events, capsule hash | CC (Muk) |
| Record fields, bundle layout, declared-against-observed | Suraj |
| Scorecard, Sample Run Export, Library Snapshot | Suraj |
| Bundle retention and access | open, needs a product decision |

**What I would change on my side.** Add `agent_id` and the other fields the join needs to the Observation ([list](../system/observability.md#gaps-the-canary-found-and-the-resolution-proposed-for-each)). Your `records/` folder would be an export of the CC store.

**Smaller mappings.** Your four failure classes seem to map to our failure reasons and the scientific verdict. Your native trace settings may not be needed, because the runner writes its own spans.
## Appendix B: CC context for code agent

> **Copied on 2026-10-02 from the CC owner pages so a code agent can read it without the vault.** Where this text and the linked owner page differ, the owner page wins. The schemas are `proposed`, not `v1`, and field names can still move. `INV-n` and `M1 checked/unchecked` labels are CC-internal; read them as notes. Types: `id`, `sha256`, `time` (RFC 3339 UTC), `Ref(kind)` is `{id, sha256}` pointing at another record, `reg(x)` is a value from a closed registry, `?` marks nullable.

**How to read the model.** Every CC record is written once, by one tool, and carries the common envelope. An **Observation** is the record of one capsule call (its `id` is the `obs_id`). It points at **Artifacts** (the values that went in and came out) and, after the gate, a **Verification** points at the Observation. Raw material (prompts, replies, process output) is not in the Observation. It is in the **capture**, a manifest of files by hash, which the Observation references.

### B.1 Common envelope (every record)

**Envelope**

| Field                | Type                        | Req | M1        | Unlocks        | Description                                                                                                            |
| -------------------- | --------------------------- | --- | --------- | -------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `schema_version`     | `string`                    | req | checked   |                | The schema and major version, `cc.<name>.v<major>`. Example: `cc.observation.v1`                                       |
| `id`                 | `id`                        | req | checked   | [[brief-gate]] | The record's id, unique within its kind. A page may call it `verdict_id`, `obs_id` and so on. Example: `obs-0001`      |
| `scope`              | `object`                    | req | checked   |                | What the record belongs to. Exactly one of the three fields below is set                                               |
| `scope.run_id`       | `id`                        | opt | checked   |                | A run: one pass of a workflow from request to answer. Example: `run-0001`                                              |
| `scope.candidate_id` | `id`                        | opt | checked   |                | An admission: the Verdict and admission's test calls. Example: `cand-0001`                                             |
| `scope.library`      | `boolean`                   | opt | checked   |                | `true` for records about the library, in no run: Standing, test cases and suites, the port type vocabulary, the policy |
| `at`                 | `time`                      | req | checked   |                | When it was written, RFC 3339 UTC (as jiuwenswarm's E2A `timestamp`)                                                   |
| `producer`           | `object`                    | req | checked   |                | The record kind's one writer (INV-3)                                                                                   |
| `producer.component` | `string`                    | req | checked   |                | The tool that wrote it. Example: `runner`                                                                              |
| `producer.version`   | `string`                    | req | checked   |                | Its code version. Example: `cc@1a2b3c4`                                                                                |
| `producer.model`     | `string`                    | opt | checked   |                | The model, when a model produced the content. Example: `qwen3-32b`                                                     |
| `causation_id`       | `id`                        | opt | checked   |                | The record that caused this one, when no field of the record already names it                                          |
| `idempotency_key`    | `string`                    | opt | unchecked | retries        | A second write with the same key is dropped, so retries are safe. Example: `run-0001/extract/1`                        |
| `trace`              | `object`                    | opt | unchecked | tracing        | The agent-core span, when one exists. Spans are sampled and expire; records do not                                     |
| `trace.trace_id`     | `string`                    | req | unchecked | tracing        | The OpenTelemetry trace id                                                                                             |
| `trace.span_id`      | `string`                    | req | unchecked | tracing        | The OpenTelemetry span id                                                                                              |
| `visibility`         | `enum(all, builder_hidden)` | opt | unchecked | certification  | Default `all`. `builder_hidden` hides it from builders (people and RSI) when it would leak a sealed suite              |
| `ext`                | `map<string, json>`         | opt | checked   |                | Extensions keyed by tool, e.g. `{"openjiuwen": {...}}`; other readers ignore them (INV-14, INV-18)                     |

**Shared shapes**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `Ref.id` | `id` | req | checked |  | The id of the record pointed at, written `Ref(kind)` in type columns |
| `Ref.sha256` | `sha256` | req | checked |  | That record's hash (INV-15), so a wrong reference fails loudly |
| `EvidenceRef.evidence_type` | `string` | req | checked |  | The kind of evidence. Example: `observation` |
| `EvidenceRef.reference` | `string` | req | checked |  | A record id or a URI. Example: `obs-0001` |
| `EvidenceRef.description` | `text` | opt | checked |  | One line on what it shows |
| `EvidenceRef.metadata` | `map<string, json>` | opt | checked |  | Anything else the producer keeps |
| `Reason.code` | `reg(reason_code)` | req | checked |  | Why something failed or moved. Example: `CARRIER_CHANGED` |
| `Reason.message` | `text` | req | checked |  | The same in plain words |
| `Reason.evidence` | `list<EvidenceRef>` | opt | checked |  | What shows it, e.g. the failing Observation |

### B.2 Observation: one per capsule call

Extends common. Its `scope` is `run_id`, or `candidate_id` for an admission test call. Its `trace` links the span. Its `id` is the `obs_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `caller` | `reg(caller)` | req | checked |  | Who asked for the call: `dispatch` (a workflow call in a run), `gate` (a judge call by the gate), `admission` (a test call) or `nested` (a call a capsule's code makes to a capsule in its `needs.external`, such as an operator). The gate checks every `dispatch` call and writes one Verification for it |
| `started_at` | `time` | req | checked |  | When the call started. The envelope's `at` is when it ended |
| `binding_ref` | `Ref(binding)?` | req | checked |  | The Binding the call ran under; for a judge call, the Binding whose `verifier` it is. Null for admission test calls and for `BINDING_MISSING` |
| `test_ref` | `Ref(test_case)` | opt | checked |  | For an admission test call: the test case it ran |
| `decl_hash` | `sha256?` | req | checked |  | What the runner loaded and ran. In a run it must equal the Binding's `decl_hash`, its `verifier.decl_hash`, or, for a `nested` call, a `decl_hash` the bound capsule pins in `needs.external`. Null when the call was refused before any code was chosen (`BINDING_MISSING`) |
| `attempt` | `integer` | req | checked |  | 1 for the first try; a retry is a new Observation with this number one higher |
| `inputs` | `map<string, Ref(artifact)>` | req | checked |  | Port name to the Artifact that went in. Example: `{"pdf": {"id": "art-0003", "sha256": "..."}}` |
| `outputs` | `map<string, Ref(artifact)>` | req | checked |  | Port name to the Artifact that came out; empty when the call failed |
| `predicates` | `list<object>` | req | checked |  | The preconditions checked on fresh state just before the call. Each is `{predicate_id, result}`, with `result` `pass`, `fail` or `defer` |
| `outcome` | `enum(ok, error, refused)` | req | checked |  | `refused` when the runner would not start the call; the cases are listed on the Binding page |
| `reason` | `string?` | req | checked |  | Why, when `outcome` is not `ok`; otherwise null. A `reason_code` registry value. A failure outside the capsule uses a runtime code (`RUNTIME_UNAVAILABLE`, `TIMEOUT`), never a capsule code; an exception the capsule raises is `CAPSULE_ERROR`; a capsule stopped at its own time budget is `BUDGET_EXCEEDED`. Each code's owner is in the policy. *Proposed* (INV-19): for `error`, one of the capsule's `failure_modes[].reason_code`, and `CAPSULE_RAISED_UNDECLARED` for any other exception it raises. Example: `CARRIER_CHANGED` |
| `seen_code_sha256` | `sha256` | opt | checked |  | On `CARRIER_CHANGED`: the hash the loader actually found |
| `models` | `list<object>` | opt | checked |  | For calls that used models: every distinct model that served a turn, in order of first use, as `{id, version}`. A call may use many, for example when it routes per turn; which turn used which is in `ext.runner.turns`. Only models the runtime reported. Example: `[{"id": "qwen3-32b", "version": "2026-08"}, {"id": "deepseek-r1", "version": null}]` |
| `cost` | `object` | req | checked |  | What the call spent. The gate checks it against the Binding's `budget` |
| `cost.tokens` | `object` | opt | unchecked | budgets | Model tokens, in RSI's shape: `{input, output, cache_hit}` |
| `cost.time_s` | `number` | req | checked |  | Wall-clock seconds. Example: `0.004` |
| `cost.money` | `number` | opt | unchecked | budgets | In the currency policy `budgets` names |
| `trajectory_ref` | `id` | opt | unchecked | RSI, exempt agents | An agent-core trajectory id: what a general-purpose agent did. The policy requires it for `exempt` capsules |
| `effects_observed` | `list<object>` | opt | unchecked | librarian | What the call was seen to touch, each `{resource_key, op}`, from the permission engine. The librarian compares it with the Declaration's `effects` |

## Elsewhere

No `upstream` field: `inputs` gives Artifacts, and each Artifact's `produced_by` names the call that made it. Workflow engine ids: `ext.<engine>`. When a trajectory is required, and retry bounds: policy `levels`, `gates`. Span attribute names and storage: the runner.

### B.3 Artifact: one per value

Extends common. Its `scope` is `run_id` for what a run makes, `candidate_id` for what an admission makes (test inputs, test-call outputs), or `library` for test inputs and fixtures kept with a suite. Its `id` is the `artifact_id`. The runner writes every Artifact in a run, including values that people or control code hand to it; admission writes those of an admission and of the library.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `content_sha256` | `sha256` | req | checked |  | The key of the content: the hash of `value` in canonical form, or of the bytes behind `content_ref`. The same content is stored once |
| `type` | `reg(port_type)` | req | checked |  | What the value is. It is validated against the type's `value_schema` before it is stored. Example: `text` |
| `value` | `json` | opt | checked |  | The value, when it travels inline. Exactly one of `value` and `content_ref` is set. Example: `"Page 1 ..."` |
| `content_ref` | `object` | opt | checked |  | Where the bytes are, for values stored by reference (files, reports) |
| `content_ref.uri` | `uri` | req | checked |  | Example: `kv://cc/content/5d41...` |
| `content_ref.name` | `string` | opt | checked |  | The file name, if any. Example: `sample.pdf` |
| `content_ref.mime_type` | `string` | opt | checked |  | Example: `application/pdf` |
| `content_ref.size` | `integer` | opt | checked |  | The size in bytes. Example: `1824` |
| `origin` | `enum(capsule, human, control)` | req | checked |  | Who made it: a capsule call, a person (a request, an uploaded document), or control code (e.g. a workflow saving the request text) |
| `issues` | `list<Reason>` | opt | checked |  | The standard place for caveats about the value: vague, incomplete or contradictory input (`INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE`, `INPUT_CONTRADICTORY`), and anything else a reader should know. Example: `[{"code": "INPUT_INCOMPLETE", "message": "pages 4-6 unreadable"}]` |
| `produced_by` | `object` | opt | checked |  | Set when `origin` is `capsule`: `{obs_id, port}`, the call and output port that produced it. An id, not a `Ref`: the Observation is written after its outputs and pins their hashes, so the Artifact cannot pin the Observation's |

**Lineage.** `produced_by` names the call; that call's Observation names its input Artifacts; each of those names its own call. Following the chain gives the calls behind any value, so no `derived_from` field is stored (INV-5). What a call read outside its ports is not in the chain.

## Elsewhere

How `content_sha256` is computed: INV-15, policy `hashing`. Whether a value travels inline, and which store holds content: the runner's choice. A new kind of value is a new port type, never a new Artifact field.

### B.4 Verification: the gate decision on one step

Extends common, with `scope.run_id`. Its `id` is the `verification_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `invocation_ref` | `Ref(observation)` | req | checked |  | The Observation of the call. Its `binding_ref` gives the checks, the budget, the judge and the policy; its `outputs` are the Artifacts checked; its `outcome` and `cost` feed the gate's own checks |
| `results` | `list<object>` | req | checked |  | One entry per check run: the deterministic and reference entries in the Binding's order, then the gate's fixed checks, then the judged entries in the Binding's order (gate host). Judged checks the fold did not reach have no entry |
| `results[].check_id` | `id` | req | checked |  | Which check. Example: `text_not_empty` |
| `results[].source` | `reg(check_source)` | req | checked |  | `capsule`, `type` or `step` as the Binding says, or `gate` for the gate's fixed checks |
| `results[].result` | `enum(pass, fail, unknown)` | req | checked |  | `unknown` when it could not be evaluated; never counted as a pass (INV-8) |
| `results[].runner_sha256` | `sha256` | req | checked |  | Which runner code produced the result |
| `results[].evidence` | `list<EvidenceRef>` | opt | checked |  | What the check saw; for a judged check, the judge call's Observation |
| `results[].judge` | `object` | opt | checked |  | For judged checks: `{judge_decl_hash, model}`, where `judge_decl_hash` is the Binding's `verifier.decl_hash` |
| `decision` | `enum(pass, fail, blocked)` | req | checked |  | The fold of `results`, by policy `gates` |
| `gate_result` | `object` | req | checked |  | The durable PRD 4.2.8 decision snapshot, computed once from this fold and frozen evidence; this record is its only authority |
| `gate_result.run_id` | `id` | req | checked |  | Equals scope.run_id; external Gate JSON requires this alias |
| `gate_result.stage_id` | `id` | req | checked |  | Equals the invocation Binding's step_id |
| `gate_result.gate_verdict` | `enum(PASS, PASS_WITH_KNOWN_LIMITATIONS, FAIL, ENVIRONMENT_BLOCKED, INCONCLUSIVE)` | req | checked |  | Detailed runtime Gate verdict; scientific classification is separate |
| `gate_result.normalized_verdict` | `enum(PASS, FAIL, BLOCKED, INCONCLUSIVE)` | req | checked |  | PASS_WITH_KNOWN_LIMITATIONS maps to PASS; ENVIRONMENT_BLOCKED maps to BLOCKED; other verdicts retain their spelling |
| `gate_result.routing_action` | `enum(ADVANCE, HALT, ESCALATE_TO_HUMAN)` | req | checked |  | Only PASS and PASS_WITH_KNOWN_LIMITATIONS advance. M1's other outcomes require attributable human triage |
| `gate_result.tier_1` | `object` | req | checked |  | Mechanical tier summary |
| `gate_result.tier_1.status` | `enum(PASS, FAIL, BLOCKED)` | req | checked |  | Result of the fixed Tier 1 fold |
| `gate_result.tier_1.checks` | `list<id>` | req | checked |  | Check ids indexing this record's results; check outputs are not copied |
| `gate_result.tier_2` | `object` | req | checked |  | Independent semantic tier summary |
| `gate_result.tier_2.status` | `enum(PASS, FAIL, INCONCLUSIVE, NOT_RUN)` | req | checked |  | NOT_RUN when Tier 1 blocks or an approved mechanical-only gate applies |
| `gate_result.tier_2.reasons` | `list<Reason>` | req | checked |  | Attributable semantic or reviewer-runtime reasons |
| `gate_result.tier_2.evidence_refs` | `list<EvidenceRef>` | req | checked |  | Judge capture and assessment refs; no hidden fixture contents |
| `gate_result.failed_checks` | `list<id>` | req | checked |  | Failing check ids from results |
| `gate_result.warnings` | `list<text>` | req | checked |  | Non-blocking warnings at decision time |
| `gate_result.known_limitations` | `list<text>` | req | checked |  | Recorded output issues propagated downstream |
| `gate_result.evidence_refs` | `list<EvidenceRef>` | req | checked |  | Complete stage capture manifest and supporting committed records |
| `gate_result.timestamp` | `time` | req | checked |  | Equals the Verification envelope at; PRD projection requires the alias |
| `labels` | `list<reg(label)>` | opt | checked |  | Why a pass is weaker than it looks, recorded when decided, because a judge's calibration changes later. Example: `["judge_unmeasured"]` |

## Elsewhere

Issue 46 is implemented by extending this one existing record, not adding a competing decision writer. `gate_result` is a required product snapshot under INV-5; aliases and normalized/routing values must equal their canonical source at commit. Gate calls use deterministic record identity from invocation obs_id; exact repeats return the stored result and different bytes conflict. The supervisor verifies this committed record before release (lifecycle).

The fold, blame and label rules: policy `gates`. Blame is not stored: it follows from `results[].source` and `result`, and a fit failure is recorded as a Finding. Admission's own test runs are recorded in the Verdict, not here.

### B.5 Capture: the sealed raw evidence for one call

The complete Stage Evidence Bundle is an internal immutable manifest, not the bounded model-facing `evidence_bundle`. `seal_execution(obs_id, capture) -> EvidenceManifestRef` and `get_execution(ref) -> ExecutionEvidence` are the collector's public APIs. `EvidenceManifestRef` contains `obs_id`, `manifest_sha256` and a workspace-relative manifest path. `ExecutionEvidence` contains record refs, captured files `{role, relative_path, content_sha256, size_bytes}`, start/end host facts, declared-versus-observed operations, and capture completeness/status. Allowed roles are input, output, stdout, stderr, model_prompt, model_reply, tool_call, security_check and environment. All paths resolve under the bundle root.

### B.6 Runner and model bridge messages

`RunnerRequest` is `{request_id: id, protocol_version: 1, operation: call|cancel|status, dispatch_id, obs_id, attempt, reservation_ref: SystemRef, call_descriptor}`; only `call` includes the descriptor, whose schema is owned by the runner. `RunnerResponse` is `{request_id, state: running|complete|cancelled|denied|unavailable, observation_ref: Ref(Observation)?, reason: Reason?}`. A complete response requires a durable Observation. Frames use bounded UTF-8 JSON with a 4-byte big-endian length prefix and reject frames above configured `ipc.max_frame_bytes`. The supervisor establishes the authenticated local channel, authorizes a run at connection setup, and rejects another run's descriptor. Cancellation addresses the existing request and kills/reaps its entire process tree; it cannot start work.

`ModelBridgeRequest` is `{request_id, run_id, obs_id, operation: turn|cancel|status, session_id, model_id, deadline_at, text_content_sha256?}`. A turn includes an authorized prompt-content ref; cancel/status address an existing request. `ModelBridgeResult` is `{request_id, state: complete|cancelled|unavailable|timed_out|denied, reply_content_sha256?, reason?}`. It uses lifecycle's bounded framing. Duplicate ids with identical content return the original result/status; different content gives `REQUEST_CONFLICT`. No timeout automatically resubmits a paid/model turn. Credentials and app-server launch parameters never cross the response. Model request/reply bytes are captured before a successful response.

The runner builds this context for every model turn. It stays on the trusted side of the model bridge and is not sent to the model endpoint:

```python
@dataclass(frozen=True)
class ModelCallContext:       # which capsule call a model turn belongs to; for M05's records and an endpoint that routes itself
    obs_id: str
    turn: int                 # 1, 2, ... within that call
    capsule_name: str
    decl_hash: str
    step_id: str | None
    role: str | None          # the Binding's role (unchecked at M1)

@dataclass
class ModelReply:
    text: str
    model_id: str | None          # None when the runtime does not report it
    elapsed_s: float
    tokens: dict | None           # {input, output, cache_hit}, when reported
    route_record_id: str | None   # set only by an endpoint that routes itself (a gateway); a capsule's own routing comes through cc.model's route_id
```

**Every turn is recorded.** For each model turn the runner stores the prompt as sent and the reply text as content (`cc/content/<sha256>`), and appends one entry to the Observation's `ext.runner.turns`: `{turn, session_id, prompt_sha256, reply_sha256, elapsed_s, model_hint, model_id, tokens, route_record_id}`. `model_hint` is the model this turn asked for; `route_record_id` is the `route_id` the capsule passed to `cc.model`, else `ModelReply.route_record_id`. So the exact exchange can be rebuilt from records (seams). When any turn reports `tokens`, the Observation's `cost.tokens` is their sum.

### B.7 Events (live feed, derived from the records)

| Event | Emitted by | When | Also carries |
|---|---|---|---|
| `cc.run.started` | launcher | after the `run_plan` and `intake` are recorded | `run_plan` ref |
| `cc.run.frozen` | freeze | after all Bindings are written | `{step_id: binding ref}` |
| `cc.call.started` | runner | pipeline step 0 | `obs_id`, `caller`, `step_id` |
| `cc.call.resolved` | runner | after code is verified | `obs_id`, `decl_hash`, `code_sha256` |
| `cc.call.refused` | runner | a refusal in steps 1 to 6 | `obs_id`, reason |
| `cc.call.nested` | runner (broker) | a nested call starts | parent and child `obs_id` |
| `cc.model.turn` | runner (broker) | each finished model turn (announce only) | `obs_id`, turn, elapsed, `model_hint`, `model_id`, `route_record_id` |
| `cc.call.finished` | runner | after the Observation is written | Observation ref, outcome, reason |
| `cc.gate.decided` | gate host | after the Verification is written | `step_id`, `obs_id`, Verification ref, decision, verdict |
| `cc.run.halted` | halt host | a halting verdict ended the run | `step_id`, verdict, Verification ref |
| `cc.run.finished` | launcher | the script returned | every step's envelope |


### B.8 Proposed changes to these schemas (not yet in them)

These are what the join and the Data Foundation record need. They are proposals from the [observability](../system/observability.md#one-join-key-one-answer-per-question) page, not current fields.

| Change | Why |
|---|---|
| add `step_id`, `capsule_name`, `role` to the Observation | today they are reachable only through `binding_ref`, which is the caller's Binding for a nested call and null for an admission call |
| add `request_id` to each turn entry, and move `turns` out of `ext.runner` into a checked Observation field | the model bridge `request_id` must join to the Observation |
| split `route_record_id` into `route_id` and `gateway_route_id` | one field currently holds either |
| add `agent_id` (Swarmflow) to the Observation | so Data Foundation can join to the Swarmflow run tree |
| add `obs_id` to runner-to-tool-host and runner-to-confined-process frames, and a `RunnerEvent` frame | events and evidence from other processes must name their call |
