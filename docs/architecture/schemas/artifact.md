---
type: schema
id: cc.artifact.v1
status: proposed
tags: [schema]
---

# Artifact: one value · `cc.artifact.v1`

One value that a capsule produced, a person supplied, or control code made. It has two layers: the **content**, stored once and keyed by its hash, and the **Artifact record**, one per appearance, which says what the content is and where it came from. Observations, test cases and the Candidate refer to it by `Ref(artifact)`.

**A capsule's output is always an Artifact.** Its `type` is the output port's type; for a `json` port its `value` also matches the port's `Port.value_schema`. It is never written again as a separate record (INV-5). Records are what CC's tools write; values are Artifacts.

**Rules:** INV-2, INV-5, INV-15.

## Fields

Extends [common](common.md). Its `scope` is `run_id` for what a run makes, `candidate_id` for what an admission makes (test inputs, test-call outputs), or `library` for test inputs and fixtures kept with a suite. Its `id` is the `artifact_id`. The runner writes every Artifact in a run, including values that people or control code hand to it; admission writes those of an admission and of the library.

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
| `issues` | `list<Reason>` | opt | unchecked | quality labels, RSI | Proposed. The standard place for caveats about the value: vague, incomplete or contradictory input (`INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE`, `INPUT_CONTRADICTORY`), and anything else a reader should know. Example: `[{"code": "INPUT_INCOMPLETE", "message": "pages 4-6 unreadable"}]` |
| `produced_by` | `object` | opt | checked |  | Set when `origin` is `capsule`: `{obs_id, port}`, the call and output port that produced it. An id, not a `Ref`: the Observation is written after its outputs and pins their hashes, so the Artifact cannot pin the Observation's |

**Lineage.** `produced_by` names the call; that call's Observation names its input Artifacts; each of those names its own call. Following the chain gives the calls behind any value, so no `derived_from` field is stored (INV-5). What a call read outside its ports is not in the chain.

## Elsewhere

How `content_sha256` is computed: INV-15, policy `hashing`. Whether a value travels inline, and which store holds content: the runner's choice. A new kind of value is a new [port type](port-types.md), never a new Artifact field.

## Reuse

- `E2AFileRef {uri, name, mime_type, size}` (jiuwenswarm `common/e2a/models.py:60`): as is, for `content_ref`.
- Object store and KV store (agent-core `core/foundation/store/object/base_storage_client.py`, `base_kv_store.py:42`): as is, for the content.
- `ArtifactRef {artifact_id, sha256, kind, path}` (`rsi/schema.py:152`): mapped on import from RSI; `sha256` becomes `content_sha256`, `kind` becomes `type`.
- `content_hash` (`extensions/observability/content_addressing.py:84`, `:153`): not reused for JSON; it serialises without sorted keys, so equal values can hash differently.
