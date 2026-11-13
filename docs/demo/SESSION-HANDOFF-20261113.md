# Session handoff — 2026-11-13 (safe to clear context)

## State
- Branch `cc-siminfeng` and tag `cc-demo-incremental-v1` pushed to `git@github.com:Stellven/jiuwenswarm.git` (HTTPS has no creds; push via the ssh URL).
- Stable RSI capsule `cc-rsi-v1` untouched (`factory/ccs` diff empty). Run 5 shelved.
- Demo deliverables: `artifacts/factory/demo-incremental/` (start with `RESULTS.md`, `CC-VS-RAW-PERF.md`, `LAUNCH-REPLAY.md`, `RSI-HANDOFF.md`). Decision trail: `docs/demo/WORKLOG.md`.
- Fill result is PRELIMINARY (gate null twice). Confirmed evidence is the historical J-OM13 (fill+pregate, 841.5 -> 711.4 ms/tok).

## Features added this session (jiuwenswarm `factory`)
Crash-safe resume (active-time budget, new session `<task>-sN` with context), `factory baseline-import`, `factory note`,
`demo_record.sh` starts+verifies the jobq worker. 292 tests pass.

## Gotchas
- Shared `siminfeng/lab/jobq` needs a running `bin/jobq worker`; it dies on reboot and nothing restarts it.
- Crash at ~00:47 on Nov 13: no panic/OOM/thermal logs, no pstore. Likely power or hard freeze. Check PSU; enable persistent journald.
- No RTC: clock jumps after boot; don't trust wall time across reboots.
- Disk: / was 90% full (12 GB free) — `DISK_SPACE_LOW` aborted attempt 1. Prune old images/builds.
- ffmpeg: `/home/muk/.cache/uv/archive-v0/xxLhdxjOJ0qcnJDE/imageio_ffmpeg/binaries/ffmpeg-linux-aarch64-v9.0.2`; venv `~/venvs/present`.

## Open / optional
- Confirm fill: quieter host, more ABBA rounds. Run expert_pregate on the quick contract.
- Future capsule candidates: adaptive expert-read policy, workload-aware CPU/GPU placement, KV-cache/context-memory management.
- USB drive `Danta` (/dev/sda1, exFAT, 57.7 GB) attached but NOT mounted (needs sudo): `sudo mkdir -p /mnt/danta && sudo mount -o uid=1000,gid=1000 /dev/sda1 /mnt/danta`, then copy
  `artifacts/factory/demo-incremental/`, `~/.jiuwenswarm-factory/` and `siminfeng/experiments/jetson/OM/J-OM13` (see below).

## Disk cleanup (done, approved)
Removed 12 superseded docker image tags (kept bare-cf34d311, incremental4-fill, bd173c08-restored/pregate, om11, d4b71bcc-thread-names-1),
pruned build cache >72h, removed 5 side worktrees (branches pushed first: ai4r/ccv2-revise, ai4r/contract-loop, ai4r/demo, ai4r/f15-taskgraph, c2/heavy-guard).
Root 90% -> 85% (18 GB free). Biggest remaining: ~/models (38 GB), docker images ~10 GB. Local backup: `~/backup/demo-session-20261113.tgz`.

Models removed (approved): qwen35-9b, gemma4-e4b, granite HF dir + bf16/mixE4K ggufs. Kept: qwen36-35b-a3b, granite Q8_0 (CPU config probe), kl, data. Root now 71% (33 GB free). Re-download via `models/campaign/MANIFEST.jsonl` repos if needed.
