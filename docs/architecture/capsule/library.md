---
type: capsule
status: draft
tags: [capsule, library, m1]
---

# The M1 capsule library

The library stores immutable admitted capabilities, bytes, declarations, evidence and manual Standing changes. Admission and the librarian are ordinary control modules. Production resolves fixed names; isolated planning reads a frozen catalogue. This page owns snapshot/alias APIs, [admission](admission.md) owns provider semantics, and [storage](../system/storage.md) owns durable publication.

## What the library holds

M1 local tool and skill capabilities have canonical declarations, complete hashed body/dependency/check closure, Candidates, admission Verdicts, visible test suites and Standing history. Historical versions remain retrievable by exact hash. Composite/remote/generalist capsules, automatic catalogue ranking, live installs, automatic drift revocation and third-party certified suites remain outside the runtime whitelist.

One capability name denotes independently meaningful work, not a file, process or pipeline position. A mechanical helper remains an ordinary module unless independent reuse/governance/permissions justify a capability. The inventory owns the initial names. An implementation revision creates a new declaration hash; released port-schema changes require an explicit new type version and adapter. RSI cannot change the interface.

## Admission: the only way in

Mandatory parsing, hashes, interface generation, dependency closure and permissions precede policy-selected AdmissionProvider assessment. Tested admission grants provisional after actual visible checks. Developer Puppet admission grants exempt to exact allowlisted hashes after mandatory integrity checks. Neither grants certified in M1. Suites are recorded only when executed, and library admission never grants runtime Gate PASS.

The librarian publishes the Verdict before exposing an admitted version. Partial publication is recovered using immutable records; a missing durable Verdict means unavailable. An RSI child starts admitted_inactive. Activation, suspension, deprecation and rollback are explicit local operator actions; no background automation changes the active alias.

## Tests and lineage

Visible suites are immutable sets of interface-keyed cases held by admission. A compatible child must satisfy its parent's applicable suites as well as its own before tested admission. Hidden RSI optimization suites belong to the private oracle, are never copied into Candidate tests and do not create certified admission evidence. Parent hashes form an append-only lineage. Identical bytes may share content storage, but each admission and activation keeps its own authoritative record.

## Eligibility and failure

Freeze reads one snapshot, resolves fixed versions and validates each Verdict/Standing, all hashes, exact port versions, policy epoch and closure. Unknown/missing/revoked entries fail closed before dispatch. The active pointer cannot change a frozen run. Duplicate snapshot/activation requests return committed records; changed bytes under one request ID conflict. No control record is overwritten.

## Frozen library snapshot and activation

The librarian alone publishes `LibrarySnapshot`: closed `{schema_version: 1, entries: [{capability_name, decl_hash, interface_hash, verdict_ref, standing_ref}], policy_epoch, vocabulary_sha256, created_at}`. Entries sort by capability name then declaration hash; duplicate hashes/names in the active selection are invalid. Snapshot hash is canonical JSON SHA-256 and includes complete dependency/check/profile closure references through pinned declarations. No mutable alias is dereferenced after freeze. `snapshot(request_id) -> snapshot_ref` publishes atomically; `catalogue(snapshot_ref) -> entries` is read-only and redacts no contract needed by the isolated planner.

`activate(capability_name, admitted_decl_hash, expected_current_hash, actor, reason, request_id)` compares the current pointer, commits an activation SystemRecord, then exposes the pointer projection. A crash before projection repair retains the committed record as authority. Stale expected hash returns `STORE_CONFLICT`; identical request returns the committed result. Rollback uses the same action selecting a historical admitted hash. Activation changes future snapshots only. RSI children remain inactive until this action. The version/alias separation follows [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/); replace storage backend behind snapshot/activation APIs when concurrency exceeds the single-writer M1 design.

## Deferred capsule interaction analysis

SkillFuzz-style analysis of how independently valid capsules behave together is deferred. M1 still validates exact typed ports, dependency closure, permissions, budgets and required Gates. Those checks establish structural eligibility, not semantic safety of every combination. No interaction campaign is claimed to have run or required for current admission. [Planner](../system/planner.md) and [presentation package](../presentation/showcase/README.md) use this same boundary.
