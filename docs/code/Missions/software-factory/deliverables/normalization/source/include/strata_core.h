#pragma once
#include <vector>
#include <cstdint>
#include <cstddef>
namespace strata_core {
struct Routing{std::vector<int> ids;std::vector<float> weights;};
void invoke_c9b0d6f190bcc119(float*,const float*,int64_t,int64_t,float);
void rms_norm(float*,const float*,int64_t,int64_t,float);
const char* backend();
}
