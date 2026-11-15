# Spark dependency, relocation and cleanup audit

Observed 2026-11-14 around 11:00 UTC. This was a read-only audit: no packages installed, processes stopped, containers/images deleted or files removed. Machine inventory: `ROOT/results/handoff-cleanup-inventory.json`, where ROOT is `/home/user2/software-factory-spark-20261113`. Inventory contains path/size/process/image metadata, not process environments or credential contents. Sizes below are allocated bytes from `du -sx -B1`, expressed as GiB/MiB; nested rows overlap and must not be summed.

## Current disk inventory and proposed disposition

| Path relative to ROOT unless absolute | Measured allocated bytes | Approximate size | Disposition |
|---|---:|---:|---|
| ROOT |27,168,854,016|25.30GiB|Keep until portable exports and evidence are verified offhost|
| `sources/` |2,603,663,360|2.42GiB|Keep selected source snapshots, git patches/bundles and revision manifests; historical duplicate checkouts can be reconsidered after archive|
| `mission-store/` |1,076,994,048|1.00GiB|Keep durable DB, evidence, CC releases, attempts and telemetry; build trees may be separated only after evidence/archive checks|
| `port-store/` |744,751,104|710.25MiB|Keep provenance/evidence; most space is intermediate builds|
| `results/` |919,158,784|876.58MiB|Keep real measurements and reports; synthetic test scratch classified below|
| Test/scratch directories in `results/` selected by name containing `test` or ending `-tmp` |464,494,592|442.98MiB|Remove-after-archive candidates; name match alone is not deletion authority|
| `agent-build-context-001/` |1,556,586,496|1.45GiB|Remove only after corresponding image archive is verified offhost and source/manifests are retained|
| `builder-build-context-001/` |5,912,846,336|5.51GiB|Same condition; includes copied system/toolchain content|
| `incoming/` |893,378,560|852.00MiB|Review duplicate staging/download payloads after archive; retain origins/checksums|
| `cache/` |13,371,297,792|12.45GiB|Mixed build cache and owned model; not one disposable class|
| `cache/owned-model/` |12,109,578,240|11.28GiB|Historical GPT-OSS private test copy; eligible only after retained provenance and decision that rerunning those probes is unnecessary|
| `exports/` |29,822,976|28.44MiB|Keep and verify against the portable archives|
| `venv/` |40,927,232|39.03MiB|Project-local environment; recreate rather than relocate binary virtualenv unchanged|

Build contexts are not safe to delete merely because image tags currently exist. Tags can move and local images can be pruned. The required condition is an image archive verified offhost, retained immutable image IDs and source/build manifests, and no active build/use of the context. No cleanup was executed by this audit.

The large owned-model file is `cache/owned-model/gptoss20.gguf`, logical size 12,109,566,624 bytes. Its source is `/home/user2/ai4r-data/inference-v3/models/gptoss20/gpt-oss-20b-MXFP4.gguf`. `tools/inference_probe_v3.py:19` copies the source to a distinct owned inode, verifies its hash, and applies file-local cache advice for historical memory/I/O probes. Current stat shows distinct inodes 62396285 versus 57956402, with owned-copy link count 1. The current DeepSeek benchmark uses the external DeepSeek pack/model tree, not this GPT-OSS copy. This audit did not rehash 12 GB to re-establish content equality; the copy/verification mechanism and retained run evidence establish its recorded purpose.

## Dependencies outside ROOT: retain shared resources, fix relocation assumptions

