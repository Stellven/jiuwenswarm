---
type: schema
id: cc.declaration.v1
status: proposed
tags: [schema]
---

# Declaration · `cc.declaration.v1`

The contract one capability declares: what it takes, gives, needs, changes and promises. It points at its code by hash and never holds it. It holds no task and no policy. Once admitted it never changes; a change is a new version with its own `decl_hash`. *Proposed:* a capsule completes its Declaration: it returns outputs that match its ports even for vague or incomplete input, and puts the difficulty inside the output as data (INV-19).

**Rules:** INV-7 (no task), INV-9 (every output has a check), INV-14 (strict core), INV-17 (the policy decides what is required), INV-19 (proposed: declared failures only).

## Fields

Authored JSON. It carries `schema_version` and `ext` from [common](common.md); the rest of the envelope belongs to the [Candidate](candidate.md) that submits it.

**identity**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `identity.name` | `string` | req | checked |  | A stable dot-separated handle, local to a library; `decl_hash` is the global identity. Versions hang off it; the Standing is keyed by it. Example: `doc.pdf_to_text` |
| `identity.namespace` | `string` | opt | unchecked | store, importer | The publisher the name belongs to, when a capsule moves between libraries. Example: `org.example` |
| `identity.kind` | `reg(capsule_kind)` | req | checked |  | The form of the capability; the runner calls each kind its own way. Example: `tool` |
| `identity.carrier` | `object` | opt | checked |  | The code, when it is one file that imports no unpinned local module; otherwise use `body`. Exactly one of `carrier`, `body`, `remote` or `members` is set |
| `identity.carrier.ref` | `string` | req | checked |  | A path relative to the capsule root (one of the Candidate's `files[].path`) plus a symbol. Example: `pdf_text.py:extract` |
| `identity.carrier.sha256` | `sha256` | req | checked |  | The file's hash, which the code must match when loaded; a mismatch refuses the load with `CARRIER_CHANGED` |
| `identity.body` | `list<object>` | opt | checked |  | Every file of the capability, each hashed, including every imported module that is not a pinned dependency. For more than one file, e.g. a skill folder |
| `identity.body[].path` | `string` | req | checked |  | Relative to the capsule root. Example: `SKILL.md` |
| `identity.body[].sha256` | `sha256` | req | checked |  | That file's hash |
| `identity.remote` | `object` | opt | unchecked | remote capsules | A service we do not host and so cannot hash: a remote MCP server or an A2A agent |
| `identity.remote.endpoint` | `uri` | req | unchecked | remote capsules | Where it is. Example: `https://mcp.example.org/sse` |
| `identity.remote.version` | `string` | req | unchecked | remote capsules | The version pinned at admission. Example: `1.4.2` |
| `identity.remote.interface_version_range` | `string` | opt | unchecked | remote capsules | Compatible interface versions. Example: `>=1.4 <2` |
| `identity.owner` | `string` | opt | unchecked | store | Who answers for the capability now. Example: `team-docs` |
| `identity.tags` | `list<string>` | opt | unchecked | store, selection | Free labels for search. Example: `["documents"]` |
| `identity.license` | `string` | opt | unchecked | importer, store | An SPDX licence id. Example: `Apache-2.0` |
| `identity.summary` | `text` | req | checked |  | At most 400 characters on what it does: the only prose a model sees when choosing. Names no step, workflow or other capsule (INV-7). Example: `Extract the plain text of a PDF, page by page.` |
| `identity.lineage` | `object` | opt | unchecked | RSI, tracking | Where this version came from. Versions form a tree; merges make it a graph |
| `identity.lineage.parent_hash` | `sha256` | req | unchecked | RSI, tracking | The parent version's `decl_hash` |
| `identity.lineage.relation` | `enum(supersedes, specialises, merges, migrated_from)` | req | unchecked | RSI, tracking | How it relates to its parent. `supersedes`: a new version under the same name. `specialises`: a branch under a new name. `merges`: joins `co_parent_hashes` into it. `migrated_from`: the same capability rewritten for a new schema or runtime. A rollback is a Standing move, not a new version |
| `identity.lineage.co_parent_hashes` | `list<sha256>` | opt | unchecked | RSI, merge | The other versions merged or fused into this one; required when `relation` is `merges` |

**ports.** Each entry is a `Port`, with the field names of agent-core's `CapabilityIO`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `ports.inputs` | `list<Port>` | req | checked |  | Every input. May be empty |
| `ports.outputs` | `list<Port>` | req | checked |  | Every output; at least one |
| `Port.name` | `string` | req | checked |  | Unique within its list. Example: `text` |
| `Port.type` | `reg(port_type)` | req | checked |  | A type from the [port type vocabulary](port-types.md). Example: `text` |
| `Port.description` | `text` | opt | checked |  | One line on what the value means |
| `Port.required` | `boolean` | opt | checked |  | Inputs only. Default `true` |
| `Port.value_schema` | `object` | opt | checked |  | The value's schema when `type` is `json` (the policy requires it then), pinned by hash (INV-6). `check.value_matches_type.v1` checks every value of the port against it |
| `Port.value_schema.uri` | `uri` | req | checked |  | Where the JSON Schema is |
| `Port.value_schema.sha256` | `sha256` | req | checked |  | The schema's hash, so a changed schema is refused |
| `Port.check_id` | `id` | opt | checked |  | The check that validates this output. Absent on inputs; required on every output (INV-9). Example: `text_not_empty` |

**needs**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `needs.when` | `list<Predicate>` | req | checked |  | Preconditions that must hold before it runs; may be empty. One shared precondition evaluator runs them |
| `Predicate.id` | `id` | req | checked |  | Observations cite it as `predicate_id`. Example: `pdf_present` |
| `Predicate.path` | `string` | req | checked |  | Where in the state to look. Example: `inputs.pdf` |
| `Predicate.op` | `reg(predicate_op)` | req | checked |  | The test. Example: `present` |
| `Predicate.value` | `json` | opt | checked |  | What to compare with, for ops that need one. Example: `0` for `gt` |
| `Predicate.evaluable_at` | `enum(planning, dispatch, both)` | opt | unchecked | planner | When the fact can be known: `planning` (before the run starts), `dispatch` (just before the call), or both. Default `dispatch` |
| `Predicate.state_source` | `string` | opt | unchecked | selection | `inputs`, `workspace` or `external:<ref>`. Example: `workspace` |
| `needs.external` | `list<object>` | opt | checked |  | The capabilities or services it calls. Calls made through the runner are refused outside this list; in-process calls are enforced only in the isolated sandbox |
| `needs.external[].ref` | `string` | req | checked |  | A capsule name or a service id. Example: `op.ocr` |
| `needs.external[].pinned` | `boolean` | req | checked |  | Whether one exact version is required |
| `needs.external[].decl_hash` | `sha256?` | req | checked |  | The exact version when pinned; null otherwise |
| `needs.external[].unpinned_purpose` | `text` | opt | checked |  | Why any version will do. Required when not pinned |
| `needs.network` | `enum(none, egress, ingress, both)` | opt | checked |  | The network access it needs. Default `none`. Enforced where a permission check or the sandbox runs |
| `needs.dependencies` | `object` | opt | unchecked | importer, isolated verification | What must be installed to run it in isolation |
| `needs.dependencies.runtime` | `string` | req | unchecked | importer, isolated verification | Language and runtime version. Example: `python>=3.11` |
| `needs.dependencies.platforms` | `list<string>` | opt | unchecked | importer, isolated verification | Platforms it runs on. Example: `["linux/amd64"]` |
| `needs.dependencies.packages` | `list<object>` | opt | unchecked | importer, isolated verification | Each `{name, version, source}`. Example: `{"name": "pypdf", "version": "4.2.0", "source": "pypi"}` |
| `needs.dependencies.lockfile` | `object` | opt | unchecked | importer, isolated verification | `{uri, sha256}` of a lockfile that pins every package. Without it, third-party packages are not pinned. Example: `{"uri": "uv.lock", "sha256": "..."}` |
| `needs.config` | `object` | opt | unchecked | importer, isolated verification | Settings fixed when the capability is installed or started, which are not ports. Secrets go in `needs.secrets` |
| `needs.config.args` | `map<string, json>` | opt | unchecked | importer, isolated verification | Start-up arguments. Example: `{"max_pages": 500}` |
| `needs.config.env` | `map<string, string>` | opt | unchecked | importer, isolated verification | Environment variables that are not secrets. Example: `{"LANG": "C.UTF-8"}` |
| `needs.secrets` | `list<object>` | opt | unchecked | isolated verification | Credentials it needs, by name only, never values: each `{name, purpose}`. The sandbox injects them and the permission check allows them. Example: `{"name": "GITHUB_TOKEN", "purpose": "read private repos"}` |
| `needs.resources` | `object` | opt | unchecked | isolated verification | What one call needs to run: `{cpu, gpu, memory_mb, disk_mb, timeout_s}`, each optional. Example: `{"memory_mb": 2048, "timeout_s": 120}` |

There is no model field and no role field. Whether a capsule uses a model, which one, and whether it is routed are the author's choice, made in the capsule's hashed files and never exposed to the capsule layer. Roles are set in the Binding. See [fields](../capsule/fields.md#needs-what-must-hold-and-what-it-uses).

**changes**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `changes.effect_class` | `enum(pure, read_only, idempotent, compensable, irreversible)` | req | checked |  | The author's promise about state and undo. Retries, parallelism and permissions follow from it through policy `mappings` |
| `changes.effects` | `list<object>` | opt | checked |  | Each effect on the world. Admission checks they agree with `effect_class` |
| `changes.effects[].resource_key` | `string` | req | checked |  | What it touches. Example: `fs:workspace/out/*` |
| `changes.effects[].scope` | `string` | req | checked |  | How far it reaches. Example: `run` |
| `changes.effects[].idempotent` | `boolean` | req | checked |  | Whether doing it twice equals doing it once |
| `changes.effects[].reversibility` | `enum(none, compensable, reversible)` | req | checked |  | Whether and how it can be undone: `none`, by a compensating action, or by restoring the prior state |
| `changes.effects[].undo` | `text` | opt | checked |  | How to undo it, or a statement that it cannot be undone |
| `changes.state_kind` | `enum(none, reads_external, session, persistent)` | opt | checked |  | Which outside state it depends on. `reads_external` capsules ship fixtures with their tests. Default `none` |

**guarantees**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `guarantees.checks` | `list<Check>` | req | checked |  | Every promise, each a [check](checks.md); at least one |
| `guarantees.failure_modes` | `list<object>` | opt | unchecked | retries, fallbacks, RSI | Proposed. The only ways the capsule may end without an output (INV-19). The runner records one as `outcome: error` with its code |
| `guarantees.failure_modes[].reason_code` | `string` | req | unchecked | retries, fallbacks, RSI | `UPPER_SNAKE`, unique within the capsule, and not a `reason_code` registry value. Additive: a later version never drops an admitted code. Example: `PDF_ENCRYPTED` |
| `guarantees.failure_modes[].when` | `text` | req | unchecked | retries, fallbacks, RSI | When it happens. Example: `The PDF is password-protected.` |
| `guarantees.failure_modes[].retriable` | `boolean` | req | unchecked | retries, fallbacks, RSI | Whether the same call may succeed if tried again |
| `guarantees.quality` | `object` | opt | unchecked | librarian | For judged outputs: the pass rate the judged check should reach |
| `guarantees.quality.criterion_check_id` | `id` | req | unchecked | librarian | The judged check that defines "good". Example: `text_faithful` |
| `guarantees.quality.target_rate` | `number` | req | unchecked | librarian | Between 0 and 1. Example: `0.9` |

**composition** (for `kind: composite`)

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `members` | `list<object>` | opt | unchecked | composer | The capsules it is made of, each pinned. Set instead of `carrier`, `body` or `remote` |
| `members[].id` | `string` | req | unchecked | composer | The member's local name, used in `wiring`. Example: `ocr` |
| `members[].decl_hash` | `sha256` | req | unchecked | composer | The member version. Its own `code_sha256` pins its code |
| `structure` | `enum(sequence, parallel, graph)` | opt | unchecked | composer | How members run: in order, at once, or as `wiring` says. Required with `members` |
| `wiring` | `list<object>` | opt | unchecked | composer | Each `{from, to}`: `inputs.<port>` or `<member>.outputs.<port>` into `<member>.inputs.<port>` or `outputs.<port>`. Example: `{"from": "inputs.pdf", "to": "ocr.inputs.image"}` |

Reserved names, not specified: `evolution`, `changes.provides[]`, `changes.invariants[]`, `needs.injects[]`.

## Computed by admission

- **`decl_hash`**: the hash (INV-15) of the whole Declaration **with every default filled in**. Each optional field whose description names a default (such as `Port.required: true`) is written out before hashing, so an explicit and an implicit default give the same hash. Only defaults defined in v1.0 are filled in; a field added in a later v1.x hashes as absent when it is absent, so existing `decl_hash` values never change (INV-16). It is the capsule's identity and version; there is no version number.
- **`interface_hash`**: the hash of what a test depends on, and nothing else, with v1.0 defaults filled in as for `decl_hash`: `identity.name`, `identity.kind`, `ports` without `description`s, `needs.when`, `changes.effect_class`, and each check's `id`, `target`, `anchor` and `applies_at`. Moving a file, editing the summary or updating a check's runner leaves it unchanged, so the tests still apply. `guarantees.failure_modes` is left out: codes are only ever added (rule `failure_modes_additive`), and adding one does not change what existing tests expect.
- **`code_sha256`**: what the loader checks. With a `carrier`, `carrier.sha256`; with a `body`, the hash of the `body` list sorted by `path`; with a `remote`, the hash of `{endpoint, version}`, which proves what was pinned, not what the service runs; with `members`, the hash of the `members` list sorted by `id`.

The Verdict records `decl_hash` and `interface_hash`; the [Binding](binding.md) records `decl_hash` and `code_sha256`. The Verdict's `scope.candidate_id` links a `decl_hash` to the Candidate that submitted it.

## Elsewhere

Cost, latency and pass rate are measured from Observations, never authored: a [Finding](finding.md) of kind `measurement`. In the policy: required fields per epoch (`required`), predicate `on_unknown` and `max_age_s` (`defaults`), what a level needs (`levels`), effect class to permissions (`mappings`). In the Verdict: exemption (`level: exempt`). In the Binding: budget, overlays. In the Candidate: provenance, builder evidence, test aids. In a test case: `fixtures`, which reset outside state.

## Reuse

- `CapabilityDescriptor`, `CapabilityIO` (agent-core `symphony/models/capability.py:15`, `:61`): port names as there; `value_schema` travels in `CapabilityIO.metadata`.
- `ToolCard` flags (`core/foundation/tool/base.py:92-119`) and `PermissionLevel` (`harness/security/permission_engine/models.py:19`): as is, as what `effect_class` maps to. Three booleans cannot hold five classes, so `effect_class` stays ours.
- `ToolExposure` (`core/foundation/tool/exposure.py:14`): as is, in `ext.openjiuwen.exposure`.
- `capsule-openjiuwen/merged/capsule.schema.json` `$defs`: the starting shapes, renamed.
