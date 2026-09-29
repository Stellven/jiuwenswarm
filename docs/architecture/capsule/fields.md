---
type: schema
id: cc.declaration.v1
status: proposed
tags: [capsule, schema]
---

# Declaration · `cc.declaration.v1`

A capsule is its Declaration: the contract one capability declares, written by its author. It says what the capability takes, gives, needs, changes and promises. It points at its code by hash and never holds it. It holds no task and no policy. Once admitted it never changes; a change is a new version with its own `decl_hash`. A capsule completes its Declaration rather than failing: see [when a call goes wrong](capsule.md#when-a-call-goes-wrong-proposed) (proposed, INV-19).

This is the only page that defines the Declaration's fields. The [schemas](../schemas/schemas.md) folder holds the records the system keeps *about* capsules, such as Candidates, Verdicts and Observations.

The **M1** and **Unlocks** columns are defined on [checked and unchecked at M1](stages.md); the type grammar is in the [invariants](../schemas/invariants.md).

A field serves one or more of four uses:

- **Verification:** the code that runs is the code that was tested, and outputs keep their promises.
- **RSI** (recursive self-improvement): build a new version from evidence.
- **Selection:** choose a capsule for a call.
- **Observability:** explain afterwards what ran, why and at what cost.

**Rules:** INV-7 (no task), INV-9 (every output has a check), INV-14 (strict core), INV-17 (the policy decides what is required), INV-19 (proposed: declared failures only). See [invariants](../schemas/invariants.md).

## Fields

Authored JSON. It carries `schema_version` and `ext` (extensions, such as agent-core settings) from [common](../schemas/common.md); the rest of the envelope belongs to the [Candidate](../schemas/candidate.md) that submits it.

### identity: what it is, and which code

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `identity.name` | `string` | req | checked |  | A stable dot-separated handle, local to a library; `decl_hash` is the global identity. Every version hangs off it, the Standing is keyed by it, and Observations group by it. Example: `doc.pdf_to_text` |
| `identity.namespace` | `string` | opt | unchecked | store, importer | The publisher the name belongs to, when a capsule moves between libraries. Example: `org.example` |
| `identity.kind` | `reg(capsule_kind)` | req | checked |  | How the capability runs, a `capsule_kind` value; see [kinds](capsule.md#kinds-of-capsule). The runner calls each kind its own way, and admission tests it that way. Example: `tool` |
| `identity.carrier` | `object` | opt | checked |  | The code, when it is one file that imports no unpinned local module; otherwise use `body`. Exactly one of `carrier`, `body`, `remote` or `members` is set |
| `identity.carrier.ref` | `string` | req | checked |  | A path relative to the capsule root (one of the Candidate's `files[].path`) plus a symbol. Example: `pdf_text.py:extract` |
| `identity.carrier.sha256` | `sha256` | req | checked |  | The file's hash. Admission hashes the file again and refuses a mismatch (`HASH_MISMATCH`); the runner refuses changed code at load (`CARRIER_CHANGED`) |
| `identity.body` | `list<object>` | opt | checked |  | Every file of the capability, each hashed, including every imported module that is not a pinned dependency. For more than one file, such as a skill folder |
| `identity.body[].path` | `string` | req | checked |  | Relative to the capsule root. Example: `SKILL.md` |
| `identity.body[].sha256` | `sha256` | req | checked |  | That file's hash |
| `identity.remote` | `object` | opt | unchecked | remote capsules | A service we do not host and so cannot hash, such as a remote MCP server or an A2A agent, pinned by endpoint and version instead. The pin proves what was pinned, not what the service runs |
| `identity.remote.endpoint` | `uri` | req | unchecked | remote capsules | Where it is. Example: `https://mcp.example.org/sse` |
| `identity.remote.version` | `string` | req | unchecked | remote capsules | The version pinned at admission. Example: `1.4.2` |
| `identity.remote.interface_version_range` | `string` | opt | unchecked | remote capsules | Compatible interface versions. Example: `>=1.4 <2` |
| `identity.owner` | `string` | opt | unchecked | store | Who answers for the capability now. Example: `team-docs` |
| `identity.tags` | `list<string>` | opt | unchecked | store, selection | Free labels for search. Example: `["documents"]` |
| `identity.license` | `string` | opt | unchecked | importer, store | An SPDX licence id for imported code. Example: `Apache-2.0` |
| `identity.summary` | `text` | req | checked |  | At most 400 characters on what it does: the only prose a model sees when choosing a capsule. Names no step, workflow or other capsule (INV-7). Example: `Extract the plain text of a PDF, page by page.` |
| `identity.lineage` | `object` | opt | unchecked | RSI, tracking | Where this version came from: the version tree RSI branches from. Merges make it a graph. A child with the same `interface_hash` must also pass its parent's suites ([checks](../schemas/checks.md)) |
| `identity.lineage.parent_hash` | `sha256` | req | unchecked | RSI, tracking | The parent version's `decl_hash` |
| `identity.lineage.relation` | `enum(supersedes, specialises, merges, migrated_from)` | req | unchecked | RSI, tracking | How it relates to its parent. `supersedes`: a new version under the same name. `specialises`: a branch under a new name. `merges`: joins `co_parent_hashes` into it. `migrated_from`: the same capability rewritten for a new schema or runtime. A rollback is a Standing move, not a new version |
| `identity.lineage.co_parent_hashes` | `list<sha256>` | opt | unchecked | RSI, merge, composer | The other versions merged or fused into this one; required when `relation` is `merges` |

### ports: what it takes and gives

Each entry is a `Port`, with the field names of agent-core's `CapabilityIO`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `ports.inputs` | `list<Port>` | req | checked |  | Every input. May be empty |
| `ports.outputs` | `list<Port>` | req | checked |  | Every output; at least one. Checks run on every output, and selection matches and chains capsules by port type |
| `Port.name` | `string` | req | checked |  | Unique within its list. Example: `text` |
| `Port.type` | `reg(port_type)` | req | checked |  | A type from the [port type vocabulary](../schemas/port-types.md). Example: `text` |
| `Port.description` | `text` | opt | checked |  | One line on what the value means |
| `Port.required` | `boolean` | opt | checked |  | Inputs only. Default `true` |
| `Port.value_schema` | `object` | opt | checked |  | The value's JSON Schema when `type` is `json` (the policy requires it then), pinned by hash so it cannot change under a fixed `decl_hash` (INV-6). `check.value_matches_type.v1` checks every value of the port against it |
| `Port.value_schema.uri` | `uri` | req | checked |  | Where the JSON Schema is |
| `Port.value_schema.sha256` | `sha256` | req | checked |  | The schema's hash, so a changed schema is refused |
| `Port.check_id` | `id` | opt | checked |  | The check that validates this output. Absent on inputs; required on every output (INV-9). Example: `text_not_empty` |

### needs: what must hold, and what it uses

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `needs.when` | `list<Predicate>` | req | checked |  | Preconditions; may be empty. One shared evaluator runs them. The runner refuses a call whose precondition is false and records each result in the Observation. Selection filters out capsules that cannot run |
| `Predicate.id` | `id` | req | checked |  | Observations cite it as `predicate_id`. Example: `pdf_present` |
| `Predicate.path` | `string` | req | checked |  | Where in the state to look. Example: `inputs.pdf` |
| `Predicate.op` | `reg(predicate_op)` | req | checked |  | The test. Example: `present` |
| `Predicate.value` | `json` | opt | checked |  | What to compare with, for ops that need one. Example: `0` for `gt` |
| `Predicate.evaluable_at` | `enum(planning, dispatch, both)` | opt | unchecked | planner | When the fact can be known: `planning` (before the run starts), `dispatch` (just before the call), or both. Default `dispatch` |
| `Predicate.state_source` | `string` | opt | unchecked | selection | Where the state comes from: `inputs`, `workspace` or `external:<ref>`. Example: `workspace` |
| `needs.external` | `list<object>` | opt | checked |  | The other capsules it calls, each pinned to one admitted version. A service we cannot host is itself a remote capsule with its own pin. Admission refuses a dependency that is not admitted (`OPERATOR_NOT_ADMITTED`). Calls made through the runner are refused outside this list; in-process calls are enforced only in the isolated sandbox |
| `needs.external[].ref` | `string` | req | checked |  | The capsule's name. Example: `op.ocr` |
| `needs.external[].decl_hash` | `sha256` | req | checked |  | The exact admitted version it calls. A new version of the dependency changes nothing here until a new version of this capsule re-pins it |
| `needs.external[].purpose` | `text` | opt | unchecked | RSI | What the dependency is for, in a sentence. When present, RSI may re-pin it to a newer version, if `evolution.rsi` allows ([RSI](rsi.md#updating-dependencies)). Knowing a dependency's purpose is what lets a builder repair a capsule when the dependency changes. Read by builders as data, never as instructions. Example: `OCR for scanned pages` |
| `needs.network` | `enum(none, egress, ingress, both)` | opt | checked |  | The network access it needs. Default `none`. Where a permission check or the sandbox runs, it allows only this |
| `needs.dependencies` | `object` | opt | unchecked | importer, isolated verification | What must be installed to run it in isolation |
| `needs.dependencies.runtime` | `string` | req | unchecked | importer, isolated verification | Language and runtime version. Example: `python>=3.11` |
| `needs.dependencies.platforms` | `list<string>` | opt | unchecked | importer, isolated verification | Platforms it runs on. Example: `["linux/amd64"]` |
| `needs.dependencies.packages` | `list<object>` | opt | unchecked | importer, isolated verification | The direct packages, each `{name, version, source, purpose}`, every one pinned by the lockfile. `purpose` is optional and means what it does in `needs.external`: when present, RSI may re-pin the package. Example: `{"name": "pydantic", "version": "2.9.2", "source": "pypi", "purpose": "validates port values"}` |
| `needs.dependencies.lockfile` | `object` | opt | unchecked | importer, isolated verification | `{uri, sha256}` of a lockfile that pins every package, including indirect ones. Required when `packages` is set (rule `dependencies_pinned`). Example: `{"uri": "uv.lock", "sha256": "..."}` |
| `needs.config` | `object` | opt | unchecked | importer, isolated verification | Settings fixed when the capability is installed or started, which are not ports. Secrets go in `needs.secrets` |
| `needs.config.args` | `map<string, json>` | opt | unchecked | importer, isolated verification | Start-up arguments. Example: `{"max_pages": 500}` |
| `needs.config.env` | `map<string, string>` | opt | unchecked | importer, isolated verification | Environment variables that are not secrets. Example: `{"LANG": "C.UTF-8"}` |
| `needs.secrets` | `list<object>` | opt | unchecked | isolated verification | Credentials it needs, by name only, never values: each `{name, purpose}`. The sandbox injects them and the permission check allows them. Example: `{"name": "GITHUB_TOKEN", "purpose": "read private repos"}` |
| `needs.resources` | `object` | opt | unchecked | isolated verification | What one call needs to run: `{cpu, gpu, memory_mb, disk_mb, timeout_s}`, each optional. Example: `{"memory_mb": 2048, "timeout_s": 120}` |

**Models are not part of the capsule layer.** There is no model field and no role field. Selection picks a capsule, never a model, and there is no central library that picks both. Whether a capsule uses a model, which one, and whether that model is routed at runtime are its author's choice and its author's job, made in the capsule's own files, such as a skill's front matter or its code. Those files are hashed, so a change of fixed model is a new version, tested like any other change. A capsule whose author wants its model chosen at runtime calls a model router from its own code; the capsule layer never sees that. The Declaration still describes the work in enough detail that a router could choose from it. Which agent or role runs a capsule is decided in the [Binding](../schemas/binding.md), not in the capsule.

### changes: what it does to the world

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `changes.effect_class` | `enum(pure, read_only, idempotent, compensable, irreversible)` | req | checked |  | The author's promise about state and undo. Admission checks it against `effects`. Retries, parallelism and permissions follow from it through policy `mappings` |
| `changes.effects` | `list<object>` | opt | checked |  | Each effect on the world. Admission checks they agree with `effect_class` |
| `changes.effects[].resource_key` | `string` | req | checked |  | What it touches. Example: `fs:workspace/out/*` |
| `changes.effects[].scope` | `string` | req | checked |  | How far it reaches. Example: `run` |
| `changes.effects[].idempotent` | `boolean` | req | checked |  | Whether doing it twice equals doing it once |
| `changes.effects[].reversibility` | `enum(none, compensable, reversible)` | req | checked |  | Whether and how it can be undone: `none`, by a compensating action, or by restoring the prior state |
| `changes.effects[].undo` | `text` | opt | checked |  | How to undo it, applied by a person or a later tool, or a statement that it cannot be undone |
| `changes.state_kind` | `enum(none, reads_external, session, persistent)` | opt | checked |  | Which outside state it depends on. Default `none`. `reads_external` capsules ship fixtures with their tests, so the tests do not depend on the outside world |

### guarantees: what it promises

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `guarantees.checks` | `list<Check>` | req | checked |  | Every promise, each a [check](#checks-one-runnable-test-each); at least one |
| `guarantees.failure_modes` | `list<object>` | opt | unchecked | retries, fallbacks, RSI | Proposed. The only ways the capsule may end without an output (INV-19). The runner records one as `outcome: error` with its code. What happens to other exceptions: [capsule](capsule.md#when-a-call-goes-wrong-proposed) |
| `guarantees.failure_modes[].reason_code` | `string` | req | unchecked | retries, fallbacks, RSI | `UPPER_SNAKE`, unique within the capsule, and not a `reason_code` registry value. Additive: a later version never drops an admitted code. Example: `PDF_ENCRYPTED` |
| `guarantees.failure_modes[].when` | `text` | req | unchecked | retries, fallbacks, RSI | When it happens. Example: `The PDF is password-protected.` |
| `guarantees.failure_modes[].retriable` | `boolean` | req | unchecked | retries, fallbacks, RSI | Whether the same call may succeed if tried again |
| `guarantees.quality` | `object` | opt | unchecked | librarian | For judged outputs: the pass rate the judged check should reach. The librarian measures the actual rate, and RSI improves toward the target |
| `guarantees.quality.criterion_check_id` | `id` | req | unchecked | librarian | The judged check that defines "good". Example: `text_faithful` |
| `guarantees.quality.target_rate` | `number` | req | unchecked | librarian | Between 0 and 1. Example: `0.9` |

### checks: one runnable test each

A `Check` is a shape, not a record. It is written in full in one of three places: here, in `guarantees.checks`; in the [port type vocabulary](../schemas/port-types.md)'s `checks`, for registry checks and the gate's fixed checks; or in a [Binding](../schemas/binding.md)'s `step_checks`, for checks a workflow adds at one call site. Elsewhere it is named by id. Test cases and suites, which admission writes to run checks, are on the [checks](../schemas/checks.md) page.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `Check.id` | `id` | req | checked |  | Referred to as `check_id`. Unique within its Declaration, and `<capsule name>/<id>` from outside. A registry check is `check.<name>.v<n>` |
| `Check.anchor` | `reg(check_anchor)` | req | checked |  | What a pass rests on: `deterministic` (code), `reference` (a known answer) or `judged` (a model or person) |
| `Check.target` | `string` | req | checked |  | A port or a type. Example: `ports.outputs.text` |
| `Check.over` | `enum(each_call, outputs, inputs_and_outputs)` | req | checked |  | What it looks at. `each_call`: the call's Observation (outcome, cost), not the values. `outputs`: the output values. `inputs_and_outputs`: the input and output values |
| `Check.applies_at` | `enum(admission, node, both)` | req | checked |  | `admission`: needs a test case's `expected`, so runs only at admission. `node`: needs only the output, so runs at the gate after a call in a run, and at admission on test-call outputs. `both`: each |
| `Check.runner` | `object` | req | checked |  | The pinned code that runs it. For a judged check, the rubric code; the model-backed judge is the Binding's `verifier` |
| `Check.runner.ref` | `string` | req | checked |  | A module path or evaluator id. Example: `checks/text.py:not_empty` |
| `Check.runner.sha256` | `sha256` | req | checked |  | The runner's hash; every result names it |
| `Check.description` | `text` | req | checked |  | What passes, in one line. Example: `The text has a non-space character.` |
| `Check.author` | `string` | req | checked |  | Who wrote it; for a certifying check, not the builder (INV-10). Example: `reviewer-1` |


### composition: capsules made of capsules

Every capsule is a graph of capsules. A **singleton**, the most common form, is a one-node graph whose node is its own code. A composite lists its nodes in `members` and its edges in `wiring`. A sequence, a fan-out and a tree are all just wirings, so there is no field for the shape. See [composition](composition.md).

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `members` | `list<object>` | opt | unchecked | composer | The nodes of the graph: the capsules it is made of, each pinned. Set instead of `carrier`, `body` or `remote` |
| `members[].id` | `string` | req | unchecked | composer | The member's local name, used in `wiring`. Example: `ocr` |
| `members[].decl_hash` | `sha256` | req | unchecked | composer | The member version. Its own `code_sha256` pins its code |
| `wiring` | `list<object>` | opt | unchecked | composer | The edges of the graph, which also give the order. Required with `members`. Each `{from, to}`: `inputs.<port>` or `<member>.outputs.<port>` into `<member>.inputs.<port>` or `outputs.<port>`. Example: `{"from": "inputs.pdf", "to": "ocr.inputs.image"}` |

### evolution: what RSI may change

RSI is opt-in. Every capsule states whether RSI may build new versions of it; if its author does not allow it, RSI may not touch it. See [RSI](rsi.md).

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `evolution.rsi` | `enum(none, propose, submit)` | req | checked |  | What RSI may do with this capsule. `none`: nothing; RSI may not submit a child of it. `propose`: RSI may submit a child, which admission holds as `admitted_inactive` until a person activates it. `submit`: RSI may submit a child that becomes current when admitted. Example: `none` |
| `evolution.frozen` | `list<string>` | opt | unchecked | RSI | Parts of the Declaration a child must keep unchanged, as field paths. Example: `["ports", "changes.effect_class"]` |
| `evolution.notes` | `text` | opt | unchecked | RSI | What the author wants a builder to know: weak spots, ideas, what not to change |

Reserved names, not specified: `changes.provides[]`, `changes.invariants[]`, `needs.injects[]`.

## Computed by admission, never written by the author

All three are checked at M1.

- **`decl_hash`**: the hash (INV-15) of the whole Declaration **with every default filled in**. Each optional field whose description names a default (such as `Port.required: true`) is written out before hashing, so an explicit and an implicit default give the same hash. Only v1.0 defaults are filled in (INV-16). It is the capsule's identity and version; there is no version number. Every record about a capsule names it.
- **`interface_hash`**: the hash of what a test depends on, and nothing else, with v1.0 defaults filled in as for `decl_hash`: `identity.name`, `identity.kind`, `ports` without `description`s, `needs.when`, `changes.effect_class`, and each check's `id`, `target`, `anchor` and `applies_at`. Moving a file, editing the summary or updating a check's runner leaves it unchanged, so the tests still apply, and a child with the same interface reuses its parent's tests. `guarantees.failure_modes` is left out: codes are only ever added (rule `failure_modes_additive`), and adding one does not change what existing tests expect.
- **`code_sha256`**: what the loader checks before every call. With a `carrier`, `carrier.sha256`; with a `body`, the hash of the `body` list sorted by `path`; with a `remote`, the hash of `{endpoint, version}`, which proves what was pinned, not what the service runs; with `members`, the hash of the `members` list sorted by `id`.

The [Verdict](../schemas/verdict.md) records `decl_hash` and `interface_hash`; the [Binding](../schemas/binding.md) records `decl_hash` and `code_sha256`. The Verdict's `scope.candidate_id` links a `decl_hash` to the Candidate that submitted it.

## Example

A complete Declaration for a small tool, with only checked fields and `evolution`:

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "doc.pdf_to_text",
    "kind": "tool",
    "carrier": {"ref": "pdf_text.py:extract", "sha256": "9f2c..."},
    "summary": "Extract the plain text of a PDF, page by page."
  },
  "ports": {
    "inputs": [{"name": "pdf", "type": "file", "description": "the PDF to read"}],
    "outputs": [{"name": "text", "type": "text", "description": "the text, pages in order", "check_id": "text_not_empty"}]
  },
  "needs": {
    "when": [{"id": "pdf_present", "path": "inputs.pdf", "op": "present"}],
    "external": [{"ref": "op.ocr", "decl_hash": "41ab...", "purpose": "OCR for scanned pages"}],
    "network": "none"
  },
  "changes": {"effect_class": "pure", "effects": []},
  "guarantees": {
    "checks": [{
      "id": "text_not_empty", "anchor": "deterministic", "target": "ports.outputs.text",
      "over": "outputs", "applies_at": "both",
      "runner": {"ref": "checks/text.py:not_empty", "sha256": "c3d1..."},
      "description": "The text has a non-space character.", "author": "reviewer-1"
    }]
  },
  "evolution": {"rsi": "propose"}
}
```

## Elsewhere, not in the Declaration

- **Measured, never authored:** cost, latency and pass rate come from Observations, recorded in a [Finding](../schemas/finding.md) of kind `measurement` (unchecked: librarian, RSI).
- **In the policy:** required fields per epoch (`required`), predicate `on_unknown` and `max_age_s` (`defaults`), what a level needs (`levels`), effect class to permissions (`mappings`).
- **In the Verdict:** exemption (`level: exempt`). **In the Binding:** budget, overlays, and which role runs the capsule. **In the Candidate:** provenance, builder evidence, test aids. **In a test case:** `fixtures`, which reset outside state.

## Reuse

- `CapabilityDescriptor`, `CapabilityIO` (agent-core `symphony/models/capability.py:15`, `:61`): port names as there; `value_schema` travels in `CapabilityIO.metadata`.
- `ToolCard` flags (`core/foundation/tool/base.py:92-119`) and `PermissionLevel` (`harness/security/permission_engine/models.py:19`): as is, as what `effect_class` maps to. Three booleans cannot hold five classes, so `effect_class` stays ours.
- `ToolExposure` (`core/foundation/tool/exposure.py:14`): as is, in `ext.openjiuwen.exposure`.
- `capsule-openjiuwen/merged/capsule.schema.json` `$defs`: the starting shapes, renamed.
