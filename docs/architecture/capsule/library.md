---
id: capsule.library
type: module-spec
status: proposed
tags: [capsule, library, m1]
level: detail
provides: [capsule.library]
depends_on: [admission.md, ../system/storage.md, fields.md]
prd: [4.1.2]
---

# The M1 capsule library

PRD: 4.1.2

> Answers: What does the M1 capsule library hold, and how does a run pin a snapshot of it?

## Purpose

*Kubernetes parallel ([k8s-lens](../k8s-lens.md)): versions are like image digests (immutable), the active alias is like a tag (movable). Admission is like an admission controller.*

The library stores immutable admitted capabilities, bytes, declarations, evidence and manual Standing changes. Admission and the librarian are ordinary control modules. One library snapshot is pinned per run at launch: the planner service reads it to propose a DAG, and the binder resolves exact versions from the same snapshot ([decisions](../decisions.md), A26). This page is the home of snapshot/alias APIs, [admission](admission.md) is the home of provider semantics, and [storage](../system/storage.md) is the home of durable publication.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-library-snapshot"></a>**library snapshot** (also: LibrarySnapshot, snapshot) | The frozen, hashed list of exact capability versions (name, `decl_hash`, `interface_hash`, Verdict and Standing refs) that one run is pinned to at launch. The planner reads it and the binder resolves versions from it; a running run keeps its snapshot. |
| <a id="term-alias"></a>**alias** (also: active alias, pointer) | The movable pointer from a capability name to the current admitted `decl_hash`. Versions are immutable; only the alias moves, and a frozen run never dereferences it again. |
| <a id="term-activation"></a>**activation** | The librarian action that moves the alias to an already admitted exact hash, written as a durable activation SystemRecord. A person requests it, and an RSI child needs it to become current. |
| <a id="term-rollback"></a>**rollback** | An activation request that points the alias at a historical admitted hash. It is not a Standing change and creates no new version. |

## Interface

