# C2 held-out layer-27 placement functional lab

Exactly three layer-27 expert tensors moved to CUDA0, the other 117 stayed on CPU, and both greedy output pairs matched across all three launch modes.

| Selected tensor | Actual buffer | Payload bytes |
|---|---|---:|
| `blk.27.ffn_gate_exps.weight` | CUDA0 | 1,309,409,280 |
| `blk.27.ffn_down_exps.weight` | CUDA0 | 990,904,320 |
| `blk.27.ffn_up_exps.weight` | CUDA0 | 1,309,409,280 |

The selected payload totals 3,609,722,880 bytes. The instrumented gate-enabled launch provided per-tensor readback. Both controls used the equivalent explicit placement allowlist and logged no component markers.

| Scope | CUDA0 model buffers | Launch to ready | Peak cgroup memory |
|---|---:|---:|---:|
| equivalent-stock | 8882.92 MiB | 68.11 s | 54.75 GiB |
| off | 8882.92 MiB | 68.11 s | 62.66 GiB |
| on | 8882.92 MiB | 87.13 s | 61.72 GiB |

Gate-on CUDA0 allocation differed from equivalent stock by +0.00 MiB and from gate-off by +0.00 MiB at log precision. These are equivalent-policy comparisons.

| Scope | Prompt tokens | Client TTFT | Server prompt | Server decode | Decode tok/s |
|---|---:|---:|---:|---:|---:|
| equivalent-stock | 512 | 59.70 s | 59.67 s | 8.61 s | 3.60 |
| equivalent-stock | 2048 | 45.89 s | 45.87 s | 7.06 s | 4.39 |
| off | 512 | 66.37 s | 66.34 s | 9.58 s | 3.24 |
| off | 2048 | 64.13 s | 64.11 s | 7.27 s | 4.26 |
| on | 512 | 63.40 s | 63.37 s | 9.40 s | 3.30 |
| on | 2048 | 82.38 s | 82.36 s | 7.05 s | 4.40 |

- At 512 tokens, gate-on minus gate-off was -2.97 s in server prompt processing and -0.18 s in server decode.
- At 2048 tokens, gate-on minus gate-off was +18.25 s in server prompt processing and -0.22 s in server decode.

Each scope issued one discarded request per size, with zero cached prompt tokens and 32 greedy generated tokens. These phases were collected during the functional window, which overlapped other work. The timings are descriptive and cannot isolate a performance effect.

- 512 prompt tokens matched across all modes. Content SHA256 `ff3f7037d306cd94961a2e3627e1bf75ab683c7f0d29152afb70a319ffd74fba` and reasoning SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- 2048 prompt tokens matched across all modes. Content SHA256 `07a7579baa3338e7d11cf9133571974efc69ca9f0734eece2dc776a3732a1768` and reasoning SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Compare the equivalent policy with matched quiet stock endpoints first. Use a separately labeled strict-A comparison to quantify the placement policy itself. Retain the layer-27 readback as an activation check for the next placement decision.

Native analysis and deterministic verification used sealed release `4c6deb7a4c7f813255bdaf0a82c586ef098d72df8e0fccac877f3a2b8b906e39`. The retained lab and analysis are `spark-c2-layer27-functional/lab.json` and `spark-c2-layer27-functional/analysis.json`.
