# Expert-streaming source map

Checkout revision read: `0b514fba8` = `cf34d3113` + patches 01..08.

Source read: integrated checkout `/home/muk/.jiuwenswarm-factory/agent-workspace/llama.cpp`, HEAD `0b514fba8`
("Revert worker names"). Its log: 93a61111e (01 mmap advice), 5cded3e76 (02 router prefetch),
c0427fe6c (03-05 fill), 6e9d96cf4 (06-08 pregate), 133b42aed (09 thread names), 0b514fba8 (reverts 09).
So HEAD = base + patches 01-08; patch 09 (`pthread_setname_np("xfill-N")`) is NOT in HEAD (verified: no `setname` in
`src/llama-expert-fill.h`). All line numbers below are from HEAD unless prefixed `base:` (cf34d3113).
Patches: `/home/muk/projects/jiuwenswarm/jiuwenswarm/factory/ccs/expert_streaming/components/{mmap_advice,router_prefetch,expert_fill,expert_pregate,thread_names}/`.
Diffstat vs base: ggml-backend.{h,cpp}, llama-context.{h,cpp} (+675), new `src/llama-expert-fill.h` (545 lines),
llama-mmap.cpp, llama-model-loader.cpp, llama-model.{h,cpp}. Nothing in ggml-cpu, ggml-cuda, llama-graph, models/.
Not run-verified: everything here is from reading source; nothing was built or executed.

## 1. Stock behaviour at cf34d311 for `-ngl 99 -cmoe -lm mmap`

**Argv.**
- `-cmoe/--cpu-moe` -> `common/arg.cpp:2731-2735` pushes `llm_ffn_exps_cpu_override()` (`common/common.h:1267`) =
  `{LLM_FFN_EXPS_REGEX, ggml_backend_cpu_buffer_type()}`. Regex (`common/common.h:1259`): `\.ffn_(up|down|gate|gate_up)_(ch|)exps`.
  It is a tensor-buft override: tensors whose name matches get the plain CPU buffer type (NOT the repacked/extra CPU buft).
- `-lm mmap` -> `LLAMA_LOAD_MODE_MMAP` (`common/arg.cpp:2673`); `llama_model_loader` sets `use_mmap` (`src/llama-model-loader.cpp:567`).
- MoE cache (`-cmoe-cache`-style `moe_cache_size`, default 0 at `llama-context.cpp:4951`) is off, so
  `build_moe_cache_slots` yields no slots and `ggml_mul_mat_id(w, cur, ids)` is used directly (`llama-graph.cpp:1764`).

**Load/mmap path.**
- `llama_model_base::load_tensors` (`src/llama-model.cpp`) -> `ml.init_mappings(true, ...)` (`llama-model.cpp:1995`; prefetch=true).
- `llama_model_loader::init_mappings` (`llama-model-loader.cpp:1426`) builds one `llama_mmap` per GGUF file with
  `prefetch_size = prefetch && use_mmap ? -1 : 0` (`:1458`).
- `llama_mmap::impl` (`src/llama-mmap.cpp:483`): `posix_fadvise(SEQUENTIAL)`; `MAP_POPULATE` if `prefetch && lazy_ranges.empty()`;
  `mmap(PROT_READ, MAP_SHARED)` of the whole file at offset 0; `POSIX_MADV_WILLNEED` over non-lazy ranges.
  (On an 8 GB box with a 20.8 GiB file the MAP_POPULATE/WILLNEED outcome is kernel-dependent; not verified here.)
- Buffers (`llama-model.cpp:2016-2060`): for each context/buft, if `ml.use_mmap && buffer_from_host_ptr && is_default_buft`
  (true for the CPU default buft; CUDA is `buffer_from_host_ptr=false`, `ggml-cuda.cu:5882`), it wraps the mmap region with
  `ggml_backend_dev_buffer_from_host_ptr`. `load_all_data` (`llama-model-loader.cpp:1729-1753`): for a tensor in a mmap-backed buffer,
  `ggml_backend_tensor_alloc(buf_mmap, cur, data)` with `data = mapping->addr() + weight->offs`, so
  **`ffn_*_exps->data` points straight into the file mapping**. Tensors on the GPU buffer take the `else` branch
  (`ggml_backend_tensor_set`, `:1766`) and are copied once from the mapping.
- After load `unmap_fragment` (`:1888-1895`) unmaps mapping bytes before the first and after the last host-mapped tensor
  (`mmaps_used`, `:1761-1763`), so the mapping can have holes (patch 06 therefore reads routers from the file, not from the mapping).
- Per-tensor file offset: `llama_model_loader::llama_tensor_weight{idx, offs}` (`llama-model-loader.h:32-44`),
  `offs = gguf_get_data_offset + gguf_get_tensor_offset`; stored in `ml.weights_map` keyed by tensor name.

**Router / expert selection** (Qwen3.6-A3B = `LLM_ARCH_QWEN35MOE`; `src/models/qwen35moe.cpp:474 build_layer_ffn` -> `build_moe_ffn`):
- `llm_graph_context::build_moe_ffn` (`src/llama-graph.cpp:2244`): `logits = mul_mat(gate_inp, cur)` (`ffn_moe_logits`),
  softmax gating `ffn_moe_probs` (`:2296-2303`), `selected_experts = ggml_argsort_top_k(selection_probs, n_expert_used)` (`:2364`),
  named `cb(selected_experts, "ffn_moe_topk", il)` (`:2367`) so the tensor name is `ffn_moe_topk-<il>`.
  Weights = `ggml_get_rows(probs, selected_experts)`, normalised after top-k (`norm_w=true`).
