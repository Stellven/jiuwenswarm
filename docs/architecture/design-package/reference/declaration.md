# Capability capsule declaration

`Tier 3 · Part of: [Reference](README.md)`

Purpose: the machine-readable contract of one CC version. It says what the CC takes, what it produces, what it needs, what it may change, how it can be checked and what RSI may change in it ([D34](../method/decisions.md#d34)). [2. Capability Capsules](../2-capability-capsules.md) explains why CCs declare first. [Library and checking](../capability-capsules/library-and-checking.md) explains admission and lifecycle, and [authoring](../capability-capsules/authoring.md) explains how a CC is written.

`capsule-declaration` (exact [schema](schemas/capsule-declaration.schema.json), version 1.0.0) · Producer: the CC author or importer. For an RSI child, the RSI workbench packager. Consumers: library admission, library snapshot, Planner (through the snapshot), binder, CC runner, Verifier CC, RSI workbench.

A declaration describes a reusable capability and its pinned implementation, never a task or a run. The node objective, artifact bindings, effective permissions, verifier assignment and release decision live in protected runtime records. A declaration grants no permission. The runner allows only what the declaration, the node contract and the run policy all allow.

The mandatory check bundle of a CC version is a separate library record, not a declaration field. `guarantees.checks[]`, port `check_ids` and invariant `check_id` values are the author's claims and coverage links. They do not choose, weaken or replace the bundle. Protected admission pins the bundle to the exact version.

The schema is the machine mirror of this page. It is closed: a field outside it is rejected. Admission adds the semantic checks in [host checks](#host-checks).

## M1 status

Every field below has an M1 status.

| Value | Meaning |
|---|---|
| `checked` | Admission validates the field, and an M1 component uses it |
| `accepted-unused` | The schema accepts the field and admission stores it. No M1 component acts on it, and nobody reads it as a promise |
| `rejected-in-M1` | Admission or binding refuses a declaration that uses the field or value in M1 |

## Root fields

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | `checked` | Format version. Reject any other value. |
| `identity` | `Identity` | yes | see [identity](#identity) | `checked` | Who the CC is and which code it pins. |
| `ports` | `Ports` | yes | see [ports](#ports) | `checked` | Typed inputs and outputs. |
| `needs` | `Needs` | yes | see [needs](#needs) | `checked` | What must be available before it runs. |
| `changes` | `Changes` | yes | see [changes and effects](#changes-and-effects) | `checked` | What it may change, and how each change can be undone. |
| `guarantees` | `Guarantees` | yes | see [guarantees](#guarantees) | `checked` | The author's claimed checks. Claims only. |
| `budget` | `Budget` | yes | see [budget](#budget) | `checked` | Per-call limits and how each is enforced. |
| `members` | `Member[]` | no | composite only | `rejected-in-M1` | Pinned member CCs of a composite. See [composition](#composition-reserved). |
| `structure` | `Structure` | no | composite only | `rejected-in-M1` | Internal graph of a composite. |
| `wiring` | `Wire[]` | no | composite only | `rejected-in-M1` | Port connections of a composite. |
| `evolution` | `Evolution` | yes | see [evolution](#evolution-what-rsi-may-change) | `checked` | Whether RSI may build a child of this CC, which parts it may change, and builder notes. |
| `coverage` | `Coverage` | yes | see [coverage](#coverage) | `checked` | What the declaration deliberately leaves out. |
| `ext` | `object` | no | keys match `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$` | `accepted-unused` | Namespaced diagnostic data, written by the CC author or importer. Consumers may ignore it. It never changes meaning, permission, acceptance or any gate decision, and no M1 component acts on it. |

Required groups are always present. An empty list means "not applicable" and is written explicitly. An optional field that does not apply is left out.

## Identity

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `identity.name` | `string` | yes | at least 1 character. The library pins it with pattern `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$` | `checked` | Stable dotted name, for example `research.screening`, chosen by the author. Every version of one capability shares it, and an RSI child never changes it (always-protected set). |
| `identity.version_label` | `string` | yes | at least 1 character. The library pins it with pattern `^[a-z0-9][a-z0-9._-]{0,31}$`. Unique per name | `checked` | Implementation label, a display value only: it never identifies content (the exact identity is `declaration_sha256`, see the hashing profile). A changed body needs a new label. The workbench packager sets it for an RSI child. |
| `identity.kind` | `string` | yes | enum, see [kind](#enum-identitykind) | `checked` | Execution style. M1 admits `agent` and `tool`. |
| `identity.summary` | `string` | yes | 1 to 400 characters | `checked` | Task-independent purpose, written by the author. It describes the capability, never a task or a run. The Planner reads it with the ports. |
| `identity.carrier` | `CodePin` | yes for `agent` and `tool` | absent for a composite. Exactly one of `carrier` with `body`, or `remote` | `checked` | Entry point the runner loads. |
| `identity.body` | `BodyFile[]` | yes for `agent` and `tool` | at least 1 item, paths unique | `checked` | Every implementation file, each with its own digest. |
| `identity.remote` | `RemotePin` | no | only without `carrier` and `body` | `rejected-in-M1` | Pinned remote interface of an MCP or A2A capability. |
| `identity.load_mode` | `string` | no | enum `invoked`, `context_injected`. Absent means `invoked` | `checked` for `invoked`. `context_injected` is `rejected-in-M1` | How the runner loads the CC. |
| `identity.overlays` | `Overlay[]` | no | each overlay pinned by hash | `accepted-unused`. A non-empty list fails binding, because no M1 runner supports overlays | Experience or prompt layers loaded with the CC. |
| `identity.lineage` | `Lineage` | no. Required for every RSI child | see [lineage](#lineage) | `checked` | Parent version and how this version was built. For an RSI child the workbench packager writes it once, and the RSI proposer never writes it. |

**CodePin**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `ref` | `string` | yes | at least 1 character | `checked` | ID the loader resolves, for example a module path. |
| `sha256` | `sha256` | yes | 64 lowercase hex characters, the digest of the exact bytes | `checked` | What `ref` must hash to at load. A mismatch aborts the load. |

**BodyFile**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `path` | `string` | yes | at least 1 character, relative to the CC root | `checked` | Implementation file. |
| `sha256` | `sha256` | yes | digest of the exact file bytes | `checked` | Pins that one file. |

**RemotePin**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `endpoint` | `string` | yes | at least 1 character | `rejected-in-M1` | Remote endpoint. |
| `version` | `string` | yes | at least 1 character | `rejected-in-M1` | Remote version. |
| `interface_version_range` | `string` | yes | at least 1 character | `rejected-in-M1` | Interface versions the CC accepts. |
| `fingerprint` | `sha256` | yes | 64 lowercase hex characters | `rejected-in-M1` | Digest of the remote interface description. |

**Overlay**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `kind` | `string` | yes | at least 1 character | `accepted-unused` | Overlay kind, for example a prompt section. |
| `ref` | `string` | yes | at least 1 character | `accepted-unused` | Overlay ID. |
| `sha256` | `sha256` | yes | digest of the overlay bytes | `accepted-unused` | Pins the overlay. |
| `source` | `string` | yes | at least 1 character | `accepted-unused` | Where the overlay came from. |

### Enum `identity.kind`

| Value | Meaning | M1 status |
|---|---|---|
| `agent` | Bounded model calls through the model bridge | `checked` |
| `tool` | Pinned code the CC runner runs | `checked` |
| `skill` | Instructions loaded into an agent's context | `rejected-in-M1` |
| `prompt` | A prompt section used by another CC | `rejected-in-M1` |
| `subagent` | A delegated agent run with its own context | `rejected-in-M1` |
| `mcp` | A remote MCP tool | `rejected-in-M1` |
| `a2a` | A remote A2A agent | `rejected-in-M1` |
| `composite` | A graph of other CCs | `rejected-in-M1`. Reserved for December |

### Enum `identity.load_mode`

| Value | Meaning | M1 status |
|---|---|---|
| `invoked` | The CC runs behind a boundary, with its own call and record | `checked` |
| `context_injected` | The CC shares an agent's context. Its calls cannot be told apart | `rejected-in-M1` |

## Ports

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `ports.inputs` | `Port[]` | yes | 0 to 16 items, names unique | `checked` | Inputs the CC reads. |
| `ports.outputs` | `Port[]` | yes | 1 to 16 items, names unique | `checked` | Outputs the CC writes. Every output gets its own verifier call and gate decision. |

**Port**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$` in the library | `checked` | Port name. |
| `artifact_type` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$` in the library | `checked` | Artifact type that flows through the port, for example `candidate_set`. |
| `schema_ref` | `string` | yes | a schema URN, a field-contract ID or the reserved `opaque-bytes` | `checked` | Exact contract of the port content. Two ports connect only when `artifact_type` and `schema_ref` are equal. |
| `required` | `boolean` | yes | none | `checked` | Whether the CC needs this input, or always writes this output. |
| `description` | `string` | yes | at least 1 character | `checked` | Plain description. The Planner reads it. |
| `check_ids` | `string[]` | yes | may be empty. Each ID is defined on the CC's build page | `checked` | Checks the author links to this port. A link, not the check bundle. |

## Needs

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `needs.when` | `Predicate[]` | yes | may be empty | `checked`. A non-empty list is `rejected-in-M1`, because no M1 component evaluates predicates and an unevaluated predicate must never pass | Preconditions as predicates. |
| `needs.external` | `External[]` | yes | may be empty. Each item has exactly one of `pin` and `floating` | `checked` | Packages, data, models, services or CCs the CC depends on. |
| `needs.network` | `Network` | yes | see the rule below | `checked` | Network authorization and direction. |
| `needs.resources` | `ResourceUse[]` | yes | may be empty, keys unique | `checked` | Resources the CC uses, by inventory key. |
| `needs.injects` | `Inject[]` | yes | may be empty | `checked` | Services the host injects. M1 injects only `audited_model_bridge`. |
| `needs.model` | `ModelNeeds` | no. Present when `injects` holds the model bridge | none | `checked` | What the model must support. It never names a model. |
| `needs.secrets` | `Secret[]` | no | 0 to 16 items, names unique | `checked` | Credentials the CC needs, by name only. See [secrets](#secrets). |
| `needs.human_interaction` | `string` | no | enum `none`, `optional`, `blocking`. Absent means `none` | `none` is `checked`. `optional` and `blocking` are `rejected-in-M1` | Whether a call may ask a person while it runs. Reserved: a headless run never waits for a person ([D10](../method/decisions.md)). |

**Predicate**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `id` | `string` | yes | at least 1 character | `rejected-in-M1` | Predicate ID. |
| `check` | `PredicateCheck` | yes | `{path, operator, value}`, `path` and `operator` required | `rejected-in-M1` | What to test, for example `path` `resource.gpu.count`, `operator` `ge`, `value` 1. |
| `state_source` | `string` | yes | at least 1 character | `rejected-in-M1` | Where the state comes from. |
| `evaluable_at` | `string` | yes | enum `planning`, `dispatch`, `both` | `rejected-in-M1` | When it can be evaluated. |
| `max_age_s` | `integer` | no | min 0 | `rejected-in-M1` | Oldest state it accepts. |
| `on_unknown` | `string` | yes | enum `block`, `defer_to_dispatch` | `rejected-in-M1` | What to do when the state is unknown. Unknown never passes. |
| `on_unavailable` | `string` | yes | exactly `block` | `rejected-in-M1` | What to do when the state cannot be read. |
| `parity_check` | `Ref` | no | none | `rejected-in-M1` | Test that planning and dispatch evaluate alike. |

**External**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `kind` | `string` | yes | at least 1 character | `checked` | Dependency kind, for example `package`, `dataset`, `operator`. Kind `package` needs a `pin` and a `lockfile`. |
| `identifier` | `string` | yes | at least 1 character | `checked` | Dependency name. |
| `pin` | `CodePin` | one of `pin`, `floating` | digest of the dependency bytes | `checked` | Captured, pinned dependency. Part of the closure admission checks. |
| `floating` | `FloatingNeed` | one of `pin`, `floating` | `{purpose, role, contracts}`, `contracts` at least 1 item | `checked` | A dependency chosen later. It must resolve to a pin under policy before dispatch, or the node halts. Never allowed for kind `package`. |
| `purpose` | `string` | no | at least 1 character, only with `pin` | `accepted-unused` | What the dependency is for, in one sentence. A builder reads it as data, never as an instruction. RSI re-pinning of a dependency is later work. |
| `lockfile` | `CodePin` | yes for kind `package`, absent otherwise | `ref` names the lockfile, `sha256` is the digest of its exact bytes | `checked` | Lockfile that pins the package and every indirect package it brings. |

Rule `dependencies_pinned`: every external dependency of kind `package` has a `pin` and a `lockfile`, and no other kind has a `lockfile`. A package never floats. Admission captures the lockfile bytes with the rest of the closure.

**Secret**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[A-Z][A-Z0-9_]{0,63}$`, unique in the declaration, on the admission allowlist | `checked` | Name of the credential. Never its value. |
| `purpose` | `string` | yes | at least 1 character | `accepted-unused` | What the credential is used for. |

### Secrets

A declaration names the secrets a CC needs and never holds a value. Rule `secrets_allowed`: every name is on the admission allowlist, which the operator sets and M1 ships empty. The CC runner injects each value at call time. A value never appears in a declaration, an output, a record or a log.

**Network**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `mode` | `string` | yes | enum, see below | `checked` | What the CC is authorized to reach. |
| `direction` | `string` | yes | enum, see below | `checked` | Which way traffic flows. Never inferred from `mode`. |
| `allowlist` | `string[]` | yes | empty when `mode` is `none`. At least 1 host when `mode` is `allowlist` | `checked` | Hosts the CC may reach. |

Rule `network_consistent`: `mode` `none` needs `direction` `none` and an empty allowlist. `mode` `allowlist` needs `direction` `egress` and a non-empty allowlist. An injected bridge never grants direct network access.

| `mode` value | Meaning | M1 status |
|---|---|---|
| `none` | No network access | `checked` |
| `allowlist` | Only the listed hosts | `checked` |
| `open` | Any host | `rejected-in-M1` |

| `direction` value | Meaning | M1 status |
|---|---|---|
| `none` | No traffic | `checked` |
| `egress` | Outgoing requests only | `checked` |
| `ingress` | Incoming connections only | `rejected-in-M1` |
| `both` | Incoming and outgoing | `rejected-in-M1` |

**ResourceUse**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `resource_key` | `string` | yes | a resource inventory key | `checked` | Resource the CC uses. |
| `mode` | `string` | yes | enum `read` (reads only), `write` (changes it), `exclusive` (no other node may use it during the attempt) | `checked` | How the CC uses it. The library snapshot copies it. |

**Inject**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `service_key` | `string` | yes | at least 1 character. M1 injects only `audited_model_bridge` | `checked` | Service the host provides. |
| `interface_version_range` | `string` | yes | at least 1 character, for example `1.x` | `checked` | Interface versions the CC accepts. |

**ModelNeeds**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `tool_calling` | `boolean` | yes | none | `checked` | Whether the model must support tool calls. |
| `modalities` | `string[]` | yes | at least 1 item, for example `text` | `checked` | Input and output modalities the model must support. |
| `min_context` | `integer` | no | min 0 | `checked` | Smallest context window, in tokens. |
| `families` | `string[]` | no | may be empty | `checked` | Model families that fit. The router reads it. |
| `excludes` | `string[]` | no | may be empty | `checked` | Model families that must not be used. |

## Changes and effects

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `changes.effect_class` | `string` | yes | enum, see below | `checked` | The author's class for the whole CC. The plan policy filters on it. It is never weaker than the effects imply, and admission rejects a weaker class (`effect_class_matches_effects`). |
| `changes.effects` | `Effect[]` | yes | empty only when the CC changes nothing | `checked` | Each change the CC may make. |
| `changes.provides` | `ProvidedService[]` | yes | may be empty | `accepted-unused` | Services the CC offers to other CCs. |
| `changes.invariants` | `Invariant[]` | yes | may be empty | `accepted-unused` | Statements the CC keeps true, each linked to a check. |

**Effect**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `id` | `string` | yes | at least 1 character, unique in the declaration | `checked` | Effect ID. |
| `resource_key` | `string` | yes | at least 1 character | `checked` | What the effect touches. |
| `op` | `string` | yes | at least 1 character, for example `model_invoke`, `write`, `network_egress` | `checked` | Operation, in plain words. Descriptive only: admission judges an effect by `resource_key`, `scope`, `reversibility` and `risk`, not by `op`. |
| `scope` | `string` | yes | at least 1 character | `checked` | How far the effect reaches, in the author's words, for example `/workspace/poc/ only`. Written by the CC author. Admission reads it with `resource_key`, `reversibility` and `risk` to judge the effect (`effect_class_matches_effects`). It grants nothing: the runner enforces authority from the binding, never from this text. |
| `idempotent` | `boolean` | yes | none | `checked` | Whether running twice leaves the same state as once. The author's claim. It feeds the `effect_class_matches_effects` check. |
| `reversibility` | `string` | yes | enum, see below | `checked` | Whether and how the effect can be undone. |
| `undo` | `nullable-CodePin` | yes | non-null for `compensate`. Null for `none`, `scoped` and `emission` | `checked` | Pinned code that undoes the effect. |
| `risk` | `Risk` | yes | see below | `checked` | How bad the effect can be. |
| `assurance` | `string` | yes | at least 1 character | `checked` | What the author says enforces the effect's limits, for example the protected bridge. A claim for reviewers. No M1 component decides on it. |

**Risk**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `severity` | `string` | yes | enum, see below | `checked` | Severity class. |
| `blast_radius` | `string` | yes | at least 1 character | `checked` | What the worst case reaches. |
| `irreversibility` | `boolean` | yes | none | `checked` | Whether the worst case cannot be undone. |

**ProvidedService**: `service_key` (`string`, required), `interface_version` (`string`, required), `commutative` (`boolean`, required). All `accepted-unused`.

**Invariant**: `id` (`string`, required), `statement` (`string`, required), `check_id` (`string`, required, a check of the CC's build page). All `accepted-unused`.

### Enum `changes.effect_class`

| Value | Meaning | M1 status |
|---|---|---|
| `pure` | Reads only its inputs and writes only inside its own call scope | `checked` |
| `read_only` | Reads shared or external state, changes nothing | `checked` |
| `idempotent` | Every change is idempotent | `checked` |
| `compensable` | Every change that is not idempotent can be undone or is confined to a discarded scope | `checked` |
| `irreversible` | Anything else, including an emission that is not idempotent | `rejected-in-M1`. The plan policy excludes it |

Rule `effect_class_matches_effects`: the declared class is never weaker than the effects imply. A `model_invoke` effect is a call through the audited model bridge, which enforces its own limits, and it does not raise the class. For every other effect: a repeat-safe (`idempotent`) effect that is not `scoped` needs at least `read_only`. A non-repeat-safe effect that is `scoped`, `inverse` or `compensate` needs at least `compensable`. A non-repeat-safe effect that is `none` or `emission` needs `irreversible`. Class `pure` needs every such effect to be `scoped`. A stronger class than needed is accepted.

### Enum `effects[].reversibility`

| Value | Meaning |
|---|---|
| `none` | The effect cannot be undone, for example a disclosure to a model |
| `scoped` | The effect stays inside a scope the host discards, for example a per-attempt workspace |
| `inverse` | An exact inverse operation restores the state |
| `compensate` | Pinned `undo` code repairs the state. The result may not be identical |
| `emission` | The effect leaves the system, for example a sent message. It cannot be recalled |

### Enum `effects[].risk.severity`

| Value | Meaning | M1 status |
|---|---|---|
| `low` | The worst case affects only the call's own scratch state | `checked` |
| `bounded` | The worst case stays inside the declared scope and blast radius | `checked` |
| `high` | The worst case reaches shared or external state. A named human must approve each use | `rejected-in-M1`. M1 has no per-call approval path |

## Guarantees

The guarantees are the author's claims. The checks that decide are in the check bundle that admission pins.

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `guarantees.checks` | `ClaimedCheck[]` | yes | at least 1 item, IDs unique. Each ID is defined on the CC's build page | `checked` | Checks the author claims cover the CC. Claims and coverage links only: they never choose, weaken or replace the check bundle that admission pins. |
| `guarantees.acceptance` | `string[]` | yes | may be empty. Each is a `checks[].id` | `accepted-unused` | Check IDs the author considers acceptance. |
| `guarantees.evals` | `Eval[]` | yes | may be empty | `accepted-unused` | Evaluation suites with a metric and threshold. |
| `guarantees.unanchored` | `string[]` | yes | may be empty | `checked` | Claims the author cannot back with a check. The verifier reads them as limits. |
| `guarantees.quality` | `QualityTarget` | no | `{criterion, judge, target_rate, window, min_observations}` | `accepted-unused` | A measured quality rate over a window. Below `min_observations` it is unmeasured. |
| `guarantees.exempt` | `Exemption` | no | exactly `{reason: generalist}` | `rejected-in-M1` | Library eligibility exemption for a generalist. Never an exemption from gates. |
| `guarantees.failure_modes` | `FailureMode[]` | no | 0 to 32 items, `reason_code` unique | `checked` for format | The only ways the CC may end without an output. Each reason code needs at least one self-test that expects it (`failure_modes_have_self_tests`). |
| `guarantees.self_tests` | `SelfTest[]` | no | 0 to 64 items, `id` unique | `checked` | Tests the author ships with the CC. Admission runs every one in the confined executor ([D45](../method/decisions.md#d45)). They never replace the check bundle. |

**ClaimedCheck**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `id` | `string` | yes | at least 1 character | `checked` | Check ID. |
| `kind` | `string` | yes | enum, see below | `checked` | How the check decides. |
| `target` | `string` | yes | at least 1 character, for example `outputs.intent` | `checked` | What the check reads. A negative control names the input it must refuse. |
| `runner` | `CodePin` | yes | digest of the runner bytes | `checked` | Pinned check implementation. |
| `anchor` | `string` | yes | at least 1 character | `accepted-unused` | What the check compares against, in plain words. |
| `over` | `string[]` | yes | at least 1 item, each enum `each_call`, `outputs`, `inputs_and_outputs` | `checked` | What the check covers. |
| `author` | `string` | yes | at least 1 character | `checked` | Who wrote the claimed check, in plain words. Written by the CC author. A claim for reviewers. No M1 component decides on it. |
| `written_before_body` | `boolean` | yes | none | `checked` | Whether the check existed before the body. The author's claim. |
| `held_out` | `boolean` | yes | none | `checked` | Whether the body author could see the check. The author's claim. |
| `signal_source` | `string` | yes | at least 1 character | `accepted-unused` | Where the claimed check's signal comes from, in plain words. Accepted and stored, never used in M1: guarantees are claims only. |
| `owner` | `string` | yes | at least 1 character | `accepted-unused` | Who maintains the claimed check, in plain words. Accepted and stored, never used in M1: guarantees are claims only. |
| `assurance` | `string` | yes | at least 1 character | `accepted-unused` | How strong the author says the claimed check is, in plain words. Accepted and stored, never used in M1: guarantees are claims only. |

**FailureMode**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `reason_code` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,63}$`, unique in the declaration | `checked` | Stable code the runner records when the CC ends this way. A later version never drops an admitted code. |
| `when` | `string` | yes | at least 1 character | `checked` | When it happens, in plain words. |
| `retriable` | `boolean` | yes | must be `false` in M1 | `checked` | Whether the same call may succeed if tried again. M1 never retries a failed call ([D4](../method/decisions.md)). |

Rule `failure_modes_valid`: the codes are lowercase snake case and unique, every `when` is non-empty and every `retriable` is `false`. The check reads the format only. It does not prove the CC can fail in that way. The self-tests below do.

**SelfTest**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,63}$`, unique in the declaration | `checked` | Self-test ID. |
| `kind` | `string` | yes | enum `fixture`, `command` | `checked` | `fixture`: `ref` is an input the CC runs on. `command`: `ref` is a pinned script that drives the CC and reports its end state. |
| `ref` | `CodePin` | yes | digest of the exact bytes | `checked` | The pinned fixture or command. |
| `expects` | `string` | yes | `pass`, or a declared `guarantees.failure_modes[].reason_code` | `checked` | The end state the test must see. `pass` means the CC returns its outputs. A reason code means the CC ends without an output and records exactly that code. `pass` is never a failure mode code. |

Rule `failure_modes_have_self_tests`: every declared failure mode is the `expects` of at least one self-test, every `expects` other than `pass` is a declared reason code, and the self-test IDs are unique. Admission also runs every self-test in the confined executor and compares the end state with `expects`. A test that does not meet its expectation rejects the declaration. The platform builds no negative test of its own from a failure mode: the author supplies the self-tests and admission runs them.

**Eval**: `suite_ref` (`Ref`), `metric` (`string`), `threshold` (`number`), `held_out` (`boolean`). All required, all `accepted-unused`.

**QualityTarget**: `criterion` (`string`), `judge` (`Ref`), `target_rate` (`number`, 0 to 1), `window` (`integer`, min 1), `min_observations` (`integer`, min 1). All required, all `accepted-unused`.

### Enum `guarantees.checks[].kind`

| Value | Meaning |
|---|---|
| `deterministic` | A program decides from the bytes, the same way every time. A comparison with a reference answer is deterministic |
| `semantic` | A model or a person judges. The result can vary and needs calibration |

## Budget

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `budget.per_call` | `PerCallBudget` | yes | see below | `checked` | Ceilings for one call. |
| `budget.enforcement` | `object` | yes | keys equal exactly the keys of `per_call`. Each value enum `hard`, `between_calls`, `post_hoc` | `checked` | How each ceiling is enforced. A dimension nobody measures cannot be claimed enforced. |
| `budget.on_exhaust` | `string` | yes | enum `fail`, `return_partial` | `fail` is `checked`. `return_partial` is `rejected-in-M1` | What happens when a ceiling is hit. In M1 the attempt ends `budget_exhausted`. |

**PerCallBudget**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `wall_s` | `number` | yes | above 0 | `checked` | Wall time in seconds. The library copies it into `max_limits.time_s`. |
| `invocations` | `integer` | yes | min 1 | `checked` | Model invocations. The library copies it into `max_limits.model_calls` when the bridge is injected. |
| `tool_calls` | `integer` | no | min 0 | `checked` | Tool calls. |
| `tokens` | `integer` | no | min 0 | `accepted-unused` | Token ceiling. |
| `cost` | `number` | no | min 0 | `accepted-unused` | Cost ceiling. |
| `iterations` | `integer` | no | min 0 | `accepted-unused` | Loop iterations. |

| `enforcement` value | Meaning |
|---|---|
| `hard` | The runner stops the call when the ceiling is reached |
| `between_calls` | The runner checks the ceiling between model or tool calls |
| `post_hoc` | The ceiling is measured after the call and reported. It does not stop the call |

## Composition (reserved)

Composite CCs are reserved for December. M1 admission rejects every field in this section.

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `members` | `Member[]` | composite only | at least 1 item, each `{role, decl_hash}` | `rejected-in-M1` | Member CCs pinned by declaration digest. |
| `structure` | `Structure` | composite only | `{type: dag, direction: forward, nodes, edges}` | `rejected-in-M1` | Finite internal graph. |
| `wiring` | `Wire[]` | composite only | at least 1 item, each `{from, to}` | `rejected-in-M1` | Typed connections between member ports and the composite boundary. |

## Evolution: what RSI may change

RSI is opt-in twice. `evolution.rsi` says whether RSI may build a child of this CC at all. `evolution.may_change` lists the only parts a child may differ in. The author knows which parts are safe to change, so the author decides ([D34](../method/decisions.md#d34)).

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `evolution.rsi` | `string` | yes | enum, see below | `none` and `propose` are `checked`. `submit` is `rejected-in-M1` | What RSI may do with this CC. |
| `evolution.may_change` | `string[]` | no | 0 to 16 unique entries. Each is `files:<glob>` or a JSON pointer (RFC 6901) into this declaration. See the rules below | `checked` | The only parts an RSI child may change. Missing or empty means RSI may change nothing, whatever `evolution.rsi` says. |
| `evolution.notes_for_builder` | `string[]` | yes | may be empty | `accepted-unused` | Advice for whoever builds the next version. Never a guarantee and never a permission. |

### Enum `evolution.rsi`

| Value | Meaning | M1 status |
|---|---|---|
| `none` | RSI may not build a child of this CC | `checked` |
| `propose` | RSI may submit a child; admission stores it `inactive` until a human activates it | `checked` |
| `submit` | RSI may submit a child that becomes current when admitted | `rejected-in-M1`. Admission is manual and a human activates |

### May-change rules

- **Entries.** `files:<glob>` is a path pattern relative to the CC root, for example `files:rank_opportunities.py`. `*` matches any characters except `/`, `**` matches any characters including `/`, and `?` matches one character. A pointer names a part of the declaration. M1 accepts only `files:` entries and the two body pointers `/identity/body` and `/identity/carrier`. The proposer edits body files and never edits the declaration, so a child's declaration changes only in the derived fields below. Any other pointer is rejected (`may_change_entries_valid`).
- **`rsi_cannot_grant`.** `may_change` never lists `/evolution` or anything under it. RSI cannot give itself more rights. Admission rejects such a declaration.
- **`rsi_mode_allowed`.** `submit` is rejected. A verifier CC, and a CC whose output is gate evidence, must have `rsi: none`. The referee never improves itself. The protected role list names them. In M1 it holds `research.verifier`, `research.benchmark` and `research.evaluation`.
- **`changes_allowed`.** A child differs from its parent only inside the parent's `may_change` and in the derived identity fields below. The admission command checks every body file that was added, removed or changed against the `files:` globs. A change anywhere else declares a new capability, not a child. See the [candidate package](rsi-contracts.md#candidate-package).
- **`rsi_no_copy`.** RSI cannot get round `none` by submitting a copy as a child of another CC. Admission rejects a candidate whose body files match a CC whose `rsi` is `none`.
- **`profile_within_may_change`.** The `mutable_paths` of an RSI target profile must all be covered by the `files:` globs of the parent's `may_change`. See the [target profile](rsi-contracts.md#rsi-target-profile).

**Always-protected set.** These pointers can never be listed, and a child never differs from its parent at them:

| Pointer | Why |
|---|---|
| `/ports` | Consumers and plans depend on the port contract |
| `/needs` | Permissions, network and resources are checked against it |
| `/changes` | Effects and their undo are the safety contract |
| `/guarantees` | The claims the checks were written against |
| `/budget` | Plan limits are copied from it |
| `/identity/name` | The name ties all versions of one capability together |
| `/identity/lineage` | Written once by the builder of the version. The RSI proposer never writes it |
| `/evolution` | RSI cannot widen its own rights (`rsi_cannot_grant`) |

**Derived fields.** A child differs from its parent at these pointers whatever `may_change` says, because they follow from a changed body:

| Pointer | Who writes it |
|---|---|
| `/identity/version_label` | The workbench packager, a new label |
| `/identity/carrier` | The workbench packager, the digest of the changed entry point |
| `/identity/body` | The workbench packager, derived from the changed body files |
| `/identity/lineage` | The workbench packager, once, naming the parent (see [lineage](#lineage)) |

The checks, check bundles, checking profiles, referee and hidden fixtures stay outside every CC, so no declaration can widen what RSI may change.

## Lineage

**Lineage**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `parent` | `nullable-Ref` | yes | the parent declaration bytes. Null only for a first version | `checked` | Version this one derives from. |
| `co_parents` | `Ref[]` | yes | may be empty. Must be empty in M1 | `checked` | Further parents of a composed version. |
| `relation` | `string` | yes | enum, see below | `checked` | How this version relates to its parent. |
| `builder` | `string` | yes | at least 1 character. `rsi_workbench` for an RSI child | `checked` | Who or what built the version. |
| `build_trigger` | `string` | yes | at least 1 character. The session ID for an RSI child | `checked` | Why it was built. |
| `context_capsules` | `Ref[]` | yes | may be empty | `accepted-unused` | CCs that were in the builder's context. |
| `diagnosis_inputs` | `Ref[]` | yes | may be empty | `accepted-unused` | Records the builder diagnosed. |
| `builder_ref` | `Ref` | yes | for an RSI child, the final attempt record | `checked` | The builder's own record of this build. |
| `provenance` | `BuildProvenance` | yes | see below | `checked` | Model, prompt and trajectory, or explicit nulls. |

**BuildProvenance**

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `generating_model` | `nullable-string` | yes | null when unavailable | `checked` | Model that generated the change. |
| `prompt_ref` | `nullable-Ref` | yes | null when unavailable | `checked` | Exact prompt or policy. |
| `trajectory_ref` | `nullable-Ref` | yes | null when unavailable | `checked` | Exact proposal trace. |

### Enum `identity.lineage.relation`

| Value | Meaning | M1 status |
|---|---|---|
| `supersedes` | A new version of the same capability. Every RSI child uses it | `checked` |
| `specialises` | A narrower version of the parent | `checked` |
| `rollback_of` | A new version that restores an earlier version's content | `rejected-in-M1`. Rollback is a standing move ([D41](../method/decisions.md#d41)) |
| `migrated_from` | Imported from a historical format | `checked` |
| `composes` | Built from several CCs | `rejected-in-M1` |
| `fuses` | Members merged into one body. Reserved, not implemented | `rejected-in-M1` |

**Rule `rsi_child_has_lineage`.** Every RSI child has `identity.lineage`. `parent` is the Ref of the parent declaration bytes, `relation` is `supersedes` and `builder` is `rsi_workbench`. The admission inbox knows a declaration is an RSI child because it arrives in a [candidate package](rsi-contracts.md#candidate-package). A child without lineage is rejected, and so is any declaration whose relation is `rollback_of`, `composes` or `fuses`. This follows [RSI ruling 10](../side-systems/owner-rulings.md#rsi-v02).

## Coverage

| Field | Type | Required | Constraint | M1 status | Meaning |
|---|---|---|---|---|---|
| `coverage.undeclared_notes` | `string[]` | yes | may be empty | `checked` | What the declaration deliberately leaves out, and why. A missing claim is never read as a promise. The verifier reads it. |

## Hashing profile

One profile for every CC version in M1. It is the profile every [CcPin](run-plan.md#library-snapshot) carries.

- `declaration_sha256` is the SHA-256 of the exact declaration file bytes, as captured at admission. Nothing is parsed, reserialized, key-sorted or normalized first, including line endings and Unicode. One changed byte is a new digest, so a new version.
- Each body file is hashed on its own: `identity.body[].sha256` is the SHA-256 of that file's exact bytes. `identity.carrier.sha256` is the same for the entry point.
- A changed body file changes its body pin, so it changes the declaration bytes and `declaration_sha256`. One digest therefore identifies the declaration and the whole body.
- Every `CcPin {cc_name, cc_version, declaration_sha256}` carries this digest: in the library snapshot, the run plan, the dispatch record, the library admission record, the evaluation profile and the candidate package.
- M1 has no canonical contract hash that leaves out notes. It is reserved for later. Until then a changed note is a new version. An `interface_hash` over only what tests depend on, so that a child with the same interface reuses its parent's tests, is later work.

## Invariants

- A leaf declaration (`agent` or `tool`) has `carrier` and `body` and no `remote`, `members`, `structure` or `wiring`.
- `budget.enforcement` has exactly the keys of `budget.per_call`.
- `evolution.may_change` never lists `/evolution`, and a CC with `rsi` other than `none` is not a verifier or gate-evidence CC.
- An RSI child has lineage that names its parent with relation `supersedes`.
- The body and carrier digests equal the digests of the files as captured.

## Producer obligations

**Author or importer**
- Declare every effect, dependency and resource the body uses. An undeclared effect is treated as `irreversible`.
- Write empty lists explicitly, and say in `coverage.undeclared_notes` what is left out.
- Never name a model. State model needs only.
- Import a historical declaration by an explicit mapping. Never claim byte compatibility with another format.

**RSI workbench packager**
- Derive the child declaration from the parent declaration bytes. Change only the derived identity fields.
- Write lineage once, from the session and the final attempt.

## Host checks

Admission runs these on every declaration, after schema validation.

| Check ID | Rule | Outcome |
|---|---|---|
| `m1_kind_admitted` | `identity.kind` is `agent` or `tool`. No `members`, `structure`, `wiring` or `remote`. `load_mode`, when present, is `invoked` | `rejected` |
| `network_consistent` | The network rule above holds. `mode` is not `open` | `rejected` |
| `rsi_mode_allowed` | `evolution.rsi` is `none` or `propose`. A verifier CC or a CC whose output is gate evidence has `none` | `rejected` |
| `rsi_cannot_grant` | `evolution.may_change` lists neither `/evolution` nor anything under it | `rejected` |
| `may_change_entries_valid` | Each entry is a relative `files:` glob or one of `/identity/body` and `/identity/carrier`. No entry repeats | `rejected` |
| `rsi_child_has_lineage` | An RSI child has lineage with a parent, relation `supersedes` and builder `rsi_workbench`. No declaration uses relation `composes`, `fuses` or `rollback_of` | `rejected` |
| `dependencies_pinned` | Every external dependency of kind `package` has a `pin` and a `lockfile`. No other kind has a `lockfile` | `rejected` |
| `secrets_allowed` | Every `needs.secrets` name is on the admission allowlist and appears once | `rejected` |
| `failure_modes_valid` | Every `guarantees.failure_modes` code is lowercase snake case and unique, every `when` is non-empty and every `retriable` is `false` | `rejected` |
| `failure_modes_have_self_tests` | Every declared failure mode has at least one self-test that expects its reason code. Every `expects` other than `pass` is a declared code. Self-test IDs are unique. Admission runs each self-test in the confined executor and it ends as `expects` says | `rejected` |
| `human_interaction_none` | `needs.human_interaction` is absent or `none` | `rejected` |
| `effect_class_matches_effects` | `changes.effect_class` is not weaker than the effects imply (see [changes and effects](#changes-and-effects)) | `rejected` |
| `body_hashes_match` | Every body file and the carrier hash to their pinned digests | `blocked` when a file is missing, `rejected` when a digest differs |

RSI child admission adds `changes_allowed`, `rsi_no_copy` and `profile_within_may_change`. They run in the admission command and are listed in the [RSI contracts](rsi-contracts.md#candidate-package).

Binding adds two M1 checks: a node whose CC lists overlays fails binding, and a non-empty `needs.when` fails binding.

## Failure outcomes

| Condition | Outcome | What is kept |
|---|---|---|
| Schema validation fails | Admission record `rejected`, standing `inactive` | The declaration and the errors |
| A host check fails | Admission record `rejected` or `blocked`, standing `inactive` | The declaration, the check results and the reasons |
| A body file is missing at admission | `blocked`. A new admission record can follow | The declaration and the reason |

## Examples

| File | Role | Rejected by |
|---|---|---|
| [capsule_declaration.json](examples/capsule_declaration.json) | valid `agent` declaration (`intent.compiler`) | |
| [research_benchmark_capsule.json](examples/research_benchmark_capsule.json) | valid `tool` declaration with network allowlist and a scoped effect | |
| [ranking_child_declaration.json](examples/ranking_child_declaration.json) | valid RSI child with lineage | |
| [verifier_capsule_invalid_rsi_propose.json](examples/verifier_capsule_invalid_rsi_propose.json) | verifier CC with `rsi` `propose` | `rsi_mode_allowed` |

The RSI candidate examples that fail `changes_allowed`, `rsi_no_copy` and `profile_within_may_change` are listed in the [RSI contracts](rsi-contracts.md#candidate-package). Every CC build page links its own declaration example. All are listed in the [contract index](README.md#contract-index).

**Minimum quality bar.** A reviewer can tell from the declaration alone what the CC may touch, how each change is undone, which parts RSI may change, and which exact bytes the version pins.

<a id="differences-from-the-historical-source"></a>

## Current declaration rules

Version `1.0.0` and the current [schema](schemas/capsule-declaration.schema.json) define this package's declaration format. Importers map other formats explicitly; similarity does not imply byte compatibility.

| Topic | Current format | Ruling |
|---|---|---|
| Required groups | All nine root groups | Every group is present. An empty list is explicit, so a missing claim is never read as a promise |
| `schema_version` | Exactly `1.0.0` | A new format owned by this package. Importers map old declarations explicitly |
| `identity.kind` | `tool`, `skill`, `mcp`, `a2a`, `prompt`, `subagent`, `agent`, `composite` | `agent_template` becomes `agent`. `prompt_section` becomes `prompt`. `bundle` is dropped: a bundle is a composite later. M1 admits only `agent` and `tool` |
| `identity.load_mode` | `invoked`, `context_injected` | The question is isolation, not timing. M1 admits only `invoked` |
| `identity.overlays` | Objects pinned by `sha256` | An overlay must be pinned to be checked. No M1 runner supports overlays |
| `identity.remote` | Adds a required `fingerprint` and range | A remote interface needs a digest. Remote CCs are rejected in M1 |
| `identity.lineage` | `Ref` objects, all fields required when lineage is present | Refs resolve to bytes. Lineage is required for every RSI child ([ruling 10](../side-systems/owner-rulings.md#rsi-v02)) |
| `lineage.relation` | `supersedes`, `specialises`, `rollback_of`, `migrated_from`, `composes`, `fuses` | `composes` and `fuses` are rejected in M1 |
| `effects[].reversibility` | `none`, `scoped`, `inverse`, `compensate`, `emission` | `reversible` splits into `scoped` and `inverse`. `compensable` becomes `compensate` with pinned `undo`. `emission` is added for effects that leave the system |
| `effects[].op` | Free text | Lost enum. Admission judges an effect by `resource_key`, `scope`, `reversibility` and `risk`. `op` is descriptive |
| `effects[].risk.severity` | `low`, `bounded`, `high` | Enum decided here. `high` is rejected in M1 |
| `effects[]` other fields | All nine fields required | Every effect states repeat safety, undo and risk |
| `guarantees.checks[].kind` | `deterministic`, `semantic` | `reference` is deterministic. `judge` is semantic. A negative control is a deterministic check whose `target` names the input to refuse. The deciding checks live in the check bundle |
| `guarantees.checks[]` `anchor`, `signal_source`, `owner`, `assurance` | Free text | Lost enums. Guarantees are claims only, so these describe and never decide |
| `guarantees.checks[].over` | `each_call`, `outputs`, `inputs_and_outputs` | The declared scope is explicit |
| `guarantees.acceptance`, `evals` | `string[]` and `Eval[]` objects | Type change. Both are accepted-unused in M1 |
| `guarantees.quality.window` | `integer` | Type change: a window is a count of observations |
| `guarantees.exempt` | `{reason: generalist}` | The reason is explicit. Rejected in M1 |
| `ports` | `{name, artifact_type, schema_ref, required, description, check_ids}` | One port vocabulary. Ports connect only when type and contract are equal |
| `needs.network` | `mode` + `direction` + `allowlist` | Authorization and direction are separate. M1 admits `none`/`none` and `allowlist`/`egress` |
| `needs.external` | `{kind, identifier}` with `pin` or `floating` | A floating need states purpose, role and contracts and must pin before dispatch |
| `needs.resources`, `needs.injects` | Objects with `mode` or an interface range | Type change. The library and binder read the mode |
| `needs.when` predicates | `check.operator` free text, `on_unknown` `block` or `defer_to_dispatch`, `on_unavailable` `block` | Unknown never passes. A non-empty list is rejected in M1 |
| `budget` | `per_call` dimensions with `enforcement` and `on_exhaust` | Each limit says how it is enforced. `concurrency` is dropped: M1 runs one node at a time |
| `evolution` | `rsi`, `may_change` (allowlist) and `notes_for_builder`. No `frozen` | The October 6 rebuild replaced the author's allowlist with a denylist and moved the allowlist into the target profile, with no recorded decision. [D34](../method/decisions.md#d34) restores the allowlist. The target profile `mutable_paths` must be a subset of `may_change` |
| `needs.external[].purpose`, `needs.human_interaction`, `needs.secrets`, package and lockfile pins, `guarantees.failure_modes` | Restored with the M1 status given above | Dropped in the same rebuild ([D34](../method/decisions.md#d34)). Package pins now use an external dependency of kind `package` with a `lockfile` |
| `lineage.relation` `rollback_of` | `rejected-in-M1` | Rollback is a standing move ([D41](../method/decisions.md#d41)) |
| `interface_hash` | None | Later work. M1 compares exact declaration bytes |
| `structure.nodes` | `string[]`, `type` `dag`, `direction` `forward` | A finite acyclic graph. Composites are rejected in M1 |
| Contract hash | None. One digest of the exact bytes | See [hashing profile](#hashing-profile). A canonical contract hash is reserved |

## Execution styles and consumers

Admission reads identity, closure and safety. The Planner reads the summary, ports and needs through the library snapshot. The binder and runner read ports, effects and limits. The verifier reads the whole declaration as the CC's promise. RSI reads lineage and `evolution` alongside its protected target profile. An unsupported obligation blocks admission or binding. It is never silently skipped.

## Model-backed export

Fill `needs.model.tool_calling`, `min_context`, `modalities`, `families` and `excludes` from the actual capability. The admitted declaration and its original-byte closure are exported through [SelectedCapsuleInput](model-routing-contract.md#selected-capsule-input). Profiles, eligibility, task context, route decisions and budgets stay in protected runtime records.