Messages of the library and the librarian. The meaning of each is in the sections below, especially [frozen library snapshot and activation](#frozen-library-snapshot-and-activation).

- **snapshot() request** (call, supervisor at launch -> librarian). Schema: [`library-rsi-v1.schema.json#library_snapshot_request`](../contracts/library-rsi-v1.schema.json).
- **snapshot() reply** (call, librarian -> supervisor). Schema: [`library-rsi-v1.schema.json#library_snapshot_result`](../contracts/library-rsi-v1.schema.json).
- **Committed LibrarySnapshot record** (record, librarian -> store (read by planner, binder)). Schema: [`library-rsi-v1.schema.json#library_snapshot`](../contracts/library-rsi-v1.schema.json).
- **catalogue() request** (call, planner service -> librarian). Schema: [`library-rsi-v1.schema.json#catalogue_request`](../contracts/library-rsi-v1.schema.json).
- **catalogue() reply** (call, librarian -> planner service). Schema: [`library-rsi-v1.schema.json#catalogue_result`](../contracts/library-rsi-v1.schema.json).
- **activate() request** (call, developer CLI -> librarian). Schema: [`library-rsi-v1.schema.json#activation_request`](../contracts/library-rsi-v1.schema.json).
- **activation [SystemRecord](../system/records.md#term-systemrecord) payload** (record, librarian -> store). Schema: [`library-rsi-v1.schema.json#activation_record`](../contracts/library-rsi-v1.schema.json).
- **Manual Standing command: suspend, deprecate, retire, revoke or restore** (call; rollback is not one of these, it is an `activation_request`), developer CLI -> librarian). Schema: [`tools-v1.schema.json#standing_change_request`](../contracts/tools-v1.schema.json).
- **Result of a manual Standing command, with the new Standing ref** (record, librarian -> developer CLI, store). Schema: [`tools-v1.schema.json#standing_change_record`](../contracts/tools-v1.schema.json).

## What the library holds

M1 local tool and skill capabilities have canonical declarations, complete hashed body/dependency/check closure, [Candidates](../schemas/candidate.md#term-candidate), admission [Verdicts](../schemas/verdict.md#term-verdict), visible [test suites](../schemas/checks.md#term-test-suite) and Standing history. Historical versions remain retrievable by exact hash. Composite/remote/generalist [capsules](capsule.md#term-capability-capsule), automatic catalogue ranking, live installs, automatic drift revocation and third-party certified suites remain outside the runtime whitelist.

One capability name denotes independently meaningful work, not a file, process or pipeline position. A mechanical helper remains an [ordinary module](../capabilities/README.md#term-ordinary-module) unless independent reuse/governance/permissions justify a capability. The inventory is the home of the initial names. An implementation revision creates a new declaration hash; [released](../system/lifecycle.md#term-release) port-schema changes require an explicit new type version and adapter. [RSI](../rsi.md#term-rsi) cannot change the interface.

## Behavior: admission, the only way in

Mandatory parsing, hashes, interface generation, dependency closure and permissions precede policy-selected AdmissionProvider assessment. Tested admission grants provisional after actual visible [checks](fields.md#term-check). Developer [Puppet admission](admission.md#term-puppet-admission) grants exempt to exact allowlisted hashes after mandatory integrity checks. Neither grants certified in M1. Suites are recorded only when executed, and library admission never grants runtime [Gate](../verification.md#term-gate) PASS.

The librarian publishes the Verdict before exposing an admitted version. Partial publication is recovered using immutable records; a missing durable Verdict means unavailable. An [RSI child](rsi.md#term-parent-and-child) starts [admitted_inactive](admission.md#term-admitted-inactive). Activation, suspension and deprecation are explicit local [operator](../capabilities/README.md#term-operator) actions, and rollback is an activation request that points at a historical admitted hash (not a Standing change); no background automation changes the active alias.

## Suites and lineage

Visible suites are immutable sets of interface-keyed cases held by admission. A compatible child must satisfy its parent's applicable suites as well as its own before tested admission. Hidden RSI optimization suites belong to the [private oracle](fixture-oracle.md#term-fixture-oracle), are never copied into Candidate tests and do not create certified admission evidence. Parent hashes form an append-only lineage. Identical bytes may share content storage, but each admission and activation keeps its own authoritative record.

## Failure: eligibility and failure

| Situation | Outcome | Recovery |
|---|---|---|
| Unknown, missing or revoked entry at freeze | fails closed before dispatch | fix the snapshot or the entry, then a new run |
| Partial publication of an admitted version | recovered from immutable records; a missing durable Verdict means unavailable | repeat the admission request |
| Crash before the activation projection is repaired | the committed activation record is kept | the pointer projection is repaired from that record |


Freeze reads one snapshot, resolves fixed versions and validates each Verdict/Standing, all hashes, exact port versions, [policy epoch](../schemas/policy.md#term-epoch) and closure. Unknown/missing/revoked entries fail closed before dispatch. The active pointer cannot change a [frozen](../system/lifecycle.md#term-freeze) run: a running run keeps its pinned snapshot. Duplicate snapshot/activation requests return committed records; changed bytes under one request ID conflict. No control record is overwritten.

## Frozen library snapshot and activation

The librarian alone publishes `LibrarySnapshot`: closed `{schema_version: 1, entries: [{capability_name, decl_hash, interface_hash, verdict_ref, standing_ref}], policy_epoch, vocabulary_sha256, created_at}`. Entries sort by capability name then declaration hash; duplicate hashes/names in the active selection are invalid. Snapshot hash is canonical JSON SHA-256 and includes complete dependency/check/profile closure references through pinned declarations. No mutable alias is dereferenced after freeze. `snapshot(request_id) -> snapshot_ref` publishes atomically; `catalogue(snapshot_ref) -> entries` is read-only and redacts no contract needed by the isolated planner.

Schema: `library-rsi-v1.schema.json#library_snapshot_request` (call), `library-rsi-v1.schema.json#library_snapshot_result` (reply), `library-rsi-v1.schema.json#library_snapshot` (the committed record), `library-rsi-v1.schema.json#catalogue_request` and `library-rsi-v1.schema.json#catalogue_result`. Sort order and uniqueness of entries are checked at publication, not by the schema.

`activate(capability_name, admitted_decl_hash, expected_current_hash, actor, reason, request_id)` compares the current pointer, commits an activation SystemRecord, then exposes the pointer projection. A crash before projection repair retains the committed record as authority. Stale expected hash returns `STORE_CONFLICT`; identical request returns the committed result. Rollback is an `activation_request` selecting a historical admitted hash; it is never a `standing_change_request`, which covers only suspend, deprecate, retire, revoke and restore. First activation is done by `cc bootstrap` (actor `installer`, `expected_current_hash` null), which admits and activates the seed capsules: toy capsules at build step 1, research capsules when each is ported. Schema: `library-rsi-v1.schema.json#activation_request` (a null `expected_current_hash` means no pointer exists yet) and `library-rsi-v1.schema.json#activation_record` (the activation SystemRecord payload, which carries the previous and new hash, actor, reason and the resulting Standing ref). RSI children are activated through this one call; [RSI engine](rsi-engine.md) has no separate activation API. Activation changes future snapshots only. RSI children remain inactive until this action. The version/alias separation follows [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/); replace storage backend behind snapshot/activation APIs when concurrency exceeds the single-writer M1 design.

## Deferred capsule interaction analysis

SkillFuzz-style analysis of how independently valid capsules behave together is deferred. M1 still validates exact typed [ports](fields.md#term-port), dependency closure, permissions, budgets and required Gates. Those checks establish structural eligibility, not semantic safety of every combination. No interaction campaign is claimed to have run or required for current admission. [Planner](../system/planner.md) and presentation package use this same boundary.

## Tests: connected rows

Rows in [test surfaces](../system/test-surfaces.md#verification-table): [V04](../system/test-surfaces.md#verification-table), [V28](../system/test-surfaces.md#verification-table).