- Expert matmuls: `build_experts` lambda (`:2434`) -> `build_lora_mm_id` -> `ggml_mul_mat_id(w, cur, ids)` for `gate_up_exps` (merged) or
  `up_exps`, `gate_exps`, then `down_exps`. `src[0]`=expert weight tensor `[.., .., n_expert]`, `src[1]`=activations, `src[2]`=ids (I32 `[n_used, n_tokens]`).
- Scheduling: ops whose weights are in a CPU buffer run on the CPU backend; the ids tensor and the activation are
  split inputs, copied GPU->host by `ggml_backend_sched_copy_input` in `ggml_backend_sched_compute_splits` (`ggml-backend.cpp:2200-2225`) before
  the split is computed. So at the CPU MUL_MAT_ID, `ids` and `src[1]` are in host memory and valid.
- CPU consumption: `ggml_compute_forward_mul_mat_id` (`ggml/src/ggml-cpu/ggml-cpu.c:1566`): the first phase scans `ids` and builds per-expert row lists
  (`matrix_row_counts`, `~:1666-1680`), then for each *used* expert `src0_cur = src0->data + cur_a*nb02` (`~:1703`) and calls
  `ggml_compute_forward_mul_mat_id_one_chunk` (`:1495`) which dot-products rows directly from the mmap. Only used experts are touched; each first touch of
  a page not in the page cache is a major fault serviced synchronously by the touching compute thread (on this mapping with `POSIX_FADV_SEQUENTIAL`/default
  readahead unless advice changed). Pages already in page cache but without PTE are minor faults.

**Hook points the patches use.**
- New CPU-only before-node callback `ggml_backend_sched_set_cpu_callback` (`ggml/include/ggml-backend.h:332-338`, `ggml/src/ggml-backend.cpp:2240-2262`,
  `:2513-2517`; fields `:1226-1227`). In `ggml_backend_sched_compute_splits` a `compute` lambda walks the CPU split's nodes;
  for each node asks (`ask=true`) whether to observe; at an observed node it runs the preceding nodes as a `ggml_graph_view` prefix,
  `ggml_backend_synchronize`, calls the callback with `ask=false` ON THE CALLING (main) THREAD, then continues from that node
  (the observed node is included in the next view). Only for devices of type CPU. The pre-existing `ggml_backend_sched_eval_callback` is untouched.
- Installed per ubatch in `llama_context::process_ubatch` (`llama-context.cpp:2360`): `ggml_backend_sched_set_cpu_callback(sched.get(), expert_prefetch_layers.empty() ? nullptr : expert_prefetch_cb, this)`.
- Callback: `llama_context::expert_prefetch_cb` (`llama-context.cpp:1127`); it matches `t->op==GGML_OP_MUL_MAT_ID` and `t->src[0]` in a layer's
  `ffn_{up,gate,down,gate_up}_exps` (`:1132-1142`), observes only the FIRST such node per layer per ubatch (`expert_prefetch_layers[il].observed`, reset `:2356-2359`)
  unless diag is on (then every MUL_MAT_ID, `:1144-1149`). It requires `src[2]` I32, host, named `ffn_moe_topk-*` (`:1162-1164`);
  otherwise `expert_fill_failed=true` + `expert_fill: inactive (unsupported host router ids)` (`:1167-1169`).
  It dedups ids into `selected` (`:1177-1187`), then dispatches (`:1188-1200`).

## 2. Per-patch map

### 01 mmap_advice (`01-mmap-advice-random.patch`, 27 lines) -> `src/llama-mmap.cpp:488-540`
- Env `LLAMA_MMAP_ADVICE=random` (any other value = no-op). Effect: `prefetch=0` (no MAP_POPULATE/WILLNEED), skip `POSIX_FADV_SEQUENTIAL`
  (`:507`), `POSIX_MADV_RANDOM` on the whole mapping (`:538`). Default off.
- Log: `llama_mmap: LLAMA_MMAP_ADVICE=random (no FADV_SEQUENTIAL, no WILLNEED, MADV_RANDOM)`.
- In HEAD this is suppressed when `expert_prefetch` (02 mode, fill off) is on: `j_random = !expert_prefetch && ...` (`:497`).
- Per task note, dormant in the kept engine.

### 02 router_prefetch (`02-router-prefetch.patch`, 392 lines)
- Env `LLAMA_EXPERT_PREFETCH=0|1` (default 0), `LLAMA_EXPERT_PREFETCH_NEXT=0|1`. Only active when FILL is off (`llama-mmap.cpp:493`, `llama-context.cpp:2351`).
- Adds: `ggml_backend_sched_set_cpu_callback` (see section 1), `expert_prefetch_cb`, `expert_prefetch_advise` (`llama-context.cpp:1066`): for each selected expert id,
  `madvise(MADV_WILLNEED)` on `[w->data + id*w->nb[2], +nb[2])` page-aligned for each expert tensor (`:1085-1114`), with a 32-id/32-token per-layer LRU (`:1069-1081,1116-1119`).
  `PREFETCH_NEXT` also advises the same ids in layer L+1 (`:1211-1222`, "same-ID" prediction). Loader additionally adds expert tensors as MADV_RANDOM ranges
  (`llama-model-loader.cpp:1445-1456`, via the lazy-range path; side effect: disables MAP_POPULATE because `lazy_ranges` is non-empty, `llama-mmap.cpp:509`).
