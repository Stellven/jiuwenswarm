---
type: schema
id: cc.binding.v1
status: proposed
tags: [schema]
---

# Binding · `cc.binding.v1`

The pin for one call site of a run: exactly one capsule version, by hash, with the Verdict that admitted it, the checks the gate runs on its output, its budget, and the judge the gate may call. It is written once, by freeze (M03), before the call site first runs. Every capsule call made through the runner is pinned: the runner refuses a call in a run that has no Binding, and refuses to load code that does not match it. A `nested` call (an operator or other capsule the bound capsule calls) runs under the bound capsule's Binding, pinned by the `decl_hash` its Declaration names in `needs.external`, which admission already checked. The writer refuses a Binding when the capsule's code, or any code it pins in `needs.external`, no longer hashes to what was admitted (`CARRIER_CHANGED`): changed code is never bound. It refuses a wiring whose output type differs from the input it feeds (`PORT_TYPE_MISMATCH`). Third-party packages are pinned only when the Declaration's `needs.dependencies.lockfile` is set.

**Rules:** INV-2, INV-5 (its `checks` list is the one allowed assembled copy), INV-9, INV-17.

## Fields

Extends [common](common.md), with `scope.run_id` set to the run's id, a plain string. Its `id` is the `binding_id`. `binding_sha256` is its hash (INV-15); Observations cite it through `Ref(binding)`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `step_id` | `string` | req | checked |  | The call site in the run, unique within the run. A plain string the workflow chooses. Example: `extract` |
| `decl_hash` | `sha256` | req | checked |  | The capsule version bound here |
| `code_sha256` | `sha256` | req | checked |  | What the loader checks before each call, as the [Declaration](../capsule/fields.md) page defines it. The loader fetches each file by its own hash, then checks this value; a mismatch refuses the call with `CARRIER_CHANGED` |
| `verdict_ref` | `Ref(verdict)` | req | checked |  | The Verdict that admitted `decl_hash`. The writer refuses a Verdict whose `outcome` is not `admit`, and one whose `policy_ref.epoch` is neither this Binding's epoch nor listed in that epoch's `levels.accepts` |
| `policy_ref` | `object` | req | checked |  | The policy the runner and the gate follow for this call site: `{epoch, sha256}`. Every Binding of a run pins the same one (INV-17) |
| `policy_ref.epoch` | `string` | req | checked |  | The epoch name. Example: `e1` |
| `policy_ref.sha256` | `sha256` | req | checked |  | The policy document's hash |
| `vocabulary_ref` | `object` | req | checked |  | The [port type vocabulary](port-types.md) whose schemas and checks apply. The writer refuses one in which a port type of the capsule has a different `types[].version` than in the Verdict's `vocabulary_ref`. Every Binding of a run pins the same vocabulary, as it pins the same policy |
| `vocabulary_ref.version` | `integer` | req | checked |  | The vocabulary's `vocabulary_version`. Example: `1` |
| `vocabulary_ref.sha256` | `sha256` | req | checked |  | The vocabulary document's hash |
| `checks` | `list<object>` | req | checked |  | Every check the gate runs on this call's output, assembled once from every check whose `applies_at` is `node` or `both`. Each is `{check_id, source}`, `source` being `capsule` (the Declaration's), `type` (the output type's, from the vocabulary) or `step` (from `step_checks`). At least one, since every type has a `node` check (INV-9) |
| `step_checks` | `list<Check>` | opt | checked |  | The full [Check](checks.md) for each `checks` entry with `source: step`: a check the workflow adds for this call site. Required when there is one |
| `budget` | `object` | req | checked |  | The limit per call, from policy `budgets`: `{tokens, time_s, money}`, each optional; the Gate fails a finished call over it |
| `retry_profile_ref` | `object` | req | checked |  | Pinned ProfileRef(kind=retry); canonical services-v1 retry_profile requires zero autonomous execution retries at M1. Freeze validates profile id/hash/epoch before publication |
| `retry_profile_ref.kind` | `enum(retry)` | req | checked |  | Profile discriminator; always `retry` for this reference |
| `retry_profile_ref.id` | `id` | req | checked |  | Policy-local profile id |
| `retry_profile_ref.sha256` | `sha256` | req | checked |  | Complete immutable profile hash |
| `execution_profile_ref` | `object` | req | checked |  | Pinned `ProfileRef(kind=execution)` for identity, paths, network, credentials, IPC and limits |
| `execution_profile_ref.kind` | `enum(execution)` | req | checked |  | Always `execution` |
| `execution_profile_ref.id` | `id` | req | checked |  | Policy-local profile id |
| `execution_profile_ref.sha256` | `sha256` | req | checked |  | Complete immutable profile hash |
| `verifier` | `object` | opt | checked |  | The step's **gate capsule**: the capsule the gate host calls with this Binding's `judged` checks, pinned like the capsule ([nodes](../system/nodes.md#gates)). Required when any of `checks` is judged; policy `every_step_gated` (proposed) requires it on every `dispatch` Binding |
| `verifier.decl_hash` | `sha256` | req | checked |  | The judge's version |
| `verifier.code_sha256` | `sha256` | req | checked |  | What the loader checks before each judge call |
| `verifier.verdict_ref` | `Ref(verdict)` | req | checked |  | The Verdict that admitted the judge |
| `verifier.budget` | `object` | req | checked |  | The limit per judge call, from policy `budgets`, in the shape of `budget`. Example: `{"time_s": 120}` |
| `gate_profile_ref` | `object` | req | checked |  | Pinned `ProfileRef(kind=gate)` selecting all applicable deterministic, semantic, evidence and fold rules. Required on every governed dispatch Binding |
| `gate_profile_ref.kind` | `enum(gate)` | req | checked |  | Profile discriminator; always `gate` for this reference |
| `gate_profile_ref.id` | `id` | req | checked |  | Policy-local profile id |
| `gate_profile_ref.sha256` | `sha256` | req | checked |  | Complete immutable profile hash |
| `nested_gate_profiles` | `list<object>` | opt | checked |  | Freeze-generated entries for every admitted nested dependency reachable from this step; required when one exists; no runtime profile selection |
| `nested_gate_profiles[].decl_hash` | `sha256` | req | checked |  | Exact dependency declaration subject to the nested Gate |
| `nested_gate_profiles[].profile_ref` | `object` | req | checked |  | Policy-owned applicable deterministic/semantic criteria for this dependency |
| `nested_gate_profiles[].profile_ref.kind` | `enum(gate)` | req | checked |  | Nested dependency profile discriminator; always gate |
| `nested_gate_profiles[].profile_ref.id` | `id` | req | checked |  | Policy-local profile name |
| `nested_gate_profiles[].profile_ref.sha256` | `sha256` | req | checked |  | Complete immutable profile closure hash |
| `role` | `string` | opt | unchecked | planner | Which agent or role runs the capsule at this call site, as the workflow names it. The capsule itself never names a role. Example: `reviewer` |
| `overlays` | `list<Ref(artifact)>` | opt | unchecked | RSI | Experience or guidance loaded with the capsule at this call site. Nothing else is loaded |

**The runner refuses** a call in a run, writing an Observation with `outcome: refused`, when: there is no Binding (`BINDING_MISSING`); a profile is missing or hash/epoch mismatched (`POLICY_UNRESOLVED`); the loaded code's hash differs from `code_sha256` (`CARRIER_CHANGED`); input names or types differ (`PORT_MISMATCH`); an execution requirement is unsupported (`PERMISSION_UNENFORCEABLE` or `UNSUPPORTED_SECURITY_PROFILE`); a permission is denied (`PERMISSION_DENIED`); or a precondition fails.

A capsule tried in place of another is bound by its own Binding with its own `step_id`. Everything else the runner needs (effect class, preconditions, ports, model limits) it reads from the Declaration by `decl_hash`, so the Binding repeats none of it (INV-5).

## Reuse

- Symphony and agent-core have no binding record; this one is ours.
- `CapabilityDescriptor.content_hash` (agent-core `symphony/models/capability.py:74`): not the code pin; at most a cross-check.
