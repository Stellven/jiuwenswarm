# Spark overnight operations

The live wrappers are linked from `~/predemo-spark/bin/`. Run:

```
bin/quiet
bin/capped --arm A --result-dir OPS/runs/unique-run-id -- /absolute/path/to/llama-server -lm mmap --cpu-moe ...
```

`capped` requires the single GPU flock and 110 GiB MemAvailable. It creates a user systemd scope with MemoryMax=100 GiB, MemorySwapMax=0, AllowedCPUs=0-7 and CPUQuota=800%. Before exec, the scope member verifies kernel memory, swap, OOM-group and CPU quota controls, sets and verifies affinity to CPUs 0–7, and waits for the external watchdog handshake. The watchdog kills the entire scope when available memory falls below 8 GiB. Signals kill the scope too. Unexpected oom/oom_kill or watchdog events append a STOP to OPS status and blockers; the operator must review before continuing.

This machine does **not** delegate the cpuset controller to the user manager. AllowedCPUs is requested but cannot take effect here. Verified affinity plus the kernel eight-CPU bandwidth quota provide the effective CPU restriction. The orchestrator approved this deviation in the terminal on 2026-11-20. No sudo is used.

Each invocation records command, executable digest, timestamps, cgroup controls, stdout, stderr, sampled RSS, sampled kernel memory peak and a final result, with start/stop ledger rows. Kernel memory peak is sampled every 50 ms; scope teardown can lose the last interval, and this systemd version reports MemoryPeak as unset. Do not describe the sampled value as an exact final peak. GB10 CUDA/UMA driver allocations may escape cgroup accounting; host MemAvailable is the real backstop. The result records its minimum. Reclaim-only memory.max events are informational, as approved by the orchestrator. Result=oom-kill is retained independently by systemd and is required by the enforcement test.

```
bin/capped --arm P0-enforcement --result-dir OPS/runs/unique-test-id --enforcement-test
```

The test exclusively runs the built-in gradual 256 MiB allocator with the same scope controls but a 128 MiB memory cap. It passes only when the scope was verified and an OOM kill is observed. It cannot run arbitrary commands at a reduced limit. Failed preliminary tests remain in OPS/runs and the ledger.

The initial gate was approved on 2026-11-20. For a fresh campaign, do not start DeepSeek or Strata until `P0 READY FOR REVIEW` has been written to OPS/STATUS.md and the orchestrator has approved in the terminal. The first load of each engine and any unexpected memory event have separate review stops in BRIEF.md.

The native tuner must use `bin/tune-server` in place of llama-server. This preserves per-load locking, capping, engine log forwarding and ledger rows and refuses cache sizes above 61440 MiB. Keep its `--out` unique: the upstream tuner deletes entries if a reused directory has a different command.
