// No model or shard data. Submit the exact single-token routed GGML descriptors
// to the CUDA library copied from the pinned image. Nsight records only compute.
#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include "ggml-cuda.h"
#include <cuda_profiler_api.h>

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <string_view>
#include <vector>

int main(int argc, char ** argv) {
    if (argc != 2) return 2;
    const std::string_view name = argv[1];
    const bool down = name == "q2_down";
    const bool adjacent_pair = name == "iq2_adjacent_gate_up";
    const bool paired = adjacent_pair || name == "iq2_gate_up_pair";
    if (!down && !paired && name != "iq2_projection") return 2;

    constexpr int k = 4096, n = 4096, selected = 8, tokens = 1;
    constexpr int slots = 8, padded_slots = slots + 1;
    const int channels = down ? selected : 1;
    const ggml_type dtype = down ? GGML_TYPE_Q2_K : GGML_TYPE_IQ2_XXS;
    ggml_backend_t gpu = ggml_backend_cuda_init(0);
    if (!gpu) return 3;

    ggml_context * context = ggml_init({size_t(1) << 20, nullptr, true});
    ggml_tensor * bank = ggml_new_tensor_3d(context, dtype, k, n, padded_slots);
    ggml_tensor * weights = ggml_view_3d(context, bank, k, n, slots, bank->nb[1], bank->nb[2], 0);
    ggml_tensor * input = ggml_new_tensor_3d(context, GGML_TYPE_F32, k, channels, tokens);
    ggml_tensor * ids = ggml_new_tensor_2d(context, GGML_TYPE_I32, selected, tokens);
    ggml_tensor * result = ggml_mul_mat_id(context, weights, input, ids);
    ggml_cgraph * graph = ggml_new_graph(context);
    if (paired) {
        ggml_tensor * gate_bank = ggml_new_tensor_3d(context, dtype, k, n, padded_slots);
        ggml_tensor * gate = ggml_view_3d(context, gate_bank, k, n, slots, gate_bank->nb[1], gate_bank->nb[2], 0);
        ggml_tensor * gate_out = ggml_mul_mat_id(context, gate, input, ids);
        if (adjacent_pair) {
            // Resolve weight views first, so the backend can inspect adjacent MMVQ
            // nodes and GLU just as it does in a fusion-eligible split.
            ggml_build_forward_expand(graph, weights);
            ggml_build_forward_expand(graph, gate);
        }
        result = ggml_swiglu_split(context, gate_out, result);
    }
    ggml_build_forward_expand(graph, result);
    ggml_backend_buffer_t buf = ggml_backend_alloc_ctx_tensors(context, gpu);
    if (!buf || !ggml_backend_supports_op(gpu, result)) return 4;

    ggml_backend_buffer_set_usage(buf, GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
    ggml_backend_buffer_clear(buf, 0);
    const std::vector<float> x(k * channels, 1.0f);
    const std::array<int32_t, selected> routes = {7, 0, 2, 1, 4, 5, 6, 3};
    ggml_backend_tensor_set(input, x.data(), 0, x.size() * sizeof(float));
    ggml_backend_tensor_set(ids, routes.data(), 0, routes.size() * sizeof(int32_t));
    // Separate GPU setup and any allocator work from the measured dispatch.
    for (int i = 0; i < 3; ++i) {
        if (ggml_backend_graph_compute(gpu, graph) != GGML_STATUS_SUCCESS) return 5;
    }
    if (cudaProfilerStart() != cudaSuccess) return 6;
    if (ggml_backend_graph_compute(gpu, graph) != GGML_STATUS_SUCCESS) return 7;
    if (cudaProfilerStop() != cudaSuccess) return 8;

    std::vector<float> y(n * selected, 1.0f);
    ggml_backend_tensor_get(result, y.data(), 0, y.size() * sizeof(float));
    if (!std::all_of(y.begin(), y.end(), [](float v) { return v == 0.0f; })) return 9;
    std::printf("{\"case\":\"%s\",\"weight_type\":\"%s\",\"k\":%d,\"n\":%d,\"routes\":%d,"
                "\"tokens\":%d,\"operand_channels\":%d,\"bank_slots\":%d,\"row_bytes\":%zu,"
                "\"expert_bytes\":%zu,\"cuda_buffer_bytes\":%zu,\"zero_output_guard\":true}\n",
                argv[1], ggml_type_name(dtype), k, n, selected, tokens, channels, slots,
                weights->nb[1], weights->nb[2], ggml_backend_buffer_get_size(buf));
    ggml_backend_buffer_free(buf);
    ggml_free(context);
    ggml_backend_free(gpu);
}
