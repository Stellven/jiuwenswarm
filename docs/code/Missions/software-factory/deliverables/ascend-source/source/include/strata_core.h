#pragma once
#include <vector>
#include <cstdint>
#include <cstddef>
namespace strata_core {
struct Routing{std::vector<int> ids;std::vector<float> weights;};
Routing invoke_49ab87035bb021f7(const std::vector<float>&,int);
Routing route(const std::vector<float>&,int);
void invoke_82afe71f227b1515(const float*,const float*,float*,int);
void swiglu(const float*,const float*,float*,int);
void invoke_6f47e6c5df6f167e(const float*,const float*,const float*,float*,int,int,int);
void moe_combine(const float*,const float*,const float*,float*,int,int,int);
const char* backend();
}
