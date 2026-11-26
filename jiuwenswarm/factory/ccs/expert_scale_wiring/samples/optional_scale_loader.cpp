// SAMPLE (labelled; READ-ONLY reference of the stock loader pattern in src/llama-model.cpp, do not edit there):
// optional tensors are created with TENSOR_NOT_REQUIRED, so a pack that lacks them loads with nullptr.
for (int i = 0; i < n_layer; ++i) {
    auto & layer = layers[i];
    // MoE expert weight scales (per-expert, shape {n_expert}) - only where the expert weight exists
    if (!layer.ffn_gate_exps_s && layer.ffn_gate_exps) {
        layer.ffn_gate_exps_s = create_tensor(tn(LLM_TENSOR_FFN_GATE_EXPS, "scale", i), {n_expert}, TENSOR_NOT_REQUIRED);
    }
    // ... same for down and up; and "input_scale" -> ffn_*_exps_in_s
}
// Consequence for the graph: passing layer.ffn_*_exps_s is safe for every pack. With the tensor absent the
// argument is nullptr and build_moe_ffn takes the unscaled path, i.e. exactly what stock computed.
