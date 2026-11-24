# Batch layout mapper

Build a mapper for the uncached rows of a single-slot causal text prompt on llama.cpp at `9048bad8`. Choose logical submissions that let the stock engine fill its physical microbatches within the existing compute-buffer reservation. Keep stock handling for multi-slot serving and emit observable planned row boundaries.

## Zero footprint when off

When `LLAMA_BATCH_LAYOUT` is unset, use the stock path after one cached `getenv`
check. Do zero component work beyond that check. Emit zero lines with the
`batch_layout_mapper:` prefix, including at teardown. The `active`,
`inactive (<reason>)` and `stats` markers are emitted only when the gate
is set. Keep the cached presence bit distinct from eligibility so a set but
invalid value can still report a reason.

```cpp
void example_first_use() {
    static const char * const gate = std::getenv("LLAMA_BATCH_LAYOUT");
    if (gate == nullptr) return;
    LOG_INFV(4, "batch_layout_mapper: inactive (example only)\n");
}
```

## Build sequence

1. Read the immutable contract selected by `contract_id`, the admitted flags and environment in `initial_run_config`, and the ownership constraints on `source.subpath`. Check the checkout pin, build and freeze the stock reference, and record the model, tokenizer, limits, memory allowance, cache settings and greedy request sequence. Use the generation loop and memory budget slice in [ONTOLOGY.yaml](ONTOLOGY.yaml).
2. Locate the server context, the effective batch accessors and the prompt row loop using [SOURCE-MAP.md](SOURCE-MAP.md). Trace from `update_slots` through `pre_decode` to `decode` and the KV splitter. Find the stock prefix handling and final-token replay before locating the eligible row contribution. Confirm that the configured slot count is one. A single occupied slot in a multi-slot server still uses the stock path.
3. Search the owned checkout for `LLAMA_BATCH_LAYOUT`, mapper status logs and existing prompt caps. If absent, create a small header under `src/` and add a hook at the server prompt-collection boundary. If present, update the gate, cap and logs in place and remove duplicate mapper caps within the owned paths. Verify that the default-off path reaches the original loop with its original bound. The [component specification](components/batch_layout_mapper/component.yaml) gives the contract for the change.
4. Establish eligibility before changing the cap. Require an empty pending batch and splittable, plain, causal text completion. Leave multimodal, embeddings, speculative, checkpoint, shared-prefix synchronization, aLoRA transition and other special scheduling paths on stock. Ordinary cached text prefixes remain eligible. Keep stock positions, row order, output flags, checkpoints, sampling, and KV cleanup and retry control. On an admission error, use the stock bound and record the reason.
5. Derive the aligned cap from effective `llama_n_batch` and `llama_n_ubatch` after context creation. If the contract explicitly admits a smaller physical width, use it when sizing the stock context so its reservation and the mapper agree. Keep that context configuration identical across the parity arms. With eligible rows, choose the largest full multiple of the physical width within the logical limit, then let the existing loop stop at prompt end or an existing break condition. For example, 16 uncached rows at effective limits 13 and 8 can be planned as 8 + 8 rather than the stock logical submissions 13 + 3. Use the actual rows added to log a half-open span starting at the post-cache prompt cursor. Count these as planned boundaries. A decode retry may split the work differently.
6. Read the gate once at server-context creation. With the gate set, emit one first-use status with the effective limits or a reason at INFO verbosity 4. Emit planned spans and one orderly-exit stats line per context. Count only actual eligible contributions as mapper decisions and document what your bypass counter counts. Use fixed-size state and account for it in the host ledger. The small patterns in [samples](samples/) cover environment reading, INFO logs, alignment and sweep design.

## Defaults when the contract is silent

| Decision | `chosen_by_cc` | Reason |
|---|---|---|
| Integration | Header-only helper plus a single server prompt-loop hook. | Fits the stock build graph and ownership boundary. |
| Eligibility | One configured slot and plain causal text with an empty pending batch. | Mixed-slot serving previously diverged in greedy output. Stock also owns special request boundaries. |
| Effective limits | Use the context's stock limits and align at the configured physical width. | Raw CLI values can differ from effective limits. Zero, inconsistent limits, or an unsupported path go to stock. |
| Capacity | Zero added dynamic buffer bytes and at most 128 fixed bytes per server context. | The existing reservation already provides compute buffers. Retain only gate, status and counter state. |
| Gate and events | Exact `1` enables. Unset keeps stock behavior, and other values produce an invalid-value reason. Use INFO at verbosity 4 and half-open row spans. | Makes the setting and the chosen cuts observable. |
| Silent-contract parity settings | Effective `n_batch=13` and `n_ubatch=8`, one slot and the 14 lengths in [METHOD.md](METHOD.md). | Covers aligned, misaligned and multi-submission cases. Use the smallest admitted model and context sufficient for the workload. |

## Pitfalls on Satay

- Look for activation markers with `-lv 4`. Library INFO activation output is hidden at lower verbosity on this setup. Compare the saved server log as well as the output.
- On this Jetson, `-lm auto` has resolved to no mmap. Find the effective mode in `load_tensors: ... (load_mode = none)`. For any component that depends on mapped weights, set `-lm mmap` in every parity arm and require `(load_mode = mmap)` in the load log. This mapper uses prompt rows and stock buffers, so keep the contract's load mode unless mapped-weight work in the same configuration requires mmap.
- Matching output with the gate set can occur on the stock fallback path. Require `batch_layout_mapper: active` on eligible gate-on probes, and inspect the planned spans to verify that at least one misaligned case actually changes a logical cut.
- Compare runs within one configuration. Stock itself can produce different tokens under `-ngl 0` and `-ngl 99 -cmoe`. Compare stock, gate unset and gate on with the same effective offload, load mode, model, flags and request sequence.
- The worker sandbox cannot access the GPU or open server ports. Use it for static verification, fixture and sample checks, and inspecting saved logs. Use an authorized real shell for server-path activation, parity and multi-slot controls, and the target hardware for GPU and physical traffic measurements.

## Done criteria

Run [VALIDATION.md](VALIDATION.md) on the full change against the owned baseline. When modifying an older version, use the complete proposed change against a baseline that predates the gate and markers so the verifier can see the required added lines. Review the result and compile and link every touched unit in the normal engine build. Require active and changed-cut evidence, all 28 single-slot probes with exact greedy parity, the multi-slot bypass and parity control, invalid-value fallback, orderly-exit counters and memory accounting. Preserve the raw evidence and label it using [METHOD.md](METHOD.md).
