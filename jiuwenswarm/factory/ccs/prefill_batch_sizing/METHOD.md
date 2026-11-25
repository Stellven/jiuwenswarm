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
   exceeds the budget. The estimate scales the ubatch-dependent buffers (compute, host compute, KV padding)
   linearly, which overestimates them. Measured: compute buffer 1538.5 MiB at 512, 2128.1 MiB at 2048.
3. Load the server with the plan's `args` added (same everything else, same cap) and run the same requests
   the baseline ran: one cold and at least one warm per prompt size, greedy, a fixed seed.
4. Call `verify` with the plan, the new log and the two sets of rows.

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
