---
type: schema
id: cc.binding.v1
status: proposed
tags: [schema]
---

# Binding · `cc.binding.v1`

The pin for one call site of a run: exactly one capsule version, by hash, with the Verdict that admitted it, the checks the gate runs on its output, its budget, and the judge the gate may call. It is written once, by the control code that starts the run (the workflow runtime), before the call site first runs. Every capsule call made through the runner is pinned: the runner refuses a call in a run that has no Binding, and refuses to load code that does not match it. Third-party packages are pinned only when the Declaration's `needs.dependencies.lockfile` is set.

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
| `vocabulary_ref` | `object` | req | checked |  | The [port type vocabulary](port-types.md) whose schemas and checks apply. The writer refuses one in which a port type of the capsule has a different `types[].version` than in the Verdict's `vocabulary_ref` |
| `vocabulary_ref.version` | `integer` | req | checked |  | The vocabulary's `vocabulary_version`. Example: `1` |
| `vocabulary_ref.sha256` | `sha256` | req | checked |  | The vocabulary document's hash |
| `checks` | `list<object>` | req | checked |  | Every check the gate runs on this call's output, assembled once from every check whose `applies_at` is `node` or `both`. Each is `{check_id, source}`, `source` being `capsule` (the Declaration's), `type` (the output type's, from the vocabulary) or `step` (from `step_checks`). At least one, since every type has a `node` check (INV-9) |
| `step_checks` | `list<Check>` | opt | checked |  | The full [Check](checks.md) for each `checks` entry with `source: step`: a check the workflow adds for this call site. Required when there is one |
| `budget` | `object` | req | checked |  | The limit per call, from policy `budgets`: `{tokens, time_s, money}`, each optional; `tokens` and `money` are unchecked (Unlocks: budgets). The gate fails a finished call over it. Example: `{"time_s": 600}` |
| `verifier` | `object` | opt | checked |  | The model-backed judge capsule the gate calls for this Binding's `judged` checks, pinned like the capsule. Required when any of `checks` is judged |
| `verifier.decl_hash` | `sha256` | req | checked |  | The judge's version |
| `verifier.code_sha256` | `sha256` | req | checked |  | What the loader checks before each judge call |
| `verifier.verdict_ref` | `Ref(verdict)` | req | checked |  | The Verdict that admitted the judge |
| `verifier.budget` | `object` | req | checked |  | The limit per judge call, from policy `budgets`, in the shape of `budget`. Example: `{"time_s": 120}` |
| `role` | `string` | opt | unchecked | planner | Which agent or role runs the capsule at this call site, as the workflow names it. The capsule itself never names a role. Example: `reviewer` |
| `overlays` | `list<Ref(artifact)>` | opt | unchecked | RSI | Experience or guidance loaded with the capsule at this call site. Nothing else is loaded |

**The runner refuses** a call in a run, writing an Observation with `outcome: refused`, when: there is no Binding (`BINDING_MISSING`); the loaded code's hash differs from `code_sha256` (`CARRIER_CHANGED`); the input names differ from the capsule's `Port.name`s (`PORT_MISMATCH`); a permission is denied (`PERMISSION_DENIED`); or a precondition fails (`PRECONDITION_FAILED`, `PRECONDITION_DEFERRED`).

A capsule tried in place of another is bound by its own Binding with its own `step_id`. Everything else the runner needs (effect class, preconditions, ports, model limits) it reads from the Declaration by `decl_hash`, so the Binding repeats none of it (INV-5).

## Reuse

- Symphony and agent-core have no binding record; this one is ours.
- `CapabilityDescriptor.content_hash` (agent-core `symphony/models/capability.py:74`): not the code pin; at most a cross-check.