- Logs: `expert_prefetch: CPU host-consumer hook enabled; device-only experts skipped, next=%d, LRU=32 ids/32 tokens`,
  `llama_mmap: expert prefetch (RANDOM expert ranges, default non-expert advice)`,
  at teardown `expert_prefetch: advise calls=%llu bytes advised=%llu failures=%llu next-layer prediction hits/total=%llu/%llu (%.2f%%)` (`llama-context.cpp:1287`).
- This is the only component that is not "read via pread"; it uses `madvise(WILLNEED)`, which is async readahead into the page cache. Dormant in the kept engine.

### 03 expert_fill (`03-expert-fill.patch`, 462 lines)
- New header `src/llama-expert-fill.h`: `ExpertConfig` (`:32`), `ExpertFiller` (`:116`). Context members `llama-context.h:57-69`.
- Env `LLAMA_EXPERT_FILL=0|1` (default 0; component sets 1), `_THREADS`, `_CHUNK_KIB`, `_RANDOM`. Ranges and defaults in HEAD (`:86-93`, patch 08 made them strict):
  FILL 0..1 (0); RANDOM `0|1|decode` (0; component sets `decode`); THREADS 1..64 (8; component 16); CHUNK_KIB 64..65536 (1024; component 2048);
  MIN_TOKENS 0..2147483647 (0); MAX_TOKENS 0..2147483647 (0 = unlimited; component 1); DIAG 0..1 (0); POPULATE 0..1 (0); `DIAG_CSV` nonempty path.
  (component.yaml `env_ranges` describes 03's looser fallbacks, 08's strict parse is what HEAD has.)
- `llama_model::expert_file_info` (`llama-model.cpp:2557`) and `pimpl->expert_files/expert_offsets` (`:1357-1358`, filled `:2152-2167`), see section 3.
- `llama_context::expert_fill_init` (`llama-context.cpp:648`) called from `process_ubatch` (`:2340`) once: checks every `ffn_{gate,up,down,gate_up}_exps` is mmap-backed
  contiguous with `ne[3]==1` and `nb[2]!=0`; builds one `ExpertFiller` per GGUF file (path `/proc/self/fd/<fd>`).
- `expert_fill_selected` (`:996`) builds per-file `Range{offset=tensor_file_offset+id*nb[2], len=nb[2]}` for ALL expert tensors of layer L and each selected id and calls `ExpertFiller::fill` (see section 4).
- Failure: any exception -> `expert_fill_failed=true` (permanent) + `expert_fill: inactive (<what>)`.
- Logs: `expert_fill: active threads=%zu chunk_kib=%zu random=%s files=%zu` (`:683`),
  `expert_fill: inactive (%s)` (`:689`),
  teardown `expert_fill: stats calls=%llu ranges=%llu bytes_requested=%llu bytes_skipped_resident=%llu bytes_read=%llu read_syscalls=%llu total_fill_wall_ns=%llu max_single_fill_ns=%llu prompt_calls=%llu prompt_bytes_read=%llu prompt_fill_wall_ns=%llu decode_calls=%llu decode_bytes_read=%llu decode_fill_wall_ns=%llu populate_calls=%llu populate_ns=%llu populate_errors=%llu demand_wait_ns_total=%llu demand_wait_ns_per_token=%.3f` (`:1271-1283`).
  (Patch 03 originally had the shorter prefix of this; `populate_*` from 05, `demand_wait_*` from 08.)

### 04 fill_phase (`04-fill-phase.patch`, 157 lines)
- `LLAMA_EXPERT_FILL_MIN_TOKENS`, `_MAX_TOKENS`, `_RANDOM=decode`. `expert_fill_phase(n_tokens)` (`llama-context.cpp:957`, called `:2341`):
  `expert_fill_decode = (n_tokens==1)`; `expert_fill_this_ubatch = n_tokens>=MIN && (!MAX || n_tokens<=MAX)` (`:967-969`).
  With the component values (MIN 0, MAX 1) fill runs only for ubatches of exactly one token: decode, and also a 1-token prompt.
  Prompt-processing ubatches (n>1) get no fill and no pregate (`expert_fill_selected:997`, pregate guards `:747,786`).
- `RANDOM=decode`: at the first 1-token ubatch, `madvise(MADV_RANDOM)` over each expert tensor's page-aligned file range via the mapping (`:970-993`),
  once (`expert_fill_random_applied`). Log: `expert_fill: random advice applied at decode`; on failure `expert_fill: inactive (decode random advice failed)`.
  `RANDOM=1` instead applies MADV_RANDOM at load (loader `llama-model-loader.cpp:1445-1456`). The `random advice` line is an engagement check in component.yaml.
