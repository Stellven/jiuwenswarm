#pragma once
// Adapter for the actual planar Q2_0 ExpertJob payload in STRATA 13eedf5524.
// This does not claim to implement the rest of the model's attention/SSM graph.
#include "strata/artifact/dequant.hpp"
#include "strata/kernels/cpu/expert.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

namespace strata::kernels::ascend {
inline bool requested() {
    const char* value = std::getenv("STRATA_EXPERT_BACKEND");
    if (!value || std::string(value) == "cpu") return false;
    if (std::string(value) != "ascend") throw std::runtime_error("STRATA_EXPERT_BACKEND must be cpu or ascend");
    return true;
}
inline void activation_values(const cpu::ActQ& input, int size, float* output) {
    if (size <= 0 || size > cpu::H || size % cpu::QKA || input.nchunks != size / cpu::QKA)
        throw std::runtime_error("Ascend expert activation shape does not match ActQ chunks");
    for (int i = 0; i < size; ++i) output[i] = float(input.q[i]) * input.scale[i / cpu::QKA];
}
inline void decode_rows(const uint8_t* codes, const uint8_t* scales, int rows, int columns,
                        int row_step, int row_start, float* output) {
    if (!codes || !scales || !output || rows <= 0 || columns % cpu::QK || row_step < 1)
        throw std::runtime_error("invalid planar Q2_0 projection contract");
    const int code_bytes = columns / 4, blocks = columns / cpu::QK;
    for (int row = 0; row < rows; ++row) {
        const size_t source_row = size_t(row * row_step + row_start);
        for (int block = 0; block < blocks; ++block) {
            const float scale = strata::fp16_to_fp32(strata::read_u16(scales + (source_row * blocks + block) * 2));
            for (int j = 0; j < cpu::QK; ++j) {
                const uint8_t packed = codes[source_row * code_bytes + block * 16 + j / 4];
                output[size_t(row) * columns + block * cpu::QK + j] = float(int((packed >> (2 * (j % 4))) & 3) - 1) * scale;
            }
        }
    }
}
// Ops performs the projections and SwiGLU on its selected device. The model's
// Q8 activation boundary remains the existing STRATA quantizer, not a renamed schema.
template<class Ops>
void expert_q2(const uint8_t* blob, const cpu::ActQ& activation, float* output, Ops& ops) {
    if (!blob || !output) throw std::runtime_error("null expert input/output");
    if (cpu::expert_oracle_q8_0_enabled()) throw std::runtime_error("Ascend expert port does not support oracle Q8_0 arithmetic");
    std::vector<float> input(cpu::H), gate_weights(size_t(cpu::FF) * cpu::H),
        up_weights(size_t(cpu::FF) * cpu::H), down_weights(size_t(cpu::H) * cpu::FF),
        gate(cpu::FF), up(cpu::FF), hidden(cpu::FF), requantized(cpu::FF);
    activation_values(activation, cpu::H, input.data());
    decode_rows(blob + cpu::O_GU_CODES, blob + cpu::O_GU_SCALES, cpu::FF, cpu::H, 2, 0, gate_weights.data());
    decode_rows(blob + cpu::O_GU_CODES, blob + cpu::O_GU_SCALES, cpu::FF, cpu::H, 2, 1, up_weights.data());
    decode_rows(blob + cpu::O_D_CODES, blob + cpu::O_D_SCALES, cpu::H, cpu::FF, 1, 0, down_weights.data());
    ops.matvec(gate_weights.data(), cpu::FF, cpu::H, input.data(), gate.data());
    ops.matvec(up_weights.data(), cpu::FF, cpu::H, input.data(), up.data());
    ops.swiglu(gate.data(), up.data(), cpu::FF, hidden.data());
    cpu::ActQ intermediate;
    cpu::act_quant_q8_1(hidden.data(), cpu::FF, intermediate);
    activation_values(intermediate, cpu::FF, requantized.data());
    ops.matvec(down_weights.data(), cpu::H, cpu::FF, requantized.data(), output);
    for (int i = 0; i < cpu::H; ++i) if (!std::isfinite(output[i])) throw std::runtime_error("non-finite Ascend expert output");
}
bool compiled();
void run_expert(const uint8_t* blob, const cpu::ActQ& input, float* output);
} // namespace strata::kernels::ascend
