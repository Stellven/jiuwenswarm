# CC-guided vs raw llama.cpp — Qwen3.6-35B-A3B on Jetson Orin Nano 8 GB (`satay`)

"Raw" = plain image `factory/llamacpp:bare-cf34d311` (llama.cpp `cf34d311`, no patches, stock mmap page-fault behaviour).
"CC" = engine built by the agent using the `engine.expert_streaming` capability capsule.
Metric: decode ms/token (tokens/s). Startup/prefill excluded. Output must match the frozen reference.

## What "fill" is
`expert_fill` = demand-driven expert fill. The 35B MoE does not fit in 8 GB, so expert weights stay in the mmap'd GGUF and
are read from NVMe on demand. Stock llama.cpp lets the compute thread take page faults one page at a time. Fill instead
makes a bulk read of the experts the router just selected, using parallel worker threads (`xfill-N`, 16 threads, 2 MiB
chunks), with a synchronous per-layer barrier. Switch: `LLAMA_EXPERT_FILL=1`.
`expert_pregate` (predictive reads) is a second component that starts reads for experts predicted for the next layer.
`mmap_advice` and `router_prefetch` are source prerequisites only, not active.
Known limit: fill is synchronous, so IO does not overlap compute (J-OM9: 29.0 s in fill vs 24.8 s between fills).

## Results
| Workload | Raw | CC build | Ratio | Gate | Status |
|---|---|---|---|---|---|
| 64 tok, J-OM13, 12 runs | 841.5 ms/tok (1.19 tok/s) | fill+pregate 711.4 (1.41) | 1.183 (thr 0.080) | improved | **CONFIRMED** |
| 64 tok, Run 4 | 903.95 | 785.22 | 1.151 | one run/endpoint | recorded fallback |
| 32 tok, ABBA 1 round | 903.98 (1.11) | fill only 839.69 (1.19) | 1.077 (thr 0.078) | null | PRELIMINARY |
| 32 tok, ABBA 3 rounds | 956.92 (1.05) | fill only 854.44 (1.17) | 1.120 (thr 0.257, A/A 0.128) | null | PRELIMINARY |

Output is identical to the reference in every run. 32-tok and 64-tok are different workloads; never combine or multiply ratios.
Honest read: fill alone is about 7-12% faster in both fresh ABBAs, but the host noise (A/A 12.8%) is too high to confirm.
Fill + predictive reads is the confirmed result: 841.5 -> 711.4 ms/token (-15.5% time, 1.183x speed).
Engagement: fill counters 6.27 GB read, 1,240 decode fills. Contract-level engagement checks read 0/2 only because the
fill-only build lacks patch 08/09 logging.
