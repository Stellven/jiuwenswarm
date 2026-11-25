# Expert fill builder: guide for the worker

**Expert fill** is the demand-driven part of expert streaming (atlas `engine.expert_streaming`, subcomponent
`expert_fill`): once a layer's router has chosen its experts, read those experts' bytes that are not yet in
memory with several reads in flight, before the expert matmuls fault them in one page at a time. This capsule
is the method for building that into whatever llama.cpp tree is in front of you, plus the verifier that judges
the result. It ships no finished change; `tests/fixtures/good.diff` exists only to calibrate the verifier.

## Why (Muse Spark Open on a DGX Spark)

- 816B MoE, 62 layers x 256 experts, Q2_K pack 304.7 GB on a 128 GB unified-memory GB10 with ~7 GB/s NVMe.
  Run as `llama-server -lm mmap --cpu-moe --moe-cache-mib 61440 -c 4096 -np 1` under a 96 GiB cgroup.
- Decode is ~0.8 tok/s in every arm and SSD-bound: the CPU `MUL_MAT_ID` reads each selected expert straight
  from the file mapping, and each first touch of a missing page is a major fault serviced synchronously on the
  compute thread, with readahead tuned for sequential access. Effective queue depth is about one.
- NVMe wants queue depth. The fill turns "fault, wait, fault, wait" into N parallel `pread`s of the selected
  experts' missing ranges, issued between routing and the matmul. The matmul then takes minor faults.

## The change, in words

A gate (`LLAMA_EXPERT_FILL`, default off). When on: a hook that sees each layer's selected expert ids before
the expert matmuls run; per selected expert and expert tensor, the byte range in the mapped file; a residency
probe (`mincore`) to skip pages already resident; a fixed pool of reader threads doing buffered `pread`s into
scratch buffers; the hook waits for the pool, then the graph continues. One activation line when the context
starts, one stats line when it ends. Decode ubatches only by default. Nothing in the computation changes.

## Rules of thumb

1. **Before the matmul, not after.** The stock eval callback fires *after* the node it asked for. Key on the
   router output (`ffn_moe_topk-<il>`), never on `ffn_moe_{up,gate,down}` or a `MUL_MAT_ID` node in that
   callback. If you build a before-node scheduler hook instead (the expert_streaming 2.x route), say so in the
   change; the static rule recognizes `set_cpu_callback`-style hooks.
2. **Warm the page cache, never the tensor.** `pread` into your own buffer. No `ggml_backend_tensor_set`, no
   stores through `->data`, no `MAP_PRIVATE`/`PROT_WRITE` remaps. Values must be byte-identical.
3. **Off means stock.** Unset gate: no hook installed, no threads, no lines in the log.
4. **Chain the eval callback.** It is the same slot `llama-eval-callback` and imatrix use; call theirs too.
5. **Skip what you cannot serve.** Device-resident experts (no host buffer) and repacked copies (not a file
   mapping) are counted (`unmapped`) and skipped, not failed.
6. **Measure decode separately.** verify proves correctness and engagement on a tiny pack. Whether decode gets
   faster on the 304.7 GB pack is a lab A/B against the stock-as-documented baseline (see the expert_streaming
   capsule's AB.md and EVIDENCE.md: fewer faults or more bytes read do not imply lower ms/token).

## Samples (labelled starting points)

- `samples/router_hook.cpp` - the eval-callback chain at `ffn_moe_topk-<il>` and how to turn ids into ranges.
- `samples/read_pool.h` - the pread pool, the `/proc/self/maps` address-to-file lookup, the `mincore` probe.
- `samples/acceptance_run.sh` - the parity, marker, stats and perplexity runs verify makes, by hand.

See METHOD.md for the steps, SOURCE-MAP.md for anchors and allowed paths, VALIDATION.md for the gates.
