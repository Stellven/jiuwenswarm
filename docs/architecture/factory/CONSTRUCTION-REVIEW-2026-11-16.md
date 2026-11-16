# Construction implementation review and current limits

The workspace already contained the construction implementation, frozen runtime
snapshots and a spent acceptance campaign when this review began. That work was
preserved and inspected before changes. See [implementation](CONSTRUCTION-LOOP.md)
and [historical live acceptance](CONSTRUCTION-ACCEPTANCE.md). The original
construction-handoff-v1 remains unchanged.

## Review repairs

- Shared construction build/GPU allowances are now enforced in the existing Jobs
  attempt ledger across campaign-owner revisions, including failed attempts.
  Idempotent recovery and successful build reuse do not consume another attempt.
- Already-submitted builds and durable reuse aliases can reconcile after deadline
  or stop. A successful recovered build does not authorize a new lab launch after
  expiry. Abandon cannot hide an existing reused build.
- Interpreter-bound execution records verify the interpreter actually executing,
  not merely an unchanged nominated interpreter file. Image bindings retain their
  separate identity semantics.
- Baseline accounting rejects negative workspace/reservation sizes and invalid KV
  dimensions. Ceiling calculations require explicit precision/sparsity and report
  absent or mismatched phase/shape/model/workload identity. Caller-provided reports
  or self-asserted verification do not become authenticated measurements.
- The baseline GGUF reader now knows storage extents for the pinned model's packed
  types, rejects truncated/overlapping tensors, duplicate names and malformed row
  alignment. The enum/block definitions are pinned in LAYOUT-SOURCES.json. Storage
  accounting does not establish a working packed kernel or complete model execution.

Read-only inspection of all four existing model shards accounted for 1,008 tensors
and 138,233,575,680 tensor bytes. All encountered layouts were recognized. Header
identities and per-shard counts are in ROOT/construction-review-v2/model-storage.json.
This inspection did not hash full weight files, run inference or measure a ceiling.

## Acceptance boundaries

The existing campaign recorded 24 agent turns and three native build attempts;
both allowances are exhausted. It recorded six lab attempts, of which two were
successful actual GPU launches. The successful GPU work was host-run FP32-slice
calibration. The lost-acknowledgement job was deduplicated but failed before GPU
execution. These are not a successful autonomous source-changing GPU investigation.
No allowance was renewed by this review, and it ran no native build, GPU probe or
live agent campaign.

Remaining work is explicit: qualify the repaired build/admit/GPU/collect/agent
continuation path, repeat successful-GPU lost-ack recovery, and build/calibrate a
model-native packed expert oracle with representative routing/activations. The
current baseline package supports accounting, replay and scoped resident-slice
experiments, but does not yet determine the model's whole-system performance
ceiling. The serial capacity replay is a modeled reference, not an optimal
prefetch schedule. Neither a numerical pass nor a storage-layout inventory supplies
missing kernel, attention/KV, observer-overhead or end-to-end quality evidence.

## Verification and handoff

Review evidence is under ROOT/construction-review-v2 and ROOT/results/construction-*
review logs. ROOT is `/home/user2/software-factory-spark-20261113`. Final source and
review evidence form a supplement to construction-handoff-v1; its historical
runtime/image and receipt identities must not be relabeled as the repaired source.
Fresh execution requires a newly frozen binding. Runtime stores and copied
qualification packages remain local artifacts, not source-controlled dependencies.

Final source regression: **1,408 passed, one skipped, one deselected in 169.31s**.
The deselected existing Docker service test requires its unavailable pinned image.
The successful run used the existing `/tmp/factory-construction-test-env`, its bin
folder on PATH, and the retained SIMINFENG_ROOT test dependency. Earlier review
invocations retained one missing-MCP collection failure and one missing-PATH test
failure; neither was counted as a pass. No new global dependencies were installed.
All 49 declarations passed the pinned upstream schema, and the final baseline CC
completed the same replay through our runner and the upstream runner. These are
CPU/package checks, not a new GPU or live-agent qualification.
