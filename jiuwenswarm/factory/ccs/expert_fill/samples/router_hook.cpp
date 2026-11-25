// SAMPLE (starting point, not the change): where the selected experts are known and the matmuls have not run.
//
// Stock 9048bad8: build_moe_ffn names the router output `ffn_moe_topk-<il>` (an I32 view [n_expert_used,
// n_tokens] of the argsort). ggml_backend_sched_compute_splits, when an eval callback is set, asks the
// callback about every node (ask=true), computes the nodes up to the first one it wants, synchronizes and then
// calls it again (ask=false) AFTER that node is computed. So:
//   - asking for ffn_moe_topk-<il> -> the callback runs after routing and BEFORE the expert MUL_MAT_IDs (good);
//   - asking for ffn_moe_{up,gate,down}-<il> or a MUL_MAT_ID node -> it runs AFTER the matmul read the pages
//     (fill too late; verify: fill_before_matmul).
// The callback slot is shared with users (llama-eval-callback, imatrix): chain, never replace.

// in the context constructor, after cparams.cb_eval is copied from the params:
//     if (gate_on) {
//         saved_cb = cparams.cb_eval; saved_ud = cparams.cb_eval_user_data;
//         cparams.cb_eval = fill_eval; cparams.cb_eval_user_data = this;
//         LLAMA_LOG_INFO("expert_fill: active threads=%d ...\n", ...);   // the one activation marker
//     }

static bool fill_eval(ggml_tensor * t, bool ask, void * ud) {
    auto * ctx  = static_cast<my_context *>(ud);
    const bool ours = ctx->fill_this_ubatch && std::strncmp(ggml_get_name(t), "ffn_moe_topk-", 13) == 0;
    if (ask) {
        return ours || (ctx->saved_cb && ctx->saved_cb(t, true, ctx->saved_ud));
    }
    if (ours) {
        ctx->fill_layer(t);                       // blocks until the reads finished
    }
    // Forward to the user's callback only for nodes it asked for. The scheduler asked once (ask=true) for the
    // union of both callbacks; re-asking here tells which one wanted this node. A callback without side effects
    // on ask=true can be re-asked safely; keep the answer from the ask pass instead if yours has them.
    if (ctx->saved_cb && ctx->saved_cb(t, true, ctx->saved_ud)) {
        return ctx->saved_cb(t, false, ctx->saved_ud);
    }
    return true;                                  // false would stop the graph
}

// ids: read with ggml_backend_tensor_get (works for host and device tensors) and index with nb[0], nb[1]; the
// tensor is a strided view. Per selected id e and per expert tensor w of the layer (ffn_up_exps, ffn_gate_exps,
// ffn_down_exps, ffn_gate_up_exps when present) the range is [w->data + e*w->nb[2], w->nb[2]). Skip w when
// w->buffer is not host (device copy) and when the address is not a file mapping (CPU_REPACK copies).
//
// decode only by default: set fill_this_ubatch = (ubatch.n_tokens <= max_tokens) in process_ubatch before
// the graph is computed (graph reuse keeps the callback installed on the scheduler).
//
// GPU arms (-ngl 99 --cpu-moe): routing runs on CUDA; the ids reach the CPU MUL_MAT_ID split as an input copy.
// The eval callback still fires after the CUDA split computed ffn_moe_topk; tensor_get syncs. Expect a graph
// split per MoE layer (there already is one with --cpu-moe) - measure, do not assume it is free.