- Fill `expert_demand_tokens += n_tokens` only for ubatches that fill (`:2342`): denominator for `demand_wait_ns_per_token`.

### 05 fill_diag (`05-fill-diag.patch`, 414 lines)
- `LLAMA_EXPERT_FILL_DIAG=1` (default 0), `LLAMA_EXPERT_FILL_POPULATE=0|1`, `LLAMA_EXPERT_FILL_DIAG_CSV=<path>`. Struct `llama_context::fill_diag` (`llama-context.h:87`).
- Diag adds `getrusage(RUSAGE_SELF/THREAD)`, extra `mincore` probes, and observes EVERY MUL_MAT_ID node (extra graph cuts, `:1144-1149`). **Perturbs timing; do not use DIAG=1 for performance numbers.**
- CSV header (`:676`): `token_idx,fill_ns,between_ns,majflt_fill,majflt_between,post_fill_nonresident_pages,pre_use_nonresident_pages,bytes_read` (one row per decode token, `:930-937`, flushed each row).
- stderr every 16th token (`:938-944`): `expert_fill: diag token=%llu fill_ns=%llu between_ns=%llu majflt_fill=%llu majflt_between=%llu post_nonresident=%llu pre_use_nonresident=%llu bytes_read=%llu`.
- Teardown (`:1234-1253`), single line: `expert_fill: diag tokens=N fill_ns= between_ns= majflt_fill= minflt_fill= majflt_between= minflt_between= thread_majflt= thread_minflt= post_nonresident= pre_use_nonresident= next_nonresident= bytes_read= post_checks= pre_use_checks= next_checks= populate_calls= populate_ns= populate_errors=`.
- `POPULATE=1`: after preads, a second pass `madvise(MADV_POPULATE_READ)` over the merged ranges (`llama-expert-fill.h:385-399`, worker `:459-472`); installs PTEs (removes later minor faults) at extra cost. `EINVAL` -> `expert_fill: populate unsupported` once.

### 06 pregate (`06-pregate.patch`, 463 lines), 07 pregate_sched (276), 08 pregate_observe (702)
- 06: `expert_pregate_init/_arrive/_hook/_stats`, async path in `ExpertFiller` (`enqueue_async`, `AsyncBatch`, `Prediction`). Env `LLAMA_EXPERT_PREGATE=0|1` (0), `_K` 1..32 (8).
- 07: `LLAMA_EXPERT_PREGATE_ORDER=after|before` (after), deadline-ordered async queue + `cancel_async_through` (`llama-expert-fill.h:227-286`).
- 08: `LLAMA_EXPERT_PREGATE_MAX_INFLIGHT` 1..64 (4), `_LOOKAHEAD` 1..2 (1), strict env validation of every `LLAMA_EXPERT_*` (`:68-106`), the
  `expert_config: effective ...` line, timeliness classification (`Arrival`, `Timeliness`, `arrive_async_through`), `demand_wait_*`.
- Pregate is initialised from inside `expert_fill_init` (`:670`), so **PREGATE=1 with FILL=0 is silently inert (no log at all except the config line)**.
- Logs: `expert_pregate: active k=%zu arch=qwen35moe gating=softmax router=file-cpu-copy order=%s` (`:738`);
  `expert_pregate: inactive (%s)` (`:742`; reasons: arch != QWEN35MOE, groups>1, LoRA, hadamard rotations, router layout/type);
  `expert_pregate: prediction disabled (%s)` (`:857`, sets `expert_pregate_failed`); teardown `expert_pregate: stats ...` (format in section 8).
- Config line printed exactly once per context at construction (`llama-context.cpp:199`):
  `expert_config: effective fill=%zu random=%s max_tokens=%zu threads=%zu chunk_kib=%zu pregate=%zu k=%zu order=%s max_inflight=%zu lookahead=%zu min_tokens=%zu diag=%zu populate=%zu diag_csv=%s prefetch=%zu prefetch_next=%zu` (`llama-expert-fill.h:108-112`).
  Invalid value/unknown `LLAMA_EXPERT_*` name -> `expert_config: invalid NAME=VALUE (range ...)` then `abort()` (even when features are disabled).
  `ExpertConfig::read()` is also called from `llama-mmap.cpp:492`, `llama-model-loader.cpp:1446`, `llama-model.cpp:2153`.

### 09 thread_names: renames fill workers `xfill-N`; reverted in HEAD (not part of kept engine). No behavioral change.

## 3. Expert identity and byte ranges
- Identity: runtime router output `ids` = `ffn_moe_topk-<il>` I32 `[n_expert_used, n_tokens]` in host memory at the CPU MUL_MAT_ID (`expert_prefetch_cb:1160-1187`).
  `selected` = unique ids within `[0, src0->ne[2])`, over all tokens of the ubatch.
- Tensor -> file: `pimpl->expert_offsets[tensor name] = {file idx, offs}` copied from `ml.weights_map` only if `ExpertConfig.fill && use_mmap_buffer`
  (`llama-model.cpp:2152-2167`, `use_mmap_buffer` is a constant `true` at `:1690`). Tensor name is the key (`blk.N.ffn_*_exps.weight`).
  `pimpl->expert_files` re-opens `/proc/self/fd/<fd>` per file as an independent `llama_file`.
