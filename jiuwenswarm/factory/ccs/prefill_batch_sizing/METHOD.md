# Prefill batch sizing

**Builds:** the llama-server batch settings (`-b`, `-ub`) for a MoE model whose routed experts stay on the
CPU side (`-lm mmap`, `--cpu-moe`, optionally a GPU `--moe-cache-mib` cache) and stream from the SSD.

## Why it matters

Prompt processing runs in physical micro-batches of `n_ubatch` tokens (default 512). With CPU-resident
experts, each micro-batch offloads the expert matmuls to the GPU and streams every routed expert it touches
again. A long prompt touches nearly all experts in every micro-batch, so prefill time grows with the number of
micro-batches, not with the number of tokens.

Measured on the DGX Spark (Muse Spark Open, Q2_K pack, 304.7 GB; 60 GiB MoE cache; 96 GiB cgroup cap):

| prompt | ubatch 512 | ubatch 2048 |
|---|---|---|
| 511 tokens, warm TTFT | 100 s | 95 s |
| 2047 tokens, cold TTFT | 311 s | 120 s |
| 2047 tokens, warm TTFT | 295 s | 112 s |

Decode speed is unchanged (single-token batches).

## Steps

1. Load the server once at the current batch with the exact model, context, cache and placement flags, at
   `-lv 4`, under the memory cap. Keep its log (it prints `n_batch`, `n_ubatch` and every device buffer).
2. Call `plan` with that log, the prompt sizes the workload sends and the device budget. It picks the
   smallest power of two that covers the longest prompt (capped by `n_ctx`) and halves it while the estimate
   exceeds the budget. The default estimate keeps the measured model, MoE cache and KV sizes and scales
   the compute buffers linearly with the ubatch. With `measured_reference`, the exact candidate batch uses
   the fresh default load's measured device buffers plus the historical change in KV and in CUDA and host
   compute. Other batches use the default estimate.
   The baseline load must use the target context: KV and the attention part of the compute buffer grow with
   `n_ctx`, so `plan` fails `baseline_context` when the target is larger than the log's.
3. Load the server with the plan's `args` added (same everything else, same cap) and run the same requests
   the baseline ran: one cold and at least one warm per prompt size, greedy, a fixed seed.
4. Call `verify` with the plan, the new log and the two sets of rows.

## Measured reference for the Muse mixed 2-bit pack

Use the fresh capped mixed-pack log as `baseline_log`. The historical Q2_K logs from November 25 at
`/home/user2/muse-demo/lab/B.stderr.log` and `/home/user2/muse-demo/lab/Bub.stderr.log` can be passed as
`measured_reference.baseline_log` and `measured_reference.candidate_log`. They are stock build `9048bad8d`
loads at context 4096, one sequence, logical batch 2048, and ubatch 512 and 2048 respectively. The separate
`C.stderr.log` and `D.stderr.log` pair from build `56afc3581` measured the same deltas. Each reference pair
uses one build and cache size.

| Buffer | ubatch 512 (MiB) | ubatch 2048 (MiB) | Increase (MiB) |
|---|---:|---:|---:|
| CUDA0 KV | 716.00 | 992.00 | 276.00 |
| CUDA0 compute | 1538.51 | 2128.05 | 589.54 |
| CUDA_Host compute | 70.53 | 288.10 | 217.57 |

The increase in KV is in the sliding-window buffer. The previous mixed load at
`graph-v4/runs/fd07412594dd4491864b5fddfbf37b2f/server.log` matched the reference at ubatch 512 for all
three buffers and for the GPU model allocation, board, architecture, KV layout and scheduler graph. Its
expert weights and cache slots differed, so the estimate uses the fresh mixed load's model and does the
cache calculation for the target budget. With a budget of 110000 MiB, headroom of 2048 MiB and prompts of
511 and 2047 tokens, the historical mixed log projects `-b 2048 -ub 2048 --moe-cache-mib 66560` and
107364.8 MiB before expert slot rounding.

This is a cross-pack planning estimate. The exact candidate buffer usage on the mixed pack is measured
by the fresh planned load. The plan records each input log's SHA-256, log-reported model and build, batch
and allocations. The planner checks layout and measured default allocations. The caller supplies the
provenance of the fresh capped runs and uses their request rows for `verify`.

## Budget

On GB10 the CUDA buffers live in the same unified memory as everything else, and they are not charged to the
cgroup the way page cache is. Budget the sum of the device buffers against physical memory left after the
OS and a page-cache margin for the streamed experts (the Muse contract pins 110,000 MiB of 121 GiB). The cgroup
cap still bounds the host side; the lab samples it separately.

## Outputs

A different micro-batch split changes the order of float sums in prefill, so greedy text can diverge after a
while even though nothing is wrong. On Muse the 511-token outputs stayed byte-identical and the 2047-token
outputs matched for 136 characters, then took a different, equally coherent path. `verify` accepts
byte-identical outputs or a common prefix of at least `min_agree_chars` (default 64). It does not measure
quality; use a KLD run against the default batch when quality matters more than this sanity check.

## When it does not help

- Experts fully resident on the GPU: micro-batches no longer re-stream weights; gains are small.
- Many short prompts: they already fit one micro-batch.
- A budget too tight for one micro-batch per prompt: fewer, larger micro-batches still help; `plan` halves
  until it fits and reports the micro-batch counts.
