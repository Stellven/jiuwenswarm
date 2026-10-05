---
type: schema
id: cc.observation.v1
status: proposed
tags: [schema]
prd: [4.1.4, 4.5.3]
level: detail
---

# Observation: one capsule call · `cc.observation.v1`

PRD: 4.1.4, 4.5.3

One record per reserved [capsule](../capsule/capsule.md#term-capability-capsule) call, logically produced by the runner, which returns it, and committed by the supervisor on the runner's behalf as the only store writer, including human-approved new [attempts](../system/lifecycle.md#term-attempt), judge calls and admission tests. Values are [Artifacts](artifact.md); mandatory raw execution details are retained in the sealed capture manifest referenced by [ext](common.md#term-ext).runner.execution_evidence. Native spans are optional debugging views and cannot replace that capture. No automatic execution retry occurs at M1. A call reserved before interruption may have no terminal Observation; that absence is not proof that no effects occurred.

**Rules:** INV-2, INV-5 (no copies of values), INV-8.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-observation"></a>**Observation** (also: Observations) | One record per reserved capsule call: who called it, the pinned version, inputs by reference, precondition results, outcome and reason, time, cost and model. The runner produces it and the supervisor commits it; a call with no Observation went around the runner. |

## Fields

Extends [common](common.md). Its `scope` is `run_id`, or `candidate_id` for an admission test call. Its `trace` links the span. Its `id` is the `obs_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `caller` | `reg(caller)` | req | checked |  | Who asked for the call: `dispatch` (a workflow call in a run), `gate` (a judge call by the gate), `admission` (a test call) or `nested` (a call a capsule's code makes to a capsule in its `needs.external`, such as an [operator](../capabilities/README.md#term-operator)). The gate [checks](../capsule/fields.md#term-check) every `dispatch` call and writes one [Verification](verification-record.md) for it. A `nested` call gets a mechanical [Verification](verification-record.md#term-verification) persisted before it returns and is covered by its parent node's [Gate](../verification.md#term-gate); the nested verifier review inside `research.compile_intent` is validated by the calling capsule and is not itself Gated |
| `started_at` | `time` | req | checked |  | When the call started. The envelope's `at` is when it ended |
| `binding_ref` | `Ref(binding)?` | req | checked |  | The [Binding](binding.md) the call ran under; for a judge call, the [Binding](binding.md#term-binding) whose `verifier` it is. Null for admission test calls and for `BINDING_MISSING` |
| `test_ref` | `Ref(test_case)` | opt | checked |  | For an admission test call: the [test case](checks.md#term-test-case) it ran |
| `decl_hash` | `sha256?` | req | checked |  | What the runner loaded and ran. In a run it must equal the Binding's `decl_hash`, its `verifier.decl_hash`, or, for a `nested` call, a `decl_hash` the bound capsule pins in `needs.external`. Null when the call was refused before any code was chosen (`BINDING_MISSING`) |
| `attempt` | `integer` | req | checked |  | 1 for the first try; a retry is a new Observation with this number one higher |
| `inputs` | `map<string, Ref(artifact)>` | req | checked |  | Port name to the Artifact that went in. Example: `{"pdf": {"id": "art-0003", "sha256": "..."}}` |
| `outputs` | `map<string, Ref(artifact)>` | req | checked |  | Port name to the Artifact that came out; empty when the call failed |
| `predicates` | `list<object>` | req | checked |  | The preconditions checked on fresh state just before the call. Each is `{predicate_id, result}`, with `result` `pass`, `fail` or `defer` |
| `outcome` | `enum(ok, error, refused)` | req | checked |  | `refused` when the runner would not start the call; the cases are listed on the [Binding](binding.md) page |
| `reason` | `string?` | req | checked |  | Why, when `outcome` is not `ok`; otherwise null. A `reason_code` registry value. A failure outside the capsule uses a runtime code (`RUNTIME_UNAVAILABLE`, `TIMEOUT`), never a capsule code; an exception the capsule raises is `CAPSULE_ERROR`; a capsule stopped at its own time budget is `BUDGET_EXCEEDED`. Each code's owner is in the policy. Optional failure-mode diagnostics are retained in ext; ordinary exceptions remain CAPSULE_ERROR. Example: `CARRIER_CHANGED` |
| `seen_code_sha256` | `sha256` | opt | checked |  | On `CARRIER_CHANGED`: the hash the loader actually found |
| `models` | `list<object>` | opt | checked |  | For calls that used models: every distinct model that served a [turn](../system/model-bridge.md#term-model-turn), in order of first use, as `{id, version}`. A call may use many, for example when it routes per turn; which turn used which is in `ext.runner.turns`. Only models the runtime reported. Example: `[{"id": "qwen3-32b", "version": "2026-08"}, {"id": "deepseek-r1", "version": null}]` |
| `cost` | `object` | req | checked |  | What the call spent. The gate checks it against the Binding's `budget` |
| `cost.tokens` | `object` | opt | unchecked | budgets | Model tokens, in [RSI](../rsi.md#term-rsi)'s shape: `{input, output, cache_hit}` |
| `cost.time_s` | `number` | req | checked |  | Wall-clock seconds. Example: `0.004` |
| `cost.money` | `number` | opt | unchecked | budgets | In the currency policy `budgets` names |
| `trajectory_ref` | `id` | opt | unchecked | RSI, exempt agents | An agent-core trajectory id: what a general-purpose agent did. The policy requires it for `exempt` capsules |
| `effects_observed` | `list<object>` | req | checked |  | Trusted broker/process capture of observed operations, each `{resource_key, op}`, compared with the pinned [Declaration](../capsule/fields.md#term-declaration) and authorized process profile before an ok Observation. Empty is valid only for no observed operations or pre-launch refusal; absent/incomplete required capture cannot report ok. Denied operations retain attributable capture/Reason evidence. Automated librarian drift/Standing changes remain deferred |

## Elsewhere

No `upstream` field: `inputs` gives [Artifacts](artifact.md#term-artifact), and each Artifact's `produced_by` names the call that made it. Workflow engine ids: `ext.<engine>`. When a trajectory is required, and retry bounds: policy `levels`, `gates`. Span attribute names and storage: the runner.

## Reuse

- Run id on spans, `openjiuwen.run.id` (agent-core `extensions/observability/semconv.py:50`, `harness/observability/run_span.py:152`): as is; our `run_id` is passed to `open_agent_run_span`, so span and record share one key.
- The current tool span (`span_context.py:946`): as is; the runner stamps `cc.obs_id`, `cc.decl_hash`, `cc.step_id`, `cc.caller`, `cc.attempt` and `cc.outcome` on it.
- `openjiuwen.step.id` (`semconv.py:53`): not reused; it is the agent's reasoning-loop step.
- `tool_failure_reason` (`tool_outcome.py:33`): as is, to derive `outcome`, so span status and record agree.
- GenAI attributes (`gen_ai_semconv.py:53-90`): as is, the source of `models` and token counts. RSI's token shape (`rsi/schema.py:57`): for `cost.tokens`.
- `Trajectory`, `TrajectoryStore` (`agent_evolving/trajectory/model.py:132`, `store.py:23`): as is, for `trajectory_ref`.
- Write-once KV (core/foundation/store/base_kv_store.py:42, :93): a rebuildable index adapter. Durable file publication in [storage](../system/storage.md) is authoritative; exclusive_set alone is not a commit/fsync contract.
- Symphony `CapabilityCall` (`symphony/models/evaluation.py:90`): not reused; it holds values inline and names the capability, not its hash.
