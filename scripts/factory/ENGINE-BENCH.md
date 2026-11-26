# Muse Spark Open benchmark data

Generate `~/muse-demo/bench/engine-bench.jsonl` from the Spark receipts.

```sh
python3 scripts/factory/normalize_engine_bench.py
```

The generator reads receipts, logs and shard metadata using Python's standard library. After the Phase 4 lab has exited, add `--phase-four-report ~/muse-demo/lab/v4-fast/report.json` to incorporate the real B/P rows. The output is replaced atomically.

Each `engine-bench/1` row has a stable ID, run cohort, arm and kind. `source` points to the original file and JSON Pointer or 1-based log line. `sources` identifies supporting receipts. Digests are SHA-256 over file bytes. `raw` preserves the source values used for the normalization. When a historical pack lacks a manifest, size is obtained from the filesystem metadata of its complete shard set. File size and BPW stated by llama.cpp are retained on load rows when available. `pack.census_digest` hashes the server's type-to-tensor-count object encoded as compact, key-sorted JSON. `pack.manifest_sha256` identifies the shard manifest separately.

| Run | Sources and scope |
|---|---|
| `nov24-lab-abc` | `lab/report.json` is the Spark copy of the Nov 24 overnight A/B/C lab. The original A/B/C server logs were superseded locally by the Nov 25 files, so device details tied to the earlier loads are blank. |
| `nov25-lab-abcde` | `lab/report-abcde.json` and `lab/{A,B,C,D,E}.stderr.log`. Use only this cohort's A for the historical 512/2048 baseline. A used the expert-scale-wired stock build at 9048bad8d on NVFP4, ctx 4096 and 128 requested output tokens. E is the expert-fill arm. |
| `nov25-probe-d`, `nov25-probe-ub2048` | `lab/probe-D.json` and `lab/probe-ub2048.json`. The latter has its own `Bub.stderr.log`. The later D log belongs to the A–E lab and cannot establish the earlier probe's allocations. |
| `nov25-size-probe` | `lab/report-sizes.json` and `A-sizes.stderr.log`. Short-length historical A trials at 128/1024 nominal prompt tokens. |
| `nov25-agent-sweep` | `lab/sweep-agent.json` and `{A,B,C,D}-agent.stderr.log`. Context 33792, 49152 MiB requested cache. The fitted rows preserve the source's estimated decode and raw prefill-pass duration. Agent-turn `prompt_tokens` counts the tokens processed on that turn, with cached tokens recorded alongside. |
| `nov24-smoke` | `smoke/e0-nvfp4.json` and `smoke/e0-nvfp4.stderr.log`. NVFP4 response and loading evidence. |
| `nov25-mmlu-q2` | `acc/state.json` and `acc/run.log`. The final 250-question paired look reports NVFP4 94.0%, Q2_K 93.2%, signed delta −0.8 points, interval [−4.71, +2.88] points and a five-point non-inferiority pass. Published checkpoints are paired even though one arm scored ahead of the other. |
| `r8-smoke` | Capped `graph-r8/runs` evidence. One NVFP4 smoke and eight mixed 2-bit smoke requests. These are separate from B/P. |
| `r8-prefill-calibration` | Two capped `graph-r8/runs` loads, each with two repetitions at p512 and p2048. CAL-P's log reports checkpoint segments 507+4 and 2043+4. Checkpoint segment counts do not establish the total physical micro-batch count. |
| `r8-lab` | Requires the explicitly supplied, completed Phase 4 report and its B/P server logs. The report contains immutable image, binary and pack identity, observed request timings, and per-row quiet samples. |

`request.prompt_tokens` is what the server reported. Nominal p512/p2048 labels are 511/2047 server tokens. `metrics.ttft_ms` uses client first-token timing, while `server_prefill_ms` uses the server's reported prefill duration. Values and units are retained as milliseconds, seconds or tokens per second as the field names indicate. Comparisons of request totals need matched output lengths. Cross-campaign comparisons are indicative.

Memory values are MiB. `peak_rss` represents the server process's measured RSS and is null where the source lacks it. `peak_cgroup_mib` is the separate sampled cgroup memory peak. `min_available` is the sampled host MemAvailable floor. Device components are logged CUDA allocations. `memory.fit_margin` is the difference between the budget and the sum of the four logged device buffers, when all are known. `settings.fitt` is the launch-time free-memory target, in MiB. Historical A's 110000 MiB budget comes from BENCH-PLAN §2.

`quiet.eligible` is true for accepted quiet evidence, false for an explicit exclusion, and null for missing row-level quiet evidence. The quiet summary calculates the peak observed one-minute load across all samples and includes the sample count. It groups process observations by name, kind, state and lab ownership, with the 24 most relevant groups shown and the omitted group count recorded. The `quiet.source` pointer leads to the complete original snapshots in the lab report. Accuracy, signed delta, interval and margin use fractions. Measured and indicative labels identify the underlying evidence independently of quiet status.
