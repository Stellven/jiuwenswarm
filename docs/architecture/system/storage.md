---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ledgers.md, ../capsule/toolchain.md]
provides: [system.durable_storage, system.stage_evidence]
consumes: [cc.observation, cc.artifact, cc.binding, cc.verification]
depends_on: [../capsule/toolchain.md, ledgers.md]
tags: [system, m1, storage, evidence]
---

# Durable publication, frozen inputs and execution evidence

M12 owns the following persistence semantics for PRD 1.4, 4.2.8–4.2.9 and 4.5. The Store API signatures remain on [toolchain](../capsule/toolchain.md#m12-store). Upstream `exclusive_set` alone does not promise durability or a multi-record transaction. The authoritative M1 backend is immutable local files; a Shelve/KV index and the engine journal are rebuildable caches.

## Layout and authority

`DATA` is the resolved user data directory; `WORKSPACE` is the selected research workspace. Relative paths are resolved by [configuration](environment.md), never by an arbitrary child working directory.

| Location | Writer | Authority |
|---|---|---|
| `DATA/cc/content/<sha256>` | M12 on an authorized writer's request | immutable bytes, verified when read |
| `DATA/cc/commits/<batch_id>/` with `manifest.json` and record JSON files | M12 only | committed records; manifest lists kind, scope, id and hash |
| `DATA/cc/index/` | M12 | lookup cache, rebuilt from complete commits |
| `records/runs/<run_id>/` in WORKSPACE | evidence collector / supervisor | run configuration, host facts, lifecycle records, journal and emergency incident log |
| `records/bundles/<run_id>/<obs_id>/` | evidence collector | required raw execution capture, completed by immutable manifest |
| `records/records.jsonl`, scorecards, `records/exports/<export_id>/` | Data Foundation assembler/exporter | derived records and frozen exports |
| `WORKSPACE/.cc/snapshots/<run_id>/` | authorized snapshot service | read-only project/dataset/model/blueprint snapshots |
| `WORKSPACE/poc/<run_id>/<request_id>/` | confined POC process only through approved service | disposable attempt working tree and venv; never original input assets |
| `WORKSPACE/outputs/<run_id>/` | delivery through authorized workspace writer | published report and POC zip; returned paths identify committed bytes |

## Store contract

Add `commit_batch(batch_id: id, records: list<Record>) -> list<Ref>` to Store. Record is a canonical CC schema kind; put_record delegates to a single-record batch. Freeze publishes all Bindings together. put_content durably publishes bytes before a referencing record. Internal dispatch/lifecycle/review/RSI records use the separate registered put_system/get_system API and namespace owned by [system records](records.md), with this same durable publication mechanism; they are not unregistered CC record kinds.

M12 serializes writers using one supervisor-owned process and a local advisory lock. It validates writer authority, schema, record-key uniqueness and hashes before publishing. Writes go into a temporary directory on the same filesystem. Files and their manifest are flushed and fsynced; atomic directory rename publishes the batch, followed by parent-directory fsync. The lock guards destination existence so an existing commit is never replaced. Readers see only final commit directories. `commit_batch` returns only after publication is durable. Unsupported filesystems or unavailable directory fsync fail doctor; network filesystems are outside this M1 backend.

| Condition | Error / behavior |
|---|---|
| same batch or record key, identical canonical bytes | return existing refs; no second write |
| same identity with different bytes | `STORE_CONFLICT`; halt, preserve both proposed hashes in incident evidence |
| absent record/content | `STORE_NOT_FOUND`; fail the consumer, never fabricate a value |
| bytes differ from recorded/expected hash | `STORE_CORRUPT`; refuse read and block the run |
| lock held / run already active | `RUN_BUSY`; no second writer or dispatch |
| write/fsync/publication fails | `STORE_UNAVAILABLE`; no success ref is returned |

Restart scans complete manifests, verifies every referenced file and rebuilds indexes. Incomplete staging directories are quarantined and never exposed as committed. A lost response after successful commit is safe to retry using the same batch identity. An orphan content blob is harmless and remains unreadable to consumers without an authorized ref. `records.jsonl` is an append-only derived view: truncate only an incomplete trailing line during repair, then regenerate missing entries from committed records. It is never the gate authorization source.

## Required evidence and derived views

The complete Stage Evidence Bundle is an internal immutable manifest, not the bounded model-facing [`evidence_bundle`](../types/evidence-bundle.md). `seal_execution(obs_id, capture) -> EvidenceManifestRef` and `get_execution(ref) -> ExecutionEvidence` are the collector's public APIs. `EvidenceManifestRef` contains `obs_id`, `manifest_sha256` and a workspace-relative manifest path. `ExecutionEvidence` contains record refs, captured files `{role, relative_path, content_sha256, size_bytes}`, start/end host facts, declared-versus-observed operations, and capture completeness/status. Allowed roles are input, output, stdout, stderr, model_prompt, model_reply, tool_call, security_check and environment. All paths resolve under the bundle root.

Raw model turns, tool frames, process streams and required security evidence are written as they occur. The runner seals capture before committing its terminal Observation; that Observation's `ext.runner.execution_evidence` stores the manifest reference. The gate verifies the manifest's hashes, scope and completeness before any pass. Judge invocation creates another required capture under its own `obs_id`; the Verification points to that invocation. Loss of required evidence is `EVIDENCE_UNAVAILABLE` or `EVIDENCE_CORRUPT`, never an optional warning. UI notifications and optional diagnostic spans may fail independently, but required capture cannot be implemented as an ignored event subscriber.

Before a frozen blueprint is released, `snapshot_resources(intake_ref, resource_ids) -> ResourceSnapshotManifestRef` copies the explicitly bound inputs into an owned snapshot and records per-file hashes, sizes and safe relative paths. No symlinks, special files, external mounts, changing files during copy or workspace escapes are accepted. This is experimental freezing, not a cryptographic ingestion/signing feature (issue 15 remains a product reading). Baseline/model and validation data references used by later stages resolve to this snapshot manifest, not mutable intake paths. Consumers recheck hashes; a changed source after snapshot cannot change the experiment.

The same run pins its configuration snapshot, plan, policy, vocabulary, capsule versions, gate profiles, blueprint, dataset and seed policy. No downstream stage writes these objects. The POC process receives private writable copies while blueprint and dataset originals remain read-only. Data Foundation views can be rebuilt from CC records **and retained mandatory raw capture**; raw capture itself cannot be recreated from a missing trace.

## Crash and recovery cases

- Before publication: no record is visible and downstream remains locked.
- After publication but before the reply/event: repeat the same identity, return committed refs, then emit any missing notification.
- After work completed but before its Gate: reuse the committed Observation and evaluate it; do not execute work again just to repair a gate write.
- Child may have performed effects but no terminal Observation exists: mark the attempt interrupted; explicit human review is required before a new execution attempt.
- All durable sinks unavailable: terminate execution, report failure on the controlling terminal and retain in-memory context as available. Do not claim a persisted forensic record when storage failed.

These are required architecture scenarios, not claims of executed tests; [verification](verification.md) defines their observation points.