- `llama_model::expert_file_info(t, out, require_host)` (`llama-model.cpp:2557`): returns `{file_index, offset, mapping_size, mapping addr, source_fd}`;
  with `require_host` it demands `mapping->addr()+offset == t->data` (`:2565-2566`) and `tensor_is_mapped(t)` (`:2571`). With `require_host=false` (used for GPU-resident routers, `:715`)
  it returns file metadata only.
- Per expert byte range: contiguous 3D tensors; expert `e` occupies `[offset + e*t->nb[2], + t->nb[2])` where `nb[2]` is bytes per expert (row bytes x ne[1]).
  Built identically for demand (`llama-context.cpp:1009`) and for predictions (`:836`). For each layer, ranges for every present tensor of
  `{ffn_gate_exps, ffn_up_exps, ffn_down_exps, ffn_gate_up_exps}`, so one "expert" = all its tensors for that layer. These are file offsets; the same offsets are used as
  mapping offsets because the filler requires offset-zero live mmap (`ExpertFiller` ctor `:188-217`, checks fd file size == mapping size).
- Page alignment: ranges are rounded to page boundaries (start down, end up, clamped to file size); thus `bytes_requested` >= raw expert bytes.

## 4. Fill workers (src/llama-expert-fill.h)
- Pool: `ExpertFiller` has `threads_` std::threads (default 8, component 16) per GGUF file, created in the ctor (`:213`), unnamed in HEAD. Per-thread scratch buffer `max(page, chunk)` bytes (`:211`).
  Max RSS cost = THREADS x CHUNK (16 x 2 MiB = 32 MiB) plus residency vectors.
- Method: `pread(fd_, scratch, len, off)` on an independent O_RDONLY fd (worker `:486,494`) into private scratch. **It does not touch or write the mmap and does not install PTEs.**
  The kernel puts the pages in the page cache; the mmap later maps them via minor faults. Residency check = `mincore` on the mapping (`:360,476`), which reports page-cache presence of those file pages, not PTE presence (comment `:298`).
- Chunking: demand jobs are runs of non-resident pages inside merged page-aligned ranges, split in `chunk_` = `CHUNK_KIB*1024` pieces (`fill():355-375`); async jobs split with `step = max(page, chunk/page*page)` (`:235`).
- Populate: only if POPULATE=1 and kernel supports `MADV_POPULATE_READ` (22); a second pass after all preads over ALL merged ranges (even resident ones), by the workers (`:385-399`). Default off.
- Demand fill, `ExpertFiller::fill` (`:317`): serialised by `fill_mutex_`; sets `demand_active_` (`DemandScope`) first so that async workers stop picking up new jobs; computes the union, `mincore`, publishes `jobs_`, and **blocks the caller on `done_` until every pread job finished**
  (`:376-384`). Worker picks sync jobs first (`:446`), else async (`:448`) only if `!demand_active_ && async_running_ < async_limit_`.
- Phase gating: `MIN/MAX_TOKENS` act on `ubatch.n_tokens` (see 04). Prompt vs decode counters are separate (`prompt_*` vs `decode_*`) because `fill(ranges, decode)` takes `expert_fill_decode`.
- **Synchronisation with compute: yes, demand fill blocks compute.** The call chain is: CPU split reached -> prefix nodes computed -> callback on the main thread
  (`ggml-backend.cpp:2258`) -> `expert_fill_selected` -> `fill()` returns only after all missing pages were `pread` -> the first MUL_MAT_ID of that layer starts.
  The whole layer's gate/up/down expert ranges for the selected ids are fetched before the first of the three matmuls (not three separate times).
  Callback is *before* the op, on the compute (main) thread; the fill workers are other threads and the 16 workers parallelise the IO only.

## 5. Predictive pregate (llama-context.cpp:698-894, llama-expert-fill.h:128-290)
- Predicts layer L+d (d = 1..LOOKAHEAD, default 1; up to 2) experts. Trigger: the callback of layer L at its first MUL_MAT_ID, decode only (`expert_fill_decode && expert_fill_this_ubatch`, `:786`), `il+distance < n_layer`.
- Input: `x = t->src[1]` of the layer-L first expert matmul = layer L's FFN input vector (host F32 `[n_embd,1,1,1]`, i.e. `attn_post_norm_L`-derived, per the comment at `:790-792`); must be a host contiguous F32 vector or pregate disables itself (`:796-802`).
  Router `W` of the TARGET layer is a CPU float copy decoded once from the GGUF file at init (`:710-736`, mmap of the file region, `to_float` for quantised types). Layer 0 has no router copy (loop starts at `il=1`), so layer 0 is never predicted.
  Prediction = top-K by `dot(W_e, x)` (ties by lower id), K = `LLAMA_EXPERT_PREGATE_K` (default 8) (`:810-821`); softmax skipped because monotonic.
  This is an approximation: it feeds layer L's FFN *input* into layer L+1's router, ignoring layer L's MoE/shared-expert output, residual update and layer L+1's attention/norm. Quality is measured by recall (section 8), not assumed.
  Scalar `float` dot loop on the compute thread (`:812-817`): n_expert x n_embd MACs per layer per token, plus 3 `mincore` calls per predicted expert. This sits on the critical path. Cost not measured here.
