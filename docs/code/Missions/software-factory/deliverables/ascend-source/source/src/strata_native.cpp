#include "strata_core.h"
#include <stdexcept>
namespace strata_core {
namespace ascend_detail {
void native_combine(const float*,const float*,const float*,float*,int,int,int);
Routing native_route(const std::vector<float>&,int);
void native_swiglu(const float*,const float*,float*,int);
}
Routing invoke_49ab87035bb021f7(const std::vector<float>& logits,int k){return ascend_detail::native_route(logits,k);}
Routing route(const std::vector<float>& logits,int k){return ascend_detail::native_route(logits,k);}
void invoke_82afe71f227b1515(const float* gate,const float* up,float* output,int n){ascend_detail::native_swiglu(gate,up,output,n);}
void swiglu(const float* gate,const float* up,float* output,int n){ascend_detail::native_swiglu(gate,up,output,n);}
void invoke_6f47e6c5df6f167e(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared){ascend_detail::native_combine(parts,weights,shared,output,d,k,has_shared);}
void moe_combine(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared){ascend_detail::native_combine(parts,weights,shared,output,d,k,has_shared);}
const char* backend(){return "ASCEND";}
}
