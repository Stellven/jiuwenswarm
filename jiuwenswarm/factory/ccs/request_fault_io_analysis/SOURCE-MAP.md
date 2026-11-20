# Source map

| Source and anchor | Use |
| --- | --- |
| JiuwenSwarm `abb89f285`, `ops/spark/request_resources.py`, SHA-256 `21cd74eb72f7c8b852cabc405f59024bb9f7b52b33e6a22febd0da8d3dbb8a9e` | Read-only cgroup, process and host disk collection. Device read sectors use 512-byte units. |
| JiuwenSwarm `abb89f285`, `ops/spark/bench_http.py`, SHA-256 `695818e75a3eabe6ceffba2858970639ff30e91604f6b89a3164223c165242df` | Capture start, first response token and end windows. Record the exact resource artifact hash in the result. |
| Linux kernel cgroup v2 reference for `memory.stat` and `io.stat` | Cgroup fault, file-page refault, reclaim and bytes-per-device scope. |
| Linux kernel proc reference for `stat` and `io` | Process identity, faults, read bytes and the distinction between storage and syscall data. |
| Linux kernel disk I/O statistics fields | Cumulative device read counts and reset behavior. |

[Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), [Linux proc filesystem](https://docs.kernel.org/filesystems/proc.html), [Linux disk statistics](https://docs.kernel.org/admin-guide/iostats.html)

The periodic calibration analysis also binds the completed calibration engine stderr. In the Spark run, `slot print_timing` emits task/slot, cumulative `n_gen` and rate, so repeated values can be excluded and the progress reset identified independently. The calibration report pins both that log and the cumulative JSONL counter trace.
