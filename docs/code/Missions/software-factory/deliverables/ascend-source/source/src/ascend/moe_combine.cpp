#include "strata_core.h"
#include "ascend_runtime.h"
#include <cmath>
// Source: src/kernels/cuda/shared_expert.cu sha256=8168fc598e974c423e8c09ee632d2c9fc67321b3beddcd001b4408b932ebcc79 function_sha256=7d491edf290b701705a3ea3a8d6646e6d25197891c8caaca6c3944d88d2a6cd9
namespace strata_core::ascend_detail {
void native_combine(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared){
 if(!parts||!weights||!output||d<1||d>65536||k<1||k>512||(has_shared&&!shared))throw std::invalid_argument("invalid aggregation shape");
 SessionLock lock;auto& s=lock.device;const size_t bytes=size_t(d)*sizeof(float);
 Storage p(size_t(k)*bytes),w(size_t(k)*sizeof(float)),products(p.bytes),accum(bytes),next(bytes);
 p.upload(parts,p.bytes);w.upload(weights,w.bytes);accum.zero();Tensor pt(p,{k,d}),wt(w,{k,1}),terms(products,{k,d});
 // Explicit products and ordered additions retain expert order; no matmul reassociation.
 mul(s,pt,wt,terms);Storage* current=&accum;Storage* pending=&next;
 for(int e=0;e<k;++e){Tensor a(*current,{d}),term(products,{d},ACL_FLOAT,{1},int64_t(e)*d),out(*pending,{d});add(s,a,term,out);std::swap(current,pending);}
 if(has_shared){Storage shared_values(bytes);shared_values.upload(shared,bytes);Tensor a(*current,{d}),b(shared_values,{d}),out(*pending,{d});add(s,a,b,out);std::swap(current,pending);}
 current->download(output,bytes);
}
}
