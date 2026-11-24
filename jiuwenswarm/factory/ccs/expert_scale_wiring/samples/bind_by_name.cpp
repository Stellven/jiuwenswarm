// SAMPLE (labelled; a generic architecture, not Muse): bind a long call to its declaration by parameter name.
// Copy the declaration's parameter names into comments next to each argument, then edit only the arguments
// whose names you mean to change. Here an arch whose loader created optional per-expert scales.
ggml_tensor * moe_out = build_moe_ffn(cur,
        /* gate_inp            */ model.layers[il].ffn_gate_inp,
        /* up_exps             */ model.layers[il].ffn_up_exps,
        /* gate_exps           */ model.layers[il].ffn_gate_exps,
        /* down_exps           */ model.layers[il].ffn_down_exps,
        /* exp_probs_b         */ nullptr,
        /* n_expert            */ n_expert,
        /* n_expert_used       */ n_expert_used,
        /* type_op             */ LLM_FFN_SILU,
        /* norm_w              */ true,
        /* w_scale             */ 1.0f,
        /* gating_op           */ LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX,
        /* il                  */ il,
        /* probs_in            */ nullptr,
        /* gate_up_exps        */ nullptr,
        /* up_exps_s           */ model.layers[il].ffn_up_exps_s,     // each projection takes ITS OWN scale
        /* gate_exps_s         */ model.layers[il].ffn_gate_exps_s,
        /* down_exps_s         */ model.layers[il].ffn_down_exps_s);  // trailing defaults left as declared
// A null scale (tensor absent from the pack) is skipped inside build_moe_ffn: the stock graph is unchanged.
// Check the overload: one variant takes biases (ggml_tensor *) where the other takes type_op.
