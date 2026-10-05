---
id: system.storage
type: module-spec
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, ledgers.md, ../capsule/toolchain.md]
provides: [system.durable_storage, system.stage_evidence]
consumes: [cc.observation, cc.artifact, cc.binding, cc.verification]
depends_on: [../capsule/toolchain.md, ledgers.md]
tags: [system, m1, storage, evidence]
level: detail
prd: [4.5.2, 2.10, 4.2.8]
---

# Durable publication, frozen inputs and execution evidence

PRD: 4.5.2, 2.10, 4.2.8

> Answers: How are records published durably and recovered after a crash?

## Purpose

M12 is the home of the following persistence semantics for PRD 1.4, 4.2.8–4.2.9 and 4.5. The Store API signatures remain on [toolchain](../capsule/toolchain.md#m12-store). Upstream `exclusive_set` alone does not promise durability or a multi-record transaction. The authoritative M1 backend is immutable local files; a Shelve/KV index and the engine journal are rebuildable caches.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-data-foundation"></a>**Data Foundation** | The evidence layer that captures required raw execution evidence as it happens and later assembles and exports records. Its views can be rebuilt from CC records and retained raw capture. |
| <a id="term-run-bundle"></a>**Run bundle** | The raw execution capture of one call, kept under `records/bundles/<run_id>/<obs_id>/` and completed by an immutable manifest. It is the authority for evidence that cannot be recreated. |
| <a id="term-derived-view"></a>**Derived view** (also: derived views) | A rebuildable projection such as `records.jsonl`, a scorecard or an export. It never holds a fact the records and the sealed capture lack. |
| <a id="term-commit-batch"></a>**Commit batch** (also: batch) | A set of records published together by one atomic commit, for example all Bindings of a phase. The same batch identity with identical bytes returns the existing refs. |

## Layout and authority

`DATA` is the resolved user data directory; `WORKSPACE` is the selected research workspace. Relative paths are resolved by [configuration](environment.md), never by an arbitrary child working directory.

| Location | Writer | Authority |
|---|---|---|
| `DATA/cc/content/<sha256>` | M12 on an authorized writer's request | immutable bytes, verified when read |
| `DATA/cc/commits/<batch_id>/` with `manifest.json` and record JSON files | M12 only | committed records; manifest lists [kind](../capsule/capsule.md#term-capsule-kind), scope, id and hash |
| `DATA/cc/index/` | M12 | lookup cache, rebuilt from complete commits |
| `records/runs/<run_id>/` in WORKSPACE | evidence collector / supervisor | run configuration, host facts, lifecycle records, journal and emergency incident log |
| `records/bundles/<run_id>/<obs_id>/` | evidence collector | required raw execution capture, completed by immutable manifest |
| `records/records.jsonl`, scorecards, `records/exports/<export_id>/` | Data Foundation assembler/exporter | derived records and [frozen](lifecycle.md#term-freeze) exports |
| `WORKSPACE/.cc/snapshots/<run_id>/` | authorized [snapshot](../capsule/library.md#term-library-snapshot) service | read-only project/dataset/model/blueprint snapshots |
| `WORKSPACE/poc/<run_id>/<request_id>/` | confined POC process only through approved service | disposable attempt working tree and venv; never original input assets |
| `WORKSPACE/outputs/<run_id>/` | delivery through authorized workspace writer | published report and POC zip; returned paths identify committed bytes |

## Interface: store contract

Messages of this module (the Store API signatures are on [toolchain](../capsule/toolchain.md#m12-store)).

- **Manifest of one atomic commit batch (all [Bindings](../schemas/binding.md#term-binding) of a phase)** (record, store (M12) -> readers). Schema: [`execution-v1.schema.json#commit_batch_manifest`](../contracts/execution-v1.schema.json).
- **Runner commit, one record per request** (call, runner -> supervisor, boundary BD21). The runner never writes the store: it stages bytes and sends one `commit_request` per record (capture, [Artifacts](../schemas/artifact.md#term-artifact), then the [Observation](../schemas/observation.md#term-observation) last); the supervisor re-checks the bytes and writes through M12, answering `commit_result` (`committed`, `refused` or `conflict`). Frames are length-prefixed (4-byte big-endian length, UTF-8 JSON, at most `cc.ipc.max_frame_bytes`). Schema: [`execution-v1.schema.json#commit_request`](../contracts/execution-v1.schema.json), [`execution-v1.schema.json#commit_result`](../contracts/execution-v1.schema.json).
- **Complete stage evidence manifest** (report, evidence collector -> [Gate host](../capsule/gate-host.md#term-gate-host), supervisor). Schema: [`execution-v1.schema.json#execution_evidence`](../contracts/execution-v1.schema.json).

Add `commit_batch(batch_id: id, records: list<Record>) -> list<Ref>` to Store. Record is a canonical CC schema kind; put_record delegates to a single-record batch. Each freeze publishes its Bindings together as one batch: freeze 1 ([prep plan](../types/run-plan.md#term-prep-plan), at launch) and freeze 2 ([planned plan](../types/run-plan.md#term-planned-plan), after requirements), per [records](records.md#behavior-two-freeze-points). Each batch has a manifest, `execution-v1.schema.json#commit_batch_manifest`, and the supervisor then writes one `run_phase_started` record per freeze. put_content durably publishes bytes before a referencing record. Internal dispatch/lifecycle/review/RSI records use the separate registered put_system/get_system API and namespace owned by [system records](records.md), with this same durable publication mechanism; they are not unregistered CC record kinds.

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

## Behavior: required evidence and derived views

Model captures outside public [runs](lifecycle.md#term-run)/admission use the scoped private namespaces defined in [environment](environment.md#model-call-scope-and-private-capture). services-v1 private_model_capture is the home of the closed metadata record: version, scope, [request_id](../contracts/principles.md#term-request-id), [obs_id](observability.md#term-obs-id), [turn](model-bridge.md#term-model-turn), role, content_sha256, size_bytes and sealed_at. [RSI](../rsi.md#term-rsi) controller and oracle are each the sole writer of their private namespace, using the same atomic temporary-directory/hash/fsync/publication discipline. The [model bridge](model-bridge.md#term-model-bridge) sends bytes over that namespace authority's authenticated descriptor and waits for its committed capture Ref. Private records are not public CC Artifacts/Observations and cannot be served through normal store/export/StageContext APIs. A crash before capture commit cannot return complete, refund an oracle reservation or cause automatic model replay.

The complete Stage Evidence Bundle is an internal immutable manifest, not the bounded model-facing [`evidence_bundle`](../types/evidence-bundle.md). `seal_execution(obs_id, capture) -> EvidenceManifestRef` and `get_execution(ref) -> ExecutionEvidence` are the collector's public APIs. Schema: `execution-v1.schema.json#evidence_manifest_ref` and `execution-v1.schema.json#execution_evidence`. `EvidenceManifestRef` contains `obs_id`, `manifest_sha256` and a workspace-relative manifest path. `ExecutionEvidence` contains record refs, captured files `{role, relative_path, content_sha256, size_bytes}`, start/end host facts, declared-versus-observed operations, and capture completeness/status. Allowed roles are input, output, stdout, stderr, model_prompt, model_reply, tool_call, security_check and environment. All paths resolve under the bundle root.

Raw model turns, tool frames, process streams and required security evidence are written as they occur. The runner seals capture before it asks the supervisor to commit its terminal Observation; that Observation's `ext.runner.execution_evidence` stores the manifest reference. The gate verifies the manifest's hashes, scope and completeness before any pass. Judge invocation creates another required capture under its own `obs_id`; the [Verification](../schemas/verification-record.md#term-verification) points to that invocation. Loss of required evidence is `EVIDENCE_UNAVAILABLE` or `EVIDENCE_CORRUPT`, never an optional warning. UI notifications and optional diagnostic spans may fail independently, but required capture cannot be implemented as an ignored event subscriber.

At intake, before freeze 1, `snapshot_resources(intake_ref, resource_ids) -> ResourceSnapshotManifestRef` copies the explicitly bound inputs into an owned snapshot and records per-file hashes, sizes and safe relative paths. No symlinks, special files, external mounts, changing files during copy or workspace escapes are accepted. This is experimental freezing, not a cryptographic ingestion/signing feature (issue 15 remains a product reading). Baseline/model and validation data references used by later stages resolve to this snapshot manifest, not mutable intake paths. Consumers recheck hashes; a changed source after snapshot cannot change the experiment.

The same run pins its configuration snapshot, library snapshot, prep plan, planned plan (once frozen), policy, vocabulary, [capsule](../capsule/capsule.md#term-capability-capsule) versions, gate profiles, blueprint, dataset and seed policy. No downstream stage writes these objects. The POC process receives private writable copies while blueprint and dataset originals remain read-only. Data Foundation views can be rebuilt from CC records **and retained mandatory raw capture**; raw capture itself cannot be recreated from a missing trace.

## Failure: crash and recovery cases

| Situation | Outcome | Recovery |
|---|---|---|
| Before publication | no record is visible; downstream remains locked | repeat the same batch identity |
| After freeze 1 but before freeze 2 is published | committed preparation evidence stays; no planned node can dispatch | resume revalidates the committed planner proposal and publishes freeze 2 from the same snapshot; never re-plans silently ([lifecycle](lifecycle.md#failure-human-review-and-recovery)) |
| After publication but before the reply or event | records are committed | repeat the same identity, return committed refs, then emit any missing notification |
| After work completed but before its Verification | Observation is committed | reuse it and evaluate it; do not execute work again just to repair a gate write |
| Child may have performed effects but no terminal Observation exists | attempt is marked interrupted | explicit human review before a new execution attempt |
| All durable sinks unavailable | execution terminates; failure reported on the controlling terminal; no persisted forensic record is claimed | restore storage, then explicit review |

These are required architecture scenarios, not claims of executed tests; [verification](test-surfaces.md) defines their observation points.

## Tests

Fixtures and fakes: a temporary store root with fault injection (kill mid-write, duplicate request, corrupt bytes); repeated assembly and read-only views. Rows in [test surfaces](test-surfaces.md#verification-table): [V03](test-surfaces.md#verification-table), [V17](test-surfaces.md#verification-table), [V31](test-surfaces.md#verification-table).
