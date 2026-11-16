#pragma once
#include <vector>
#include <cstdint>
#include <cstddef>
namespace strata_core {
struct Routing{std::vector<int> ids;std::vector<float> weights;};
Routing invoke_49ab87035bb021f7(const std::vector<float>&,int);
Routing route(const std::vector<float>&,int);
void invoke_99a12ae78535eaee(float* x, int64_t n, float s);
void scale_kernel(float* x, int64_t n, float s);
const char* backend();
}
