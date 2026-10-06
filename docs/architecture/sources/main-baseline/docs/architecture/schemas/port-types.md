---
type: schema
id: cc.types.v1
status: proposed
tags: [schema]
---

# Port type vocabulary · `cc.types.v1`

The one list of type names that ports and checks use, each with the schema a value must match and the checks every value of that type must pass. It gives the values of `reg(port_type)`, and it holds every registry check in full. The runner validates values by type, the gate runs each type's checks, selection chains capsules by type, and Symphony matches `CapabilityIO.type` by name. Without one list, `text` and `string` silently fail to match.

**Rules:** INV-9, INV-13, INV-16 (a new type is additive).

## Fields

One document per version. Extends [common](common.md), with `scope.library: true`. A [Verdict](verdict.md) and a [Binding](binding.md) each pin one with `vocabulary_ref {version, sha256}`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `vocabulary_version` | `integer` | req | checked |  | Each change is a new record with this number one higher (INV-2). Example: `1` |
| `types` | `list<object>` | req | checked |  | One entry per type |
| `types[].type` | `string` | req | checked |  | The name ports use: lower snake case, or parameterised as `collection<T>`. Example: `text` |
| `types[].version` | `integer` | req | checked |  | Goes up when the type's meaning changes. Ports name the type only; the vocabulary pinned by the Verdict and the Binding fixes the version. Example: `1` |
| `types[].description` | `text` | req | checked |  | One line. Example: `A UTF-8 string.` |
| `types[].value_schema` | `json` | req | checked |  | The JSON Schema every value must match. Example for `integer`: `{"type": "integer"}` |
| `types[].checks` | `list<id>` | req | checked |  | Checks every output of this type must pass at the gate (source `type`), named by id from `checks`. Always includes `check.value_matches_type.v1`, so at least one applies at `node` (INV-9). Example: `["check.value_matches_type.v1"]` |
| `checks` | `list<Check>` | req | checked |  | Every registry check in full: the type checks, and the gate's fixed checks `check.call_ok.v1` and `check.within_budget.v1` (both `deterministic`, `over: each_call`) |

## The base types

| Type | M1 | `value_schema`, in short |
|---|---|---|
| `text` | checked | a UTF-8 string |
| `integer`, `number`, `boolean` | checked | the JSON type |
| `json` | checked | any object; the port gives its schema in `Port.value_schema`, which `check.value_matches_type.v1` also applies |
| `file` | checked | a file stored by reference: the Artifact's `content_ref` |
| `path` | checked | a path inside the run's workspace |
| `collection<T>` | checked | a list of `T` |

Domain types (research outputs, reports, patches and so on) are added as entries, each with its own checks. No `unknown` or `any` type exists (policy rule `no_any_type`).

## Reuse

- `CapabilityIO.type` (agent-core `symphony/models/capability.py:19`): as is; this list is its legal values.
- AI4Research's evidence schemas (`harness/schemas/evidence/`): their `outputs` parts are the starting `value_schema`s for domain types. Their envelope requires `task_id`, `sprint_id` and `node_id`, which would put a task into a capsule (INV-7).
- AI4Research's artifact-type checks (`evaluation-checks.v1.json`, `applies_to.kind: artifact_type`): imported into each type's `checks`.