| External path | Measured allocation | Role and relocation issue |
|---|---:|---|
| `/home/user2/rsi-expert-streaming-001/factory-env` |1,504,702,464bytes|Private host Python environment used by preparation/host workflows; outside project root. Record distribution metadata and recreate explicitly on a new host. Not a global installation.|
| `/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq` |987,136bytes|Shared durable queue. Export only this campaign's records; do not delete shared queue or copy it as a live queue to a new host.|
| `/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source` |Symlink; target726,687,744bytes|Resolves to `/home/user2/rsi-expert-streaming-spark-002/lab-source`. Jobq/build recipe dependencies must be bundled or explicitly configured; archiving the symlink alone is insufficient.|
| `/home/user2/strata-baseline/Strata/.venv-build` |242,569,216bytes|Build tools referenced by `submit-build.py` and `start-bridge.sh`; archive images/toolchain recipes or recreate, rather than assuming this path exists.|
| `/home/user2/strata-baseline/Strata-data/models` |256,817,086,464bytes,239.18GiB|Actual DeepSeek shards, shared Engram and draft weights outside ROOT. Model transfer/reacquisition is a separate prerequisite for engine reruns.|
| `/home/user2/strata-baseline/Strata-data/packs/deepseek-v4.1-flash-ist-das-2.00bpw` |8,912,896bytes|Small pack descriptors/tokenizer/profile, not the full model. Copying this directory alone does not make inference portable.|

`assets/deepseek-full-identity-v1.json` lists the six external GGUF assets and hashes. Its historic `full_hash_verification` field is recorded evidence; this audit read the manifest and current directory metadata but did not rehash 239 GiB. The inventory retains the contract's identity-path/hash reference.

Concrete absolute dependencies remain in `deploy/spark/factory-container.sh`, `compare-benchmark.py`, `start-bridge.sh`, `submit-build.py` and benchmark/asset contracts. `run-mission.py` exposes queue-path overrides, but default paths still target this host. Existing admitted contracts and hashes must stay immutable: use them for archival analysis; generate separately versioned contracts to rerun at relocated paths.

The checkout's `.git` is a worktree pointer to `/home/user2/dev/jiuwenswarm/.git/worktrees/cc-dgx-spark`. A bare directory copy does not preserve an independent git repository. Preserve final tracked source, untracked authored materials, patch and revision metadata, and an appropriate git bundle/archive. Do not package only the `.git` pointer.

Both project and private factory `pyvenv.cfg` show Python 3.12.3 with `include-system-site-packages=false`. Inventory records virtualenv distribution metadata names for reconstruction. The inspected `/home/user2/.local/lib` did not exist; `/usr/local/lib/python3.12/dist-packages` existed with no top-level `*.dist-info` directories. These narrow present-time clues do not prove the absence of historic global/user installs, installations elsewhere, or changes by earlier sessions. No historic package baseline or administrator audit trail was compared.

## Docker and processes: shared resources remain untouched

At snapshot Docker reported 53 images, 108 containers, 10 volumes and 191 build-cache entries. Aggregate daemon accounting was 98.58 GB images (44.48GB reclaimable),20.61MB containers,8.983GB volumes and29.2GB build cache (11.86GB reclaimable). These are daemon-wide totals, not attributable cleanup savings for this project.

Two containers were running: `ai4r-spark-ai4r-1` and `buildx_buildkit_ai4r-spark-builder0`, both shared and without ROOT bind mounts. No container with a ROOT bind mount was present at the observation. Process metadata found Codex application/control processes; this is not an authorization to stop them. The check did not inspect process environments or print full argument lists. Recheck state immediately before any later cleanup because the snapshot is not a lease or future guarantee.

Selected image inspection confirmed ARM64 images for Strata, agent, CLI and CLI-test. Strata and agent share 15 filesystem layers; CLI and CLI-test share 22 layers. Image-list apparent sizes and inspect Size fields differ on this daemon, and neither is a direct independent reclaimable-space estimate. Preserve exact image IDs and layer metadata in the image export manifest; do not add per-tag sizes or run broad `docker system prune`, image pruning or volume pruning. Older `factory/llamacpp:spark002-*` images and stopped `strata-rsi-*` containers are prior shared campaign resources and remain untouched.

The handoff includes a separate ARM64 image archive for agent/builder/CLI/Strata plus a smaller source/evidence review bundle. An off-Spark host can review JSON, raw logs, analysis, sources and methodology tests with recreated CPU dependencies. Reproducing engine measurements additionally requires compatible ARM64 NVIDIA hardware/CUDA, model assets, imported immutable images, configured queue/executor and fresh authorized contracts. Neither portable archive alone asserts cross-platform runtime qualification.