- Per predicted expert: ranges for all tensors (`:829-837`); `nonresident()` mincore-probes all files; if everything is resident nothing is queued (`Prediction::enqueue`, `llama-expert-fill.h:176-180`, `resident_at_predict=true`); otherwise `enqueue_async` (`:227`).
  Async queue is a `std::list` sorted by (target layer asc, distance asc, FIFO) (`:255-261`); a submission that would push the queue over 4096 chunks is dropped whole (`:248-254`, `async_dropped_`).
- MAX_INFLIGHT: caps concurrent async chunk reads `async_limit_ = min(threads, MAX_INFLIGHT)` (`:193`), default 4 (component: 4). Async workers skip a job's resident pages by a fresh `mincore` at consumption (`:474-482`) and only pread the missing runs, so wrong-but-resident predictions cost a syscall and no IO.
- Relation to demand: ORDER=after (default, component): callback of layer L = `expert_pregate_arrive(L)` (cancel queued, sample, `:1191`) -> `expert_fill_selected(L)` (blocking demand fill) -> `expert_pregate_hook(L)` (enqueue L+1)(`:1194-1197`).
  ORDER=before: hook enqueues L+1 first and demand fill L afterwards (`:1192`). Because async workers do not start new chunks while `demand_active_`, ORDER=before mostly changes only when the mincore probe and enqueue happen, not when IO starts; async reads already running when demand starts keep running and compete for the device.
  So prefetch for L+1 effectively runs during: layer L's MoE matmuls + layer L+1 attention + router, until layer L+1's callback arrives. Never overlapped with the demand fill of L.
