# Validation and gate rules

The verifier half is `verify`. It returns `{"done": bool, "checks": [{name, status, stage, detail}],
"stage_reached", "not_done_because"}`; `done` is false whenever a check fails, when `require_stage` (default
`runtime acceptance`) was not reached, when a check that stage needs was `skipped` (compile, runtime), and when
an `inconclusive` check (an unrecognized static form, an uncalibrated `fixture_calibration`) was not settled by
a passing runtime acceptance stage. `skipped`, `info` and `inconclusive` never stand in for a pass. The verifier
never writes inside the checkout: it reads the base (default HEAD) with git, exports trees with `git archive`
into `work_dir` and builds there.

## Evidence stages (`node_check.STAGES`)

| Stage | Checks | Runs when |
| --- | --- | --- |
| `fixture` | `fixture_calibration` | Always: `good.diff` passes every static rule cleanly and each planted fault fails its rule on this base (`inconclusive` when the fixtures do not apply, i.e. the base is not stock 9048bad8). |
| `native CC execution` | `patch_input`, the static rules below | Always (stdlib + git). |
| `compile` | `compile` (candidate), `stock_build` (info) | Unless a static gate failed or `build: false`. Needs cmake and a C++ toolchain. |
| `runtime acceptance` | `parity_gate_unset`, `parity_gate_set`, `marker_only_with_gate`, `fill_stats`, `prefill_not_filled`, `no_nan` | With `tiny_dir` (missing: `runtime_acceptance` fails when required). Reached **only when all six ran and passed**. |

## Gates

| Check | Fails when |
| --- | --- |
| `allowed_paths` / `protected_paths` | a path outside SOURCE-MAP's allowed set / a kernel, graph builder, model graph, converter or public API path. |
| `plain_text_edits` | binary, mode-change or delete patches. |
| `gate_env` | the added code never names `"LLAMA_EXPERT_FILL"`. |
| `gate_default_off` | a recognized default-on form: helper default `("LLAMA_EXPERT_FILL", 1)`, `!getenv(...) \|\|`, `X == nullptr \|\|`. `inconclusive` when no form is recognized. |
| `fill_before_matmul` | the trigger names an expert matmul output (`"ffn_moe_{up,gate,down,gate_up}[-_]..."`) or uses `GGML_OP_MUL_MAT_ID` with an eval callback (which runs after its node). Pass needs the router name (`"ffn_moe_topk"` etc.) or a before-node hook; otherwise `inconclusive`. |
| `no_tensor_writes` | `ggml_backend_tensor_set/memset/copy`, a copy or store into `->data`, `PROT_WRITE`, `MAP_PRIVATE`, `mprotect` in the added code. |
| `no_graph_change` | a ggml graph-op constructor (`ggml_mul_mat`, `ggml_add`, `ggml_cpy`, views, custom ops, ...) in the added code. |
| `compile` | the CPU build of `llama-simple` and `llama-perplexity` fails. |
| `parity_gate_unset` | greedy `llama-simple -n 32` on the tiny pack differs from stock (stdout bytes) or exits non-zero. |
| `parity_gate_set` | the same with `LLAMA_EXPERT_FILL=1`, and again with `LLAMA_EXPERT_FILL_SKIP_RESIDENT=0`, differs from stock. |
| `marker_only_with_gate` | any `expert_fill` line without the gate, or not exactly one `expert_fill: active` line with it. |
| `fill_stats` | no stats line or a missing key (`calls`, `bytes_read`, `reads`, `fill_us`); `calls` 0 with the gate set; `calls`, `reads` or `bytes_read` 0 with the resident skip off; `read_errors` > 0. |
| `prefill_not_filled` | a prompt-only run (`-n 1`, gate set) reports `calls` != 0 or no stats line. |
| `no_nan` | `llama-perplexity -c 128 --chunks 4` with the fill on every ubatch (`MAX_TOKENS=0`, read-all) is not finite, differs from stock's final estimate, or did not fill. |

## Measured on the Spark (2026-11-25, CPU, -j 8, stock_bin given)

`good.diff`: done true, stage runtime acceptance, 75 s. Fill stats on `tiny-q2exps.gguf` (4 layers, 31 decode
tokens): gate set calls=124 bytes_requested=32.0 MB all resident, reads=0; read-all reads=1488
bytes_read=38.6 MB fill_us=27.5k; prompt-only calls=0; perplexity PPL 205577.2103 identical to stock (the tiny
model is random; finiteness and equality are what count).

Planted faults (each fails its static rule, so the default verify stops before the build; with
`runtime_even_if_static_fails` the runtime checks were also run as a calibration of the backstop):

| Fixture | Static rule that fails | Runtime backstop (forced) |
| --- | --- | --- |
| `gate-default-on.diff` (`env_long("LLAMA_EXPERT_FILL", 1, ...)`) | `gate_default_off` | `marker_only_with_gate`: marker and stats printed with the gate unset |
| `fill-after-matmul.diff` (keyed on `"ffn_moe_down-"`) | `fill_before_matmul` | `fill_stats` calls=0, `no_nan` fill calls 0 (the down output is F32, the hook never fills) |
| `fill-writes-tensor.diff` (`ggml_backend_tensor_set` into the expert) | `no_tensor_writes` | `parity_gate_set`: SIGSEGV (rc -11) writing the read-only mapping |
| `touches-ggml-cpu.diff` (new header under `ggml/src/ggml-cpu/`) | `allowed_paths`, `protected_paths` | none expected: scope is a static-only gate |

## What verify cannot see

- Speed. It proves correctness and engagement on a 0.4 GB pack that is always resident; it says nothing about
  decode tok/s on the 304.7 GB pack, nor about cold-cache behavior (the read-all knob exercises the pool on
  resident pages). That is the lab A/B's job.
- Timing order at runtime. "Before the matmul" is a static rule over source text plus the eval-callback
  semantics; no runtime check observes that the reads finished before the kernel touched the pages.
- CUDA arms. The build is CPU-only; the `--cpu-moe` + `-ngl` path (ids computed on the GPU) is not run.
- Concurrency defects that do not change outputs on 31 tokens (races in a pool, fd leaks), and llama-server
  specifics (`-np 1` slots, multiple contexts from memory fitting).
- The static rules are heuristics: an unusual but correct spelling can be `inconclusive` (runtime decides), and
  a determined author can hide a write or a default-on gate from regexes; the runtime parity and marker checks
  are the backstop.
