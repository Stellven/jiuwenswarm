#include "strata_core.h"
#include "ascend_runtime.h"
#include <cmath>
// Source: src/kernels/cuda/shared_expert.cu sha256=8168fc598e974c423e8c09ee632d2c9fc67321b3beddcd001b4408b932ebcc79 function_sha256=88378a953090b2e2883a557aa03f23ed21d36b7dfba99f727320031c0aab4f58
namespace strata_core::ascend_detail {
void native_swiglu(const float* gate,const float* up,float* output,int n){
 if(!gate||!up||!output||n<1||n>16777216)throw std::invalid_argument("invalid activation shape");
 SessionLock lock;auto& s=lock.device;const size_t bytes=size_t(n)*sizeof(float);
 Storage g(bytes),u(bytes),activated(bytes),result(bytes);g.upload(gate,bytes);u.upload(up,bytes);
 Tensor gt(g,{n}),ut(u,{n}),st(activated,{n}),yt(result,{n});
 run(s,"aclnnSilu",aclnnSiluGetWorkspaceSize,aclnnSilu,gt.ptr,st.ptr);
 mul(s,st,ut,yt);result.download(output,bytes);
}
}
