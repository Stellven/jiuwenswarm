---
type: schema
id: cc.declaration.v1
status: proposed
tags: [capsule, schema]
level: detail
prd: [4.1.1]
---

# Declaration · `cc.declaration.v1`

PRD: 4.1.1

A [capsule](capsule.md#term-capability-capsule) is its Declaration: the contract one capability declares, written by its author. It says what the capability takes, gives, needs, changes and promises. It points at its code by hash and never holds it. It holds no task and no policy. Once admitted it never changes; a change is a new version with its own `decl_hash`. A capsule completes its Declaration rather than failing: see [when a call goes wrong](capsule.md#when-a-call-goes-wrong-proposed) (proposed, INV-19).

This is the only page that defines the Declaration's fields. The [schemas](../schemas/schemas.md) folder holds the records the system keeps *about* capsules, such as [Candidates](../schemas/candidate.md#term-candidate), [Verdicts](../schemas/verdict.md#term-verdict) and [Observations](../schemas/observation.md#term-observation).

The **M1** and **Unlocks** columns are defined on [checked and unchecked at M1](stages.md). The [CC tooling and field-enforcement map](tools.md#field-validation-and-enforcement-map) distinguishes schema/admission validation from test-time verification and call-time enforcement; this page remains the sole home of field definitions. The type grammar is in the [invariants](../schemas/invariants.md).

## Frozen M1 field policy

The October 2 PRD whitelist is the runtime boundary. Required named ports, capability identity, hashed local implementation, dependency closure, checks, time budget, permission/effect [boundaries](../system/modules.md#term-boundary), and explicit [RSI](../rsi.md#term-rsi) permission are enforced. Remote/members/composite carriers, live selection/ranking, token or money enforcement, installs during a run, automatic repair and promotion remain inactive future fields even when parsable for archival compatibility. Freeze rejects an attempt to activate them as `M1_FEATURE_DISABLED`. Future-field presence cannot grant authority. Foundational model selection belongs to Model Routing, never Declaration capability selection. Released schema versions are immutable; coordinated drafts may be revised before release. Each `failure_modes` entry adds verification cost and is justified only by an enforceable hazard not already represented by a type, check, effect or standard runner error.

A field serves one or more of four uses:

- **[Verification](../schemas/verification-record.md#term-verification):** the code that [runs](../system/lifecycle.md#term-run) is the code that was tested, and outputs keep their promises.
- **RSI** (recursive self-improvement): build a new version from evidence.
- **Selection:** choose a capsule for a call.
- **Observability:** explain afterwards what ran, why and at what cost.

**Rules:** INV-7 (no task), INV-9 (every output has a check), INV-14 (strict core), INV-17 (the policy decides what is required), INV-19 (economical optional failure contracts). See [invariants](../schemas/invariants.md).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-declaration"></a>**Declaration** (also: Declarations) | The contract one capability declares: what it takes, gives, needs, changes and promises, and what RSI may change. It points at its code by hash, holds no task and no policy, and never changes once admitted; a change is a new version with its own `decl_hash`. |
| <a id="term-port"></a>**port** (also: ports) | One named input or output of a capsule, with a port type. The runner validates each value by its port type, and every output port names a check. |
| <a id="term-needs"></a>**needs** | The Declaration section for what must hold before a call and what the capsule uses: preconditions, dependencies on other capsules, network, packages, secrets and resources. |
| <a id="term-effect-class"></a>**effect class** (also: effect_class) | The author's promise about state and undo: `pure`, `read_only`, `idempotent`, `compensable`, `nonrepeatable_effect` or `irreversible`. Admission checks it against `effects`, and policy mappings turn it into permissions. |
| <a id="term-effects"></a>**effects** | The list of changes a capsule makes to the world, each with the resource it touches, its scope, whether it is idempotent and whether it can be undone. Admission checks that they agree with the effect class. |
| <a id="term-guarantees"></a>**guarantees** | The Declaration section for what a capsule promises: its checks, optional failure modes and an optional quality target. |
| <a id="term-check"></a>**check** (also: checks) | One runnable test of one target (a port or a type), anchored as `deterministic` (code), `reference` (a known answer) or `judged` (a model or person). The same shape serves capsules, port types and call sites. |
| <a id="term-rubric"></a>**rubric** | The pinned criteria text or code behind a judged check. The model-backed judge scores outputs against it, and the Binding names that judge in `verifier`. |
| <a id="term-evolution"></a>**evolution** | The Declaration section that says whether RSI may build new versions of this capsule (`rsi`: none, propose or submit) and which parts it may change (`may_change`). |
| <a id="term-may-change"></a>**may_change** | The list of Declaration field paths or `files:` globs that an RSI child may change; everything else must stay as in the parent. Absent or empty means RSI may change nothing. |
| <a id="term-carrier"></a>**carrier** | The single code file, hashed, that a capsule points at by path and symbol, used when the code imports no unpinned local module. Otherwise the Declaration uses a `body`. |
| <a id="term-body"></a>**body** | The list of every file of a multi-file capability (such as a skill folder), each hashed. It is used instead of a `carrier` when more than one file makes up the code. |
| <a id="term-singleton"></a>**singleton** | The most common capsule form: one capability as a one-node graph whose node is its own code. A composite capsule is a graph of capsules instead. |
| <a id="term-lineage"></a>**lineage** | Where a version came from: its parent's `decl_hash` and how it relates to it (supersedes, specialises, merges, migrated_from). It forms the version tree RSI branches from. |
| <a id="term-decl-hash"></a>**decl_hash** | The hash of the whole Declaration with every default filled in, computed by admission. It is the capsule's identity and version; there is no version number, and every record about a capsule names it. |
| <a id="term-interface-hash"></a>**interface_hash** | The hash of only what a test depends on (name, kind, ports, preconditions, effect class and each check's identity). A child with the same interface hash reuses its parent's tests. |
| <a id="term-code-sha256"></a>**code_sha256** | The hash of a capsule's code that the loader checks before every call: the carrier hash, the hash of the sorted body list, or the hash of the pinned remote or members. |

## Fields

Authored JSON. It carries `schema_version` and `ext` (extensions, such as agent-core settings) from [common](../schemas/common.md); the rest of the envelope belongs to the [Candidate](../schemas/candidate.md) that submits it.

### identity: what it is, and which code

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `identity.name` | `string` | req | checked |  | A stable dot-separated handle, local to a library; `decl_hash` is the global identity. Every version hangs off it, the Standing is keyed by it, and Observations group by it. Example: `doc.pdf_to_text` |
| `identity.namespace` | `string` | opt | unchecked | store, importer | The publisher the name belongs to, when a capsule moves between libraries. Example: `org.example` |
| `identity.kind` | `reg(capsule_kind)` | req | checked |  | How the capability runs, a `capsule_kind` value; see [kinds](capsule.md#kinds-of-capsule). The runner calls each [kind](capsule.md#term-capsule-kind) its own way, and admission tests it that way. Example: `tool` |
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
| `identity` responsible-party key (spelled in the [declaration schema](../exports/schemas/records/declaration.schema.json)) | `string` | opt | unchecked | store | Who answers for the capability now. Example: `team-docs` |
| `identity.tags` | `list<string>` | opt | unchecked | store, selection | Free labels for search. Example: `["documents"]` |
| `identity.license` | `string` | opt | unchecked | importer, store | An SPDX licence id for imported code. Example: `Apache-2.0` |
| `identity.summary` | `text` | req | checked |  | At most 400 characters on what it does: the only prose a model sees when choosing a capsule. Names no step, workflow or other capsule (INV-7). Example: `Extract the plain text of a PDF, page by page.` |
| `identity.lineage` | `object` | opt | checked |  | Where this version came from: the version tree RSI branches from. Merges make it a graph. A child with the same `interface_hash` must also pass its parent's suites ([checks](../schemas/checks.md)) |
| `identity.lineage.parent_hash` | `sha256` | req | checked |  | The parent version's `decl_hash` |
| `identity.lineage.relation` | `enum(supersedes, specialises, merges, migrated_from)` | req | checked |  | How it relates to its parent. `supersedes`: a new version under the same name. `specialises`: a branch under a new name. `merges`: joins `co_parent_hashes` into it. `migrated_from`: the same capability rewritten for a new schema or runtime. A rollback is a Standing move, not a new version |
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
| `needs.external[].purpose` | `text` | opt | unchecked | RSI | What the dependency is for, in a sentence. RSI may re-pin it to a newer version only when it has a purpose and `evolution.may_change` lists its pin, `needs.external[<ref>].decl_hash` ([RSI](rsi.md)). Knowing a dependency's purpose is what lets a builder repair a capsule when the dependency changes. Read by builders as data, never as instructions. Example: `OCR for scanned pages` |
| `needs.network` | `enum(none, egress, ingress, both)` | opt | checked |  | The network access it needs. Default `none`. Where a permission check or the sandbox runs, it allows only this |
| `needs.human_interaction` | `enum(none, optional, blocking)` | opt | checked |  | Whether a call may call back to a person while running, not whether the call itself needs approval to start (that is `changes.effect_class: ASK`). Default `none`. `optional`: may ask, but finishes within its budget without an answer. `blocking`: waits on an answer and can halt everything scheduled after it. Selection reads it before a [Binding](../schemas/binding.md#term-binding) exists, so a `blocking` capsule is not batched into parallel work |
| `needs.dependencies` | `object` | opt | unchecked | importer, isolated verification | What must be installed to run it in isolation |
| `needs.dependencies.runtime` | `string` | req | unchecked | importer, isolated verification | Language and runtime version. Example: `python>=3.11` |
| `needs.dependencies.platforms` | `list<string>` | opt | unchecked | importer, isolated verification | Platforms it runs on. Example: `["linux/amd64"]` |
| `needs.dependencies.packages` | `list<object>` | opt | unchecked | importer, isolated verification | The direct packages, each `{name, version, source, purpose}`, every one pinned by the lockfile. `purpose` is optional and means what it does in `needs.external`: RSI may re-pin the package only when it has a purpose and `evolution.may_change` lists its version. Example: `{"name": "pydantic", "version": "2.9.2", "source": "pypi", "purpose": "validates port values"}` |
| `needs.dependencies.lockfile` | `object` | opt | unchecked | importer, isolated verification | `{uri, sha256}` of a lockfile that pins every package, including indirect ones. Required when `packages` is set (rule `dependencies_pinned`). Example: `{"uri": "uv.lock", "sha256": "..."}` |
| `needs.config` | `object` | opt | unchecked | importer, isolated verification | Settings fixed when the capability is installed or started, which are not ports. Secrets go in `needs.secrets` |
| `needs.config.args` | `map<string, json>` | opt | unchecked | importer, isolated verification | Start-up arguments. Example: `{"max_pages": 500}` |
| `needs.config.env` | `map<string, string>` | opt | unchecked | importer, isolated verification | Environment variables that are not secrets. Example: `{"LANG": "C.UTF-8"}` |
| `needs.secrets` | `list<object>` | opt | unchecked | isolated verification | Credentials it needs, by name only, never values: each `{name, purpose}`. The sandbox injects them and the permission check allows them. Example: `{"name": "GITHUB_TOKEN", "purpose": "read private repos"}` |
| `needs.resources` | `object` | opt | checked |  | What one call needs to run: `{cpu, gpu, memory_mb, disk_mb, timeout_s}`, each optional. At M1 only `timeout_s` is read: it sets the call's time budget, within the policy's cap; the rest wait for isolated verification. Example: `{"memory_mb": 2048, "timeout_s": 120}` |

CC does not schedule pacing or cooldowns between calls to the same capsule. A capsule with its own internal queue or single-process bottleneck should declare `timeout_s` generously instead, so the budget already accounts for time spent waiting on its own backend. That waiting is the capsule's own implementation's job, the same way choosing a model is: not something the schema layer sees or manages.

**Models are not selected by the capsule layer.** Capability selection chooses the work contract. Model Routing is an ordinary service that selects endpoint/model configuration for the authorized call role and records its decision; it is not an admitted router capsule. Production uses the fixed Codex route, isolated experiments use only approved or mocked routes, and RSI [freezes](../system/lifecycle.md#term-freeze) parent/child model settings for comparison. Capsule prompts cannot override endpoint credentials, route policy or model budget. The run configuration and audit evidence pin the effective route separately from capability identity ([model routing](../model-routing/README.md)). Which execution role invokes a capability belongs to orchestration/Binding, not Declaration.

### changes: what it does to the world

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `changes.effect_class` | `enum(pure, read_only, idempotent, compensable, nonrepeatable_effect, irreversible)` | req | checked |  | The author's promise about state and undo. Admission checks it against `effects`. `nonrepeatable_effect` denotes a policy-authorized bounded empirical execution whose observations cannot be recreated by transport replay; it grants neither generic irreversible effects nor automatic retries. Pinned policy and reserved dispatch authorize the first execution, and explicit human-reviewed restart allocates a new attempt. Retries, parallelism and permissions follow policy `mappings` |
| `changes.effects` | `list<object>` | opt | checked |  | Each effect on the world. Admission checks they agree with `effect_class` |
| `changes.effects[].resource_key` | `string` | req | checked |  | What it touches. Example: `fs:workspace/out/*` |
| `changes.effects[].scope` | `string` | req | checked |  | How far it reaches. Example: `run` |
| `changes.effects[].idempotent` | `boolean` | req | checked |  | Whether doing it twice equals doing it once |
| `changes.effects[].reversibility` | `enum(none, compensable, reversible)` | req | checked |  | Whether and how it can be undone: `none`, by a compensating action, or by restoring the prior state |
| `changes.effects[].undo` | `text` | opt | checked |  | How to undo it, applied by a person or a later tool, or a statement that it cannot be undone |
| `changes.state_kind` | `enum(none, reads_external, session, persistent)` | opt | checked |  | Which outside state it depends on. Default `none`. `reads_external` capsules ship [fixtures](../system/test-surfaces.md#term-fixture) with their tests, so the tests do not depend on the outside world |

### guarantees: what it promises

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `guarantees.checks` | `list<Check>` | req | checked |  | Every promise, each a [check](#checks-one-runnable-test-each); at least one |
| `guarantees.failure_modes` | `list<object>` | opt | unchecked | verification, triage | Optional, economical hazards that the runner or [Gate](../verification.md#term-gate) must prevent or classify and that are not already implied by a type, check, permission, effect or standard runner error. Every entry creates a verification obligation. Omitting a derived or unreachable mode is preferred. The runner records a declared capsule-raised mode as `outcome: error` |
| `guarantees.failure_modes[].reason_code` | `string` | req | unchecked | retries, fallbacks, RSI | `UPPER_SNAKE`, unique within the capsule, and not a `reason_code` registry value. Additive: a later version never drops an admitted code. Example: `PDF_ENCRYPTED` |
| `guarantees.failure_modes[].when` | `text` | req | unchecked | retries, fallbacks, RSI | When it happens. Example: `The PDF is password-protected.` |
| `guarantees.failure_modes[].retriable` | `boolean` | req | unchecked | triage | Author evidence only; the pinned [RetryProfile](../schemas/profiles.md#term-retryprofile) and operation class own whether the supervisor may retry. This flag never authorizes replay |
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
| `Check.applies_at` | `enum(admission, node, both)` | req | checked |  | `admission`: needs a [test case](../schemas/checks.md#term-test-case)'s `expected`, so runs only at admission. `node`: needs only the output, so runs at the gate after a call in a run, and at admission on test-call outputs. `both`: each |
| `Check.runner` | `object` | req | checked |  | The pinned code that runs it. For a judged check, the rubric code; the model-backed judge is the Binding's `verifier` |
| `Check.runner.ref` | `string` | req | checked |  | A module path or evaluator id. Example: `checks/text.py:not_empty` |
| `Check.runner.sha256` | `sha256` | req | checked |  | The runner's hash; every result names it |
| `Check.description` | `text` | req | checked |  | What passes, in one line. Example: `The text has a non-space character.` |
| `Check.author` | `string` | req | checked |  | Who wrote it; for a certifying check, not the builder (INV-10). Example: `reviewer-1` |


### composition: capsules made of capsules

Every capsule is a graph of capsules. A **singleton**, the most common form, is a one-node graph whose node is its own code. A composite lists its [nodes](../system/nodes.md#term-node) in `members` and its edges in `wiring`. A sequence, a fan-out and a tree are all just wirings, so there is no field for the shape. See [composition](future-state.md#composition).

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `members` | `list<object>` | opt | unchecked | composer | The nodes of the graph: the capsules it is made of, each pinned. Set instead of `carrier`, `body` or `remote` |
| `members[].id` | `string` | req | unchecked | composer | The member's local name, used in `wiring`. Example: `ocr` |
| `members[].decl_hash` | `sha256` | req | unchecked | composer | The member version. Its own `code_sha256` pins its code |
| `wiring` | `list<object>` | opt | unchecked | composer | The edges of the graph, which also give the order. Required with `members`. Each `{from, to}`: `inputs.<port>` or `<member>.outputs.<port>` into `<member>.inputs.<port>` or `outputs.<port>`. Example: `{"from": "inputs.pdf", "to": "ocr.inputs.image"}` |

### evolution: what RSI may change

RSI is opt-in, twice over. `evolution.rsi` says whether RSI may build new versions at all, and `evolution.may_change` lists the only parts it may change. Everything not listed stays fixed. So RSI applies only where the author explicitly allows it. See [RSI](rsi.md).

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `evolution.rsi` | `enum(none, propose, submit)` | req | checked |  | What RSI may do with this capsule. `none`: nothing; RSI may not submit a child of it. `propose`: RSI may submit a child, which admission holds as `admitted_inactive` until a person activates it. `submit`: RSI may submit a child that becomes current when admitted. Either way the child may differ from its parent only where `evolution.may_change` allows. Example: `none` |
| `evolution.may_change` | `list<string>` | opt | checked |  | The only parts an [RSI child](rsi.md#term-parent-and-child) may change; everything else must stay as in the parent. Absent or empty: RSI may change nothing, whatever `evolution.rsi` says. Each entry is a Declaration field path, with `[]` for every item of a list and `[<name>]` for one keyed item (such as `needs.external[op.ocr].decl_hash` or `guarantees.checks[text_not_empty].runner`), or `files:<glob>` for code or skill files relative to the capsule root (such as `files:SKILL.md`). Values that follow from an allowed change (file hashes, the computed hashes, `identity.lineage`) may change with it. Never lists `evolution` itself (rule `rsi_cannot_grant`). Example: `["files:pdf_text.py"]` |
| `evolution.notes` | `text` | opt | unchecked | RSI | What the author wants a builder to know: weak spots, ideas, why the listed parts are open. Advice only, never a permission |

Reserved names, not specified: `changes.provides[]`, `changes.invariants[]`, `needs.injects[]`.

## Computed by admission, never written by the author

All three are checked at M1.

- **`decl_hash`**: the hash (INV-15) of the whole Declaration **with every default filled in**. Each optional field whose description names a default (such as `Port.required: true`) is written out before hashing, so an explicit and an implicit default give the same hash. Only v1.0 defaults are filled in (INV-16). It is the capsule's identity and version; there is no version number. Every record about a capsule names it.
- **`interface_hash`**: the hash of what a test depends on, and nothing else, with v1.0 defaults filled in as for `decl_hash`: `identity.name`, `identity.kind`, `ports` without `description`s, `needs.when`, `changes.effect_class`, and each check's `id`, `target`, `anchor` and `applies_at`. Moving a file, editing the summary or updating a check's runner leaves it unchanged, so the tests still apply, and a child with the same interface reuses its parent's tests. `guarantees.failure_modes` is included because adding or removing an externally observable failure changes the verification contract.
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
  "evolution": {"rsi": "propose", "may_change": ["files:pdf_text.py"]}
}
```

For a larger, real capsule with more of the optional fields filled in, `failure_modes` and what is computed rather than authored, see [the intent capsule](../capabilities/intent-compile.md).

## Elsewhere, not in the Declaration

- **Measured, never authored:** cost, latency and pass rate come from Observations, recorded in a [Finding](../schemas/finding.md) of kind `measurement` (unchecked: librarian, RSI).
- **In the policy:** required fields per epoch (`required`), predicate `on_unknown` and `max_age_s` (`defaults`), what a level needs (`levels`), effect class to permissions (`mappings`).
- **In the Verdict:** exemption (`level: exempt`). **In the Binding:** budget, overlays, and which role runs the capsule. **In the Candidate:** provenance, builder evidence, test aids. **In a test case:** `fixtures`, which reset outside state.

## Reuse

- `CapabilityDescriptor`, `CapabilityIO` (agent-core `symphony/models/capability.py:15`, `:61`): port names as there; `value_schema` travels in `CapabilityIO.metadata`.
- `ToolCard` flags (`core/foundation/tool/base.py:92-119`) and `PermissionLevel` (`harness/security/permission_engine/models.py:19`): as is, as what `effect_class` maps to. Three booleans cannot hold all effect classes, so `effect_class` stays ours.
- `ToolExposure` (`core/foundation/tool/exposure.py:14`): as is, in `ext.openjiuwen.exposure`.
- `capsule-openjiuwen/merged/capsule.schema.json` `$defs`: the starting shapes, renamed.
