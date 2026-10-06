---
type: schema
id: cc.observation.v1
status: proposed
tags: [schema]
---

# Observation: one capsule call · `cc.observation.v1`

One record per capsule call, written by the runner, including every retry, judge call and admission test call. It is a thin index: ids, hashes, outcome and cost. The values are [Artifacts](artifact.md); the call's details are on agent-core's span. Spans are sampled, expire (7 days by default) and can be redacted, so a missing span is normal. A call with no Observation did not go through the runner.

**Rules:** INV-2, INV-5 (no copies of values), INV-8.

## Fields

Extends [common](common.md). Its `scope` is `run_id`, or `candidate_id` for an admission test call. Its `trace` links the span. Its `id` is the `obs_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `caller` | `reg(caller)` | req | checked |  | Who asked for the call: `dispatch` (a workflow call in a run), `gate` (a judge call by the gate), `admission` (a test call) or `nested` (a call a capsule's code makes to a capsule in its `needs.external`, such as an operator). The gate checks every `dispatch` call and writes one [Verification](verification-record.md) for it |
| `started_at` | `time` | req | checked |  | When the call started. The envelope's `at` is when it ended |
| `binding_ref` | `Ref(binding)?` | req | checked |  | The [Binding](binding.md) the call ran under; for a judge call, the Binding whose `verifier` it is. Null for admission test calls and for `BINDING_MISSING` |
| `test_ref` | `Ref(test_case)` | opt | checked |  | For an admission test call: the test case it ran |
| `decl_hash` | `sha256?` | req | checked |  | What the runner loaded and ran. In a run it must equal the Binding's `decl_hash`, its `verifier.decl_hash`, or, for a `nested` call, a `decl_hash` the bound capsule pins in `needs.external`. Null when the call was refused before any code was chosen (`BINDING_MISSING`) |
| `attempt` | `integer` | req | checked |  | 1 for the first try; a retry is a new Observation with this number one higher |
| `inputs` | `map<string, Ref(artifact)>` | req | checked |  | Port name to the Artifact that went in. Example: `{"pdf": {"id": "art-0003", "sha256": "..."}}` |
| `outputs` | `map<string, Ref(artifact)>` | req | checked |  | Port name to the Artifact that came out; empty when the call failed |
| `predicates` | `list<object>` | req | checked |  | The preconditions checked on fresh state just before the call. Each is `{predicate_id, result}`, with `result` `pass`, `fail` or `defer` |
| `outcome` | `enum(ok, error, refused)` | req | checked |  | `refused` when the runner would not start the call; the cases are listed on the [Binding](binding.md) page |
| `reason` | `string?` | req | checked |  | Why, when `outcome` is not `ok`; otherwise null. A `reason_code` registry value. A failure outside the capsule uses a runtime code (`RUNTIME_UNAVAILABLE`, `TIMEOUT`), never a capsule code; an exception the capsule raises is `CAPSULE_ERROR`; a capsule stopped at its own time budget is `BUDGET_EXCEEDED`. Each code's owner is in the policy. *Proposed* (INV-19): for `error`, one of the capsule's `failure_modes[].reason_code`, and `CAPSULE_RAISED_UNDECLARED` for any other exception it raises. Example: `CARRIER_CHANGED` |
| `seen_code_sha256` | `sha256` | opt | checked |  | On `CARRIER_CHANGED`: the hash the loader actually found |
| `model` | `object` | opt | checked |  | For model capsules: the model that served the call, as `{id, version}`. Example: `{"id": "qwen3-32b", "version": "2026-08"}` |
| `cost` | `object` | req | checked |  | What the call spent. The gate checks it against the Binding's `budget` |
| `cost.tokens` | `object` | opt | unchecked | budgets | Model tokens, in RSI's shape: `{input, output, cache_hit}` |
| `cost.time_s` | `number` | req | checked |  | Wall-clock seconds. Example: `0.004` |
| `cost.money` | `number` | opt | unchecked | budgets | In the currency policy `budgets` names |
| `trajectory_ref` | `id` | opt | unchecked | RSI, exempt agents | An agent-core trajectory id: what a general-purpose agent did. The policy requires it for `exempt` capsules |
| `effects_observed` | `list<object>` | opt | unchecked | librarian | What the call was seen to touch, each `{resource_key, op}`, from the permission engine. The librarian compares it with the Declaration's `effects` |

## Elsewhere

No `upstream` field: `inputs` gives Artifacts, and each Artifact's `produced_by` names the call that made it. Workflow engine ids: `ext.<engine>`. When a trajectory is required, and retry bounds: policy `levels`, `gates`. Span attribute names and storage: the runner.

## Reuse

- Run id on spans, `openjiuwen.run.id` (agent-core `extensions/observability/semconv.py:50`, `harness/observability/run_span.py:152`): as is; our `run_id` is passed to `open_agent_run_span`, so span and record share one key.
- The current tool span (`span_context.py:946`): as is; the runner stamps `cc.obs_id`, `cc.decl_hash`, `cc.step_id`, `cc.caller`, `cc.attempt` and `cc.outcome` on it.
- `openjiuwen.step.id` (`semconv.py:53`): not reused; it is the agent's reasoning-loop step.
- `tool_failure_reason` (`tool_outcome.py:33`): as is, to derive `outcome`, so span status and record agree.
- GenAI attributes (`gen_ai_semconv.py:53-90`): as is, the source of `model` and token counts. RSI's token shape (`rsi/schema.py:57`): for `cost.tokens`.
- `Trajectory`, `TrajectoryStore` (`agent_evolving/trajectory/model.py:132`, `store.py:23`): as is, for `trajectory_ref`.
- Write-once KV (`core/foundation/store/base_kv_store.py:42`, `:93`): as is, as the store.
- Symphony `CapabilityCall` (`symphony/models/evaluation.py:90`): not reused; it holds values inline and names the capability, not its hash.
