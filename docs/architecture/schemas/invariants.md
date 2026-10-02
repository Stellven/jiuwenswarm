---
type: rules
tags: [schema, foundation]
---

# Schema invariants

Rules every schema obeys, cited as `INV-n`. `tools/sync.py` enforces the parts marked **(lint)**. The capsule's own rules are in [Capability Capsule](../capsule/capsule.md).

**Design rules.** Reuse openJiuwen (agent-core, jiuwenswarm) first; the old AI4Research harness is a source of lessons, never code to extend. Block for safety, label for quality: a safety breach stops the call, a weak result passes with a label. Fail closed: an unknown never passes, a changed hash is refused, a missing record is a bug. Every reuse claim cites a file and line.

## Records

| Id | Rule |
|---|---|
| INV-1 | Every record extends [`cc.common.v1`](common.md), with exactly its envelope field names. Exception: the Declaration, authored content carried inside a Candidate and identified by `decl_hash`. |
| INV-2 | **Written once.** No record is edited or appended to. A change is a new record: a new version, log entry or result. |
| INV-3 | **One writer per record kind.** When two parties contribute, split the record (the runner's Observation and the gate's Verification). A kind may instead fix its writer per value of a discriminator (the Finding's `kind`, the Artifact's `scope`, the Standing's `state`). A store keeps records; it never writes them. |
| INV-4 | **What, never how.** A record holds facts. Thresholds, defaults, bounds, rules and settings go in the [policy](policy.md). |
| INV-5 | **No independent derived authorities.** Do not duplicate another record's facts as a separately mutable truth. Binding checks are assembled once for reproducibility; Verification's single durable gate_result snapshot is required by PRD 4.2.8. Its aliases and normalized/routing values are checked against the same record and frozen invocation at commit. Check details remain in results and are referenced by id. |
| INV-6 | **Refer, do not repeat.** References are `Ref {id, sha256}`; code and content are referenced by hash. Capsule names are local to a library and are used only in the Standing, in `needs.external`, in a test suite's `capsule_name`, in check ids seen from outside a Declaration, in policy `levels`, in a `run_plan`'s capsule names, in an `evidence_bundle`'s `subject.capsule_name`, and in the model client's `ModelCallContext.capsule_name`. |
| INV-7 | **A capsule holds no task.** A Declaration names no step, stage, run, workflow or other capsule, except its dependencies in `needs.external`, its `members` and its `identity.lineage`. |
| INV-8 | **Unknown never passes.** A predicate or check that cannot be evaluated gives `defer`, `unknown` or `fail`, never `pass`. |
| INV-9 | **Every promise has a check.** Every output port names a `check_id`. Every port type carries a check that applies at `node`, so every Binding has a check and every live output is checked. |
| INV-10 | **No one is their own final judge.** Builder evidence is kept, never counted. A certifying check is written by someone other than the builder. |
| INV-19 | *Proposed.* **Declared failures only.** A capsule completes its Declaration: it returns outputs matching its ports even for vague, contradictory or incomplete input, and puts the difficulty inside the output as data. The Artifact's `issues` (checked at M1) is the standard place for it. The capsule may end without an output only through a declared `guarantees.failure_modes` entry. Any other exception it raises is a bug: the runner records `outcome: error` with `CAPSULE_RAISED_UNDECLARED`, and the gate folds it to `blocked`, never `pass` or `fail`. A failure outside the capsule (the model runtime, a timeout) gets a runtime code, never a capsule code. |

## Types and names

| Id | Rule |
|---|---|
| INV-11 | **(lint)** Every field row has a **Type** from the grammar below, a **Req**, an **M1** mark (`checked` or `unchecked`, defined in [common](common.md)), an **Unlocks** entry exactly when unchecked, and a **Description**. |
| INV-12 | Names are `snake_case`. Ids end `_id` (or are `id`); hashes end `_sha256`, `_hash` or `_hashes` (or are `sha256`); times end `_at` (or are `at` or `timestamp`); references end `_ref`; lists are plural. **(lint)** for ids, hashes, times and `Ref` fields. |
| INV-13 | Enum values are lowercase; reason codes are `UPPER_SNAKE` (**lint**). A list of values is closed (`enum`) only when a consumer switches on it; otherwise it is a registry (`reg`) whose values live in the policy's `registries`. Exception: `reg(port_type)` takes its values from the [port type vocabulary](port-types.md). |
| INV-14 | Core fields are strict: an unknown field is refused, except inside `ext`, which is namespaced by tool. `ext` is part of a record's hash, never of `interface_hash`. |
| INV-15 | Hashes are lowercase hex SHA-256 over RFC 8785 canonical JSON; content is hashed over its raw bytes. |

| Type | Meaning |
|---|---|
| `string`, `text` | one line; free text |
| `integer`, `number`, `boolean`, `json` | JSON types; a `json` field names its shape in the description |
| `time` | RFC 3339 UTC |
| `sha256` | 64 lowercase hex characters |
| `id`, `uri` | an opaque string id, unique within its kind; a URI |
| `enum(a, b)` | a closed set of case-sensitive wire values; source-defined uppercase values are preserved; a new value is v2 |
| `reg(name)` | an open set from the policy registry `name`; a new value is a registry row |
| `Ref(kind)` | `{id, sha256}` pointing at a record of that kind |
| `EvidenceRef`, `Reason`, `Port`, `Predicate`, `Check` | shapes defined in [common](common.md) and the [Declaration](../capsule/fields.md), which includes `Check` |
| `list<T>`, `map<K, T>`, `object` | a list; an object keyed by `K`; an object whose fields are the rows below it, as `parent.child` |
| `T?` | may be null |

**Req.** `req` is always present; `opt` may be absent. Schema required-ness is never relaxed. The policy may also require optional fields per epoch, but only in authored records (Declaration, Candidate), so authors have a stable target while enforcement tightens.

## Change

| Id | Rule |
|---|---|
| INV-16 | **Versions.** Adding an optional field or a registry row is v1.x, approved on that item only. A field added in v1.x hashes as absent when it is absent: only v1.0 defaults are filled in before hashing, so existing hashes never change. Removing, renaming, making required or changing meaning is v2, with full approval. |
| INV-17 | **Policy tightens, schema holds.** A stricter epoch raises what the policy requires; the schema does not change. Several epochs may be current at once; each run and each admission pins exactly one. |
| INV-18 | **Promotion.** A field starts in `ext.<tool>`. When a second tool reads it, it is proposed as an optional core field (v1.x). |

A page goes `draft`, `proposed`, `v1` (approved, final), `v1.x` (additive only).

**Where we are right now.** Every schema page in this folder and in `capsule/fields.md` is still `draft` or `proposed`. None is `v1` yet. A `schema_version` string such as `cc.declaration.v1` names the version a page is aiming for, not one already in force. `INV-16`'s rule about what counts as an additive `v1.x` change versus a breaking `v2` one starts to matter once a page actually reaches `v1`. That happens when real code for an actual module is being built against it, not before. Until then, a page's fields can be added, removed, renamed or have their meaning changed without a version bump, since there is no released version yet to break. This is deliberate: right now this is exploratory alpha and beta work, not a frozen contract.

**Where to edit what.** Fields: the page's Fields table. Hows: the [policy](policy.md). Registry values: the policy's `registries`. Writers: the records table in [Schemas](schemas.md). The schema map there is generated by `python tools/sync.py` (`--check` lints without writing); never edit it by hand.