- Arrival (`expert_pregate_arrive:746`, called at layer L's callback before demand): for all predictions targeting L (distance 1 from L-1, distance 2 from L-2) it snapshots per-batch states and cancels all queued chunks of layers <= L under the dispatch lock (`arrive_async_through:276`, `cancel_async_locked:421`); running chunks continue.
  Per-ubatch reset at `process_ubatch` cancels everything (`:2343-2350`).

## 6. Failure semantics
- Wrong prediction: bytes read into page cache that are never used: wasted IO bandwidth / memory / possible eviction of useful pages. No effect on computation; the demand fill reads whichever ids the real router chose.
- Late prediction read (chunk still running or queued when the layer's matmul starts): queued chunks are cancelled; running chunks complete in the background. Demand fill then `mincore`s; pages still in flight are not Uptodate, so they count as non-resident and are `pread` again by demand workers (the kernel serialises on the page lock; at worst duplicate IO, not wrong data).
  Compute never waits for async reads, only for the demand fill. (`wait_async()` is teardown-only: header `:287`, stats `:864`.)
- Feature disabled:
  - FILL=0 (and PREFETCH=0): `expert_fill_init` returns at `:651`; no `expert_files`, no fillers; `expert_prefetch_layers` empty so cpu callback is `nullptr` (`:2360`) and the `compute` lambda degenerates to one `ggml_backend_graph_compute_async` call. mmap advice is stock unless `LLAMA_MMAP_ADVICE=random`. Residual differences: env validation/abort, the `expert_config: effective` line.
  - PREGATE=0: no arrive/hook/stats; `expert_pregate_stats` only runs `if (expert_pregate_enabled)` (`:1230`).
  - Runtime error (pread error `EIO/errno`, mincore failure, unsupported layout): exception -> `expert_fill_failed` (fill) or `expert_pregate_failed` (prediction); engine continues with stock mmap faults, one log line.
  - `ggml_cpu` abort only on invalid env values.
- Why bit-identical (what I verified):
  1. Fill/pregate only `pread` into private scratch buffers and call `mincore`/`madvise`; they never write the mmap or any tensor (grep of the diff: only `memcpy` uses are the router float copy into a private vector and reading ids).
  2. Weights are mapped from the same file; data read through the mmap are the same bytes regardless of whether the page came from fault or pread.
  3. No ggml op, graph topology, tensor type, sampler or ordering of graph nodes changed. The only ggml change is splitting a CPU split into `ggml_graph_view` prefix/tail calls at observed MUL_MAT_ID nodes (`ggml-backend.cpp:2243-2260`). Each view is computed with the same CPU plan code; CPU fusion exists only for `RMS_NORM+MUL` (`ggml-cpu.c:3090-3120`), and cuts happen right before a MUL_MAT_ID so no fusable pair is separated. mul_mat_id output elements are each computed by one thread (disjoint chunks), so thread partitioning does not change reductions. This is a read-based argument; the actual identical-stdout check is a run-time obligation in component.yaml (`correctness_obligation: identical greedy stdout`).
  4. The predictor never affects `selected`; routing is still the stock `ggml_argsort_top_k` output.
- Residual caveat: the cut changes thread-pool wake/sync timing only (performance), not values.

## 7. Verified unchanged
- GGUF weights file, tensor dtypes, `build_moe_ffn`/`qwen35moe.cpp`/`llama-graph.cpp` (diffstat: untouched), ggml-cpu kernels, CUDA backend, sampler code, KV cache.
  Confirmed by `git diff cf34d3113 HEAD --stat` listing only the 9 files above. Not verified at run-time.
- Changed non-semantically: ggml sched CPU compute call structure (one extra indirection, views), loader advice list when `RANDOM=1` or prefetch, llama_mmap advice when `LLAMA_MMAP_ADVICE=random`.
- Not verified by me: that decode-time `-cmoe` graph on this model really assigns the entire MoE sub-block (ids, expert matmuls) to one CPU split such that `src[1]` is host-resident at callback; the code defensively disables pregate (`:796-802`) and fill (`:1162-1175`) otherwise, and the logs `expert_pregate: prediction disabled` / `expert_fill: inactive (unsupported host router ids)` indicate it.

## 8. Counters and what they actually measure
Demand fill (`expert_fill: stats`, summed over files; `llama-context.cpp:1256-1284`, struct `Counters` `llama-expert-fill.h:119`):
- `calls/ranges`: one call per (layer, file, ubatch) that fills; ranges = per-tensor-per-expert ranges.
- `bytes_requested`: page-aligned union per call (`:357`). `bytes_skipped_resident`: bytes of those pages that `mincore` said resident at fill start (`:364`). `bytes_read`/`read_syscalls`: bytes/syscalls actually `pread` by demand workers.
  `decode_bytes_read`, `prompt_bytes_read`: split by phase.
- `total_fill_wall_ns`/`decode_fill_wall_ns`: main-thread wall time inside `fill()` (job building, mincore, wait). `demand_wait_ns_total` equals `total_fill_wall_ns`; `demand_wait_ns_per_token = total / expert_demand_tokens` (decode tokens when MAX_TOKENS=1).
  It is blocked-on-IO time, not matmul time and not total decode time.
Pregate (`expert_pregate: stats`, `llama-context.cpp:871-893`), exact line:
`expert_pregate: stats predictions= arrivals= hits= actual= predicted= recall_at_k= precision= async_bytes_read= async_reads= async_errors= dropped= cancelled_jobs= cancelled_bytes= inflight_at_arrival= inflight_reads= pending_reads= sync_bytes_with_prediction= sync_bytes_without_prediction= sync_calls_with_prediction= sync_calls_without_prediction= skips= pred_done= pred_inflight= pred_queued= pred_resident_at_predict= hit_done= hit_inflight= hit_queued= hit_resident= recall_at_k_d1= recall_at_k_d2= actual_d1= actual_d2= hits_d1= hits_d2= demand_wait_ns_total= demand_wait_ns_per_token=`
- `predictions`: hook calls x distances (not per expert). `arrivals`: (layer, distance) pairs that had a prediction. `predicted`=K per arrival; `actual`= unique selected ids of that layer at arrival; `hits` = predicted ids that appear in `selected`.
  `recall_at_k = hits/actual`, `precision = hits/predicted`. These are set-overlap only; independent of IO.
- `pred_{done,inflight,queued,resident_at_predict}` classify every predicted expert at arrival (before demand): resident_at_predict (all its ranges were already in page cache by `mincore` at prediction),
  else queued (any chunk cancelled/not started/errored/dropped), inflight (some chunk running), done (no pending). `hit_*` = same buckets restricted to ids actually selected.
  `done` means every chunk's worker finished, including chunks skipped because the worker's own `mincore` found the pages resident; it does not re-check residency at demand time and cannot see eviction between completion and use.
- `async_bytes_read/async_reads`: all bytes preread by async workers, hit or not. `cancelled_*`: chunks cancelled before start. `dropped`: whole submissions dropped for the 4096-chunk bound.
- `sync_bytes_with_prediction` / `_without_prediction`: demand `pread` bytes in layers that had any prediction vs layers (including layer 0 and any non-predicted) that had none; calls likewise.
Diag (`LLAMA_EXPERT_FILL_DIAG=1` only): `majflt_fill/minflt_fill` (process-wide getrusage during the demand fill window), `majflt_between/minflt_between` (process-wide between fill end and next fill / token end: includes compute-side page faults, mostly expert pages),
`thread_majflt/minflt` (fill worker threads, nonzero only with POPULATE), `post_nonresident` (non-resident pages right after demand fill; should be ~0), `pre_use_nonresident` (non-resident right before first matmul use), `next_nonresident` (previous layer's ranges probed when the next layer fills, i.e. eviction after use).
All are page counts of mincore, summed over probes.

**Answer to (a)/(b)/(c):**
- (a) "predicted the right expert": `hits`, `recall_at_k(_d1/_d2)`, `precision`. Directly measured; nothing else needed.
- (b) "its bytes were resident before demand": partly. Closest are `hit_done` (+`hit_inflight` partial), `hit_resident` (resident BEFORE any pregate IO, so not credited to pregate), and the change in `decode_bytes_read` / `bytes_skipped_resident` / `sync_bytes_with_prediction` versus a fill-only baseline run.
  `bytes_skipped_resident` alone cannot attribute residency to prediction versus natural page-cache retention from earlier tokens. `hit_done` is an I/O-state classification, not a residency measurement: it is not re-validated by `mincore` at arrival/demand; with `DIAG=1`, `pre_use_nonresident` is a residency measurement but only after the demand fill, and not split by predicted/unpredicted.
- (c) fewer page faults vs lower decode time: not separable without DIAG. Without DIAG there is no fault counter at all in the engine and no per-token or per-layer wall time split; `demand_wait_ns_per_token` captures only time blocked in `fill()`. Fault counts (`majflt_between`, `minflt_between`) exist only in DIAG runs (which add cuts, getrusage and mincore overhead).
  Note preads do not count as page faults, so a fill config can drive `majflt` to ~0 while moving the same (or more) IO into `fill()`; fewer faults must not be read as less IO.

**What is missing:**
1. Per-actual-expert residency at arrival (mincore of each *selected* expert's ranges, pre-demand), split by predicted vs not predicted: gives bytes-resident-before-demand attributable to prediction. Today only classification of predicted experts exists.
2. Wasted prefetch: bytes read for ids not selected (`async_bytes_read` minus bytes of hit experts); no counter. Also no counter of prefetched-then-evicted bytes.
3. Non-DIAG fault counters (e.g. `getrusage(RUSAGE_SELF)` start/end of generation, or `/proc/self/stat` delta) and per-token decode wall time; use `llama_perf` eval ms/token plus external `/proc/<pid>/stat` or `perf stat -e major-faults,minor-faults`.
4. Matmul-side stall time (time inside MUL_MAT_ID per layer) vs fill time, so "lower decode time" can be decomposed.
5. Time the demand fill spent waiting on in-flight async pages (duplicate IO / page-lock waits) and the time for the pregate hook itself (router dot + mincore on the critical path).
6. Page-cache pressure metrics (free/available MemAvailable, Cached) over the run for an 8 GB box.

## 9. Expert placement on the GPU
No. The diff adds no `ggml_backend_tensor_set/alloc`, buffer-type, CUDA or buffer allocation code (grep over `git diff cf34d3113 HEAD`, only `memcpy` for router floats and ids). `-cmoe` keeps `ffn_*_exps` in the CPU/mmap buffer
(`common/arg.cpp:2731`), and `expert_fill_init` explicitly throws if the expert tensors are not host mmap-backed (`llama-context.cpp:657-660`). Routers (`ffn_gate_inp`, on GPU) are never read from GPU memory; the predictor decodes its own CPU copy from the file (`:709-735`).
Page-cache residency is the only "placement" being changed.

## Bugs / questionable semantics
1. Pregate predicts layer L+1 from layer L's FFN input, not the real L+1 router input (skips L's MoE+shared-expert output, residual, L+1 attention+norm). Recall may be modest; check `recall_at_k_d1` before attributing speedups. LOOKAHEAD=2 is staler.
2. `ORDER=before|after` is largely moot for IO start time because async workers are gated by `demand_active_` (`llama-expert-fill.h:444`); `before` only moves the mincore probes/enqueue earlier. Running async chunks still compete with demand IO.
3. In-flight async pages look non-resident to `mincore`, so demand re-issues the read (duplicate syscalls; page-lock serialises) and `bytes_read`/`sync_bytes` include bytes the async side also read. `hit_inflight` experts therefore are not a clean "resident before demand".
4. `Arrival::done` counts a batch with zero bytes read (all chunks skipped as resident at worker time) as done, same as one that actually read; `pred_resident_at_predict` handles only prediction-time residency.
5. Layer 0 is never predicted (router copy loop starts at 1, `:710`) and layers where `il+1>=n_layer`, so `sync_*_without_prediction` includes layer 0 every token, not only mispredicted layers.
6. `pregate_sync_with` uses `!predicted.empty()`; `predicted` accumulates across distances, so with LOOKAHEAD=2 it is true for any layer that got either prediction.
7. `DIAG=1` observes every MUL_MAT_ID (`:1144-1149`) -> extra cuts + syscalls; DIAG timing is not comparable to non-DIAG timing. `majflt_*` use RUSAGE_SELF (whole process, including CUDA/other threads), not just expert-fault attribution.
8. PREGATE=1 with FILL=0 is silently inactive (init is inside `expert_fill_init`); `expert_config: effective ... pregate=1` is printed though pregate is not active. Engagement check `expert_pregate: active` guards this.
9. `ExpertConfig::read()` aborts on any unknown `LLAMA_EXPERT_*` env var, even with FILL=0 (and is parsed repeatedly: loader, mmap, model, context).
10. `LLAMA_EXPERT_FILL_RANDOM=1` adds expert ranges to the lazy-range list, which also turns off MAP_POPULATE for the whole file (`llama-mmap.cpp:509`), a side effect on non-expert pages; `decode` variant avoids it but applies MADV_RANDOM only from first decode token (prompt-phase mmap faults, if any, unaffected, and MAX_TOKENS=1 means no fill in prompt).
11. A prompt of one token is treated as decode (`n_tokens==1`), counts in decode stats and gets random advice.
12. `expert_demand_tokens` counts filled-ubatch tokens only; with MIN/MAX changes `demand_wait_ns_per_token` denominators change meaning.
13. Fill/pregate cost per layer on the critical path (mincore probes, scalar router dot, fill job build) scales with n_expert*n_embd and K; no timers cover it.
14. Component.yaml `env_ranges` text (e.g. THREADS 1..256) refers to patch 03; HEAD (patch 08) is strict 1..64, 64..65536 for chunk; `component.yaml` default `LLAMA_EXPERT_FILL_THREADS=16` is within range.
